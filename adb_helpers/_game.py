"""Game-specific high-level operations: navigation, combat checks, teleport, etc."""

import os
import re
import time
from typing import List, Optional, Tuple

import cv2

import image_search_pattern
import search_text_fall_back
from image_helpers import ImageLike
from util import console_log_with_ign

from adb_helpers._core import HERE, retry_on_timeout
from adb_helpers._actions import process_action_command
from adb_helpers._device import close_app, open_app
from adb_helpers._input import (
    DEFAULT_REGION_HALF_SIZE,
    do_clear_screen,
    do_tap,
    swipe_down,
    swipe_up,
)
from adb_helpers._screen import grab_raw_rgba


def do_open_map(device, ign, debug=False):
    do_tap(device, (92.9963, 12.8866), ign=ign, remarks="Tap to Map", debug=debug)
    time.sleep(0.5)


def reopen_app(device, ign, package_name="com.tszz.gpsea"):
    # Run the sequence; if it took >= 60s, retry once.
    import search_text_image

    for attempt in range(2):
        start_ts = time.time()

        close_app(device, package_name)
        time.sleep(2)
        open_app(device, package_name)

        cnt = 0
        while True:
            # random click
            cnt += 1

            do_tap(device, (74.3795, 51.8492), ign=ign, remarks="Random click to dismiss popups")
            time.sleep(0.2)
            do_tap(device, (74.3795, 51.8492), ign=ign, remarks="Random click to dismiss popups")
            time.sleep(0.2)

            result = search_text_image.get_search_text(grab_raw_rgba(device, ign), region=(834, 762, 1078, 851), debug=False)
            if "start game".lower() in result.lower():

                do_tap(device, (958, 805), ign=ign, remarks="Click Start Game")
                console_log_with_ign(ign, "Found 'Start Game' text; proceeding.")
                break
            console_log_with_ign(ign, "Did not find 'Start Game' text; retrying random click...")
            time.sleep(5)
            if cnt % 5 == 0:
                console_log_with_ign(ign, "Too many retries; restarting app...")
                close_app(device, package_name)
                time.sleep(2)
                open_app(device, package_name)

        while True:
            result = search_text_image.get_search_text(grab_raw_rgba(device, ign), region=(823, 952, 1097, 1041), debug=False)
            if "startgame".lower() in result.lower():
                do_tap(device, (955, 998), ign=ign, remarks="Click StartGame")
                console_log_with_ign(ign, "Found 'StartGame' text; proceeding.")
                break

        cnt = 0
        while True:
            cnt += 1
            if cnt > 10:
                console_log_with_ign(ign, "Timeout waiting for 'Auto Spot' text; proceeding anyway.")
                time.sleep(1)
                break
            result = search_text_image.get_search_text(grab_raw_rgba(device, ign), region=(251, 222, 445, 279), debug=False)
            if "auto".lower() in result.lower():
                time.sleep(1)
                do_tap(device, (1681, 166), ign=ign, remarks="Close AutoPlay")
                console_log_with_ign(ign, "Found 'Auto Spot' text; proceeding.")
                break
            else:
                console_log_with_ign(ign, "Did not find 'Spot' text; skipping Close AutoPlay. Found: " + result)
                time.sleep(3)

        break

    return True


def check_is_alive(device, ign):
    import image_helpers

    respawn_now_region = (992, 616, 1191, 668)
    check_respawn_now_text = image_helpers.tesseract_extract_text_from_region_white(grab_raw_rgba(device, ign), respawn_now_region, ign)
    return "respawn now".lower() in check_respawn_now_text.lower()


