import sys
import time

import adb_helpers
import bot_state as state
from util import console_log_with_ign


# ---------------------------------------------------------------------------
# Map navigation functions
# ---------------------------------------------------------------------------


def go_to_vip_map(device: str):
    adb_helpers.teleport_to_divine(device, state.BOT_CONFIG.IGN)

    adb_helpers.do_clear_screen(device, ign=state.BOT_CONFIG.IGN)
    adb_helpers.do_open_map(device, ign=state.BOT_CONFIG.IGN)

    adb_helpers.do_tap(
        device,
        (58.9, 50.59),
        ign=state.BOT_CONFIG.IGN,
        remarks="Tap to VIP Domain location",
    )
    time.sleep(2)
    adb_helpers.do_clear_screen(device, ign=state.BOT_CONFIG.IGN)

    adb_helpers.do_tap(
        device, (82.71, 50.09), ign=state.BOT_CONFIG.IGN, remarks="Tap to Talk to NPC"
    )
    time.sleep(1)
    if state.VIP_MAP == 2:
        adb_helpers.do_tap(
            device,
            (39.11, 31.76),
            ign=state.BOT_CONFIG.IGN,
            remarks="Select Sanctuary 2",
        )
    if state.VIP_MAP == 3:
        adb_helpers.do_tap(
            device,
            (39.219, 38.056),
            ign=state.BOT_CONFIG.IGN,
            remarks="Select Sanctuary 3",
        )
    if state.VIP_MAP == 4:
        adb_helpers.do_tap(
            device,
            (39.115, 43.519),
            ign=state.BOT_CONFIG.IGN,
            remarks="Select Sanctuary 4",
        )
    if state.VIP_MAP == 5:
        adb_helpers.do_tap(
            device,
            (39.479, 50.000),
            ign=state.BOT_CONFIG.IGN,
            remarks="Select Sanctuary 5",
        )
    if state.VIP_MAP == 6:
        adb_helpers.do_tap(
            device,
            (39.115, 55.833),
            ign=state.BOT_CONFIG.IGN,
            remarks="Select Sanctuary 6",
        )
    if state.VIP_MAP == 7:
        adb_helpers.do_tap(
            device,
            (39.219, 61.667),
            ign=state.BOT_CONFIG.IGN,
            remarks="Select Sanctuary 7",
        )

    time.sleep(1)
    adb_helpers.do_tap(
        device,
        (49.79, 77.04),
        ign=state.BOT_CONFIG.IGN,
        remarks="Click Enter Sanctuary",
    )
    time.sleep(5)


def go_to_abyssal_ferea(device):
    state.console_log("Going to the Abyssal Ferea...")

    adb_helpers.do_clear_screen(device, ign=state.BOT_CONFIG.IGN)
    adb_helpers.do_open_map(device, ign=state.BOT_CONFIG.IGN)
    time.sleep(1)

    for _ in range(3):
        adb_helpers.process_action_command(
            device,
            "swipe 21.3285,63.6558 21.6086,26.1024 300",
            ign=state.BOT_CONFIG.IGN,
        )
        time.sleep(0.5)

    time.sleep(2)
    adb_helpers.do_tap(device, (20.7781, 47.1281), ign=state.BOT_CONFIG.IGN)
    time.sleep(5)


def go_to_swamp_of_darkness(device):
    state.console_log("Going to the Swamp of Darkness...")
    ign = state.BOT_CONFIG.IGN
    while True:
        adb_helpers.do_clear_screen(device, ign=ign)
        adb_helpers.do_open_map(device, ign=ign)
        time.sleep(0.2)

        for _ in range(5):
            adb_helpers.process_action_command(
                device,
                "swipe 22.0887,26.1414 22.1301,57.511 300",
                ign=ign,
            )
            time.sleep(0.2)
        time.sleep(1.5)

        adb_helpers.process_action_command(
            device,
            "swipe 20.804,66.4948  21.0112,24.1532 300",
            ign=ign,
        )
        time.sleep(3)

        img = adb_helpers.grab_raw_rgba(device, ign=ign)
        regionMapList = (248, 180, 571, 755)
        coordinate = adb_helpers.image_search_pattern.get_location_by_template(
            img,
            state.IMG_TEMPLATE_SWAMP_OF_DARKNESS,
            regionMapList,
            threshold=0.75,
            debug=state.BOT_CONFIG.DEBUG,
        )
        if coordinate is not None:
            break
        state.console_log("Couldn't find Swamp of Darkness on the map, retrying...")
        time.sleep(1)

    adb_helpers.do_tap(
        device,
        (coordinate[0], coordinate[1]),
        ign=ign,
    )
    time.sleep(5)


