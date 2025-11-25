from functools import lru_cache
from pathlib import Path

from bot.utils.logging import get_logger

logger = get_logger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """Load prompt text from prompts/{name}.txt with caching."""
    path = PROMPTS_DIR / f"{name}.txt"
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {path}")
        return ""
    except Exception as e:
        logger.error(f"Failed to load prompt {name}: {e}")
        return ""