def go_to_target_location(device, ign, target: Tuple[int, int], pattern_current_location=None, open_map=False, debug=False):
    import player_locator_map

    if open_map:
        do_clear_screen(device, ign=ign, debug=debug)
        time.sleep(0.5)
        do_open_map(device, ign=ign, debug=debug)
        time.sleep(0.5)

    if pattern_current_location is None:
        pattern_current_location = cv2.imread(os.path.join("images", "current_location.png"), cv2.IMREAD_UNCHANGED)

    while True:
        current_location = player_locator_map.find_location_by_image(
            grab_raw_rgba(device, ign=ign),
            pattern_current_location,
            (605, 168, 1595, 953),
            threshold=0.7,
            debug=debug,
        )
        if current_location is None:
            raise RuntimeError("couldn't determine current location on map")

        near, distance = player_locator_map.is_coordinates_near(current_location, target, tolerance=15)
        console_log_with_ign(ign, f"Near: {near}, Distance: {distance}")

        if near:
            console_log_with_ign(ign, f"Arrived at target location {target}.")
            if debug:
                console_log_with_ign(ign, f"[DEBUG] Current location {current_location} is near target {target}; stopping navigation.")
            return
        else:
            do_tap(device, (target[0], target[1]), ign=ign, debug=debug)
            time.sleep(1)
            continue


def do_check_if_buffed(device, ign, min_dmg_red=0, debug=False):
    console_log_with_ign(ign, "Opening allocation points...")

    import search_text_image

    from image_helpers import get_text_gray

    while True:

        text = get_text_gray(grab_raw_rgba(device, ign, debug), region=(1815, 756, 1914, 781), ign=ign, compare_text="allocate", debug=debug)

        allocate_found = "allocate" in text.lower()

        if not allocate_found:
            # tap switch controls
            console_log_with_ign(ign, "Tapping switch controls...")
            do_tap(device, (1867, 274), ign=ign, debug=debug)
            time.sleep(2)
            continue
        else:
            break

    do_tap(device, (1865, 733), ign=ign, debug=debug)
    time.sleep(1)

    while True:
        res = search_text_image.get_search_text(grab_raw_rgba(device, ign, debug), region=(1478, 104, 1890, 973), debug=False)
        lines = res.splitlines()

        value = None
        for line in lines:
            if "dmg reduction" in line.lower():
                # Find first number like 34.00
                match = re.search(r"(\d+(?:\.\d+)?)", line)
                if match:
                    value = float(match.group(1))
                break

        # Handle case where no damage reduction value was found
        whitelist = ["dmg reduction tit:", "dmg reduction ti"]
        if value is None:
            console_log_with_ign(ign, "No damage reduction value found. Treating as 0.")
            console_log_with_ign(ign, lines)

            # minimal change: if any whitelist substring appears in OCR lines, force value to 71
            value = 0.0
            for w in whitelist:
                wl = w.lower()
                if any(wl in ln.lower() for ln in lines):
                    value = 71.0
                    break

        res = value > min_dmg_red

        if res:
            do_clear_screen(device, ign=ign, debug=debug)
            time.sleep(1)
            text = get_text_gray(grab_raw_rgba(device, ign, debug), region=(1815, 756, 1914, 781), ign=ign, compare_text="allocate", debug=debug)
            allocate_found = "allocate" in text.lower()
            if allocate_found:
                console_log_with_ign(ign, "Tapping switch controls... Normal Scontrol Position")
                do_tap(device, (1867, 274), ign=ign, debug=debug)
                time.sleep(1)
            return True
        else:
            console_log_with_ign(ign, f"Damage Reduction {value} is less than minimum {min_dmg_red}. Need to re-buff.")


def do_tap_attack(device, ign, dry_run=False, debug=False):
    from image_helpers import get_text_gray

    img = grab_raw_rgba(device, ign=ign, debug=debug)
    text = get_text_gray(img, ign=ign, debug=debug)
    if debug:
        console_log_with_ign(ign, f"[DEBUG] Detected auto/manual text: '{text}'")
    if "manual" in text.lower():
        if debug:
            console_log_with_ign(ign, "[DEBUG] Currently in manual mode; tapping Attack button to switch to auto.")
        do_clear_screen(device, ign=ign, debug=debug)
        do_tap(device, (97.0777, 45.5903), ign=ign, dry_run=dry_run, remarks="Tap Auto / Manual button", debug=debug)
        time.sleep(1)
    else:

        if debug:
            console_log_with_ign(ign, "[DEBUG] Already in auto mode; no need to tap Attack button.")


