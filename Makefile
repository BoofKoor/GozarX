COMPOSE := docker compose

.PHONY: help up down logs ps build sync migrate revision upgrade seed fmt lint check test shell install

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Build + start all services
	$(COMPOSE) up -d --build

down: ## Stop services
	$(COMPOSE) down

logs: ## Tail service logs
	$(COMPOSE) logs -f --tail=100

ps: ## Show service status
	$(COMPOSE) ps

build: ## Build images
	$(COMPOSE) build

sync: ## Install backend deps locally with uv
	cd backend && uv sync

migrate: ## Apply migrations inside the running app container
	$(COMPOSE) exec app alembic upgrade head

revision: ## Autogenerate a migration locally (usage: make revision NAME="add users")
	cd backend && uv run alembic revision --autogenerate -m "$(NAME)"

upgrade: ## Apply migrations locally
	cd backend && uv run alembic upgrade head

seed: ## Run the seed script in the app container
	$(COMPOSE) exec app python -m gozar.seed

fmt: ## Format code (ruff)
	cd backend && uv run ruff format .

lint: ## Lint code (ruff)
	cd backend && uv run ruff check .

check: ## Byte-compile the package
	cd backend && uv run python -m compileall -q gozar

test: ## Run tests
	cd backend && uv run pytest

shell: ## Open a shell in the app container
	$(COMPOSE) exec app sh

install: ## Run the zero-touch installer (Phase 9)
	./install.sh
