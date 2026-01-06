# TradeUp User Stories - Exhaustive Testing Guide

## Overview
This document contains comprehensive user stories for testing all TradeUp membership system features. Each story includes the user role, action, expected outcome, and test steps.

---

## 1. Merchant Dashboard & Authentication

### 1.1 Embedded App Access
**As a** Shopify merchant
**I want to** access TradeUp from my Shopify admin
**So that** I can manage my membership program without leaving Shopify

**Test Steps:**
1. Log into Shopify Admin
2. Navigate to Apps → TradeUp
3. Verify dashboard loads within Shopify's embedded frame
4. Confirm you see the dashboard with stats overview

**Expected:** App loads embedded, showing dashboard with member count, recent activity, and quick actions

---

### 1.2 Dashboard Statistics
**As a** merchant
**I want to** see key metrics at a glance
**So that** I can understand my program's performance

**Test Steps:**
1. Open TradeUp dashboard
2. Verify these stats are displayed:
   - Total Members
   - Active Trade-Ins
   - Store Credit Issued (total)
   - Recent Activity feed

**Expected:** All statistics load and display accurate counts

---

## 2. Member Management

### 2.1 View All Members
**As a** merchant
**I want to** see a list of all program members
**So that** I can manage my customer base

**Test Steps:**
1. Navigate to Members tab
2. Verify member list displays with columns:
   - Name, Email, Tier, Status, Store Credit Balance, Join Date
3. Test pagination with 50+ members
4. Verify member count matches dashboard stat

**Expected:** Member list loads with all expected data, pagination works correctly

---

### 2.2 Enroll New Member
**As a** merchant
**I want to** manually enroll a customer in the program
**So that** I can add loyal customers who haven't signed up themselves

**Test Steps:**
1. Click "Enroll Customer" button
2. Search for a Shopify customer by email
3. Select a tier (Bronze, Silver, Gold, Platinum)
4. Confirm enrollment
5. Verify member appears in list

**Expected:** Customer is enrolled, assigned to selected tier, appears in member list immediately

---

### 2.3 Search Members
**As a** merchant
**I want to** search for specific members
**So that** I can quickly find customer records

**Test Steps:**
1. Use search field on Members page
2. Search by email
3. Search by name
4. Search by member number

**Expected:** Search returns matching results, filters apply correctly

---

### 2.4 View Member Details
**As a** merchant
**I want to** view a member's complete profile
**So that** I can see their activity history and current status

**Test Steps:**
1. Click on a member in the list
2. Verify profile shows:
   - Personal info (name, email, phone)
   - Current tier with benefits
   - Store credit balance
   - Trade-in history
   - Transaction ledger

**Expected:** Full member profile loads with complete history

---

### 2.5 Manually Adjust Tier
**As a** merchant
**I want to** manually change a member's tier
**So that** I can upgrade VIP customers or correct tier assignments

**Test Steps:**
1. Open member profile
2. Click "Change Tier" or edit tier dropdown
3. Select a different tier
4. Add a reason for the change
5. Save changes

**Expected:** Tier changes immediately, audit log records the change with reason

---

### 2.6 Add Store Credit Manually
**As a** merchant
**I want to** manually add store credit to a member
**So that** I can fulfill trade-ins or give goodwill credits

**Test Steps:**
1. Open member profile
2. Click "Add Credit"
3. Enter amount (e.g., $25.00)
4. Enter description (e.g., "Trade-in: Pokemon cards")
5. Submit

**Expected:** Credit is added, balance updates, ledger shows transaction with description

---

### 2.7 Deduct Store Credit
**As a** merchant
**I want to** remove store credit from a member
**So that** I can correct errors or handle chargebacks

**Test Steps:**
1. Open member profile
2. Click "Adjust Credit" or "Deduct"
3. Enter negative amount or use deduct function
4. Enter reason

**Expected:** Credit is deducted, balance updates, audit trail recorded

---