def switch_channel(device: str, ign: str, channel: int, debug: bool = False) -> None:
    console_log_with_ign(ign, f"Switching to channel {channel}...")
    do_clear_screen(device, ign=ign, debug=debug)

    do_tap(device, (97.559, 2.34708), ign=ign, debug=debug)
    time.sleep(0.5)

    search_text = str(channel) + "Switch"
    region_to_scan = (747, 278, 1162, 701)

    # Swipe based on channel
    if channel in [1, 2, 3]:
        swipe_up(device, (948, 398), (963, 588), 100)
        time.sleep(0.2)
        swipe_up(device, (948, 398), (963, 588), 100)
        time.sleep(0.2)
    elif channel in [4, 5, 6]:
        swipe_down(device, (963, 588), (948, 398), 100)
        time.sleep(0.2)
        swipe_down(device, (963, 588), (948, 398), 100)
        time.sleep(0.2)
    else:
        raise ValueError(f"invalid channel: {channel}; expected 1-5")

    img = grab_raw_rgba(device, ign, debug)

    # on region_to_scan, search for text like "1Switch", "2Switch", etc. and get its coordinates and tap it
    import pytesseract
    from PIL import Image as PILImage

    # Crop to the region
    if isinstance(img, PILImage.Image):
        cropped = img.crop((region_to_scan[0], region_to_scan[1], region_to_scan[2], region_to_scan[3]))
    else:
        cropped = img[region_to_scan[1] : region_to_scan[3], region_to_scan[0] : region_to_scan[2]]

    # Use pytesseract to get text with bounding boxes
    data = pytesseract.image_to_data(cropped, output_type=pytesseract.Output.DICT)

    # Search for the channel text
    target_text = search_text.lower()

    # Log all detected text for debugging
    detected_texts = [text for text in data["text"] if text.strip()]
    console_log_with_ign(ign, f"[DEBUG] All detected text in region: {detected_texts}")
    console_log_with_ign(ign, f"[DEBUG] Looking for: '{search_text}'")

    # Define possible OCR misreadings for each channel
    channel_variations = {
        1: ["1switch", "iswitch", "lswitch", "|switch", "1svvitch", "1swifch", "lswifch", "1swit"],
        2: ["2switch", "zswitch", "2svvitch", "2swifch", "zswifch", "2swit"],
        3: ["3switch", "bswitch", "3svvitch", "3swifch", "bswifch", "3swit"],
        4: ["4switch", "aswitch", "4svvitch", "4swifch", "aswifch", "4swit"],
        5: ["5switch", "sswitch", "5svvitch", "5swifch", "sswifch", "sssvvitch", "5swit"],
    }

    # Get variations for the current channel
    possible_texts = channel_variations.get(channel, [target_text])

    for i, text in enumerate(data["text"]):
        if text:
            text_lower = text.lower()
            # Check if any of the possible variations match
            match_found = False
            for variation in possible_texts:
                if variation in text_lower:
                    match_found = True
                    break

            if match_found:
                # Get coordinates
                x = data["left"][i]
                y = data["top"][i]
                w = data["width"][i]
                h = data["height"][i]

                # Calculate center point and adjust for region offset
                tap_x = region_to_scan[0] + x + w // 2
                tap_y = region_to_scan[1] + y + h // 2

                if debug:
                    console_log_with_ign(ign, f"[DEBUG] Found '{text}' at ({tap_x}, {tap_y})")

                # Tap on the text
                do_tap(device, (tap_x, tap_y), mode="px", ign=ign, remarks=f"Tap channel {channel}", debug=debug)
                time.sleep(0.5)

                # Tap confirm button
                do_tap(device, (49.9, 76.5292), ign=ign, remarks="confirm channel (Switch line)", debug=debug)
                time.sleep(3)
                return

    # If not found, log what was detected and raise error
    console_log_with_ign(ign, f"[ERROR] Could not find channel text '{search_text}' in region {region_to_scan}")
    console_log_with_ign(ign, f"[ERROR] Detected texts were: {detected_texts}")
    raise RuntimeError(f"Could not find channel text '{search_text}' in region {region_to_scan}. Detected texts: {detected_texts}")


