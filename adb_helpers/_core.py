"""Core ADB command execution: retry logic, run_cmd, build/run helpers."""

import os
import shlex
import subprocess
import subprocess as _subprocess
import time as _time
from typing import List, Tuple

from util import console_log_with_ign

HERE = os.path.dirname(os.path.dirname(__file__))


def _is_transient_adb_error(stderr_text: str) -> bool:
    s = (stderr_text or "").lower()
    return any(
        t in s
        for t in [
            "device not found",
            "no devices/emulators found",
            "device offline",
            "error: closed",
            "cannot connect",
            "more than one device/emulator",
        ]
    )


def retry_on_timeout(func, *args, retries: int = 3, retry_delay: float = 1.0, ign: str = "player", device: str | None = None, **kwargs):
    """
    Retry a callable if it times out OR hits transient ADB failures.
    Example:
        proc = retry_on_timeout(
            _subprocess.run,
            ["adb","-s", device, "exec-out","screencap","-p"],
            stdout=_subprocess.PIPE, stderr=_subprocess.PIPE,
            check=True, timeout=12,
            device=device, ign=IGN, retries=2, retry_delay=0.5
        )
    """
    from adb_helpers._device import ensure_device_connected

    attempt = 0
    while True:
        try:
            return func(*args, **kwargs)
        except _subprocess.TimeoutExpired as e:
            attempt += 1
            if attempt > retries:
                raise
            console_log_with_ign(ign, f"[retry {attempt}/{retries}] ADB command timed out; retrying...")
            # try to (re)connect if we can
            if device and ensure_device_connected:
                try:
                    ensure_device_connected(device)
                except Exception as ee:
                    console_log_with_ign(ign, f"ensure_device_connected failed (timeout path): {ee}")
            _time.sleep(retry_delay)

        except _subprocess.CalledProcessError as e:
            # Only retry for transient ADB states; otherwise re-raise.
            err_text = ""
            try:
                if isinstance(e.stderr, (bytes, bytearray)):
                    err_text = e.stderr.decode(errors="ignore")
                elif isinstance(e.stderr, str):
                    err_text = e.stderr
            except Exception:
                pass

            if _is_transient_adb_error(err_text) and attempt < retries:
                attempt += 1
                console_log_with_ign(ign, f"[retry {attempt}/{retries}] Transient ADB error: {err_text.strip() or e}. Retrying...")
                if device and ensure_device_connected:
                    try:
                        ensure_device_connected(device)
                    except Exception as ee:
                        console_log_with_ign(ign, f"ensure_device_connected failed (error path): {ee}")
                _time.sleep(retry_delay)
                continue

            # not transient or out of retries
            raise


def run_cmd(cmd: List[str], debug=False) -> Tuple[int, str, str]:
    # Minimal local copy of run_cmd used by helpers; callers can pass through their own if desired.
    try:
        # Accept either a full command (starting with 'adb') or a shorthand like ['devices']
        # If the caller already provided 'adb' as the first token, don't prepend it again.
        if cmd and cmd[0] == "adb":
            cmds = cmd
        else:
            cmds = ["adb"] + cmd

        if debug:
            console_log_with_ign("player", "RUN CMD:", " ".join(shlex.quote(p) for p in cmds))
        p = retry_on_timeout(subprocess.run, cmds, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False, timeout=10)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except FileNotFoundError as e:
        return 1, "", str(e)
    except Exception as e:
        # print cmd
        print("Error running command:", " ".join(shlex.quote(p) for p in cmd), e)
        raise


def build_adb_cmd(device, *args: str) -> List[str]:
    """Build an adb command list, e.g. [adb, -s device, ...args].

    If device are None, they should be resolved by callers.
    """
    cmd = ["adb"]
    if device:
        cmd += ["-s", device]
    cmd += list(args)
    return cmd


def run_adb_cmd(device, args: List[str], dry_run: bool = False, ign="player") -> Tuple[int, str, str]:
    """Run an adb command resolving device from config/env.

    args: list of adb arguments (e.g. ["shell", "input", "tap", "x", "y"]) without the adb binary.
    """
    cmd = build_adb_cmd(device, *args)
    if dry_run:
        console_log_with_ign(ign, "DRY RUN: ", " ".join(shlex.quote(p) for p in cmd))
        return 0, "", ""
    return run_cmd(cmd)
