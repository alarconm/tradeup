# Testing Bugs Found - January 13, 2026

## Critical Bugs

None found so far.

## Medium Priority Bugs

### 1. ~~Missing Suspend/Reactivate Buttons in Member Detail Modal~~ FIXED
**Location**: Members page -> Click on member -> Member detail modal
**Expected**: Buttons for Suspend and Reactivate membership (backend supports these operations)
**Actual**: Only shows: Change Tier, Cancel Membership, Delete Member, Issue Credit
**Backend Support**: Endpoints exist at:
- `POST /api/members/{id}/suspend`
- `POST /api/members/{id}/reactivate`
**Fix Applied**: Added Suspend/Reactivate buttons with confirmation modals to `EmbeddedMembers.tsx`
- Suspend button shows for active members
- Reactivate button shows for suspended or cancelled members

### 2. ~~Change Tier Dropdown Not Opening~~ VERIFIED WORKING
**Location**: Members page -> Click member -> Change Tier button -> New Tier dropdown
**Expected**: Dropdown should show available tiers
**Actual**: Dropdown opens correctly showing all tiers (No Tier, GOLDENGOOSE, Test Bronze, Silver, Gold, Platinum)
**Status**: Working as expected during E2E testing on Jan 13, 2026

### 3. ~~Suspend/Reactivate/Cancel API "Bad request" Error~~ FIXED
**Location**: Member detail modal -> Suspend/Reactivate/Cancel buttons
**Expected**: Should suspend/reactivate/cancel member successfully
**Actual**: Returns "Bad request" error
**Root Cause**: `request.get_json()` throws 400 when Content-Type is application/json but body is empty
**Fix Applied**: Changed to `request.get_json(silent=True)` in:
- `app/api/members.py` - suspend_member()
- `app/api/members.py` - reactivate_member()
- `app/api/members.py` - cancel_member()

## Low Priority Bugs (UX)

### 4. ~~Member Modal Doesn't Refresh After Issuing Credit~~ FIXED
**Location**: Member detail modal -> Issue Credit -> Success -> Modal still shows old credit value
**Expected**: Modal should refresh to show new credit balance
**Actual**: Credit balance only updates after closing and reopening modal
**Fix Applied**: Modified `closeIssueCreditModal` to close parent modal after successful credit issuance, triggering data refresh when modal is reopened

### 5. Member Search Shows Error (Intermittent)
**Location**: Members page -> Search box -> Type query
**Expected**: Should filter members by name/email
**Actual**: Sometimes shows "Failed to load members" error
**Status**: Needs investigation - may be related to API throttling or session timeout

## E2E Testing Completed - January 13, 2026

| Feature | Status | Notes |
|---------|--------|-------|
| Dashboard | PASS | Stats load correctly, recent activity shows |
| Members List | PASS | All 3 members displayed with correct data |
| Member Search | PARTIAL | Works but occasionally shows error |
| Member Detail Modal | PASS | All info displayed correctly |
| Issue Credit | PASS | $5.00 test credit issued, synced to Shopify, balance updated |
| Change Tier | PASS | Dropdown opens, shows all 6 tiers |
| Suspend/Reactivate | PENDING FIX | Backend fix applied, needs deployment to verify |
| Trade-In Ledger | PASS | 1 trade-in shown with $100 total, $50 cash/$50 credit |
| New Trade-In Form | PASS | Full form with customer type, amounts, category, notes |
| Settings - Branding | PASS | Name, tagline, style dropdown |
| Settings - General | PASS | Currency (USD), timezone (Pacific) |
| Settings - Features | PASS | Self-signup ON, Points OFF, Referral ON |

## Testing Completed Previously

| Feature | Status | Notes |
|---------|--------|-------|
| Settings - Auto-Enrollment | Working | Enable + min order |
| Settings - Cashback | Working | Delivery method + options |
| Settings - Trade-In Rules | Working | Thresholds configured |
| Settings - Subscriptions | Working | Monthly/yearly + trial |
| Settings - Tiers | Working | 5 tiers configured |
| Settings - Notifications | Working | Granular email controls |
| Billing/Plans | Working | All 4 plans displayed |
| Theme Blocks | Working | All 4 blocks available |

## Testing Remaining

- [ ] App proxy endpoints (storefront) - **404 error** - needs `shopify app deploy`
- [ ] Customer account extension - Needs Shopify checkout extension deployment
- [ ] Webhook handling - Needs live order/customer update
- [ ] Export members CSV - Not tested
- [ ] Add new member - Not tested

## Notes

### App Proxy 404 Issue
The app proxy at `/apps/rewards` returns 404 from Shopify. The backend proxy endpoint at `https://app.cardflowlabs.com/proxy/` is working correctly (returns "Invalid signature" for unsigned requests).

**Solution**: Run `shopify app deploy` to activate the app proxy configuration.

### Deployment Needed
Backend fixes for Suspend/Reactivate/Cancel API need to be deployed to production.
