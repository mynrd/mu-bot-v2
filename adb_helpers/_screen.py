"""Screen capture and coordinate conversion utilities."""

import re
import struct
import time
from pathlib import Path
from typing import Tuple, Union

import subprocess
from image_helpers import ImageLike
from util import console_log_with_ign

from adb_helpers._core import retry_on_timeout, run_adb_cmd

try:
    from PIL import Image
except Exception:
    Image = None


def get_screen_size(device, dry_run: bool = False) -> Tuple[int, int]:
    """Return (width, height) in pixels for the device.

    Uses `adb shell wm size` and parses the output. If dry_run is True, returns
    a sensible default (1080x1920).
    """
    code, out, err = run_adb_cmd(device, ["shell", "wm", "size"], dry_run=dry_run)
    if dry_run:
        return 1080, 1920
    if code != 0:
        raise RuntimeError(f"adb wm size failed: {err or out}")
    m = re.search(r"(\d+)x(\d+)", out)
    if not m:
        raise RuntimeError(f"unable to parse screen size from: {out}")
    return int(m.group(1)), int(m.group(2))


def _coord_to_px(value: Union[float, int], total: int) -> int:
    """Convert a coordinate given either as a fraction (0.0-1.0) or absolute pixels.

    - If value is a float between 0 and 1, it's treated as a percentage of total.
    - If value is an int (or a float >= 1), it's treated as absolute pixels.
    """
    if isinstance(value, float) and 0.0 < value <= 1.0:
        return int(value * total)
    try:
        iv = int(value)
        return iv
    except Exception:
        raise ValueError(f"invalid coordinate value: {value}")


def coords_to_pixels(
    x: float,
    y: float,
    width: int = 1920,
    height: int = 1080,
    mode: str = "auto",  # 'px' | 'pct' | 'norm' | 'auto'
) -> Tuple[int, int]:
    if mode == "px":
        return int(round(x)), int(round(y))
    if mode == "pct":
        return int(round(x / 100.0 * width)), int(round(y / 100.0 * height))
    if mode == "norm":
        return int(round(x * width)), int(round(y * height))

    # auto (backward-compatible heuristics)
    if x <= 1 and y <= 1:
        return int(round(x * width)), int(round(y * height))
    if x <= 100 and y <= 100:
        return int(round(x / 100.0 * width)), int(round(y / 100.0 * height))
    return int(round(x)), int(round(y))


def coords_to_percents(x: float, y: float, width: int = 1920, height: int = 1080) -> Tuple[float, float]:
    """Convert absolute pixel coordinates to percentages (0.0-100.0)."""
    return (x / width) * 100, (y / height) * 100


def parse_coord_tokens(s: str):
    nums = re.findall(r"-?\d+\.?\d*", s)
    if len(nums) < 2:
        raise ValueError(f"couldn't find two coordinates in '{s}'")
    return float(nums[0]), float(nums[1])


def grab_raw_rgba(device: str, ign: str = "", debug: bool = False) -> ImageLike:
    for attempt in range(3):
        try:
            # screencap (no -p) => [w,h,fmt] little-endian ints + w*h*4 RGBA
            proc = retry_on_timeout(subprocess.run, ["adb", "-s", device, "exec-out", "screencap"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=10)
            data = proc.stdout
            w, h, fmt = struct.unpack_from("<III", data, 0)
            pixels = data[12 : 12 + (w * h * 4)]
            img = Image.frombytes("RGBA", (w, h), pixels)
            if debug:
                console_log_with_ign(ign, f"[DEBUG] grab_raw_rgba: {w}x{h}, fmt={fmt}, data size={len(data)}, pixels size={len(pixels)}")
                # save the file
                temp_path = Path(f"temp/{ign}_screenshot_raw_rgba.png")
                temp_path.parent.mkdir(parents=True, exist_ok=True)
                img.save(temp_path)
                console_log_with_ign(ign, f"[DEBUG] grab_raw_rgba: saved screenshot to {temp_path}")

            return img  # PIL.Image in memory (no disk I/O)
        except Exception:
            if attempt < 2:
                time.sleep(0.3)
                continue
            raise
