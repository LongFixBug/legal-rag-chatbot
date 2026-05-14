SHELL := /bin/bash

COMPOSE := docker compose
COMPOSE_LLAMA := $(COMPOSE) --profile llama

.PHONY: help sync test smoke up down restart ps logs logs-api logs-streamlit health

help:
	@printf "Available targets:\n"
	@printf "  make sync          Install project dependencies with uv\n"
	@printf "  make test          Run pytest suite\n"
	@printf "  make smoke         Run runtime smoke test against the local API\n"
	@printf "  make up            Start full Docker stack with llama profile\n"
	@printf "  make down          Stop Docker stack\n"
	@printf "  make restart       Restart full Docker stack with rebuild\n"
	@printf "  make ps            Show Docker Compose service status\n"
	@printf "  make logs          Tail Docker Compose logs\n"
	@printf "  make logs-api      Tail API logs only\n"
	@printf "  make logs-streamlit Tail Streamlit logs only\n"
	@printf "  make health        Check API health endpoint\n"

sync:
	uv sync --dev

test:
	uv run pytest -q

smoke:
	bash scripts/smoke_test.sh

up:
	$(COMPOSE_LLAMA) up -d --build

down:
	$(COMPOSE_LLAMA) down

restart:
	$(COMPOSE_LLAMA) up -d --build

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f

logs-api:
	$(COMPOSE) logs -f api

logs-streamlit:
	$(COMPOSE) logs -f streamlit

health:
	curl -sS http://127.0.0.1:8000/health
