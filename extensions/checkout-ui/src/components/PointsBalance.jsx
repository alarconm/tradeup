/**
 * PointsBalance Component
 *
 * Displays the customer's current points balance with
 * optional earning multiplier indicator.
 */
import {
  BlockStack,
  InlineStack,
  Text,
  useTranslate,
} from '@shopify/ui-extensions-react/checkout';

/**
 * @param {Object} props
 * @param {number} props.balance - Current points balance
 * @param {number} props.multiplier - Earning multiplier (e.g., 1.5 for 1.5x)
 */
export function PointsBalance({ balance, multiplier }) {
  const translate = useTranslate();

  const formattedBalance = balance.toLocaleString();
  const hasBonus = multiplier > 1;

  return (
    <BlockStack spacing="extraTight">
      <InlineStack spacing="tight" blockAlignment="center">
        <Text size="small" appearance="subdued">
          {translate('current_balance')}
        </Text>
      </InlineStack>

      <InlineStack spacing="tight" blockAlignment="baseline">
        <Text emphasis="bold" size="large">
          {formattedBalance}
        </Text>
        <Text size="medium" appearance="subdued">
          {translate('points')}
        </Text>

        {hasBonus && (
          <InlineStack spacing="extraTight" blockAlignment="center">
            <Text
              size="small"
              appearance="success"
              emphasis="bold"
            >
              {multiplier}x
            </Text>
            <Text size="small" appearance="success">
              {translate('earning_rate')}
            </Text>
          </InlineStack>
        )}
      </InlineStack>
    </BlockStack>
  );
}
