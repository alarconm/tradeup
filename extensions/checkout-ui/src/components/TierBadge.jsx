/**
 * TierBadge Component
 *
 * Displays the customer's loyalty tier as a styled badge
 * with appropriate visual treatment for different tier levels.
 */
import {
  InlineStack,
  Text,
  Icon,
  View,
} from '@shopify/ui-extensions-react/checkout';
import { useMemo } from 'react';

/**
 * Map tier names to visual appearance
 * Supports common tier naming conventions
 */
const TIER_STYLES = {
  // Standard tier names
  bronze: { icon: 'star', appearance: 'subdued' },
  silver: { icon: 'star', appearance: 'info' },
  gold: { icon: 'starFilled', appearance: 'accent' },
  platinum: { icon: 'starFilled', appearance: 'success' },
  diamond: { icon: 'diamond', appearance: 'success' },

  // Alternative naming
  basic: { icon: 'star', appearance: 'subdued' },
  standard: { icon: 'star', appearance: 'subdued' },
  premium: { icon: 'starFilled', appearance: 'accent' },
  elite: { icon: 'starFilled', appearance: 'success' },
  vip: { icon: 'crown', appearance: 'success' },

  // Collectibles themed (for sports cards, Pokemon, MTG stores)
  rookie: { icon: 'star', appearance: 'subdued' },
  allstar: { icon: 'starFilled', appearance: 'info' },
  mvp: { icon: 'starFilled', appearance: 'accent' },
  halloffame: { icon: 'trophy', appearance: 'success' },
  legend: { icon: 'trophy', appearance: 'success' },

  // Default for unrecognized tiers
  default: { icon: 'star', appearance: 'info' },
};

/**
 * @param {Object} props
 * @param {string} props.tier - Tier name
 */
export function TierBadge({ tier }) {
  // Get style based on tier name (case-insensitive, no spaces)
  const style = useMemo(() => {
    if (!tier) return TIER_STYLES.default;

    const normalizedTier = tier.toLowerCase().replace(/[\s-_]+/g, '');
    return TIER_STYLES[normalizedTier] || TIER_STYLES.default;
  }, [tier]);

  if (!tier) return null;

  return (
    <View
      padding="extraTight"
      cornerRadius="base"
      border="base"
    >
      <InlineStack
        spacing="extraTight"
        blockAlignment="center"
      >
        <Icon
          source={style.icon}
          appearance={style.appearance}
          size="extraSmall"
        />
        <Text
          size="small"
          emphasis="bold"
          appearance={style.appearance}
        >
          {tier}
        </Text>
      </InlineStack>
    </View>
  );
}
