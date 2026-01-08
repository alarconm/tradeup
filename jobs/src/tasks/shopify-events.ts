/**
 * Shopify Event Handlers
 *
 * Handles Shopify webhooks as durable, async tasks.
 * These tasks are triggered by the Flask API when webhooks are received.
 *
 * Benefits:
 * - Webhooks are acknowledged immediately (Shopify 5s timeout)
 * - Processing happens durably in background
 * - Automatic retries on failure
 * - Full observability in Trigger.dev dashboard
 *
 * @see https://trigger.dev/docs/guides/background-jobs
 */

import { task, logger, schemaTask } from "@trigger.dev/sdk/v3";
import { z } from "zod";
import { callTradeUpAPI } from "../config/database.js";
import { AI_MODELS, AGENT_PRESETS } from "../config/ai-models.js";

// ============================================================================
// SCHEMAS
// ============================================================================

const OrderPayload = z.object({
  tenantId: z.number(),
  orderId: z.string(),
  shopifyOrderId: z.string(),
  customerId: z.string().nullable(),
  email: z.string().nullable(),
  totalPrice: z.number(),
  lineItems: z.array(z.object({
    productId: z.string(),
    variantId: z.string(),
    title: z.string(),
    quantity: z.number(),
    price: z.number(),
  })),
});

const CustomerPayload = z.object({
  tenantId: z.number(),
  shopifyCustomerId: z.string(),
  email: z.string(),
  firstName: z.string().nullable(),
  lastName: z.string().nullable(),
  tags: z.array(z.string()),
});

const TradeInPayload = z.object({
  tenantId: z.number(),
  tradeInId: z.number(),
  memberId: z.number(),
  items: z.array(z.object({
    name: z.string(),
    category: z.string().nullable(),
    quantity: z.number(),
    estimatedValue: z.number(),
  })),
  totalValue: z.number(),
  photoUrls: z.array(z.string()),
});

const MembershipPurchasePayload = z.object({
  tenantId: z.number(),
  orderId: z.string(),
  customerId: z.string().nullable(),
  email: z.string().nullable(),
  membershipProducts: z.array(z.object({
    productId: z.string(),
    variantId: z.string(),
    title: z.string(),
  })),
});

const CashbackPayload = z.object({
  tenantId: z.number(),
  orderId: z.string(),
  shopifyCustomerId: z.string(),
  totalPrice: z.number(),
});

const WelcomeNotificationPayload = z.object({
  tenantId: z.number(),
  memberId: z.number(),
});

// ============================================================================
// ORDER EVENTS
// ============================================================================

/**
 * Handle order creation - check for membership purchases, award cashback
 */
export const handleOrderCreated = task({
  id: "handle-order-created",
  retry: {
    maxAttempts: 3,
    factor: 2,
    minTimeoutInMs: 2000,
  },

  run: async (payload, { ctx }) => {
    const order = OrderPayload.parse(payload);

    logger.info("Processing order created", {
      tenantId: order.tenantId,
      orderId: order.orderId,
    });

    // Check if this order contains a membership product
    const membershipProducts = order.lineItems.filter(
      (item) => item.title.toLowerCase().includes("membership") ||
                item.title.toLowerCase().includes("tradeup")
    );

    if (membershipProducts.length > 0) {
      // Trigger membership enrollment
      await handleMembershipPurchase.trigger({
        tenantId: order.tenantId,
        orderId: order.orderId,
        customerId: order.customerId,
        email: order.email,
        membershipProducts,
      });
    }

    // Check if customer is a member for cashback
    if (order.customerId) {
      await processPurchaseCashback.trigger({
        tenantId: order.tenantId,
        orderId: order.orderId,
        shopifyCustomerId: order.customerId,
        totalPrice: order.totalPrice,
      });
    }

    return { processed: true, orderId: order.orderId };
  },
});

/**
 * Handle membership product purchase - enroll customer
 */
export const handleMembershipPurchase = schemaTask({
  id: "handle-membership-purchase",
  schema: MembershipPurchasePayload,
  retry: {
    maxAttempts: 3,
    minTimeoutInMs: 5000,
  },

  run: async ({ tenantId, orderId, customerId, email, membershipProducts }) => {

    logger.info("Processing membership purchase", {
      tenantId,
      orderId,
      productCount: membershipProducts.length,
    });

    // Call Flask API to handle enrollment
    const result = await callTradeUpAPI<{
      enrolled: boolean;
      memberId: number | null;
      tier: string | null;
      error: string | null;
    }>("/api/members/enroll-from-purchase", {
      method: "POST",
      body: {
        orderId,
        customerId,
        email,
        products: membershipProducts,
      },
      tenantId,
    });

    if (result.enrolled) {
      logger.info("Member enrolled from purchase", {
        memberId: result.memberId,
        tier: result.tier,
      });

      // Send welcome notification
      await sendWelcomeNotification.trigger({
        tenantId,
        memberId: result.memberId!,
      });
    } else {
      logger.warn("Membership enrollment failed", {
        orderId,
        error: result.error,
      });
    }

    return result;
  },
});

