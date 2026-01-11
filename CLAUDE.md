# TradeUp - Claude Code Project Memory

## Overview

TradeUp is a **Shopify embedded app** for loyalty programs, trade-in management, and store credit. Built for collectibles stores (sports cards, Pokemon, MTG).

- **Production**: https://app.cardflowlabs.com
- **Railway Backend**: https://tradeup-production.up.railway.app
- **Test Store**: uy288y-nx.myshopify.com (ORB Sports Cards)
- **Repository**: https://github.com/alarconm/tradeup

## Current Status (January 2026)

**PRODUCTION-READY** - See `SHOPIFY_APP_STORE_READINESS.md` for full audit.

### What's Complete

| Component | Status | LOC |
|-----------|--------|-----|
| Backend API (16 endpoints) | Complete | 6,749 |
| Frontend (49 components) | Complete | 2,433 |
| Services (10 services) | Complete | 7,300 |
| Customer Account Extension | Complete | - |
| Theme Blocks (4 blocks) | Complete | - |
| Shopify Billing (4 plans) | Complete | - |
| Webhooks (6 handlers) | Complete | - |
| Landing Pages (13 variants) | Complete | - |
| Documentation (11 docs) | Complete | - |
| App Store Assets | Complete | - |

### Remaining Items

1. **Fix admin auth** - Commented out in `frontend/src/App.tsx`
2. **End-to-end testing** - Customer flows need verification
3. **Set SHOPIFY_BILLING_TEST=false** - For production charges

## Quick Commands

```bash
# Windows
scripts\validate.bat         # Validate locally
scripts\push.bat             # Validate + push
scripts\status.bat           # Production health check

# Unix/Mac
make validate                # Validate locally
make push                    # Validate + push
make dev                     # Local development
```

## Directory Structure

```
tradeup/
├── app/                    # Flask backend
│   ├── api/               # 17 REST API blueprints (incl. proxy)
│   ├── models/            # 7 SQLAlchemy models
│   ├── services/          # 10 business logic services
│   ├── webhooks/          # 6 Shopify webhook handlers
│   └── utils/             # Helpers (sentry.py)
├── frontend/              # React SPA (Vite + TypeScript)
│   ├── src/admin/         # Merchant admin pages
│   ├── src/embedded/      # Shopify embedded pages
│   └── src/pages/         # Public pages
├── extensions/            # Shopify extensions
│   ├── customer-account-ui/  # Customer rewards display
│   └── theme-blocks/         # 4 storefront blocks
├── landing-pages/         # 13 A/B test variants
├── migrations/            # 9 Alembic migrations
├── scripts/               # Dev tools
└── docs/                  # 11 documentation files
```

## API Endpoints

### Core
- `GET /health` - Health check
- `GET /api/dashboard/stats` - Dashboard metrics

### Members & Tiers
- `GET/POST /api/members` - Member CRUD
- `GET/POST /api/tiers` - Tier configuration
- `POST /api/membership/assign-tier` - Assign tier to member

### Trade-Ins
- `GET/POST /api/trade-ins` - Batch management
- `POST /api/trade-ins/{id}/items` - Add items

### Store Credit
- `POST /api/store-credit/add` - Issue credit
- `POST /api/store-credit/deduct` - Deduct credit
- `GET /api/store-credit-events` - Bulk campaigns

### Billing
- `GET /api/billing/plans` - Available plans
- `POST /api/billing/subscribe` - Start subscription
- `POST /api/billing/cancel` - Cancel subscription

### Onboarding
- `GET /api/onboarding/status` - Setup progress
- `GET /api/onboarding/store-credit-check` - Verify store credit enabled
- `POST /api/onboarding/templates/{key}/apply` - Apply tier template

### App Proxy (Customer-Facing)
- `GET /proxy/` - Rewards landing page (HTML)
- `GET /proxy/balance` - Customer points balance (JSON)
- `GET /proxy/rewards` - Available rewards catalog (JSON)
- `GET /proxy/tiers` - Tier benefits comparison (JSON)

Accessible at: `store.myshopify.com/apps/rewards`

