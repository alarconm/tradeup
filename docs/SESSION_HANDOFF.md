# Cardflow Labs - Session Handoff

*Updated: January 6, 2026*

---

## CURRENT STATUS: FULLY WORKING ✅

### User Story Testing: 37/37 PASSING
- Created comprehensive API test script: `scripts/test_user_stories.py`
- All user stories from `docs/USER_STORIES_TESTING.md` verified and working
- Run tests: `python scripts/test_user_stories.py`

### TradeUp Embedded App: v1.7 WORKING
- App loads and displays correctly inside Shopify Admin iframe
- All API calls working (uses XMLHttpRequest, not fetch)
- Dashboard shows real data from Shopify
- Test member: Michael Alarcon (michael.alarconii@gmail.com)

### Railway Deployment: WORKING
- Health endpoint: `https://web-production-41bb1.up.railway.app/health`
- App URL: `https://web-production-41bb1.up.railway.app/app?shop=uy288y-nx.myshopify.com`

### Access in Shopify Admin
- Navigate to: Apps → TradeUp
- Direct URL: `https://admin.shopify.com/store/uy288y-nx/apps/tradeup-2`

---

## COMPLETED THIS SESSION

### 1. User Story Testing & Bug Fixes (Latest)
Fixed 7 bugs discovered during comprehensive user story testing:

| Bug | Fix |
|-----|-----|
| `StoreCreditLedger.tenant_id` doesn't exist | Join through Member table in dashboard.py |
| `total_value` field not found | Changed to `total_trade_value` |
| `len(b.items)` on AppenderQuery fails | Use stored `b.total_items` count |
| Missing validation returns 500 | Added proper 400 response in members.py |
| Legacy QF prefix only | Updated to support both TU and QF |
| Missing `/settings/auto-enrollment` endpoint | Added GET/PATCH endpoints |
| Missing `/settings/notifications` endpoint | Added GET/PATCH endpoints |

### 2. Fixed Shopify Iframe API Issue (Previous Session)
- **Problem**: `fetch()` calls hang inside Shopify embedded iframes (never resolve)
- **Solution**: Converted all API calls to use `XMLHttpRequest` instead
- **Result**: All API calls now complete successfully

### 3. TradeUp Dashboard Features Working
- Dashboard stats (members, credit, trade-ins, cashback)
- Recent members list with real Shopify customer data
- Quick action buttons (Add Member, New Trade-In, Cashback, Settings)
- Bottom navigation (Home, Members, Trade-Ins, Cashback, Settings)
- Light/dark mode toggle
- Mobile-optimized responsive design

### 4. Test Data
- Member: Michael Alarcon (michael.alarconii@gmail.com)
- Member ID: TU1001
- Tier: Silver
- Store Credit: $0

---

## KEY TECHNICAL FIX

**fetch() vs XMLHttpRequest in Shopify iframes:**

```javascript
// DON'T USE fetch() - it hangs in Shopify iframes:
fetch(url, { headers: {...} })  // ❌ Never resolves

// USE XMLHttpRequest instead:
const xhr = new XMLHttpRequest();  // ✅ Works
xhr.open('GET', url, true);
xhr.setRequestHeader('X-Tenant-ID', '1');
xhr.onreadystatechange = function() {...};
xhr.send();
```

This is documented in `app/__init__.py` around line 921.

---

## NEXT STEPS

### 1. Configure DNS in Namecheap (Manual)
```
Type: CNAME
Name: app
Value: 20du0xvq.up.railway.app
TTL: Automatic
```

### 2. Build Out Remaining Features
- Add Member form functionality
- New Trade-In workflow
- Cashback management
- Settings page with tier configuration

### 3. Shopify Billing Integration
- Already have billing columns in database
- Need to implement App Bridge billing flow

---

## KEY CREDENTIALS

| Service | Value |
|---------|-------|
| Shopify Client ID | f27841c5cf965100dfa81a212d7d9c10 |
| Shopify Client Secret | (in .env file) |
| ORB Shopify Domain | uy288y-nx.myshopify.com |
| Railway Live URL | https://web-production-41bb1.up.railway.app |
| Custom Domain | app.cardflowlabs.com (pending DNS) |
| Railway CNAME | 20du0xvq.up.railway.app |

---

## PRICING (Already in Code)

| Tier | Price | Members |
|------|-------|---------|
| Free | $0 | 50 |
| Starter | $19/mo | 200 |
| Growth | $49/mo | 1,000 |
| Pro | $99/mo | Unlimited |

---

## REPO LOCATION
```
C:\Users\malar\OneDrive\Documents\Coding Projects\tradeup
```

---

*App is now functional! Next: Add form functionality and billing integration.*
