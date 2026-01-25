/**
 * TradeUp Checkout UI Extension
 *
 * Displays loyalty rewards at checkout - adapts to show either:
 * - Store Credit mode: "$X store credit", "Earn $Y cashback"
 * - Points mode: "X points", "Earn Y points"
 *
 * @author Cardflow Labs
 * @version 2.0.0 - Mode-aware update
 */
import {
  reactExtension,
  Banner,
  BlockStack,
  InlineStack,
  Text,
  Divider,
  Icon,
  SkeletonText,
  useApi,
  useAppMetafields,
  useTotalAmount,
  useSettings,
  useExtensionLanguage,
  useTranslate,
} from '@shopify/ui-extensions-react/checkout';
import { useMemo } from 'react';

import { TierBadge } from './components/TierBadge.jsx';

// Main checkout block render
export default reactExtension(
  'purchase.checkout.block.render',
  () => <TradeUpCheckout />
);

// Also render after cart line list for visibility
reactExtension(
  'purchase.checkout.cart-line-list.render-after',
  () => <TradeUpCheckoutCompact />
);

/**
 * Format currency for display
 */
function formatCurrency(amount, currencyCode = 'USD') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currencyCode,
    minimumFractionDigits: 2,
  }).format(amount);
}

/**
 * Main TradeUp checkout component
 * Mode-aware: displays store credit OR points based on merchant setting
 */
function TradeUpCheckout() {
  const translate = useTranslate();
  const settings = useSettings();
  const totalAmount = useTotalAmount();
  const metafields = useAppMetafields();

  // Extract customer metafield values
  const customerData = useMemo(() => {
    const findMetafield = (key) => {
      const field = metafields.find(
        (m) => m.metafield?.namespace === 'tradeup' && m.metafield?.key === key
      );
      return field?.metafield?.value;
    };

    const pointsBalanceRaw = findMetafield('points_balance');
    const storeCreditRaw = findMetafield('store_credit_balance');
    const tierRaw = findMetafield('tier');
    const tierCashbackRaw = findMetafield('tier_cashback_pct');
    const multiplierRaw = findMetafield('tier_earning_multiplier');
    const loyaltyModeRaw = findMetafield('loyalty_mode');

    return {
      // Points data
      pointsBalance: pointsBalanceRaw ? parseInt(pointsBalanceRaw, 10) : 0,
      // Store credit data
      storeCreditBalance: storeCreditRaw ? parseFloat(storeCreditRaw) : 0,
      // Tier data
      tier: tierRaw || null,
      tierCashbackPct: tierCashbackRaw ? parseFloat(tierCashbackRaw) : 0,
      earningMultiplier: multiplierRaw ? parseFloat(multiplierRaw) : 1.0,
      // Mode - default to store_credit if not set
      loyaltyMode: loyaltyModeRaw || 'store_credit',
      // Status
      isLoaded: metafields.length > 0 || pointsBalanceRaw !== undefined || storeCreditRaw !== undefined,
      isMember: !!tierRaw || !!pointsBalanceRaw || !!storeCreditRaw,
    };
  }, [metafields]);

  // Calculate earnings based on mode
  const earnings = useMemo(() => {
    if (!totalAmount?.amount) return { value: 0, display: '' };

    const amount = parseFloat(totalAmount.amount);
    const currencyCode = totalAmount.currencyCode || 'USD';

    if (customerData.loyaltyMode === 'points') {
      // Points mode: X points per dollar
      const basePoints = settings.points_per_dollar || 10;
      const multiplier = customerData.earningMultiplier || 1.0;
      const points = Math.floor(amount * basePoints * multiplier);
      return {
        value: points,
        display: `+${points.toLocaleString()} points`,
        hasBonus: multiplier > 1,
        bonusText: multiplier > 1 ? `(${multiplier}x bonus!)` : '',
      };
    } else {
      // Store credit mode: X% cashback
      const cashbackPct = customerData.tierCashbackPct || 0;
      const cashback = amount * (cashbackPct / 100);
      return {
        value: cashback,
        display: cashback > 0 ? `+${formatCurrency(cashback, currencyCode)} cashback` : 'Earn cashback with a tier',
        hasBonus: cashbackPct > 0,
        bonusText: cashbackPct > 0 ? `(${cashbackPct}% back)` : '',
      };
    }
  }, [totalAmount, settings.points_per_dollar, customerData]);

  // Not a member - show signup encouragement
  if (!customerData.isMember && customerData.isLoaded) {
    const joinMessage = customerData.loyaltyMode === 'points'
      ? `Join and earn ${earnings.value.toLocaleString()} points on this order!`
      : 'Join our rewards program and earn cashback on every purchase!';

    return (
      <Banner status="info" title="TradeUp Rewards">
        <BlockStack spacing="tight">
          <Text>{joinMessage}</Text>
          <Text appearance="subdued" size="small">
            You'll be automatically enrolled with your purchase.
          </Text>
        </BlockStack>
      </Banner>
    );
  }

  // Loading state
  if (!customerData.isLoaded) {
    return (
      <BlockStack spacing="tight" padding="base">
        <SkeletonText lines={2} />
      </BlockStack>
    );
  }

  // Member view - mode-aware loyalty display
  const isPointsMode = customerData.loyaltyMode === 'points';
  const currencyCode = totalAmount?.currencyCode || 'USD';

  return (
    <BlockStack
      spacing="base"
      padding="base"
      border="base"
      cornerRadius="base"
      background="subdued"
    >
      {/* Header with tier badge */}
      <InlineStack spacing="tight" blockAlignment="center">
        <Icon source="star" appearance="accent" />
        <Text emphasis="bold" size="medium">
          TradeUp Rewards
        </Text>
        {settings.show_tier_badge !== false && customerData.tier && (
          <TierBadge tier={customerData.tier} />
        )}
      </InlineStack>

      <Divider />

      {/* Current Balance */}
      <BlockStack spacing="extraTight">
        <Text size="small" appearance="subdued">
          {isPointsMode ? 'Your Points' : 'Your Store Credit'}
        </Text>
        <InlineStack spacing="tight" blockAlignment="baseline">
          <Text emphasis="bold" size="large">
            {isPointsMode
              ? customerData.pointsBalance.toLocaleString()
              : formatCurrency(customerData.storeCreditBalance, currencyCode)
            }
          </Text>
          {isPointsMode && (
            <Text size="medium" appearance="subdued">points</Text>
          )}
        </InlineStack>
      </BlockStack>

      {/* Earnings on this order */}
      {earnings.value > 0 && (
        <BlockStack
          spacing="extraTight"
          padding="tight"
          background="interactive"
          cornerRadius="base"
        >
          <InlineStack spacing="tight" blockAlignment="center">
            <Icon source="gift" appearance="accent" size="small" />
            <Text size="small" emphasis="bold" appearance="accent">
              {isPointsMode ? 'Earning on this order' : 'Cashback on this order'}
            </Text>
          </InlineStack>

          <InlineStack spacing="tight" blockAlignment="baseline">
            <Text emphasis="bold" size="large" appearance="accent">
              {earnings.display}
            </Text>
          </InlineStack>

          {earnings.hasBonus && earnings.bonusText && (
            <InlineStack spacing="extraTight" blockAlignment="center">
              <Icon source="checkCircle" appearance="success" size="extraSmall" />
              <Text size="small" appearance="success">
                {earnings.bonusText}
              </Text>
            </InlineStack>
          )}
        </BlockStack>
      )}

      {/* Store credit auto-apply notice */}
      {!isPointsMode && customerData.storeCreditBalance > 0 && (
        <>
          <Divider />
          <InlineStack spacing="tight" blockAlignment="center">
            <Icon source="checkCircle" appearance="success" size="small" />
            <Text size="small" appearance="success">
              Your store credit will auto-apply at payment
            </Text>
          </InlineStack>
        </>
      )}
    </BlockStack>
  );
}

