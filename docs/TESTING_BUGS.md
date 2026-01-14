# Testing Bugs Found - January 13, 2026

## Critical Bugs

None found so far.

## Medium Priority Bugs

### 1. ~~Missing Suspend/Reactivate Buttons in Member Detail Modal~~ ✅ FIXED
**Location**: Members page -> Click on member -> Member detail modal
**Expected**: Buttons for Suspend and Reactivate membership (backend supports these operations)
**Actual**: Only shows: Change Tier, Cancel Membership, Delete Member, Issue Credit
**Backend Support**: Endpoints exist at:
- `POST /api/members/{id}/suspend`
- `POST /api/members/{id}/reactivate`
**Fix Applied**: Added Suspend/Reactivate buttons with confirmation modals to `EmbeddedMembers.tsx`
- Suspend button shows for active members
- Reactivate button shows for suspended or cancelled members

### 2. Change Tier Dropdown Not Opening
**Location**: Members page -> Click member -> Change Tier button -> New Tier dropdown
**Expected**: Dropdown should show available tiers
**Actual**: Dropdown doesn't open on click
**Note**: May be an iframe/Polaris interaction issue. Needs investigation.

## Low Priority Bugs (UX)

### 3. ~~Member Modal Doesn't Refresh After Issuing Credit~~ ✅ FIXED
**Location**: Member detail modal -> Issue Credit -> Success -> Modal still shows old credit value
**Expected**: Modal should refresh to show new credit balance
**Actual**: Credit balance only updates after closing and reopening modal
**Fix Applied**: Modified `closeIssueCreditModal` to close parent modal after successful credit issuance, triggering data refresh when modal is reopened

## Testing Completed

| Feature | Status | Notes |
|---------|--------|-------|
| Dashboard | ✅ Working | Stats load correctly |
| Members List | ✅ Working | All members displayed |
| Member Detail | ✅ Working | Info displayed (missing suspend buttons) |
| Issue Credit | ✅ Working | Syncs to Shopify |
| Trade-In Ledger | ✅ Working | List and summary stats |
| New Trade-In | ✅ Working | Full form with all fields |
| Settings - Branding | ✅ Working | Name, tagline, style |
| Settings - General | ✅ Working | Currency, timezone |
| Settings - Features | ✅ Working | All toggles functional |
| Settings - Auto-Enrollment | ✅ Working | Enable + min order |
| Settings - Cashback | ✅ Working | Delivery method + options |
| Settings - Trade-In Rules | ✅ Working | Thresholds configured |
| Settings - Subscriptions | ✅ Working | Monthly/yearly + trial |
| Settings - Tiers | ✅ Working | 5 tiers configured |
| Settings - Notifications | ✅ Working | Granular email controls |

## Testing Remaining

- [x] Billing/subscription flows - Working, all 4 plans displayed
- [x] Customer-facing theme blocks - **All 4 blocks available** (Credit Badge, Refer a Friend, Signup, Trade-In CTA)
- [ ] App proxy endpoints (storefront) - **404 error** - needs app reinstall to activate proxy
- [ ] Customer account extension - Needs verification (requires Shopify checkout extension deployment)
- [ ] Webhook handling - Needs live order/customer update
- [x] Metafield sync - Endpoints exist, require authentication
- [x] Daily report - Endpoint exists, requires authentication

## Notes

### App Proxy 404 Issue
The app proxy at `/apps/rewards` returns 404 from Shopify. The backend proxy endpoint at `https://app.cardflowlabs.com/proxy/` is working correctly (returns "Invalid signature" for unsigned requests).

**Solution**: May need to redeploy the app or run `shopify app deploy` to activate the app proxy configuration.
