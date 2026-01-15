# User Stories - TradeUp New Features

## Overview
This document contains user stories for all 17 new features implemented from competitive analysis.

---

## Feature 1: Klaviyo Integration

### US-1.1: Connect Klaviyo Account
**As a** merchant
**I want to** connect my Klaviyo account to TradeUp
**So that** I can sync customer loyalty data with my email marketing platform

**Acceptance Criteria:**
- [ ] Can enter Klaviyo API key in integration settings
- [ ] System validates the API key
- [ ] Connection status shows "Connected" when successful
- [ ] Can disconnect Klaviyo integration

### US-1.2: Sync Member Events to Klaviyo
**As a** merchant
**I want to** automatically sync loyalty events to Klaviyo
**So that** I can trigger email flows based on loyalty milestones

**Acceptance Criteria:**
- [ ] Member enrollment triggers `tradeup_member_enrolled` event
- [ ] Tier upgrades trigger `tradeup_tier_upgraded` event
- [ ] Trade-in completions trigger `tradeup_trade_in_completed` event
- [ ] Credit issuance triggers `tradeup_credit_issued` event

---

## Feature 2: Shopify Flow Integration

### US-2.1: View Available Flow Triggers
**As a** merchant
**I want to** see what TradeUp triggers are available in Shopify Flow
**So that** I can build automations based on loyalty events

**Acceptance Criteria:**
- [ ] Can view list of 8 available triggers
- [ ] Each trigger shows name and description
- [ ] Link to Shopify Flow editor is provided

### US-2.2: Test Flow Triggers
**As a** merchant
**I want to** test Flow triggers before going live
**So that** I can verify my automations will work correctly

**Acceptance Criteria:**
- [ ] Can send test event for each trigger type
- [ ] Test events appear in Shopify Flow logs

---

## Feature 3: Shopify POS Extension

### US-3.1: View TradeUp Tile on POS Home
**As a** store associate
**I want to** see a TradeUp tile on my POS home screen
**So that** I can quickly access loyalty features

**Acceptance Criteria:**
- [ ] TradeUp tile appears on POS home screen
- [ ] Tile shows quick member count
- [ ] Tapping tile opens member lookup

### US-3.2: Look Up Member at POS
**As a** store associate
**I want to** search for a customer's loyalty account
**So that** I can check their status during checkout

**Acceptance Criteria:**
- [ ] Can search by email or phone number
- [ ] Results show member name, tier, and credit balance
- [ ] Can view detailed member history

### US-3.3: Issue Credit from POS
**As a** store manager
**I want to** issue store credit from the POS terminal
**So that** I can reward customers for in-store trade-ins

**Acceptance Criteria:**
- [ ] Can enter credit amount
- [ ] Can add reason/note
- [ ] Credit appears immediately in customer's account
- [ ] Quick credit limited by settings

---

## Feature 4: Points Expiry System

### US-4.1: Configure Points Expiry
**As a** merchant
**I want to** set points to expire after a certain period
**So that** I can encourage customers to use their points

**Acceptance Criteria:**
- [ ] Can enable/disable points expiry
- [ ] Can set expiry period (days)
- [ ] Can configure warning email intervals

### US-4.2: View Expiring Points Warning
**As a** customer
**I want to** be notified when my points are about to expire
**So that** I can redeem them before they're lost

**Acceptance Criteria:**
- [ ] Dashboard shows expiring points warning
- [ ] Warning emails sent at configured intervals
- [ ] Customer portal shows expiry dates

### US-4.3: Points Expire Automatically
**As a** merchant
**I want** points to expire automatically based on my settings
**So that** I don't have to manually manage expirations

**Acceptance Criteria:**
- [ ] Points expire at configured date
- [ ] Expired points removed from balance
- [ ] Expiry recorded in transaction history

---

## Feature 5: Advanced Analytics & CLV Dashboard

### US-5.1: View Customer Lifetime Value
**As a** merchant
**I want to** see CLV metrics for my loyalty members
**So that** I can understand the value of my program

**Acceptance Criteria:**
- [ ] Dashboard shows average CLV
- [ ] Can view CLV by tier
- [ ] Can view CLV trends over time

### US-5.2: Analyze Cohort Retention
**As a** merchant
**I want to** see retention by signup cohort
**So that** I can identify trends in customer engagement

**Acceptance Criteria:**
- [ ] Cohort retention heatmap displayed
- [ ] Can filter by time period
- [ ] Shows 30/60/90 day retention rates

### US-5.3: Calculate Program ROI
**As a** merchant
**I want to** see the ROI of my loyalty program
**So that** I can justify the investment

**Acceptance Criteria:**
- [ ] Shows credit issued vs revenue driven
- [ ] Calculates ROI percentage
- [ ] Shows trend over time

---

## Feature 6: Referral Landing Pages

### US-6.1: Customize Referral Page
**As a** merchant
**I want to** customize my referral landing page
**So that** it matches my brand

