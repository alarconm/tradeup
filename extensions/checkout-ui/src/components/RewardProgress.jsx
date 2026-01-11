/**
 * RewardProgress Component
 *
 * Displays a progress bar showing how close the customer
 * is to their next reward, with motivational messaging.
 */
import {
  BlockStack,
  InlineStack,
  Text,
  Progress,
  Icon,
  useTranslate,
} from '@shopify/ui-extensions-react/checkout';

/**
 * @param {Object} props
 * @param {number} props.currentPoints - Current points (including pending from order)
 * @param {number} props.threshold - Points needed for next reward
 * @param {number} props.progress - Progress percentage (0-100)
 * @param {number} props.pointsNeeded - Points still needed for reward
 * @param {string} props.rewardValue - Description of reward (e.g., "$5 off")
 * @param {boolean} props.hasReward - Whether customer has reached reward threshold
 */
export function RewardProgress({
  currentPoints,
  threshold,
  progress,
  pointsNeeded,
  rewardValue,
  hasReward,
}) {
  const translate = useTranslate();

  // Customer has reached reward threshold
  if (hasReward) {
    return (
      <BlockStack
        spacing="tight"
        padding="tight"
        background="success"
        cornerRadius="base"
      >
        <InlineStack spacing="tight" blockAlignment="center">
          <Icon source="checkCircle" appearance="success" />
          <Text emphasis="bold" appearance="success">
            {translate('reward_unlocked')}
          </Text>
        </InlineStack>

        <Text size="small" appearance="success">
          {translate('reward_available', { reward: rewardValue })}
        </Text>
      </BlockStack>
    );
  }

  // Show progress toward next reward
  return (
    <BlockStack spacing="tight">
      <InlineStack spacing="loose" blockAlignment="center" inlineAlignment="spaceBetween">
        <Text size="small" emphasis="bold">
          {translate('next_reward')}
        </Text>
        <Text size="small" appearance="subdued">
          {currentPoints.toLocaleString()} / {threshold.toLocaleString()} {translate('points')}
        </Text>
      </InlineStack>

      <Progress value={progress} />

      <InlineStack spacing="tight" blockAlignment="center">
        {progress >= 75 ? (
          <>
            <Icon source="star" appearance="accent" size="extraSmall" />
            <Text size="small" appearance="accent">
              {translate('almost_there', { points: pointsNeeded.toLocaleString() })}
            </Text>
          </>
        ) : progress >= 50 ? (
          <>
            <Icon source="arrowUp" appearance="info" size="extraSmall" />
            <Text size="small" appearance="subdued">
              {translate('halfway_there', { points: pointsNeeded.toLocaleString() })}
            </Text>
          </>
        ) : (
          <Text size="small" appearance="subdued">
            {translate('points_to_reward', {
              points: pointsNeeded.toLocaleString(),
              reward: rewardValue,
            })}
          </Text>
        )}
      </InlineStack>
    </BlockStack>
  );
}
