import threading
import time
from datetime import datetime, timedelta

import bot_state as state
from bot_settings import BotSettings
from util import console_log_with_ign


def _refresh_map_locations_loop(stop_event: threading.Event):
    """Background worker: refresh MAP_INFOS every 10 seconds from local data/map_locations.json."""
    import local_data

    while not stop_event.is_set():
        try:
            map_ids = [m.strip() for m in str(state.BOT_CONFIG.MAP).split(",") if m.strip()]
            state.MAP_INFOS = local_data.load_map_locations(map_ids)
        except Exception as e:
            state.console_log(f"Map locations refresh error: {e}")
        finally:
            stop_event.wait(10.0)


def _refresh_bot_config_loop(stop_event: threading.Event):
    """Background worker: reload config from config/bot_config.ini every 5 seconds."""
    import local_data

    while not stop_event.is_set():
        try:
            config_text = local_data.load_config_text(botname=state.BOT_NAME)
            with state.BOT_CONFIG_LOCK:
                state.CONFIG_CONTENT = config_text
                state.BOT_CONFIG.configurationTextContent = config_text
                config = state.load_bot_config()
                try:
                    new_settings = BotSettings.from_config_dict(config, prev=state.BOT_CONFIG if isinstance(state.BOT_CONFIG, BotSettings) else None)
                    if isinstance(state.BOT_CONFIG, BotSettings):
                        state.BOT_CONFIG.__dict__.update(new_settings.__dict__)
                except Exception:
                    pass
        except Exception as e:
            state.console_log(f"Config refresh error: {e}")
        stop_event.wait(5.0)


def _hourly_monitor_loop(stop_evt: threading.Event) -> None:
    """Triggers a restart exactly every hour (or RESTART_AFTER_MINUTES)."""
    if state._APP_START_TIME is None:
        state._APP_START_TIME = datetime.now()

    next_trigger = state._APP_START_TIME + timedelta(hours=1)

    while not stop_evt.is_set():
        now = datetime.now()
        while now >= next_trigger:
            next_trigger += timedelta(hours=1)

        wait_seconds = (next_trigger - now).total_seconds()
        console_log_with_ign(state.BOT_CONFIG.IGN, f"Hourly monitor: waiting {wait_seconds:.1f} seconds until next trigger ({next_trigger}).")

        if stop_evt.wait(timeout=max(0.0, wait_seconds)):
            break

        try:
            if state.CURRENT_TARGET is not None:
                console_log_with_ign(state.BOT_CONFIG.IGN, f"Hourly monitor: currently targeting boss {state.CURRENT_TARGET}, skipping restart.")
                time.sleep(3)
                continue

            if state.BOT_CONFIG.AFK_MODE:
                console_log_with_ign(state.BOT_CONFIG.IGN, "Hourly monitor: AFK mode is enabled, skipping restart.")
                return

            console_log_with_ign(state.BOT_CONFIG.IGN, "Hourly monitor: triggering bot restart.")
            from bot_exceptions import RestartRaise
            raise RestartRaise("Hourly monitor restart.")
        except Exception as e:
            console_log_with_ign(state.BOT_CONFIG.IGN, f"Hourly monitor error while triggering: {e}")

        next_trigger += timedelta(hours=1)


def start_config_background_refresh():
    """Start the background threads that refresh BOT_CONFIG, map locations, and hourly monitor."""
    if state._CONFIG_REFRESH_THREAD and state._CONFIG_REFRESH_THREAD.is_alive():
        return
    console_log_with_ign(state.BOT_CONFIG.IGN, "Starting config background refresh thread.")
    t = threading.Thread(
        target=_refresh_bot_config_loop,
        args=(state._CONFIG_REFRESH_STOP,),
        daemon=True,
        name="bot-config-refresher",
    )
    state._CONFIG_REFRESH_THREAD = t
    t.start()

    if not (state._HOURLY_THREAD and state._HOURLY_THREAD.is_alive()):
        console_log_with_ign(state.BOT_CONFIG.IGN, "Starting hourly monitor thread.")
        t2 = threading.Thread(
            target=_hourly_monitor_loop,
            args=(state._HOURLY_STOP,),
            daemon=True,
            name="hourly-monitor",
        )
        state._HOURLY_THREAD = t2
        t2.start()

    if not (state._MAP_REFRESH_THREAD and state._MAP_REFRESH_THREAD.is_alive()):
        console_log_with_ign(state.BOT_CONFIG.IGN, "Starting map-locations background refresh thread.")
        t3 = threading.Thread(
            target=_refresh_map_locations_loop,
            args=(state._MAP_REFRESH_STOP,),
            daemon=True,
            name="map-locations-refresher",
        )
        state._MAP_REFRESH_THREAD = t3
        t3.start()


def stop_config_background_refresh():
    """Signal the background refresher threads to stop and join briefly."""
    console_log_with_ign(state.BOT_CONFIG.IGN, "Stopping config background refresh thread.")
    state._CONFIG_REFRESH_STOP.set()
    t = state._CONFIG_REFRESH_THREAD
    if t is not None:
        try:
            t.join(timeout=1.0)
        except Exception:
            pass

    console_log_with_ign(state.BOT_CONFIG.IGN, "Stopping hourly monitor thread.")
    state._HOURLY_STOP.set()
    ht = state._HOURLY_THREAD
    if ht is not None:
        try:
            ht.join(timeout=1.0)
        except Exception:
            pass

    console_log_with_ign(state.BOT_CONFIG.IGN, "Stopping map-locations background refresh thread.")
    state._MAP_REFRESH_STOP.set()
    mt = state._MAP_REFRESH_THREAD
    if mt is not None:
        try:
            mt.join(timeout=1.0)
        except Exception:
            pass