def go_to_kalima(device, kalima_number=None):
    state.console_log("Going to the Kalima...")

    adb_helpers.do_clear_screen(device, ign=state.BOT_CONFIG.IGN)
    adb_helpers.do_open_map(device, ign=state.BOT_CONFIG.IGN)
    time.sleep(1)

    for _ in range(3):
        adb_helpers.process_action_command(
            device,
            "swipe 21.3285,63.6558 21.6086,26.1024 300",
            ign=state.BOT_CONFIG.IGN,
        )
        time.sleep(0.5)

    time.sleep(2)

    adb_helpers.do_tap(
        device,
        (22.029, 28.6451),
        ign=state.BOT_CONFIG.IGN,
        remarks="Tap to Kalima location",
    )
    time.sleep(0.2)
    adb_helpers.do_tap(
        device,
        (22.029, 28.6451),
        ign=state.BOT_CONFIG.IGN,
        remarks="Tap to Kalima location",
    )
    time.sleep(5)

    kalima_coords = {
        1: (39.2043, 25.6996),
        2: (39.11, 31.76),
        3: (39.219, 38.056),
        4: (39.115, 43.519),
        5: (39.479, 50.000),
        6: (39.115, 55.833),
        7: (39.219, 61.667),
    }

    if kalima_number in kalima_coords:
        adb_helpers.do_tap(
            device,
            kalima_coords[kalima_number],
            ign=state.BOT_CONFIG.IGN,
            remarks=f"Kalima {kalima_number}",
        )
        time.sleep(0.3)
        adb_helpers.do_tap(
            device,
            kalima_coords[kalima_number],
            ign=state.BOT_CONFIG.IGN,
            remarks=f"Kalima {kalima_number}",
        )
        time.sleep(0.3)
        adb_helpers.do_tap(
            device,
            kalima_coords[kalima_number],
            ign=state.BOT_CONFIG.IGN,
            remarks=f"Kalima {kalima_number}",
        )
        time.sleep(0.3)
        adb_helpers.do_tap(
            device,
            kalima_coords[kalima_number],
            ign=state.BOT_CONFIG.IGN,
            remarks=f"Kalima {kalima_number}",
        )

    time.sleep(0.5)
    adb_helpers.do_tap(
        device,
        (50.2691, 76.5832),
        ign=state.BOT_CONFIG.IGN,
        remarks=(
            "Tap to Enter to Kalima " + str(kalima_number) if kalima_number else "..."
        ),
    )
    time.sleep(5)


def go_to_land_of_demons(device):
    state.console_log("Going to the Land of Demons...")
    ign = state.BOT_CONFIG.IGN
    while True:
        adb_helpers.do_clear_screen(device, ign=ign)
        adb_helpers.do_open_map(device, ign=ign)
        time.sleep(0.2)

        for _ in range(5):
            adb_helpers.process_action_command(
                device,
                "swipe 22.1301,57.511 22.0887,26.1414 300",
                ign=ign,
            )
            time.sleep(0.2)
        time.sleep(1.5)

        adb_helpers.process_action_command(
            device,
            "swipe 20.804,66.4948  21.0112,24.1532 300",
            ign=ign,
        )
        time.sleep(3)

        img = adb_helpers.grab_raw_rgba(device, ign=ign)
        regionMapList = (248, 180, 571, 755)
        coordinate = adb_helpers.image_search_pattern.get_location_by_template(
            img,
            state.IMG_TEMPLATE_MAP_LAND_OF_DEMONS,
            regionMapList,
            threshold=0.75,
            debug=state.BOT_CONFIG.DEBUG,
        )
        if coordinate is not None:
            break
        state.console_log("Couldn't find Land of Demons on the map, retrying...")
        time.sleep(1)

    adb_helpers.do_tap(
        device,
        (coordinate[0], coordinate[1]),
        ign=ign,
    )
    time.sleep(5)


