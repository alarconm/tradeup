# AI Agent Architecture for TradeUp

## Vision

Build an AI-native platform where agents handle:
- 80% of customer interactions
- 100% of pricing lookups
- 100% of cashback calculations
- Real-time inventory tracking
- Proactive alerts and recommendations

---

## Agent Types

### 1. Pricing Agent

**Purpose**: Instant, accurate card pricing from TCGPlayer

**Inputs**:
- Card name + set + collector number
- Product photos (OCR + identification)
- Customer's handwritten lists

**Outputs**:
- Market price (not lowest listing)
- Price confidence score
- Price history trend
- Suggested trade-in value

**Implementation**:
```python
class PricingAgent:
    """
    Autonomous agent for card pricing.
    Uses browser automation to fetch real TCGPlayer market prices.
    """

    def price_card(self, card_info: dict) -> dict:
        """
        Get market price for a single card.

        Args:
            card_info: {
                'name': 'Charizard ex',
                'set': 'Obsidian Flames',
                'collector_number': '223',
                'variant': 'Full Art'
            }

        Returns:
            {
                'market_price': 45.99,
                'currency': 'USD',
                'confidence': 0.95,
                'source': 'tcgplayer.com',
                'last_updated': '2026-01-04T12:00:00Z'
            }
        """
        pass

    def price_list(self, cards: list) -> dict:
        """
        Batch price multiple cards.
        Parallelizes lookups for speed.
        """
        pass

    def price_from_image(self, image_path: str) -> list:
        """
        Identify cards from photo and price them.
        Uses Claude vision to identify cards.
        """
        pass
```

**MCP Server**: Could expose as MCP tool for Claude Code integration

---

### 2. Trade-In Agent

**Purpose**: Process trade-in requests autonomously

**Workflow**:
1. Customer submits list/photos
2. Agent identifies all cards
3. Agent prices each card
4. Agent calculates tier-based trade-in value
5. Agent generates offer
6. Human reviews (optional) or auto-approves under threshold

**Implementation**:
```python
class TradeInAgent:
    """
    Handles the full trade-in workflow.
    """

    def __init__(self, pricing_agent: PricingAgent, tier_config: dict):
        self.pricer = pricing_agent
        self.tiers = tier_config

    def process_trade_in(self, member_id: int, items: list) -> dict:
        """
        Process a complete trade-in submission.

        Returns:
            {
                'items': [...],
                'total_market_value': 150.00,
                'trade_in_rate': 0.75,  # Gold tier
                'offer_amount': 112.50,
                'requires_review': False,  # Under $100 threshold
                'expires_at': '2026-01-11T00:00:00Z'
            }
        """
        # Price all items
        prices = self.pricer.price_list(items)

        # Get member tier
        member = self.get_member(member_id)
        rate = self.tiers[member.tier]['trade_in_rate']

        # Calculate offer
        total = sum(p['market_price'] for p in prices)
        offer = total * rate

        # Check if human review needed
        requires_review = any([
            total > 500,  # High value
            any(p['confidence'] < 0.8 for p in prices),  # Uncertain pricing
            any(p['market_price'] > 100 for p in prices)  # Expensive singles
        ])

        return {
            'items': prices,
            'total_market_value': total,
            'trade_in_rate': rate,
            'offer_amount': offer,
            'requires_review': requires_review
        }
```

---

### 3. Cashback Monitor Agent

**Purpose**: Track purchases and issue cashback automatically

**Workflow**:
1. Listen to Shopify webhooks for order completions
2. Check if customer is a TradeUp member
3. Calculate cashback based on tier rate
4. Issue store credit automatically

**Implementation**:
```python
class CashbackMonitorAgent:
    """
    Monitors purchases and issues cashback rewards.
    Runs as background process.
    """

    def on_order_paid(self, order: dict):
        """
        Handle order webhook.
        Calculate and issue cashback for eligible members.
        """
        customer_id = order.get('customer', {}).get('id')
        if not customer_id:
            return

        # Find member by Shopify customer ID
        member = self.find_member_by_shopify_id(customer_id)
        if not member:
            return

        # Calculate cashback
        order_total = float(order.get('total_price', 0))
        cashback_rate = member.tier.bonus_rate
        cashback_amount = order_total * cashback_rate

        if cashback_amount > 0:
            self.issue_store_credit(
                member.shopify_customer_id,
                cashback_amount,
                f"Cashback - Order #{order['order_number']}"
            )

            # Notify member
            self.send_cashback_notification(member, cashback_amount, order)
```

---

### 4. Member Support Agent

**Purpose**: 24/7 customer support via chat

**Capabilities**:
- Answer FAQs about membership tiers
- Check trade-in status
- Explain cashback calculations
- Escalate to human when needed

