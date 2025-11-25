# Use bash for convenience
set shell := ["bash", "-cu"]
set quiet := true

# Format, lint, and validate i18n in one go
check:
	uv run ruff format
	uv run ruff check
	uv run tools/i18n/check_i18n.py

# Start the bot, preferring an active virtualenv, then .venv, otherwise uv
start:
	@if [ -n "${VIRTUAL_ENV-}" ]; then \
		uv run main.py; \
	elif [ -d ".venv" ]; then \
		. .venv/bin/activate; \
		uv run main.py; \
	else \
		echo "Creating .venv and syncing deps..."; \
		uv venv; \
		. .venv/bin/activate; \
		uv sync; \
		uv run main.py; \
	fi
