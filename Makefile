.PHONY: install migrate dev test lint fmt typecheck

install:
	uv sync --all-groups

migrate:
	uv run alembic upgrade head

dev:
	uv run python -m opdbot.main

test:
	uv run pytest -q

lint:
	uv run ruff check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy src