## 3. Tier Configuration

### 3.1 View All Tiers
**As a** merchant
**I want to** see all available membership tiers
**So that** I can understand and manage my tier structure

**Test Steps:**
1. Navigate to Settings → Tiers
2. Verify default tiers display:
   - BRONZE (free)
   - SILVER ($9.99/mo)
   - GOLD ($19.99/mo)
   - PLATINUM ($29.99/mo)
3. Verify each tier shows: name, price, trade-in bonus, cashback rate

**Expected:** All tiers display with correct configuration

---

### 3.2 Edit Tier Settings
**As a** merchant
**I want to** customize tier settings
**So that** I can set competitive pricing and benefits

**Test Steps:**
1. Click edit on a tier (e.g., GOLD)
2. Modify:
   - Monthly price
   - Yearly price
   - Trade-in bonus percentage
   - Cashback percentage
   - Description
3. Save changes

**Expected:** Changes save successfully, tier updates immediately

---

### 3.3 Yearly Pricing Configuration
**As a** merchant
**I want to** set yearly subscription prices
**So that** I can offer discounts for annual commitments

**Test Steps:**
1. Edit a tier
2. Set yearly_price (e.g., $179.99 for GOLD)
3. Verify yearly_savings and yearly_discount_pct calculate correctly
4. Save

**Expected:** Yearly price saves, savings/discount percentage display correctly

---

### 3.4 View Tier Audit Trail
**As a** merchant
**I want to** see who changed tier settings and when
**So that** I can track configuration changes

**Test Steps:**
1. Edit tier settings
2. Check audit log or history tab
3. Verify previous changes are recorded

**Expected:** Audit trail shows who changed what and when

---

## 4. Trade-In Management

### 4.1 View All Trade-Ins
**As a** merchant
**I want to** see all pending and completed trade-ins
**So that** I can manage incoming items

**Test Steps:**
1. Navigate to Trade-Ins tab
2. Verify list shows: customer, items, status, value, date
3. Filter by status: pending, in_review, approved, completed, rejected
4. Test pagination

**Expected:** Trade-in list loads with all data, filters work correctly

---

### 4.2 Create New Trade-In
**As a** merchant
**I want to** create a trade-in on behalf of a customer
**So that** I can process in-store trade-ins

**Test Steps:**
1. Click "New Trade-In"
2. Select member
3. Add items with descriptions and values
4. Set initial status (pending or approved)
5. Submit

**Expected:** Trade-in creates, member is notified, appears in list

---

### 4.3 Review Trade-In
**As a** merchant
**I want to** review a pending trade-in
**So that** I can verify items before approval

**Test Steps:**
1. Open a pending trade-in
2. View item list and descriptions
3. Adjust item values if needed
4. Change status to "in_review"
5. Add notes

**Expected:** Status updates, notes are saved, timeline shows activity

---

### 4.4 Approve Trade-In
**As a** merchant
**I want to** approve a trade-in
**So that** the customer receives their store credit

**Test Steps:**
1. Open a reviewed trade-in
2. Verify final values
3. Click "Approve"
4. Confirm credit amount

**Expected:** Status changes to approved, store credit is issued to member, ledger records transaction

---

### 4.5 Complete Trade-In
**As a** merchant
**I want to** mark a trade-in as complete
**So that** I can track when items are received

**Test Steps:**
1. Open approved trade-in
2. Confirm items received
3. Click "Complete"

**Expected:** Status changes to completed, trade-in is archived

---

### 4.6 Reject Trade-In
**As a** merchant
**I want to** reject a trade-in
**So that** I can decline items that don't meet standards

**Test Steps:**
1. Open pending trade-in
2. Click "Reject"
3. Enter rejection reason
4. Confirm

**Expected:** Status changes to rejected, customer is notified with reason, no credit issued

---

## 5. Store Credit System

### 5.1 Check Credit Balance via API
**As a** system
**I want to** query member credit balance
**So that** checkout extensions can display available credit

