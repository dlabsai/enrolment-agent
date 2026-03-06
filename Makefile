SHELL := /bin/bash

ROOT_DIR := $(CURDIR)
PROJECT_NAME ?= $(notdir $(ROOT_DIR))
UID := $(shell id -u)
GID := $(shell id -g)
STATIC_PUBLIC_VOLUME := $(PROJECT_NAME)_static-public
STATIC_INTERNAL_VOLUME := $(PROJECT_NAME)_static-internal

export UID
export GID
export COMPOSE_IGNORE_ORPHANS ?= 1
export COMPOSE_PROGRESS ?= quiet

COMPOSE_FILES ?= -f docker-compose.yml -f docker-compose.prod.yml
COMPOSE := docker compose $(COMPOSE_FILES)

FRONTEND_HASH_FILE := frontend/.build-hash
BACKEND_HASH_FILE := backend/.build-hash

.PHONY: build frontend-build backend-build up demo wp-up wp-seed rag reset wait-db down

build: frontend-build backend-build

frontend-build:
	@hash=$$( \
		{ \
			cd frontend && find . -type f \
				-not -path './node_modules/*' \
				-not -path './dist*/*' \
				-not -path './.vite/*' \
				-not -path './.build-hash' \
				-print0 | sort -z | xargs -0 sha256sum; \
			if [[ -f "$(ROOT_DIR)/.env" ]]; then sha256sum "$(ROOT_DIR)/.env"; fi; \
			sha256sum "$(ROOT_DIR)/docker-compose.prod.yml"; \
		} | sha256sum | awk '{print $$1}'; \
	); \
	prev=$$(cat $(FRONTEND_HASH_FILE) 2>/dev/null || true); \
	if [[ -z "$$prev" || "$$hash" != "$$prev" ]]; then \
		echo "Frontend changed; building..."; \
		docker run --rm \
			-v $(STATIC_PUBLIC_VOLUME):/static-public \
			-v $(STATIC_INTERNAL_VOLUME):/static-internal \
			alpine:3.20 sh -c "chown -R $(UID):$(GID) /static-public /static-internal"; \
		$(COMPOSE) rm -f frontend-build >/dev/null 2>&1 || true; \
		$(COMPOSE) --profile build up -d frontend-build; \
		container_id=$$($(COMPOSE) ps -q frontend-build || true); \
		if [[ -z "$$container_id" ]]; then \
			echo "frontend-build container not running; cannot build frontends."; \
			exit 1; \
		fi; \
		echo "Waiting for frontend-build to finish..."; \
		docker logs -f "$$container_id" & \
		log_pid=$$!; \
		exit_code=$$(docker wait "$$container_id"); \
		kill "$$log_pid" >/dev/null 2>&1 || true; \
		if [[ "$$exit_code" != "0" ]]; then \
			echo "frontend-build failed (exit code $$exit_code)."; \
			exit 1; \
		fi; \
		echo "$$hash" > $(FRONTEND_HASH_FILE); \
	else \
		echo "Frontend unchanged; skipping build."; \
	fi; \
	$(COMPOSE) rm -f frontend-build >/dev/null 2>&1 || true

backend-build:
	@hash=$$(cd backend && find . -type f \
		-not -path './.venv/*' \
		-not -path './**/__pycache__/*' \
		-not -path './.pytest_cache/*' \
		-not -path './.build-hash' \
		-print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $$1}'); \
	prev=$$(cat $(BACKEND_HASH_FILE) 2>/dev/null || true); \
	if [[ -z "$$prev" || "$$hash" != "$$prev" ]]; then \
		echo "Backend changed; building image..."; \
		$(COMPOSE) build backend; \
		echo "$$hash" > $(BACKEND_HASH_FILE); \
	else \
		echo "Backend unchanged; skipping build."; \
	fi

up: build
	$(COMPOSE) up -d
	$(MAKE) wait-db
	$(MAKE) demo

demo:
	cd wordpress-demo && ./cli.sh all

wp-up:
	cd wordpress-demo && ./cli.sh up

wp-seed:
	cd wordpress-demo && ./cli.sh seed

rag:
	cd wordpress-demo && ./cli.sh rag

reset:
	cd wordpress-demo && ./cli.sh reset

wait-db:
	@container_id=$$($(COMPOSE) ps -q db); \
	if [[ -z "$$container_id" ]]; then \
		echo "Postgres container not found."; \
		exit 1; \
	fi; \
	echo "Waiting for Postgres to be healthy..."; \
	for _ in {1..40}; do \
		status=$$(docker inspect --format '{{.State.Health.Status}}' "$$container_id" 2>/dev/null || true); \
		if [[ "$$status" == "healthy" ]]; then \
			exit 0; \
		fi; \
		sleep 3; \
	done; \
	echo "Postgres did not become healthy in time."; \
	exit 1

down:
	$(COMPOSE) --profile wp-demo down
