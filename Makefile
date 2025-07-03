.PHONY: help build-dev up-dev down-dev down-dev-v logs scrapy-shell api-shell elasticsearch-shell run-scrapy start-api clean

# Show available commands
help:
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Build all containers
build-dev: ## Build all Docker containers
	docker-compose -f docker-compose.yml build

# Start all containers in detached mode
up-dev: ## Start all containers in detached mode
	docker-compose -f docker-compose.yml up -d

# Stop all containers
down-dev: ## Stop all containers
	docker-compose -f docker-compose.yml down

# Clean up containers and images
clean: ## Stop containers and clean up Docker system
	docker-compose -f docker-compose.yml down -v
	docker system prune -f

# Default target - build and start everything
all: build-dev up-dev ## Build and start everything