**Acceptance Criteria:**
- [ ] Can set page headline and description
- [ ] Can upload background image
- [ ] Can configure social sharing options

### US-6.2: Share Referral Link
**As a** customer
**I want to** easily share my referral link
**So that** I can earn rewards for referring friends

**Acceptance Criteria:**
- [ ] Shareable URL generated for each member
- [ ] Can share via Facebook, Twitter, WhatsApp, email
- [ ] Copy link button available

### US-6.3: Track Referral Conversions
**As a** merchant
**I want to** see referral conversion metrics
**So that** I can measure program effectiveness

**Acceptance Criteria:**
- [ ] Shows referral link clicks
- [ ] Shows successful conversions
- [ ] Shows conversion rate

---

## Feature 7: Multi-Language (i18n) Support

### US-7.1: View App in My Language
**As a** merchant
**I want to** use TradeUp in my preferred language
**So that** I can understand all features

**Acceptance Criteria:**
- [ ] App detects browser/Shopify locale
- [ ] UI displays in detected language
- [ ] Can manually switch language

### US-7.2: Customer Pages in Local Language
**As a** customer
**I want to** see loyalty pages in my language
**So that** I can understand my rewards

**Acceptance Criteria:**
- [ ] Customer portal respects locale
- [ ] Email templates localized
- [ ] Currency formatted correctly

---

## Feature 8: Gorgias Integration

### US-8.1: Connect Gorgias Account
**As a** merchant
**I want to** connect Gorgias to TradeUp
**So that** support can see loyalty data in tickets

**Acceptance Criteria:**
- [ ] Can enter Gorgias API key and domain
- [ ] Connection validates successfully
- [ ] Can disconnect integration

### US-8.2: View Loyalty Data in Tickets
**As a** support agent
**I want to** see customer loyalty info in Gorgias
**So that** I can provide better service

**Acceptance Criteria:**
- [ ] Widget shows tier and credit balance
- [ ] Shows recent trade-in history
- [ ] Shows points balance

---

## Feature 9: Judge.me Integration

### US-9.1: Connect Judge.me
**As a** merchant
**I want to** connect Judge.me to TradeUp
**So that** customers earn points for reviews

**Acceptance Criteria:**
- [ ] Can enter Judge.me API key
- [ ] Connection validates successfully
- [ ] Can configure point amounts

### US-9.2: Earn Points for Reviews
**As a** customer
**I want to** earn points when I leave a review
**So that** I'm rewarded for my feedback

**Acceptance Criteria:**
- [ ] Text review awards base points (50)
- [ ] Photo review awards bonus points (100)
- [ ] Video review awards maximum points (200)

---

## Feature 10: Recharge Integration

### US-10.1: Connect Recharge
**As a** merchant
**I want to** connect Recharge to TradeUp
**So that** subscription revenue counts toward loyalty

**Acceptance Criteria:**
- [ ] Can enter Recharge API key
- [ ] Connection validates successfully
- [ ] Can configure tracking options

### US-10.2: Track Subscription Revenue
**As a** merchant
**I want** subscription payments to count for tier eligibility
**So that** subscribers get loyalty benefits

**Acceptance Criteria:**
- [ ] Subscription revenue tracked in member total
- [ ] Tier status considers subscription value
- [ ] Points awarded on recurring payments

---

## Feature 11: Cashback Campaigns

### US-11.1: Create Cashback Campaign
**As a** merchant
**I want to** create promotional cashback campaigns
**So that** I can incentivize purchases during specific periods

**Acceptance Criteria:**
- [ ] Can set campaign name and dates
- [ ] Can set cashback percentage
- [ ] Can set min/max purchase thresholds
- [ ] Can target specific tiers

### US-11.2: Automatic Cashback on Orders
**As a** customer
**I want to** automatically receive cashback during promotions
**So that** I don't have to take extra steps

**Acceptance Criteria:**
- [ ] Cashback calculated on qualifying orders
- [ ] Credit issued automatically
- [ ] Customer notified of cashback earned

### US-11.3: View Campaign Performance
**As a** merchant
**I want to** see how my cashback campaigns perform
**So that** I can optimize future promotions

**Acceptance Criteria:**
- [ ] Shows total cashback issued
- [ ] Shows number of qualifying orders
- [ ] Shows revenue during campaign

---

## Feature 12: Gift Card Creation

### US-12.1: Issue Gift Card as Reward
**As a** merchant
**I want to** issue Shopify gift cards as rewards
**So that** customers have flexible redemption options

**Acceptance Criteria:**
- [ ] Can create gift card from admin
- [ ] Gift card amount configurable
- [ ] Customer receives gift card code

### US-12.2: Bulk Gift Card Issuance
**As a** merchant
**I want to** issue gift cards to multiple customers at once
**So that** I can run promotions efficiently

