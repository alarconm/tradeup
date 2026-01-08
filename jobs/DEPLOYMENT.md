# TradeUp Jobs - Deployment Checklist

## Overview

To deploy the Trigger.dev jobs infrastructure, you need:
1. Trigger.dev account and project
2. Environment variables configured
3. Flask backend endpoints (many already exist, some need adding)
4. Shopify webhooks configured

---

## Step 1: Trigger.dev Setup

### Create Account & Project
1. Go to [trigger.dev](https://trigger.dev) and sign up
2. Create a new project called "tradeup-jobs"
3. Copy your **Secret Key** from the project settings

### Install CLI
```bash
npm install -g @trigger.dev/cli
```

---

## Step 2: Environment Variables

Create `.env` in the `jobs/` directory:

```bash
# Trigger.dev (from step 1)
TRIGGER_SECRET_KEY=tr_dev_xxxxxxxxxxxxx

# Flask Backend
TRADEUP_API_URL=https://your-tradeup-backend.com
TRADEUP_API_KEY=your-internal-api-key

# Database (same as Flask)
DATABASE_URL=postgresql://user:pass@host:5432/tradeup

# AI Agents
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
```

---

## Step 3: Flask Backend Endpoints

### Already Implemented (verify these exist)
These are standard TradeUp endpoints that likely exist:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tenants/active` | GET | List active tenants |
| `/api/tenants/all` | GET | List all tenants |
| `/api/notifications/send` | POST | Send notification to member |
| `/api/members/enroll-from-purchase` | POST | Enroll member from Shopify order |
| `/api/cashback/award` | POST | Award purchase cashback |
| `/api/members/check-auto-enroll` | POST | Check auto-enrollment eligibility |
| `/api/members/sync-customer` | POST | Sync Shopify customer tags |

### Core Jobs - Need to Add
These endpoints are called by the scheduled credit tasks:

```python
# app/api/scheduled_tasks.py

@bp.route('/monthly-credits/eligible-batch', methods=['POST'])
def get_eligible_members_batch():
    """
    Get batch of members eligible for monthly credits.
    Input: { tenantId, cursor, batchSize, monthKey }
    Output: { members: [], nextCursor, hasMore }
    """
    pass

@bp.route('/monthly-credits/issue', methods=['POST'])
def issue_monthly_credit():
    """
    Issue monthly credit to single member (idempotent).
    Input: { memberId, monthKey }
    Output: { credited: bool, amount, reason }
    """
    pass

@bp.route('/monthly-credits/preview', methods=['GET'])
def preview_monthly_credits():
    """
    Preview what would be credited (dry run).
    Output: { processed, credited, total_amount, details[] }
    """
    pass

@bp.route('/expiration/process-batch', methods=['POST'])
def process_expiration_batch():
    """
    Expire credits in batch.
    Input: { cursor, batchSize }
    Output: { processed, expired, expiredAmount, errors, nextCursor, hasMore }
    """
    pass

@bp.route('/expiration/upcoming', methods=['GET'])
def get_upcoming_expirations():
    """
    Get members with credits expiring soon.
    Query: ?days=7
    Output: { members_with_expiring_credits, total_amount_expiring, members[] }
    """
    pass

@bp.route('/expiration/preview', methods=['GET'])
def preview_expirations():
    """
    Preview what would expire today (dry run).
    Output: { processed, expired_entries, members_affected, total_expired }
    """
    pass
```

### AI Agents - Add When Ready
These are for the AI-powered features (can skip initially):

**Insights Agent endpoints:**
- `POST /api/insights/member/{id}/purchases`
- `POST /api/insights/segment/purchases`
- `POST /api/insights/member/{id}/credits`
- `POST /api/insights/segment/credits`
- `POST /api/insights/member/{id}/tier`
- `POST /api/insights/segment/tiers`
- `POST /api/insights/member/{id}/engagement`
- `POST /api/insights/segment/engagement`
- `POST /api/insights/cohort-comparison`

**Engagement Agent endpoints:**
- `POST /api/engagement/at-risk`
- `POST /api/engagement/expiring-credits`
- `GET /api/engagement/member/{id}/history`
- `POST /api/engagement/campaigns`
- `POST /api/engagement/segment-size`

**Orchestrator endpoints:**
- `GET /api/tenants/overview`
- `POST /api/tenants/trends`

**AI result storage:**
- `POST /api/ai/churn-scan-results`
- `POST /api/ai/monthly-review`
- `POST /api/ai/strategic-plans`
- `POST /api/members/{id}/ai-insights`
- `POST /api/notifications/queue-rescue-campaign`

---

## Step 4: Deploy Jobs

### Local Development
```bash
cd jobs
npm install
npm run dev
```

This connects to Trigger.dev and registers tasks.

### Production Deploy
```bash
cd jobs
npm run deploy
```

---

## Step 5: Shopify Webhooks

Configure Shopify to send webhooks to Trigger.dev (via your Flask backend):

| Shopify Event | Your Endpoint | Triggers Task |
|---------------|---------------|---------------|
| `orders/create` | `/webhooks/shopify/order` | `handle-order-created` |
| `customers/create` | `/webhooks/shopify/customer` | `handle-customer-created` |
| `customers/update` | `/webhooks/shopify/customer` | `handle-customer-updated` |

Your Flask webhook handler should call Trigger.dev:

```python
import requests

def trigger_task(task_id: str, payload: dict):
    """Trigger a Trigger.dev task from Flask"""
    response = requests.post(
        f"https://api.trigger.dev/v3/tasks/{task_id}/trigger",
        headers={
            "Authorization": f"Bearer {TRIGGER_SECRET_KEY}",
            "Content-Type": "application/json"
        },
        json=payload
    )
    return response.json()

# In your Shopify webhook handler:
@bp.route('/webhooks/shopify/order', methods=['POST'])
def handle_shopify_order():
    data = request.json
    trigger_task("handle-order-created", {
        "tenantId": get_tenant_id(),
        "orderId": data['id'],
        # ... map Shopify data to task payload
    })
    return "", 200
```

---

## Step 6: Verify Deployment

### Check Tasks Registered
Go to [Trigger.dev Dashboard](https://cloud.trigger.dev) and verify:
- [ ] `monthly-credits-schedule` shows up
- [ ] `credit-expiration-schedule` shows up
- [ ] All event tasks are registered

### Test Manually
From the Trigger.dev dashboard, you can manually trigger tasks:
1. Go to Tasks → `trigger-monthly-credits-manual`
2. Click "Test"
3. Enter payload: `{ "tenantId": 1, "dryRun": true }`
4. Check logs for results

### Monitor Scheduled Tasks
- Monthly credits: Runs 1st of month at 6 AM UTC
- Credit expiration: Runs daily at midnight UTC
- Expiration warnings: Runs daily at 9 AM UTC

---

## Phased Rollout Recommendation

### Phase 1: Core Jobs (Start Here)
1. Set up Trigger.dev
2. Implement the 6 scheduled-tasks endpoints
3. Deploy and test `monthly-credits` and `credit-expiration`
4. Monitor for 1 month

### Phase 2: Shopify Integration
1. Update Shopify webhook handlers to trigger tasks
2. Test membership purchases, cashback
3. Monitor for 2 weeks

### Phase 3: AI Agents
1. Add AI analytics endpoints
2. Enable AI scheduled tasks
3. Test with `dryRun: true` first

---

## Troubleshooting

### Tasks Not Running
- Check TRIGGER_SECRET_KEY is correct
- Verify tasks are deployed: `npm run deploy`
- Check Trigger.dev dashboard for errors

### API Errors
- Check TRADEUP_API_URL is accessible from Trigger.dev
- Verify X-Tenant-ID header is being passed
- Check Flask logs for endpoint errors

### AI Tasks Failing
- Verify ANTHROPIC_API_KEY is set
- Check token usage in Anthropic dashboard
- AI tasks need the analytics endpoints implemented

---

## Cost Estimation

### Trigger.dev
- Free tier: 1,000 task runs/month
- Pro: $20/month for 10,000 runs

### Anthropic (AI Agents)
- Sonnet 4.5: ~$3/million input tokens, $15/million output
- Opus 4.5: ~$15/million input, $75/million output
- Estimated: $10-50/month depending on usage
