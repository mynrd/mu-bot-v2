import argparse
import sys
import time
import threading

import adb_helpers
import bot_state as state
import local_data
from bot_exceptions import ResetRaise, RestartRaise
from bot_settings import BotSettings
from bot_threads import start_config_background_refresh, stop_config_background_refresh
from bot_combat import go_to_spot
from bot_navigation import go_to_afk_spot, go_to_buffer
from util import console_log_with_ign


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="bot_yhwach")
    parser.add_argument("-d", "--port", required=False, help="Adb Device Port")
    parser.add_argument("--ign", required=False, help="In-game name (override default IGN)")
    parser.add_argument("--skip-names", required=False, help="Comma-separated list of player names to skip")
    parser.add_argument("--channel", required=False, type=int, help="Channel number to use for actions (default: 1)")
    parser.add_argument("--ignore-name", action="store_true", help="Ignore checking player name (for free players)")
    parser.add_argument("--use-teleport", action="store_true", help="Use teleportation to reach golden boss location")
    parser.add_argument("--map", required=False, help="Map name to use (if applicable)")
    parser.add_argument("--vip-map", required=False, type=int, help="VIP map number to use (default: 2)")
    parser.add_argument("--engage-red-boss", action="store_true", help="Engage the boss when found, but do not recycle inventory")
    parser.add_argument("--radius-search", type=int, help="Radius to search for nearest boss when teleporting (default: 120)")
    parser.add_argument("--bot-id", type=int, help="Bot ID (for logging purposes)")
    parser.add_argument("--skip-buffer", action="store_true", help="Skip going to buffer before boss hunting")
    parser.add_argument("--engage-golden-boss", action="store_true", help="Engage the golden boss only")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--restart-after-minutes", type=int, help="Automatically restart the bot after this many minutes (default: 60)")
    parser.add_argument("--wait-buffer", action="store_true", help="Wait until buffer is available before going to boss")
    parser.add_argument("--reopen", action="store_true", help="Reopen the app if it's not running")
    parser.add_argument("--check-git-updates", action="store_true", help="Check for latest git codes and auto-restart if updated")
    parser.add_argument("--afk-mode", action="store_true", help="Enable AFK mode (stay at AFK spot)")

    if argv is None and len(sys.argv) <= 1:
        config = state.load_bot_config()
        bool_args = {"ignore-name", "use-teleport", "engage-red-boss", "skip-buffer",
                      "engage-golden-boss", "debug", "wait-buffer", "reopen",
                      "check-git-updates", "afk-mode"}
        value_args = {"port", "ign", "skip-names", "channel", "map", "vip-map",
                       "radius-search", "bot-id", "restart-after-minutes"}
        fake_argv = []
        for k, v in config.items():
            k_cli = k.lower().replace("_", "-")
            if k_cli in bool_args:
                if str(v).lower() in ("1", "true", "yes", "on"):
                    fake_argv.append(f"--{k_cli}")
            elif k_cli in value_args:
                if str(v) != "":
                    fake_argv.append(f"--{k_cli}")
                    fake_argv.append(str(v))
        return parser.parse_args(fake_argv)
    return parser.parse_args(argv)


def run_buffer_mode(device: str, ign: str) -> None:
    """Run buffer-mode loop: ensure app open, revive if needed, and keep buffing."""
    import bot_buffer

    console_log_with_ign(ign, "IS_BUFFER is enabled, going to buffer spot...")
    buffer_start_time = time.time()
    adb_helpers.teleport_to_endless_abyss(device, ign=ign)
    while True:
        try:
            if adb_helpers.check_if_app_is_open(device, ign=ign) == False:
                console_log_with_ign(ign, "App is not open, reopening app...")
                adb_helpers.reopen_app(device, ign=ign)
                time.sleep(5)
                adb_helpers.teleport_to_endless_abyss(device, ign=ign)

            if adb_helpers.check_is_alive(device, ign):
                console_log_with_ign(ign, "Detected 'Respawn Now' prompt, character is dead.")
                adb_helpers.process_action_command(device, "tap 43.082 58.9838", ign=ign)
                time.sleep(0.100)
                adb_helpers.process_action_command(device, "tap 43.082 58.9838", ign=ign)
                time.sleep(0.100)
                adb_helpers.process_action_command(device, "tap 43.082 58.9838", ign=ign)
                time.sleep(0.100)
                time.sleep(5)
                adb_helpers.teleport_to_endless_abyss(device, ign=ign)

            bot_buffer.startBuffing(device, state.BOT_CONFIG)
            if (time.time() - buffer_start_time) >= 3600:
                console_log_with_ign(ign, "1 hour elapsed in buffer mode. Reopening app...")
                adb_helpers.close_app(device, ign=ign)

                adb_helpers.reopen_app(device, ign=ign)
                time.sleep(2)
                adb_helpers.teleport_to_endless_abyss(device, ign=ign)
                time.sleep(2)

                time.sleep(2)
                buffer_start_time = time.time()
        except Exception as e:
            console_log_with_ign(ign, f"Buffer mode exception caught: {e}. Reopening app and re-buffering...")
            adb_helpers.close_app(device, ign=ign)
            time.sleep(2)