**Test Steps:**
1. GET /api/promotions/credit/balance/{member_id}
2. Verify response includes:
   - current_balance
   - pending_balance
   - lifetime_earned
   - lifetime_redeemed

**Expected:** Balance endpoint returns accurate figures

---

### 5.2 View Credit Ledger
**As a** merchant
**I want to** see the complete credit history for a member
**So that** I can audit transactions

**Test Steps:**
1. Open member profile → Credit History
2. Verify transactions show:
   - Date, type, amount, description, running balance
3. Filter by transaction type

**Expected:** Complete ledger with all transactions displayed

---

### 5.3 Sync Credit to Shopify
**As a** system
**I want to** sync store credit to Shopify native store credit
**So that** customers can redeem at checkout

**Test Steps:**
1. Add credit to a member
2. Check Shopify admin → Customers → [Customer] → Store Credit
3. Verify amount matches TradeUp balance

**Expected:** Credit syncs to Shopify within seconds

---

## 6. Cashback System

### 6.1 Configure Cashback Settings
**As a** merchant
**I want to** configure how cashback is delivered
**So that** I can choose the best method for my store

**Test Steps:**
1. Navigate to Settings → Cashback
2. Verify options:
   - Native Store Credit (recommended)
   - Discount Codes
   - Gift Cards
   - Manual
3. Toggle purchase_cashback_enabled
4. Toggle trade_in_credit_enabled
5. Set min_cashback_amount
6. Set rounding_mode (down, up, nearest)
7. Save

**Expected:** Settings save successfully, affect future transactions

---

### 6.2 Automatic Cashback on Purchase
**As a** customer
**I want to** earn cashback on my purchases
**So that** I can save on future orders

**Test Steps:**
1. Ensure purchase_cashback_enabled = true
2. Place a test order with a member account
3. Check member's credit balance after order
4. Verify cashback amount matches tier rate

**Expected:** Cashback is automatically credited based on tier percentage

---

### 6.3 Same Transaction Bonus
**As a** customer
**I want to** get my tier benefits on the same order I purchase membership
**So that** I start earning immediately

**Test Steps:**
1. Ensure same_transaction_bonus = true
2. Place order that includes membership upgrade
3. Verify tier benefits apply to that order's cashback

**Expected:** Tier benefits apply to the same transaction, not just future ones

---

## 7. Subscription Settings

### 7.1 Configure Subscription Options
**As a** merchant
**I want to** control subscription offerings
**So that** I can match my business model

**Test Steps:**
1. Navigate to Settings → Subscriptions
2. Toggle monthly_enabled
3. Toggle yearly_enabled
4. Set trial_days
5. Set grace_period_days
6. Save

**Expected:** Settings save, affect subscription availability

---

### 7.2 Yearly vs Monthly Billing Display
**As a** system
**I want to** calculate yearly savings
**So that** customers see the benefit of annual plans

**Test Steps:**
1. Check tier with both monthly and yearly prices
2. Verify yearly_savings = (monthly × 12) - yearly
3. Verify yearly_discount_pct calculation

**Expected:** Savings calculations are accurate

---

## 8. Referral Program

### 8.1 Generate Referral Code
**As a** customer
**I want to** get a unique referral code
**So that** I can share with friends

**Test Steps:**
1. Check member profile for referral_code
2. Verify code is unique
3. Verify referral link format

**Expected:** Each member has unique, shareable referral code

---

### 8.2 Track Referral Count
**As a** member
**I want to** see how many people I've referred
**So that** I can track my earnings

**Test Steps:**
1. Check member profile → referral_count
2. Verify referred_by_id relationship works
3. Check referral_earnings total

**Expected:** Referral metrics display accurately

---

## 9. Theme App Extension

### 9.1 Membership Signup Block
**As a** merchant
**I want to** add a membership signup widget to my store
**So that** customers can join the program

