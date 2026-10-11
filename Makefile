#!/usr/bin/make -f

.DEFAULT_GOAL := help
.PHONY: test unit-test integration-test linting check-types check-style check-format fix-linting fix-style fix-format help

test: ## Run the full test suite
	uv run pytest $(filter-out $@,$(MAKECMDGOALS))

unit-test: ## Run unit tests (exclude integration and entrypoint)
	uv run pytest -m "not integration and not entrypoint" $(filter-out $@,$(MAKECMDGOALS))

integration-test: ## Run integration and entrypoint tests
	uv run pytest -m "integration or entrypoint" $(filter-out $@,$(MAKECMDGOALS))

linting: check-types check-style check-format ## Run all linters

check-types: ## Run mypy
	uv run mypy .

check-style: ## Run ruff check
	uv run ruff check .

check-format: ## Run ruff format check
	uv run ruff format --check .

fix-linting: fix-format fix-style ## Fix format and style

fix-style: ## Fix style with ruff
	uv run ruff check --fix .

fix-format: ## Fix format with ruff
	uv run ruff format .

help: ## Display this help text
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
