import os
import time
from datetime import datetime
from typing import List, Tuple

import adb_helpers
import bot_state as state
import local_data
import player_locator_map
from local_data import BossDto
from bot_navigation import go_to_buffer, go_to_buffer_location, go_to_map
from image_helpers import ImageLike
from util import console_log_with_ign


# ---------------------------------------------------------------------------
# Boss coordinate helpers
# ---------------------------------------------------------------------------

def get_the_nearest_red_boss(
    device: str,
    ign: str,
    current_location: Tuple[float, float],
    coordinates: List[Tuple[float, float]],
    min_distance=None,
    debug=False,
) -> Tuple[float, float]:
    nearest_boss = None
    if min_distance is None:
        min_distance = 10000

    for coord in coordinates:
        near, distance = player_locator_map.is_coordinates_near(coord, current_location, tolerance=15, debug=state.BOT_CONFIG.DEBUG)
        if distance < min_distance:
            min_distance = distance
            nearest_boss = coord

    return nearest_boss


def _age_minutes(now_utc: datetime, dt) -> float | None:
    try:
        UTC_TZ = datetime.UTC  # type: ignore[attr-defined]
    except AttributeError:
        from datetime import timezone

        UTC_TZ = timezone.utc

    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC_TZ)
    return (now_utc - dt).total_seconds() / 60.0


def _include_for_channel(boss: BossDto, current_channel: int, now_utc: datetime) -> bool:
    info = boss.bossChannelInfo or []
    if not info:
        return True

    if boss.engageBy == state.BOT_CONFIG.name:
        return True

    ch_entries = [r for r in info if getattr(r, "channel", None) == current_channel]

    if not ch_entries:
        return True

    for r in ch_entries:
        m = _age_minutes(now_utc, getattr(r, "detectedAt", None))
        if m is not None and m > 2.0:
            return True

    return False


def _log_recent_detected_bosses(map_info, current_channel: int, now_utc: datetime, ign: str) -> None:
    try:
        recent_not_mine: List[Tuple[BossDto, float]] = []
        bosses = getattr(map_info, "bosses", None) or []
        for b in bosses:
            info = getattr(b, "bossChannelInfo", None) or []
            ch_entries = [r for r in info if getattr(r, "channel", None) == current_channel]
            if not ch_entries:
                continue
            if getattr(b, "engageBy", None) == state.BOT_CONFIG.name:
                continue
            ages = [_age_minutes(now_utc, getattr(r, "detectedAt", None)) for r in ch_entries]
            if ages and all((m is not None and m <= 2.0) for m in ages):
                recent_not_mine.append((b, min(ages)))

        if recent_not_mine:
            console_log_with_ign(
                ign,
                f"Detected <=2 min (not mine) on ch {current_channel}: {len(recent_not_mine)}",
            )
            for b, age_min in recent_not_mine:
                btype = "Red" if getattr(b, "bossType", None) == 1 else ("Golden" if getattr(b, "bossType", None) == 2 else str(getattr(b, "bossType", None)))
                console_log_with_ign(
                    ign,
                    f" - {btype} at ({getattr(b, 'coordX', '?')}, {getattr(b, 'coordY', '?')}) | age {age_min:.2f} min",
                )
    except Exception as e:
        console_log_with_ign(ign, f"Logging of recent detected bosses failed: {e}")


