"""Basic input actions: tap, swipe, clear screen."""

import time
from typing import Optional, Tuple, Union

from util import console_log_with_ign

from adb_helpers._core import run_adb_cmd
from adb_helpers._screen import _coord_to_px, coords_to_pixels, get_screen_size

DEFAULT_REGION_HALF_SIZE = 10

def _do_swipe(
    device,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    duration_ms: int = 300,
    dry_run: bool = False,
) -> int:
    """Perform a generic swipe from (x1,y1) to (x2,y2) with duration in ms.

    Coordinates must be pixel values.
    """
    args = ["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)]
    code, out, err = run_adb_cmd(device, args, dry_run=dry_run)
    if code != 0:
        raise RuntimeError(f"adb swipe failed: {err or out}")
    return code


def swipe_up(
    device,
    start: Optional[Tuple[Union[float, int], Union[float, int]]] = None,
    end: Optional[Tuple[Union[float, int], Union[float, int]]] = None,
    duration_ms: int = 300,
    dry_run: bool = False,
    andPause: bool = False,
) -> int:
    """Perform a swipe up gesture.

    Defaults are percent-based and should work on most devices:
    - start defaults to (0.5, 0.8) -> middle, near bottom
    - end defaults to (0.5, 0.3)   -> middle, higher up

    You can pass absolute pixel coords too, e.g. start=(540,1600).
    If andPause is True, will tap at end coordinate to stop scrolling momentum.
    """
    w, h = get_screen_size(device, dry_run=dry_run)
    if start is None:
        start = (0.5, 0.8)
    if end is None:
        end = (0.5, 0.3)
    x1 = _coord_to_px(start[0], w)
    y1 = _coord_to_px(start[1], h)
    x2 = _coord_to_px(end[0], w)
    y2 = _coord_to_px(end[1], h)
    args = ["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)]
    code, out, err = run_adb_cmd(device, args, dry_run=dry_run)
    if code != 0:
        raise RuntimeError(f"adb swipe failed: {err or out}")

    # If andPause is True, hold at end coordinate to stop momentum scrolling
    if andPause and not dry_run:
        hold_args = ["shell", "input", "swipe", str(x2), str(y2), str(x2 + 200), str(y2), "100"]
        run_adb_cmd(device, hold_args, dry_run=dry_run)

    return code


def swipe_down(
    device,
    start: Optional[Tuple[Union[float, int], Union[float, int]]] = None,
    end: Optional[Tuple[Union[float, int], Union[float, int]]] = None,
    duration_ms: int = 300,
    dry_run: bool = False,
    andPause: bool = False,
) -> int:
    """Perform a swipe down gesture.

    Defaults are the inverse of swipe_up:
    - start defaults to (0.5, 0.3) -> middle, higher up
    - end defaults to (0.5, 0.8)   -> middle, near bottom
    If andPause is True, will tap at end coordinate to stop scrolling momentum.
    """
    w, h = get_screen_size(device, dry_run=dry_run)
    if start is None:
        start = (0.5, 0.3)
    if end is None:
        end = (0.5, 0.8)
    x1 = _coord_to_px(start[0], w)
    y1 = _coord_to_px(start[1], h)
    x2 = _coord_to_px(end[0], w)
    y2 = _coord_to_px(end[1], h)
    args = ["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)]
    code, out, err = run_adb_cmd(device, args, dry_run=dry_run)
    if code != 0:
        raise RuntimeError(f"adb swipe failed: {err or out}")

    # If andPause is True, hold at end coordinate to stop momentum scrolling
    if andPause and not dry_run:
        hold_args = ["shell", "input", "swipe", str(x2), str(y2), str(x2), str(y2), "100"]
        run_adb_cmd(device, hold_args, dry_run=dry_run)

    return code


def do_tap(
    device: str,
    coords: Union[Tuple[Union[int, float], Union[int, float]], list],
    width: int = 1920,
    height: int = 1080,
    ign: str = "player",
    mode: str = "auto",  # 'px' | 'pct' | 'norm' | 'auto'
    dry_run: bool = False,
    remarks: str = "",
    debug: bool = False,
) -> int:
    if not (isinstance(coords, (tuple, list)) and len(coords) == 2):
        raise TypeError("coords must be a tuple or list of two numbers (x, y)")

    import inspect, os
    frame = inspect.stack()[1]
    caller = f"{os.path.basename(frame.filename)}:{frame.lineno}"
    console_log_with_ign(ign, f"[{caller}] - Tapping at {coords} (mode={mode})")

    if remarks:
        console_log_with_ign(ign, f"Remarks: {remarks}")

    x, y = coords
    x_px, y_px = coords_to_pixels(x, y, width, height, mode=mode)

    if debug:
        console_log_with_ign(ign, f"[DEBUG] TAP: {x},{y} -> {x_px},{y_px}")

    args = ["shell", "input", "tap", str(x_px), str(y_px)]
    code, out, err = run_adb_cmd(device, args, dry_run=dry_run)
    if code != 0:
        raise RuntimeError(f"adb tap failed: {err or out}")
    return code


def do_clear_screen(device: str, dry_run: bool = False, click_x=False, ign: str = "", debug: bool = False) -> None:
    # two quick taps on the first coordinate, then two on the second (keeps original timing)
    if debug:
        console_log_with_ign(ign, "[DEBUG] Clearing screen by tapping twice on two coordinates...")
    # Coordinates to tap (keeps original two-tap pattern for each coord)
    coords = [(35.36, 99.0754), (38.48, 98.7909)]

    if click_x:
        do_tap(device, (87.5901, 15.1494), ign=ign, dry_run=dry_run, remarks="Initial tap to clear dialogs", debug=debug)

    for coord in coords:
        # perform two quick taps at each coordinate with the original pacing
        for _ in range(2):
            do_tap(device, coord, ign=ign, dry_run=dry_run, debug=debug)
            time.sleep(0.1)
