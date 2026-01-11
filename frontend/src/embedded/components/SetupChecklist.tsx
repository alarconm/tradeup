/**
 * SetupChecklist - Visual progress tracker for store setup
 *
 * Shows completion status for all setup steps with actionable links.
 * Includes milestone celebrations for achievements.
 */

import {
  Card,
  BlockStack,
  InlineStack,
  Text,
  ProgressBar,
  Icon,
  Button,
  Badge,
  Box,
  Collapsible,
  Banner,
} from '@shopify/polaris';
import {
  CheckCircleIcon,
  MinusCircleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  StarFilledIcon,
} from '@shopify/polaris-icons';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface ChecklistItem {
  id: string;
  title: string;
  description: string;
  completed: boolean;
  fully_complete?: boolean;
  action_url: string;
  action_label: string;
  priority: number;
  category: string;
  depends_on?: string;
}

interface Milestone {
  id?: string;
  achieved: boolean;
  celebrated: boolean;
  title: string;
  message: string;
  icon: string;
}

interface SetupStatus {
  checklist: ChecklistItem[];
  completion: {
    setup_percentage: number;
    setup_completed: number;
    setup_total: number;
    all_complete: boolean;
  };
  next_action: ChecklistItem | null;
  milestones: Record<string, Milestone>;
  uncelebrated_milestones: Array<Milestone & { id: string }>;
}

interface SetupChecklistProps {
  shop: string | null;
  compact?: boolean;
  onMilestoneShow?: (milestone: Milestone & { id: string }) => void;
}

async function fetchSetupStatus(shop: string | null): Promise<SetupStatus> {
  const response = await authFetch(
    `${getApiUrl()}/setup/status`,
    shop
  );
  if (!response.ok) throw new Error('Failed to fetch setup status');
  return response.json();
}

async function celebrateMilestone(shop: string | null, milestoneId: string): Promise<void> {
  const response = await authFetch(
    `${getApiUrl()}/setup/milestones/${milestoneId}/celebrate`,
    shop,
    { method: 'POST' }
  );
  if (!response.ok) throw new Error('Failed to mark milestone as celebrated');
}

