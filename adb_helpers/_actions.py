"""Action command processing: parse and execute tap/wait/swipe from text."""

import os
import re
import time

from util import console_log_with_ign

from adb_helpers._input import _do_swipe, do_tap
from adb_helpers._screen import coords_to_pixels, parse_coord_tokens

HERE = os.path.dirname(os.path.dirname(__file__))


# Shared implementation for processing action lines from any iterable
def _process_action_lines(
    device,
    lines,
    width: int,
    height: int,
    ign="",
    dry_run: bool = False,
    debug: bool = False,
):
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("tap"):
            try:
                rest = line[len("tap") :].strip()
                x, y = parse_coord_tokens(rest)

                do_tap(device, (x, y), width=width, height=height, ign=ign, dry_run=dry_run, debug=debug)

            except Exception as e:
                console_log_with_ign(ign, f"failed to process tap line '{line}': {e}")
        elif line.lower().startswith("wait"):
            try:
                nums = re.findall(r"\d+", line)
                if not nums:
                    continue
                ms = int(nums[0])
                if debug:
                    console_log_with_ign(ign, f"[DEBUG] WAIT: {ms} ms")
                if not dry_run:
                    time.sleep(ms / 1000.0)
            except Exception as e:
                console_log_with_ign(ign, f"failed to process wait line '{line}': {e}")
        elif line.lower().startswith("swipe"):
            try:
                rest = line[len("swipe") :].strip()
                parts = rest.split()
                if len(parts) < 2:
                    raise ValueError("not enough arguments for swipe")
                x1f, y1f = parse_coord_tokens(parts[0])
                x2f, y2f = parse_coord_tokens(parts[1])
                duration_ms = 300
                if len(parts) >= 3:
                    nums = re.findall(r"\d+", parts[2])
                    if nums:
                        duration_ms = int(nums[0])

                x1_px, y1_px = coords_to_pixels(x1f, y1f, width, height)
                x2_px, y2_px = coords_to_pixels(x2f, y2f, width, height)
                if debug:
                    console_log_with_ign(ign, f"[DEBUG] SWIPE: {x1f},{y1f} -> {x1_px},{y1_px}  to {x2f},{y2f} -> {x2_px},{y2_px} dur={duration_ms}ms")
                _do_swipe(
                    device,
                    x1_px,
                    y1_px,
                    x2_px,
                    y2_px,
                    duration_ms,
                    dry_run=dry_run,
                )
            except Exception as e:
                console_log_with_ign(ign, f"failed to process swipe line '{line}': {e}")
        else:
            console_log_with_ign(ign, f"unknown line (skipped): {line}")


# Variant: process action commands from a string (content) instead of a file path
def process_action_command(
    device,
    content: str,
    width: int = 1920,
    height: int = 1080,
    dry_run: bool = False,
    ign: str = "player",
    remarks: str = "",
    debug: bool = False,
):

    if remarks:
        console_log_with_ign(ign, f"--- {remarks} ---")

    if content == "GO_STARTING_POINT":
        content = """tap  97.7991 1.99147
                    wait 1000
                    tap  49.98 76.1735
                    wait 3000"""

    if content == "CLOSE_MAP":
        content = """#close map
            tap 89.4758 11.6643
            wait 1000"""

    if content == "OPEN_MAP":
        content = """# tap to remove any dialog-boxes
tap 83.7961 18.5567
wait 100
tap 83.7961 18.5567
wait 100

# tap to map
tap 92.9963 12.8866
wait 500"""

    if content == "RANDOM_LOCATION":
        content = """tap 86.407 85.2725
wait 200
"""

    _process_action_lines(
        device,
        content.splitlines(),
        width=width,
        height=height,
        dry_run=dry_run,
        ign=ign,
    )
