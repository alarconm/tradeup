/**
 * TradeUp Checkout UI Extension
 *
 * Displays loyalty points balance, earnings preview, and reward progress
 * at checkout to encourage purchases and highlight membership value.
 *
 * @author Cardflow Labs
 * @version 1.0.0
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

import { PointsBalance } from './components/PointsBalance.jsx';
import { PointsEarning } from './components/PointsEarning.jsx';
import { RewardProgress } from './components/RewardProgress.jsx';
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
 * Main TradeUp checkout component
 * Full display with all loyalty information
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
    const tierRaw = findMetafield('tier');
    const multiplierRaw = findMetafield('tier_earning_multiplier');
    const lifetimeRaw = findMetafield('lifetime_points');

    return {
      pointsBalance: pointsBalanceRaw ? parseInt(pointsBalanceRaw, 10) : 0,
      tier: tierRaw || null,
      earningMultiplier: multiplierRaw ? parseFloat(multiplierRaw) : 1.0,
      lifetimePoints: lifetimeRaw ? parseInt(lifetimeRaw, 10) : 0,
      isLoaded: metafields.length > 0 || pointsBalanceRaw !== undefined,
      isMember: !!tierRaw || !!pointsBalanceRaw,
    };
  }, [metafields]);

  // Calculate points to earn on this order
  const pointsToEarn = useMemo(() => {
    if (!totalAmount?.amount) return 0;

    const basePoints = settings.points_per_dollar || 1;
    const amount = parseFloat(totalAmount.amount);
    const multiplier = customerData.earningMultiplier || 1.0;

    return Math.floor(amount * basePoints * multiplier);
  }, [totalAmount, settings.points_per_dollar, customerData.earningMultiplier]);

  // Calculate reward progress
  const rewardProgress = useMemo(() => {
    const threshold = settings.next_reward_threshold || 500;
    const currentPoints = customerData.pointsBalance + pointsToEarn;
    const progress = Math.min((currentPoints / threshold) * 100, 100);
    const pointsNeeded = Math.max(threshold - currentPoints, 0);

    return {
      currentPoints,
      threshold,
      progress,
      pointsNeeded,
      rewardValue: settings.next_reward_value || '$5 off',
      hasReward: currentPoints >= threshold,
    };
  }, [customerData.pointsBalance, pointsToEarn, settings]);

  // Not a member - show signup encouragement
  if (!customerData.isMember && customerData.isLoaded) {
    return (
      <Banner status="info" title={translate('join_program')}>
        <BlockStack spacing="tight">
          <Text>
            {translate('join_description', { points: pointsToEarn })}
          </Text>
          <Text appearance="subdued" size="small">
            {translate('auto_enroll')}
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

  // Member view - full loyalty display
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
          {translate('loyalty_rewards')}
        </Text>
        {settings.show_tier_badge !== false && customerData.tier && (
          <TierBadge tier={customerData.tier} />
        )}
      </InlineStack>

      <Divider />

      {/* Points balance */}
      <PointsBalance
        balance={customerData.pointsBalance}
        multiplier={customerData.earningMultiplier}
      />

      {/* Points to earn */}
      <PointsEarning
        pointsToEarn={pointsToEarn}
        multiplier={customerData.earningMultiplier}
        orderTotal={totalAmount?.amount}
        currencyCode={totalAmount?.currencyCode}
      />

      {/* Reward progress */}
      {settings.show_reward_progress !== false && (
        <>
          <Divider />
          <RewardProgress
            currentPoints={rewardProgress.currentPoints}
            threshold={rewardProgress.threshold}
            progress={rewardProgress.progress}
            pointsNeeded={rewardProgress.pointsNeeded}
            rewardValue={rewardProgress.rewardValue}
            hasReward={rewardProgress.hasReward}
          />
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
  const translate = useTranslate();
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
    const multiplierRaw = findMetafield('tier_earning_multiplier');

    return {
      pointsBalance: pointsBalanceRaw ? parseInt(pointsBalanceRaw, 10) : 0,
      earningMultiplier: multiplierRaw ? parseFloat(multiplierRaw) : 1.0,
      isMember: !!pointsBalanceRaw,
    };
  }, [metafields]);

  const pointsToEarn = useMemo(() => {
    if (!totalAmount?.amount) return 0;
    const basePoints = settings.points_per_dollar || 1;
    const amount = parseFloat(totalAmount.amount);
    const multiplier = customerData.earningMultiplier || 1.0;
    return Math.floor(amount * basePoints * multiplier);
  }, [totalAmount, settings.points_per_dollar, customerData.earningMultiplier]);

  // Only show for members
  if (!customerData.isMember) {
    return null;
  }

  return (
    <InlineStack spacing="tight" blockAlignment="center" padding="tight">
      <Icon source="star" appearance="accent" size="small" />
      <Text size="small" appearance="accent">
        {translate('earn_points_compact', { points: pointsToEarn })}
      </Text>
      {customerData.earningMultiplier > 1 && (
        <Text size="small" appearance="success">
          ({customerData.earningMultiplier}x {translate('bonus')})
        </Text>
      )}
    </InlineStack>
  );
}