def get_available_boss_coordinates(device: str, ign: str, map_id: str, img: ImageLike = None, debug=False) -> List[Tuple[float, float]]:
    map_info = state.get_map_info(map_id)

    try:
        utc_tz = datetime.UTC  # type: ignore[attr-defined]
    except AttributeError:
        from datetime import timezone

        utc_tz = timezone.utc
    now_utc = datetime.now(utc_tz)

    red_coordinates = [(x.coordX, x.coordY) for x in map_info.bosses if x.bossType == 1 and _include_for_channel(x, state.CURRENT_CHANNEL, now_utc)]
    golden_coordinates = [(x.coordX, x.coordY) for x in map_info.bosses if x.bossType == 2 and _include_for_channel(x, state.CURRENT_CHANNEL, now_utc)]
    console_log_with_ign(ign, f"Available bosses for channel {state.CURRENT_CHANNEL}: Red {len(red_coordinates)}, Golden {len(golden_coordinates)}")
    _log_recent_detected_bosses(map_info, state.CURRENT_CHANNEL, now_utc, ign)

    alive_boss = []

    if state.BOT_CONFIG.ENGAGE_RED_BOSS:
        alive_boss = adb_helpers.get_alive_red_boss_coordinates(device, red_coordinates, ign, img=img, debug=state.BOT_CONFIG.DEBUG)
    if state.BOT_CONFIG.ENGAGE_GOLDEN_BOSS:
        alive_boss = alive_boss + adb_helpers.get_alive_golden_boss_coordinates(
            device,
            golden_coordinates,
            ign,
            img=img,
            debug=state.BOT_CONFIG.DEBUG,
        )

    return alive_boss


def get_map_invalid_areas(map_id: str) -> List[List[Tuple[float, float]]]:
    try:
        import json

        invalid_areas_file = os.path.join(adb_helpers.HERE, "invalid_areas.json")

        if not os.path.exists(invalid_areas_file):
            state.console_log(f"Invalid areas file not found: {invalid_areas_file}")
            return []

        with open(invalid_areas_file, "r") as f:
            data = json.load(f)

        if data.get("mapId") == map_id:
            areas = data.get("areas", [])
            result = []
            for area_group in areas:
                area_coords = []
                for coord_str in area_group:
                    try:
                        x, y = coord_str.split(", ")
                        area_coords.append((float(x), float(y)))
                    except (ValueError, AttributeError) as e:
                        state.console_log(f"Failed to parse coordinate '{coord_str}': {e}")
                        continue
                if area_coords:
                    result.append(area_coords)
            return result
        else:
            return []

    except Exception as e:
        state.console_log(f"Error loading invalid areas for map {map_id}: {e}")
        return []


# ---------------------------------------------------------------------------
# Boss engagement / combat
# ---------------------------------------------------------------------------

def check_boss_active_killing(device, ign, img=None, debug=False):
    import image_search_pattern

    if img is None:
        img = adb_helpers.grab_raw_rgba(device, ign=ign, debug=debug)
    result = image_search_pattern.get_location_by_template_by_img(img, state.IMG_TEMPLATE_BOSS_ACTIVE, region=(763, 10, 882, 120), threshold=0.6)
    return result


