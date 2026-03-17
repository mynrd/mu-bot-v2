import os
import time
from typing import Tuple
import adb_helpers
import image_helpers
import image_search_pattern
from bot_settings import BotSettings
from util import console_log_with_ign
from concurrent.futures import ThreadPoolExecutor

_THREAD_EXECUTOR = ThreadPoolExecutor(max_workers=4)

BOT_CONFIG: BotSettings = BotSettings(DEBUG=False, id=0, name="", configurationTextContent="", IGN="", PORT="")

DEVICE_ID = ""


def _load_buffer_config():
    cfg = {}
    text = getattr(BOT_CONFIG, "configurationTextContent", "") or ""
    if not text:
        return cfg
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip().upper()
        v = v.strip()
        if v.startswith("{") and v.endswith("}"):
            v = v[1:-1].strip()
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        cfg[k] = v
    return cfg


_BUF_CFG = _load_buffer_config()


def _list_from_cfg(key: str):
    v = _BUF_CFG.get(key.upper(), None)
    if not v:
        return []
    return [p.strip() for p in v.split(",") if p.strip()]


def party_user(
    slot,
    device,
    region_name: Tuple[int, int, int, int],
    region_guild: Tuple[int, int, int, int],
    invite_coordinate,
    invite_button_region=Tuple[int, int, int, int],
    image_binary: any = None,
) -> bool:
    console_log_with_ign(BOT_CONFIG.IGN, f"{slot}: Checking for whitelist names/guilds...")

    start_time = time.perf_counter()

    if image_binary is not None:
        f_name = _THREAD_EXECUTOR.submit(image_helpers.tesseract_extract_text_from_region_white_fast, image_binary, region=region_name)
        f_guild = _THREAD_EXECUTOR.submit(image_helpers.tesseract_extract_text_from_region_white_fast, image_binary, region=region_guild)
    else:
        console_log_with_ign(BOT_CONFIG.IGN, f"{slot}: Grabbing screenshot for OCR...")
        img = adb_helpers.grab_raw_rgba(device, ign=BOT_CONFIG.IGN, debug=False)
        f_name = _THREAD_EXECUTOR.submit(image_helpers.tesseract_extract_text_from_region_white, img, region_name, BOT_CONFIG.IGN)
        f_guild = _THREAD_EXECUTOR.submit(image_helpers.tesseract_extract_text_from_region_white, img, region_guild, BOT_CONFIG.IGN)

    get_name = f_name.result()
    get_guild = f_guild.result()

    elapsed = time.perf_counter() - start_time
    console_log_with_ign(BOT_CONFIG.IGN, f"{slot}: Finished OCR in {elapsed:.2f} seconds")

    if get_name and str(get_name).strip():
        console_log_with_ign(BOT_CONFIG.IGN, f"{slot}: Extracted name: {get_name}")
    if get_guild and str(get_guild).strip():
        console_log_with_ign(BOT_CONFIG.IGN, f"{slot}: Extracted guild: {get_guild}")

    whitelist_names = BOT_CONFIG.BUFFER_WHITELIST_NAMES if hasattr(BOT_CONFIG, "BUFFER_WHITELIST_NAMES") else []
    whitelist_guilds = BOT_CONFIG.BUFFER_WHITELIST_GUILDS if hasattr(BOT_CONFIG, "BUFFER_WHITELIST_GUILDS") else []

    if any(name.lower() in get_name.lower() for name in whitelist_names) or any(guild.lower() in get_guild.lower() for guild in whitelist_guilds):
        console_log_with_ign(BOT_CONFIG.IGN, f"{slot}: Whitelisted name or guild found, sending invite...")

        adb_helpers.process_action_command(device, "tap " + invite_coordinate, ign=BOT_CONFIG.IGN)
        time.sleep(0.1)
        adb_helpers.process_action_command(device, "tap 84.3413 82.7688", ign=BOT_CONFIG.IGN)
        time.sleep(0.1)
        adb_helpers.process_action_command(device, "tap 84.3413 82.7688", ign=BOT_CONFIG.IGN)
        time.sleep(0.5)

        img = adb_helpers.grab_raw_rgba(device, ign=BOT_CONFIG.IGN, debug=False)
        pattern_invited = os.path.join(adb_helpers.HERE, "images", "invited.png")
        coordinate_invited = image_search_pattern.get_location_by_template_by_img(img, pattern_invited, region=(1375, 303, 1598, 369), threshold=0.75, debug=False)
        if coordinate_invited is not None:
            console_log_with_ign(BOT_CONFIG.IGN, f"{slot}: Invite appears to have been sent successfully. But need to Accept on the other side.")
            return False

        return True
    return False


def kick_slot_2():
    adb_helpers.do_tap(DEVICE_ID, (902, 535), ign=BOT_CONFIG.IGN)
    time.sleep(0.5)

    adb_helpers.do_tap(DEVICE_ID, (775, 533), ign=BOT_CONFIG.IGN)
    time.sleep(0.2)


def startBuffing(device_id: str, bot_config: BotSettings):
    global BOT_CONFIG, DEVICE_ID
    BOT_CONFIG = bot_config

    DEVICE_ID = device_id

    adb_helpers.do_clear_screen(device_id, ign=bot_config.IGN)
    time.sleep(0.2)
    adb_helpers.do_tap(DEVICE_ID, (29, 137), ign=bot_config.IGN)
    time.sleep(0.2)
    adb_helpers.do_tap(DEVICE_ID, (34, 297), ign=bot_config.IGN)
    time.sleep(0.2)

    import search_text_image

    adb_helpers.do_tap_attack(DEVICE_ID, bot_config.IGN)

    check_create_text = search_text_image.get_search_text("startBuffing:check_create", adb_helpers.grab_raw_rgba(device_id, ign=BOT_CONFIG.IGN), region=(211, 245, 336, 281))
    if check_create_text is not None and check_create_text.lower() == "create":
        console_log_with_ign(BOT_CONFIG.IGN, "Create button detected, will create team first")
        adb_helpers.do_tap(DEVICE_ID, (275, 265), ign=BOT_CONFIG.IGN)
        time.sleep(1)

    adb_helpers.do_tap(DEVICE_ID, (336, 342), ign=bot_config.IGN, remarks="Click Team on the Left Side")
    time.sleep(0.3)

    adb_helpers.do_tap(DEVICE_ID, (380, 297), ign=bot_config.IGN, remarks="Click My Team on the Dialog Box")
    time.sleep(0.3)

    kick_slot_2()

    adb_helpers.do_tap(DEVICE_ID, (380, 433), ign=bot_config.IGN, remarks="Click Nearby on the Dialog Box")
    time.sleep(0.3)

    img = None
    for _ in range(3):
        party_user("Slot 1", DEVICE_ID, (504, 301, 733, 366), (1066, 303, 1318, 375), "77.2577 31.0751", invite_button_region=(1375, 303, 1598, 369), image_binary=img)

    party_user("Slot 2", DEVICE_ID, (512, 397, 731, 457), (1067, 395, 1326, 465), "77.2577 39.7644", invite_button_region=(1375, 386, 1598, 467), image_binary=img)
    party_user("Slot 3", DEVICE_ID, (514, 482, 723, 553), (1067, 485, 1316, 558), "76.9677 48.38", invite_button_region=(1375, 483, 1598, 559), image_binary=img)