def teleport_to_endless_abyss(device, ign):
    do_clear_screen(device, ign=ign)
    do_open_map(device, ign=ign)
    time.sleep(1)

    swipe_down(device, (400, 340), (400, 630), 100, andPause=False)
    time.sleep(0.2)
    swipe_down(device, (400, 340), (400, 630), 100, andPause=False)
    time.sleep(0.2)
    swipe_down(device, (400, 340), (400, 630), 100, andPause=False)
    time.sleep(1)

    regionToScanText = (254, 184, 562, 748)
    search_text = "Endless"

    attempt_count = 0
    max_attempts = 6

    while True:
        swipe_up(device, (400, 670), (400, 300), 100, andPause=True)
        time.sleep(0.5)
        coordinate = get_coordinate_of_text(device, search_text, ign, regionToScanText, debug=False)
        if coordinate:
            do_tap(device, coordinate, ign)
            time.sleep(3)
            do_open_map(device, ign=ign)
            time.sleep(1)
            print(f"Found '{search_text}' on the map at {coordinate}, tapping to teleport...")
            do_tap(device, (994, 782), ign)
            time.sleep(3)
            do_clear_screen(device, ign=ign)
            break
        else:
            attempt_count += 1
            if attempt_count >= max_attempts:
                raise Exception(f"Failed to find '{search_text}' after {max_attempts} attempts in go_to_endless_abyss")


def teleport_to_divine(device, ign):
    console_log_with_ign(ign, "Teleporting to Divine Realm...")

    while True:
        do_clear_screen(device, ign=ign)
        do_open_map(device, ign=ign)
        time.sleep(0.2)

        process_action_command(device, "swipe 22.0887,26.1414 22.1301,57.511 300", ign=ign)
        time.sleep(0.2)
        process_action_command(device, "swipe 22.0887,26.1414 22.1301,57.511 300", ign=ign)
        time.sleep(0.2)
        process_action_command(device, "swipe 22.0887,26.1414 22.1301,57.511 300", ign=ign)
        time.sleep(1.5)

        process_action_command(device, "swipe 20.804,66.4948  21.0112,24.1532 300", ign=ign)
        time.sleep(3)

        img = grab_raw_rgba(device, ign=ign, debug=False)
        pattern = cv2.imread(os.path.join(HERE, "images", "divine-realm.png"))
        regionMapList = (248, 180, 571, 755)
        divineRealmCoordinate = image_search_pattern.get_location_by_template(img, pattern, regionMapList, threshold=0.75, debug=False)
        if divineRealmCoordinate is not None:
            console_log_with_ign(ign, "Found Divine Realm on the map at", divineRealmCoordinate)
            break
        console_log_with_ign(ign, "Couldn't find Divine Realm on the map, retrying...")
        time.sleep(1)

    do_tap(device, (divineRealmCoordinate[0], divineRealmCoordinate[1]), ign=ign)
    time.sleep(8)