def engage_and_check_isvalid(device, ign, skipNames: List[str] = [], ignoreName=False, target_boss=None, debug=False):

    console_log_with_ign(ign, "Starting kill action sequence...")

    adb_helpers.do_tap(device, (92.7152, 81.8851), ign=ign, remarks="Tap Attack", debug=debug)
    time.sleep(0.1)
    adb_helpers.do_tap(device, (92.7152, 81.8851), ign=ign, remarks="Tap Attack", debug=debug)
    time.sleep(3)

    console_log_with_ign(ign, "Ensuring auto-attack mode is active...")

    max_retries = 2
    retry_delay = 0.1
    for attempt in range(1, max_retries + 1):
        if state.should_exit_bot(msg="start_killing"):
            console_log_with_ign(ign, "Exit flag detected in configuration. Exiting kill action.")
            return False

        console_log_with_ign(ign, f"Kill action attempt {attempt} of {max_retries}...")
        check, skipUsers = True, []
        if not ignoreName:
            console_log_with_ign(ign, f"Checking if '{ign}' exists in region (attempt {attempt}/{max_retries})...")
            img = adb_helpers.grab_raw_rgba(device, ign=ign, debug=debug)
            is_engage = check_boss_active_killing(device, ign, img=img, debug=debug)

            if is_engage is None:
                console_log_with_ign(ign, "Failed to determine if boss is active. Aborting kill action.")
                return False

            if state.MAP_INFO.mapId.startswith("SB-"):
                console_log_with_ign(ign, "Special map Superb Realm - detected, skipping name check and proceeding to kill.")
                adb_helpers.do_tap_attack(device, ign=ign, debug=debug)
                return True

            check, skipUsers, found_text = adb_helpers.check_ign_exists(device, ign, region=(880, 1, 1300, 60), skip_names=skipNames, img=img, debug=debug)

            state.CURRENT_FOUND_IGN_ON_BOSS = found_text

            if found_text == None or found_text == "":
                console_log_with_ign(ign, f"No text found in region, possibly dead. Aborting kill action for '{ign}'.")
                continue

            import search_text_fall_back

            if search_text_fall_back.is_close_match(ign, found_text):
                console_log_with_ign(ign, f'Exact or close match for "{ign}" found in region: "{found_text}". Proceeding with kill action.')
                adb_helpers.do_tap_attack(device, ign=ign, debug=debug)
                return True

        if skipUsers:
            console_log_with_ign(ign, f"Skip users detected: {skipUsers}. Aborting kill action for '{ign}'.")
            console_log_with_ign(ign, f'Blacklisted name found, aborting kill action for "{ign}".')
            return False

        if check:
            console_log_with_ign(ign, f'"{ign}" found in region, proceeding with kill action (attempt {attempt}).')
            console_log_with_ign(ign, f'Killing in progress: "{ign}" found in region (attempt {attempt}).')
            adb_helpers.do_tap_attack(device, ign=ign, debug=debug)
            return True
        else:
            if attempt < max_retries:
                console_log_with_ign(ign, f'"{ign}" not found in region (attempt {attempt}), retrying...')
                CURRENT_TARGET = next((bi for bi in state.MAP_INFO.bosses if (bi.coordX, bi.coordY) == tuple(target_boss)), None)
                if CURRENT_TARGET:
                    local_data.set_boss_found_dead(boss_id=CURRENT_TARGET.id, channel=state.CURRENT_CHANNEL)
                time.sleep(retry_delay)

    console_log_with_ign(ign, f'Killing not detected after {max_retries} attempts: "{ign}" not found.')
    return False


def monitor_until_its_gone(device, ign, interval=2, skipNames: List[str] = [], ignoreName=False, debug=False) -> None:
    from bot_exceptions import RestartRaise

    while True:
        state.check_bot_paused()

        dead = adb_helpers.revive_if_dead(device, ign, debug=debug)
        if dead:
            console_log_with_ign(ign, "Character was dead and has been revived. Exiting monitor.")
            raise RestartRaise("Character died during boss fight.")

        res = check_boss_active_killing(device, ign, debug=debug)
        if res is not None:
            console_log_with_ign(ign, "Boss is still active, continuing to monitor...")
            time.sleep(interval)
            continue
        else:
            console_log_with_ign(ign, "Boss is no longer active, exiting monitor.")
            time.sleep(5)
            return


# ---------------------------------------------------------------------------
# Boss engagement loop (inner loop shared by teleport and walking flows)
# ---------------------------------------------------------------------------

