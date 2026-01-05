# TradeUp - Claude Code Project Memory

## Overview
TradeUp is a Shopify app for trade-in programs and store credit management.

- **Production**: https://quick-flip-production.up.railway.app
- **Hosting**: Railway (auto-deploys from main branch)
- **Repository**: https://github.com/alarconm/quick-flip

## Critical Deployment Workflow

**NEVER push directly to main without validation!** Railway auto-deploys on every push to main, and failed deploys generate email spam.

### Before ANY Push to Main

1. **Run validation locally:**
   ```bash
   python scripts/validate.py
   ```

2. **Or use the pre-push hook (recommended):**
   ```bash
   # One-time setup
   cp scripts/pre-push .git/hooks/pre-push
   chmod +x .git/hooks/pre-push
   ```

3. **For iterative development, use a feature branch:**
   ```bash
   git checkout -b feature/my-feature
   # ... make changes ...
   git push origin feature/my-feature
   # Only merge to main after validation passes
   ```

### Local Testing Environment

```bash
# Copy local env file
cp .env.local .env

# Run validation
python scripts/validate.py

# Start local server (optional)
flask run --port 5000
```

### What the Validation Checks

1. **Imports** - All modules can be imported without errors
2. **App Creation** - Flask app starts successfully
3. **Migrations** - No syntax errors in migration files
4. **Models** - All expected columns exist

## Common Issues & Fixes

### Import Errors
- Check relative imports (`from ..extensions` not `from app.extensions`)
- Verify service classes are imported correctly (class vs instance)

### Database/Migration Errors
- Use idempotent migrations with `IF NOT EXISTS` checks
- Test migrations locally with SQLite before pushing

### Railway Not Deploying
- Check Railway dashboard for build logs
- Verify GitHub webhook is connected
- Manual redeploy from Railway dashboard if needed

## Technology Stack

| Layer | Technology |
|-------|------------|
| Backend | Flask 3.x, SQLAlchemy 2.x |
| Database | PostgreSQL (Railway) / SQLite (local) |
| Frontend | React, TypeScript, Vite |
| Hosting | Railway |

## Directory Structure

```
quick-flip-standalone/
├── app/                    # Flask application
│   ├── api/               # REST API endpoints
│   ├── models/            # SQLAlchemy models
│   ├── services/          # Business logic
│   ├── webhooks/          # Shopify webhooks
│   └── __init__.py        # App factory
├── frontend/              # React SPA
├── migrations/            # Alembic migrations
├── scripts/               # Utility scripts
│   ├── validate.py        # Pre-deploy validation
│   └── pre-push           # Git hook
└── railway.json           # Railway config
```

## Key API Endpoints

### Promotions & Store Credit
- `GET /api/promotions/health` - Health check
- `GET /api/promotions/tiers` - List membership tiers
- `GET/POST /api/promotions/promotions` - CRUD promotions
- `POST /api/promotions/credit/add` - Issue store credit
- `GET /api/promotions/stats` - Dashboard statistics

### Trade-ins
- `GET/POST /api/trade-ins` - Trade-in management
- `GET /api/dashboard` - Dashboard data

## Environment Variables

### Required for Production (Railway provides DATABASE_URL automatically)
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - Flask session secret
- `SHOPIFY_*` - Shopify app credentials

### Local Development
Copy `.env.local` to `.env` for SQLite-based local testing.

## Git Workflow

```
main (production) ← Only merge validated code here
  └── feature/* branches (iterate here)
```

1. Create feature branch: `git checkout -b feature/xyz`
2. Make changes and test locally
3. Run `python scripts/validate.py`
4. If passes, merge to main
5. Railway auto-deploys

## Coding Standards

- Use relative imports within the app package
- Maximum 1000 lines per file
- Add error handling with try/except for database operations
- Use type hints for function signatures
