# GeoMeasure developer commands. Everything runs inside Docker Compose.
COMPOSE ?= docker compose
BACKEND := $(COMPOSE) exec backend

.DEFAULT_GOAL := help
.PHONY: help env up down logs backend-shell migrate revision test lint format frontend-install frontend-dev frontend-test frontend-build

help: ## List available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

env: ## Create .env from .env.example if it does not exist
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

up: env ## Build and start the stack (migrations run on backend start)
	$(COMPOSE) up --build -d
	@echo "App:      http://localhost:$${FRONTEND_PORT:-5173}"
	@echo "API docs: http://localhost:$${BACKEND_PORT:-8000}/api/docs"

down: ## Stop the stack (data volumes are kept)
	$(COMPOSE) down

logs: ## Follow logs from all services
	$(COMPOSE) logs -f --tail=200

backend-shell: ## Open a shell in the backend container
	$(BACKEND) bash

migrate: ## Apply database migrations
	$(BACKEND) alembic upgrade head

revision: ## Create a migration from model changes: make revision m="add column"
	@test -n "$(m)" || (echo 'usage: make revision m="message"' && exit 1)
	$(BACKEND) alembic revision --autogenerate -m "$(m)"

test: ## Run the backend test suite against the test database
	$(BACKEND) pytest

lint: ## Lint and check formatting
	$(BACKEND) ruff check .
	$(BACKEND) ruff format --check .

format: ## Auto-format and apply safe lint fixes
	$(BACKEND) ruff format .
	$(BACKEND) ruff check --fix .

frontend-install: ## Install frontend dependencies (local Node 22)
	cd frontend && npm ci

frontend-dev: ## Run the Vite dev server against the API on localhost:8000
	cd frontend && npm run dev

frontend-test: ## Run frontend tests
	cd frontend && npm run test

frontend-build: ## Type-check and build the frontend
	cd frontend && npm run build