def go_to_foggy_forest(device):
    state.console_log("Going to the Foggy of Forest...")
    ign = state.BOT_CONFIG.IGN
    while True:
        adb_helpers.do_clear_screen(device, ign=ign)
        adb_helpers.do_open_map(device, ign=ign)
        time.sleep(0.2)

        for _ in range(5):
            adb_helpers.process_action_command(
                device,
                "swipe 22.1301,57.511 22.0887,26.1414 300",
                ign=ign,
            )
            time.sleep(0.2)
        time.sleep(1.5)

        adb_helpers.process_action_command(
            device,
            "swipe 20.804,66.4948  21.0112,24.1532 300",
            ign=ign,
        )
        time.sleep(3)

        img = adb_helpers.grab_raw_rgba(device, ign=ign)
        regionMapList = (248, 180, 571, 755)
        coordinate = adb_helpers.image_search_pattern.get_location_by_template(
            img,
            state.IMG_TEMPLATE_MAP_FOGGY_FOREST,
            regionMapList,
            threshold=0.75,
            debug=state.BOT_CONFIG.DEBUG,
        )
        if coordinate is not None:
            break
        state.console_log("Couldn't find Foggy of Forest on the map, retrying...")
        time.sleep(1)

    adb_helpers.do_tap(
        device,
        (coordinate[0], coordinate[1]),
        ign=ign,
    )
    time.sleep(5)


def go_to_superb_realm(device):
    console_log_with_ign(state.BOT_CONFIG.IGN, "Going to the Excellent Boss...")
    import image_search_pattern

    adb_helpers.do_clear_screen(device, ign=state.BOT_CONFIG.IGN)
    adb_helpers.switch_channel(device, ign=state.BOT_CONFIG.IGN, channel=1)
    state.CURRENT_CHANNEL = 1
    time.sleep(1)

    console_log_with_ign(state.BOT_CONFIG.IGN, "Looking for Boss Challenge button...")

    img = adb_helpers.grab_raw_rgba(device, ign=state.BOT_CONFIG.IGN)

    res = image_search_pattern.get_location_by_template_by_img(
        img,
        state.IMG_TEMPLATE_BOSS_CHALLENGE,
        region=(1424, 13, 1552, 154),
        threshold=0.6,
    )

    if res is None:
        console_log_with_ign(
            state.BOT_CONFIG.IGN, "Couldn't find Boss Challenge button, retrying..."
        )
        adb_helpers.do_clear_screen(device, ign=state.BOT_CONFIG.IGN)
        adb_helpers.do_tap(device, (82.1272, 4.83642), ign=state.BOT_CONFIG.IGN)
        time.sleep(1)

    console_log_with_ign(
        state.BOT_CONFIG.IGN, "Found Boss Challenge button, proceeding..."
    )
    adb_helpers.do_tap(device, (77.7689, 8.25036), ign=state.BOT_CONFIG.IGN)
    time.sleep(2)

    adb_helpers.do_tap(device, (38.7045, 23.0441), ign=state.BOT_CONFIG.IGN)
    time.sleep(0.5)

    adb_helpers.do_tap(device, (44.5422, 72.6885), ign=state.BOT_CONFIG.IGN)
    time.sleep(0.2)
    adb_helpers.do_tap(device, (58.0568, 72.5462), ign=state.BOT_CONFIG.IGN)
    time.sleep(5)
    adb_helpers.do_tap(device, (960, 826), mode="px", ign=state.BOT_CONFIG.IGN)
    time.sleep(5)


