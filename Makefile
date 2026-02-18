# Makefile for Investment Portfolio Project

.PHONY: help install setup clean test lint format run-collector run-dashboard db-setup

# Default target
help:
	@echo "Investment Portfolio System - Available Commands"
	@echo "================================================"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install      - Install Python dependencies"
	@echo "  make setup        - Full setup (venv + deps + database)"
	@echo "  make db-setup     - Initialize database schema"
	@echo ""
	@echo "Running:"
	@echo "  make run-collector - Start data collection agents"
	@echo "  make run-dashboard - Launch web dashboard"
	@echo ""
	@echo "Development:"
	@echo "  make test         - Run test suite"
	@echo "  make lint         - Run code linters"
	@echo "  make format       - Format code with black"
	@echo "  make clean        - Remove cache and temp files"
	@echo ""
	@echo "Optimization:"
	@echo "  make cost-report  - Show agent cost estimates"
	@echo ""

# Python virtual environment
venv:
	python3 -m venv venv
	@echo "✓ Virtual environment created"
	@echo "  Activate with: source venv/bin/activate"

# Install dependencies
install:
	pip install --upgrade pip
	pip install -r requirements.txt
	@echo "✓ Dependencies installed"

# Full setup
setup: venv install
	@echo ""
	@echo "Next steps:"
	@echo "1. Copy .env.example to .env and add your API keys"
	@echo "2. Run: make db-setup"
	@echo "3. Run: make run-collector"

# Database setup
db-setup:
	python scripts/setup_database.py

# Run data collector
run-collector:
	python agents/data_collector.py

# Run dashboard
run-dashboard:
	streamlit run dashboard/app.py

# Testing
test:
	pytest tests/ -v --cov=. --cov-report=html

# Linting
lint:
	flake8 agents/ analysis/ utils/ scripts/ --max-line-length=100
	mypy agents/ analysis/ utils/ --ignore-missing-imports

# Code formatting
format:
	black agents/ analysis/ utils/ scripts/ dashboard/ --line-length=100
	@echo "✓ Code formatted"

# Clean cache files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ htmlcov/ .coverage
	@echo "✓ Cleaned cache files"

# Cost reporting
cost-report:
	python agents/agent_config.py

# Backup database
backup-db:
	@mkdir -p backups
	@echo "Backing up database..."
	pg_dump $$DATABASE_URL > backups/investing_db_$$(date +%Y%m%d_%H%M%S).sql
	@echo "✓ Database backed up to backups/"

# Show logs
logs:
	@echo "Recent logs:"
	@tail -n 50 logs/app_$$(date +%Y-%m-%d).log || echo "No logs found for today"

# Show agent decisions
agent-logs:
	@echo "Recent agent decisions:"
	@tail -n 30 logs/agent_decisions_$$(date +%Y-%m-%d).log || echo "No agent logs found"

# Quick data check
data-status:
	@echo "Checking data status..."
	@python -c "from database import get_db; print('Database connection: OK')" || echo "Database: ERROR"
	@echo ""
	@echo "Recent price data:"
	@psql $$DATABASE_URL -c "SELECT symbol, MAX(date) as last_update, COUNT(*) as rows FROM daily_prices GROUP BY symbol ORDER BY last_update DESC LIMIT 10;" || echo "Query failed"
