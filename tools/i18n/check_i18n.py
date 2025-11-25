# tools/i18n/check_i18n.py

import sys
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[1] / "i18n"


def flatten(d, parent=""):
    out = {}
    for k, v in d.items():
        full = f"{parent}.{k}" if parent else k
        if isinstance(v, dict):
            out.update(flatten(v, full))
        else:
            out[full] = v
    return out


def load_lang(lang):
    lang_dir = BASE / lang
    data = {}
    for file in lang_dir.glob("*.yml"):
        with open(file, encoding="utf-8") as f:
            content = yaml.safe_load(f) or {}
            data.update(flatten(content))
    return data


def main():
    en = load_lang("en")
    ru = load_lang("ru")

    errors = []

    for key in en:
        if key not in ru:
            errors.append(f"[RU MISSING] {key}")

    for key in ru:
        if key not in en:
            errors.append(f"[EN MISSING] {key}")

    if errors:
        print("❌ I18N ERROR: missing keys")
        for e in errors:
            print("   ", e)
        sys.exit(1)

    print("✓ All i18n keys are in sync.")


if __name__ == "__main__":
    main()