## Shopify Extensions

### Customer Account UI
- **File**: `extensions/customer-account-ui/src/TradeUpRewards.jsx`
- Shows rewards balance and trade-in history in customer account

### Theme Blocks
- `membership-signup.liquid` - Join membership CTA
- `credit-badge.liquid` - Store credit balance display
- `trade-in-cta.liquid` - Start trade-in button
- `refer-friend.liquid` - Referral program block

## Billing Plans

| Plan | Price | Members | Tiers |
|------|-------|---------|-------|
| Free | $0 | 50 | 2 |
| Starter | $19/mo | 200 | 3 |
| Growth | $49/mo | 1,000 | 5 |
| Pro | $99/mo | Unlimited | Unlimited |

## Environment Variables

### Required
```env
SECRET_KEY=<secure-random>
DATABASE_URL=postgresql://...
SHOPIFY_API_KEY=<from-partner-dashboard>
SHOPIFY_API_SECRET=<from-partner-dashboard>
APP_URL=https://app.cardflowlabs.com
```

### Optional
```env
SHOPIFY_BILLING_TEST=true    # Set false for production
SENTRY_DSN=<sentry-dsn>      # Error tracking
```

## Key Files

| File | Purpose |
|------|---------|
| `app/__init__.py` | Flask app factory, blueprint registration |
| `app/config.py` | Environment configuration |
| `frontend/src/App.tsx` | React router (AdminRoute auth here) |
| `frontend/src/admin/api.ts` | API client with shop domain interceptor |
| `shopify.app.toml` | Shopify app configuration |

## Development Notes

### Shop Domain Header
API requires `X-Shopify-Shop-Domain` header. In development, the axios interceptor in `frontend/src/admin/api.ts` adds this automatically.

### Local Testing
```bash
# Backend (Flask)
cd tradeup && python run.py

# Frontend (Vite)
cd frontend && npm run dev

# Test API
curl -H "X-Shopify-Shop-Domain: uy288y-nx.myshopify.com" http://localhost:5000/api/onboarding/status
```

### Database
- PostgreSQL in production (Railway)
- SQLite locally (auto-created)
- Migrations: `flask db upgrade`

## Railway Deployment Best Practices

### Quick Deploy Commands
```bash
# Check deployment status FIRST
railway deployment list

# Deploy (pick ONE method, not both)
railway up                    # Direct upload
git push origin main          # GitHub trigger

# Check logs if deployment fails
railway logs --deployment <id>
```

### Critical Rules
1. **Keep startCommand simple** - Just `gunicorn -c gunicorn.conf.py run:app`
2. **Never add migrations to startCommand** - They can timeout and fail health checks
3. **Use fix-schema endpoint for quick schema fixes** - `POST /api/admin/fix-schema?key=tradeup-schema-fix-2026`
4. **Check `railway deployment list` immediately** - Don't wait blindly for deploys
5. **The `nul` file is in .gitignore** - Windows reserved name that breaks Railway indexer

### If Deployment Fails
1. Run `railway deployment list` to confirm failure
2. Check logs: `railway logs --deployment <deployment-id>`
3. Common issues:
   - `nul` file in repo → delete it, it's in .gitignore
   - Health check timeout → simplify startCommand
   - Migration errors → use fix-schema endpoint instead

### Fix-Schema Endpoint
For adding missing columns without migrations:
```bash
curl -X POST "https://app.cardflowlabs.com/api/admin/fix-schema?key=tradeup-schema-fix-2026"
```
Add new columns to `app/api/admin.py` in the `columns_to_add` list.

## Recent Changes (January 6, 2026)

1. Added onboarding flow with store credit check
2. Added Sentry error tracking (frontend + backend)
3. Fixed BrowserRouter missing in main.tsx
4. Added Vite proxy for local API calls
5. Added CSS variables for onboarding styling
6. Comprehensive audit confirmed all features complete

## Contact

- **App**: TradeUp by Cardflow Labs
- **Support**: support@cardflowlabs.com
- **Privacy**: privacy@cardflowlabs.com
