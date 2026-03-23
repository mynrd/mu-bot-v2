"""Local data module – replaces bot_api.py.

Reads configuration from config/bot_config.ini and map/boss data from
data/map_locations.json.  Writes attack records and coins to data/ folder.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(_HERE, "config")
DATA_DIR = os.path.join(_HERE, "data")

_file_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Dataclasses (moved from bot_api.py)
# ---------------------------------------------------------------------------

@dataclass
class BossChannelInfoDto:
    channel: int
    isAlive: bool
    detectedAt: Optional[datetime]

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "BossChannelInfoDto":
        return BossChannelInfoDto(
            channel=int(d.get("channel") or 0),
            isAlive=bool(d.get("isAlive", False)),
            detectedAt=_parse_iso8601(d.get("detectedAt")),
        )


@dataclass
class BossDto:
    id: int
    name: str
    coordX: int
    coordY: int
    bossType: int
    durationToRevive: int
    mapId: Optional[str]
    bossChannelInfo: List[BossChannelInfoDto] | None = None

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "BossDto":
        bci_raw = d.get("bossChannelInfo") or []
        bci_list = []
        if isinstance(bci_raw, list):
            bci_list = [BossChannelInfoDto.from_dict(x) for x in bci_raw if isinstance(x, dict)]

        return BossDto(
            id=int(d.get("id")),
            name=str(d.get("name") or ""),
            coordX=int(d.get("coordX") or 0),
            coordY=int(d.get("coordY") or 0),
            bossType=int(d.get("bossType") or 0),
            durationToRevive=int(d.get("durationToRevive") or 0),
            mapId=d.get("mapId"),
            bossChannelInfo=bci_list,
        )


@dataclass
class MapLocation:
    id: int
    mapId: Optional[str]
    name: Optional[str]
    totalChannel: int
    bosses: List[BossDto]

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "MapLocation":
        bosses_raw = d.get("bosses")
        if not isinstance(bosses_raw, list):
            raise ValueError("MapLocation payload missing required 'bosses' array")
        bosses_list = [BossDto.from_dict(x) for x in bosses_raw if isinstance(x, dict)]
        return MapLocation(
            id=int(d.get("id")),
            mapId=d.get("mapId"),
            name=d.get("name"),
            totalChannel=int(d.get("totalChannel") or 0),
            bosses=bosses_list,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_iso8601(dt: Optional[str]) -> Optional[datetime]:
    if not dt:
        return None
    try:
        return datetime.fromisoformat(str(dt).replace("Z", "+00:00"))
    except Exception:
        return None


def _to_utc_iso(dt: datetime) -> str:
    from datetime import timezone
    dt_utc = (dt if dt.tzinfo is not None else dt.astimezone()).astimezone(timezone.utc)
    return dt_utc.isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Config – read from config/bot_config.ini
# ---------------------------------------------------------------------------

def load_config_text() -> str:
    """Read the raw text content of config/bot_config.ini."""
    path = os.path.join(CONFIG_DIR, "bot_config.ini")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Map locations – read from data/map_locations.json
# ---------------------------------------------------------------------------

def load_map_locations(map_ids: List[str] | None = None) -> List[MapLocation]:
    """Load map locations from data/map_locations.json, optionally filtered by map_ids."""
    path = os.path.join(DATA_DIR, "map_locations.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Map locations file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Expected a list in {path}, got {type(data)}")

    locations = [MapLocation.from_dict(item) for item in data if isinstance(item, dict)]

    if map_ids:
        normalized = [m.strip().lower() for m in map_ids if m.strip()]
        locations = [loc for loc in locations if (loc.mapId or "").lower() in normalized]

    return locations


def save_map_locations(locations: List[MapLocation]) -> None:
    """Write map locations back to data/map_locations.json."""
    path = os.path.join(DATA_DIR, "map_locations.json")

    def _boss_to_dict(b: BossDto) -> dict:
        d = {
            "id": b.id,
            "name": b.name,
            "coordX": b.coordX,
            "coordY": b.coordY,
            "bossType": b.bossType,
            "durationToRevive": b.durationToRevive,
            "mapId": b.mapId,
        }
        return d

    data = []
    for loc in locations:
        data.append({
            "id": loc.id,
            "mapId": loc.mapId,
            "name": loc.name,
            "totalChannel": loc.totalChannel,
            "bosses": [_boss_to_dict(b) for b in loc.bosses],
        })

    with _file_lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Attack records – append to data/attack_records.json
# ---------------------------------------------------------------------------

def add_attack_record(
    *,
    bot_id: int = 0,
    boss_id: Optional[int] = None,
    coin: Optional[float] = None,
    coin_bound: Optional[float] = None,
    start_attack: Optional[datetime] = None,
    end_attack: Optional[datetime] = None,
    map_id: str = "",
    found_attack_name: str = "",
) -> None:
    """Append an attack record to data/attack_records.json."""
    path = os.path.join(DATA_DIR, "attack_records.json")

    record = {
        "botId": bot_id,
        "bossId": boss_id,
        "coin": coin,
        "coinBound": coin_bound,
        "startAttack": _to_utc_iso(start_attack) if isinstance(start_attack, datetime) else None,
        "endAttack": _to_utc_iso(end_attack) if isinstance(end_attack, datetime) else None,
        "mapId": map_id,
        "foundAttackName": found_attack_name,
    }

    with _file_lock:
        records = []
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except (json.JSONDecodeError, ValueError):
                records = []

        records.append(record)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)


# ---------------------------------------------------------------------------
# Coins – save to data/bot_state.json
# ---------------------------------------------------------------------------

def save_coins(coins: float) -> None:
    """Save coin balance to data/bot_state.json."""
    path = os.path.join(DATA_DIR, "bot_state.json")

    with _file_lock:
        state = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    state = json.load(f)
            except (json.JSONDecodeError, ValueError):
                state = {}

        state["coins"] = coins
        state["lastUpdated"] = _to_utc_iso(datetime.now())

        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# Boss state updates – update data/map_locations.json
# ---------------------------------------------------------------------------

def update_boss_fields(map_id: str, boss_id: int, fields: dict) -> bool:
    """Atomically update specific fields of a boss in the JSON file.

    Fields id, mapId, and bossChannelInfo are never modified.
    """
    _PROTECTED = {"id", "mapId", "bossChannelInfo"}
    path = os.path.join(DATA_DIR, "map_locations.json")

    with _file_lock:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for loc in data:
            if loc.get("mapId") == map_id:
                for boss in loc.get("bosses", []):
                    if boss.get("id") == boss_id:
                        for key, value in fields.items():
                            if key not in _PROTECTED:
                                boss[key] = value
                        with open(path, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2)
                        return True
    return False



def set_boss_found_dead(boss_id: int, channel: int) -> None:
    """Mark a boss as found dead (no-op for local, just logs)."""
    pass