export function SetupChecklist({ shop, compact = false, onMilestoneShow }: SetupChecklistProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(!compact);
  const [showingMilestone, setShowingMilestone] = useState<(Milestone & { id: string }) | null>(null);

  const { data: status, isLoading } = useQuery({
    queryKey: ['setup-status', shop],
    queryFn: () => fetchSetupStatus(shop),
    enabled: !!shop,
    staleTime: 30000,
  });

  const celebrateMutation = useMutation({
    mutationFn: (milestoneId: string) => celebrateMilestone(shop, milestoneId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['setup-status', shop] });
    },
  });

  // Show uncelebrated milestones
  useEffect(() => {
    if (status?.uncelebrated_milestones && status.uncelebrated_milestones.length > 0) {
      const milestone = status.uncelebrated_milestones[0];
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setShowingMilestone(milestone);
      if (onMilestoneShow) {
        onMilestoneShow(milestone);
      }
    }
  }, [status?.uncelebrated_milestones, onMilestoneShow]);

  const handleDismissMilestone = () => {
    if (showingMilestone) {
      celebrateMutation.mutate(showingMilestone.id);
      setShowingMilestone(null);
    }
  };

  if (isLoading || !status) {
    return (
      <Card>
        <BlockStack gap="400">
          <Text as="h3" variant="headingMd">Setup Progress</Text>
          <Box background="bg-surface-secondary" borderRadius="100" minHeight="8px" />
          <Box background="bg-surface-secondary" borderRadius="100" minHeight="40px" />
        </BlockStack>
      </Card>
    );
  }

  // If all setup is complete, show minimal view
  if (status.completion.all_complete && compact) {
    return null; // Hide completely in compact mode when done
  }

  const setupItems = status.checklist.filter(item => item.category === 'setup');
  const milestoneItems = status.checklist.filter(item => item.category === 'milestone');

  // Get progress color
  const getProgressTone = (percentage: number) => {
    if (percentage === 100) return 'success';
    if (percentage >= 60) return 'highlight';
    return 'primary';
  };

  return (
    <Card>
      <BlockStack gap="400">
        {/* Header with progress */}
        <InlineStack align="space-between" blockAlign="center">
          <BlockStack gap="100">
            <Text as="h3" variant="headingMd">
              {status.completion.all_complete ? 'Setup Complete!' : 'Setup Progress'}
            </Text>
            <Text as="p" variant="bodySm" tone="subdued">
              {status.completion.setup_completed} of {status.completion.setup_total} steps completed
            </Text>
          </BlockStack>
          <InlineStack gap="200" blockAlign="center">
            <Text as="span" variant="headingLg" fontWeight="bold">
              {status.completion.setup_percentage}%
            </Text>
            {compact && (
              <Button
                variant="plain"
                onClick={() => setExpanded(!expanded)}
                icon={expanded ? ChevronUpIcon : ChevronDownIcon}
                accessibilityLabel={expanded ? 'Collapse' : 'Expand'}
              />
            )}
          </InlineStack>
        </InlineStack>

        <ProgressBar
          progress={status.completion.setup_percentage}
          size="small"
          tone={getProgressTone(status.completion.setup_percentage)}
        />

        {/* Milestone celebration banner */}
        {showingMilestone && (
          <Banner
            title={showingMilestone.title}
            tone="success"
            onDismiss={handleDismissMilestone}
            icon={StarFilledIcon}
          >
            <p>{showingMilestone.message}</p>
          </Banner>
        )}

        {/* Collapsible checklist */}
        <Collapsible open={expanded || !compact} id="setup-checklist">
          <BlockStack gap="300">
            {/* Setup items */}
            {setupItems.map((item) => (
              <ChecklistItemRow
                key={item.id}
                item={item}
                onAction={() => navigate(item.action_url)}
              />
            ))}

            {/* Milestone items (optional display) */}
            {!compact && milestoneItems.length > 0 && (
              <>
                <Box paddingBlockStart="200">
                  <Text as="h4" variant="headingSm" tone="subdued">
                    Milestones
                  </Text>
                </Box>
                {milestoneItems.map((item) => (
                  <ChecklistItemRow
                    key={item.id}
                    item={item}
                    onAction={() => navigate(item.action_url)}
                    isMilestone
                  />
                ))}
              </>
            )}
          </BlockStack>
        </Collapsible>

        {/* Next action prompt */}
        {!status.completion.all_complete && status.next_action && compact && !expanded && (
          <Box paddingBlockStart="200">
            <Button
              variant="primary"
              onClick={() => navigate(status.next_action!.action_url)}
            >
              {status.next_action.action_label}
            </Button>
          </Box>
        )}
      </BlockStack>
    </Card>
  );
}

interface ChecklistItemRowProps {
  item: ChecklistItem;
  onAction: () => void;
  isMilestone?: boolean;
}

function ChecklistItemRow({ item, onAction, isMilestone = false }: ChecklistItemRowProps) {
  return (
    <Box
      paddingBlock="200"
      paddingInline="100"
      borderRadius="200"
      background={item.completed ? 'bg-surface-success' : undefined}
    >
      <InlineStack align="space-between" blockAlign="center" gap="400">
        <InlineStack gap="300" blockAlign="center">
          <Box>
            <Icon
              source={item.completed ? CheckCircleIcon : MinusCircleIcon}
              tone={item.completed ? 'success' : 'subdued'}
            />
          </Box>
          <BlockStack gap="050">
            <InlineStack gap="200" blockAlign="center">
              <Text
                as="span"
                variant="bodyMd"
                fontWeight={item.completed ? 'regular' : 'semibold'}
                tone={item.completed ? 'subdued' : undefined}
              >
                {item.title}
              </Text>
              {item.fully_complete === false && item.completed && (
                <Badge tone="attention">Partial</Badge>
              )}
              {isMilestone && item.completed && (
                <Badge tone="success">Achieved</Badge>
              )}
            </InlineStack>
            <Text as="span" variant="bodySm" tone="subdued">
              {item.description}
            </Text>
          </BlockStack>
        </InlineStack>
        {!item.completed && (
          <Button size="slim" onClick={onAction}>
            {item.action_label}
          </Button>
        )}
      </InlineStack>
    </Box>
  );
}

// Compact version for dashboard sidebar
export function SetupChecklistCompact({ shop }: { shop: string | null }) {
  return <SetupChecklist shop={shop} compact />;
}
