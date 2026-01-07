# Cardflow Labs - Session Handoff

*Updated: January 6, 2026 (afternoon)*

---

## CURRENT STATUS: DNS & SSL WORKING ✅ / DEBUGGING SHOPIFY API

### Custom Domain: LIVE ✅
- **app.cardflowlabs.com** - DNS configured and SSL working
- Direct embedded app URL: `https://app.cardflowlabs.com/app?shop=uy288y-nx.myshopify.com`

### Railway Deployment: WORKING
- Health endpoint: `https://web-production-41bb1.up.railway.app/health`
- Custom domain: `https://app.cardflowlabs.com`

### Access in Shopify Admin
- Navigate to: Apps → TradeUp
- Direct URL: `https://admin.shopify.com/store/uy288y-nx/apps/tradeup-2`

### Known Issues Being Fixed
1. **Customer Search 500 Error** - Added debug logging to identify root cause
2. **Membership Tiers** - Added auto-seeding of default tiers (Silver, Gold, Platinum)

---

## COMPLETED THIS SESSION (Jan 6, 2026 PM)

### 1. DNS & SSL Configuration
- Configured CNAME record in Namecheap: `app` → `web-production-41bb1.up.railway.app`
- Railway SSL provisioned automatically
- **app.cardflowlabs.com** now working with HTTPS

### 2. Auto-Seed Membership Tiers
- Added automatic tier seeding when `/api/members/tiers` returns empty
- Default tiers: Silver (5%), Gold (10%), Platinum (15%)

### 3. Debug Logging for 500 Error
- Added detailed error response to `/api/members/search-shopify`
- Shows environment variable status and error details
- Helps identify if it's credential vs API issue

### 4. User Story Testing & Bug Fixes (Earlier)
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

### 1. Fix Customer Search 500 Error
- Test the search after Railway deployment completes (~1 min)
- Error response now includes debug info to identify cause
- Likely issues: wrong SHOPIFY_DOMAIN format or SHOPIFY_ACCESS_TOKEN permissions

### 2. Build Out Remaining Features
- Non-member trade-ins (requires DB migration)
- Settings page improvements
- Bonuses feature
- Cashback management

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
