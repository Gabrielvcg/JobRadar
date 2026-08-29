PYTHON ?= python

.PHONY: install lint test migrate ingest run down

install:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m mypy app tests

test:
	$(PYTHON) -m pytest

migrate:
	alembic upgrade head

ingest:
	$(PYTHON) -m app.cli ingest

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

down:
	docker compose down

