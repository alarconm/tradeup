/**
 * PointsEarning Component
 *
 * Shows how many points the customer will earn from
 * completing this purchase, with bonus multiplier highlighting.
 */
import {
  BlockStack,
  InlineStack,
  Text,
  Icon,
  useTranslate,
} from '@shopify/ui-extensions-react/checkout';

/**
 * @param {Object} props
 * @param {number} props.pointsToEarn - Points to be earned on this order
 * @param {number} props.multiplier - Earning multiplier
 * @param {string} props.orderTotal - Order total amount
 * @param {string} props.currencyCode - Currency code (e.g., 'USD')
 */
export function PointsEarning({ pointsToEarn, multiplier, orderTotal, currencyCode }) {
  const translate = useTranslate();

  const formattedPoints = pointsToEarn.toLocaleString();
  const hasBonus = multiplier > 1;

  // Calculate what points would be without bonus for comparison
  const basePoints = hasBonus
    ? Math.floor(pointsToEarn / multiplier)
    : pointsToEarn;
  const bonusPoints = pointsToEarn - basePoints;

  return (
    <BlockStack
      spacing="extraTight"
      padding="tight"
      background="interactive"
      cornerRadius="base"
    >
      <InlineStack spacing="tight" blockAlignment="center">
        <Icon source="gift" appearance="accent" size="small" />
        <Text size="small" emphasis="bold" appearance="accent">
          {translate('earning_this_order')}
        </Text>
      </InlineStack>

      <InlineStack spacing="tight" blockAlignment="baseline">
        <Text emphasis="bold" size="large" appearance="accent">
          +{formattedPoints}
        </Text>
        <Text size="medium" appearance="accent">
          {translate('points')}
        </Text>
      </InlineStack>

      {/* Show bonus breakdown if applicable */}
      {hasBonus && bonusPoints > 0 && (
        <InlineStack spacing="extraTight" blockAlignment="center">
          <Icon source="checkCircle" appearance="success" size="extraSmall" />
          <Text size="small" appearance="success">
            {translate('includes_bonus', {
              bonus: bonusPoints.toLocaleString(),
              multiplier: multiplier,
            })}
          </Text>
        </InlineStack>
      )}
    </BlockStack>
  );
}