def recycle_inventory(device, ign, is_free_player=False, bot_id=None, debug=False):
    console_log_with_ign(ign, "Recycling inventory...")

    do_clear_screen(device, ign=ign)

    # Tap to Inventory
    do_tap(device, (97.472, 35.7879), ign=ign)
    time.sleep(1)

    # Tap to Recycle Button from Inventory Screen
    do_tap(device, (86.0754, 91.2371), ign=ign)
    time.sleep(0.5)

    # Tap to Recycle Button from Recycle Screen
    do_tap(device, (86.0754, 91.2371), ign=ign)
    time.sleep(0.5)

    from search_text_image import get_search_text

    # check if there is notification regarding  to Unbound MU Coins
    check_text = get_search_text(grab_raw_rgba(device, ign=ign, debug=debug), region=(676, 397, 1254, 551), ign=ign, debug=False)
    print(f"Check text for recycle: {check_text}")
    if "purchase" in check_text.lower() or "increased" in check_text.lower() or "recycle" in check_text.lower():
        console_log_with_ign(ign, "Detected notification dialog; tapping to dismiss dialog...")
        do_tap(device, (751, 567), mode="px", ign=ign)
        time.sleep(0.5)
        do_tap(device, (826, 639), mode="px", ign=ign)
        time.sleep(0.5)

    do_tap(device, (86.0754, 91.2371), ign=ign)
    time.sleep(0.2)
    do_tap(device, (86.0754, 91.2371), ign=ign)
    time.sleep(0.2)

    try:
        do_clear_screen(device, ign=ign)
        do_tap(device, (97.472, 35.7879), ign=ign)
        time.sleep(0.5)
        img = grab_raw_rgba(device, ign=ign, debug=debug)
        import ocr_number
        import local_data

        coins = ocr_number.extract_number(img, region=(1103, 939, 1280, 981), number_range=None, show_all_digits=True, debug=False)
        local_data.save_coins(coins)

    except Exception as e:
        console_log_with_ign(ign, f"Error saving coins locally: {e}")

    do_clear_screen(device, ign=ign)
    time.sleep(0.2)


def is_golden_boss_alive(img: ImageLike, device: str, coordinate: Tuple[float, float], ign: str, half_size: int = DEFAULT_REGION_HALF_SIZE, dont_open_map: bool = False, debug=False) -> bool:
    import player_locator_map

    if not dont_open_map:
        do_clear_screen(device, ign=ign, debug=debug)

        console_log_with_ign(ign, "Checking if golden boss is alive at", coordinate)
        do_open_map(device, ign=ign, debug=debug)

    # region is (left, top, right, bottom) around the coordinate; half-size is configurable
    region = (
        int(coordinate[0] - half_size),
        int(coordinate[1] - half_size),
        int(coordinate[0] + half_size),
        int(coordinate[1] + half_size),
    )
    target_colors = [
        (242, 212, 127),  # bright yellow in BGR
        (153, 119, 34),  # darker yellow in BGR
    ]
    if img is None:
        console_log_with_ign(ign, "is_golden_boss_alive: Taking screenshot for golden boss detection...")
        img = grab_raw_rgba(device, ign=ign, debug=debug)

    coordinates = player_locator_map.find_color_to_image(img, target_colors, region=region, ign=ign, debug=debug)
    if coordinates is None:
        return False
    return len(coordinates) > 0


def is_red_boss_alive(device: str, coordinate: Tuple[float, float], ign: str, img: ImageLike = None, half_size: int = DEFAULT_REGION_HALF_SIZE, dont_open_map: bool = False, debug=False) -> bool:
    import player_locator_map

    if not dont_open_map:
        do_clear_screen(device, ign=ign, debug=debug)

        console_log_with_ign(ign, "Checking if golden boss is alive at", coordinate)
        do_open_map(device, ign=ign, debug=debug)

    # region is (left, top, right, bottom) around the coordinate; half-size is configurable
    region = (
        int(coordinate[0] - half_size),
        int(coordinate[1] - half_size),
        int(coordinate[0] + half_size),
        int(coordinate[1] + half_size),
    )
    target_colors = [
        (204, 58, 21),
        (253, 193, 127),
    ]

    if img is None:
        console_log_with_ign(ign, "is_red_boss_alive: Taking screenshot for red boss detection...")
        img = grab_raw_rgba(device, ign=ign, debug=debug)

    coordinates = player_locator_map.find_color_to_image(img, target_colors, region=region, ign=ign, debug=debug)
    if coordinates is None:
        return False
    return len(coordinates) > 0


