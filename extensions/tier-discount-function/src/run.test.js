/**
 * Tests for TradeUp Tier-Based Discount Function
 *
 * Run with: npm test
 */

import { describe, it, expect } from 'vitest';
import {
  run,
  extractTierData,
  buildProductDiscount,
  buildDiscountTitle,
  qualifiesForFreeShipping,
} from './run.js';

// ============================================================================
// Test Fixtures
// ============================================================================

/**
 * Creates a mock customer with tier metafields.
 */
function createMockCustomer(options = {}) {
  const {
    tier = 'GOLD',
    discountPct = '10',
    freeShippingThreshold = '50.00',
  } = options;

  return {
    id: 'gid://shopify/Customer/123456789',
    tierMetafield: tier ? { value: tier } : null,
    discountMetafield: discountPct ? { value: discountPct } : null,
    shippingThresholdMetafield: freeShippingThreshold !== null
      ? { value: freeShippingThreshold }
      : null,
  };
}

/**
 * Creates a mock cart line.
 */
function createMockLine(options = {}) {
  const {
    id = 'gid://shopify/CartLine/1',
    quantity = 1,
    amount = '29.99',
    hasExclusionTag = false,
  } = options;

  return {
    id,
    quantity,
    merchandise: {
      id: 'gid://shopify/ProductVariant/1',
      product: {
        id: 'gid://shopify/Product/1',
        hasAnyTag: hasExclusionTag,
      },
    },
    cost: {
      amountPerQuantity: { amount, currencyCode: 'USD' },
      totalAmount: { amount: (parseFloat(amount) * quantity).toFixed(2), currencyCode: 'USD' },
    },
  };
}

/**
 * Creates a complete mock input object.
 */
function createMockInput(options = {}) {
  const {
    customer = createMockCustomer(),
    lines = [createMockLine()],
    subtotalAmount = '59.98',
  } = options;

  return {
    cart: {
      buyerIdentity: {
        customer,
      },
      lines,
      cost: {
        totalAmount: { amount: subtotalAmount, currencyCode: 'USD' },
        subtotalAmount: { amount: subtotalAmount, currencyCode: 'USD' },
      },
      deliveryGroups: [],
    },
  };
}

// ============================================================================
// Unit Tests: extractTierData
// ============================================================================

describe('extractTierData', () => {
  it('extracts valid tier data from customer metafields', () => {
    const customer = createMockCustomer({
      tier: 'GOLD',
      discountPct: '10',
      freeShippingThreshold: '50.00',
    });

    const result = extractTierData(customer);

    expect(result.tier).toBe('GOLD');
    expect(result.tierDisplay).toBe('Gold');
    expect(result.discountPercent).toBe(10);
    expect(result.freeShippingThreshold).toBe(50);
  });

  it('handles lowercase tier names', () => {
    const customer = createMockCustomer({ tier: 'platinum' });
    const result = extractTierData(customer);

    expect(result.tier).toBe('PLATINUM');
    expect(result.tierDisplay).toBe('Platinum');
  });

  it('handles mixed case tier names', () => {
    const customer = createMockCustomer({ tier: 'SiLvEr' });
    const result = extractTierData(customer);

    expect(result.tier).toBe('SILVER');
    expect(result.tierDisplay).toBe('Silver');
  });

  it('returns null tier for missing metafield', () => {
    const customer = createMockCustomer({ tier: null });
    const result = extractTierData(customer);

    expect(result.tier).toBeNull();
    expect(result.discountPercent).toBe(0);
  });

  it('returns null tier for empty string', () => {
    const customer = createMockCustomer({ tier: '  ' });
    const result = extractTierData(customer);

    expect(result.tier).toBeNull();
  });

  it('returns 0 discount for invalid percentage', () => {
    const customer = createMockCustomer({ discountPct: 'invalid' });
    const result = extractTierData(customer);

    expect(result.discountPercent).toBe(0);
  });

  it('caps discount at 100%', () => {
    const customer = createMockCustomer({ discountPct: '150' });
    const result = extractTierData(customer);

    // Discount should be 0 since 150 > 100 is invalid
    expect(result.discountPercent).toBe(0);
  });

  it('rejects negative discount', () => {
    const customer = createMockCustomer({ discountPct: '-10' });
    const result = extractTierData(customer);

    expect(result.discountPercent).toBe(0);
  });

  it('handles zero free shipping threshold (always free)', () => {
    const customer = createMockCustomer({ freeShippingThreshold: '0' });
    const result = extractTierData(customer);

    expect(result.freeShippingThreshold).toBe(0);
  });

  it('handles null free shipping threshold', () => {
    const customer = createMockCustomer({ freeShippingThreshold: null });
    const result = extractTierData(customer);

    expect(result.freeShippingThreshold).toBeNull();
  });
});

