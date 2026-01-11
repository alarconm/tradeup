/**
 * TradeUp Checkout Validation Function
 *
 * Validates:
 * 1. Points redemption - customer has enough points
 * 2. Reward availability - reward is still active and not exceeded max redemptions
 * 3. Tier-restricted products - customer has required tier
 * 4. Minimum points thresholds - customer meets product requirements
 *
 * Uses Shopify Functions API 2025-01
 * https://shopify.dev/docs/api/functions/reference/cart-checkout-validation
 */

// @ts-check

/**
 * @typedef {Object} CartAttribute
 * @property {string} key
 * @property {string|null} value
 */

/**
 * @typedef {Object} Metafield
 * @property {string|null} value
 */

/**
 * @typedef {Object} Product
 * @property {string} id
 * @property {string} title
 * @property {Metafield|null} tierRestriction
 * @property {Metafield|null} minPointsRequired
 * @property {string[]} tags
 */

/**
 * @typedef {Object} ProductVariant
 * @property {string} id
 * @property {Product} product
 */

/**
 * @typedef {Object} CartLine
 * @property {string} id
 * @property {number} quantity
 * @property {{__typename: string} & ProductVariant} merchandise
 * @property {{totalAmount: {amount: string, currencyCode: string}}} cost
 */

/**
 * @typedef {Object} Customer
 * @property {string} id
 * @property {string|null} email
 * @property {Metafield|null} pointsBalance
 * @property {Metafield|null} tier
 * @property {Metafield|null} tierLevel
 * @property {Metafield|null} lifetimePoints
 * @property {Metafield|null} memberStatus
 * @property {Metafield|null} redemptionsThisMonth
 * @property {Metafield|null} maxRedemptionsPerMonth
 */

/**
 * @typedef {Object} Input
 * @property {{
 *   attribute: CartAttribute|null,
 *   attributes: CartAttribute[],
 *   lines: CartLine[],
 *   discountCodes: {code: string, applicable: boolean}[],
 *   cost: {
 *     subtotalAmount: {amount: string, currencyCode: string},
 *     totalAmount: {amount: string, currencyCode: string}
 *   }
 * }} cart
 * @property {{customer: Customer|null}} buyerIdentity
 * @property {{country: {isoCode: string}, language: {isoCode: string}}} localization
 */

/**
 * @typedef {Object} ValidationError
 * @property {string} localizedMessage
 * @property {{cartLineId?: string, cartAttributeKey?: string}} target
 */

/**
 * @typedef {Object} FunctionResult
 * @property {ValidationError[]} errors
 */

// Tier hierarchy for comparison
const TIER_HIERARCHY = {
  'bronze': 1,
  'silver': 2,
  'gold': 3,
  'platinum': 4,
  'diamond': 5,
};

/**
 * Get tier level from tier name
 * @param {string|null} tierName
 * @returns {number}
 */
function getTierLevel(tierName) {
  if (!tierName) return 0;
  return TIER_HIERARCHY[tierName.toLowerCase()] || 0;
}

/**
 * Parse a metafield value safely
 * @param {Metafield|null} metafield
 * @param {any} defaultValue
 * @returns {any}
 */
function parseMetafield(metafield, defaultValue = null) {
  if (!metafield || !metafield.value) return defaultValue;

  try {
    // Try parsing as JSON first
    return JSON.parse(metafield.value);
  } catch {
    // Return raw value if not JSON
    return metafield.value;
  }
}

/**
 * Parse numeric metafield
 * @param {Metafield|null} metafield
 * @param {number} defaultValue
 * @returns {number}
 */
function parseNumericMetafield(metafield, defaultValue = 0) {
  if (!metafield || !metafield.value) return defaultValue;

  const parsed = parseInt(metafield.value, 10);
  return isNaN(parsed) ? defaultValue : parsed;
}

/**
 * Get cart attribute by key
 * @param {CartAttribute[]} attributes
 * @param {string} key
 * @returns {string|null}
 */