def go_to_dissimilated_nixies(device):
    console_log_with_ign(state.BOT_CONFIG.IGN, "Going to the Dissimilated Nixies...")
    ign = state.BOT_CONFIG.IGN
    while True:
        adb_helpers.do_clear_screen(device, ign=ign)
        adb_helpers.do_open_map(device, ign=ign)
        time.sleep(0.2)

        for _ in range(5):
            adb_helpers.process_action_command(
                device,
                "swipe 22.1301,57.511 22.0887,26.1414 300",
                ign=ign,
            )
            time.sleep(0.2)
        time.sleep(1.5)

        adb_helpers.process_action_command(
            device,
            "swipe 20.804,66.4948  21.0112,24.1532 300",
            ign=ign,
        )
        time.sleep(3)

        img = adb_helpers.grab_raw_rgba(device, ign=ign)
        regionMapList = (248, 180, 571, 755)
        coordinate = adb_helpers.image_search_pattern.get_location_by_template(
            img,
            state.IMG_TEMPLATE_MAP_MENU_DISSIMILATED_NIXIES,
            regionMapList,
            threshold=0.75,
            debug=state.BOT_CONFIG.DEBUG,
        )
        if coordinate is not None:
            break
        state.console_log("Couldn't find Dissimilated Nixies on the map, retrying...")
        time.sleep(1)

    adb_helpers.do_tap(
        device,
        (coordinate[0], coordinate[1]),
        ign=ign,
    )
    time.sleep(5)


def go_to_darkshade_canyon(device):
    state.console_log("Going to the Swamp of Abyss...")

    adb_helpers.do_clear_screen(device, ign=state.BOT_CONFIG.IGN)
    adb_helpers.do_open_map(device, ign=state.BOT_CONFIG.IGN)
    time.sleep(1)

    for _ in range(4):
        adb_helpers.process_action_command(
            device,
            "swipe 21.3285,63.6558 21.6086,26.1024 300",
            ign=state.BOT_CONFIG.IGN,
        )
        time.sleep(0.5)

    time.sleep(2)
    adb_helpers.do_tap(device, (21.0484, 58.9616), ign=state.BOT_CONFIG.IGN)
    time.sleep(5)


def go_to_endless_abyss(device):
    state.console_log("Going to the Endless Abyss...")
    adb_helpers.teleport_to_endless_abyss(device, state.BOT_CONFIG.IGN)


def go_to_corridor_of_agony(device):
    state.console_log("Going to the Corridor of Agony...")
    adb_helpers.teleport_to_corridor_of_agony(device, state.BOT_CONFIG.IGN)


# ---------------------------------------------------------------------------
# Buff / debuff functions
# ---------------------------------------------------------------------------


def debuff(device, ign, debug=False):
    state.console_log(ign, "Applying debuff...")

    from image_helpers import get_text_gray

    while True:
        if state.should_exit_bot(msg="debuff"):
            state.console_log(ign, "Exit detected. Exiting debuff.")
            return

        img = adb_helpers.grab_raw_rgba(device, ign=ign)

        expired = adb_helpers.image_search_pattern.get_location_by_template(
            img,
            state.IMG_TEMPLATE_MU_COIN_BOOST_EXPIRED,
            region=(535, 434, 708, 615),
            threshold=0.7,
            debug=state.BOT_CONFIG.DEBUG,
        )
        if expired is not None:
            close_coords = adb_helpers.coords_to_percents(1495, 302)
            adb_helpers.do_tap(
                device, close_coords, ign=ign, debug=state.BOT_CONFIG.DEBUG
            )

        text = get_text_gray(
            img,
            region=(1582, 639, 1685, 669),
            ign=ign,
            compare_text="Element",
            debug=state.BOT_CONFIG.DEBUG,
        )
        if debug:
            state.console_log(ign, f"[DEBUG] Detected text: '{text}'")
        if "element" not in text.lower():
            if debug:
                state.console_log(ign, "[DEBUG] Tapping menu button")
            adb_helpers.do_tap(
                device, (97.3499, 26.1414), ign=ign, debug=state.BOT_CONFIG.DEBUG
            )
            time.sleep(0.5)
        else:
            if debug:
                state.console_log(
                    ign, "[DEBUG] 'Element' text found; proceeding to debuff."
                )
            break

    adb_helpers.do_tap(device, (85.383, 57.732), debug=state.BOT_CONFIG.DEBUG, ign=ign)
    time.sleep(1)

    adb_helpers.do_tap(
        device, (83.0572, 10.0147), debug=state.BOT_CONFIG.DEBUG, ign=ign
    )
    time.sleep(0.5)

    adb_helpers.do_tap(device, (79.793, 93.6672), debug=state.BOT_CONFIG.DEBUG, ign=ign)
    time.sleep(3)

    adb_helpers.do_tap(device, (75.735, 9.86745), debug=state.BOT_CONFIG.DEBUG, ign=ign)
    time.sleep(0.5)

    adb_helpers.do_tap(device, (79.793, 93.6672), debug=state.BOT_CONFIG.DEBUG, ign=ign)
    time.sleep(3)

    adb_helpers.do_clear_screen(device, ign=ign, debug=state.BOT_CONFIG.DEBUG)


