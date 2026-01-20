# TradeUp Complete Testing Checklist
## For Team Testing - Printer Friendly Version

**App:** TradeUp by Cardflow Labs
**Test Store:** uy288y-nx.myshopify.com (ORB Sports Cards)
**Production:** https://app.cardflowlabs.com
**Total User Stories:** 240 (200 core + 40 new features)

---

**Tester Name:** ________________________________
**Date:** ________________________________
**Browser/Device:** ________________________________

---

# SECTION 1: APP DISCOVERY & INSTALLATION (4 Stories)

*Note: Requires Shopify App Store listing - test post-launch*

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-1.1 | Find TradeUp in Shopify App Store with correct category tags | [ ] | [ ] | |
| US-1.2 | View screenshots, pricing, and feature descriptions in app listing | [ ] | [ ] | |
| US-1.3 | Click Install, complete OAuth, tenant created | [ ] | [ ] | |
| US-1.4 | Review and approve permissions screen | [ ] | [ ] | |

---

# SECTION 2: ONBOARDING & INITIAL SETUP (8 Stories)

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-2.1 | Step-by-step setup wizard displays with clear steps | [ ] | [ ] | |
| US-2.2 | Store credit check endpoint returns correct status | [ ] | [ ] | |
| US-2.3 | Link to Shopify settings when store credit disabled | [ ] | [ ] | |
| US-2.4 | Select tier templates (2-tier, 3-tier, 5-tier) | [ ] | [ ] | |
| US-2.5 | Modify tier names, pricing, benefits after template applied | [ ] | [ ] | |
| US-2.6 | Skip button works, redirects to dashboard | [ ] | [ ] | |
| US-2.7 | Completion marks tenant as onboarded | [ ] | [ ] | |
| US-2.8 | Resume onboarding where left off across sessions | [ ] | [ ] | |

**Test Steps for Onboarding:**
1. Open app as new merchant
2. Verify wizard shows Steps 1-5
3. Click through each step
4. Test skip functionality
5. Verify progress persists if you leave and return

---

# SECTION 3: BILLING & SUBSCRIPTION (11 Stories)

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-3.1 | See all 4 plans: Free, Starter ($19), Growth ($49), Pro ($99) | [ ] | [ ] | |
| US-3.2 | Free plan enforces 50 members, 2 tiers | [ ] | [ ] | |
| US-3.3 | Subscribe to Starter - Shopify charge created | [ ] | [ ] | |
| US-3.4 | Subscribe to Growth - Shopify charge created | [ ] | [ ] | |
| US-3.5 | Subscribe to Pro - Shopify charge created | [ ] | [ ] | |
| US-3.6 | 7-day free trial tracked, features unlocked | [ ] | [ ] | |
| US-3.7 | Upgrade plan mid-cycle works | [ ] | [ ] | |
| US-3.8 | Downgrade scheduled for cycle end | [ ] | [ ] | |
| US-3.9 | Cancel subscription stops billing | [ ] | [ ] | |
| US-3.10 | View payment history and invoices | [ ] | [ ] | |
| US-3.11 | Usage warnings at 80%, 90%, 100% of limits | [ ] | [ ] | |

**Test Steps for Billing:**
1. Navigate to Settings > Billing
2. Verify all 4 plans display with correct pricing
3. Click Subscribe on a plan (test mode)
4. Complete Shopify billing flow
5. Return to app and verify plan updated

---