function getCartAttribute(attributes, key) {
  const attr = attributes.find((a) => a.key === key);
  return attr?.value || null;
}

/**
 * Validate points redemption
 * @param {Input} input
 * @returns {ValidationError[]}
 */
function validatePointsRedemption(input) {
  const errors = [];
  const { cart, buyerIdentity } = input;
  const customer = buyerIdentity?.customer;

  // Check if customer is redeeming points
  const pointsToRedeem = getCartAttribute(cart.attributes, 'tradeup_points_redeem');

  if (!pointsToRedeem) {
    // Also check for the primary attribute from query
    if (!cart.attribute?.value) {
      return errors; // No redemption requested
    }
  }

  const requestedPoints = parseInt(pointsToRedeem || cart.attribute?.value || '0', 10);

  if (requestedPoints <= 0) {
    return errors; // No valid redemption amount
  }

  // Customer must be logged in to redeem points
  if (!customer) {
    errors.push({
      localizedMessage: 'You must be logged in to redeem points.',
      target: { cartAttributeKey: 'tradeup_points_redeem' },
    });
    return errors;
  }

  // Check member status
  const memberStatus = parseMetafield(customer.memberStatus, 'none');
  if (memberStatus !== 'active') {
    errors.push({
      localizedMessage:
        'Your TradeUp membership is not active. Please contact support to redeem points.',
      target: { cartAttributeKey: 'tradeup_points_redeem' },
    });
    return errors;
  }

  // Get customer's points balance
  const pointsBalance = parseNumericMetafield(customer.pointsBalance, 0);

  // Validate sufficient points
  if (requestedPoints > pointsBalance) {
    const pointsNeeded = requestedPoints - pointsBalance;
    errors.push({
      localizedMessage: `You need ${pointsNeeded.toLocaleString()} more points to redeem this reward. Your current balance is ${pointsBalance.toLocaleString()} points.`,
      target: { cartAttributeKey: 'tradeup_points_redeem' },
    });
  }

  // Check monthly redemption limits
  const redemptionsThisMonth = parseNumericMetafield(customer.redemptionsThisMonth, 0);
  const maxRedemptionsPerMonth = parseNumericMetafield(customer.maxRedemptionsPerMonth, 0);

  if (maxRedemptionsPerMonth > 0 && redemptionsThisMonth >= maxRedemptionsPerMonth) {
    errors.push({
      localizedMessage: `You have reached your maximum of ${maxRedemptionsPerMonth} redemptions this month. Limit resets on the 1st.`,
      target: { cartAttributeKey: 'tradeup_points_redeem' },
    });
  }

  return errors;
}

/**
 * Validate reward code (discount code that represents a TradeUp reward)
 * @param {Input} input
 * @returns {ValidationError[]}
 */
function validateRewardCodes(input) {
  const errors = [];
  const { cart, buyerIdentity } = input;
  const customer = buyerIdentity?.customer;

  // Check for TradeUp reward codes (prefixed with TU-)
  const tradeUpCodes = cart.discountCodes.filter(
    (dc) => dc.code.startsWith('TU-') || dc.code.startsWith('TRADEUP-')
  );

  if (tradeUpCodes.length === 0) {
    return errors; // No TradeUp reward codes
  }

  // Customer must be logged in to use reward codes
  if (!customer) {
    for (const code of tradeUpCodes) {
      errors.push({
        localizedMessage: `You must be logged in to use reward code "${code.code}".`,
        target: {},
      });
    }
    return errors;
  }

  // Check if reward code is applicable
  for (const code of tradeUpCodes) {
    if (!code.applicable) {
      // Check if this might be a tier-restricted reward
      const tierName = parseMetafield(customer.tier, null);

      errors.push({
        localizedMessage: `Reward code "${code.code}" cannot be applied. It may have expired, already been used, or require a higher membership tier.`,
        target: {},
      });
    }
  }

  return errors;
}

