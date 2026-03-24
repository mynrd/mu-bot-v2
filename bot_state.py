import inspect
import os
import threading
import time
from datetime import datetime
from typing import List, Tuple

import cv2
import adb_helpers
from local_data import MapLocation
from bot_exceptions import RestartRaise, ResetRaise
from bot_settings import BotSettings
from util import console_log_with_ign

# ---------------------------------------------------------------------------
# Global state variables
# ---------------------------------------------------------------------------
DEVICE = ""
SKIP_BUFFER = False
START_TIME_25M = None
MAX_SECONDS_25M = 25 * 60  # 25 minutes
CONFIG_CONTENT = ""
CURRENT_MAP_ID = ""
CURRENT_FOUND_IGN_ON_BOSS = []
RESTART_AFTER_MINUTES = 60
VIP_MAP = 5
WAIT_BUFFER = True
BOT_PAUSE = False
BOT_NAME = None

BOT_CONFIG: BotSettings = BotSettings(
    DEBUG=False, id=0, name="", configurationTextContent="", IGN="", PORT="",
)

BOT_CONFIG_LOCK = threading.Lock()
_CONFIG_REFRESH_STOP = threading.Event()
_CONFIG_REFRESH_THREAD: threading.Thread | None = None

MAP_INFOS_LOCK = threading.Lock()
_MAP_REFRESH_STOP = threading.Event()
_MAP_REFRESH_THREAD: threading.Thread | None = None

_HOURLY_THREAD = None
_HOURLY_STOP = threading.Event()

_DATETIME_START_ATTACK = None
_APP_START_TIME: datetime | None = None

BOT_ID = 1

MAP_INFOS: List[MapLocation] = []
MAP_INFO: MapLocation | None = None

CURRENT_TARGET = None
CURRENT_CHANNEL = None
PORT = ""

# ---------------------------------------------------------------------------
# Image templates
# ---------------------------------------------------------------------------
IMG_TEMPLATE_BOSS_ACTIVE = cv2.imread(os.path.join(adb_helpers.HERE, "images", "boss_active.png"))
IMG_TEMPLATE_SWAMP_OF_DARKNESS = cv2.imread(os.path.join(adb_helpers.HERE, "images", "swamp-of-darkness.png"))
IMG_TEMPLATE_MAP_LAND_OF_DEMONS = cv2.imread(os.path.join(adb_helpers.HERE, "images", "map-land-of-demons.png"))
IMG_TEMPLATE_MAP_FOGGY_FOREST = cv2.imread(os.path.join(adb_helpers.HERE, "images", "map-foggy-forest.png"))
IMG_TEMPLATE_BOSS_CHALLENGE = cv2.imread(os.path.join(adb_helpers.HERE, "images", "boss_challenge.png"))
IMG_TEMPLATE_MAP_MENU_DISSIMILATED_NIXIES = cv2.imread(os.path.join(adb_helpers.HERE, "images", "map_menu_dissimilated_nixies.png"))
IMG_TEMPLATE_MU_COIN_BOOST_EXPIRED = cv2.imread(os.path.join(adb_helpers.HERE, "images", "mu-coin-boost-expired.png"))
IMG_TEMPLATE_CURRENT_LOCATION = cv2.imread(os.path.join(adb_helpers.HERE, "images", "current_location.png"))
IMG_TEMPLATE_LOW_LIFE = cv2.imread(os.path.join(adb_helpers.HERE, "images", "low-life.png"))


# ---------------------------------------------------------------------------
# Utility functions that depend on global state
# ---------------------------------------------------------------------------
def console_log(*args, **kwargs):
    first = str(args[0]) if args else ""
    if first.startswith("["):
        console_log_with_ign(BOT_CONFIG.IGN, *args, **kwargs)
    else:
        frame = inspect.stack()[1]
        caller = f"{os.path.basename(frame.filename)}:{frame.lineno}"
        console_log_with_ign(BOT_CONFIG.IGN, f"[{caller}]", *args, **kwargs)


