# TradeUp Comprehensive Test Plan

## Current State Assessment

Based on the testing session on Jan 26, 2026:
- **Event History**: Required fix to persist events
- **Credit Ledger**: Missing database table
- **UI Issues**: Date picker corruption, clunky workflows
- **Documentation**: Overstated readiness

## Test Environment Setup

### Option A: Matrixify Migration (Recommended)

**Time**: ~2 hours
**Cost**: $20 (one month, cancel after)

1. Install [Matrixify](https://apps.shopify.com/excel-export-import) on production store
2. Export:
   - Products (with variants, images, metafields)
   - Collections (smart rules preserved)
   - Customers (with tags, addresses)
   - Orders (last 6 months minimum)
3. Install Matrixify on test store
4. Import in order: Products → Collections → Customers → Orders

### Option B: API Migration Script

I can create `scripts/migrate_store_data.py` that:
- Connects to source store via Admin API
- Copies products, collections, customers
- Creates synthetic orders based on patterns

### Option C: Synthetic Test Data Generator

Create `scripts/generate_test_data.py` that:
- Creates realistic products in categories (Sports Cards, Pokemon, MTG)
- Creates test customers with various attributes
- Creates orders with different scenarios
- Sets up members at different tiers

---

## Required Test Data

### Products (minimum 50)
| Category | Count | Notes |
|----------|-------|-------|
| Sports Cards | 20 | Various price points $5-$500 |
| Pokemon | 15 | Singles and sealed |
| MTG | 10 | Singles and sealed |
| Supplies | 5 | Sleeves, toploaders |

### Collections
| Collection | Type | Products |
|------------|------|----------|
| Sports Cards | Smart (tag-based) | 20 |
| Pokemon | Smart (tag-based) | 15 |
| MTG | Smart (tag-based) | 10 |
| New Arrivals | Smart (date-based) | Auto |
| Sale Items | Smart (compare_at_price) | Variable |
| High Value | Smart (price > $100) | Variable |

### Customers (minimum 30)
| Type | Count | Characteristics |
|------|-------|-----------------|
| Active members | 10 | Various tiers, purchase history |
| Inactive members | 5 | No purchases in 60+ days |
| Non-members | 10 | Customers without membership |
| New customers | 5 | Created in last 7 days |

### Orders (minimum 100)
| Scenario | Count | Notes |
|----------|-------|-------|
| POS orders | 40 | In-store purchases |
| Online orders | 40 | Web checkout |
| Multi-item orders | 15 | 3+ items |
| Refunded orders | 5 | Partial and full refunds |

---

## User Stories to Test

### Epic 1: Member Management

| ID | Story | Priority | Status |
|----|-------|----------|--------|
| MM-001 | As a merchant, I can view all members in a searchable list | High | ⬜ |
| MM-002 | As a merchant, I can search members by name, email, phone, member# | High | ⬜ |
| MM-003 | As a merchant, I can view a member's complete profile | High | ⬜ |
| MM-004 | As a merchant, I can manually add a new member | High | ⬜ |
| MM-005 | As a merchant, I can edit member details | Medium | ⬜ |
| MM-006 | As a merchant, I can assign/change a member's tier | High | ⬜ |
| MM-007 | As a merchant, I can suspend a member | Medium | ⬜ |
| MM-008 | As a merchant, I can reactivate a suspended member | Medium | ⬜ |
| MM-009 | As a merchant, I can view member's store credit balance | High | ⬜ |
| MM-010 | As a merchant, I can manually add store credit to a member | High | ⬜ |
| MM-011 | As a merchant, I can manually deduct store credit from a member | High | ⬜ |
| MM-012 | As a merchant, I can view member's credit transaction history | High | ⬜ |
| MM-013 | As a merchant, I can view member's purchase history | Medium | ⬜ |
| MM-014 | As a merchant, I can view member's points balance | High | ⬜ |
| MM-015 | As a merchant, I can manually adjust points | Medium | ⬜ |

### Epic 2: Tier Management

| ID | Story | Priority | Status |
|----|-------|----------|--------|
| TM-001 | As a merchant, I can view all configured tiers | High | ⬜ |
| TM-002 | As a merchant, I can create a new tier | High | ⬜ |
| TM-003 | As a merchant, I can edit tier benefits | High | ⬜ |
| TM-004 | As a merchant, I can set tier pricing (monthly/yearly) | High | ⬜ |
| TM-005 | As a merchant, I can configure trade-in bonus percentage | High | ⬜ |
| TM-006 | As a merchant, I can configure purchase cashback percentage | High | ⬜ |
| TM-007 | As a merchant, I can configure points multiplier | Medium | ⬜ |
| TM-008 | As a merchant, I can set tier colors and icons | Low | ⬜ |
| TM-009 | As a merchant, I can reorder tier display priority | Low | ⬜ |
| TM-010 | As a merchant, I can delete an unused tier | Medium | ⬜ |

### Epic 3: Trade-In Management

| ID | Story | Priority | Status |
|----|-------|----------|--------|
| TR-001 | As a merchant, I can create a new trade-in batch | High | ⬜ |
| TR-002 | As a merchant, I can add items to a trade-in batch | High | ⬜ |
| TR-003 | As a merchant, I can edit item values in a batch | High | ⬜ |
| TR-004 | As a merchant, I can remove items from a batch | High | ⬜ |
| TR-005 | As a merchant, I can view batch total and tier bonus | High | ⬜ |
| TR-006 | As a merchant, I can complete a trade-in batch | High | ⬜ |
| TR-007 | As a merchant, I can cancel a trade-in batch | Medium | ⬜ |
| TR-008 | As a merchant, I can view completed trade-in history | High | ⬜ |
| TR-009 | As a merchant, I can create a trade-in for a non-member | Medium | ⬜ |
| TR-010 | Completing trade-in issues correct store credit | High | ⬜ |
| TR-011 | Completing trade-in applies tier bonus correctly | High | ⬜ |

### Epic 4: Store Credit Events (Bulk)

| ID | Story | Priority | Status |
|----|-------|----------|--------|
| SC-001 | As a merchant, I can create a bulk credit event | High | ⬜ |
| SC-002 | As a merchant, I can set date range for event | High | ⬜ |
| SC-003 | As a merchant, I can filter by order source (POS, online) | High | ⬜ |
| SC-004 | As a merchant, I can filter by collection | High | ⬜ |
| SC-005 | As a merchant, I can preview before applying credits | High | ⬜ |
| SC-006 | As a merchant, I can see individual customer amounts | High | ⬜ |
| SC-007 | As a merchant, I can apply credits to all customers | High | ⬜ |
| SC-008 | Applied credits show correct amounts | High | ⬜ |
| SC-009 | Event history shows completed events | High | ⬜ |
| SC-010 | As a merchant, I can target members only or all customers | Medium | ⬜ |

### Epic 5: Live Promotions (Scheduled)

| ID | Story | Priority | Status |
|----|-------|----------|--------|
| LP-001 | As a merchant, I can create a scheduled promotion | High | ⬜ |
| LP-002 | As a merchant, I can set promotion date/time window | High | ⬜ |
| LP-003 | As a merchant, I can set cashback percentage | High | ⬜ |
| LP-004 | As a merchant, I can limit to specific collections | Medium | ⬜ |
| LP-005 | As a merchant, I can limit to specific tiers | Medium | ⬜ |
| LP-006 | Promotion activates at scheduled time | High | ⬜ |
| LP-007 | Promotion deactivates at end time | High | ⬜ |
| LP-008 | Orders during promotion receive cashback | High | ⬜ |
| LP-009 | Cashback applies only to qualifying products | High | ⬜ |

### Epic 6: Credit Ledger

| ID | Story | Priority | Status |
|----|-------|----------|--------|
| CL-001 | As a merchant, I can view all credit transactions | High | ⬜ |
| CL-002 | As a merchant, I can search by customer email | High | ⬜ |
| CL-003 | As a merchant, I can filter by event type | Medium | ⬜ |
| CL-004 | As a merchant, I can filter by date range | Medium | ⬜ |
| CL-005 | As a merchant, I can export to CSV | Medium | ⬜ |
| CL-006 | Ledger shows accurate running balances | High | ⬜ |
| CL-007 | All credit events appear in ledger | High | ⬜ |

### Epic 7: Points/Gamification

| ID | Story | Priority | Status |
|----|-------|----------|--------|
| PT-001 | As a merchant, I can configure points per dollar | High | ⬜ |
| PT-002 | As a merchant, I can view points leaderboard | Medium | ⬜ |
| PT-003 | Purchases earn points correctly | High | ⬜ |
| PT-004 | Tier multipliers apply to points | High | ⬜ |
| PT-005 | As a merchant, I can create badges | Medium | ⬜ |
| PT-006 | Badges award automatically based on rules | Medium | ⬜ |

### Epic 8: Referrals

| ID | Story | Priority | Status |
|----|-------|----------|--------|
| RF-001 | Members have unique referral codes | High | ⬜ |
| RF-002 | Referred customer links to referrer | High | ⬜ |
| RF-003 | Referrer receives credit on referee's purchase | High | ⬜ |
| RF-004 | As a merchant, I can configure referral reward amount | High | ⬜ |

### Epic 9: Webhooks/Integrations

| ID | Story | Priority | Status |
|----|-------|----------|--------|
| WH-001 | New order creates points/cashback | High | ⬜ |
| WH-002 | Refund reverses points/cashback | High | ⬜ |
| WH-003 | New customer can be auto-enrolled | Medium | ⬜ |
| WH-004 | App uninstall cleans up data | High | ⬜ |

### Epic 10: Customer-Facing (Extensions)

| ID | Story | Priority | Status |
|----|-------|----------|--------|
| CF-001 | Checkout shows points to be earned | High | ⬜ |
| CF-002 | Checkout shows tier badge | High | ⬜ |
| CF-003 | Customer account shows rewards dashboard | High | ⬜ |
| CF-004 | Customer account shows points balance | High | ⬜ |
| CF-005 | Customer account shows credit balance | High | ⬜ |
| CF-006 | Customer account shows tier benefits | High | ⬜ |
| CF-007 | Post-purchase shows celebration | Medium | ⬜ |
| CF-008 | Post-purchase shows referral prompt | Medium | ⬜ |
| CF-009 | POS shows member lookup | High | ⬜ |

### Epic 11: Billing

| ID | Story | Priority | Status |
|----|-------|----------|--------|
| BL-001 | As a merchant, I can view available plans | High | ⬜ |
| BL-002 | As a merchant, I can subscribe to a plan | High | ⬜ |
| BL-003 | As a merchant, I can upgrade plan | High | ⬜ |
| BL-004 | As a merchant, I can downgrade plan | Medium | ⬜ |
| BL-005 | As a merchant, I can cancel subscription | High | ⬜ |
| BL-006 | Usage limits enforce correctly | High | ⬜ |

---

## Testing Execution Plan

### Phase 1: Setup (Day 1)
1. [ ] Choose data migration approach
2. [ ] Execute data migration to test store
3. [ ] Verify test data imported correctly
4. [ ] Install TradeUp app on test store
5. [ ] Run through onboarding

### Phase 2: Core Features (Day 2-3)
1. [ ] Member Management (MM-001 to MM-015)
2. [ ] Tier Management (TM-001 to TM-010)
3. [ ] Trade-In Management (TR-001 to TR-011)

### Phase 3: Credit & Promotions (Day 4-5)
1. [ ] Store Credit Events (SC-001 to SC-010)
2. [ ] Live Promotions (LP-001 to LP-009)
3. [ ] Credit Ledger (CL-001 to CL-007)

### Phase 4: Advanced Features (Day 6-7)
1. [ ] Points/Gamification (PT-001 to PT-006)
2. [ ] Referrals (RF-001 to RF-004)
3. [ ] Webhooks (WH-001 to WH-004)

### Phase 5: Customer-Facing (Day 8)
1. [ ] All Extensions (CF-001 to CF-009)
2. [ ] App Proxy customer page

### Phase 6: Billing & Edge Cases (Day 9-10)
1. [ ] Billing flows (BL-001 to BL-006)
2. [ ] Edge cases and error scenarios
3. [ ] Performance testing

---

## Bug Tracking Template

When a bug is found, document:

```markdown
### BUG-XXX: [Title]

**Story**: [User story ID]
**Severity**: Critical / High / Medium / Low
**Status**: Open / In Progress / Fixed / Verified

**Steps to Reproduce**:
1.
2.
3.

**Expected Result**:

**Actual Result**:

**Screenshot/Video**:

**Fix Applied**:
```

---

## Decision Needed

Which approach would you like to take for test data?

1. **Matrixify** - Full production data copy (~$20, ~2 hours)
2. **API Script** - I build a migration script (free, ~4 hours dev time)
3. **Synthetic Generator** - Generate realistic fake data (free, ~2 hours dev time)

Recommendation: **Option 1 (Matrixify)** for realistic testing, then **Option 3** for edge case scenarios.