/**
 * Validate tier-restricted products
 * @param {Input} input
 * @returns {ValidationError[]}
 */
function validateTierRestrictions(input) {
  const errors = [];
  const { cart, buyerIdentity } = input;
  const customer = buyerIdentity?.customer;

  // Get customer tier
  const customerTier = customer ? parseMetafield(customer.tier, null) : null;
  const customerTierLevel = getTierLevel(customerTier);

  for (const line of cart.lines) {
    // Only check ProductVariant merchandise
    if (line.merchandise.__typename !== 'ProductVariant') {
      continue;
    }

    const product = line.merchandise.product;

    // Check tier restriction metafield
    const tierRestriction = parseMetafield(product.tierRestriction, null);

    if (tierRestriction) {
      let requiredTier = null;
      let minTierLevel = 0;

      // Handle both string and object format
      if (typeof tierRestriction === 'string') {
        requiredTier = tierRestriction;
        minTierLevel = getTierLevel(requiredTier);
      } else if (typeof tierRestriction === 'object') {
        requiredTier = tierRestriction.required_tier || tierRestriction.requiredTier;
        minTierLevel = tierRestriction.min_level || getTierLevel(requiredTier);
      }

      if (requiredTier && customerTierLevel < minTierLevel) {
        if (!customer) {
          errors.push({
            localizedMessage: `"${product.title}" requires ${requiredTier} tier membership. Please log in to verify your membership.`,
            target: { cartLineId: line.id },
          });
        } else {
          const currentTierDisplay = customerTier
            ? customerTier.charAt(0).toUpperCase() + customerTier.slice(1)
            : 'Basic';
          errors.push({
            localizedMessage: `"${product.title}" requires ${requiredTier} tier membership. Your current tier is ${currentTierDisplay}.`,
            target: { cartLineId: line.id },
          });
        }
      }
    }

    // Check for tier-restricted product tags
    const tierTags = product.tags.filter((tag) => tag.toLowerCase().startsWith('tier:'));
    for (const tierTag of tierTags) {
      const requiredTier = tierTag.split(':')[1];
      const requiredLevel = getTierLevel(requiredTier);

      if (requiredLevel > 0 && customerTierLevel < requiredLevel) {
        errors.push({
          localizedMessage: `"${product.title}" is exclusive to ${requiredTier.charAt(0).toUpperCase() + requiredTier.slice(1)} tier members and above.`,
          target: { cartLineId: line.id },
        });
      }
    }
  }

  return errors;
}

/**
 * Validate minimum points requirements for products
 * @param {Input} input
 * @returns {ValidationError[]}
 */
