/**
 * TradeUp Post-Purchase UI Extension
 *
 * Celebrates points earned, shows new balance, reward progress,
 * and prompts referrals after a successful purchase.
 * This is the moment customers feel most rewarded!
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
  Button,
  Divider,
  Icon,
  Progress,
  Image,
  TextContainer,
  Heading,
  View,
  SkeletonText,
  useApi,
  useAppMetafields,
  useOrder,
  useSettings,
  useTranslate,
  useCustomer,
} from '@shopify/ui-extensions-react/checkout';
import { useMemo, useState, useCallback } from 'react';

// Main thank-you block render
export default reactExtension(
  'purchase.thank-you.block.render',
  () => <PostPurchaseRewards />
);

// Also render after customer information for visibility
reactExtension(
  'purchase.thank-you.customer-information.render-after',
  () => <PostPurchaseCompact />
);

/**
 * Main Post-Purchase Rewards Component
 * Full celebration display with all loyalty information
 */
function PostPurchaseRewards() {
  const translate = useTranslate();
  const settings = useSettings();
  const order = useOrder();
  const customer = useCustomer();
  const metafields = useAppMetafields();
  const [referralCopied, setReferralCopied] = useState(false);

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
    const referralCodeRaw = findMetafield('referral_code');

    return {
      pointsBalance: pointsBalanceRaw ? parseInt(pointsBalanceRaw, 10) : 0,
      tier: tierRaw || 'Member',
      earningMultiplier: multiplierRaw ? parseFloat(multiplierRaw) : 1.0,
      lifetimePoints: lifetimeRaw ? parseInt(lifetimeRaw, 10) : 0,
      referralCode: referralCodeRaw || generateReferralCode(customer?.email),
      isLoaded: metafields.length > 0 || pointsBalanceRaw !== undefined,
      isMember: !!tierRaw || !!pointsBalanceRaw,
    };
  }, [metafields, customer]);

  // Calculate points earned on this order
  const pointsEarned = useMemo(() => {
    if (!order?.totalPrice?.amount) return 0;

    const basePoints = settings.points_per_dollar || 1;
    const amount = parseFloat(order.totalPrice.amount);
    const multiplier = customerData.earningMultiplier || 1.0;

    return Math.floor(amount * basePoints * multiplier);
  }, [order, settings.points_per_dollar, customerData.earningMultiplier]);

  // Calculate new balance and reward progress
  const rewardData = useMemo(() => {
    const threshold = settings.next_reward_threshold || 500;
    const previousBalance = customerData.pointsBalance;
    const newBalance = previousBalance + pointsEarned;
    const progress = Math.min((newBalance / threshold) * 100, 100);
    const pointsNeeded = Math.max(threshold - newBalance, 0);

    // Check if they crossed a reward threshold with this purchase
    const previousProgress = Math.min((previousBalance / threshold) * 100, 100);
    const crossedThreshold = previousProgress < 100 && progress >= 100;

    // Check if they're close to next reward (within 50 points)
    const almostThere = pointsNeeded > 0 && pointsNeeded <= 50;

    return {
      previousBalance,
      newBalance,
      threshold,
      progress,
      pointsNeeded,
      rewardValue: settings.next_reward_value || '$5 off',
      crossedThreshold,
      almostThere,
      hasReward: progress >= 100,
    };
  }, [customerData.pointsBalance, pointsEarned, settings]);

  // Handle referral link copy
  const handleCopyReferral = useCallback(() => {
    // In a real implementation, this would use the clipboard API
    // For now, we just show visual feedback
    setReferralCopied(true);
    setTimeout(() => setReferralCopied(false), 3000);
  }, []);

  // Loading state
  if (!customerData.isLoaded) {
    return (
      <BlockStack spacing="tight" padding="base">
        <SkeletonText lines={3} />
      </BlockStack>
    );
  }

  const referralBonus = settings.referral_bonus_points || 500;

  return (
    <BlockStack spacing="loose" padding="base">
      {/* Main Celebration Banner */}
      {settings.show_celebration !== false && (
        <CelebrationBanner
          pointsEarned={pointsEarned}
          multiplier={customerData.earningMultiplier}
          tier={customerData.tier}
          crossedThreshold={rewardData.crossedThreshold}
          rewardValue={rewardData.rewardValue}
        />
      )}

      {/* Reward Unlocked Celebration */}
      {rewardData.crossedThreshold && (
        <RewardUnlockedBanner rewardValue={rewardData.rewardValue} />
      )}

      {/* New Points Balance */}
      {settings.show_new_balance !== false && (
        <PointsBalanceCard
          previousBalance={rewardData.previousBalance}
          newBalance={rewardData.newBalance}
          pointsEarned={pointsEarned}
          tier={customerData.tier}
        />
      )}

      {/* Reward Progress */}
      {settings.show_reward_progress !== false && !rewardData.hasReward && (
        <RewardProgressCard
          progress={rewardData.progress}
          pointsNeeded={rewardData.pointsNeeded}
          newBalance={rewardData.newBalance}
          threshold={rewardData.threshold}
          rewardValue={rewardData.rewardValue}
          almostThere={rewardData.almostThere}
        />
      )}

      {/* Referral Prompt */}
      {settings.show_referral_prompt !== false && (
        <ReferralCard
          referralCode={customerData.referralCode}
          bonusPoints={referralBonus}
          copied={referralCopied}
          onCopy={handleCopyReferral}
        />
      )}
    </BlockStack>
  );
}