**Implementation**:
```python
class MemberSupportAgent:
    """
    Conversational AI agent for member support.
    Uses Claude API with tool access.
    """

    SYSTEM_PROMPT = """
    You are a helpful assistant for TradeUp membership program.

    You can help members with:
    - Checking their membership tier and benefits
    - Explaining trade-in rates and cashback
    - Tracking pending trade-ins
    - Answering questions about store credit

    Always be friendly and helpful. If you can't help with something,
    offer to connect them with a human team member.
    """

    def __init__(self):
        self.tools = [
            self.get_member_status,
            self.get_trade_in_history,
            self.check_store_credit,
            self.explain_tier_benefits,
            self.escalate_to_human
        ]

    def chat(self, member_id: int, message: str) -> str:
        """
        Process a chat message from a member.
        """
        # Get member context
        member = self.get_member(member_id)

        # Call Claude with tools
        response = claude.messages.create(
            model="claude-sonnet-4-20250514",
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
            tools=self.tools,
            context={"member": member.to_dict()}
        )

        return response.content
```

---

### 5. Analytics Agent

**Purpose**: Proactive insights and recommendations

**Capabilities**:
- Identify at-risk members (low engagement)
- Spot trends in trade-in patterns
- Recommend tier upgrades
- Generate weekly reports

**Implementation**:
```python
class AnalyticsAgent:
    """
    Generates insights from membership and trade-in data.
    """

    def generate_weekly_insights(self, tenant_id: int) -> dict:
        """
        Generate weekly analytics for a shop.
        """
        return {
            'member_growth': self.calculate_growth(tenant_id),
            'trade_in_volume': self.calculate_volume(tenant_id),
            'cashback_issued': self.calculate_cashback_total(tenant_id),
            'at_risk_members': self.identify_at_risk(tenant_id),
            'upgrade_candidates': self.find_upgrade_candidates(tenant_id),
            'recommendations': self.generate_recommendations(tenant_id)
        }

    def find_upgrade_candidates(self, tenant_id: int) -> list:
        """
        Find members who would benefit from upgrading.

        Criteria:
        - Trade-in volume exceeds tier threshold
        - Cashback savings would pay for upgrade
        - Consistent activity over 3+ months
        """
        pass
```

---

## Agent Orchestration

### Event-Driven Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Event Bus (Redis/SQS)                    │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ Pricing Agent │   │ Trade-In Agent│   │ Cashback      │
│               │   │               │   │ Monitor       │
└───────────────┘   └───────────────┘   └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                              ▼
                    ┌───────────────┐
                    │   Database    │
                    │  (PostgreSQL) │
                    └───────────────┘
```

### Event Types

```python
EVENTS = {
    'trade_in.submitted': TradeInAgent,
    'trade_in.approved': CashbackMonitorAgent,
    'order.paid': CashbackMonitorAgent,
    'member.created': MemberSupportAgent,
    'member.tier_changed': AnalyticsAgent,
    'pricing.requested': PricingAgent,
    'chat.message': MemberSupportAgent,
    'daily.analytics': AnalyticsAgent
}
```

---

## MCP Server Integration

Expose agents as MCP tools for Claude Code integration:

```json
{
  "name": "tradeup-agents",
  "version": "1.0.0",
  "tools": [
    {
      "name": "price_card",
      "description": "Get TCGPlayer market price for a card",
      "inputSchema": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "set": {"type": "string"},
          "collector_number": {"type": "string"}
        }
      }
    },
    {
      "name": "process_trade_in",
      "description": "Process a trade-in submission for a member",
      "inputSchema": {...}
    },
    {
      "name": "check_cashback_status",
      "description": "Check cashback reward eligibility",
      "inputSchema": {...}
    }
  ]
}
```

---

## Implementation Phases

### Phase 1: Pricing Agent (Week 1)
- [ ] Playwright browser automation for TCGPlayer
- [ ] Card identification from text
- [ ] Price caching (Redis)
- [ ] API endpoint

### Phase 2: Trade-In Agent (Week 2)
- [ ] Integration with Pricing Agent
- [ ] Tier-based calculation
- [ ] Auto-approval rules
- [ ] Offer generation

### Phase 3: Cashback Monitor (Week 3)
- [ ] Webhook listeners
- [ ] Order matching logic
- [ ] Cashback calculation
- [ ] Store credit integration

### Phase 4: Support & Analytics (Week 4)
- [ ] Claude-powered chat
- [ ] Analytics dashboard
- [ ] Weekly email reports
- [ ] Recommendation engine

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Agent Framework | Python + Claude API |
| Browser Automation | Playwright |
| Event Bus | Redis Pub/Sub |
| Database | PostgreSQL |
| Cache | Redis |
| API | Flask |
| MCP Server | TypeScript |

---

## Cost Estimates

| Agent | API Calls/Day | Cost/Month |
|-------|---------------|------------|
| Pricing | ~100 | $5 (browser, no LLM) |
| Trade-In | ~20 | $10 (Claude Haiku) |
| Support | ~50 | $25 (Claude Sonnet) |
| Analytics | 1 | $5 (Claude Sonnet) |
| **Total** | | **~$45/month** |

---

*Last updated: January 2026*