def go_to_buffer(device, ign, debug=False):

    if state.should_exit_bot(msg="go_to_buffer"):
        state.console_log(ign, "Exit detected. Exiting go_to_spot.")
        return

    adb_helpers.do_clear_screen(device, ign=ign)

    if state.BOT_CONFIG.DEBUFF_BEFORE_BUFF:
        debuff(device, ign, debug=state.BOT_CONFIG.DEBUG)
        if state.should_exit_bot(msg="go_to_buffer 2"):
            state.console_log(ign, "Exit detected. Exiting go_to_spot.")
            return

    if state.BOT_CONFIG.BUFFER_MAP == "DIVINE" or state.BOT_CONFIG.BUFFER_MAP == "":
        state.console_log(ign, "Going to the buffer map Divine...")
        adb_helpers.teleport_to_divine(device, ign)
        adb_helpers.do_clear_screen(device, ign=ign)
        time.sleep(0.2)
        adb_helpers.do_open_map(device, ign=ign)
        time.sleep(1)
        state.console_log(ign, "Going to the buffer...")
        adb_helpers.go_to_target_location(
            device, ign=ign, target=(1160, 455), debug=debug
        )
        time.sleep(3)

    if state.BOT_CONFIG.BUFFER_MAP == "CORRIDOR_OF_AGONY":
        state.console_log(ign, "Going to the buffer map Cooridor of Agony...")
        go_to_corridor_of_agony(device)

    if state.BOT_CONFIG.BUFFER_MAP == "ENDLESS_ABYSS":
        state.console_log(ign, "Going to the buffer map Endless Abyss...")
        go_to_endless_abyss(device)

    if state.BOT_CONFIG.BUFFER_MAP.startswith("KALIMA-"):
        kalima_number = None
        kalima_number = int(state.BOT_CONFIG.BUFFER_MAP.split("-")[1])

        if kalima_number is not None and 1 <= kalima_number <= 7:
            state.console_log(ign, f"Going to the buffer map Kalima {kalima_number}...")
            go_to_kalima(device, kalima_number=kalima_number)

            adb_helpers.do_clear_screen(device, ign=ign)
            time.sleep(0.2)
            adb_helpers.do_open_map(device, ign=ign)
            time.sleep(1)
            state.console_log(ign, "Going to the buffer...")

            k_coord_x = float(state.BOT_CONFIG.BUFFER_COORDINATE.split(",")[0])
            k_coord_y = float(state.BOT_CONFIG.BUFFER_COORDINATE.split(",")[1])

            adb_helpers.go_to_target_location(
                device, ign=ign, target=(k_coord_x, k_coord_y), debug=debug
            )
            time.sleep(3)
        else:
            raise ValueError(
                f"Invalid BUFFER_MAP '{state.BOT_CONFIG.BUFFER_MAP}' for Kalima"
            )

    adb_helpers.do_clear_screen(device, ign=ign, debug=state.BOT_CONFIG.DEBUG)
    time.sleep(0.2)

    adb_helpers.do_check_if_buffed(
        device,
        ign=ign,
        min_dmg_red=state.BOT_CONFIG.THRESHOLD_DMG_RED,
        debug=state.BOT_CONFIG.DEBUG,
    )
    state.START_TIME_25M = time.time()
    time.sleep(0.5)


