/**
 * ActionableEmptyState - Contextual empty states with quick actions
 *
 * Provides helpful guidance when pages are empty, with specific
 * actions to help users get started.
 */

import {
  EmptyState,
  Card,
  BlockStack,
  Text,
  Button,
  InlineStack,
  Icon,
  Box,
} from '@shopify/polaris';
import type { IconSource } from '@shopify/polaris';
import {
  PersonAddIcon,
  ExchangeIcon,
  GiftCardIcon,
  ImportIcon,
  LinkIcon,
} from '@shopify/polaris-icons';
import { useNavigate } from 'react-router-dom';

type EmptyStateType =
  | 'members'
  | 'trade-ins'
  | 'promotions'
  | 'tiers'
  | 'products';

interface ActionableEmptyStateProps {
  type: EmptyStateType;
  shop?: string | null;
}

interface EmptyStateConfig {
  heading: string;
  description: string;
  image: string;
  primaryAction: {
    content: string;
    url?: string;
    onClick?: () => void;
  };
  secondaryActions?: Array<{
    content: string;
    url?: string;
    onClick?: () => void;
    icon?: IconSource;
  }>;
  tips?: string[];
}

export function ActionableEmptyState({ type, shop }: ActionableEmptyStateProps) {
  const navigate = useNavigate();

  const configs: Record<EmptyStateType, EmptyStateConfig> = {
    members: {
      heading: 'Start Building Your Loyalty Community',
      description: 'Members earn rewards on purchases and trade-ins. Import existing customers or share your signup link to get started.',
      image: 'https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png',
      primaryAction: {
        content: 'Add Your First Member',
        onClick: () => navigate('/app/members?action=add'),
      },
      secondaryActions: [
        {
          content: 'Import from CSV',
          icon: ImportIcon,
          onClick: () => navigate('/app/members?action=import'),
        },
        {
          content: 'Copy Signup Link',
          icon: LinkIcon,
          onClick: () => {
            const signupUrl = `https://${shop}/pages/membership`;
            navigator.clipboard.writeText(signupUrl);
          },
        },
      ],
      tips: [
        'Members automatically earn rewards when they make purchases',
        'Higher tiers get better trade-in bonuses',
        'Import existing customers to start them at a base tier',
      ],
    },
    'trade-ins': {
      heading: 'Ready to Accept Trade-Ins',
      description: 'Process trade-ins to issue store credit and grow customer loyalty. Members earn bonus credit based on their tier.',
      image: 'https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png',
      primaryAction: {
        content: 'Start a Trade-In',
        onClick: () => navigate('/app/trade-ins/new'),
      },
      secondaryActions: [
        {
          content: 'Configure Categories',
          onClick: () => navigate('/app/trade-ins/categories'),
        },
      ],
      tips: [
        'Set up categories with base values for quick pricing',
        'Members see their tier bonus applied automatically',
        'Issue store credit directly to Shopify balance',
      ],
    },
    promotions: {
      heading: 'Boost Engagement with Promotions',
      description: 'Create limited-time offers to drive trade-ins and purchases. Bonus multipliers and special events keep members engaged.',
      image: 'https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png',
      primaryAction: {
        content: 'Create a Promotion',
        onClick: () => navigate('/app/promotions?action=create'),
      },
      tips: [
        'Double points weekends drive 3x more trade-ins',
        'New member bonuses help with acquisition',
        'Tier upgrade promotions encourage spending',
      ],
    },
    tiers: {
      heading: 'Set Up Membership Tiers',
      description: 'Create tiers with different benefits to reward your best customers. Higher tiers get better trade-in bonuses.',
      image: 'https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png',
      primaryAction: {
        content: 'Create Your First Tier',
        onClick: () => navigate('/app/tiers?action=add'),
      },
      secondaryActions: [
        {
          content: 'Use a Template',
          onClick: () => navigate('/app/onboarding'),
        },
      ],
      tips: [
        'Start with 2-3 tiers (e.g., Bronze, Silver, Gold)',
        'Set trade-in bonuses between 5-20% per tier',
        'Consider minimum spend thresholds for upgrades',
      ],
    },
    products: {
      heading: 'Create Membership Products',
      description: 'Let customers purchase memberships directly from your store. Products link to tiers automatically.',
      image: 'https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png',
      primaryAction: {
        content: 'Launch Product Wizard',
        onClick: () => navigate('/app/products/wizard'),
      },
      tips: [
        'Products are created in draft mode first',
        'Choose from professional templates',
        'Pricing is pulled from your tier settings',
      ],
    },
  };

  const config = configs[type];
  if (!config) return null;

  return (
    <Card>
      <EmptyState
        heading={config.heading}
        image={config.image}
        action={{
          content: config.primaryAction.content,
          onAction: config.primaryAction.onClick,
          url: config.primaryAction.url,
        }}
        secondaryAction={config.secondaryActions?.[0] ? {
          content: config.secondaryActions[0].content,
          onAction: config.secondaryActions[0].onClick,
          url: config.secondaryActions[0].url,
        } : undefined}
      >
        <p>{config.description}</p>
      </EmptyState>

      {/* Tips section */}
      {config.tips && config.tips.length > 0 && (
        <Box paddingInline="600" paddingBlockEnd="400">
          <BlockStack gap="200">
            <Text as="h4" variant="headingSm">Quick Tips</Text>
            <BlockStack gap="100">
              {config.tips.map((tip, index) => (
                <Text key={index} as="p" variant="bodySm" tone="subdued">
                  • {tip}
                </Text>
              ))}
            </BlockStack>
          </BlockStack>
        </Box>
      )}

      {/* Additional actions */}
      {config.secondaryActions && config.secondaryActions.length > 1 && (
        <Box paddingInline="600" paddingBlockEnd="400">
          <InlineStack gap="300">
            {config.secondaryActions.slice(1).map((action, index) => (
              <Button
                key={index}
                variant="plain"
                onClick={action.onClick}
                url={action.url}
              >
                {action.content}
              </Button>
            ))}
          </InlineStack>
        </Box>
      )}
    </Card>
  );
}

