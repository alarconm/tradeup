/**
 * Gamification Page
 *
 * Manage badges, achievements, streaks, and milestones
 * to engage and reward loyal customers.
 */

import React, { useState } from 'react';
import {
  Page,
  Layout,
  Card,
  Text,
  Badge,
  Button,
  Modal,
  TextField,
  Select,
  FormLayout,
  DataTable,
  Banner,
  BlockStack,
  InlineStack,
  ProgressBar,
  Spinner,
  Icon,
  Tabs,
  Thumbnail,
  EmptyState,
} from '@shopify/polaris';
import {
  StarFilledIcon,
  StarIcon,
  ClockIcon,
  CheckCircleIcon,
} from '@shopify/polaris-icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface EmbeddedGamificationProps {
  shop: string | null;
}

interface BadgeData {
  id: number;
  name: string;
  description: string;
  icon: string;
  color: string;
  criteria_type: string;
  criteria_value: number;
  points_reward: number;
  credit_reward: number;
  is_active: boolean;
  is_secret: boolean;
  display_order: number;
}

interface MilestoneData {
  id: number;
  name: string;
  description: string;
  milestone_type: string;
  threshold: number;
  points_reward: number;
  credit_reward: number;
  celebration_message: string;
  is_active: boolean;
}

interface GamificationStats {
  total_badges: number;
  total_milestones: number;
  total_badges_earned: number;
}

interface BadgeForm {
  name: string;
  description: string;
  icon: string;
  color: string;
  criteria_type: string;
  criteria_value: string;
  points_reward: string;
  credit_reward: string;
  is_secret: boolean;
}

interface MilestoneForm {
  name: string;
  description: string;
  milestone_type: string;
  threshold: string;
  points_reward: string;
  credit_reward: string;
  celebration_message: string;
}

const initialBadgeForm: BadgeForm = {
  name: '',
  description: '',
  icon: 'trophy',
  color: '#e85d27',
  criteria_type: 'first_purchase',
  criteria_value: '1',
  points_reward: '0',
  credit_reward: '0',
  is_secret: false,
};

const initialMilestoneForm: MilestoneForm = {
  name: '',
  description: '',
  milestone_type: 'points_earned',
  threshold: '100',
  points_reward: '0',
  credit_reward: '0',
  celebration_message: '',
};

const CRITERIA_TYPES = [
  { label: 'First Purchase', value: 'first_purchase' },
  { label: 'Trade-In Count', value: 'trade_in_count' },
  { label: 'Points Earned', value: 'points_earned' },
  { label: 'Referral Count', value: 'referral_count' },
  { label: 'Tier Reached', value: 'tier_reached' },
  { label: 'Streak Days', value: 'streak_days' },
  { label: 'Total Spent', value: 'total_spent' },
  { label: 'Member Anniversary', value: 'member_anniversary' },
];

const MILESTONE_TYPES = [
  { label: 'Points Earned', value: 'points_earned' },
  { label: 'Trade-Ins Completed', value: 'trade_ins_completed' },
  { label: 'Referrals Made', value: 'referrals_made' },
  { label: 'Total Spent', value: 'total_spent' },
  { label: 'Days as Member', value: 'member_days' },
];

const ICON_OPTIONS = [
  { label: 'Trophy', value: 'trophy' },
  { label: 'Star', value: 'star' },
  { label: 'Medal', value: 'medal' },
  { label: 'Fire', value: 'fire' },
  { label: 'Heart', value: 'heart' },
  { label: 'Gift', value: 'gift' },
  { label: 'Crown', value: 'crown' },
  { label: 'Lightning', value: 'lightning' },
];

async function fetchBadges(shop: string | null): Promise<{ badges: BadgeData[] }> {
  const response = await authFetch(`${getApiUrl()}/gamification/badges?include_inactive=true`, shop);
  if (!response.ok) throw new Error('Failed to fetch badges');
  return response.json();
}

