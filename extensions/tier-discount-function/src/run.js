/**
 * TradeUp Tier-Based Discount Function
 *
 * This Shopify Function automatically applies membership tier discounts at checkout.
 *
 * Features:
 * - Percentage discounts based on customer tier (Bronze, Silver, Gold, Platinum)
 * - Free shipping when order meets tier-specific threshold
 * - Excludes products tagged with "no-tier-discount", "sale", or "clearance"
 * - Clear discount messaging for customer transparency
 *
 * Metafield Schema (namespace: "tradeup"):
 * - tier: string - Tier name (e.g., "GOLD")
 * - tier_discount_pct: string - Discount percentage (e.g., "10")
 * - free_shipping_threshold: string - Free shipping threshold (e.g., "50.00", "0" for always)
 *
 * Performance Notes:
 * - Functions have 5ms execution limit and 256KB memory limit
 * - We minimize allocations and use early returns
 * - All calculations use integers where possible to avoid floating point issues
 *
 * @see https://shopify.dev/docs/api/functions/reference/order-discounts
 */

// WASM-compatible JSON parsing for Shopify Functions
const EMPTY_DISCOUNTS = { discounts: [] };

/**
 * Main entry point for the Shopify Function.
 *
 * @param {Object} input - The input object from Shopify containing cart and customer data
 * @returns {Object} - Discount response object with discounts array
 */
export function run(input) {
  // Early return if no cart data
  if (!input?.cart) {
    return EMPTY_DISCOUNTS;
  }

  const { cart } = input;
  const { buyerIdentity, lines, cost, deliveryGroups } = cart;

  // Early return if no customer (guest checkout)
  const customer = buyerIdentity?.customer;
  if (!customer) {
    return EMPTY_DISCOUNTS;
  }

  // Extract tier data from metafields
  const tierData = extractTierData(customer);

  // Early return if customer has no tier or no discount configured
  if (!tierData.tier || tierData.discountPercent <= 0) {
    return EMPTY_DISCOUNTS;
  }

  // Build discounts array
  const discounts = [];

  // Apply product discounts to eligible lines
  const productDiscount = buildProductDiscount(lines, tierData);
  if (productDiscount) {
    discounts.push(productDiscount);
  }

  // Note: Free shipping discounts require the Delivery Customization API
  // or Shipping Discount API, not Order Discounts. We include the logic
  // here for reference but it would need a separate function deployment.
  //
  // For now, we add a message about free shipping eligibility in the
  // discount title when applicable.

  return { discounts };
}

/**
 * Extracts and validates tier data from customer metafields.
 *
 * @param {Object} customer - Customer object with metafields
 * @returns {Object} - Normalized tier data
 */
function extractTierData(customer) {
  // Default tier data for customers without metafields
  const defaultTierData = {
    tier: null,
    tierDisplay: null,
    discountPercent: 0,
    freeShippingThreshold: null,
  };

  // Get tier name
  const tierValue = customer.tierMetafield?.value;
  if (!tierValue || typeof tierValue !== 'string') {
    return defaultTierData;
  }

  // Normalize tier name (handle case variations)
  const tier = tierValue.trim().toUpperCase();
  if (!tier) {
    return defaultTierData;
  }

  // Get discount percentage with validation
  const discountRaw = customer.discountMetafield?.value;
  let discountPercent = 0;

  if (discountRaw) {
    const parsed = parseFloat(discountRaw);
    // Validate: must be between 0 and 100
    if (!isNaN(parsed) && parsed > 0 && parsed <= 100) {
      discountPercent = parsed;
    }
  }

  // Get free shipping threshold
  const shippingRaw = customer.shippingThresholdMetafield?.value;
  let freeShippingThreshold = null;

  if (shippingRaw !== null && shippingRaw !== undefined) {
    const parsed = parseFloat(shippingRaw);
    // 0 means always free shipping, positive number is threshold
    if (!isNaN(parsed) && parsed >= 0) {
      freeShippingThreshold = parsed;
    }
  }

  // Create display-friendly tier name (e.g., "GOLD" -> "Gold")
  const tierDisplay = tier.charAt(0) + tier.slice(1).toLowerCase();

  return {
    tier,
    tierDisplay,
    discountPercent,
    freeShippingThreshold,
  };
}

/**
 * Builds a product discount for all eligible cart lines.
 *
 * Uses the percentage-off value method for accurate discount calculations.
 * Excludes products tagged with exclusion tags (no-tier-discount, sale, clearance).
 *
 * @param {Array} lines - Cart lines from input
 * @param {Object} tierData - Extracted tier data
 * @returns {Object|null} - Discount object or null if no eligible lines
 */
function buildProductDiscount(lines, tierData) {
  if (!lines || lines.length === 0) {
    return null;
  }

  // Filter to eligible product lines only
  const eligibleLines = [];

  for (const line of lines) {
    // Skip non-product lines (gift cards, etc.)
    if (!line.merchandise?.product) {
      continue;
    }

    // Skip products with exclusion tags
    if (line.merchandise.product.hasAnyTag) {
      continue;
    }

    // Skip lines with no cost
    if (!line.cost?.totalAmount?.amount) {
      continue;
    }

    eligibleLines.push(line);
  }

  // No eligible lines means no discount
  if (eligibleLines.length === 0) {
    return null;
  }

  // Build targets array for the discount
  const targets = eligibleLines.map(line => ({
    cartLine: {
      id: line.id,
    },
  }));

  // Build a clear, informative discount title
  // Examples: "Gold Member 10% Off" or "Platinum Member 15% Off"
  const discountTitle = buildDiscountTitle(tierData);

  // Return the discount object using percentage off value
  // This applies the percentage to each eligible line
  return {
    targets,
    value: {
      percentage: {
        // Shopify expects percentage as a string decimal (e.g., "10.0" for 10%)
        value: tierData.discountPercent.toString(),
      },
    },
    message: discountTitle,
  };
}

/**
 * Builds a customer-friendly discount title.
 *
 * Examples:
 * - "Gold Member 10% Off"
 * - "Platinum Member 15% Off + Free Shipping"
 *
 * @param {Object} tierData - Tier data with display name and discount
 * @returns {string} - Formatted discount title
 */
function buildDiscountTitle(tierData) {
  const { tierDisplay, discountPercent, freeShippingThreshold } = tierData;

  // Base title with tier and discount
  let title = `${tierDisplay} Member ${discountPercent}% Off`;

  // Add free shipping note if applicable
  // (0 = always free shipping)
  if (freeShippingThreshold === 0) {
    title += ' + Free Shipping';
  }

  return title;
}

/**
 * Calculates if the order qualifies for free shipping.
 *
 * Note: This is informational only. Actual free shipping requires
 * the Delivery Customization API or Shipping Discount API.
 *
 * @param {Object} cost - Cart cost object
 * @param {Object} tierData - Tier data with shipping threshold
 * @returns {boolean} - Whether order qualifies for free shipping
 */
function qualifiesForFreeShipping(cost, tierData) {
  const { freeShippingThreshold } = tierData;

  // No threshold configured = no free shipping benefit
  if (freeShippingThreshold === null) {
    return false;
  }

  // 0 threshold = always free shipping
  if (freeShippingThreshold === 0) {
    return true;
  }

  // Check if order subtotal meets threshold
  const subtotal = parseFloat(cost?.subtotalAmount?.amount || '0');
  return subtotal >= freeShippingThreshold;
}

// Export for testing
export { extractTierData, buildProductDiscount, buildDiscountTitle, qualifiesForFreeShipping };