def _engage_boss_and_update(
    device: str,
    ign: str,
    target_boss: Tuple[float, float],
    pattern_current_location: str,
    loop_count: int,
    map_id: str,
    alive_all_type_bosses: List[Tuple[float, float]],
    debug: bool = False,
    *,
    recalc_location_each_loop: bool = True,
    initial_location: Tuple[float, float, float, float, float] | None = None,
):
    state.CURRENT_TARGET = next((bi for bi in state.MAP_INFO.bosses if (bi.coordX, bi.coordY) == tuple(target_boss)), None)

    counter = 0
    while True:
        counter += 1
        if state.should_exit_bot(msg="_engage_boss_and_update main loop"):
            state.console_log(ign, "Exit detected. Exiting go_to_spot.")
            return True, True, alive_all_type_bosses

        if recalc_location_each_loop or initial_location is None:
            current_location = player_locator_map.find_location_by_image(
                adb_helpers.grab_raw_rgba(device, ign=ign),
                pattern_current_location,
                (605, 168, 1595, 953),
                threshold=0.7,
                debug=state.BOT_CONFIG.DEBUG,
            )
            if current_location is None:
                state.console_log(ign, "Failed to determine current location after teleport. Exiting")
                return True, None, alive_all_type_bosses
        else:
            current_location = initial_location

        x, y, score, angle, scale = current_location

        get_nearest_boss = get_the_nearest_red_boss(
            device,
            ign,
            (x, y),
            alive_all_type_bosses,
            min_distance=200,
            debug=state.BOT_CONFIG.DEBUG,
        )

        if get_nearest_boss is not None and (get_nearest_boss[0] == target_boss[0] and get_nearest_boss[1] == target_boss[1]) == False:
            target_boss = [get_nearest_boss[0], get_nearest_boss[1]]
            if state.BOT_CONFIG.TAP_ON_MAP_WHILE_WALKING:
                adb_helpers.do_tap(device, target_boss, ign=ign)
            state.console_log(ign, f"Target boss changed to nearest: {target_boss}")

        near, distance = player_locator_map.is_coordinates_near(target_boss, (x, y), tolerance=15)
        if counter % 10 == 0:
            state.console_log(ign, f"Near: {near}, Distance: {distance}")

        if near:
            state.console_log(ign, f"Arrived at Red Boss location {current_location}.")
            adb_helpers.do_clear_screen(device, ign=state.BOT_CONFIG.IGN)

            state._DATETIME_START_ATTACK = datetime.now()
            isValidToKill = engage_and_check_isvalid(
                device,
                ign=state.BOT_CONFIG.IGN,
                ignoreName=state.BOT_CONFIG.IGNORE_NAME,
                skipNames=state.BOT_CONFIG.SKIP_NAMES,
                target_boss=target_boss,
                debug=state.BOT_CONFIG.DEBUG,
            )

            state.console_log(ign, f"isValidToKill: {isValidToKill}")
            if state.CURRENT_TARGET:
                try:
                    local_data.update_boss_engaged(boss_id=state.CURRENT_TARGET.id, bot_name=state.BOT_CONFIG.name)
                except Exception as e:
                    state.console_log(ign, f"Failed to update boss engaged (non-fatal): {e}")

            if isValidToKill:
                state.console_log(ign, f"Starting to kill the red boss at {target_boss}.")
                shoud_exit = monitor_until_its_gone(
                    device,
                    ign=state.BOT_CONFIG.IGN,
                    ignoreName=state.BOT_CONFIG.IGNORE_NAME,
                    skipNames=state.BOT_CONFIG.SKIP_NAMES,
                    debug=state.BOT_CONFIG.DEBUG,
                )
                state.console_log(ign, f"shoud_exit: {shoud_exit}")
                time.sleep(3)
                names = ", ".join(state.CURRENT_FOUND_IGN_ON_BOSS) if state.CURRENT_FOUND_IGN_ON_BOSS else "(none)"
                try:
                    local_data.add_attack_record(bot_id=state.BOT_CONFIG.id, boss_id=state.CURRENT_TARGET.id if state.CURRENT_TARGET else None, coin=0, coin_bound=0, start_attack=state._DATETIME_START_ATTACK, end_attack=datetime.now(), map_id=state.CURRENT_MAP_ID, found_attack_name=ign)
                    if state.CURRENT_TARGET:
                        local_data.update_boss_killed(boss_id=state.CURRENT_TARGET.id)
                except Exception as e:
                    state.console_log(ign, f"Failed to save attack record (non-fatal): {e}")

                state.CURRENT_TARGET = None

                if shoud_exit:
                    return True, True, alive_all_type_bosses

                adb_helpers.do_clear_screen(device, ign=state.BOT_CONFIG.IGN)
                adb_helpers.do_open_map(device, ign=state.BOT_CONFIG.IGN)

                img = adb_helpers.grab_raw_rgba(device, ign=ign, debug=state.BOT_CONFIG.DEBUG)
                alive_all_type_bosses = get_available_boss_coordinates(
                    device,
                    ign,
                    map_id,
                    img=img,
                    debug=state.BOT_CONFIG.DEBUG,
                )
                count_alive = len(alive_all_type_bosses)
                state.console_log(ign, f"Alive bosses after kill: {alive_all_type_bosses}")
                state.console_log(ign, f"Using teleportation to reach the nearest red boss. Alive bosses count: {count_alive}")

                return False, None, alive_all_type_bosses
            else:

                state.console_log(ign, "Not a valid boss to kill.")
                coord = state.BOT_CONFIG.TAP_SKILL_CANCEL_ATTACK_COORDS
                if coord is None:
                    coord = (84.0033, 75.9205)
                adb_helpers.do_tap(device, coord, ign=ign)

                adb_helpers.do_clear_screen(device, ign=state.BOT_CONFIG.IGN)
                adb_helpers.go_to_starting_position(device, ign=state.BOT_CONFIG.IGN)

                import search_text_image

                check_if_strucked = search_text_image.get_search_text_blue(adb_helpers.grab_raw_rgba(device, ign=state.BOT_CONFIG.IGN), region=(12, 878, 530, 1018), debug=False)
                any_possible_text = ["teleportation", "available", "leaving", "combat"]
                if any(s in check_if_strucked.lower() for s in any_possible_text):
                    console_log_with_ign(ign, f"Detected possible stuck state with text '{check_if_strucked}'. Attempting to recover by teleporting to Divine.")
                    go_to_buffer_location(device, ign=state.BOT_CONFIG.IGN)
                    adb_helpers.do_clear_screen(device, ign=state.BOT_CONFIG.IGN)
                    time.sleep(0.2)
                    adb_helpers.do_open_map(device, ign=state.BOT_CONFIG.IGN)
                    time.sleep(1)
                    adb_helpers.do_tap(device, (1121, 585), ign=ign)
                    time.sleep(5)
                    adb_helpers.do_clear_screen(device, ign=state.BOT_CONFIG.IGN)

                try:
                    names = ", ".join(state.CURRENT_FOUND_IGN_ON_BOSS) if state.CURRENT_FOUND_IGN_ON_BOSS else "(none)"
                    local_data.add_attack_record(bot_id=state.BOT_ID, coin=0, coin_bound=0, start_attack=state._DATETIME_START_ATTACK, end_attack=datetime.now(), map_id=state.CURRENT_MAP_ID, found_attack_name=names)
                except Exception as e:
                    state.console_log(ign, f"Failed to save attack record (non-fatal): {e}")
                adb_helpers.do_clear_screen(device, ign=state.BOT_CONFIG.IGN)
                adb_helpers.do_open_map(device, ign=state.BOT_CONFIG.IGN)

                if target_boss in alive_all_type_bosses:
                    alive_all_type_bosses.remove(target_boss)
                return False, None, alive_all_type_bosses