function validateMinPointsRequirements(input) {
  const errors = [];
  const { cart, buyerIdentity } = input;
  const customer = buyerIdentity?.customer;

  // Get customer points
  const customerPoints = customer ? parseNumericMetafield(customer.pointsBalance, 0) : 0;
  const lifetimePoints = customer ? parseNumericMetafield(customer.lifetimePoints, 0) : 0;

  for (const line of cart.lines) {
    // Only check ProductVariant merchandise
    if (line.merchandise.__typename !== 'ProductVariant') {
      continue;
    }

    const product = line.merchandise.product;

    // Check minimum points requirement
    const minPointsRequired = parseMetafield(product.minPointsRequired, null);

    if (minPointsRequired) {
      let minPoints = 0;
      let useLifetime = false;

      // Handle both number and object format
      if (typeof minPointsRequired === 'number') {
        minPoints = minPointsRequired;
      } else if (typeof minPointsRequired === 'object') {
        minPoints = minPointsRequired.points || minPointsRequired.min_points || 0;
        useLifetime = minPointsRequired.use_lifetime === true;
      } else if (typeof minPointsRequired === 'string') {
        minPoints = parseInt(minPointsRequired, 10) || 0;
      }

      if (minPoints > 0) {
        const checkBalance = useLifetime ? lifetimePoints : customerPoints;

        if (!customer) {
          errors.push({
            localizedMessage: `"${product.title}" requires ${minPoints.toLocaleString()} points to purchase. Please log in to verify your points balance.`,
            target: { cartLineId: line.id },
          });
        } else if (checkBalance < minPoints) {
          const pointsNeeded = minPoints - checkBalance;
          const balanceType = useLifetime ? 'lifetime' : 'current';
          errors.push({
            localizedMessage: `"${product.title}" requires ${minPoints.toLocaleString()} ${balanceType} points. You need ${pointsNeeded.toLocaleString()} more points to purchase this item.`,
            target: { cartLineId: line.id },
          });
        }
      }
    }

    // Check for points requirement in tags (e.g., "min-points:1000")
    const pointsTags = product.tags.filter((tag) => tag.toLowerCase().startsWith('min-points:'));
    for (const pointsTag of pointsTags) {
      const minPoints = parseInt(pointsTag.split(':')[1], 10);

      if (minPoints > 0 && customerPoints < minPoints) {
        if (!customer) {
          errors.push({
            localizedMessage: `"${product.title}" requires ${minPoints.toLocaleString()} points. Please log in to verify your balance.`,
            target: { cartLineId: line.id },
          });
        } else {
          const pointsNeeded = minPoints - customerPoints;
          errors.push({
            localizedMessage: `"${product.title}" requires ${minPoints.toLocaleString()} points. You need ${pointsNeeded.toLocaleString()} more points.`,
            target: { cartLineId: line.id },
          });
        }
      }
    }
  }

  return errors;
}

/**
 * Validate members-only products
 * @param {Input} input
 * @returns {ValidationError[]}
 */
function validateMembersOnlyProducts(input) {
  const errors = [];
  const { cart, buyerIdentity } = input;
  const customer = buyerIdentity?.customer;

  // Check member status
  const memberStatus = customer ? parseMetafield(customer.memberStatus, 'none') : 'none';
  const isMember = memberStatus === 'active';

  for (const line of cart.lines) {
    // Only check ProductVariant merchandise
    if (line.merchandise.__typename !== 'ProductVariant') {
      continue;
    }

    const product = line.merchandise.product;

    // Check for members-only tag
    const hasMembersOnlyTag = product.tags.some(
      (tag) => tag.toLowerCase() === 'members-only' || tag.toLowerCase() === 'tradeup-members-only'
    );

    if (hasMembersOnlyTag && !isMember) {
      if (!customer) {
        errors.push({
          localizedMessage: `"${product.title}" is exclusive to TradeUp members. Please log in or join our membership program.`,
          target: { cartLineId: line.id },
        });
      } else {
        errors.push({
          localizedMessage: `"${product.title}" is exclusive to TradeUp members. Join our membership program to purchase this item.`,
          target: { cartLineId: line.id },
        });
      }
    }
  }

  return errors;
}

/**
 * Main function entry point
 * @param {Input} input
 * @returns {FunctionResult}
 */
export function run(input) {
  /** @type {ValidationError[]} */
  const allErrors = [];

  try {
    // Run all validations
    allErrors.push(...validatePointsRedemption(input));
    allErrors.push(...validateRewardCodes(input));
    allErrors.push(...validateTierRestrictions(input));
    allErrors.push(...validateMinPointsRequirements(input));
    allErrors.push(...validateMembersOnlyProducts(input));

    // Deduplicate errors by message
    const uniqueErrors = [];
    const seenMessages = new Set();

    for (const error of allErrors) {
      if (!seenMessages.has(error.localizedMessage)) {
        seenMessages.add(error.localizedMessage);
        uniqueErrors.push(error);
      }
    }

    return { errors: uniqueErrors };
  } catch (error) {
    // Log error but don't block checkout
    console.error('TradeUp validation error:', error);
    return { errors: [] };
  }
}

// Default export for Shopify Functions
export default { run };
