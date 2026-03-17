"""adb_helpers package — drop-in replacement for the former adb_helpers.py module.

All public names are re-exported here so that existing code like
``import adb_helpers; adb_helpers.do_tap(...)`` keeps working unchanged.
"""

# -- core ADB command execution --
from adb_helpers._core import (
    HERE,
    _is_transient_adb_error,
    build_adb_cmd,
    retry_on_timeout,
    run_adb_cmd,
    run_cmd,
)

# -- screen / coordinate utilities --
from adb_helpers._screen import (
    _coord_to_px,
    coords_to_percents,
    coords_to_pixels,
    get_screen_size,
    grab_raw_rgba,
    parse_coord_tokens,
)

# -- basic input actions --
from adb_helpers._input import (
    DEFAULT_REGION_HALF_SIZE,
    _do_swipe,
    do_clear_screen,
    do_tap,
    swipe_down,
    swipe_up,
)

# -- device management --
from adb_helpers._device import (
    check_if_app_is_open,
    close_app,
    disconnect,
    ensure_connected,
    ensure_device_connected,
    open_app,
    set_show_touches,
)

# -- action command processing --
from adb_helpers._actions import (
    _process_action_lines,
    process_action_command,
)

# -- image search --
import image_search_pattern

# -- game-specific operations --
from adb_helpers._game import (
    check_ign_exists,
    check_is_alive,
    do_check_if_buffed,
    do_open_map,
    do_tap_attack,
    get_alive_golden_boss_coordinates,
    get_alive_red_boss_coordinates,
    get_coordinate_of_text,
    go_to_starting_position,
    go_to_target_location,
    is_golden_boss_alive,
    is_red_boss_alive,
    random_teleport,
    recycle_inventory,
    reopen_app,
    revive_if_dead,
    switch_channel,
    teleport_to_divine,
    teleport_to_endless_abyss,
    teleport_to_corridor_of_agony
)