# ---------------------------------------------------------------------------
# Boss hunting main loop
# ---------------------------------------------------------------------------

def start_boss_hunting(device: str, ign: str, map_id: str, debug=False):
    adb_helpers.do_clear_screen(device, ign=state.BOT_CONFIG.IGN, debug=state.BOT_CONFIG.DEBUG)
    state.console_log(ign, f"Starting hunt for red bosses in channel {state.CURRENT_CHANNEL}...")
    adb_helpers.switch_channel(device, ign=ign, channel=state.CURRENT_CHANNEL, debug=state.BOT_CONFIG.DEBUG)

    adb_helpers.do_open_map(device, ign=state.BOT_CONFIG.IGN, debug=state.BOT_CONFIG.DEBUG)
    img = adb_helpers.grab_raw_rgba(device, ign=ign, debug=state.BOT_CONFIG.DEBUG)

    alive_all_type_boss = get_available_boss_coordinates(device, ign, map_id, img=img, debug=state.BOT_CONFIG.DEBUG)
    state.console_log(ign, f"Alive bosses: {alive_all_type_boss}")

    random_teleport_attempts = 0
    loop_count = 0
    radius_search = state.BOT_CONFIG.RADIUS_SEARCH

    invalid_areas = get_map_invalid_areas(map_id)

    while True:
        if state.should_exit_bot(msg="start_boss_hunting main loop"):
            state.console_log(ign, "Exit detected. Exiting go_to_spot.")
            return True

        loop_count += 1

        if state.is_already_25_mins():
            state.console_log(ign, "Exiting boss loop after 25.0 minutes (limit 25 minutes).")
            return False

        if len(alive_all_type_boss) == 0:
            state.console_log(ign, f"No alive red bosses found in channel {state.CURRENT_CHANNEL}. Exiting hunt.")
            return True

        state.console_log(ign, f"Alive Red or Golden Boss: {alive_all_type_boss}")
        if (state.BOT_CONFIG.USE_TELEPORT == True or state.MAP_INFO.mapId == "K-01") and state.MAP_INFO.mapId.startswith("SB-") != False:
            if random_teleport_attempts != 0 and ((random_teleport_attempts) % 10) == 0:
                console_log_with_ign(state.BOT_CONFIG.IGN, f"Reached {random_teleport_attempts} consecutive teleport attempts without finding a boss. Refreshing map and screen.")
                adb_helpers.do_clear_screen(device, ign=ign, debug=state.BOT_CONFIG.DEBUG)
                adb_helpers.do_open_map(device, ign=ign, debug=state.BOT_CONFIG.DEBUG)

            count_alive = len(alive_all_type_boss)
            state.console_log(ign, f"Using teleportation to reach the nearest red boss. Alive bosses count: {count_alive}")

            if invalid_areas is not None and len(invalid_areas) > 0:
                for areas in invalid_areas:
                    while True:
                        current_location = player_locator_map.find_location_by_image(
                            adb_helpers.grab_raw_rgba(device, ign=ign),
                            state.IMG_TEMPLATE_CURRENT_LOCATION,
                            (605, 168, 1595, 953),
                            threshold=0.7,
                            debug=state.BOT_CONFIG.DEBUG,
                        )
                        if current_location is None:
                            break

                        x, y, score, angle, scale = current_location
                        is_invalid_area = player_locator_map.is_point_in_polygon((x, y), areas)

                        if is_invalid_area:
                            console_log_with_ign(ign, f"Current location is in invalid area. Teleporting randomly.")
                            adb_helpers.random_teleport(device, ign=ign, debug=state.BOT_CONFIG.DEBUG)
                        else:
                            console_log_with_ign(ign, "Current location is valid. Continuing.")
                            break

            current_location = player_locator_map.find_location_by_image(
                adb_helpers.grab_raw_rgba(device, ign=ign),
                state.IMG_TEMPLATE_CURRENT_LOCATION,
                (605, 168, 1595, 953),
                threshold=0.7,
                debug=state.BOT_CONFIG.DEBUG,
            )
            if current_location is None:
                state.console_log(ign, "Failed to determine current location after teleport. Exiting")
                return True
            x, y, score, angle, scale = current_location
            state.console_log(ign, f"Current location: x={x}, y={y}, score={score}, ang={angle}, scale={scale} __")

            nearest_boss = get_the_nearest_red_boss(
                device,
                ign,
                (x, y),
                alive_all_type_boss,
                radius_search,
                debug=state.BOT_CONFIG.DEBUG,
            )

            if nearest_boss is None:
                state.console_log(
                    ign,
                    "random_teleport_attempts: ",
                    random_teleport_attempts,
                )
                if random_teleport_attempts <= 10:
                    adb_helpers.do_tap(device, (84, 78.6629), ign=ign, debug=state.BOT_CONFIG.DEBUG)
                    time.sleep(0.05)
                    adb_helpers.do_tap(device, (84, 78.6629), ign=ign, debug=state.BOT_CONFIG.DEBUG)
                    time.sleep(0.05)
                    adb_helpers.random_teleport(device, ign, debug=state.BOT_CONFIG.DEBUG)
                    time.sleep(0.1)
                    state.console_log(ign, f"Random teleport attempts: {random_teleport_attempts}")
                    random_teleport_attempts += 1
                    time.sleep(0.5)
                    continue
                else:
                    state.console_log(ign, "Failed to teleport, manually going to starting position and walking to boss.")
                    nearest_boss = get_the_nearest_red_boss(
                        device,
                        ign,
                        (x, y),
                        alive_all_type_boss,
                        debug=state.BOT_CONFIG.DEBUG,
                    )
                    adb_helpers.do_clear_screen(device, ign=ign, debug=state.BOT_CONFIG.DEBUG)
                    adb_helpers.go_to_starting_position(device, ign=ign, debug=state.BOT_CONFIG.DEBUG)
                    time.sleep(2)
                    adb_helpers.do_open_map(device, ign=ign, debug=state.BOT_CONFIG.DEBUG)
                    time.sleep(1)

            state.console_log(ign, f"Nearest red boss: {nearest_boss}")
            adb_helpers.do_tap(
                device,
                nearest_boss,
                ign=ign,
                remarks="Tap to nearest red boss",
            )

            should_term, ret_val, alive_all_type_boss = _engage_boss_and_update(
                device,
                ign,
                nearest_boss,
                state.IMG_TEMPLATE_CURRENT_LOCATION,
                loop_count,
                map_id,
                alive_all_type_boss,
                debug,
            )
            if should_term:
                return ret_val
        else:
            state.console_log(ign, "Walking to the nearest red boss...")
            if state.BOT_CONFIG.ON_WALK_MODE_GO_TO_STARTING_POINT:
                adb_helpers.go_to_starting_position(device, ign=ign, debug=state.BOT_CONFIG.DEBUG)

            adb_helpers.do_clear_screen(device, ign=state.BOT_CONFIG.IGN, debug=state.BOT_CONFIG.DEBUG)
            time.sleep(0.2)
            adb_helpers.do_open_map(device, ign=state.BOT_CONFIG.IGN, debug=state.BOT_CONFIG.DEBUG)
            time.sleep(1)

            if invalid_areas is not None and len(invalid_areas) > 0:
                for areas in invalid_areas:
                    while True:
                        current_location = player_locator_map.find_location_by_image(
                            adb_helpers.grab_raw_rgba(device, ign=ign),
                            state.IMG_TEMPLATE_CURRENT_LOCATION,
                            (605, 168, 1595, 953),
                            threshold=0.7,
                            debug=state.BOT_CONFIG.DEBUG,
                        )
                        if current_location is None:
                            break

                        x, y, score, angle, scale = current_location
                        is_invalid_area = player_locator_map.is_point_in_polygon((x, y), areas)

                        if is_invalid_area:
                            console_log_with_ign(ign, f"Current location is in invalid area. Teleporting randomly.")
                            adb_helpers.random_teleport(device, ign=ign, debug=state.BOT_CONFIG.DEBUG)
                        else:
                            console_log_with_ign(ign, "Current location is valid. Continuing.")
                            break

            img = adb_helpers.grab_raw_rgba(device, ign=ign, debug=state.BOT_CONFIG.DEBUG)

            if len(alive_all_type_boss) == 0:
                state.console_log(ign, f"No alive red bosses found in channel {state.CURRENT_CHANNEL}. Exiting hunt.")
                return True

            current_location = player_locator_map.find_location_by_image(
                adb_helpers.grab_raw_rgba(device, ign=ign),
                state.IMG_TEMPLATE_CURRENT_LOCATION,
                (605, 168, 1595, 953),
                threshold=0.7,
                debug=state.BOT_CONFIG.DEBUG,
            )
            if current_location is None:
                state.console_log(ign, "Failed to determine current location after teleport. Exiting")
                return True
            x, y, score, angle, scale = current_location
            state.console_log(ign, f"Current location: x={x}, y={y}, score={score}, ang={angle}, scale={scale} __")

            nearest_boss = get_the_nearest_red_boss(
                device,
                ign,
                (x, y),
                alive_all_type_boss,
                debug=state.BOT_CONFIG.DEBUG,
            )
            adb_helpers.do_tap(
                device,
                nearest_boss,
                ign=ign,
                remarks="Tap to first red boss",
            )

            should_term, ret_val, alive_all_type_boss = _engage_boss_and_update(
                device,
                ign,
                nearest_boss,
                state.IMG_TEMPLATE_CURRENT_LOCATION,
                loop_count,
                map_id,
                alive_all_type_boss,
                debug,
                recalc_location_each_loop=True,
                initial_location=current_location,
            )
            if should_term:
                return ret_val

        random_teleport_attempts = 0


