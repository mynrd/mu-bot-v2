# Bot Flow (bot.py)

## 1. Startup (`main()`)

1. Parse CLI args (or load from local config file if no args given)
2. Set state variables: `WAIT_BUFFER`, `SKIP_BUFFER`, `BOT_ID`, `PORT`
3. Start **Ctrl+P listener** thread (Windows only) - toggles `BOT_PAUSE`
4. Load bot config from `local_data` -> create `BotSettings`
5. Merge local config overrides into `BOT_CONFIG`
6. Start **config background refresh** thread
7. Resolve device address from PORT
8. ADB: disconnect + reconnect device
9. Set show_touches overlay based on config
10. Print configuration
11. Reopen app if `--reopen` flag or app not open
12. Load map locations from `local_data` for configured map IDs

## 2. Mode Selection

### AFK Mode (`--afk-mode` or `AFK_MODE` config)
```
Loop forever:
  go_to_buffer() -> go_to_afk_spot() -> sleep 30 minutes
  On ResetRaise: restart loop
```

### Buffer Mode (`IS_BUFFER` config)
```
Teleport to Endless Abyss
Loop forever:
  - Check app is open (reopen if closed)
  - Revive if dead -> teleport back to Endless Abyss
  - Run startBuffing()
  - After 1 hour: close app, reopen, re-teleport
  On exception: close app, retry
```

### Boss Hunting Mode (default)
```
Loop forever (main bot loop):
  go_to_spot(device, skip_buffer)
  skip_buffer = False (only skip once)

  Exception handlers:
  - ResetRaise:  go_to_starting_position, sleep 5s, retry loop
  - RestartRaise: go_to_starting_position, reopen app, clear screen, retry loop
  - Generic:     disconnect + reconnect ADB, log traceback, sleep 2s, retry loop
```

## 3. `go_to_spot()` - Boss Hunting Entry

```
1. go_to_buffer() (unless skip_buffer)
2. Loop:
   a. Check pause / exit / 25-min timeout
   b. For each map_id in config:
      - Set CURRENT_MAP_ID
      - go_to_map(device, map_id)
      - initiate_boss(device, map_id, map_name)
        -> if returns True: exit go_to_spot
      - Check exit flag
```

## 4. `initiate_boss()` - Channel Iteration

```
1. Determine channels to hunt (from config or all available)
2. For each channel:
   a. Set CURRENT_CHANNEL
   b. start_boss_hunting(device, ign, map_id)
      -> if returns False (25-min timeout):
         - Recycle inventory
         - Clear screen
         - go_to_buffer()
         - go_to_map() (back to current map)
   c. Check exit flag
```

## 5. `start_boss_hunting()` - Core Boss Loop

```
1. Clear screen, switch to target channel
2. Open map, scan for alive boss coordinates
3. Get invalid areas for the map

4. Loop:
   a. Check exit / 25-min timeout
   b. If no alive bosses -> return True (done)

   c. MODE: Teleport
      - Every 10 failed teleports: refresh map/screen
      - Log "Using teleportation..."

   d. MODE: Walk
      - Optionally go_to_starting_position (if ON_WALK_MODE_GO_TO_STARTING_POINT)
      - Clear screen, open map

   e. Escape invalid areas
   f. Find current location via player_locator_map
      - If location not found -> return True (exit)

   g. Find nearest boss from alive list
      - TELEPORT + no boss in radius:
        - Try random teleport (up to 10 attempts), then fallback to walking

   h. Tap on nearest boss on map

   i. _engage_boss_and_update():
      - Walk/teleport to boss (monitoring distance until near)
      - On arrival: engage_and_check_isvalid()
        - IF valid: monitor_until_its_gone() (combat loop)
          -> Save attack record
          -> Re-scan alive bosses
          -> Return to loop for next boss
        - IF not valid:
          -> Cancel attack
          -> go_to_starting_position  <-- (the issue you found)
          -> Check for stuck state
          -> Remove boss from alive list
          -> Return to loop for next boss

   j. Reset random_teleport_attempts on success
```

## 6. `engage_and_check_isvalid()` - Kill Validation

```
1. Tap attack button twice (enable auto-attack)
2. Wait 2 seconds
3. For each attempt (max 2):
   a. Check exit flag
   b. Grab screenshot
   c. Check boss_active_killing (template match for active boss icon)
      - If not active -> return False
   d. Special map "SB-": skip name check, return True
   e. OCR check_ign_exists in region (880, 1, 1300, 60)
      - No text found -> continue (retry)
      - Close match to IGN -> tap attack, return True
      - Skip name found -> return False
      - IGN found (exact) -> tap attack, return True
      - IGN not found -> mark boss as dead in DB, retry
4. After all attempts fail -> return False
```

## 7. `monitor_until_its_gone()` - Combat Monitor

```
Loop:
  - Check pause
  - Revive if dead
  - Check boss still active (template match)
    - If gone: boss is dead, return
  - Check exit flag
  - Check for skip names (blacklisted players)
  - Sleep interval (2s)
```

## Flow Diagram (simplified)

```
main()
  |
  +-- AFK Mode -----> go_to_buffer -> go_to_afk_spot -> sleep loop
  |
  +-- Buffer Mode ---> teleport -> buff loop (1hr cycle)
  |
  +-- Boss Mode -----> go_to_spot()
                          |
                          +-> go_to_buffer()
                          +-> for each map:
                                go_to_map()
                                initiate_boss()
                                  |
                                  +-> for each channel:
                                        start_boss_hunting()
                                          |
                                          +-> scan bosses on map
                                          +-> loop:
                                                find nearest boss
                                                walk/teleport to boss
                                                engage_and_check_isvalid()
                                                  |
                                                  +-> valid: monitor_until_its_gone() -> next boss
                                                  +-> invalid: cancel -> next boss
```
