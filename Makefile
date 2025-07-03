.PHONY: help build up-dev down-dev

# Show available commands
help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

# Build all containers
build: ## Build all Docker containers
	docker-compose -f docker-compose.yml build

# Start all containers in detached mode
up-dev: ## Start all containers in detached mode
	docker-compose -f docker-compose.yml up -d

# Stop all containers
down-dev: ## Stop all containers
	docker-compose -f docker-compose.yml down