# ---------------------------------------------------------------------------
# High-level orchestration
# ---------------------------------------------------------------------------

def initiate_boss(device: str, map_id: str, map_name: str):
    state.console_log(f"Initiating boss in map {map_name}")
    map = state.get_map_info(map_id)

    channels = []

    if state.BOT_CONFIG.CHANNELS is not None and state.BOT_CONFIG.CHANNELS != "":
        console_log_with_ign(state.BOT_CONFIG.IGN, f"Specified channels in config: {state.BOT_CONFIG.CHANNELS}")
        channels = [int(c) for c in str(state.BOT_CONFIG.CHANNELS).split(",") if c.strip().isdigit()]
        if len(channels) > map.totalChannel:
            console_log_with_ign(state.BOT_CONFIG.IGN, f"Warning: Specified channels {channels} exceed total channels {map.totalChannel} for map {map_id}. Using all available channels instead.")
            channels = list(range(1, map.totalChannel + 1))
    else:
        console_log_with_ign(state.BOT_CONFIG.IGN, f"No channels specified in config. Using all available channels for map {map_id}. Total channels: {map.totalChannel}")
        channels = list(range(1, map.totalChannel + 1))

    console_log_with_ign(state.BOT_CONFIG.IGN, f"Using channels: {channels}")

    for channel in channels:
        state.CURRENT_CHANNEL = channel
        if start_boss_hunting(device, state.BOT_CONFIG.IGN, map_id) == False:
            adb_helpers.recycle_inventory(device, ign=state.BOT_CONFIG.IGN, bot_id=state.BOT_CONFIG.id, is_free_player=True)
            adb_helpers.do_clear_screen(device, ign=state.BOT_CONFIG.IGN)
            go_to_buffer(device, state.BOT_CONFIG.IGN)
            go_to_map(device, map_id)

        if state.should_exit_bot(msg="go_to_spot after other channel"):
            state.console_log("Exit detected. Exiting go_to_spot.")
            return


