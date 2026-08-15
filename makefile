# Convenience runner for common dev tasks.
# Usage:  make <target>
#
# The local workflow uses `uv` (https://docs.astral.sh/uv/) for fast
# reproducible Python tooling. The Docker build also uses uv — see
# Dockerfile — so local and container environments match.
#
# Why a Makefile? It documents the canonical commands so a new student
# never has to guess how to run migrations, tests, or start the stack.

.PHONY: help install dev sync lint format typecheck test run up down logs ps migrate fresh shell

PYTHON ?= python
UV     ?= uv
COMPOSE ?= docker compose

help:                       ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "\033[36m%-14s\033[0m %s\n", $$1, $$2}'

# --- Local uv workflow -----------------------------------------------------
# `uv sync --all-extras` reads pyproject.toml + uv.lock and creates a
# `.venv` in the project root. Run this once on a fresh clone.

sync:                       ## Create/update the .venv from uv.lock (dev + extras)
	$(UV) sync --all-extras

dev: sync                   ## Alias: same as `make sync`
	@true

install:                    ## Sync only runtime deps (no dev extras)
	$(UV) sync --no-dev

# Tooling wrappers run inside the project's venv via `uv run`, so students
# don't need to remember to `source .venv/bin/activate`.

lint:                       ## Run ruff (lint only)
	$(UV) run ruff check app tests

format:                     ## Format with black + ruff --fix
	$(UV) run black app tests
	$(UV) run ruff check --fix app tests

typecheck:                  ## Run mypy
	$(UV) run mypy app

test:                       ## Run pytest
	$(UV) run pytest -v

run:                        ## Start uvicorn locally (without Docker)
	$(UV) run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# --- Docker stack --------------------------------------------------------

up:                         ## Build + start api, postgres (and redis)
	$(COMPOSE) up --build -d

down:                       ## Stop and remove containers (keep volumes)
	$(COMPOSE) down

logs:                       ## Tail container logs
	$(COMPOSE) logs -f api

ps:                         ## Show container status
	$(COMPOSE) ps

migrate:                    ## Apply Alembic migrations inside the api container
	$(COMPOSE) exec api alembic upgrade head

fresh:                      ## Danger: drop volume + re-run migrations
	$(COMPOSE) down -v
	$(COMPOSE) up --build -d
	@echo "Stack recreated. Run \`make migrate\` once api is healthy."

shell:                      ## Open a shell in the api container
	$(COMPOSE) exec api bash