/**
 * Process purchase cashback for existing members
 */
export const processPurchaseCashback = schemaTask({
  id: "process-purchase-cashback",
  schema: CashbackPayload,
  retry: {
    maxAttempts: 3,
    minTimeoutInMs: 2000,
  },

  run: async ({ tenantId, orderId, shopifyCustomerId, totalPrice }) => {

    logger.info("Processing purchase cashback", {
      tenantId,
      orderId,
      totalPrice,
    });

    // Call Flask API to check membership and award cashback
    const result = await callTradeUpAPI<{
      awarded: boolean;
      amount: number | null;
      tier: string | null;
      cashbackRate: number | null;
      reason: string;
    }>("/api/cashback/award", {
      method: "POST",
      body: {
        orderId,
        shopifyCustomerId,
        totalPrice,
      },
      tenantId,
    });

    if (result.awarded) {
      logger.info("Cashback awarded", {
        amount: result.amount,
        tier: result.tier,
        cashbackRate: result.cashbackRate,
      });
    } else {
      logger.debug("No cashback awarded", { reason: result.reason });
    }

    return result;
  },
});

// ============================================================================
// CUSTOMER EVENTS
// ============================================================================

/**
 * Handle customer creation - check for auto-enrollment
 */
export const handleCustomerCreated = task({
  id: "handle-customer-created",
  retry: {
    maxAttempts: 2,
    minTimeoutInMs: 2000,
  },

  run: async (payload, { ctx }) => {
    const customer = CustomerPayload.parse(payload);

    logger.info("Processing customer created", {
      tenantId: customer.tenantId,
      email: customer.email,
    });

    // Check if auto-enrollment is enabled and customer qualifies
    const result = await callTradeUpAPI<{
      enrolled: boolean;
      memberId: number | null;
      reason: string;
    }>("/api/members/check-auto-enroll", {
      method: "POST",
      body: {
        shopifyCustomerId: customer.shopifyCustomerId,
        email: customer.email,
        firstName: customer.firstName,
        lastName: customer.lastName,
      },
      tenantId: customer.tenantId,
    });

    return result;
  },
});

/**
 * Handle customer update - sync tags with membership
 */
export const handleCustomerUpdated = task({
  id: "handle-customer-updated",

  run: async (payload, { ctx }) => {
    const customer = CustomerPayload.parse(payload);

    logger.info("Processing customer update", {
      tenantId: customer.tenantId,
      email: customer.email,
    });

    // Sync customer tags with TradeUp membership
    await callTradeUpAPI("/api/members/sync-customer", {
      method: "POST",
      body: {
        shopifyCustomerId: customer.shopifyCustomerId,
        tags: customer.tags,
      },
      tenantId: customer.tenantId,
    });

    return { synced: true };
  },
});

// ============================================================================
// TRADE-IN EVENTS
// ============================================================================

/**
 * Handle new trade-in submission
 * Note: Trade-in valuation is handled separately (e.g., via ORB integration)
 * This task handles the loyalty program aspects (bonus credits, tier tracking)
 */
export const handleTradeInSubmitted = task({
  id: "handle-trade-in-submitted",
  retry: {
    maxAttempts: 3,
    minTimeoutInMs: 5000,
  },

  run: async (payload, { ctx }) => {
    const tradeIn = TradeInPayload.parse(payload);

    logger.info("Processing trade-in for loyalty tracking", {
      tenantId: tradeIn.tenantId,
      tradeInId: tradeIn.tradeInId,
      memberId: tradeIn.memberId,
      totalValue: tradeIn.totalValue,
    });

    // Track trade-in activity for member insights
    // The actual valuation is handled externally (ORB, manual, etc.)
    await callTradeUpAPI("/api/trade-ins/track-activity", {
      method: "POST",
      body: {
        tradeInId: tradeIn.tradeInId,
        memberId: tradeIn.memberId,
        itemCount: tradeIn.items.length,
        totalValue: tradeIn.totalValue,
      },
      tenantId: tradeIn.tenantId,
    });

    return {
      processed: true,
      tradeInId: tradeIn.tradeInId,
    };
  },
});

// ============================================================================
// NOTIFICATION TASKS
// ============================================================================

/**
 * Send welcome notification to new member
 */
export const sendWelcomeNotification = schemaTask({
  id: "send-welcome-notification",
  schema: WelcomeNotificationPayload,
  retry: {
    maxAttempts: 3,
    minTimeoutInMs: 5000,
  },

  run: async ({ tenantId, memberId }) => {

    logger.info("Sending welcome notification", { tenantId, memberId });

    await callTradeUpAPI("/api/notifications/send", {
      method: "POST",
      body: {
        type: "welcome",
        memberId,
      },
      tenantId,
    });

    return { sent: true };
  },
});

// ============================================================================
// INDEX FILE EXPORT
// ============================================================================

// All tasks are automatically discovered by Trigger.dev from the tasks directory
