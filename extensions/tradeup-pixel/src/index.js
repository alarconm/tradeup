/**
 * TradeUp Loyalty Analytics Web Pixel
 *
 * Tracks loyalty program events for ROI measurement:
 * - tradeup_points_earned: Points earned from orders
 * - tradeup_reward_viewed: Customer views rewards page
 * - tradeup_reward_redeemed: Reward redemption
 * - tradeup_tier_displayed: Tier badge shown
 * - tradeup_referral_shared: Referral link shared
 *
 * Lightweight and performant - optimized for minimal impact on page load.
 */

import { register } from "@shopify/web-pixels-extension";

register(({ analytics, browser, settings, init }) => {
  // Configuration
  const ENDPOINT = settings.endpoint_url || "https://app.cardflowlabs.com/api/analytics/pixel";
  const DEBUG = settings.debug_mode === true;
  const ENABLE_CHECKOUT = settings.enable_checkout_tracking !== false;
  const ENABLE_PAGE = settings.enable_page_tracking !== false;

  // TradeUp metafield namespace
  const TRADEUP_NAMESPACE = "tradeup";

  // Extract shop domain from init data
  const shopDomain = init.data?.shop?.domain || "";

  /**
   * Lightweight event sender using sendBeacon for non-blocking requests
   * Falls back to fetch if sendBeacon unavailable
   */
  const sendEvent = async (eventName, payload) => {
    const event = {
      event: eventName,
      timestamp: new Date().toISOString(),
      shop: shopDomain,
      ...payload,
    };

    if (DEBUG) {
      console.log(`[TradeUp Pixel] ${eventName}:`, event);
    }

    try {
      const data = JSON.stringify(event);

      // Use sendBeacon for non-blocking, fire-and-forget delivery
      if (navigator.sendBeacon) {
        const blob = new Blob([data], { type: "application/json" });
        navigator.sendBeacon(ENDPOINT, blob);
      } else {
        // Fallback to fetch with keepalive
        fetch(ENDPOINT, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: data,
          keepalive: true,
        }).catch(() => {
          // Silent fail - analytics should never break the store
        });
      }
    } catch (e) {
      // Silent fail - never impact store performance
      if (DEBUG) {
        console.error("[TradeUp Pixel] Error:", e);
      }
    }
  };

  /**
   * Extract TradeUp metafields from customer data
   */
  const extractTradeUpData = (customer) => {
    if (!customer) return {};

    const data = {};

    // Look for TradeUp metafields
    if (customer.metafields) {
      for (const mf of customer.metafields) {
        if (mf.namespace === TRADEUP_NAMESPACE) {
          data[mf.key] = mf.value;
        }
      }
    }

    return data;
  };

  /**
   * Calculate points earned from order
   * Default: 1 point per dollar spent (can be customized via metafields)
   */
  const calculatePointsEarned = (order, tradeupData) => {
    const orderTotal = parseFloat(order.totalPrice?.amount || 0);
    const pointsMultiplier = parseFloat(tradeupData.points_multiplier || 1);
    const tierBonus = parseFloat(tradeupData.tier_bonus || 0);

    // Base points + tier bonus
    const basePoints = Math.floor(orderTotal * pointsMultiplier);
    const bonusPoints = Math.floor(basePoints * (tierBonus / 100));

    return {
      base: basePoints,
      bonus: bonusPoints,
      total: basePoints + bonusPoints,
    };
  };

  // ============================================================
  // CHECKOUT EVENTS - Points Earned
  // ============================================================

  if (ENABLE_CHECKOUT) {
    /**
     * Track when checkout is completed - points earned event
     */
    analytics.subscribe("checkout_completed", (event) => {
      const checkout = event.data?.checkout;
      if (!checkout) return;

      const customer = checkout.customer;
      const tradeupData = extractTradeUpData(customer);
      const points = calculatePointsEarned(checkout, tradeupData);

      sendEvent("tradeup_points_earned", {
        order_id: checkout.order?.id,
        order_number: checkout.order?.name,
        customer_id: customer?.id,
        customer_email: customer?.email,
        order_value: parseFloat(checkout.totalPrice?.amount || 0),
        currency: checkout.totalPrice?.currencyCode || "USD",
        points_earned: points.total,
        points_base: points.base,
        points_bonus: points.bonus,
        tier: tradeupData.tier_name || null,
        tier_id: tradeupData.tier_id || null,
        is_member: !!tradeupData.member_id,
        member_id: tradeupData.member_id || null,
        item_count: checkout.lineItems?.length || 0,
        discount_codes: checkout.discountCodes?.map(d => d.code) || [],
      });
    });

    /**
     * Track checkout started for funnel analysis
     */
    analytics.subscribe("checkout_started", (event) => {
      const checkout = event.data?.checkout;
      if (!checkout) return;

      const customer = checkout.customer;
      const tradeupData = extractTradeUpData(customer);

      // Only track if customer is a TradeUp member
      if (tradeupData.member_id) {
        sendEvent("tradeup_checkout_started", {
          checkout_id: checkout.token,
          customer_id: customer?.id,
          member_id: tradeupData.member_id,
          tier: tradeupData.tier_name || null,
          cart_value: parseFloat(checkout.totalPrice?.amount || 0),
          currency: checkout.totalPrice?.currencyCode || "USD",
          item_count: checkout.lineItems?.length || 0,
        });
      }
    });
  }

  // ============================================================
  // PAGE VIEW EVENTS - Reward Views, Tier Display
  // ============================================================

  if (ENABLE_PAGE) {
    /**
     * Track page views for rewards-related pages
     */
    analytics.subscribe("page_viewed", (event) => {
      const context = event.context;
      const url = context?.document?.location?.href || "";
      const pathname = context?.document?.location?.pathname || "";

      // Detect rewards/account pages
      const isRewardsPage =
        pathname.includes("/account") ||
        pathname.includes("/rewards") ||
        pathname.includes("/loyalty") ||
        pathname.includes("/points") ||
        url.includes("tradeup");

      if (isRewardsPage) {
        sendEvent("tradeup_reward_viewed", {
          page_url: url,
          page_path: pathname,
          page_title: context?.document?.title || "",
          referrer: context?.document?.referrer || "",
        });
      }
    });
  }

  // ============================================================
  // CUSTOM EVENTS - Tier Display, Reward Redemption, Referral
  // ============================================================

  /**
   * Listen for custom TradeUp events fired from theme blocks
   * Theme blocks use: browser.sendEvent("tradeup_*", data)
   */

  // Tier badge displayed (fired from credit-badge.liquid or similar)
  analytics.subscribe("tradeup_tier_displayed", (event) => {
    sendEvent("tradeup_tier_displayed", {
      tier_name: event.customData?.tier_name,
      tier_id: event.customData?.tier_id,
      member_id: event.customData?.member_id,
      points_balance: event.customData?.points_balance,
      credit_balance: event.customData?.credit_balance,
      page_url: event.context?.document?.location?.href,
    });
  });

  // Reward redeemed (fired from rewards UI)
  analytics.subscribe("tradeup_reward_redeemed", (event) => {
    sendEvent("tradeup_reward_redeemed", {
      reward_id: event.customData?.reward_id,
      reward_name: event.customData?.reward_name,
      reward_type: event.customData?.reward_type,
      points_spent: event.customData?.points_spent,
      reward_value: event.customData?.reward_value,
      member_id: event.customData?.member_id,
      customer_id: event.customData?.customer_id,
    });
  });

  // Referral link shared (fired from refer-friend.liquid)
  analytics.subscribe("tradeup_referral_shared", (event) => {
    sendEvent("tradeup_referral_shared", {
      referral_code: event.customData?.referral_code,
      share_method: event.customData?.share_method, // 'copy', 'email', 'facebook', 'twitter', etc.
      member_id: event.customData?.member_id,
      customer_id: event.customData?.customer_id,
      page_url: event.context?.document?.location?.href,
    });
  });

  // Member enrolled (fired when new member signs up)
  analytics.subscribe("tradeup_member_enrolled", (event) => {
    sendEvent("tradeup_member_enrolled", {
      member_id: event.customData?.member_id,
      customer_id: event.customData?.customer_id,
      tier_name: event.customData?.tier_name,
      referral_code: event.customData?.referral_code,
      signup_source: event.customData?.signup_source,
    });
  });

  // ============================================================
  // PRODUCT EVENTS - Track engagement with trade-in eligible items
  // ============================================================

  /**
   * Track when customers view products (for trade-in interest)
   */
  analytics.subscribe("product_viewed", (event) => {
    const product = event.data?.productVariant?.product;
    if (!product) return;

    // Check if product has trade-in metafields
    const hasTradeIn = product.metafields?.some(
      mf => mf.namespace === TRADEUP_NAMESPACE && mf.key === "trade_in_eligible"
    );

    if (hasTradeIn) {
      sendEvent("tradeup_trade_in_product_viewed", {
        product_id: product.id,
        product_title: product.title,
        product_type: product.type,
        product_vendor: product.vendor,
        variant_id: event.data?.productVariant?.id,
        variant_title: event.data?.productVariant?.title,
        price: parseFloat(event.data?.productVariant?.price?.amount || 0),
        currency: event.data?.productVariant?.price?.currencyCode || "USD",
      });
    }
  });

  // ============================================================
  // CART EVENTS - Track loyalty program influence on cart
  // ============================================================

  /**
   * Track items added to cart by loyalty members
   */
  analytics.subscribe("product_added_to_cart", (event) => {
    // This event helps measure if loyalty members shop more
    const cartLine = event.data?.cartLine;
    if (!cartLine) return;

    sendEvent("tradeup_cart_add", {
      product_id: cartLine.merchandise?.product?.id,
      product_title: cartLine.merchandise?.product?.title,
      variant_id: cartLine.merchandise?.id,
      quantity: cartLine.quantity,
      price: parseFloat(cartLine.cost?.totalAmount?.amount || 0),
      currency: cartLine.cost?.totalAmount?.currencyCode || "USD",
    });
  });

  if (DEBUG) {
    console.log("[TradeUp Pixel] Initialized", {
      endpoint: ENDPOINT,
      shop: shopDomain,
      checkout_tracking: ENABLE_CHECKOUT,
      page_tracking: ENABLE_PAGE,
    });
  }
});