// ============================================================================
// Unit Tests: buildDiscountTitle
// ============================================================================

describe('buildDiscountTitle', () => {
  it('formats standard tier discount title', () => {
    const tierData = {
      tierDisplay: 'Gold',
      discountPercent: 10,
      freeShippingThreshold: 50,
    };

    const result = buildDiscountTitle(tierData);

    expect(result).toBe('Gold Member 10% Off');
  });

  it('adds free shipping note when threshold is 0', () => {
    const tierData = {
      tierDisplay: 'Platinum',
      discountPercent: 15,
      freeShippingThreshold: 0,
    };

    const result = buildDiscountTitle(tierData);

    expect(result).toBe('Platinum Member 15% Off + Free Shipping');
  });

  it('does not add free shipping note when threshold is positive', () => {
    const tierData = {
      tierDisplay: 'Silver',
      discountPercent: 5,
      freeShippingThreshold: 100,
    };

    const result = buildDiscountTitle(tierData);

    expect(result).toBe('Silver Member 5% Off');
  });
});

// ============================================================================
// Unit Tests: buildProductDiscount
// ============================================================================

describe('buildProductDiscount', () => {
  const tierData = {
    tier: 'GOLD',
    tierDisplay: 'Gold',
    discountPercent: 10,
    freeShippingThreshold: 50,
  };

  it('builds discount for eligible lines', () => {
    const lines = [
      createMockLine({ id: 'line1', amount: '29.99' }),
      createMockLine({ id: 'line2', amount: '19.99' }),
    ];

    const result = buildProductDiscount(lines, tierData);

    expect(result).not.toBeNull();
    expect(result.targets).toHaveLength(2);
    expect(result.targets[0].cartLine.id).toBe('line1');
    expect(result.targets[1].cartLine.id).toBe('line2');
    expect(result.value.percentage.value).toBe('10');
    expect(result.message).toBe('Gold Member 10% Off');
  });

  it('excludes lines with exclusion tags', () => {
    const lines = [
      createMockLine({ id: 'line1', hasExclusionTag: false }),
      createMockLine({ id: 'line2', hasExclusionTag: true }), // sale/clearance item
    ];

    const result = buildProductDiscount(lines, tierData);

    expect(result.targets).toHaveLength(1);
    expect(result.targets[0].cartLine.id).toBe('line1');
  });

  it('returns null for empty lines array', () => {
    const result = buildProductDiscount([], tierData);
    expect(result).toBeNull();
  });

  it('returns null when all lines have exclusion tags', () => {
    const lines = [
      createMockLine({ hasExclusionTag: true }),
      createMockLine({ hasExclusionTag: true }),
    ];

    const result = buildProductDiscount(lines, tierData);

    expect(result).toBeNull();
  });
});

// ============================================================================
// Unit Tests: qualifiesForFreeShipping
// ============================================================================

describe('qualifiesForFreeShipping', () => {
  it('returns true when threshold is 0 (always free)', () => {
    const cost = { subtotalAmount: { amount: '10.00' } };
    const tierData = { freeShippingThreshold: 0 };

    expect(qualifiesForFreeShipping(cost, tierData)).toBe(true);
  });

  it('returns true when order meets threshold', () => {
    const cost = { subtotalAmount: { amount: '75.00' } };
    const tierData = { freeShippingThreshold: 50 };

    expect(qualifiesForFreeShipping(cost, tierData)).toBe(true);
  });

  it('returns false when order below threshold', () => {
    const cost = { subtotalAmount: { amount: '25.00' } };
    const tierData = { freeShippingThreshold: 50 };

    expect(qualifiesForFreeShipping(cost, tierData)).toBe(false);
  });

  it('returns false when threshold is null (no free shipping benefit)', () => {
    const cost = { subtotalAmount: { amount: '100.00' } };
    const tierData = { freeShippingThreshold: null };

    expect(qualifiesForFreeShipping(cost, tierData)).toBe(false);
  });

  it('returns true when order exactly meets threshold', () => {
    const cost = { subtotalAmount: { amount: '50.00' } };
    const tierData = { freeShippingThreshold: 50 };

    expect(qualifiesForFreeShipping(cost, tierData)).toBe(true);
  });
});

