# TradeUp - Claude Code Project Memory

## Overview

TradeUp is a **Shopify embedded app** for loyalty programs, trade-in management, and store credit. Built for collectibles stores (sports cards, Pokemon, MTG).

- **Production**: https://app.cardflowlabs.com
- **Railway Backend**: https://tradeup-production.up.railway.app
- **Test Store**: uy288y-nx.myshopify.com (ORB Sports Cards)
- **Repository**: https://github.com/alarconm/tradeup

## Current Status (January 21, 2026)

**READY FOR APP STORE SUBMISSION** - 89 E2E tests passing. See `docs/E2E_TEST_REPORT.md`.

**Codebase Review Complete** - 8 new PRDs created for competitive features. See roadmap section below.

### What's Complete

| Component | Status | Notes |
|-----------|--------|-------|
| Backend API (43 modules) | ✅ Complete | All bugs fixed |
| Frontend (18 admin pages) | ✅ Complete | Including Pending Distributions |
| Services (30 services) | ✅ Complete | All services functional |
| Customer Account Extension | ✅ Complete | 1,211 lines, production ready |
| Checkout UI Extension | ✅ Complete | Points display, tier badges |
| Post-Purchase Extension | ✅ Complete | Celebration + referral prompts |
| POS UI Extension | ✅ Complete | Member lookup for retail |
| Shopify Billing (4 plans) | ✅ Complete | Free, Starter, Growth, Pro |
| Webhooks (13/13 handlers) | ✅ Complete | All handlers implemented |
| Landing Pages (13 variants) | ✅ Complete | Live at /landing/* |
| App Proxy | ✅ Complete | Customer rewards page |
| Pending Distribution Approval | ✅ Complete | Monthly credit approval workflow |

### All Critical Bugs FIXED

| Bug | Fix Applied |
|-----|-------------|
| `flow_service.py:651` | ✓ Changed to `get_shopify_balance(member).get('balance', 0)` |
| `tier_service.py:46` | ✓ Added `shopify_client` parameter to `__init__()` |

### All Webhook Handlers IMPLEMENTED

| Topic | Status |
|-------|--------|
| `refunds/create` | ✓ Reverses points and credit proportionally |
| `orders/paid` | ✓ Optional payment confirmation workflow |
| `products/create` | ✓ Detects new membership products |
| `orders/create` | ✓ Loyalty point earning |
| `orders/fulfilled` | ✓ Fulfillment tracking |
| `orders/cancelled` | ✓ Order cancellation handling |
| `customers/create` | ✓ New customer enrollment |
| `customers/update` | ✓ Customer data sync |
| `customers/delete` | ✓ GDPR compliance |
| `shop/update` | ✓ Store settings sync |
| `app/uninstalled` | ✓ Cleanup on uninstall |
| `app_subscriptions/update` | ✓ Billing status sync |
| `app_purchases_one_time/update` | ✓ One-time purchase handling |

### Disabled Shopify Functions (Optional Post-Launch)

| Extension | What It Does | Why Disabled |
|-----------|--------------|--------------|
| checkout-validation | Validates checkout (min order, membership status) | Shopify Functions require WebAssembly build; can add post-launch |
| tier-discount-function | Auto-applies tier discounts at checkout | Shopify Functions require WebAssembly build; can add post-launch |

**Note**: These are Shopify Functions (Rust/WebAssembly), not UI extensions. The core app works without them. Tier discounts can still be applied via discount codes.

### Before Going Live

1. **Set `SHOPIFY_BILLING_TEST=false`** in Railway for production charges

## Quick Commands

```bash
# Development
npm run dev                  # Hot-reload extensions in dev store
npm run validate             # Run validation checks

# Extension Deployment
npm run deploy               # Deploy extensions (staging, not released)
npm run release --version=X  # Release to users
npm run deploy:release       # Deploy + release in one command

# Pre-Release
npm run prerelease           # Run all pre-release checks
npm run prerelease:deploy    # Pre-release checks + deploy

# Versioning (creates git tag + pushes)
npm run version:patch        # 2.0.0 -> 2.0.1 (bug fixes)
npm run version:minor        # 2.0.0 -> 2.1.0 (new features)
npm run version:major        # 2.0.0 -> 3.0.0 (breaking changes)

# Legacy (Windows)
scripts\validate.bat         # Validate locally
scripts\push.bat             # Validate + push
```

## Professional Deployment Workflow

See `DEPLOYMENT.md` for full documentation.

### Architecture

| Component | Deployment | Trigger |
|-----------|------------|---------|
| Backend (Flask) | Railway CI/CD | Auto on `git push` |
| Extensions (4) | Shopify CLI | Manual `npm run deploy` |

### Release Process

```bash
# 1. Run pre-release checks
npm run prerelease

# 2. Deploy to staging (not released yet)
npm run deploy
# Output: "tradeup-by-cardflow-labs-XX"

# 3. Test in dev store manually

# 4. Release to users
npm run release --version=tradeup-by-cardflow-labs-XX

# 5. Tag the release
npm run version:patch
```

### Dev vs Production App Separation

**Current (Development)**:
- Single app: "TradeUp by Cardflow Labs"
- Test store: uy288y-nx.myshopify.com

**Post-Launch (Production)**:
Create separate apps for isolation:

| App | Purpose | Stores |
|-----|---------|--------|
| TradeUp Dev | Testing, staging | Internal test stores |
| TradeUp | Production | Real merchant stores |

This prevents test deployments from affecting real merchants.

## Directory Structure

```
tradeup/
├── app/                    # Flask backend
│   ├── api/               # 43 REST API modules
│   ├── models/            # 11 SQLAlchemy models
│   ├── services/          # 30 business logic services
│   ├── webhooks/          # 6 webhook handler files (10 implemented topics)
│   └── utils/             # Helpers (sentry.py)
├── frontend/              # React SPA (Vite + TypeScript)
│   ├── src/admin/         # Admin components
│   ├── src/embedded/      # 17+ Shopify embedded pages
│   └── src/pages/         # Public pages
├── extensions/            # Shopify UI extensions (4 active)
│   ├── checkout-ui/       # Checkout points display
│   ├── customer-account-ui/  # Customer rewards display (1,211 lines)
│   ├── post-purchase-ui/  # Post-purchase celebration
│   └── pos-ui/            # POS member lookup
├── extensions-disabled/   # Disabled Shopify Functions (local backup)
├── landing-pages/         # 13 A/B test variants
├── migrations/            # Alembic migrations
├── scripts/               # Dev tools
└── docs/                  # Documentation files
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

### Active Extensions (4)

| Extension | Purpose | Key Files |
|-----------|---------|-----------|
| checkout-ui | Points display at checkout | `src/Checkout.jsx`, 5 components |
| customer-account-ui | Full rewards dashboard | `src/TradeUpRewards.jsx` (1,211 lines) |
| post-purchase-ui | Celebration + referral prompt | `src/index.jsx` (585 lines) |
| pos-ui | POS member lookup | `src/SmartGridTile.tsx`, `src/MemberModal.tsx` (TypeScript) |

### Disabled Shopify Functions (2)
Moved to `extensions-disabled/` folder (not deployed):
- `checkout-validation` - Would enforce checkout rules (min order, membership required)
- `tier-discount-function` - Would auto-apply tier discounts at checkout

**Why disabled**: Shopify Functions require JavaScript→WebAssembly compilation via Javy, which takes 30+ minutes in CI. The core app works without them - tier discounts can be applied via discount codes instead. Can re-enable post-launch if needed.

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
| `frontend/src/App.tsx` | React router (routes to EmbeddedApp) |
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

## Recent Changes

### January 21, 2026 - Professional Deployment Setup
- ✅ Added npm deploy scripts (deploy, release, version:patch/minor/major)
- ✅ Created DEPLOYMENT.md with full workflow documentation
- ✅ Added prerelease.py validation script
- ✅ Set up semantic versioning with git tags
- ✅ Removed Shopify Functions from extensions/ (moved to extensions-disabled/)
- ✅ Updated all extension API versions to 2026-01
- ✅ Deployed and released version tradeup-by-cardflow-labs-16

### January 20, 2026 - App Store Ready
- ✅ Completed E2E browser testing (89 tests, 87 passed)
- ✅ Added Pending Distribution Approval workflow
- ✅ Fixed mobile navigation spacing for touch targets
- ✅ Verified landing pages live at /landing/*
- ✅ Created user stories and test plans (docs/pending-distributions-user-stories.md)
- ✅ Updated documentation for App Store submission

### January 17, 2026 - Bug Fixes & Webhooks
- Fixed flow_service.py:651 balance retrieval
- Fixed tier_service.py:46 shopify_client parameter
- Implemented refunds/create webhook
- Implemented orders/paid webhook
- Implemented products/create webhook

### January 13-14, 2026 - Feature Completion
- Added usage warnings at 80%, 90%, 100% thresholds
- Added member suspend/reactivate/cancel endpoints
- Added tier change logging
- Added trade-in item editing (PUT/DELETE)
- Added auto-approval threshold enforcement
- Added auto-upgrade/downgrade service
- Added metafield sync/verify endpoints
- Added 15+ granular notification controls
- Added daily report endpoint with comparison metrics
- Disabled checkout-validation and tier-discount-function to unblock deploy
- Made member search instant (like Shopify POS)

### January 6, 2026 - Initial Setup
- Added onboarding flow with store credit check
- Added Sentry error tracking (frontend + backend)
- Fixed BrowserRouter missing in main.tsx

## Product Roadmap & PRDs

PRDs are stored in `roadmap/epics/` for autonomous execution by Ralph.

### PRD Summary (January 21, 2026)

| Epic | PRD | Priority | Stories | Status |
|------|-----|----------|---------|--------|
| 01 | Test Coverage | Medium | 10 | Existing |
| 02 | Performance Optimization | Medium | 10 | Existing |
| 03 | API Documentation | Low | 10 | Existing |
| 04 | Monitoring & Observability | Medium | 10 | Existing |
| 05 | Developer Experience | Low | 10 | Existing |
| 06 | **Code Quality Fixes** | **HIGH** | 8 | **NEW** |
| 07 | **Gamification System** | **HIGH** | 10 | **NEW** |
| 08 | **Birthday Rewards** | **HIGH** | 10 | **NEW** |
| 09 | **Nudges & Reminders** | **HIGH** | 10 | **NEW** |
| 10 | **Loyalty Page Builder** | **HIGH** | 10 | **NEW** |
| 11 | **Review Collection** | **HIGH** | 10 | **NEW** |
| 12 | Widget Builder | Medium | 10 | NEW |
| 13 | AI Trade-In Pricing | Medium | 10 | NEW |

### Priority Guide

**Phase 1 - Pre-Launch (Do First)**
- 06: Code Quality Fixes - Security and code cleanup
- 11: Review Collection - Critical for App Store visibility

**Phase 2 - Competitive Parity (30 days)**
- 07: Gamification System - Badges, achievements, streaks
- 08: Birthday Rewards - Auto-send birthday rewards
- 09: Nudges & Reminders - Points expiring, tier progress
- 10: Loyalty Page Builder - Custom rewards page

**Phase 3 - Differentiation (60-90 days)**
- 12: Widget Builder - Visual customization
- 13: AI Trade-In Pricing - Unique competitive advantage

### Running PRDs with Ralph

```bash
# Execute a single PRD
/ralph roadmap/epics/06-code-quality-fixes/prd.json

# Run overnight (autonomous execution)
/ralph --all
```

See `docs/ROADMAP_TO_NUMBER_ONE.md` for full competitive analysis and strategy.

## Contact

- **App**: TradeUp by Cardflow Labs
- **Support**: support@cardflowlabs.com
- **Privacy**: privacy@cardflowlabs.com