/**
 * Compact version for cart line list placement
 * Shows essential info only
 */
function TradeUpCheckoutCompact() {
  const settings = useSettings();
  const totalAmount = useTotalAmount();
  const metafields = useAppMetafields();

  const customerData = useMemo(() => {
    const findMetafield = (key) => {
      const field = metafields.find(
        (m) => m.metafield?.namespace === 'tradeup' && m.metafield?.key === key
      );
      return field?.metafield?.value;
    };

    const pointsBalanceRaw = findMetafield('points_balance');
    const storeCreditRaw = findMetafield('store_credit_balance');
    const tierCashbackRaw = findMetafield('tier_cashback_pct');
    const multiplierRaw = findMetafield('tier_earning_multiplier');
    const loyaltyModeRaw = findMetafield('loyalty_mode');

    return {
      pointsBalance: pointsBalanceRaw ? parseInt(pointsBalanceRaw, 10) : 0,
      storeCreditBalance: storeCreditRaw ? parseFloat(storeCreditRaw) : 0,
      tierCashbackPct: tierCashbackRaw ? parseFloat(tierCashbackRaw) : 0,
      earningMultiplier: multiplierRaw ? parseFloat(multiplierRaw) : 1.0,
      loyaltyMode: loyaltyModeRaw || 'store_credit',
      isMember: !!pointsBalanceRaw || !!storeCreditRaw,
    };
  }, [metafields]);

  // Calculate earnings
  const earnings = useMemo(() => {
    if (!totalAmount?.amount) return null;

    const amount = parseFloat(totalAmount.amount);
    const currencyCode = totalAmount.currencyCode || 'USD';

    if (customerData.loyaltyMode === 'points') {
      const basePoints = settings.points_per_dollar || 10;
      const multiplier = customerData.earningMultiplier || 1.0;
      const points = Math.floor(amount * basePoints * multiplier);
      return {
        display: `Earn ${points.toLocaleString()} points`,
        hasBonus: multiplier > 1,
        bonusText: `${multiplier}x`,
      };
    } else {
      const cashbackPct = customerData.tierCashbackPct || 0;
      if (cashbackPct <= 0) return null;
      const cashback = amount * (cashbackPct / 100);
      return {
        display: `Earn ${formatCurrency(cashback, currencyCode)} cashback`,
        hasBonus: true,
        bonusText: `${cashbackPct}%`,
      };
    }
  }, [totalAmount, settings.points_per_dollar, customerData]);

  // Only show for members with earnings
  if (!customerData.isMember || !earnings) {
    return null;
  }

  return (
    <InlineStack spacing="tight" blockAlignment="center" padding="tight">
      <Icon source="star" appearance="accent" size="small" />
      <Text size="small" appearance="accent">
        {earnings.display}
      </Text>
      {earnings.hasBonus && (
        <Text size="small" appearance="success">
          ({earnings.bonusText})
        </Text>
      )}
    </InlineStack>
  );
}
