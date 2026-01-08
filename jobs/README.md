# TradeUp Jobs - Background Task Infrastructure

Durable, scalable background jobs for TradeUp powered by [Trigger.dev](https://trigger.dev).

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TRADEUP JOB ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────────┐    ┌──────────────────────────────────────────┐  │
│   │  Schedules  │    │         Trigger.dev Cloud                 │  │
│   │  (Cron)     │───▶│  • Durable execution                      │  │
│   └─────────────┘    │  • Auto-scaling (0 to 1000s)              │  │
│                      │  • Retries with backoff                    │  │
│   ┌─────────────┐    │  • Observability dashboard                 │  │
│   │  Webhooks   │───▶│                                           │  │
│   │  (Shopify)  │    └──────────────────────────────────────────┘  │
│   └─────────────┘              │                                   │
│                                ▼                                   │
│                      ┌──────────────────────────────────────────┐  │
│                      │       Flask API (Internal)                │  │
│                      │  /api/scheduled-tasks/*                   │  │
│                      │  • Batch processing endpoints             │  │
│                      │  • Idempotent credit issuance             │  │
│                      └──────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
cd jobs
npm install
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values
```

Required environment variables:
- `TRIGGER_SECRET_KEY` - From Trigger.dev dashboard
- `TRADEUP_API_URL` - Flask backend URL
- `DATABASE_URL` - PostgreSQL connection string

### 3. Start Development

```bash
npm run dev
```

This connects to Trigger.dev and registers your tasks.

### 4. Deploy

```bash
npm run deploy
```

## Tasks

### Scheduled Tasks

| Task | Schedule | Description |
|------|----------|-------------|
| `monthly-credits-schedule` | 1st of month, 6 AM UTC | Distributes monthly credits to all tenants |
| `credit-expiration-schedule` | Daily, midnight UTC | Expires old credits |
| `expiration-warning-schedule` | Daily, 9 AM UTC | Sends 7-day warning emails |

### Event Tasks

| Task | Trigger | Description |
|------|---------|-------------|
| `handle-order-created` | Shopify webhook | Processes memberships, cashback |
| `handle-customer-created` | Shopify webhook | Auto-enrollment check |
| `handle-trade-in-submitted` | TradeUp API | AI valuation (Phase 2) |

## Multi-Tenant Processing

Jobs are designed for scale:

```
monthly-credits-schedule (cron)
    │
    └──▶ processTenantMonthlyCredits (per tenant, isolated)
              │
              └──▶ processMonthlyCreditsBatch (100 members at a time)
                        │
                        └──▶ issueMemberMonthlyCredit (individual, idempotent)
```

**Benefits:**
- Tenant isolation: One tenant failure doesn't affect others
- Batch processing: Memory efficient for large member counts
- Checkpointing: Resume from where it left off if interrupted
- Idempotency: Safe to retry without double-crediting

## AI Agents ✅

Multi-agent system for intelligent loyalty program management.

### Models

```typescript
// src/config/ai-models.ts
export const AI_MODELS = {
  ORCHESTRATOR: "claude-opus-4-5-20251101",  // Strategic planning
  SUBAGENT: "claude-sonnet-4-5-20250929",    // Fast execution
};
```

### Agent Hierarchy

| Agent | Purpose | Model | Use Case |
|-------|---------|-------|----------|
| **Orchestrator** | Multi-agent coordination | Opus 4.5 | Complex strategic goals |
| **Insights Agent** | Member behavior analysis | Sonnet 4.5 | Analytics, recommendations |
| **Engagement Agent** | Churn prevention | Sonnet 4.5 | Campaigns, rescue plans |

### Architecture

```
Strategic Goal ("Reduce churn 20%")
    │
    └──▶ Orchestrator (Opus 4.5)
              │
              ├──▶ get_tenant_overview
              ├──▶ get_historical_trends
              │
              ├──▶ Insights Agent (Sonnet 4.5)
              │         ├──▶ get_purchase_history
              │         ├──▶ get_credit_activity
              │         ├──▶ get_tier_analysis
              │         └──▶ get_engagement_metrics
              │
              └──▶ Engagement Agent (Sonnet 4.5)
                        ├──▶ get_at_risk_members
                        ├──▶ get_expiring_credits
                        └──▶ get_campaign_performance
              │
              └──▶ Strategic Plan with KPIs
```

### Scheduled AI Tasks

| Task | Schedule | Description |
|------|----------|-------------|
| `weekly-churn-prevention-scan` | Monday 9 AM | Identifies at-risk members |
| `daily-expiration-rescue` | Daily 10 AM | Saves expiring credits |
| `monthly-strategic-review` | 1st of month | Full loyalty program analysis |

### On-Demand AI Tasks

| Task | Input | Output |
|------|-------|--------|
| `analyze-member-insights` | Member ID | Behavior analysis, recommendations |
| `analyze-segment` | Segment filters | Segment-wide insights |
| `plan-campaign` | Campaign goal | Multi-channel campaign plan |
| `plan-strategic-goal` | Natural language goal | Comprehensive execution plan |

### Example: Strategic Goal

```typescript
// Admin asks: "Increase Gold tier retention by 25%"
await planStrategicGoal.trigger({
  tenantId: 1,
  goal: "Increase Gold tier retention by 25%",
  timeline: "Q1 2026",
  targetSegment: "Gold tier",
});

// Orchestrator returns:
// - Current state analysis
// - 3-phase execution plan
// - Specific campaigns and offers
// - KPIs with targets
// - Executive summary
```

### Key Features

- **Multi-Agent Coordination**: Opus 4.5 orchestrates Sonnet 4.5 subagents
- **Durable Execution**: Trigger.dev retries on failure
- **Scheduled Intelligence**: Proactive churn prevention
- **Natural Language Goals**: "Reduce churn" → Actionable plan

## Monitoring

View all job executions in the [Trigger.dev Dashboard](https://cloud.trigger.dev):

- Real-time execution logs
- Retry history
- Error tracking
- Performance metrics

## Development

### Type Check

```bash
npm run typecheck
```

### Add New Task

1. Create file in `src/tasks/`
2. Export task function
3. Add to `src/tasks/index.ts`
4. Run `npm run dev` to register

### Testing Tasks Locally

Tasks can be triggered manually from the Trigger.dev dashboard or via API.

## Deployment

### Railway (Recommended)

```bash
# Add to railway.json
{
  "jobs": {
    "build": "cd jobs && npm install && npm run deploy"
  }
}
```

### Manual

```bash
cd jobs
npm install
TRIGGER_SECRET_KEY=xxx npm run deploy
```

## FAQ

**Q: Why not Celery?**
A: Trigger.dev provides durable execution, auto-scaling, and a dashboard without managing Redis/RabbitMQ infrastructure.

**Q: How does it handle failures?**
A: Automatic retries with exponential backoff. Failed jobs go to dead letter queue with full error context.

**Q: What about rate limits?**
A: Batch processing and tenant isolation prevent overwhelming the database or Shopify API.

**Q: How do I monitor jobs?**
A: Trigger.dev dashboard shows real-time execution, logs, and metrics.
