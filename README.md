# TradeUp Membership Platform

A Shopify app for card shops offering membership programs, trade-in tracking, and store credit management.

## Features

- **Membership Tiers**: Silver, Gold, Platinum tiers with configurable benefits
- **Trade-In Tracking**: Batch processing, item-level tracking
- **Cashback Rewards**: Members earn bonus store credit on purchases
- **Shopify Integration**: Webhooks, store credit via Shopify's native system
- **Store Credit Events**: Run promotional credit campaigns for targeted customers
- **Multi-Tenant Ready**: Built for SaaS from day one

## Tech Stack

- **Backend**: Python/Flask
- **Frontend**: React/TypeScript (Vite)
- **Database**: PostgreSQL
- **E-commerce**: Shopify Admin API (GraphQL)
- **Deployment**: Docker, Railway

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/alarconm/tradeup.git
cd tradeup
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
- `GET /api/membership/tiers` - List membership tiers

### Trade-Ins
- `POST /api/trade-ins` - Create trade-in batch
- `POST /api/trade-ins/<id>/items` - Add items to batch
- `PUT /api/trade-ins/<id>/complete` - Complete batch and issue credit

### Store Credit
- `GET /api/store-credit/balance` - Get member's balance
- `POST /api/store-credit/add` - Issue store credit
- `GET /api/store-credit/history` - Transaction history

### Webhooks
- `POST /webhook/shopify/<tenant>/order-paid` - Handle sales for cashback
- `POST /webhook/shopify/<tenant>/app-installed` - Handle app installation

## Shopify Integration

### Required Webhooks
Register these webhooks in Shopify:
- `orders/paid` → `/webhook/shopify/{tenant}/order-paid`
- `app/installed` → `/webhook/shopify/{tenant}/app-installed`
- `customers/data_request` → `/webhook/shopify/{tenant}/customer-data-request`

### Customer Tagging
Members are tagged in Shopify with:
- `tu-member` - Indicates TradeUp member
- `tu-tier-{tier}` - Their tier level (e.g., `tu-tier-gold`)

## License

Proprietary - Cardflow Labs

## Contact

- **Repository**: https://github.com/alarconm/tradeup
- **Support**: support@cardflowlabs.com