// ============================================================================
// Integration Tests: run
// ============================================================================

describe('run (integration)', () => {
  it('returns empty discounts for null input', () => {
    const result = run(null);
    expect(result.discounts).toEqual([]);
  });

  it('returns empty discounts for guest checkout', () => {
    const input = createMockInput();
    input.cart.buyerIdentity.customer = null;

    const result = run(input);

    expect(result.discounts).toEqual([]);
  });

  it('returns empty discounts for customer without tier', () => {
    const input = createMockInput({
      customer: createMockCustomer({ tier: null }),
    });

    const result = run(input);

    expect(result.discounts).toEqual([]);
  });

  it('returns empty discounts for tier with 0% discount', () => {
    const input = createMockInput({
      customer: createMockCustomer({ discountPct: '0' }),
    });

    const result = run(input);

    expect(result.discounts).toEqual([]);
  });

  it('applies Gold tier discount correctly', () => {
    const input = createMockInput({
      customer: createMockCustomer({
        tier: 'GOLD',
        discountPct: '10',
        freeShippingThreshold: '50.00',
      }),
      lines: [
        createMockLine({ id: 'line1', amount: '29.99' }),
      ],
    });

    const result = run(input);

    expect(result.discounts).toHaveLength(1);
    expect(result.discounts[0].value.percentage.value).toBe('10');
    expect(result.discounts[0].message).toBe('Gold Member 10% Off');
  });

  it('applies Platinum tier with free shipping note', () => {
    const input = createMockInput({
      customer: createMockCustomer({
        tier: 'PLATINUM',
        discountPct: '15',
        freeShippingThreshold: '0', // Always free shipping
      }),
      lines: [createMockLine()],
    });

    const result = run(input);

    expect(result.discounts).toHaveLength(1);
    expect(result.discounts[0].message).toBe('Platinum Member 15% Off + Free Shipping');
  });

  it('excludes sale items from discount', () => {
    const input = createMockInput({
      customer: createMockCustomer(),
      lines: [
        createMockLine({ id: 'regular', hasExclusionTag: false }),
        createMockLine({ id: 'sale', hasExclusionTag: true }),
      ],
    });

    const result = run(input);

    expect(result.discounts).toHaveLength(1);
    expect(result.discounts[0].targets).toHaveLength(1);
    expect(result.discounts[0].targets[0].cartLine.id).toBe('regular');
  });

  it('handles cart with only excluded items', () => {
    const input = createMockInput({
      customer: createMockCustomer(),
      lines: [
        createMockLine({ hasExclusionTag: true }),
        createMockLine({ hasExclusionTag: true }),
      ],
    });

    const result = run(input);

    expect(result.discounts).toEqual([]);
  });

  it('handles multiple tiers with different discount levels', () => {
    // Test Bronze tier
    const bronzeInput = createMockInput({
      customer: createMockCustomer({ tier: 'BRONZE', discountPct: '5' }),
    });
    expect(run(bronzeInput).discounts[0].value.percentage.value).toBe('5');

    // Test Silver tier
    const silverInput = createMockInput({
      customer: createMockCustomer({ tier: 'SILVER', discountPct: '7' }),
    });
    expect(run(silverInput).discounts[0].value.percentage.value).toBe('7');

    // Test Gold tier
    const goldInput = createMockInput({
      customer: createMockCustomer({ tier: 'GOLD', discountPct: '10' }),
    });
    expect(run(goldInput).discounts[0].value.percentage.value).toBe('10');

    // Test Platinum tier
    const platinumInput = createMockInput({
      customer: createMockCustomer({ tier: 'PLATINUM', discountPct: '15' }),
    });
    expect(run(platinumInput).discounts[0].value.percentage.value).toBe('15');
  });
});