**Test Steps:**
1. Go to Shopify Theme Editor
2. Add TradeUp → Membership Signup block
3. Configure block settings
4. Verify it displays:
   - Tier benefits
   - Join button
   - Pricing

**Expected:** Block renders correctly, links to signup flow

---

### 9.2 Credit Badge Block
**As a** merchant
**I want to** show customers their credit balance
**So that** they're reminded to spend it

**Test Steps:**
1. Add TradeUp → Credit Badge block
2. View as logged-in customer
3. Verify balance displays

**Expected:** Badge shows current balance for logged-in members

---

### 9.3 Trade-In CTA Block
**As a** merchant
**I want to** promote trade-ins on my store
**So that** I can acquire more inventory

**Test Steps:**
1. Add TradeUp → Trade-In CTA block
2. Verify it displays:
   - Description of trade-in program
   - Start trade-in button

**Expected:** Block renders with proper styling and links

---

### 9.4 Refer a Friend Block
**As a** merchant
**I want to** promote referrals on my store
**So that** members bring new customers

**Test Steps:**
1. Add TradeUp → Refer a Friend block
2. View as logged-in member
3. Verify referral code/link displays

**Expected:** Block shows member's unique referral info

---

## 10. Webhook Processing

### 10.1 Order Created Webhook
**As a** system
**I want to** process order webhooks
**So that** cashback is awarded automatically

**Test Steps:**
1. Create test order in Shopify
2. Check server logs for webhook receipt
3. Verify cashback processing triggered
4. Check member credit updated

**Expected:** Webhook processes, cashback awarded correctly

---

### 10.2 Customer Created Webhook
**As a** system
**I want to** process customer webhooks
**So that** new customers can be auto-enrolled

**Test Steps:**
1. Enable auto_enrollment in settings
2. Create new customer in Shopify
3. Verify member record created in TradeUp

**Expected:** New customers automatically become members

---

### 10.3 Order Cancelled Webhook
**As a** system
**I want to** handle order cancellations
**So that** cashback is reversed

**Test Steps:**
1. Create and pay for test order
2. Verify cashback awarded
3. Cancel the order
4. Verify cashback is deducted/reversed

**Expected:** Cancellation reverses any cashback awarded

---

### 10.4 Refund Created Webhook
**As a** system
**I want to** handle refunds
**So that** cashback is prorated

**Test Steps:**
1. Create test order, verify cashback
2. Process partial refund
3. Verify cashback adjusted proportionally

**Expected:** Refund adjusts cashback based on refunded amount

---

## 11. Settings & Configuration

### 11.1 Branding Settings
**As a** merchant
**I want to** customize the app branding
**So that** it matches my store

**Test Steps:**
1. Navigate to Settings → Branding
2. Set app_name
3. Set tagline
4. Upload logo
5. Choose style (glass, solid, minimal)
6. Set primary color
7. Save and verify changes apply

**Expected:** Branding changes reflect throughout the app

---

### 11.2 Auto-Enrollment Settings
**As a** merchant
**I want to** configure auto-enrollment rules
**So that** customers join automatically

**Test Steps:**
1. Navigate to Settings → Auto-Enrollment
2. Toggle enabled
3. Set default_tier_id
4. Set min_order_value
5. Add excluded_tags (e.g., "wholesale", "staff")
6. Save

**Expected:** Settings save, affect auto-enrollment behavior

---

### 11.3 Notification Settings
**As a** merchant
**I want to** configure email notifications
**So that** members get relevant updates

**Test Steps:**
1. Navigate to Settings → Notifications
2. Toggle: welcome_email, trade_in_updates, tier_change, credit_issued
3. Set from_name and from_email
4. Save

**Expected:** Email settings affect what notifications are sent

---

## 12. API Endpoints Testing

### 12.1 GET /api/promotions/tiers
**Expected Response:**
```json
{
  "tiers": [
    {
      "id": 1,
      "tier_name": "BRONZE",
      "monthly_price": 0,
      "yearly_price": null,
      "trade_in_bonus_pct": 50,
      "cashback_pct": 0
    }
  ]
}
```