def go_to_spot(device: str, skip_buffer=False):
    if not skip_buffer:
        go_to_buffer(device, state.BOT_CONFIG.IGN)
    else:
        state.console_log("Skipping buffer; assuming already in the correct location.")

    while True:
        state.check_bot_paused()

        if state.should_exit_bot(msg="go_to_spot main loop"):
            state.console_log("Exit detected. Exiting go_to_spot.")
            return

        if state.is_already_25_mins():
            state.console_log("Exiting boss loop after 25.0 minutes (limit 25 minutes).")
            break

        map_ids = state.BOT_CONFIG.MAP.split(",")
        state.console_log(f"Going to map id(s): {map_ids}")
        for map_id in map_ids:
            state.check_bot_paused()
            state.CURRENT_MAP_ID = map_id.strip()
            console_log_with_ign(state.BOT_CONFIG.IGN, f"Navigating to map ID: {state.CURRENT_MAP_ID}")
            map_name = state.get_map_info(map_id).name
            state.console_log(f" - {map_id}: {map_name}")
            go_to_map(device, map_id)

            if initiate_boss(device, map_id, map_name):
                return

            if state.should_exit_bot(msg="go_to_spot after map loop"):
                state.console_log("Exit detected. Exiting go_to_spot.")
                return
        time.sleep(0.5)
