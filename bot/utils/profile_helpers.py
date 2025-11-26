import html
import math

from bot.utils.i18n import t


def short(text: str | None, lang: str, limit: int = 500, truncated_key: str = "profile.resume_truncated") -> str:
    if not text:
        return t("profile.not_set", lang)
    text = html.escape(text.strip())
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n" + t(truncated_key, lang)


def hide_key(key: str | None) -> str:
    if not key:
        return "not set"
    if len(key) < 6:
        return "***"
    return key[:3] + "***" + key[-2:]


def normalize_skills(raw: str) -> list[str]:
    """Convert mixed-format skill text (bullets/commas/newlines) into a clean list."""
    cleaned = raw.replace("•", "\n").replace("·", "\n").replace(";", ",").replace("—", "\n").replace("–", "\n")

    parts: list[str] = []
    for chunk in cleaned.split("\n"):
        parts.extend(chunk.split(","))

    skills: list[str] = []
    seen = set()
    for part in parts:
        item = part.strip()
        item = item.lstrip("-*•·–— ").strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        skills.append(item)
    return skills


def build_skills_preview(skills: list[str] | None, max_items: int = 5) -> tuple[int, str]:
    """Return total count and a spaced preview across the list (start/middle/end)."""
    cleaned = [s.strip().replace("\n", " ") for s in (skills or []) if s and s.strip()]
    count = len(cleaned)
    if count == 0:
        return 0, ""

    if count <= max_items:
        selected = cleaned
    else:
        span = count - 1
        indices = [math.floor(i * span / (max_items - 1)) for i in range(max_items)]
        seen = set()
        selected: list[str] = []
        for idx in indices:
            if idx in seen:
                continue
            seen.add(idx)
            selected.append(cleaned[idx])

    preview = ", ".join(selected)
    return count, preview


def format_search_filters(filters: dict | None, lang: str) -> str:
    filters = filters or {}
    min_salary = filters.get("min_salary")
    remote = filters.get("remote_only")
    freshness = filters.get("freshness_days")
    employment = filters.get("employment")
    experience = filters.get("experience")

    employment_label = t(f"profile.employment.{employment}", lang) if employment else t("profile.not_set", lang)
    experience_label = t(f"profile.experience.{experience}", lang) if experience else t("profile.not_set", lang)

    return (
        t("profile.search_filters.min_salary", lang).format(
            value=min_salary if min_salary else t("profile.not_set", lang)
        )
        + "\n"
        + t("profile.search_filters.remote", lang).format(
            state=t("profile.on", lang) if remote else t("profile.off", lang)
        )
        + "\n"
        + t("profile.search_filters.freshness", lang).format(value=freshness or t("profile.not_set", lang))
        + "\n"
        + t("profile.search_filters.employment", lang).format(value=employment_label)
        + "\n"
        + t("profile.search_filters.experience", lang).format(value=experience_label)
    )