/**
 * Celebration Banner Component
 * Shows exciting points earned message with tier highlighting
 */
function CelebrationBanner({ pointsEarned, multiplier, tier, crossedThreshold, rewardValue }) {
  const hasBonus = multiplier > 1;
  const basePoints = hasBonus ? Math.floor(pointsEarned / multiplier) : pointsEarned;
  const bonusPoints = pointsEarned - basePoints;

  return (
    <Banner
      status="success"
      title=""
    >
      <BlockStack spacing="tight">
        {/* Main celebration message */}
        <InlineStack spacing="tight" blockAlignment="center">
          <Text size="extraLarge">
            {crossedThreshold ? 'You unlocked a reward!' : 'You earned points!'}
          </Text>
        </InlineStack>

        {/* Points earned with animation-ready styling */}
        <BlockStack spacing="extraTight" inlineAlignment="center">
          <Text emphasis="bold" size="extraLarge" appearance="success">
            +{pointsEarned.toLocaleString()} points
          </Text>

          {/* Tier bonus callout */}
          {hasBonus && (
            <InlineStack spacing="tight" blockAlignment="center">
              <Icon source="checkCircle" appearance="success" size="small" />
              <Text size="small" appearance="success">
                {tier} bonus: +{bonusPoints.toLocaleString()} extra ({multiplier}x earning rate)
              </Text>
            </InlineStack>
          )}
        </BlockStack>

        {/* Reward unlocked teaser */}
        {crossedThreshold && (
          <Text size="medium" appearance="success">
            You've unlocked {rewardValue} - use it on your next purchase!
          </Text>
        )}
      </BlockStack>
    </Banner>
  );
}

/**
 * Reward Unlocked Banner
 * Extra prominent celebration when crossing reward threshold
 */
function RewardUnlockedBanner({ rewardValue }) {
  return (
    <View
      border="base"
      cornerRadius="large"
      padding="loose"
      background="interactive"
    >
      <BlockStack spacing="tight" inlineAlignment="center">
        <InlineStack spacing="tight" blockAlignment="center">
          <Icon source="gift" appearance="accent" />
          <Text emphasis="bold" size="large" appearance="accent">
            Reward Unlocked!
          </Text>
          <Icon source="gift" appearance="accent" />
        </InlineStack>

        <Text size="medium" appearance="accent">
          Congratulations! You've earned {rewardValue}
        </Text>

        <Text size="small" appearance="subdued">
          Your reward will be automatically applied to your next eligible purchase
        </Text>
      </BlockStack>
    </View>
  );
}

/**
 * Points Balance Card
 * Shows before/after balance with visual increase
 */
