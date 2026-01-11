/**
 * OnboardingTooltips - Contextual help for first-time users
 *
 * Shows helpful hints and guidance throughout the app.
 * Tooltips are dismissable and won't show again once dismissed.
 */

import {
  Popover,
  ActionList,
  Button,
  BlockStack,
  Text,
  InlineStack,
  Box,
  Badge,
  Icon,
} from '@shopify/polaris';
import {
  QuestionCircleIcon,
  XIcon,
  LightbulbIcon,
} from '@shopify/polaris-icons';
import { useState, createContext, useContext } from 'react';
import type { ReactNode } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

// Tooltip definitions
interface TooltipDefinition {
  id: string;
  title: string;
  content: string;
  target: string; // CSS selector or area name
  position?: 'above' | 'below' | 'left' | 'right';
}

const TOOLTIPS: TooltipDefinition[] = [
  {
    id: 'dashboard-members',
    title: 'Member Overview',
    content: 'Click here to view all your loyalty members. You can add members manually or they can sign up through your storefront.',
    target: 'members-card',
  },
  {
    id: 'dashboard-trade-ins',
    title: 'Trade-In Processing',
    content: 'Process trade-ins here to issue store credit. Members automatically get their tier bonus applied.',
    target: 'trade-ins-card',
  },
  {
    id: 'tier-bonus',
    title: 'Trade-In Bonus Rate',
    content: 'This percentage bonus is added to all trade-ins for members of this tier. Higher tiers should have higher bonuses to incentivize loyalty.',
    target: 'tier-bonus-input',
  },
  {
    id: 'store-credit',
    title: 'Store Credit Balance',
    content: 'This shows the total store credit you\'ve issued. It syncs with Shopify\'s native store credit system.',
    target: 'store-credit-card',
  },
  {
    id: 'product-wizard',
    title: 'Membership Products',
    content: 'Create products that customers can purchase to join specific membership tiers. Great for paid VIP programs.',
    target: 'product-wizard-link',
  },
];

// Context for managing tooltip state
interface TooltipContextType {
  dismissedTooltips: string[];
  dismissTooltip: (id: string) => void;
  isTooltipDismissed: (id: string) => boolean;
  showTooltip: (id: string) => boolean;
}

const TooltipContext = createContext<TooltipContextType>({
  dismissedTooltips: [],
  dismissTooltip: () => {},
  isTooltipDismissed: () => false,
  showTooltip: () => true,
});

// Provider component
interface TooltipProviderProps {
  children: ReactNode;
  shop: string | null;
}

async function fetchDismissedTooltips(shop: string | null): Promise<string[]> {
  const response = await authFetch(
    `${getApiUrl()}/setup/tooltips/dismissed`,
    shop
  );
  if (!response.ok) return [];
  const data = await response.json();
  return data.dismissed || [];
}

async function dismissTooltipApi(shop: string | null, tooltipId: string): Promise<void> {
  await authFetch(
    `${getApiUrl()}/setup/tooltips/${tooltipId}/dismiss`,
    shop,
    { method: 'POST' }
  );
}

export function TooltipProvider({ children, shop }: TooltipProviderProps) {
  const queryClient = useQueryClient();

  const { data: dismissedTooltips = [] } = useQuery({
    queryKey: ['dismissed-tooltips', shop],
    queryFn: () => fetchDismissedTooltips(shop),
    enabled: !!shop,
    staleTime: Infinity, // These rarely change
  });

  const dismissMutation = useMutation({
    mutationFn: (tooltipId: string) => dismissTooltipApi(shop, tooltipId),
    onMutate: async (tooltipId) => {
      // Optimistic update
      await queryClient.cancelQueries({ queryKey: ['dismissed-tooltips', shop] });
      const previous = queryClient.getQueryData<string[]>(['dismissed-tooltips', shop]);
      queryClient.setQueryData(['dismissed-tooltips', shop], [...(previous || []), tooltipId]);
      return { previous };
    },
    onError: (err, tooltipId, context) => {
      queryClient.setQueryData(['dismissed-tooltips', shop], context?.previous);
    },
  });

  const isTooltipDismissed = (id: string) => dismissedTooltips.includes(id);
  const showTooltip = (id: string) => !isTooltipDismissed(id);

  return (
    <TooltipContext.Provider
      value={{
        dismissedTooltips,
        dismissTooltip: (id) => dismissMutation.mutate(id),
        isTooltipDismissed,
        showTooltip,
      }}
    >
      {children}
    </TooltipContext.Provider>
  );
}

