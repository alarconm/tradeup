# TradeUp - Shopify App Store Submission Checklist

**Created:** January 19, 2026
**Target:** Submit to Shopify App Store for review

---

## Pre-Flight Checklist

### 1. Legal & Compliance Pages

| Item | Status | URL | Notes |
|------|--------|-----|-------|
| Privacy Policy | ✅ DONE | `/privacy-policy.html` | Live at app.cardflowlabs.com |
| Terms of Service | ✅ DONE | `/terms-of-service.html` | Created Jan 19, 2026 |
| GDPR Webhooks | ✅ DONE | See shopify.app.toml | All 3 implemented |

### 2. App Assets

| Item | Status | File/Location | Notes |
|------|--------|---------------|-------|
| App Icon (512x512) | ✅ DONE | `frontend/public/tradeup-icon-512.png` | Distinct, no Shopify bag |
| App Icon (1200x1200) | ✅ DONE | `frontend/public/tradeup-icon-1200.png` | High-res version |
| Screenshot: Dashboard | ✅ DONE | `frontend/public/screenshots/screenshot-dashboard.png` | |
| Screenshot: Members | ✅ DONE | `frontend/public/screenshots/screenshot-members.png` | |
| Screenshot: Trade-Ins | ✅ DONE | `frontend/public/screenshots/screenshot-trade-ins.png` | |
| Screenshot: Quick Flip | ✅ DONE | `frontend/public/screenshots/screenshot-quick-flip.png` | |

### 3. App Listing Content

| Item | Status | Notes |
|------|--------|-------|
| App Name | ✅ DONE | "TradeUp by Cardflow Labs" |
| Tagline | ✅ DONE | See APP_STORE_LISTING.md |
| Short Description | ✅ DONE | See APP_STORE_LISTING.md |
| Long Description | ✅ DONE | See APP_STORE_LISTING.md |
| Categories | ✅ DONE | Customer accounts, Loyalty and rewards |
| Search Keywords | ✅ DONE | See APP_STORE_LISTING.md |
| Demo Video/Screencast | ⏳ TODO | 2-5 min showing full flow |

### 4. Technical Requirements

| Item | Status | Notes |
|------|--------|-------|
| GraphQL API (not REST) | ✅ DONE | Using GraphQL Admin API |
| Shopify Billing API | ✅ DONE | 4 plans configured |
| GDPR Webhooks | ✅ DONE | customer_redact, shop_redact, data_request |
| OAuth Flow | ✅ DONE | HMAC verified, state param |
| Embedded App | ✅ DONE | App Bridge integrated |

### 5. Environment Configuration

| Item | Status | Action Required |
|------|--------|-----------------|
| SHOPIFY_BILLING_TEST | ⚠️ CHANGE | **Set to `false` in Railway before launch** |
| SENTRY_DSN | ✅ DONE | Error tracking active |
| DATABASE_URL | ✅ DONE | PostgreSQL on Railway |
| APP_URL | ✅ DONE | https://app.cardflowlabs.com |

---

## Action Items (Do These Now)

### CRITICAL: Set Billing to Production Mode

```bash
# In Railway Dashboard:
# 1. Go to your TradeUp service
# 2. Click "Variables"
# 3. Add or update:

SHOPIFY_BILLING_TEST=false
```

**Why:** Currently set to `true` (test mode). Shopify will not approve an app that can't actually charge merchants.

### Required: Add Emergency Contact

1. Go to: https://partners.shopify.com
2. Click: Settings → Contact information
3. Add emergency developer contact:
   - Name: Michael Alarcon
   - Email: mike@cardflowlabs.com
   - Phone: [Your phone]

### Required: Create Demo Video

**Tools:** Loom (free), OBS, or Screen Studio

**Script (3-4 minutes):**
1. **Install** (0:00-0:20) - Show app installation from admin
2. **Onboard** (0:20-1:00) - Complete setup wizard, pick tier template
3. **Dashboard** (1:00-1:30) - Show metrics and quick actions
4. **Create Member** (1:30-2:00) - Enroll a customer
5. **Process Trade-In** (2:00-2:45) - Add items, calculate credit
6. **Customer View** (2:45-3:15) - Show /apps/rewards customer page
7. **Wrap Up** (3:15-3:30) - Settings overview

**Upload to:** YouTube (unlisted) or direct upload to Partner Dashboard

### Recommended: Test Support Email

Send a test email to verify it works:
```
To: mike@orbsportscards.com
Subject: Test - Pre-launch check
Body: Testing support email before App Store submission.
```