function PointsBalanceCard({ previousBalance, newBalance, pointsEarned, tier }) {
  return (
    <View
      border="base"
      cornerRadius="base"
      padding="base"
      background="subdued"
    >
      <BlockStack spacing="tight">
        <InlineStack spacing="tight" blockAlignment="center" inlineAlignment="spaceBetween">
          <InlineStack spacing="tight" blockAlignment="center">
            <Icon source="star" appearance="accent" />
            <Text emphasis="bold" size="medium">
              Your TradeUp Balance
            </Text>
          </InlineStack>
          <TierBadge tier={tier} />
        </InlineStack>

        <Divider />

        <InlineStack spacing="loose" blockAlignment="center" inlineAlignment="spaceBetween">
          <BlockStack spacing="extraTight">
            <Text size="small" appearance="subdued">
              Previous Balance
            </Text>
            <Text size="medium">
              {previousBalance.toLocaleString()} points
            </Text>
          </BlockStack>

          <InlineStack spacing="tight" blockAlignment="center">
            <Icon source="arrowRight" appearance="subdued" size="small" />
          </InlineStack>

          <BlockStack spacing="extraTight" inlineAlignment="end">
            <Text size="small" appearance="subdued">
              New Balance
            </Text>
            <InlineStack spacing="tight" blockAlignment="baseline">
              <Text emphasis="bold" size="large" appearance="accent">
                {newBalance.toLocaleString()}
              </Text>
              <Text size="medium" appearance="accent">
                points
              </Text>
            </InlineStack>
          </BlockStack>
        </InlineStack>

        <InlineStack spacing="tight" blockAlignment="center" inlineAlignment="center">
          <Icon source="arrowUp" appearance="success" size="extraSmall" />
          <Text size="small" appearance="success">
            +{pointsEarned.toLocaleString()} from this purchase
          </Text>
        </InlineStack>
      </BlockStack>
    </View>
  );
}

/**
 * Reward Progress Card
 * Shows progress toward next reward with motivational messaging
 */
function RewardProgressCard({ progress, pointsNeeded, newBalance, threshold, rewardValue, almostThere }) {
  return (
    <View
      border="base"
      cornerRadius="base"
      padding="base"
    >
      <BlockStack spacing="tight">
        <InlineStack spacing="loose" blockAlignment="center" inlineAlignment="spaceBetween">
          <Text size="small" emphasis="bold">
            Progress to Next Reward
          </Text>
          <Text size="small" appearance="subdued">
            {newBalance.toLocaleString()} / {threshold.toLocaleString()} points
          </Text>
        </InlineStack>

        <Progress value={progress} />

        <InlineStack spacing="tight" blockAlignment="center">
          {almostThere ? (
            <>
              <Icon source="star" appearance="accent" size="small" />
              <Text size="small" appearance="accent" emphasis="bold">
                So close! Just {pointsNeeded.toLocaleString()} more points to unlock {rewardValue}!
              </Text>
            </>
          ) : progress >= 75 ? (
            <>
              <Icon source="star" appearance="accent" size="extraSmall" />
              <Text size="small" appearance="accent">
                Almost there! {pointsNeeded.toLocaleString()} points to {rewardValue}
              </Text>
            </>
          ) : progress >= 50 ? (
            <>
              <Icon source="arrowUp" appearance="info" size="extraSmall" />
              <Text size="small" appearance="subdued">
                Great progress! {pointsNeeded.toLocaleString()} points to go
              </Text>
            </>
          ) : (
            <Text size="small" appearance="subdued">
              {pointsNeeded.toLocaleString()} more points to unlock {rewardValue}
            </Text>
          )}
        </InlineStack>
      </BlockStack>
    </View>
  );
}

/**
 * Referral Card
 * Prompts customer to share referral link for bonus points
 */