### 12.2 PUT /api/promotions/tiers/{id}
**Request:**
```json
{
  "monthly_price": 19.99,
  "yearly_price": 179.99,
  "trade_in_bonus_pct": 65
}
```

### 12.3 GET /api/settings/cashback
**Expected Response:**
```json
{
  "cashback": {
    "method": "native_store_credit",
    "purchase_cashback_enabled": true,
    "trade_in_credit_enabled": true,
    "same_transaction_bonus": true,
    "rounding_mode": "down",
    "min_cashback_amount": 0.01
  },
  "available_methods": {...}
}
```

### 12.4 PATCH /api/settings/cashback
**Request:**
```json
{
  "method": "native_store_credit",
  "rounding_mode": "nearest"
}
```

### 12.5 GET /api/members
**Parameters:** page, per_page, search, tier_id, status

### 12.6 POST /api/promotions/credit/add
**Request:**
```json
{
  "member_id": 2,
  "amount": 25.00,
  "description": "Trade-in: Pokemon cards"
}
```

---

## 13. Error Handling & Edge Cases

### 13.1 Invalid Tier Assignment
**Test:** Assign a non-existent tier to member
**Expected:** Error message, no changes made

### 13.2 Negative Credit Amount
**Test:** Try to deduct more credit than available
**Expected:** Error or warning, prevent negative balance

### 13.3 Webhook Signature Verification
**Test:** Send webhook with invalid signature
**Expected:** 401 Unauthorized response

### 13.4 Missing Shopify Customer
**Test:** Try to enroll customer that doesn't exist
**Expected:** Clear error message

### 13.5 Duplicate Enrollment
**Test:** Try to enroll already-enrolled customer
**Expected:** Error or update existing record

---

## 14. Performance Testing

### 14.1 Large Member List
**Test:** Load page with 1000+ members
**Expected:** Pagination works, page loads in <3 seconds

### 14.2 Concurrent Webhook Processing
**Test:** Multiple orders placed simultaneously
**Expected:** All webhooks process correctly without conflicts

### 14.3 Credit Ledger with High Volume
**Test:** Member with 500+ transactions
**Expected:** Ledger loads with pagination, calculations accurate

---

## Testing Checklist Summary

### Merchant Dashboard
- [ ] App loads embedded in Shopify
- [ ] Dashboard stats display correctly
- [ ] Navigation between sections works

### Member Management
- [ ] View all members
- [ ] Search members
- [ ] Enroll new member
- [ ] Change tier
- [ ] Add/deduct credit
- [ ] View member profile

### Tier Configuration
- [ ] View all tiers
- [ ] Edit tier settings
- [ ] Yearly pricing works
- [ ] Audit trail records changes

### Trade-Ins
- [ ] Create trade-in
- [ ] Review trade-in
- [ ] Approve trade-in
- [ ] Complete trade-in
- [ ] Reject trade-in
- [ ] Credit issued on approval

### Store Credit
- [ ] Balance API works
- [ ] Credit syncs to Shopify
- [ ] Ledger displays correctly

### Cashback
- [ ] Settings save correctly
- [ ] Cashback awarded on purchase
- [ ] Same transaction bonus works
- [ ] Refund adjusts cashback

### Theme Extension
- [ ] Membership signup block
- [ ] Credit badge block
- [ ] Trade-in CTA block
- [ ] Refer a friend block

### Webhooks
- [ ] Order created processes
- [ ] Order cancelled reverses cashback
- [ ] Refund adjusts cashback
- [ ] Customer created auto-enrolls

### Settings
- [ ] Branding settings work
- [ ] Cashback settings work
- [ ] Subscription settings work
- [ ] Auto-enrollment works
- [ ] Notifications configured

---

## Version History
- v1.0 - Initial user stories - 2026-01-06