async function fetchMilestones(shop: string | null): Promise<{ milestones: MilestoneData[] }> {
  const response = await authFetch(`${getApiUrl()}/gamification/milestones?include_inactive=true`, shop);
  if (!response.ok) throw new Error('Failed to fetch milestones');
  return response.json();
}

async function fetchStats(shop: string | null): Promise<{ stats: GamificationStats }> {
  const response = await authFetch(`${getApiUrl()}/gamification/stats`, shop);
  if (!response.ok) throw new Error('Failed to fetch stats');
  return response.json();
}

async function initializeDefaults(shop: string | null): Promise<{ badges_created: number; milestones_created: number }> {
  const response = await authFetch(`${getApiUrl()}/gamification/initialize`, shop, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to initialize defaults');
  return response.json();
}

export function EmbeddedGamification({ shop }: EmbeddedGamificationProps) {
  const [selectedTab, setSelectedTab] = useState(0);
  const [showBadgeModal, setShowBadgeModal] = useState(false);
  const [showMilestoneModal, setShowMilestoneModal] = useState(false);
  const [badgeForm, setBadgeForm] = useState<BadgeForm>(initialBadgeForm);
  const [milestoneForm, setMilestoneForm] = useState<MilestoneForm>(initialMilestoneForm);
  const [editingBadge, setEditingBadge] = useState<BadgeData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const queryClient = useQueryClient();

  const { data: badgesData, isLoading: loadingBadges } = useQuery({
    queryKey: ['gamification-badges', shop],
    queryFn: () => fetchBadges(shop),
    enabled: !!shop,
  });

  const { data: milestonesData, isLoading: loadingMilestones } = useQuery({
    queryKey: ['gamification-milestones', shop],
    queryFn: () => fetchMilestones(shop),
    enabled: !!shop,
  });

  const { data: statsData } = useQuery({
    queryKey: ['gamification-stats', shop],
    queryFn: () => fetchStats(shop),
    enabled: !!shop,
  });

  const createBadgeMutation = useMutation({
    mutationFn: async (badge: BadgeForm) => {
      const response = await authFetch(`${getApiUrl()}/gamification/badges`, shop, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: badge.name,
          description: badge.description,
          icon: badge.icon,
          color: badge.color,
          criteria_type: badge.criteria_type,
          criteria_value: parseInt(badge.criteria_value),
          points_reward: parseInt(badge.points_reward),
          credit_reward: parseFloat(badge.credit_reward),
          is_secret: badge.is_secret,
        }),
      });
      if (!response.ok) throw new Error('Failed to create badge');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gamification-badges', shop] });
      queryClient.invalidateQueries({ queryKey: ['gamification-stats', shop] });
      setShowBadgeModal(false);
      setBadgeForm(initialBadgeForm);
      setEditingBadge(null);
    },
    onError: (err) => setError(err.message),
  });

  const updateBadgeMutation = useMutation({
    mutationFn: async ({ id, badge }: { id: number; badge: BadgeForm }) => {
      const response = await authFetch(`${getApiUrl()}/gamification/badges/${id}`, shop, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: badge.name,
          description: badge.description,
          icon: badge.icon,
          color: badge.color,
          criteria_type: badge.criteria_type,
          criteria_value: parseInt(badge.criteria_value),
          points_reward: parseInt(badge.points_reward),
          credit_reward: parseFloat(badge.credit_reward),
          is_secret: badge.is_secret,
        }),
      });
      if (!response.ok) throw new Error('Failed to update badge');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gamification-badges', shop] });
      setShowBadgeModal(false);
      setBadgeForm(initialBadgeForm);
      setEditingBadge(null);
    },
    onError: (err) => setError(err.message),
  });

  const deleteBadgeMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await authFetch(`${getApiUrl()}/gamification/badges/${id}`, shop, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete badge');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gamification-badges', shop] });
      queryClient.invalidateQueries({ queryKey: ['gamification-stats', shop] });
    },
  });

  const createMilestoneMutation = useMutation({
    mutationFn: async (milestone: MilestoneForm) => {
      const response = await authFetch(`${getApiUrl()}/gamification/milestones`, shop, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: milestone.name,
          description: milestone.description,
          milestone_type: milestone.milestone_type,
          threshold: parseInt(milestone.threshold),
          points_reward: parseInt(milestone.points_reward),
          credit_reward: parseFloat(milestone.credit_reward),
          celebration_message: milestone.celebration_message,
        }),
      });
      if (!response.ok) throw new Error('Failed to create milestone');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gamification-milestones', shop] });
      queryClient.invalidateQueries({ queryKey: ['gamification-stats', shop] });
      setShowMilestoneModal(false);
      setMilestoneForm(initialMilestoneForm);
    },
    onError: (err) => setError(err.message),
  });

  const initializeMutation = useMutation({
    mutationFn: () => initializeDefaults(shop),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gamification-badges', shop] });
      queryClient.invalidateQueries({ queryKey: ['gamification-milestones', shop] });
      queryClient.invalidateQueries({ queryKey: ['gamification-stats', shop] });
    },
    onError: (err) => setError(err.message),
  });

  const handleEditBadge = (badge: BadgeData) => {
    setEditingBadge(badge);
    setBadgeForm({
      name: badge.name,
      description: badge.description || '',
      icon: badge.icon,
      color: badge.color,
      criteria_type: badge.criteria_type,
      criteria_value: String(badge.criteria_value),
      points_reward: String(badge.points_reward),
      credit_reward: String(badge.credit_reward),
      is_secret: badge.is_secret,
    });
    setShowBadgeModal(true);
  };

  const handleBadgeSubmit = () => {
    if (!badgeForm.name || !badgeForm.criteria_type) {
      setError('Please fill in all required fields');
      return;
    }
    if (editingBadge) {
      updateBadgeMutation.mutate({ id: editingBadge.id, badge: badgeForm });
    } else {
      createBadgeMutation.mutate(badgeForm);
    }
  };

  const handleMilestoneSubmit = () => {
    if (!milestoneForm.name || !milestoneForm.milestone_type || !milestoneForm.threshold) {
      setError('Please fill in all required fields');
      return;
    }
    createMilestoneMutation.mutate(milestoneForm);
  };

  const badges = badgesData?.badges || [];
  const milestones = milestonesData?.milestones || [];
  const stats = statsData?.stats || { total_badges: 0, total_milestones: 0, total_badges_earned: 0 };

  const tabs = [
    { id: 'badges', content: 'Badges', panelID: 'badges-panel' },
    { id: 'milestones', content: 'Milestones', panelID: 'milestones-panel' },
    { id: 'overview', content: 'Overview', panelID: 'overview-panel' },
  ];

  const isLoading = loadingBadges || loadingMilestones;

  if (isLoading) {
    return (
      <Page title="Gamification">
        <Card>
          <BlockStack gap="200" inlineAlign="center">
            <Spinner size="large" />
            <Text as="p">Loading gamification data...</Text>
          </BlockStack>
        </Card>
      </Page>
    );
  }

  const badgeRows = badges.map((badge) => [
    <InlineStack gap="200" blockAlign="center" key={badge.id}>
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: '50%',
          background: badge.color,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white',
          fontSize: '16px',
        }}
      >
        {badge.icon === 'trophy' ? <Icon source={StarFilledIcon} /> : badge.icon.charAt(0).toUpperCase()}
      </div>
      <Text as="span" variant="bodyMd" fontWeight="semibold">{badge.name}</Text>
    </InlineStack>,
    badge.description || '-',
    CRITERIA_TYPES.find((c) => c.value === badge.criteria_type)?.label || badge.criteria_type,
    `${badge.criteria_value}`,
    badge.points_reward > 0 ? `${badge.points_reward} pts` : '-',
    badge.credit_reward > 0 ? `$${badge.credit_reward}` : '-',
    badge.is_active ? <Badge tone="success">Active</Badge> : <Badge>Inactive</Badge>,
    <InlineStack gap="100" key={`actions-${badge.id}`}>
      <Button size="slim" onClick={() => handleEditBadge(badge)}>Edit</Button>
      <Button
        size="slim"
        tone="critical"
        onClick={() => deleteBadgeMutation.mutate(badge.id)}
        loading={deleteBadgeMutation.isPending}
      >
        Delete
      </Button>
    </InlineStack>,
  ]);

  const milestoneRows = milestones.map((milestone) => [
    milestone.name,
    milestone.description || '-',
    MILESTONE_TYPES.find((m) => m.value === milestone.milestone_type)?.label || milestone.milestone_type,
    `${milestone.threshold}`,
    milestone.points_reward > 0 ? `${milestone.points_reward} pts` : '-',
    milestone.credit_reward > 0 ? `$${milestone.credit_reward}` : '-',
    milestone.is_active ? <Badge tone="success">Active</Badge> : <Badge>Inactive</Badge>,
  ]);

  return (
    <Page
      title="Gamification"
      subtitle="Engage customers with badges, achievements, and milestones"
    >
      <Layout>
        <Layout.Section>
          <Card>
            <Tabs tabs={tabs} selected={selectedTab} onSelect={setSelectedTab}>
              {/* Badges Tab */}
              {selectedTab === 0 && (
                <BlockStack gap="400">
                  <InlineStack align="space-between">
                    <Text as="h3" variant="headingMd">Badges ({badges.length})</Text>
                    <InlineStack gap="200">
                      {badges.length === 0 && (
                        <Button
                          onClick={() => initializeMutation.mutate()}
                          loading={initializeMutation.isPending}
                        >
                          Load Default Badges
                        </Button>
                      )}
                      <Button variant="primary" onClick={() => setShowBadgeModal(true)}>
                        Create Badge
                      </Button>
                    </InlineStack>
                  </InlineStack>

                  {badges.length === 0 ? (
                    <EmptyState
                      heading="No badges created yet"
                      action={{
                        content: 'Load Default Badges',
                        onAction: () => initializeMutation.mutate(),
                      }}
                      secondaryAction={{
                        content: 'Create Custom Badge',
                        onAction: () => setShowBadgeModal(true),
                      }}
                      image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                    >
                      <Text as="p">Start by loading our default badges or create your own custom achievements.</Text>
                    </EmptyState>
                  ) : (
                    <DataTable
                      columnContentTypes={['text', 'text', 'text', 'numeric', 'text', 'text', 'text', 'text']}
                      headings={['Badge', 'Description', 'Criteria', 'Value', 'Points', 'Credit', 'Status', 'Actions']}
                      rows={badgeRows}
                    />
                  )}
                </BlockStack>
              )}

              {/* Milestones Tab */}
              {selectedTab === 1 && (
                <BlockStack gap="400">
                  <InlineStack align="space-between">
                    <Text as="h3" variant="headingMd">Milestones ({milestones.length})</Text>
                    <Button variant="primary" onClick={() => setShowMilestoneModal(true)}>
                      Create Milestone
                    </Button>
                  </InlineStack>

                  {milestones.length === 0 ? (
                    <EmptyState
                      heading="No milestones created yet"
                      action={{
                        content: 'Create Milestone',
                        onAction: () => setShowMilestoneModal(true),
                      }}
                      image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                    >
                      <Text as="p">Create milestones to celebrate customer achievements like reaching 1000 points.</Text>
                    </EmptyState>
                  ) : (
                    <DataTable
                      columnContentTypes={['text', 'text', 'text', 'numeric', 'text', 'text', 'text']}
                      headings={['Milestone', 'Description', 'Type', 'Threshold', 'Points', 'Credit', 'Status']}
                      rows={milestoneRows}
                    />
                  )}
                </BlockStack>
              )}

              {/* Overview Tab */}
              {selectedTab === 2 && (
                <BlockStack gap="400">
                  <Text as="h3" variant="headingMd">Program Overview</Text>
                  <InlineStack gap="400" wrap={false}>
                    <Card>
                      <BlockStack gap="200" inlineAlign="center">
                        <Icon source={StarFilledIcon} />
                        <Text as="p" variant="headingLg">{`${stats.total_badges}`}</Text>
                        <Text as="p" variant="bodyMd" tone="subdued">Total Badges</Text>
                      </BlockStack>
                    </Card>
                    <Card>
                      <BlockStack gap="200" inlineAlign="center">
                        <Icon source={StarIcon} />
                        <Text as="p" variant="headingLg">{`${stats.total_milestones}`}</Text>
                        <Text as="p" variant="bodyMd" tone="subdued">Total Milestones</Text>
                      </BlockStack>
                    </Card>
                    <Card>
                      <BlockStack gap="200" inlineAlign="center">
                        <Icon source={CheckCircleIcon} />
                        <Text as="p" variant="headingLg">{`${stats.total_badges_earned}`}</Text>
                        <Text as="p" variant="bodyMd" tone="subdued">Badges Earned</Text>
                      </BlockStack>
                    </Card>
                  </InlineStack>
                </BlockStack>
              )}
            </Tabs>
          </Card>
        </Layout.Section>

        <Layout.Section variant="oneThird">
          <Card>
            <BlockStack gap="300">
              <Text as="h3" variant="headingMd">How Gamification Works</Text>
              <Text as="p" variant="bodyMd" tone="subdued">
                Gamification increases engagement by rewarding customers for their loyalty activities.
              </Text>
              <BlockStack gap="200">
                <Text as="p" variant="bodyMd"><strong>Badges:</strong> Award for specific achievements</Text>
                <Text as="p" variant="bodyMd"><strong>Milestones:</strong> Celebrate cumulative progress</Text>
                <Text as="p" variant="bodyMd"><strong>Streaks:</strong> Track consecutive activity</Text>
              </BlockStack>
            </BlockStack>
          </Card>

          <Card>
            <BlockStack gap="300">
              <Text as="h3" variant="headingMd">Badge Ideas</Text>
              <BlockStack gap="100">
                <Text as="p" variant="bodyMd">First Purchase Champion</Text>
                <Text as="p" variant="bodyMd">Trade-In Master (50 trade-ins)</Text>
                <Text as="p" variant="bodyMd">Referral King (10 referrals)</Text>
                <Text as="p" variant="bodyMd">Loyalty Legend (1 year member)</Text>
                <Text as="p" variant="bodyMd">Streak Warrior (30 day streak)</Text>
              </BlockStack>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>

      {/* Create/Edit Badge Modal */}
      <Modal
        open={showBadgeModal}
        onClose={() => {
          setShowBadgeModal(false);
          setBadgeForm(initialBadgeForm);
          setEditingBadge(null);
          setError(null);
        }}
        title={editingBadge ? 'Edit Badge' : 'Create Badge'}
        primaryAction={{
          content: editingBadge ? 'Update Badge' : 'Create Badge',
          onAction: handleBadgeSubmit,
          loading: createBadgeMutation.isPending || updateBadgeMutation.isPending,
        }}
        secondaryActions={[
          { content: 'Cancel', onAction: () => setShowBadgeModal(false) },
        ]}
      >
        <Modal.Section>
          {error && (
            <Banner tone="critical" onDismiss={() => setError(null)}>
              {error}
            </Banner>
          )}
          <FormLayout>
            <TextField
              label="Badge Name"
              value={badgeForm.name}
              onChange={(v) => setBadgeForm({ ...badgeForm, name: v })}
              placeholder="Trade-In Pro"
              autoComplete="off"
            />

            <TextField
              label="Description"
              value={badgeForm.description}
              onChange={(v) => setBadgeForm({ ...badgeForm, description: v })}
              placeholder="Awarded for completing 10 trade-ins"
              multiline={2}
              autoComplete="off"
            />

            <FormLayout.Group>
              <Select
                label="Icon"
                options={ICON_OPTIONS}
                value={badgeForm.icon}
                onChange={(v) => setBadgeForm({ ...badgeForm, icon: v })}
              />
              <TextField
                label="Color"
                value={badgeForm.color}
                onChange={(v) => setBadgeForm({ ...badgeForm, color: v })}
                placeholder="#e85d27"
                autoComplete="off"
              />
            </FormLayout.Group>

            <FormLayout.Group>
              <Select
                label="Criteria Type"
                options={CRITERIA_TYPES}
                value={badgeForm.criteria_type}
                onChange={(v) => setBadgeForm({ ...badgeForm, criteria_type: v })}
              />
              <TextField
                label="Criteria Value"
                type="number"
                value={badgeForm.criteria_value}
                onChange={(v) => setBadgeForm({ ...badgeForm, criteria_value: v })}
                helpText="e.g., 10 for '10 trade-ins'"
                autoComplete="off"
              />
            </FormLayout.Group>

            <FormLayout.Group>
              <TextField
                label="Points Reward"
                type="number"
                value={badgeForm.points_reward}
                onChange={(v) => setBadgeForm({ ...badgeForm, points_reward: v })}
                suffix="points"
                autoComplete="off"
              />
              <TextField
                label="Credit Reward"
                type="number"
                value={badgeForm.credit_reward}
                onChange={(v) => setBadgeForm({ ...badgeForm, credit_reward: v })}
                prefix="$"
                autoComplete="off"
              />
            </FormLayout.Group>
          </FormLayout>
        </Modal.Section>
      </Modal>

      {/* Create Milestone Modal */}
      <Modal
        open={showMilestoneModal}
        onClose={() => {
          setShowMilestoneModal(false);
          setMilestoneForm(initialMilestoneForm);
          setError(null);
        }}
        title="Create Milestone"
        primaryAction={{
          content: 'Create Milestone',
          onAction: handleMilestoneSubmit,
          loading: createMilestoneMutation.isPending,
        }}
        secondaryActions={[
          { content: 'Cancel', onAction: () => setShowMilestoneModal(false) },
        ]}
      >
        <Modal.Section>
          {error && (
            <Banner tone="critical" onDismiss={() => setError(null)}>
              {error}
            </Banner>
          )}
          <FormLayout>
            <TextField
              label="Milestone Name"
              value={milestoneForm.name}
              onChange={(v) => setMilestoneForm({ ...milestoneForm, name: v })}
              placeholder="1000 Point Club"
              autoComplete="off"
            />

            <TextField
              label="Description"
              value={milestoneForm.description}
              onChange={(v) => setMilestoneForm({ ...milestoneForm, description: v })}
              placeholder="Celebrate reaching 1000 points"
              multiline={2}
              autoComplete="off"
            />

            <FormLayout.Group>
              <Select
                label="Milestone Type"
                options={MILESTONE_TYPES}
                value={milestoneForm.milestone_type}
                onChange={(v) => setMilestoneForm({ ...milestoneForm, milestone_type: v })}
              />
              <TextField
                label="Threshold"
                type="number"
                value={milestoneForm.threshold}
                onChange={(v) => setMilestoneForm({ ...milestoneForm, threshold: v })}
                helpText="Value to reach"
                autoComplete="off"
              />
            </FormLayout.Group>

            <FormLayout.Group>
              <TextField
                label="Points Reward"
                type="number"
                value={milestoneForm.points_reward}
                onChange={(v) => setMilestoneForm({ ...milestoneForm, points_reward: v })}
                suffix="points"
                autoComplete="off"
              />
              <TextField
                label="Credit Reward"
                type="number"
                value={milestoneForm.credit_reward}
                onChange={(v) => setMilestoneForm({ ...milestoneForm, credit_reward: v })}
                prefix="$"
                autoComplete="off"
              />
            </FormLayout.Group>

            <TextField
              label="Celebration Message"
              value={milestoneForm.celebration_message}
              onChange={(v) => setMilestoneForm({ ...milestoneForm, celebration_message: v })}
              placeholder="Congratulations! You've reached 1000 points!"
              multiline={2}
              autoComplete="off"
            />
          </FormLayout>
        </Modal.Section>
      </Modal>
    </Page>
  );
}

export default EmbeddedGamification;