function ReferralCard({ referralCode, bonusPoints, copied, onCopy }) {
  return (
    <View
      border="base"
      cornerRadius="base"
      padding="base"
      background="interactive"
    >
      <BlockStack spacing="tight">
        <InlineStack spacing="tight" blockAlignment="center">
          <Icon source="profile" appearance="accent" />
          <Text emphasis="bold" size="medium" appearance="accent">
            Refer a Friend, Earn {bonusPoints.toLocaleString()} Bonus Points!
          </Text>
        </InlineStack>

        <Text size="small">
          Share your unique code with friends. When they make their first purchase,
          you both earn {bonusPoints.toLocaleString()} bonus points!
        </Text>

        <Divider />

        <BlockStack spacing="tight">
          <Text size="small" emphasis="bold">
            Your Referral Code:
          </Text>

          <InlineStack spacing="tight" blockAlignment="center" inlineAlignment="spaceBetween">
            <View
              border="base"
              cornerRadius="base"
              padding="tight"
              background="subdued"
            >
              <Text emphasis="bold" size="medium">
                {referralCode}
              </Text>
            </View>

            <Button
              kind="secondary"
              onPress={onCopy}
              accessibilityLabel="Copy referral code"
            >
              {copied ? 'Copied!' : 'Copy Code'}
            </Button>
          </InlineStack>
        </BlockStack>

        <InlineStack spacing="loose" blockAlignment="center" inlineAlignment="center">
          <Button
            kind="plain"
            accessibilityLabel="Share on Facebook"
          >
            Share
          </Button>
          <Text appearance="subdued">|</Text>
          <Button
            kind="plain"
            accessibilityLabel="Share via Email"
          >
            Email
          </Button>
          <Text appearance="subdued">|</Text>
          <Button
            kind="plain"
            accessibilityLabel="Share via Text"
          >
            Text
          </Button>
        </InlineStack>
      </BlockStack>
    </View>
  );
}

/**
 * Tier Badge Component
 * Displays customer's current loyalty tier
 */
function TierBadge({ tier }) {
  const tierColors = {
    Bronze: 'subdued',
    Silver: 'subdued',
    Gold: 'accent',
    Platinum: 'accent',
    Diamond: 'accent',
    VIP: 'accent',
  };

  const appearance = tierColors[tier] || 'subdued';

  return (
    <View
      border="base"
      cornerRadius="fullyRounded"
      padding="extraTight"
      background={appearance === 'accent' ? 'interactive' : 'subdued'}
    >
      <InlineStack spacing="extraTight" blockAlignment="center">
        <Icon source="star" appearance={appearance} size="extraSmall" />
        <Text size="small" emphasis="bold" appearance={appearance}>
          {tier}
        </Text>
      </InlineStack>
    </View>
  );
}

/**
 * Compact Post-Purchase Component
 * Minimal display for customer information placement
 */
function PostPurchaseCompact() {
  const settings = useSettings();
  const order = useOrder();
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

  const pointsEarned = useMemo(() => {
    if (!order?.totalPrice?.amount) return 0;
    const basePoints = settings.points_per_dollar || 1;
    const amount = parseFloat(order.totalPrice.amount);
    const multiplier = customerData.earningMultiplier || 1.0;
    return Math.floor(amount * basePoints * multiplier);
  }, [order, settings.points_per_dollar, customerData.earningMultiplier]);

  // Only show for members
  if (!customerData.isMember) {
    return null;
  }

  const newBalance = customerData.pointsBalance + pointsEarned;

  return (
    <View padding="tight">
      <InlineStack spacing="loose" blockAlignment="center" inlineAlignment="spaceBetween">
        <InlineStack spacing="tight" blockAlignment="center">
          <Icon source="star" appearance="success" size="small" />
          <Text size="small" appearance="success" emphasis="bold">
            +{pointsEarned.toLocaleString()} points earned
          </Text>
        </InlineStack>
        <Text size="small" appearance="subdued">
          Balance: {newBalance.toLocaleString()} pts
        </Text>
      </InlineStack>
    </View>
  );
}

/**
 * Generate a referral code from customer email
 * Falls back to random code if no email
 */
function generateReferralCode(email) {
  if (email) {
    const prefix = email.split('@')[0].substring(0, 6).toUpperCase();
    const suffix = Math.random().toString(36).substring(2, 6).toUpperCase();
    return `${prefix}${suffix}`;
  }
  return `REF${Math.random().toString(36).substring(2, 8).toUpperCase()}`;
}
