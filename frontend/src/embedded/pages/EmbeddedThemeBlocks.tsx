/**
 * Theme Blocks Installation Wizard
 *
 * Guides users through installing TradeUp theme blocks on their storefront.
 * Shows previews, recommended placements, and tracks installation status.
 */

import { useNavigate } from 'react-router-dom';
import {
  Page,
  Layout,
  Card,
  Text,
  BlockStack,
  InlineStack,
  Button,
  Badge,
  Box,
  Banner,
  Icon,
  Divider,
  List,
} from '@shopify/polaris';
import {
  CheckCircleIcon,
  MinusCircleIcon,
  ExternalIcon,
} from '@shopify/polaris-icons';
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface ThemeBlock {
  id: string;
  name: string;
  description: string;
  installed: boolean;
  recommended_pages: string[];
  preview_image: string;
}

interface ThemeBlocksStatus {
  blocks: ThemeBlock[];
  installed_count: number;
  total_count: number;
  all_installed: boolean;
}

interface ThemeBlocksProps {
  shop: string | null;
}

async function fetchThemeBlocksStatus(shop: string | null): Promise<ThemeBlocksStatus> {
  const response = await authFetch(
    `${getApiUrl()}/setup/theme-blocks/status`,
    shop
  );
  if (!response.ok) throw new Error('Failed to fetch theme blocks status');
  return response.json();
}

async function markBlockInstalled(shop: string | null, blockId: string): Promise<void> {
  const response = await authFetch(
    `${getApiUrl()}/setup/theme-blocks/${blockId}/mark-installed`,
    shop,
    { method: 'POST' }
  );
  if (!response.ok) throw new Error('Failed to mark block as installed');
}

// Block detail content with installation instructions
const BLOCK_DETAILS: Record<string, {
  fullDescription: string;
  benefits: string[];
  installSteps: string[];
  previewDescription: string;
}> = {
  'membership-signup': {
    fullDescription: 'A call-to-action block that encourages visitors to join your loyalty program. Shows membership benefits and a signup button.',
    benefits: [
      'Increase membership signups',
      'Highlight program benefits',
      'Customizable design to match your theme',
    ],
    installSteps: [
      'Go to Online Store > Themes > Customize',
      'Navigate to the page where you want the block',
      'Click "Add section" or "Add block"',
      'Search for "TradeUp" and select "Membership Signup"',
      'Position and customize as needed',
      'Save your changes',
    ],
    previewDescription: 'Shows a card with membership benefits and a "Join Now" button',
  },
  'credit-badge': {
    fullDescription: 'Displays the customer\'s current store credit balance. Great for headers or account pages to remind customers of their available credit.',
    benefits: [
      'Encourage credit redemption',
      'Build customer loyalty',
      'Reduce support inquiries about balance',
    ],
    installSteps: [
      'Go to Online Store > Themes > Customize',
      'Click on your header section',
      'Add the "TradeUp Credit Badge" block',
      'Position it near your cart icon',
      'Save your changes',
    ],
    previewDescription: 'Shows a small badge with credit amount (e.g., "$25.00 Credit")',
  },
  'trade-in-cta': {
    fullDescription: 'A prominent button that links to your trade-in submission form. Encourages customers to trade in their items.',
    benefits: [
      'Drive trade-in submissions',
      'Increase customer engagement',
      'Promote circular economy',
    ],
    installSteps: [
      'Go to Online Store > Themes > Customize',
      'Navigate to your homepage or collection pages',
      'Add the "TradeUp Trade-In CTA" block',
      'Customize the button text and style',
      'Save your changes',
    ],
    previewDescription: 'Shows a button like "Trade In Your Items" with optional icon',
  },
  'refer-friend': {
    fullDescription: 'Enables your referral program by showing customers how to invite friends and earn rewards.',
    benefits: [
      'Grow through word-of-mouth',
      'Reward loyal customers',
      'Track referral success',
    ],
    installSteps: [
      'Go to Online Store > Themes > Customize',
      'Navigate to your account page or thank you page',
      'Add the "TradeUp Refer a Friend" block',
      'Configure referral rewards if needed',
      'Save your changes',
    ],
    previewDescription: 'Shows referral link and reward info for customers',
  },
};

