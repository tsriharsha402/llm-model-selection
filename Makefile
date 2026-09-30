.PHONY: install test lint format estimate benchmark

install:
	pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .
	ruff check --fix .

# What a full run will cost. No API calls.
estimate:
	python -m model_selection estimate

# Needs ANTHROPIC_API_KEY. Shows the estimate and asks for confirmation before spending.
benchmark:
	python -m model_selection run