---

## Submission Process

### Step 1: Partner Dashboard Prep

1. Log into https://partners.shopify.com
2. Go to Apps → TradeUp by Cardflow Labs
3. Click "App listing" in sidebar

### Step 2: Fill Out Listing

Copy content from `docs/APP_STORE_LISTING.md`:

- **App name:** TradeUp by Cardflow Labs
- **Tagline:** (copy from doc)
- **Description:** (copy from doc)
- **Screenshots:** Upload all 4 from `frontend/public/screenshots/`
- **App icon:** Upload from `frontend/public/tradeup-icon-512.png`
- **Demo video:** Add YouTube link or upload file
- **Categories:** Customer accounts (primary), Loyalty and rewards (secondary)
- **Privacy policy:** https://app.cardflowlabs.com/privacy-policy.html
- **Support:** mike@orbsportscards.com
- **Developer website:** https://cardflowlabs.com

### Step 3: Pricing

Set up pricing in Partner Dashboard → Billing:

| Plan | Monthly Price | Trial Days |
|------|---------------|------------|
| Free | $0 | - |
| Starter | $19 | 7 |
| Growth | $49 | 7 |
| Pro | $99 | 7 |

### Step 4: Test Credentials

In the "Notes to reviewer" section, add:

```
Test Store: uy288y-nx.myshopify.com (ORB Sports Cards)
The app is pre-installed with sample data.

To test:
1. Navigate to Apps → TradeUp in the admin
2. Dashboard shows metrics and quick actions
3. Members page has sample customers with different tiers
4. Trade-Ins page shows sample trade-in batches
5. Customer portal: [store].myshopify.com/apps/rewards

All billing uses Shopify's native billing API.
All GDPR webhooks are implemented and tested.

Contact: mike@cardflowlabs.com for any questions.
```

### Step 5: Submit

Click "Submit for review"

---

## Post-Submission

### Typical Timeline

- **Review:** 5-10 business days
- **Feedback:** Usually 1-3 items to fix
- **Resubmission:** 3-5 business days after fixes
- **Total:** ~2-3 weeks to approval

### Common Rejection Reasons (Avoid These)

1. ❌ Missing GDPR webhooks → ✅ You have all 3
2. ❌ Using REST API instead of GraphQL → ✅ You use GraphQL
3. ❌ Not using Shopify Billing → ✅ You use Shopify Billing
4. ❌ Broken OAuth flow → ✅ Yours is working
5. ❌ No privacy policy → ✅ You have one
6. ❌ Pricing in app icon → ✅ Your icon is clean
7. ❌ Test mode billing → ⚠️ **Change SHOPIFY_BILLING_TEST=false**

### If You Get Feedback

1. Read the entire feedback carefully
2. Fix ALL issues mentioned (don't skip any)
3. Reply with specific explanations of what you fixed
4. Resubmit

---

## Quick Reference

### Important URLs

| What | URL |
|------|-----|
| App (Production) | https://app.cardflowlabs.com |
| Privacy Policy | https://app.cardflowlabs.com/privacy-policy.html |
| Terms of Service | https://app.cardflowlabs.com/terms-of-service.html |
| Customer Portal | https://[store].myshopify.com/apps/rewards |
| Railway Dashboard | https://railway.app |
| Partner Dashboard | https://partners.shopify.com |

### Files You'll Need

```
docs/APP_STORE_LISTING.md      # All copy/text for listing
frontend/public/tradeup-icon-512.png
frontend/public/screenshots/screenshot-dashboard.png
frontend/public/screenshots/screenshot-members.png
frontend/public/screenshots/screenshot-trade-ins.png
frontend/public/screenshots/screenshot-quick-flip.png
```

### Support Contacts

- **App Support:** mike@orbsportscards.com
- **Privacy:** mike@orbsportscards.com
- **Developer:** mike@cardflowlabs.com

---

## Final Checklist Before Clicking Submit

- [ ] SHOPIFY_BILLING_TEST=false in Railway
- [ ] Emergency contact added in Partner Dashboard
- [ ] Demo video created and uploaded
- [ ] All 4 screenshots uploaded
- [ ] App icon uploaded
- [ ] Privacy policy URL verified (click it!)
- [ ] Terms of service URL verified (click it!)
- [ ] Support email tested
- [ ] Test store credentials in reviewer notes
- [ ] Read through entire listing one more time

**When all boxes are checked: SUBMIT!**

---

*Good luck! First submission rarely passes first try - expect feedback and iterate fast.*