// Quick action cards for getting started
interface QuickActionCardProps {
  title: string;
  description: string;
  icon: IconSource;
  onClick: () => void;
  completed?: boolean;
}

export function QuickActionCard({
  title,
  description,
  icon: IconComponent,
  onClick,
  completed = false,
}: QuickActionCardProps) {
  return (
    <Card>
      <div
        onClick={onClick}
        style={{
          cursor: 'pointer',
          opacity: completed ? 0.6 : 1,
        }}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && onClick()}
      >
        <BlockStack gap="200">
          <InlineStack gap="200" blockAlign="center">
            <Icon source={IconComponent} tone={completed ? 'success' : 'base'} />
            <Text as="h3" variant="headingSm">{title}</Text>
          </InlineStack>
          <Text as="p" variant="bodySm" tone="subdued">{description}</Text>
        </BlockStack>
      </div>
    </Card>
  );
}

// Getting started section with multiple quick actions
export function GettingStartedSection() {
  const navigate = useNavigate();

  return (
    <Card>
      <BlockStack gap="400">
        <Text as="h2" variant="headingMd">Getting Started</Text>
        <InlineStack gap="400" wrap>
          <QuickActionCard
            title="Add Members"
            description="Import or add your first loyalty members"
            icon={PersonAddIcon}
            onClick={() => navigate('/app/members?action=add')}
          />
          <QuickActionCard
            title="Process Trade-In"
            description="Accept items and issue store credit"
            icon={ExchangeIcon}
            onClick={() => navigate('/app/trade-ins/new')}
          />
          <QuickActionCard
            title="Create Promotion"
            description="Boost engagement with special offers"
            icon={GiftCardIcon}
            onClick={() => navigate('/app/promotions?action=create')}
          />
        </InlineStack>
      </BlockStack>
    </Card>
  );
}