export function EmbeddedThemeBlocks({ shop }: ThemeBlocksProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [expandedBlock, setExpandedBlock] = useState<string | null>(null);

  const { data: status, isLoading } = useQuery({
    queryKey: ['theme-blocks-status', shop],
    queryFn: () => fetchThemeBlocksStatus(shop),
    enabled: !!shop,
  });

  const markInstalledMutation = useMutation({
    mutationFn: (blockId: string) => markBlockInstalled(shop, blockId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['theme-blocks-status', shop] });
      queryClient.invalidateQueries({ queryKey: ['setup-status', shop] });
    },
  });

  const handleOpenThemeEditor = () => {
    // Open Shopify theme editor in new tab
    const shopDomain = shop?.replace('.myshopify.com', '') || '';
    window.open(`https://admin.shopify.com/store/${shopDomain}/themes/current/editor`, '_blank');
  };

  if (isLoading) {
    return (
      <Page title="Theme Blocks" backAction={{ content: 'Dashboard', onAction: () => navigate('/app') }}>
        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <Box background="bg-surface-secondary" borderRadius="100" minHeight="200px" />
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  return (
    <Page
      title="Theme Blocks"
      subtitle="Add TradeUp blocks to your storefront to maximize engagement"
      backAction={{ content: 'Dashboard', onAction: () => navigate('/app') }}
      primaryAction={{
        content: 'Open Theme Editor',
        icon: ExternalIcon,
        onAction: handleOpenThemeEditor,
      }}
    >
      <Layout>
        {/* Progress summary */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between" blockAlign="center">
                <BlockStack gap="100">
                  <Text as="h2" variant="headingMd">Installation Progress</Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    {status?.installed_count || 0} of {status?.total_count || 4} blocks installed
                  </Text>
                </BlockStack>
                {status?.all_installed && (
                  <Badge tone="success">All Installed</Badge>
                )}
              </InlineStack>

              {!status?.all_installed && (
                <Banner tone="info">
                  <p>
                    Theme blocks help customers discover your loyalty program. Install at least one block to complete your setup.
                  </p>
                </Banner>
              )}
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Block cards */}
        {status?.blocks.map((block) => (
          <Layout.Section key={block.id}>
            <ThemeBlockCard
              block={block}
              details={BLOCK_DETAILS[block.id]}
              expanded={expandedBlock === block.id}
              onToggle={() => setExpandedBlock(expandedBlock === block.id ? null : block.id)}
              onMarkInstalled={() => markInstalledMutation.mutate(block.id)}
              onOpenEditor={handleOpenThemeEditor}
              isMarking={markInstalledMutation.isPending}
            />
          </Layout.Section>
        ))}

        {/* Help section */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text as="h3" variant="headingMd">Need Help?</Text>
              <Text as="p" variant="bodyMd" tone="subdued">
                If you're having trouble installing theme blocks, check out our documentation or contact support.
              </Text>
              <InlineStack gap="300">
                <Button url="https://help.cardflowlabs.com/theme-blocks" external>
                  View Documentation
                </Button>
                <Button variant="plain" url="mailto:support@cardflowlabs.com">
                  Contact Support
                </Button>
              </InlineStack>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>
    </Page>
  );
}

interface ThemeBlockCardProps {
  block: ThemeBlock;
  details: typeof BLOCK_DETAILS[string];
  expanded: boolean;
  onToggle: () => void;
  onMarkInstalled: () => void;
  onOpenEditor: () => void;
  isMarking: boolean;
}

function ThemeBlockCard({
  block,
  details,
  expanded,
  onToggle,
  onMarkInstalled,
  onOpenEditor,
  isMarking,
}: ThemeBlockCardProps) {
  return (
    <Card>
      <BlockStack gap="400">
        {/* Header */}
        <InlineStack align="space-between" blockAlign="start">
          <InlineStack gap="300" blockAlign="center">
            <Icon
              source={block.installed ? CheckCircleIcon : MinusCircleIcon}
              tone={block.installed ? 'success' : 'subdued'}
            />
            <BlockStack gap="050">
              <Text as="h3" variant="headingMd">{block.name}</Text>
              <Text as="p" variant="bodySm" tone="subdued">{block.description}</Text>
            </BlockStack>
          </InlineStack>
          <InlineStack gap="200">
            {block.installed ? (
              <Badge tone="success">Installed</Badge>
            ) : (
              <Badge>Not Installed</Badge>
            )}
          </InlineStack>
        </InlineStack>

        {/* Recommended pages */}
        <InlineStack gap="200">
          <Text as="span" variant="bodySm" fontWeight="semibold">Recommended for:</Text>
          <InlineStack gap="100">
            {block.recommended_pages.map((page) => (
              <Badge key={page} tone="info">{page}</Badge>
            ))}
          </InlineStack>
        </InlineStack>

        {/* Expand/collapse toggle */}
        <Button variant="plain" onClick={onToggle}>
          {expanded ? 'Hide installation guide' : 'Show installation guide'}
        </Button>

        {/* Expanded content */}
        {expanded && details && (
          <Box paddingBlockStart="200">
            <Divider />
            <Box paddingBlockStart="400">
              <BlockStack gap="400">
                {/* Full description */}
                <BlockStack gap="200">
                  <Text as="h4" variant="headingSm">About this block</Text>
                  <Text as="p" variant="bodyMd">{details.fullDescription}</Text>
                </BlockStack>

                {/* Benefits */}
                <BlockStack gap="200">
                  <Text as="h4" variant="headingSm">Benefits</Text>
                  <List>
                    {details.benefits.map((benefit, i) => (
                      <List.Item key={i}>{benefit}</List.Item>
                    ))}
                  </List>
                </BlockStack>

                {/* Installation steps */}
                <BlockStack gap="200">
                  <Text as="h4" variant="headingSm">Installation Steps</Text>
                  <List type="number">
                    {details.installSteps.map((step, i) => (
                      <List.Item key={i}>{step}</List.Item>
                    ))}
                  </List>
                </BlockStack>

                {/* Action buttons */}
                <InlineStack gap="300">
                  <Button variant="primary" icon={ExternalIcon} onClick={onOpenEditor}>
                    Open Theme Editor
                  </Button>
                  {!block.installed && (
                    <Button
                      onClick={onMarkInstalled}
                      loading={isMarking}
                      icon={CheckCircleIcon}
                    >
                      Mark as Installed
                    </Button>
                  )}
                </InlineStack>
              </BlockStack>
            </Box>
          </Box>
        )}
      </BlockStack>
    </Card>
  );
}