**Acceptance Criteria:**
- [ ] Can select multiple members
- [ ] Can set amount for all
- [ ] Gift cards created in batch

---

## Feature 13: Postscript SMS Integration

### US-13.1: Connect Postscript
**As a** merchant
**I want to** connect Postscript to TradeUp
**So that** I can send SMS for loyalty events

**Acceptance Criteria:**
- [ ] Can enter Postscript API key
- [ ] Connection validates successfully
- [ ] Can configure event triggers

### US-13.2: Trigger SMS on Loyalty Events
**As a** merchant
**I want to** send SMS notifications for key events
**So that** customers stay engaged with their rewards

**Acceptance Criteria:**
- [ ] SMS sent on tier upgrade
- [ ] SMS sent on credit issuance
- [ ] SMS sent on points expiry warning

---

## Feature 14: Attentive SMS Integration

### US-14.1: Connect Attentive
**As a** merchant
**I want to** connect Attentive to TradeUp
**So that** I can use Attentive for loyalty SMS

**Acceptance Criteria:**
- [ ] Can enter Attentive API key
- [ ] Connection validates successfully
- [ ] Can configure journeys

### US-14.2: Sync Attributes to Attentive
**As a** merchant
**I want** customer loyalty data synced to Attentive
**So that** I can segment by tier and points

**Acceptance Criteria:**
- [ ] Member tier synced as attribute
- [ ] Points balance synced
- [ ] Credit balance synced

---

## Feature 15: Demo Store Viewer

### US-15.1: Preview App Before Installing
**As a** prospective merchant
**I want to** see a demo of TradeUp
**So that** I can evaluate if it meets my needs

**Acceptance Criteria:**
- [ ] Demo accessible without installation
- [ ] Shows all major features
- [ ] Uses realistic sample data

### US-15.2: Explore Features Interactively
**As a** prospective merchant
**I want to** interact with the demo
**So that** I can understand how features work

**Acceptance Criteria:**
- [ ] Can navigate between pages
- [ ] Can view sample members
- [ ] Can see sample analytics

---

## Feature 16: In-App Support Chat Widget

### US-16.1: Access Help Articles
**As a** merchant
**I want to** find help articles within the app
**So that** I can solve issues quickly

**Acceptance Criteria:**
- [ ] Help button visible in app
- [ ] Popular articles displayed
- [ ] Links to full help center

### US-16.2: Submit Support Ticket
**As a** merchant
**I want to** submit a support ticket from the app
**So that** I can get help without leaving TradeUp

**Acceptance Criteria:**
- [ ] Can select issue category
- [ ] Can describe problem
- [ ] Confirmation shown on submit
- [ ] Fallback to email if API fails

---

## Feature 17: Benchmark Reports

### US-17.1: View Industry Benchmarks
**As a** merchant
**I want to** see how my program compares to industry
**So that** I know where to improve

**Acceptance Criteria:**
- [ ] Shows key metrics with percentiles
- [ ] Compares to industry median
- [ ] Shows my ranking (A/B/C grade)

### US-17.2: Identify Strengths and Opportunities
**As a** merchant
**I want to** see my program's strengths and weaknesses
**So that** I can prioritize improvements

**Acceptance Criteria:**
- [ ] Strengths highlighted (>75th percentile)
- [ ] Opportunities identified (<50th percentile)
- [ ] Recommendations provided

### US-17.3: Filter by Industry Category
**As a** merchant
**I want to** compare against similar stores
**So that** benchmarks are relevant to my business

**Acceptance Criteria:**
- [ ] Can select industry category
- [ ] Benchmarks update based on selection
- [ ] Categories include: Sports Cards, Pokemon, MTG, Collectibles

---

## Test Tracking

| Feature | User Stories | Tested | Passed |
|---------|-------------|--------|--------|
| 1. Klaviyo | 2 | [ ] | [ ] |
| 2. Shopify Flow | 2 | [ ] | [ ] |
| 3. POS Extension | 3 | [ ] | [ ] |
| 4. Points Expiry | 3 | [ ] | [ ] |
| 5. Analytics/CLV | 3 | [ ] | [ ] |
| 6. Referral Pages | 3 | [ ] | [ ] |
| 7. i18n Support | 2 | [ ] | [ ] |
| 8. Gorgias | 2 | [ ] | [ ] |
| 9. Judge.me | 2 | [ ] | [ ] |
| 10. Recharge | 2 | [ ] | [ ] |
| 11. Cashback | 3 | [ ] | [ ] |
| 12. Gift Cards | 2 | [ ] | [ ] |
| 13. Postscript | 2 | [ ] | [ ] |
| 14. Attentive | 2 | [ ] | [ ] |
| 15. Demo Viewer | 2 | [ ] | [ ] |
| 16. Support Widget | 2 | [ ] | [ ] |
| 17. Benchmarks | 3 | [ ] | [ ] |
| **TOTAL** | **40** | | |
