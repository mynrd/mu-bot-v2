from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class BotSettings:
    id: int = 0
    name: str = ""
    configurationTextContent: str = ""

    PORT: str = ""
    IGN: str = ""
    SKIP_NAMES: list[str] = field(default_factory=list)
    IGNORE_NAME: bool = False
    USE_TELEPORT: bool = False
    MAP: str = ""
    ENGAGE_RED_BOSS: bool = False
    ENGAGE_GOLDEN_BOSS: bool = False
    RADIUS_SEARCH: int = 120
    DEBUG: bool = False
    RESTART_AFTER_MINUTES: int = 60
    ON_WALK_MODE_GO_TO_STARTING_POINT: bool = False
    RETRY_COUNT_READ_LIFE_FAILS: int = 3
    DETECT_LOW_LIFE: bool = True
    TAP_ON_MAP_WHILE_WALKING: bool = True
    CHANNELS: str = ""
    THRESHOLD_DMG_RED: float = 40
    BUFFER: str = ""
    BUFFER_MAP: str = ""
    BUFFER_COORDINATE: str = ""
    DEBUFF_BEFORE_BUFF: bool = True
    AFK_MODE: bool = False
    IS_BUFFER: bool = False
    BUFFER_WHITELIST_NAMES: list[str] = field(default_factory=list)
    BUFFER_WHITELIST_GUILDS: list[str] = field(default_factory=list)
    TAP_SKILL_CANCEL_ATTACK_COORDS: Tuple[float, float] = None

    ADB_SHOW_TAP: bool = False
    SKIP_VALIDATION_BUFF: bool = False
    SKIP_BUFFER: bool = False
    DEBUG_MODE_ON_MAX_RETRIES_EXCEEDED_ON_ATTACK: bool = False
    ALLIANCE_MODE: bool = False

    @staticmethod
    def _to_bool(val: str | bool) -> bool:
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("1", "true", "yes", "on")

    @classmethod
    def from_config_dict(cls, config: dict, prev=None) -> "BotSettings":
        return cls(
            id=prev.id if prev else 0,
            name=prev.name if prev else "",
            configurationTextContent=prev.configurationTextContent if prev else "",
            PORT=config.get("PORT", prev.PORT if prev else ""),
            IGN=config.get("IGN", prev.IGN if prev else ""),
            SKIP_NAMES=[s.strip() for s in config.get("SKIP_NAMES", "").split(",") if s.strip()],
            IGNORE_NAME=cls._to_bool(config.get("IGNORE_NAME", prev.IGNORE_NAME if prev else False)),
            USE_TELEPORT=cls._to_bool(config.get("USE_TELEPORT", prev.USE_TELEPORT if prev else False)),
            MAP=config.get("MAP", prev.MAP if prev else ""),
            ENGAGE_RED_BOSS=cls._to_bool(config.get("ENGAGE_RED_BOSS", prev.ENGAGE_RED_BOSS if prev else False)),
            ENGAGE_GOLDEN_BOSS=cls._to_bool(config.get("ENGAGE_GOLDEN_BOSS", prev.ENGAGE_GOLDEN_BOSS if prev else False)),
            RADIUS_SEARCH=int(config.get("RADIUS_SEARCH", prev.RADIUS_SEARCH if prev else 120)) if config.get("RADIUS_SEARCH") else (prev.RADIUS_SEARCH if prev else 120),
            DEBUG=cls._to_bool(config.get("DEBUG", prev.DEBUG if prev else False)),
            RESTART_AFTER_MINUTES=int(config.get("RESTART_AFTER_MINUTES", prev.RESTART_AFTER_MINUTES if prev else 60)) if config.get("RESTART_AFTER_MINUTES") else (prev.RESTART_AFTER_MINUTES if prev else 60),
            ON_WALK_MODE_GO_TO_STARTING_POINT=cls._to_bool(config.get("ON_WALK_MODE_GO_TO_STARTING_POINT", prev.ON_WALK_MODE_GO_TO_STARTING_POINT if prev else False)),
            RETRY_COUNT_READ_LIFE_FAILS=int(config.get("RETRY_COUNT_READ_LIFE_FAILS", prev.RETRY_COUNT_READ_LIFE_FAILS if prev else 3)) if config.get("RETRY_COUNT_READ_LIFE_FAILS") else (prev.RETRY_COUNT_READ_LIFE_FAILS if prev else 3),
            DETECT_LOW_LIFE=cls._to_bool(config.get("DETECT_LOW_LIFE", prev.DETECT_LOW_LIFE if prev else True)),
            TAP_ON_MAP_WHILE_WALKING=cls._to_bool(config.get("TAP_ON_MAP_WHILE_WALKING", prev.TAP_ON_MAP_WHILE_WALKING if prev else True)),
            CHANNELS=config.get("CHANNELS", prev.CHANNELS if prev else ""),
            THRESHOLD_DMG_RED=float(config.get("THRESHOLD_DMG_RED", prev.THRESHOLD_DMG_RED if prev else 40)),
            BUFFER=config.get("BUFFER", prev.BUFFER if prev else ""),
            BUFFER_MAP=config.get("BUFFER_MAP", prev.BUFFER_MAP if prev else ""),
            BUFFER_COORDINATE=config.get("BUFFER_COORDINATE", prev.BUFFER_COORDINATE if prev else ""),
            DEBUFF_BEFORE_BUFF=cls._to_bool(config.get("DEBUFF_BEFORE_BUFF", prev.DEBUFF_BEFORE_BUFF if prev else True)),
            AFK_MODE=cls._to_bool(config.get("AFK_MODE", prev.AFK_MODE if prev else False)),
            IS_BUFFER=cls._to_bool(config.get("IS_BUFFER", prev.IS_BUFFER if prev else False)),
            BUFFER_WHITELIST_NAMES=[s.strip() for s in config.get("BUFFER_WHITELIST_NAMES", "").split(",") if s.strip()],
            BUFFER_WHITELIST_GUILDS=[s.strip() for s in config.get("BUFFER_WHITELIST_GUILDS", "").split(",") if s.strip()],
            TAP_SKILL_CANCEL_ATTACK_COORDS=tuple(map(float, config.get("TAP_SKILL_CANCEL_ATTACK_COORDS", "").split(","))) if config.get("TAP_SKILL_CANCEL_ATTACK_COORDS") else (prev.TAP_SKILL_CANCEL_ATTACK_COORDS if prev else None),

            ADB_SHOW_TAP=cls._to_bool(config.get("ADB_SHOW_TAP", prev.ADB_SHOW_TAP if prev else False)),
            SKIP_VALIDATION_BUFF=cls._to_bool(config.get("SKIP_VALIDATION_BUFF", prev.SKIP_VALIDATION_BUFF if prev else False)),
            SKIP_BUFFER=cls._to_bool(config.get("SKIP_BUFFER", prev.SKIP_BUFFER if prev else False)),
            DEBUG_MODE_ON_MAX_RETRIES_EXCEEDED_ON_ATTACK=cls._to_bool(config.get("DEBUG_MODE_ON_MAX_RETRIES_EXCEEDED_ON_ATTACK", prev.DEBUG_MODE_ON_MAX_RETRIES_EXCEEDED_ON_ATTACK if prev else False)),
            ALLIANCE_MODE=cls._to_bool(config.get("ALLIANCE_MODE", prev.ALLIANCE_MODE if prev else False)),
        )
