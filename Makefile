# Development: containers run locally, the database is the hosted Supabase STAGING project in .env.
# Run `make help` for the list. Never point these at production.
ifeq ($(OS),Windows_NT)
# In PowerShell/cmd, `bash` on PATH is the WSL launcher (or nothing), and make then falls
# back to cmd.exe. Use Git Bash, installed with Git for Windows, so make works from any terminal.
SHELL := C:/Program Files/Git/bin/bash.exe
else
SHELL := bash
endif
.DEFAULT_GOAL := help

COMPOSE := docker compose -f infra/docker-compose.yml --env-file .env
GIT_COMMIT := $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)
export GIT_COMMIT

.PHONY: help
help: ## Show targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

.PHONY: install
install: ## Install Python and Node dependencies
	uv sync
	npm install
	cd apps/web && npm install

.PHONY: docker-check
docker-check:
	@docker info >/dev/null 2>&1 || { echo "Docker is not running: start Docker Desktop, wait until it says 'Engine running', then retry."; exit 1; }

.PHONY: dev
dev: docker-check ## Start API, worker, scheduler, Redis, Mailpit (database = staging), then the web dev server
	$(COMPOSE) up -d --build
	cd apps/web && npm run dev

.PHONY: up
up: docker-check ## Start backend containers only (API, worker, scheduler, Redis, Mailpit)
	$(COMPOSE) up -d --build

.PHONY: stop
stop: ## Stop the local containers (staging data is not touched)
	-$(COMPOSE) down

.PHONY: logs
logs: ## Follow backend container logs
	$(COMPOSE) logs -f --tail=100

.PHONY: lint
lint: ## Ruff, mypy, migration check, eslint, tsc, prettier
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy
	uv run python scripts/check_migrations.py
	cd apps/web && npm run lint && npm run typecheck && npm run format:check

.PHONY: format
format: ## Format Python and TypeScript
	uv run ruff format .
	uv run ruff check --fix .
	cd apps/web && npm run format

.PHONY: test
test: ## Fast unit tests (no database)
	uv run pytest -q -m "not db"

.PHONY: test-db
test-db: ## Database tests against STAGING (never production), then the isolation suite
	LEADGEN_USE_REAL_ENV=1 uv run pytest -q -m db packages apps
	$(MAKE) test-isolation

.PHONY: test-isolation
test-isolation: ## Tenant isolation suite (seeds Agency A/B on STAGING)
	uv run pytest tests/isolation -q

.PHONY: migrate
migrate: push-staging ## Apply new migrations to staging (same as push-staging)

.PHONY: push-staging
push-staging: ## Apply new migrations to the STAGING project (refuses anything else)
	uv run python scripts/push_staging.py --dry-run
	uv run python scripts/push_staging.py

.PHONY: db-roles
db-roles: ## Set passwords on the app_api / app_system login roles from .env
	uv run python -m api.cli db-roles

.PHONY: psql
psql: ## Run SQL on staging as admin: make psql sql="select 1"  (or pipe SQL in)
	@if [ -n "$(sql)" ]; then uv run python scripts/psql.py admin -c "$(sql)"; else uv run python scripts/psql.py admin; fi

.PHONY: requirements
requirements: ## Refresh requirements.txt files used by pip-audit
	uv export --package api --no-dev --no-hashes --no-emit-workspace --frozen -q -o apps/api/requirements.txt
	uv export --package worker --no-dev --no-hashes --no-emit-workspace --frozen -q -o apps/worker/requirements.txt

.PHONY: audit
audit: requirements ## Secrets, insecure patterns and vulnerable packages
	gitleaks detect --source . --redact
	uv run pip-audit -r apps/api/requirements.txt -r apps/worker/requirements.txt
	cd apps/web && npm audit --audit-level=high

.PHONY: migration-tenant
migration-tenant: ## New tenant-table migration from the template: make migration-tenant name=leads
	@test -n "$(name)" || (echo "usage: make migration-tenant name=<table>" && exit 2)
	uv run python scripts/new_tenant_table.py $(name)

.PHONY: seed-test
seed-test: ## Seed Agency A/B test users on STAGING and write .env.test.local (tokens last 15 min)
	uv run python -m api.cli seed-test
