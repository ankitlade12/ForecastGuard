.PHONY: help setup test lint format clean build cli-demo docs

help:
	@echo "ForecastGuard — Make targets"
	@echo ""
	@echo "  make setup     Create venv and install deps (uv sync --extra dev)"
	@echo "  make test      Run pytest"
	@echo "  make lint      ruff check + ruff format --check + mypy strict"
	@echo "  make format    Auto-fix lint issues and format code"
	@echo "  make cli-demo  Run the clean replay example with strict gating"
	@echo "  make build     Build the wheel + sdist"
	@echo "  make docs      Build Sphinx docs (warnings are errors)"
	@echo "  make clean     Remove caches and build artifacts"

setup:
	uv sync --extra dev

test:
	uv run pytest

lint:
	uv run ruff check forecastguard/ tests/
	uv run ruff format --check forecastguard/ tests/
	uv run mypy forecastguard/ tests/

format:
	uv run ruff check --fix forecastguard/ tests/
	uv run ruff format forecastguard/ tests/

cli-demo:
	uv run forecastguard run --spec examples/adoption/replay-clean.yaml --strict

build:
	uv build

docs:
	uv run --extra docs sphinx-build -W --keep-going -b html docs docs/_build/html

clean:
	rm -rf .venv/ dist/ build/ docs/_build/ .pytest_cache/ .ruff_cache/ .mypy_cache/ htmlcov/ .coverage
	find forecastguard tests -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
