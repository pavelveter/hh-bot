"""Helpers for storing per-query thread bindings and delivery state."""


def normalize_search_query_key(query_text: str) -> str:
    return " ".join(query_text.split()).casefold()


def get_query_thread_map(prefs: dict) -> dict[str, int]:
    raw_map = prefs.get("query_threads")
    if not isinstance(raw_map, dict):
        return {}

    normalized: dict[str, int] = {}
    for key, value in raw_map.items():
        if not isinstance(key, str):
            continue
        if not isinstance(value, int):
            continue
        normalized[key] = value
    return normalized


def get_sent_vacancy_ids_by_query(prefs: dict) -> dict[str, list[str]]:
    raw_map = prefs.get("sent_vacancy_ids_by_query")
    if not isinstance(raw_map, dict):
        return {}

    normalized: dict[str, list[str]] = {}
    for key, value in raw_map.items():
        if not isinstance(key, str) or not isinstance(value, list):
            continue
        normalized[key] = [str(item) for item in value if item]
    return normalized
