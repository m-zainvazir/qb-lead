# Local development. Run `make help` for the list. Never point these at production.
SHELL := bash
.DEFAULT_GOAL := help

COMPOSE := docker compose -f infra/docker-compose.yml --env-file .env
SUPABASE := npx supabase
PSQL_ADMIN := docker exec -i supabase_db_leadgen psql -v ON_ERROR_STOP=1 -U postgres -d postgres
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

.PHONY: env
env: ## Create .env and apps/web/.env.local from the local Supabase stack
	$(SUPABASE) start
	uv run python scripts/make_env.py

.PHONY: dev
dev: ## Start Supabase, API, worker, scheduler, Redis, then the web dev server
	$(SUPABASE) start
	$(MAKE) db-roles
	$(COMPOSE) up -d --build
	cd apps/web && npm run dev

.PHONY: up
up: ## Start backend containers only (Supabase must be running)
	$(COMPOSE) up -d --build

.PHONY: stop
stop: ## Stop containers and the Supabase stack (data is kept)
	-$(COMPOSE) down
	$(SUPABASE) stop

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
test-db: ## Database and isolation tests against the LOCAL stack
	LEADGEN_USE_REAL_ENV=1 uv run pytest -q -m db packages apps tests

.PHONY: migrate
migrate: ## Apply new local migrations (no reset, keeps data)
	$(SUPABASE) migration up --local

.PHONY: db-reset
db-reset: ## LOCAL ONLY: rebuild the local database from migrations and seed
	$(SUPABASE) db reset --local
	$(MAKE) db-roles

.PHONY: db-roles
db-roles: ## Set passwords on the app_api / app_system login roles from .env
	uv run python -m api.cli db-roles

.PHONY: psql
psql: ## Open psql on the local database as the admin role
	docker exec -it supabase_db_leadgen psql -U postgres -d postgres

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
