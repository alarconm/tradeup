# TradeUp - Claude Code Project Memory

## Overview
TradeUp is a Shopify app for trade-in programs and store credit management.

- **Production**: https://tradeup-production.up.railway.app
- **Hosting**: Railway (auto-deploys from main branch)
- **Repository**: https://github.com/alarconm/tradeup

## CRITICAL: Deployment Workflow

**Railway auto-deploys every push to main. Failed deploys = email spam.**

### Quick Commands

```bash
# Windows
scripts\validate.bat         # Validate locally
scripts\push.bat             # Validate + push
scripts\push.bat --verify    # Push + wait + verify deployment
scripts\status.bat           # Quick production health check

# Unix/Mac (or Git Bash)
make validate            # Validate locally
make push                # Validate + push
make push-verify         # Push + wait + verify deployment
make status              # Quick production health check
make verify              # Full deployment verification
```

### First-Time Setup

```bash
python scripts/setup.py
```

This installs git hooks and sets up local environment.

### The Golden Rule

**NEVER run `git push origin main` directly.**

Always use:
- `scripts\push.bat` (Windows)
- `make push` (Unix/Mac)

These validate first, blocking bad deploys.

## What Validation Checks

| Check | Catches |
|-------|---------|
| **Imports** | Missing modules, circular imports, typos |
| **App Creation** | Blueprint registration, config issues |
| **Migrations** | Syntax errors before they break DB |
| **Models** | Missing columns that cause 500 errors |

## Development Workflow

### For Small Changes
```bash
# Edit files...
scripts\validate.bat     # Check locally
scripts\push.bat         # Deploy if passes
```

### For Larger Features
```bash
# Create feature branch
git checkout -b feature/my-feature

# Iterate freely (no Railway deploys)
git add . && git commit -m "wip"
git push origin feature/my-feature

# When ready, validate and merge
scripts\validate.bat
git checkout main
git merge feature/my-feature
scripts\push.bat
```

## API Endpoints

### Core
- `GET /` - Health check, shows version
- `GET /api/promotions/health` - Promotions API health

### Promotions
- `GET /api/promotions/tiers` - Membership tiers
- `GET/POST /api/promotions/promotions` - CRUD promotions
- `GET /api/promotions/stats` - Dashboard stats

### Store Credit
- `POST /api/promotions/credit/add` - Issue credit
- `POST /api/promotions/credit/deduct` - Deduct credit
- `GET /api/promotions/credit/bulk` - Bulk operations

### Trade-ins
- `GET/POST /api/trade-ins` - Trade-in management

## Directory Structure

```
tradeup/
├── app/                    # Flask application
│   ├── api/               # REST API blueprints
│   ├── models/            # SQLAlchemy models
│   ├── services/          # Business logic
│   └── webhooks/          # Shopify webhooks
├── frontend/              # React SPA (Vite)
├── migrations/            # Alembic migrations
├── scripts/               # Dev tools
│   ├── validate.py        # Pre-deploy validation
│   ├── validate.bat       # Windows shortcut
│   ├── push.bat           # Windows validate+push
│   ├── pre-push           # Git hook
│   └── setup.py           # First-time setup
├── .github/workflows/     # CI/CD
│   └── validate.yml       # GitHub Actions validation
├── Makefile               # Unix dev commands
└── railway.json           # Railway config
```

## Environment Variables

### Production (Railway provides automatically)
- `DATABASE_URL` - PostgreSQL
- `PORT` - Server port

### Required Secrets
- `SECRET_KEY` - Flask sessions
- `SHOPIFY_*` - Shopify app credentials

### Local Development
Copy `.env.local.example` to `.env` for SQLite-based testing.

## Common Issues

### Import Error on Deploy
- Use relative imports: `from ..extensions` not `from app.extensions`
- Check circular imports

### Database 500 Errors
- Run `POST /api/promotions/init-db` to create tables
- Check migration has `IF NOT EXISTS`

### Railway Not Deploying
- Check Railway dashboard for build logs
- Try `make status` to verify current version
- Manual redeploy from Railway dashboard

## Coding Standards

- Relative imports within app package
- Max 1000 lines per file
- Error handling with try/except for DB operations
- Type hints for function signatures
