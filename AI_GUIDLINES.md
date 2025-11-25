# AI Guidelines for This Project

## GENERAL

1. All generated code must follow pyproject.toml style settings.
2. Do not use experiments or placeholder code.
3. Logging must use bot.utils.logging.get_logger.
4. Do not invent database fields that do not exist in bot/db/models.py.
5. Keep handlers small and modular.
6. When generating text for users, avoid fancy punctuation and non-breaking spaces.
7. Prompts for LLM features must live in ./prompts/.

## LANGUAGES

You are working inside a Python project that uses a strict i18n structure.

Project folders:

- i18n/en/\*.yml → English translations
- i18n/ru/\*.yml → Russian translations
- tools/i18n/\*.py → I18N tooling (Ruff plugin etc)
- bot/... → business logic (do NOT place i18n code here)

I18N RULES:

1. Every user-facing text must be stored in the i18n YAML files.
2. Keys must be hierarchical: section.subsection.key
   Example: profile.no_profile, search.not_found, errors.timeout
3. When adding a new text for the bot:
   - Add the EN version to i18n/en/<module>.yml under the correct section.
   - Add the matching RU version to i18n/ru/<module>.yml.
   - Use the same structure and keys in both languages.
4. Never hardcode user-facing strings inside Python code.
   Always load them via t("section.key", lang) from the loader.
5. YAML formatting must be simple:
   - Use plain ASCII quotes
   - No fancy unicode quotes
   - No em dashes
   - No non-breaking spaces
6. Each YAML file should contain only one top-level section:
   Example: profile.yml contains only "profile:", search.yml contains only "search:" etc.
7. When generating translations:
   - RU translations must sound natural, human and conversational.
   - EN translations must be clean and simple.
   - No academic tone.
   - Allow very small imperfections in RU to avoid AI-polished style.
8. When creating new YAML keys:
   - Keep them short and descriptive.
   - Group logically by module (profile, search, errors, start etc).
   - Avoid duplication.
9. The I18N Ruff plugin lives in tools/i18n/\*.py and checks that RU and EN contain the same keys.
   Maintain compatibility with its expectations.

CODING RULES:

- Do not move i18n code into the bot/ folder.
- Do not create side effects or placeholders.
- Do not invent keys that are not used.
- When editing translations, keep both languages always in sync.

WHEN ASKED TO CREATE OR UPDATE TEXTS:

- Output only YAML when editing YAML files.
- Output only Python when editing Python files.
- Follow the project structure exactly.
