from functools import lru_cache
from pathlib import Path

import yaml

from bot.utils.logging import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
I18N_DIR = REPO_ROOT / "i18n"

if not I18N_DIR.exists():
    # Fallback for environments where package data lives next to bot/
    I18N_DIR = BASE_DIR / "i18n"


def detect_lang(user_lang: str | None) -> str:
    if not user_lang:
        return "en"
    code = user_lang.lower()
    if code.startswith("ru"):
        return "ru"
    return "en"


@lru_cache(maxsize=8)
def _load_lang(lang: str) -> dict:
    data: dict = {}
    lang_dir = I18N_DIR / lang
    if not lang_dir.exists():
        logger.warning(f"I18N directory not found for lang={lang}")
        return data
    for file in lang_dir.glob("*.yml"):
        try:
            loaded = yaml.safe_load(file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update(loaded)
        except Exception as e:
            logger.error(f"Failed to load i18n file {file}: {e}")
    return data


def _get_by_path(data: dict, path: str):
    cur = data
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def t(key: str, lang: str = "en", **kwargs) -> str:
    lang_data = _load_lang(lang)
    template = _get_by_path(lang_data, key)
    if template is None:
        # In case of stale cache (e.g., paths changed), try reloading once
        _load_lang.cache_clear()
        lang_data = _load_lang(lang)
        template = _get_by_path(lang_data, key)
    if template is None and lang != "en":
        # fallback to en
        template = _get_by_path(_load_lang("en"), key)
    if template is None:
        # hardcoded fallbacks for critical keys to avoid breaking user-facing text
        fallbacks = {
            "profile.on": {"en": "On", "ru": "Вкл"},
            "profile.on_tick": {"en": "On ✅", "ru": "Вкл ✅"},
            "profile.off": {"en": "Off", "ru": "Выкл"},
        }
        if key in fallbacks:
            template = fallbacks[key].get(lang) or fallbacks[key].get("en")
    if template is None:
        logger.warning(f"Missing i18n key: {key} for lang {lang}")
        return key
    try:
        return template.format(**kwargs)
    except Exception:
        return str(template)