def load_bot_config():
    config = {}
    for raw_line in CONFIG_CONTENT.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        config[k.strip().upper()] = v.strip()
    required_defaults = {
        "id": BOT_CONFIG.id or 0,
        "name": BOT_CONFIG.name or "",
        "configurationTextContent": CONFIG_CONTENT or "",
        "PORT": BOT_CONFIG.PORT or "",
        "IGN": BOT_CONFIG.IGN or "",
        "SKIP_NAMES": "",
        "IGNORE_NAME": "true" if BOT_CONFIG.IGNORE_NAME else "false",
        "USE_TELEPORT": "true" if BOT_CONFIG.USE_TELEPORT else "false",
        "MAP": BOT_CONFIG.MAP or "",
        "ENGAGE_RED_BOSS": "true" if BOT_CONFIG.ENGAGE_RED_BOSS else "false",
        "ENGAGE_GOLDEN_BOSS": "true" if BOT_CONFIG.ENGAGE_GOLDEN_BOSS else "false",
        "RADIUS_SEARCH": str(BOT_CONFIG.RADIUS_SEARCH),
        "DEBUG": "true" if BOT_CONFIG.DEBUG else "false",
        "RESTART_AFTER_MINUTES": str(RESTART_AFTER_MINUTES),
        "ON_WALK_MODE_GO_TO_STARTING_POINT": "true" if BOT_CONFIG.ON_WALK_MODE_GO_TO_STARTING_POINT else "false",
        "RETRY_COUNT_READ_LIFE_FAILS": str(BOT_CONFIG.RETRY_COUNT_READ_LIFE_FAILS),
        "DETECT_LOW_LIFE": "true" if BOT_CONFIG.DETECT_LOW_LIFE else "false",
        "TAP_ON_MAP_WHILE_WALKING": "true" if BOT_CONFIG.TAP_ON_MAP_WHILE_WALKING else "false",
        "CHANNELS": BOT_CONFIG.CHANNELS or "",
        "THRESHOLD_DMG_RED": str(BOT_CONFIG.THRESHOLD_DMG_RED),
        "BUFFER": BOT_CONFIG.BUFFER or "",
        "BUFFER_MAP": BOT_CONFIG.BUFFER_MAP or "",
        "BUFFER_COORDINATE": BOT_CONFIG.BUFFER_COORDINATE or "",
        "DEBUFF_BEFORE_BUFF": "true" if BOT_CONFIG.DEBUFF_BEFORE_BUFF else "false",
        "AFK_MODE": "true" if BOT_CONFIG.AFK_MODE else "false",
        "IS_BUFFER": "true" if BOT_CONFIG.IS_BUFFER else "false",
        "BUFFER_WHITELIST_NAMES": "",
        "BUFFER_WHITELIST_GUILDS": "",
        "TAP_SKILL_CANCEL_ATTACK_COORDS": ",".join(map(str, BOT_CONFIG.TAP_SKILL_CANCEL_ATTACK_COORDS)) if BOT_CONFIG.TAP_SKILL_CANCEL_ATTACK_COORDS else "",

        "SKIP_VALIDATION_BUFF": "true" if BOT_CONFIG.SKIP_VALIDATION_BUFF else "false",
        "SKIP_BUFFER": "true" if BOT_CONFIG.SKIP_BUFFER else "false",
    }
    for rk, rv in required_defaults.items():
        if rk not in config:
            config[rk] = rv
    return config


def is_already_25_mins() -> bool:
    global START_TIME_25M
    if START_TIME_25M is None:
        return False

    elapsed = time.time() - START_TIME_25M
    if elapsed >= MAX_SECONDS_25M:
        START_TIME_25M = time.time()
        console_log_with_ign(BOT_CONFIG.IGN, "---------------------------------------------------")
        console_log_with_ign(BOT_CONFIG.IGN, "25 minutes elapsed, resetting timer.")
        console_log_with_ign(BOT_CONFIG.IGN, "---------------------------------------------------")
        return True
    return False


def get_map_info(map_id: str) -> MapLocation:
    with MAP_INFOS_LOCK:
        for mi in MAP_INFOS:
            try:
                if (mi.mapId or "") == map_id:
                    console_log(f"Found map info for '{map_id}'.")
                    return mi
            except Exception:
                pass
    raise KeyError(f"Map info not found for map_id '{map_id}' - {MAP_INFOS}")


def is_low_life(device: str, ign: str) -> bool:
    if BOT_CONFIG.DETECT_LOW_LIFE == False:
        return False
    image = adb_helpers.grab_raw_rgba(device, ign=ign)
    from image_search_pattern import get_location_by_template_by_img

    coord = get_location_by_template_by_img(image, IMG_TEMPLATE_LOW_LIFE, region=(592, 960, 701, 1011))
    if coord is not None:
        return True
    return False


def should_exit_bot(check_life=True, msg=None) -> bool:
    if msg is not None and BOT_CONFIG.DEBUG:
        console_log_with_ign(BOT_CONFIG.IGN, f"should_exit_bot check: {msg}")

    check_app_focus = adb_helpers.check_if_app_is_open(DEVICE, ign=BOT_CONFIG.IGN)
    if check_app_focus == False:
        console_log("App is not in focus. Triggering restart.")
        raise RestartRaise("App lost focus.")

    if check_life:
        if is_low_life(DEVICE, BOT_CONFIG.IGN):
            console_log("Low life detected. Triggering reset.")
            raise ResetRaise("Low life detected.")

    return False


def check_bot_paused() -> bool:
    if BOT_PAUSE:
        console_log_with_ign(BOT_CONFIG.IGN, "Bot is paused. Waiting for Ctrl+P to resume...")
        while BOT_PAUSE:
            time.sleep(3)
