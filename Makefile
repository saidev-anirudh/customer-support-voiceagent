.DEFAULT_GOAL := help
AGENT_DIR := agent
WEB_DIR := web

.PHONY: help setup dev console test test-all lint format web deploy update-secrets

help: ## List available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

setup: ## Install agent and web dependencies and download model files
	cd $(AGENT_DIR) && uv sync && uv run main.py download-files
	cd $(WEB_DIR) && pnpm install
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env, fill in your keys."; fi
	@if [ ! -f $(WEB_DIR)/.env.local ]; then cp $(WEB_DIR)/.env.example $(WEB_DIR)/.env.local; fi

dev: ## Run the agent against your LiveKit Cloud project (hot reload)
	cd $(AGENT_DIR) && uv run main.py dev

console: ## Talk to the agent from the terminal, no browser needed
	cd $(AGENT_DIR) && uv run main.py console

web: ## Run the browser client on http://localhost:3000
	cd $(WEB_DIR) && pnpm dev

test: ## Run the tests that need no credentials
	cd $(AGENT_DIR) && uv run pytest -m "not llm"

test-all: ## Run every test, including conversation flows (needs LLM credentials)
	cd $(AGENT_DIR) && uv run pytest

lint: ## Lint the agent and type-check the web client
	cd $(AGENT_DIR) && uv run ruff check . && uv run ruff format --check .
	cd $(WEB_DIR) && pnpm exec tsc --noEmit

format: ## Format the agent and web code
	cd $(AGENT_DIR) && uv run ruff format .
	cd $(WEB_DIR) && pnpm format

deploy: ## Deploy a new agent version to LiveKit Cloud (after the first `lk agent create`)
	cd $(AGENT_DIR) && lk agent deploy

update-secrets: ## Push values from .env to the deployed agent
	cd $(AGENT_DIR) && lk agent update-secrets --secrets-file ../.env --ignore-empty-secrets
