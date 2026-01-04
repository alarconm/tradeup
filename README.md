# Quick Flip Membership Platform

A SaaS platform for card shops offering membership programs with **Quick Flip Bonus** - a unique profit-sharing feature that rewards members when their traded-in items sell quickly.

## What is Quick Flip Bonus?

When a member trades in cards at your shop:
1. Member receives **70% of market value** as store credit immediately
2. Shop lists the items for sale
3. If an item sells within **7 days**, the member gets a **bonus** (% of profit as store credit)
4. Bonus rate varies by membership tier:
   - **Silver**: 10% of profit
   - **Gold**: 20% of profit
   - **Platinum**: 30% of profit

### Example
- Gold member trades in a Charizard for $70 store credit
- Shop lists it at $100, sells for $95 in 5 days
- Profit = $95 - $70 = $25
- Bonus = $25 × 20% = **$5 extra store credit**
- Member effectively got $75 for the card!

## Features

- **Membership Management**: Silver, Gold, Platinum tiers with configurable benefits
- **Trade-In Tracking**: Batch processing, item-level tracking
- **Quick Flip Bonus Engine**: Automatic bonus calculation when items sell fast
- **Shopify Integration**: Webhooks, store credit, customer tagging
- **Employee Dashboard**: Manage members, trade-ins, bonuses
- **Multi-Tenant Ready**: Built for SaaS from day one

## Tech Stack

- **Backend**: Python/Flask
- **Database**: PostgreSQL
- **E-commerce**: Shopify Admin API (GraphQL)
- **Deployment**: Docker, Railway/Render

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/alarconm/quick-flip.git
cd quick-flip
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Initialize Database

```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### 4. Run Development Server

```bash
python run.py
```

### Using Docker

```bash
docker-compose up -d
```

## API Endpoints

### Members
- `GET /api/members` - List members
- `POST /api/members` - Create member
- `GET /api/members/<id>` - Get member details
- `GET /api/members/tiers` - List membership tiers

### Trade-Ins
- `POST /api/trade-ins` - Create trade-in batch
- `POST /api/trade-ins/<id>/items` - Add items to batch
- `PUT /api/trade-ins/items/<id>/listed` - Mark item as listed

### Bonuses
- `GET /api/bonuses/pending` - Get pending bonuses
- `POST /api/bonuses/process` - Process and issue bonuses
- `GET /api/bonuses/history` - Bonus transaction history

### Webhooks
- `POST /webhook/shopify/<tenant>/order-paid` - Handle sales
- `POST /webhook/shopify/<tenant>/product-created` - Capture listings

## Shopify Integration

### Required Webhooks
Register these webhooks in Shopify:
- `orders/paid` → `/webhook/shopify/{tenant}/order-paid`
- `products/create` → `/webhook/shopify/{tenant}/product-created`
- `refunds/create` → `/webhook/shopify/{tenant}/order-refunded`

### Product Tagging
When listing trade-in items, add the member's tag:
- Tag format: `QF{member_number}` (e.g., `QF1001`)
- This links the product to the member for bonus tracking

## License

Proprietary - ORB Sports Cards

## Contact

- **Repository**: https://github.com/alarconm/quick-flip
- **ORB Sports Cards**: https://orbsportscards.com