def main(args) -> int:

    state.WAIT_BUFFER = args.wait_buffer
    state.console_log(f"WAIT_BUFFER: {state.WAIT_BUFFER}")

    reopen = args.reopen if args.reopen else False
    check_git_updates = args.check_git_updates if args.check_git_updates else False

    state.SKIP_BUFFER = args.skip_buffer
    state.console_log(f"SKIP_BUFFER: {state.SKIP_BUFFER}")

    state.BOT_ID = args.bot_id if args.bot_id else state.BOT_ID
    state.PORT = args.port if args.port else state.PORT

    def _start_ctrl_p_listener():
        import platform

        if platform.system().lower() != "windows":
            return
        try:
            import msvcrt  # type: ignore
        except Exception:
            return

        def _loop():
            while True:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ("\x10", "p", "P"):
                        state.BOT_PAUSE = not state.BOT_PAUSE
                        pause_state = "PAUSED" if state.BOT_PAUSE else "RESUMED"
                        state.console_log(f"[Ctrl+P] Bot {pause_state} (BOT_PAUSE={state.BOT_PAUSE})")
                time.sleep(0.1)

        threading.Thread(target=_loop, name="CtrlPListener", daemon=True).start()

    _start_ctrl_p_listener()

    # Load config from local file
    config_text = local_data.load_config_text()
    state.CONFIG_CONTENT = config_text
    state.BOT_CONFIG = BotSettings(id=state.BOT_ID, name="local", configurationTextContent=config_text)

    config = state.load_bot_config()
    try:
        new_settings = BotSettings.from_config_dict(
            config,
            prev=state.BOT_CONFIG if isinstance(state.BOT_CONFIG, BotSettings) else None,
        )
        if isinstance(state.BOT_CONFIG, BotSettings):
            # state.console_log(f"Updating bot configuration from local config: {new_settings}")
            state.BOT_CONFIG.__dict__.update(new_settings.__dict__)
        else:
            state.BOT_CONFIG = new_settings
            state.console_log(f"Setting initial bot configuration from local config: {state.BOT_CONFIG}")
    except Exception as e:
        import traceback

        state.console_log("Failed to parse bot configuration from local config, using defaults. " f"Error: {e}")
        state.console_log(traceback.format_exc())
    start_config_background_refresh()

    if state.PORT is None or state.PORT == "":
        state.PORT = state.BOT_CONFIG.PORT

    try:
        int(state.PORT)
        state.DEVICE = "127.0.0.1:" + state.PORT
    except ValueError:
        state.DEVICE = state.PORT
    state.console_log(f"Using DEVICE: {state.DEVICE}")

    adb_helpers.disconnect(state.DEVICE)
    adb_helpers.ensure_connected(state.DEVICE)

    # Enable/disable show_touches overlay based on config
    adb_helpers.set_show_touches(state.DEVICE, enabled=state.BOT_CONFIG.ADB_SHOW_TAP, ign=state.BOT_CONFIG.IGN)

    print("----------------------Configuration----------------------")
    console_log_with_ign(state.BOT_CONFIG.IGN, f"Configuration Text Content:\n{state.BOT_CONFIG.configurationTextContent}")
    print("----------------------Configuration----------------------")

    if reopen or adb_helpers.check_if_app_is_open(state.DEVICE, ign=state.BOT_CONFIG.IGN) == False:
        console_log_with_ign(state.BOT_CONFIG.IGN, "App is not open or --reopen specified, reopening app...")
        adb_helpers.reopen_app(state.DEVICE, ign=state.BOT_CONFIG.IGN)

    # Load map locations from local file
    map_ids = [m.strip() for m in str(state.BOT_CONFIG.MAP).split(",") if m.strip()]
    state.MAP_INFOS = local_data.load_map_locations(map_ids)
    state.console_log(
        f"MAP_INFOS: {[
            f'{m.id} ({m.name}) [red={sum(1 for b in m.bosses if b.bossType == 1)}, '
            f'gold={sum(1 for b in m.bosses if b.bossType == 2)}]'
            for m in state.MAP_INFOS
        ]}"
    )

    is_in_progress_reopen = False
    afkmode = args.afk_mode if args.afk_mode else False
    if state.BOT_CONFIG.AFK_MODE or afkmode:
        console_log_with_ign(state.BOT_CONFIG.IGN, "AFK_MODE is enabled, going to AFK spot...")
        while True:
            try:
                go_to_buffer(state.DEVICE, state.BOT_CONFIG.IGN)
                go_to_afk_spot(state.DEVICE)
                time.sleep(30 * 60)
            except ResetRaise:
                console_log_with_ign(state.BOT_CONFIG.IGN, "Caught ResetRaise -> performing reset logic...")

    import bot_buffer

    device = state.DEVICE
    if state.BOT_CONFIG.IS_BUFFER:
        run_buffer_mode(state.DEVICE, state.BOT_CONFIG.IGN)

    console_log_with_ign(state.BOT_CONFIG.IGN, "Starting main bot loop...")
    while True:
        state.check_bot_paused()
        try:
            go_to_spot(state.DEVICE, skip_buffer=state.SKIP_BUFFER)

            state.SKIP_BUFFER = False
        except ResetRaise:
            console_log_with_ign(state.BOT_CONFIG.IGN, "Caught ResetRaise -> performing reset logic...")
            try:
                adb_helpers.go_to_starting_position(device=state.DEVICE, ign=state.BOT_CONFIG.IGN, debug=state.BOT_CONFIG.DEBUG)
                time.sleep(5)
            except Exception as e:
                state.console_log(f"Failed during reset: {e}")
        except RestartRaise:
            console_log_with_ign(state.BOT_CONFIG.IGN, "Caught RestartRaise -> performing restart logic...")

            if not is_in_progress_reopen:
                is_in_progress_reopen = True
                try:
                    state.console_log("Restart triggered. Restarting bot loop.")
                    try:
                        adb_helpers.go_to_starting_position(device=state.DEVICE, ign=state.BOT_CONFIG.IGN, debug=state.BOT_CONFIG.DEBUG)
                    except Exception as e:
                        state.console_log(f"Failed to go_to_starting_position, non-fatal: {e}")

                    state.console_log("Reopening app...")
                    try:
                        adb_helpers.reopen_app(state.DEVICE, ign=state.BOT_CONFIG.IGN)
                    except Exception as e:
                        state.console_log(f"Failed to reopen app, non-fatal: {e}")
                    try:
                        adb_helpers.do_clear_screen(state.DEVICE, ign=state.BOT_CONFIG.IGN, click_x=True)
                    except Exception as e:
                        state.console_log(f"Failed to clear screen, non-fatal: {e}")
                finally:
                    is_in_progress_reopen = False
        except Exception as e:
            console_log_with_ign(state.BOT_CONFIG.IGN, f"Unhandled error in bot loop: {e}")

            try:
                adb_helpers.disconnect(state.DEVICE)
            except Exception:
                pass

            try:
                adb_helpers.ensure_connected(state.DEVICE)
            except Exception:
                pass

            try:
                import traceback

                console_log_with_ign(state.BOT_CONFIG.IGN, traceback.format_exc())
            except Exception:
                pass
            time.sleep(2)

        finally:
            stop_config_background_refresh()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(main(args))