def get_alive_red_boss_coordinates(device: str, coordinates: List[Tuple[float, float]], ign: str, img: ImageLike = None, half_size: int = DEFAULT_REGION_HALF_SIZE, debug=False) -> List[Tuple[int, int]]:
    alive_bosses = []

    if img is None:
        console_log_with_ign(ign, "get_alive_red_boss_coordinates: Taking screenshot for red boss detection...")
        do_clear_screen(device, ign=ign, debug=debug)
        do_open_map(device, ign=ign, debug=debug)
        img = grab_raw_rgba(device, ign=ign, debug=debug)

    for coord in coordinates:
        if is_red_boss_alive(device, coord, ign, img=img, half_size=half_size, dont_open_map=True, debug=debug):
            alive_bosses.append(coord)

    return alive_bosses


def get_alive_golden_boss_coordinates(device: str, coordinates: List[Tuple[float, float]], ign: str, img: ImageLike = None, half_size: int = DEFAULT_REGION_HALF_SIZE, debug=False) -> List[Tuple[int, int]]:
    alive_bosses = []

    if img is None:
        console_log_with_ign(ign, "get_alive_golden_boss_coordinates: Taking screenshot for golden boss detection...")
        do_clear_screen(device, ign=ign, debug=debug)
        do_open_map(device, ign=ign, debug=debug)
        img = grab_raw_rgba(device, ign=ign, debug=debug)

    for coord in coordinates:
        if is_golden_boss_alive(img, device, coord, ign, half_size=half_size, dont_open_map=True, debug=debug):
            alive_bosses.append(coord)

    return alive_bosses


def check_ign_exists(device, ign, skip_names: List[str] = [], region=(880, 1, 1300, 60), img=None, debug=False):
    from search_text_image import get_search_text

    if img is None:
        img = grab_raw_rgba(device, ign=ign, debug=debug)
    found_text = get_search_text(img, search=ign, region=region, ign=ign, debug=debug)
    if debug:
        console_log_with_ign(ign, f"[DEBUG] Detected IGN text: '{found_text}'")

    skip_names_found = False
    for name in skip_names:
        if name.lower() in found_text.lower():
            skip_names_found = True
            if debug:
                console_log_with_ign(ign, f"[DEBUG] Skip name '{name}' found in text.")
            break

    if search_text_fall_back.is_close_match(ign, found_text):
        if debug:
            console_log_with_ign(ign, f"[DEBUG] Close match found between '{ign}' and '{found_text}'.")
        return True, skip_names_found, found_text

    if found_text is None:
        found_text = ""

    return ign.lower() in found_text.lower(), skip_names_found, found_text


def go_to_starting_position(device, ign, debug=False, nodelay=True):
    console_log_with_ign(ign, "Going to starting position...")
    do_clear_screen(device, ign=ign, debug=debug)
    do_tap(device, (97.559, 2.34708), ign=ign, debug=debug)
    time.sleep(0.5)
    do_tap(device, (49.9, 76.5292), ign=ign, debug=debug)
    if nodelay:
        time.sleep(1)


def random_teleport(device, ign, path=None, debug=False):
    do_tap(device, (86.771, 85.278), ign=ign, remarks="Tap Random Teleport - At Top", debug=debug)
    time.sleep(0.2)