def go_to_buffer_location(device, ign, doTeleportToDivine=True):

    if state.should_exit_bot(msg="go_to_buffer"):
        state.console_log(ign, "Exit detected. Exiting go_to_spot.")
        return

    if doTeleportToDivine:
        adb_helpers.do_clear_screen(device, ign=ign)
        state.console_log(ign, "Going to the buffer map Divine...")
        adb_helpers.teleport_to_divine(device, ign)

    adb_helpers.do_clear_screen(device, ign=ign)
    time.sleep(0.2)
    adb_helpers.do_open_map(device, ign=ign)
    time.sleep(1)
    state.console_log(ign, "Going to the buffer...")
    adb_helpers.go_to_target_location(device, ign=ign, target=(1160, 455))
    time.sleep(3)

    adb_helpers.do_clear_screen(device, ign=ign, debug=state.BOT_CONFIG.DEBUG)
    time.sleep(0.2)


# ---------------------------------------------------------------------------
# Map routing
# ---------------------------------------------------------------------------


def parse_vip_map_from_id(map_id: str) -> int | None:
    import re

    m = re.match(r"^\s*SANC(\d+)-", str(map_id).upper())
    return int(m.group(1)) if m else None


def go_to_map(device: str, map_id: str):
    if map_id == "7-01":
        adb_helpers.teleport_to_swamp_of_abyss(device, state.BOT_CONFIG.IGN)
        state.MAP_INFO = state.get_map_info(map_id)
        return
    if map_id == "7-03":
        adb_helpers.teleport_to_swamp_of_abyss(device, state.BOT_CONFIG.IGN)
        state.MAP_INFO = state.get_map_info(map_id)
        return
    if map_id == "7-04":
        adb_helpers.teleport_to_swamp_of_abyss(device, state.BOT_CONFIG.IGN)
        state.MAP_INFO = state.get_map_info(map_id)
        return
    if map_id == "7-02":
        go_to_swamp_of_darkness(device)
        state.MAP_INFO = state.get_map_info(map_id)
        return
    if map_id == "6-01":
        go_to_dissimilated_nixies(device)
        state.MAP_INFO = state.get_map_info(map_id)
        return
    if map_id.startswith("8-01"):
        go_to_darkshade_canyon(device)
        state.MAP_INFO = state.get_map_info(map_id)
        return
    if map_id == "K-01":
        go_to_kalima(device)
        state.MAP_INFO = state.get_map_info(map_id)
        return
    if map_id == "LOD-01":
        go_to_land_of_demons(device)
        state.MAP_INFO = state.get_map_info(map_id)
        return
    if map_id == "FF-01":
        go_to_foggy_forest(device)
        state.MAP_INFO = state.get_map_info(map_id)
        return

    if map_id.startswith("5.5"):
        vip = parse_vip_map_from_id(map_id)
        go_to_abyssal_ferea(device)
        state.MAP_INFO = state.get_map_info(map_id)
        return

    if map_id.startswith("SB-"):
        go_to_superb_realm(device)
        state.MAP_INFO = state.get_map_info(map_id)
        return

    if map_id.startswith("SANC"):
        vip = parse_vip_map_from_id(map_id)
        if vip is not None:
            state.VIP_MAP = vip
        else:
            raise ValueError(f"Cannot parse VIP map from map_id '{map_id}'")

        go_to_vip_map(device)
        state.MAP_INFO = state.get_map_info(map_id)
        return

    state.console_log(f"Map {map_id} navigation not implemented.")
    sys.exit(1)


def go_to_afk_spot(device: str):
    console_log_with_ign(state.BOT_CONFIG.IGN, "Going to AFK spot...")
    adb_helpers.teleport_to_swamp_of_abyss(device, state.BOT_CONFIG.IGN)
    adb_helpers.switch_channel(device, ign=state.BOT_CONFIG.IGN, channel=3)
    time.sleep(1)
    adb_helpers.do_clear_screen(device, ign=state.BOT_CONFIG.IGN)
    adb_helpers.do_open_map(device, ign=state.BOT_CONFIG.IGN)
    target = (991, 552)
    adb_helpers.go_to_target_location(device, ign=state.BOT_CONFIG.IGN, target=target)
    adb_helpers.do_clear_screen(device, ign=state.BOT_CONFIG.IGN)
    adb_helpers.do_tap_attack(device, ign=state.BOT_CONFIG.IGN)