# SECTION 4: MEMBER MANAGEMENT (17 Stories)

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-4.1 | View paginated list of all loyalty members | [ ] | [ ] | |
| US-4.2 | Search by name, email, phone, or member number | [ ] | [ ] | |
| US-4.3 | Filter members by tier | [ ] | [ ] | |
| US-4.4 | Filter by active/cancelled/suspended status | [ ] | [ ] | |
| US-4.5 | Search Shopify customers and enroll as members | [ ] | [ ] | |
| US-4.6 | Create new customer and enroll simultaneously | [ ] | [ ] | |
| US-4.7 | View full member profile (tier, trades, credit, history) | [ ] | [ ] | |
| US-4.8 | Update member name, email, phone, notes | [ ] | [ ] | |
| US-4.9 | Add external partner IDs (e.g., ORB#) to members | [ ] | [ ] | |
| US-4.10 | Manually change member tier | [ ] | [ ] | |
| US-4.11 | See tier change history with timestamps | [ ] | [ ] | |
| US-4.12 | Suspend member account | [ ] | [ ] | |
| US-4.13 | Reactivate suspended member | [ ] | [ ] | |
| US-4.14 | Cancel member membership | [ ] | [ ] | |
| US-4.15 | Permanently delete member (GDPR) | [ ] | [ ] | |
| US-4.16 | Export member data to CSV | [ ] | [ ] | |
| US-4.17 | View member's recent activity (trades, purchases, credits) | [ ] | [ ] | |

**Test Steps for Members:**
1. Navigate to Members tab
2. Verify list loads with pagination
3. Test search box - type email, verify instant results
4. Use tier dropdown filter
5. Click member row to view detail
6. Test Add Credit, Deduct Credit buttons
7. Test Change Tier dropdown
8. Test Suspend/Reactivate/Cancel actions

---

# SECTION 5: TIER SYSTEM CONFIGURATION (15 Stories)

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-5.1 | View all configured membership tiers | [ ] | [ ] | |
| US-5.2 | Create new tier with name, pricing, benefits | [ ] | [ ] | |
| US-5.3 | Set monthly subscription price | [ ] | [ ] | |
| US-5.4 | Set yearly subscription price (discounted) | [ ] | [ ] | |
| US-5.5 | Set trade-in bonus percentage | [ ] | [ ] | |
| US-5.6 | Set cashback percentage on purchases | [ ] | [ ] | |
| US-5.7 | Set monthly credit reward amount | [ ] | [ ] | |
| US-5.8 | Add custom text benefits | [ ] | [ ] | |
| US-5.9 | Modify existing tier settings | [ ] | [ ] | |
| US-5.10 | Drag-and-drop reorder tiers | [ ] | [ ] | |
| US-5.11 | Deactivate tier (hide from new signups) | [ ] | [ ] | |
| US-5.12 | Delete unused tier | [ ] | [ ] | |
| US-5.13 | See member count per tier | [ ] | [ ] | |
| US-5.14 | Configure auto-upgrade rules (spend/trade thresholds) | [ ] | [ ] | |
| US-5.15 | Bulk assign tier to multiple members | [ ] | [ ] | |

**Test Steps for Tiers:**
1. Navigate to Settings > Tiers
2. View existing tiers
3. Click "Add Tier" button
4. Fill in all fields and save
5. Edit an existing tier
6. Try to delete a tier with members (should warn)
7. Test drag-and-drop reordering

---

# SECTION 6: TRADE-IN MANAGEMENT (20 Stories)

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-6.1 | View all trade-in batches with status and value | [ ] | [ ] | |
| US-6.2 | Filter by pending/approved/listed/completed | [ ] | [ ] | |
| US-6.3 | Filter by category (Pokemon, MTG, Sports) | [ ] | [ ] | |
| US-6.4 | Start new trade-in batch for member | [ ] | [ ] | |
| US-6.5 | Create trade-in for non-member (guest) | [ ] | [ ] | |
| US-6.6 | Add individual items with title, SKU, value | [ ] | [ ] | |
| US-6.7 | Set trade value for each item | [ ] | [ ] | |
| US-6.8 | Record market reference value | [ ] | [ ] | |
| US-6.9 | Add notes about condition | [ ] | [ ] | |
| US-6.10 | See calculated tier bonus before completing | [ ] | [ ] | |
| US-6.11 | Approve pending trade-in | [ ] | [ ] | |
| US-6.12 | Reject trade-in with reason | [ ] | [ ] | |
| US-6.13 | Mark items as listed in Shopify | [ ] | [ ] | |
| US-6.14 | Complete batch and auto-issue store credit | [ ] | [ ] | |
| US-6.15 | View all items in batch with values/status | [ ] | [ ] | |
| US-6.16 | Modify items/values before completing | [ ] | [ ] | |
| US-6.17 | Search trade-ins by member name or reference | [ ] | [ ] | |
| US-6.18 | View status change history timeline | [ ] | [ ] | |
| US-6.19 | Auto-approve trade-ins under $X threshold | [ ] | [ ] | |
| US-6.20 | Require manual review for trade-ins over $X | [ ] | [ ] | |

**Test Steps for Trade-Ins:**
1. Navigate to Trade-Ins tab
2. Click "New Trade-In"
3. Select or create member
4. Add 3+ items with different values
5. Set category
6. Save as pending
7. Edit items (change values)
8. Approve trade-in
9. Verify credit issued to member
10. Check timeline shows all events

---

# SECTION 7: STORE CREDIT OPERATIONS (12 Stories)

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-7.1 | View all store credit transactions | [ ] | [ ] | |
| US-7.2 | Manually add credit to member account | [ ] | [ ] | |
| US-7.3 | Manually deduct credit from member | [ ] | [ ] | |
| US-7.4 | Set expiration dates on issued credit | [ ] | [ ] | |
| US-7.5 | View member's current credit balance | [ ] | [ ] | |
| US-7.6 | View all credit transactions for specific member | [ ] | [ ] | |
| US-7.7 | Filter by transaction type (trade-in/purchase/referral) | [ ] | [ ] | |
| US-7.8 | Run store-wide credit event | [ ] | [ ] | |
| US-7.9 | Preview credit event before running | [ ] | [ ] | |
| US-7.10 | Schedule credit event for future date | [ ] | [ ] | |
| US-7.11 | Select from credit event templates | [ ] | [ ] | |
| US-7.12 | Choose credit delivery method (store credit/discount/gift card) | [ ] | [ ] | |

**Test Steps for Store Credit:**
1. Navigate to Store Credit tab
2. View credit events list
3. Click "New Credit Event"
4. Select template or create custom
5. Preview affected members
6. Run event
7. Verify credits issued

---

# SECTION 8: POINTS SYSTEM (8 Stories)

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-8.1 | Toggle points system on/off | [ ] | [ ] | |
| US-8.2 | Set points earned per dollar spent | [ ] | [ ] | |
| US-8.3 | Configure tier bonus multipliers (Gold = 1.5x) | [ ] | [ ] | |
| US-8.4 | View member's current points balance | [ ] | [ ] | |
| US-8.5 | View points earned/redeemed history | [ ] | [ ] | |
| US-8.6 | Manually add or remove points | [ ] | [ ] | |
| US-8.7 | Set points expiration rules | [ ] | [ ] | |
| US-8.8 | Award bonus points for signup/referral/birthday | [ ] | [ ] | |

---

# SECTION 9: REWARDS CATALOG (14 Stories)

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-9.1 | View all configured rewards | [ ] | [ ] | |
| US-9.2 | Create fixed or percentage discount reward | [ ] | [ ] | |
| US-9.3 | Create free product reward | [ ] | [ ] | |
| US-9.4 | Create store credit reward | [ ] | [ ] | |
| US-9.5 | Create free shipping reward | [ ] | [ ] | |
| US-9.6 | Set points cost for reward | [ ] | [ ] | |
| US-9.7 | Limit rewards to specific tiers | [ ] | [ ] | |
| US-9.8 | Set total redemption limit | [ ] | [ ] | |
| US-9.9 | Set per-member redemption limit | [ ] | [ ] | |
| US-9.10 | Set start/end dates for rewards | [ ] | [ ] | |
| US-9.11 | Modify reward details | [ ] | [ ] | |
| US-9.12 | Deactivate reward | [ ] | [ ] | |
| US-9.13 | View all redemptions across members | [ ] | [ ] | |
| US-9.14 | Cancel redemption and restore points | [ ] | [ ] | |

---

# SECTION 10: REFERRAL PROGRAM (8 Stories)

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-10.1 | Toggle referrals on/off | [ ] | [ ] | |
| US-10.2 | Set referrer credit amount | [ ] | [ ] | |
| US-10.3 | Set new signup credit amount | [ ] | [ ] | |
| US-10.4 | Grant rewards on signup or first purchase | [ ] | [ ] | |
| US-10.5 | Cap referrals per member per month | [ ] | [ ] | |
| US-10.6 | View referral stats and top referrers | [ ] | [ ] | |
| US-10.7 | View member's unique referral code | [ ] | [ ] | |
| US-10.8 | View referral chain (who referred whom) | [ ] | [ ] | |

---

# SECTION 11: BULK OPERATIONS (6 Stories)

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-11.1 | Email all members in specific tier | [ ] | [ ] | |
| US-11.2 | Preview bulk email recipients | [ ] | [ ] | |
| US-11.3 | Select from email templates | [ ] | [ ] | |
| US-11.4 | Use {member_name}, {tier_name} variables | [ ] | [ ] | |
| US-11.5 | Bulk assign tier to selected members | [ ] | [ ] | |
| US-11.6 | Issue credit to all matching members | [ ] | [ ] | |

---

# SECTION 12: ANALYTICS & REPORTING (10 Stories)

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-12.1 | View key metrics at a glance (dashboard) | [ ] | [ ] | |
| US-12.2 | See member count over time chart | [ ] | [ ] | |
| US-12.3 | See trade-in count and value over time | [ ] | [ ] | |
| US-12.4 | See credits issued over time | [ ] | [ ] | |
| US-12.5 | Compare this month to last month | [ ] | [ ] | |
| US-12.6 | Analyze any custom date range | [ ] | [ ] | |
| US-12.7 | See top members by trade-in value | [ ] | [ ] | |
| US-12.8 | See trade-in report by category/status | [ ] | [ ] | |
| US-12.9 | View live activity feed | [ ] | [ ] | |
| US-12.10 | See plan usage stats | [ ] | [ ] | |

---

# SECTION 13: SETTINGS & CONFIGURATION (22 Stories)

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-13.1 | Set app name, logo, colors | [ ] | [ ] | |
| US-13.2 | Select visual theme (glass/solid/minimal) | [ ] | [ ] | |
| US-13.3 | Hide advanced features toggle | [ ] | [ ] | |
| US-13.4 | Choose rounding mode (down/up/nearest) | [ ] | [ ] | |
| US-13.5 | Set minimum cashback threshold | [ ] | [ ] | |
| US-13.6 | Toggle purchase cashback on/off | [ ] | [ ] | |
| US-13.7 | Toggle trade-in credit bonuses | [ ] | [ ] | |
| US-13.8 | Apply tier benefits to same transaction | [ ] | [ ] | |
| US-13.9 | Set trial days for new memberships | [ ] | [ ] | |
| US-13.10 | Set grace period for failed payments | [ ] | [ ] | |
| US-13.11 | Toggle welcome emails | [ ] | [ ] | |
| US-13.12 | Toggle trade-in status emails | [ ] | [ ] | |
| US-13.13 | Toggle tier change emails | [ ] | [ ] | |
| US-13.14 | Toggle credit received emails | [ ] | [ ] | |
| US-13.15 | Set sender name and email | [ ] | [ ] | |
| US-13.16 | Toggle auto-enroll after first purchase | [ ] | [ ] | |
| US-13.17 | Set default tier for auto-enrolled | [ ] | [ ] | |
| US-13.18 | Set minimum order value for auto-enroll | [ ] | [ ] | |
| US-13.19 | Exclude customers with certain tags | [ ] | [ ] | |
| US-13.20 | Toggle customer self-signup | [ ] | [ ] | |
| US-13.21 | Configure store currency | [ ] | [ ] | |
| US-13.22 | Set timezone | [ ] | [ ] | |

---

# SECTION 14: PROMOTIONS & TIER RULES (9 Stories)

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-14.1 | Create promo code for tier upgrades | [ ] | [ ] | |
| US-14.2 | Limit total promo code uses | [ ] | [ ] | |
| US-14.3 | Limit promo uses per member | [ ] | [ ] | |
| US-14.4 | Set promo code expiration | [ ] | [ ] | |
| US-14.5 | Restrict promos to upgrades only | [ ] | [ ] | |
| US-14.6 | Auto-upgrade at $500/year spend to Gold | [ ] | [ ] | |
| US-14.7 | Auto-upgrade at 10+ trade-ins to Silver | [ ] | [ ] | |
| US-14.8 | Evaluate rules over rolling 365-day period | [ ] | [ ] | |
| US-14.9 | View promo usage statistics | [ ] | [ ] | |

---

# SECTION 15: SHOPIFY INTEGRATION (7 Stories)

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-15.1 | Auto-create Shopify customer segments | [ ] | [ ] | |
| US-15.2 | Create per-tier segments ("TradeUp Gold Members") | [ ] | [ ] | |
| US-15.3 | Auto-create membership products | [ ] | [ ] | |
| US-15.4 | Use product wizard for membership setup | [ ] | [ ] | |
| US-15.5 | Product variants reflect tier pricing | [ ] | [ ] | |
| US-15.6 | Publish membership products to storefront | [ ] | [ ] | |
| US-15.7 | Sync tier/credit data to customer metafields | [ ] | [ ] | |

---

# SECTION 16: THEME EXTENSIONS (6 Stories)

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-16.1 | Add "Join Our Loyalty Program" block | [ ] | [ ] | |
| US-16.2 | Display customer credit balance badge | [ ] | [ ] | |
| US-16.3 | Add "Start Trade-In" button | [ ] | [ ] | |
| US-16.4 | Display referral code and sharing options | [ ] | [ ] | |
| US-16.5 | Place blocks anywhere in theme editor | [ ] | [ ] | |
| US-16.6 | Blocks inherit theme styling | [ ] | [ ] | |

**Test Steps for Theme Extensions:**
1. Go to Shopify Admin > Online Store > Themes > Customize
2. Add TradeUp app block to a page
3. Configure block settings
4. Preview on storefront
5. Verify data displays correctly

---

# SECTION 17: CUSTOMER ACCOUNT EXTENSION (4 Stories)

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-17.1 | Display rewards info in Shopify customer account | [ ] | [ ] | |
| US-17.2 | Show past trade-ins in account | [ ] | [ ] | |
| US-17.3 | Display current tier and benefits | [ ] | [ ] | |
| US-17.4 | Show referral stats in account | [ ] | [ ] | |

**Test Steps for Customer Account:**
1. Log into test store as customer
2. Go to Account page
3. Verify TradeUp section appears
4. Check balance, tier, trade-in history display

---

# SECTION 18: APP PROXY - REWARDS PAGE (4 Stories)

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-18.1 | /apps/rewards page loads on storefront | [ ] | [ ] | |
| US-18.2 | /proxy/balance returns JSON balance | [ ] | [ ] | |
| US-18.3 | /proxy/rewards returns JSON rewards catalog | [ ] | [ ] | |
| US-18.4 | /proxy/tiers returns JSON tier benefits | [ ] | [ ] | |

**Test URL:** https://uy288y-nx.myshopify.com/apps/rewards

---

# SECTION 19: DAY-TO-DAY OPERATIONS (10 Stories)

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-19.1 | Complete trade-in flow in < 2 minutes | [ ] | [ ] | |
| US-19.2 | Search member by phone or email instantly | [ ] | [ ] | |
| US-19.3 | Look up credit balance in < 5 seconds | [ ] | [ ] | |
| US-19.4 | View credit history for troubleshooting | [ ] | [ ] | |
| US-19.5 | Issue credit with note for complaints | [ ] | [ ] | |
| US-19.6 | Manually upgrade member tier | [ ] | [ ] | |
| US-19.7 | Verify member subscription is active | [ ] | [ ] | |
| US-19.8 | Review today's trade-ins and credits | [ ] | [ ] | |
| US-19.9 | Schedule bulk credit event | [ ] | [ ] | |
| US-19.10 | UI is intuitive for staff training | [ ] | [ ] | |

---

# SECTION 20: ERROR HANDLING & SUPPORT (5 Stories)

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| US-20.1 | Critical errors captured in Sentry | [ ] | [ ] | |
| US-20.2 | Toast notifications show for errors | [ ] | [ ] | |
| US-20.3 | Support contact info visible | [ ] | [ ] | |
| US-20.4 | Help docs accessible within app | [ ] | [ ] | |
| US-20.5 | Bug report form submits successfully | [ ] | [ ] | |

---

# SECTION 21: NEW FEATURES - INTEGRATIONS (40 Stories)

## Klaviyo Integration

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| NF-1.1 | Connect Klaviyo with API key | [ ] | [ ] | |
| NF-1.2 | Sync member events to Klaviyo | [ ] | [ ] | |

## Shopify Flow Integration

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| NF-2.1 | View available Flow triggers | [ ] | [ ] | |
| NF-2.2 | Test Flow triggers | [ ] | [ ] | |

## POS Extension

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| NF-3.1 | TradeUp tile on POS home | [ ] | [ ] | |
| NF-3.2 | Look up member at POS | [ ] | [ ] | |
| NF-3.3 | Issue credit from POS | [ ] | [ ] | |

## Points Expiry

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| NF-4.1 | Configure points expiry period | [ ] | [ ] | |
| NF-4.2 | Expiring points warning displays | [ ] | [ ] | |
| NF-4.3 | Points expire automatically | [ ] | [ ] | |

## Advanced Analytics

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| NF-5.1 | View Customer Lifetime Value | [ ] | [ ] | |
| NF-5.2 | Analyze cohort retention | [ ] | [ ] | |
| NF-5.3 | Calculate program ROI | [ ] | [ ] | |

## Referral Landing Pages

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| NF-6.1 | Customize referral page | [ ] | [ ] | |
| NF-6.2 | Share referral link (social) | [ ] | [ ] | |
| NF-6.3 | Track referral conversions | [ ] | [ ] | |

## Multi-Language Support

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| NF-7.1 | App in preferred language | [ ] | [ ] | |
| NF-7.2 | Customer pages localized | [ ] | [ ] | |

## Gorgias Integration

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| NF-8.1 | Connect Gorgias account | [ ] | [ ] | |
| NF-8.2 | View loyalty data in tickets | [ ] | [ ] | |

## Judge.me Integration

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| NF-9.1 | Connect Judge.me | [ ] | [ ] | |
| NF-9.2 | Earn points for reviews | [ ] | [ ] | |

## Recharge Integration

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| NF-10.1 | Connect Recharge | [ ] | [ ] | |
| NF-10.2 | Track subscription revenue | [ ] | [ ] | |

## Cashback Campaigns

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| NF-11.1 | Create cashback campaign | [ ] | [ ] | |
| NF-11.2 | Automatic cashback on orders | [ ] | [ ] | |
| NF-11.3 | View campaign performance | [ ] | [ ] | |

## Gift Card Creation

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| NF-12.1 | Issue gift card as reward | [ ] | [ ] | |
| NF-12.2 | Bulk gift card issuance | [ ] | [ ] | |

## Postscript SMS

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| NF-13.1 | Connect Postscript | [ ] | [ ] | |
| NF-13.2 | Trigger SMS on loyalty events | [ ] | [ ] | |

## Attentive SMS

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| NF-14.1 | Connect Attentive | [ ] | [ ] | |
| NF-14.2 | Sync attributes to Attentive | [ ] | [ ] | |

## Demo Store

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| NF-15.1 | Preview app without installing | [ ] | [ ] | |
| NF-15.2 | Explore features interactively | [ ] | [ ] | |

## Support Chat Widget

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| NF-16.1 | Access help articles in app | [ ] | [ ] | |
| NF-16.2 | Submit support ticket in app | [ ] | [ ] | |

## Benchmark Reports

| # | User Story | Pass | Fail | Notes |
|---|------------|:----:|:----:|-------|
| NF-17.1 | View industry benchmarks | [ ] | [ ] | |
| NF-17.2 | Identify strengths/opportunities | [ ] | [ ] | |
| NF-17.3 | Filter by industry category | [ ] | [ ] | |

---

# SECTION 22: WEBHOOK TESTING

| Webhook Topic | Pass | Fail | Notes |
|---------------|:----:|:----:|-------|
| orders/create | [ ] | [ ] | |
| orders/paid | [ ] | [ ] | |
| orders/fulfilled | [ ] | [ ] | |
| orders/cancelled | [ ] | [ ] | |
| refunds/create | [ ] | [ ] | |
| customers/create | [ ] | [ ] | |
| customers/update | [ ] | [ ] | |
| customers/delete | [ ] | [ ] | |
| products/create | [ ] | [ ] | |
| app/uninstalled | [ ] | [ ] | |

---

# SECTION 23: API ENDPOINT TESTING

## Quick API Tests

```bash
# Health Check
curl https://app.cardflowlabs.com/health

# Dashboard Stats
curl -H "X-Shopify-Shop-Domain: uy288y-nx.myshopify.com" \
  https://app.cardflowlabs.com/api/dashboard/stats

# Members List
curl -H "X-Shopify-Shop-Domain: uy288y-nx.myshopify.com" \
  https://app.cardflowlabs.com/api/members

# Tiers List
curl -H "X-Shopify-Shop-Domain: uy288y-nx.myshopify.com" \
  https://app.cardflowlabs.com/api/tiers
```

| Endpoint | Pass | Fail | Notes |
|----------|:----:|:----:|-------|
| GET /health | [ ] | [ ] | |
| GET /api/dashboard/stats | [ ] | [ ] | |
| GET /api/members | [ ] | [ ] | |
| POST /api/members/enroll | [ ] | [ ] | |
| GET /api/members/{id} | [ ] | [ ] | |
| PUT /api/members/{id} | [ ] | [ ] | |
| POST /api/members/{id}/suspend | [ ] | [ ] | |
| POST /api/members/{id}/reactivate | [ ] | [ ] | |
| GET /api/tiers | [ ] | [ ] | |
| POST /api/tiers | [ ] | [ ] | |
| GET /api/trade-ins | [ ] | [ ] | |
| POST /api/trade-ins | [ ] | [ ] | |
| POST /api/trade-ins/{id}/approve | [ ] | [ ] | |
| POST /api/store-credit/add | [ ] | [ ] | |
| POST /api/store-credit/deduct | [ ] | [ ] | |
| GET /api/billing/plans | [ ] | [ ] | |
| GET /api/billing/status | [ ] | [ ] | |
| GET /proxy/ | [ ] | [ ] | |
| GET /proxy/balance | [ ] | [ ] | |

---

# SECTION 24: PERFORMANCE TESTING

| Test | Target | Pass | Fail | Actual Time |
|------|--------|:----:|:----:|-------------|
| Dashboard load | < 3s | [ ] | [ ] | |
| Member list load | < 2s | [ ] | [ ] | |
| Member search response | < 500ms | [ ] | [ ] | |
| Trade-in list load | < 2s | [ ] | [ ] | |
| Settings page load | < 2s | [ ] | [ ] | |

---

# SECTION 25: MOBILE/RESPONSIVE TESTING

| Test | Pass | Fail | Notes |
|------|:----:|:----:|-------|
| Desktop (1200px+) layout correct | [ ] | [ ] | |
| Tablet (768-1024px) layout correct | [ ] | [ ] | |
| Mobile (< 768px) layout correct | [ ] | [ ] | |
| Navigation drawer works on mobile | [ ] | [ ] | |
| Buttons are tap-friendly | [ ] | [ ] | |
| Forms work on mobile | [ ] | [ ] | |

---

# TESTING SUMMARY

## Summary by Section

| Section | Total | Passed | Failed |
|---------|-------|--------|--------|
| 1. App Discovery | 4 | | |
| 2. Onboarding | 8 | | |
| 3. Billing | 11 | | |
| 4. Members | 17 | | |
| 5. Tiers | 15 | | |
| 6. Trade-Ins | 20 | | |
| 7. Store Credit | 12 | | |
| 8. Points | 8 | | |
| 9. Rewards | 14 | | |
| 10. Referrals | 8 | | |
| 11. Bulk Ops | 6 | | |
| 12. Analytics | 10 | | |
| 13. Settings | 22 | | |
| 14. Promotions | 9 | | |
| 15. Shopify | 7 | | |
| 16. Theme Ext | 6 | | |
| 17. Customer Acct | 4 | | |
| 18. App Proxy | 4 | | |
| 19. Operations | 10 | | |
| 20. Error Handling | 5 | | |
| 21. New Features | 40 | | |
| **TOTAL** | **240** | | |

---

## Sign-Off

**Testing Complete:** [ ] Yes  [ ] No

**Blocking Issues Found:**
_______________________________________________________
_______________________________________________________
_______________________________________________________

**Non-Blocking Issues:**
_______________________________________________________
_______________________________________________________
_______________________________________________________

**Ready for Launch:** [ ] Yes  [ ] No

**Tester Signature:** _______________________
**Date:** _______________________
**Reviewed By:** _______________________
**Date:** _______________________

---

*Document generated: January 17, 2026*
*TradeUp v1.0 - Pre-Launch Testing*