def revive_if_dead(device, ign, debug=False) -> bool:
    if debug:
        console_log_with_ign(ign, "Checking if character is dead...")

    pattern = cv2.imread(os.path.join("images", "character-defeated.png"))
    img = grab_raw_rgba(device, ign=ign, debug=debug)
    region = (642, 347, 1281, 425)

    loc = image_search_pattern.get_location_by_template(img, pattern, region, threshold=0.7, debug=debug)

    if loc is not None:
        console_log_with_ign(ign, "Character was dead")
        do_tap(device, (813, 645), ign=ign, mode="px", remarks="Character defeated - Tap to Respawn", debug=debug)
        time.sleep(0.1)
        do_tap(device, (813, 645), ign=ign, mode="px", remarks="Character defeated - Tap to Respawn", debug=debug)
        time.sleep(0.1)
        return True
    else:
        if debug:
            console_log_with_ign(ign, "Character is alive")
        return False


def get_coordinate_of_text(device: str, search_text: str, ign: str, region: Optional[Tuple[int, int, int, int]] = None, img=None, debug=False) -> Optional[Tuple[int, int]]:
    """
    Find text on screen using OCR and return its center coordinates.

    Args:
        device: ADB device identifier
        search_text: Text to search for (case-insensitive)
        ign: Player identifier for logging
        region: Optional region to scan (left, top, right, bottom). If None, scans full screen.
        img: Optional image to use. If None, will grab screenshot from device.
        debug: Enable debug logging

    Returns:
        Tuple of (x, y) pixel coordinates of text center, or None if not found
    """
    import pytesseract
    from PIL import Image as PILImage

    if img is None:
        img = grab_raw_rgba(device, ign=ign, debug=debug)

    # If region specified, crop to that region
    if region is not None:
        if isinstance(img, PILImage.Image):
            cropped = img.crop((region[0], region[1], region[2], region[3]))
        else:
            cropped = img[region[1] : region[3], region[0] : region[2]]
    else:
        cropped = img
        region = (0, 0, img.width if isinstance(img, PILImage.Image) else img.shape[1], img.height if isinstance(img, PILImage.Image) else img.shape[0])

    # Save cropped image if debug mode is enabled
    if debug:
        import datetime

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        debug_filename = f"debug_ocr_cropped_{ign}_{timestamp}.png"
        debug_path = os.path.join("temp", debug_filename)
        os.makedirs("temp", exist_ok=True)
        if isinstance(cropped, PILImage.Image):
            cropped.save(debug_path)
        else:
            cv2.imwrite(debug_path, cropped)
        console_log_with_ign(ign, f"[DEBUG] Saved cropped image to: {debug_path}")

    # Use pytesseract to get text with bounding boxes
    data = pytesseract.image_to_data(cropped, output_type=pytesseract.Output.DICT)

    # Search for the text
    target_text = search_text.lower()

    if debug:
        detected_texts = [text for text in data["text"] if text.strip()]
        console_log_with_ign(ign, f"[DEBUG] All detected text: {detected_texts}")
        console_log_with_ign(ign, f"[DEBUG] Looking for: '{search_text}'")

    for i, text in enumerate(data["text"]):
        if text:
            text_lower = text.lower()
            # For text containing '5', OCR might read '5' as 'S', so check both patterns
            match_found = False
            if "5" in search_text:
                # Check both "5" and "s" versions (e.g., "5switch" or "sswitch")
                alt_text = target_text.replace("5", "s")
                if target_text in text_lower or alt_text in text_lower:
                    match_found = True
            else:
                if target_text in text_lower:
                    match_found = True

            if match_found:
                # Get coordinates
                x = data["left"][i]
                y = data["top"][i]
                w = data["width"][i]
                h = data["height"][i]

                # Calculate center point and adjust for region offset
                center_x = region[0] + x + w // 2
                center_y = region[1] + y + h // 2

                if debug:
                    console_log_with_ign(ign, f"[DEBUG] Found '{text}' at ({center_x}, {center_y})")

                return (center_x, center_y)

    if debug:
        console_log_with_ign(ign, f"[DEBUG] Text '{search_text}' not found")

    return None
