import os
from typing import Dict

HERE = os.path.dirname(__file__)


def _load_config_dat(path: str) -> Dict[str, str]:
    cfg: Dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                k = k.strip().upper()
                v = v.strip()
                if v.startswith("{") and v.endswith("}"):
                    v = v[1:-1].strip()
                if (v.startswith('"') and v.endswith('"')) or (
                    v.startswith("'") and v.endswith("'")
                ):
                    v = v[1:-1]
                cfg[k] = v
    except FileNotFoundError:
        return {}
    return cfg


_CONFIG = _load_config_dat(os.path.join(HERE, "config.dat"))


def get_value(key: str, default=None):
    k = key.strip().upper()
    if k in _CONFIG:
        return _CONFIG[k]
    return os.environ.get(k, default)
