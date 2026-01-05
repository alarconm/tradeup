# TradeUp Development Makefile
# Usage: make <command>

.PHONY: help validate test dev install-hooks push deploy logs

# Default target
help:
	@echo "TradeUp Development Commands"
	@echo "============================"
	@echo ""
	@echo "  make validate     - Run pre-deployment validation"
	@echo "  make test         - Run tests"
	@echo "  make dev          - Start local development server"
	@echo "  make install-hooks - Install git pre-push hook"
	@echo "  make push         - Validate and push to main"
	@echo "  make deploy       - Full validation + push (same as push)"
	@echo "  make logs         - View Railway logs"
	@echo "  make status       - Check production health"
	@echo ""

# Run validation before deploy
validate:
	@echo "Running pre-deployment validation..."
	@python scripts/validate.py

# Run tests
test:
	@pytest -v

# Start local dev server
dev:
	@cp -n .env.local.example .env 2>/dev/null || true
	@echo "Starting local server on http://localhost:5000"
	@flask run --port 5000 --reload

# Install git hooks
install-hooks:
	@echo "Installing git hooks..."
	@cp scripts/pre-push .git/hooks/pre-push
	@chmod +x .git/hooks/pre-push
	@echo "Pre-push hook installed!"

# Validate and push to main
push: validate
	@echo ""
	@echo "Validation passed! Pushing to main..."
	@git push origin main
	@echo ""
	@echo "Pushed! Railway will auto-deploy."
	@echo "Monitor at: https://railway.app"

# Alias for push
deploy: push

# View Railway logs (requires railway CLI login)
logs:
	@railway logs

# Check production health
status:
	@echo "Checking production status..."
	@curl -s https://quick-flip-production.up.railway.app/ | python -m json.tool
	@echo ""
	@echo "Checking promotions API..."
	@curl -s https://quick-flip-production.up.railway.app/api/promotions/health | python -m json.tool