// Hook to use tooltip context
// eslint-disable-next-line react-refresh/only-export-components
export function useTooltips() {
  return useContext(TooltipContext);
}

// Inline help tooltip component
interface HelpTooltipProps {
  id: string;
  children: ReactNode;
}

export function HelpTooltip({ id, children }: HelpTooltipProps) {
  const { showTooltip, dismissTooltip } = useTooltips();
  const [active, setActive] = useState(false);

  const tooltipDef = TOOLTIPS.find((t) => t.id === id);
  if (!tooltipDef || !showTooltip(id)) {
    return <>{children}</>;
  }

  return (
    <Popover
      active={active}
      activator={
        <div
          style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
          onMouseEnter={() => setActive(true)}
          onMouseLeave={() => setActive(false)}
        >
          {children}
          <Icon source={QuestionCircleIcon} tone="subdued" />
        </div>
      }
      onClose={() => setActive(false)}
      preferredPosition="above"
    >
      <Box padding="400" maxWidth="300px">
        <BlockStack gap="200">
          <InlineStack align="space-between">
            <Text as="h4" variant="headingSm">{tooltipDef.title}</Text>
            <Button
              variant="plain"
              icon={XIcon}
              onClick={() => {
                dismissTooltip(id);
                setActive(false);
              }}
              accessibilityLabel="Dismiss tip"
            />
          </InlineStack>
          <Text as="p" variant="bodySm">{tooltipDef.content}</Text>
        </BlockStack>
      </Box>
    </Popover>
  );
}

// Spotlight tooltip (more prominent, for key areas)
interface SpotlightTooltipProps {
  id: string;
  children: ReactNode;
}

export function SpotlightTooltip({ id, children }: SpotlightTooltipProps) {
  const { showTooltip, dismissTooltip } = useTooltips();
  const [visible, setVisible] = useState(true);

  const tooltipDef = TOOLTIPS.find((t) => t.id === id);
  if (!tooltipDef || !showTooltip(id) || !visible) {
    return <>{children}</>;
  }

  return (
    <div style={{ position: 'relative' }}>
      {children}
      <div
        style={{
          position: 'absolute',
          top: '100%',
          left: '50%',
          transform: 'translateX(-50%)',
          marginTop: '8px',
          backgroundColor: '#1a1a1a',
          color: 'white',
          padding: '12px 16px',
          borderRadius: '8px',
          maxWidth: '280px',
          zIndex: 1000,
          boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
        }}
      >
        <BlockStack gap="200">
          <InlineStack gap="200" blockAlign="center">
            <Icon source={LightbulbIcon} tone="warning" />
            <Text as="span" variant="headingSm">{tooltipDef.title}</Text>
          </InlineStack>
          <Text as="p" variant="bodySm">{tooltipDef.content}</Text>
          <Button
            variant="plain"
            tone="critical"
            onClick={() => {
              dismissTooltip(id);
              setVisible(false);
            }}
          >
            Got it
          </Button>
        </BlockStack>
        {/* Arrow */}
        <div
          style={{
            position: 'absolute',
            top: '-6px',
            left: '50%',
            transform: 'translateX(-50%)',
            width: 0,
            height: 0,
            borderLeft: '6px solid transparent',
            borderRight: '6px solid transparent',
            borderBottom: '6px solid #1a1a1a',
          }}
        />
      </div>
    </div>
  );
}

// Feature highlight badge
interface FeatureHighlightProps {
  id: string;
  label?: string;
}

export function FeatureHighlight({ id, label = 'New' }: FeatureHighlightProps) {
  const { showTooltip } = useTooltips();

  if (!showTooltip(id)) {
    return null;
  }

  return (
    <Badge
      tone="attention"
      progress="complete"
    >
      {label}
    </Badge>
  );
}

// All tips modal for users who want to see all tips
interface AllTipsModalProps {
  open: boolean;
  onClose: () => void;
}

export function AllTipsModal({ open, onClose }: AllTipsModalProps) {
  return (
    <Popover
      active={open}
      activator={<span />}
      onClose={onClose}
    >
      <ActionList
        items={TOOLTIPS.map((tip) => ({
          content: tip.title,
          helpText: tip.content,
        }))}
      />
    </Popover>
  );
}
