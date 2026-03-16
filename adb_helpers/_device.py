"""Device management: connect, disconnect, open/close apps."""

import subprocess
import time

from util import console_log_with_ign

from adb_helpers._core import retry_on_timeout, run_cmd


def disconnect(device: str, dry_run: bool = False, ign: str = "player") -> bool:
    """
    Disconnects an ADB device (works for TCP/IP connections).

    Args:
        device (str): Device identifier (e.g., 'emulator-5554' or '192.168.1.5:5555').
        dry_run (bool): If True, print the command instead of executing.

    Returns:
        bool: True if disconnect succeeded (or dry run), False otherwise.
    """
    cmd = ["adb", "disconnect", device]

    if dry_run:
        console_log_with_ign(ign, "[DRY RUN] Would run:", " ".join(cmd))
        return True

    try:
        result = retry_on_timeout(subprocess.run, cmd, capture_output=True, text=True, check=True, timeout=10)
        console_log_with_ign(ign, "ADB disconnect output:", result.stdout.strip())
        return True
    except subprocess.CalledProcessError as e:
        console_log_with_ign(ign, "ADB disconnect failed:", e.stderr.strip())
        return False


def ensure_connected(device: str, dry_run: bool = False, timeout_s: int = 5, ign: str = "player") -> None:
    if dry_run:
        console_log_with_ign(ign, f"DRY RUN: would run: adb devices")
        console_log_with_ign(ign, f"DRY RUN: would run: adb connect {device}")
        return

    code, out, err = run_cmd(["devices"])  # type: ignore
    if code != 0:
        raise RuntimeError(f"adb devices failed: {err or out}")

    # parse lines like: '127.0.0.1:5575\tdevice' or 'emulator-5554\tdevice'
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    connected = False
    for l in lines:
        if "\tdevice" in l and l.split()[0] == device:
            connected = True
            break

    if connected:
        console_log_with_ign(ign, f"Device {device} is already connected.")
        return

    # attempt to connect
    code, out, err = run_cmd(["connect", device])
    if code != 0:
        raise RuntimeError(f"adb connect failed: {err or out}")

    # wait briefly and re-check
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        code, out, err = run_cmd(["devices"])  # type: ignore
        if code == 0 and any((l.strip() and "\tdevice" in l and l.split()[0] == device) for l in out.splitlines()):
            console_log_with_ign(ign, f"Device {device} connected.")
            return
        time.sleep(0.2)

    raise RuntimeError(f"device {device} not listed after adb connect")


def ensure_device_connected(device: str, timeout_s: int = 5, dry_run: bool = False) -> None:
    return ensure_connected(device, dry_run=dry_run, timeout_s=timeout_s)


def close_app(device: str, package_name: str = "com.tszz.gpsea", dry_run: bool = False, ign="player") -> bool:
    cmd = ["adb", "-s", device, "shell", "am", "force-stop", package_name]

    if dry_run:
        console_log_with_ign(ign, "[DRY RUN] Would run:", " ".join(cmd))
        return True

    try:
        retry_on_timeout(subprocess.run, cmd, check=True, capture_output=True, text=True, timeout=10)
        return True
    except subprocess.CalledProcessError as e:
        console_log_with_ign(ign, "Failed to close app:", e.stderr.strip())
        return False


def open_app(device: str, package_name: str, dry_run: bool = False, ign="player") -> bool:
    cmd = ["adb", "-s", device, "shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"]

    if dry_run:
        console_log_with_ign(ign, "[DRY RUN] Would run:", " ".join(cmd))
        return True

    try:
        retry_on_timeout(subprocess.run, cmd, check=True, capture_output=True, text=True, timeout=10)
        return True
    except subprocess.CalledProcessError as e:
        console_log_with_ign(ign, "Failed to open app:", e.stderr.strip())
        return False


def check_if_app_is_open(device: str, ign: str, debug=False, package_name="com.tszz.gpsea") -> bool:
    """
    Check if com.tszz.gpsea is the current focused app on the device.

    Args:
        device (str): adb device id (example: "127.0.0.1:5605")

    Returns:
        bool: True if app is open/focused, False otherwise
    """

    try:
        # Run adb command
        if debug:
            console_log_with_ign(ign, f"Checking if {package_name} is the current focused app on device {device}...")
        result = retry_on_timeout(subprocess.run, ["adb", "-s", device, "shell", "dumpsys", "window"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, timeout=10)

        # Look for mCurrentFocus line and check if package is inside
        for line in result.stdout.splitlines():
            if "mCurrentFocus" in line and package_name in line:
                if debug:
                    console_log_with_ign(ign, f"{package_name} is currently the focused app.")
                return True
        return False

    except subprocess.CalledProcessError as e:
        print(f"Error running adb: {e.stderr}")
        return False
