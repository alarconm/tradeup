/**
 * TradeUp Points Configuration - Shopify Embedded Version
 *
 * Manage points earning rules and rewards catalog:
 * - View/create/edit earning rules
 * - View/create/edit rewards
 * - Configure points program settings
 */
import { useState, useCallback } from 'react';
import {
  Page,
  Layout,
  Card,
  Text,
  InlineStack,
  BlockStack,
  Box,
  Badge,
  Modal,
  TextField,
  FormLayout,
  Banner,
  Spinner,
  EmptyState,
  ResourceList,
  ResourceItem,
  Avatar,
  Select,
  Tabs,
  Divider,
} from '@shopify/polaris';
import { PlusIcon, StarIcon } from '@shopify/polaris-icons';
import { TitleBar } from '@shopify/app-bridge-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface PointsProps {
  shop: string | null;
}

interface EarningRule {
  id: number;
  name: string;
  code: string | null;
  description: string | null;
  rule_type: string;
  points_per_dollar: number | null;
  multiplier: number | null;
  bonus_points: number | null;
  trigger_source: string | null;
  min_order_value: number | null;
  max_points_per_order: number | null;
  is_active: boolean;
  is_base_rule: boolean;
  starts_at: string | null;
  ends_at: string | null;
  created_at: string;
}

interface Reward {
  id: number;
  name: string;
  code: string | null;
  description: string | null;
  reward_type: string;
  points_cost: number;
  credit_value: number | null;
  discount_percent: number | null;
  discount_amount: number | null;
  is_active: boolean;
  is_featured: boolean;
  available_quantity: number | null;
  redeemed_quantity: number;
  remaining_quantity: number | null;
  starts_at: string | null;
  ends_at: string | null;
  created_at: string;
}

async function fetchEarningRules(shop: string | null): Promise<EarningRule[]> {
  const response = await authFetch(
    `${getApiUrl()}/points/rules`,
    shop
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || `Failed to fetch earning rules (${response.status})`);
  }
  const data = await response.json();
  return data.rules || [];
}

async function fetchRewards(shop: string | null): Promise<Reward[]> {
  const response = await authFetch(
    `${getApiUrl()}/rewards`,
    shop
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || `Failed to fetch rewards (${response.status})`);
  }
  const data = await response.json();
  return data.rewards || [];
}

async function createEarningRule(shop: string | null, rule: Partial<EarningRule>): Promise<EarningRule> {
  const response = await authFetch(
    `${getApiUrl()}/points/rules`,
    shop,
    {
      method: 'POST',
      body: JSON.stringify(rule),
    }
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || `Failed to create rule (${response.status})`);
  }
  return response.json();
}

async function createReward(shop: string | null, reward: Partial<Reward>): Promise<Reward> {
  const response = await authFetch(
    `${getApiUrl()}/rewards`,
    shop,
    {
      method: 'POST',
      body: JSON.stringify(reward),
    }
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || `Failed to create reward (${response.status})`);
  }
  return response.json();
}

async function toggleRule(shop: string | null, ruleId: number): Promise<EarningRule> {
  const response = await authFetch(
    `${getApiUrl()}/points/rules/${ruleId}/toggle`,
    shop,
    { method: 'POST' }
  );
  if (!response.ok) {
    throw new Error('Failed to toggle rule');
  }
  return response.json();
}

async function toggleReward(shop: string | null, rewardId: number): Promise<Reward> {
  const response = await authFetch(
    `${getApiUrl()}/rewards/${rewardId}/toggle`,
    shop,
    { method: 'POST' }
  );
  if (!response.ok) {
    throw new Error('Failed to toggle reward');
  }
  return response.json();
}

export function EmbeddedPoints({ shop }: PointsProps) {
  const queryClient = useQueryClient();
  const [selectedTab, setSelectedTab] = useState(0);
  const [ruleModalOpen, setRuleModalOpen] = useState(false);
  const [rewardModalOpen, setRewardModalOpen] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);

  // Rule form state
  const [ruleForm, setRuleForm] = useState({
    name: '',
    description: '',
    rule_type: 'base_rate',
    points_per_dollar: '1',
    trigger_source: 'purchase',
    min_order_value: '',
    max_points_per_order: '',
  });

  // Reward form state
  const [rewardForm, setRewardForm] = useState({
    name: '',
    description: '',
    reward_type: 'store_credit',
    points_cost: '100',
    credit_value: '1',
  });

  const { data: earningRules, isLoading: rulesLoading, error: rulesError } = useQuery({
    queryKey: ['earning-rules', shop],
    queryFn: () => fetchEarningRules(shop),
    enabled: !!shop,
  });

  const { data: rewards, isLoading: rewardsLoading, error: rewardsError } = useQuery({
    queryKey: ['rewards', shop],
    queryFn: () => fetchRewards(shop),
    enabled: !!shop,
  });

  const createRuleMutation = useMutation({
    mutationFn: (rule: Partial<EarningRule>) => createEarningRule(shop, rule),
    onSuccess: () => {
      setMutationError(null);
      queryClient.invalidateQueries({ queryKey: ['earning-rules'] });
      setRuleModalOpen(false);
      setRuleForm({
        name: '',
        description: '',
        rule_type: 'base_rate',
        points_per_dollar: '1',
        trigger_source: 'purchase',
        min_order_value: '',
        max_points_per_order: '',
      });
    },
    onError: (error: Error) => {
      setMutationError(error.message);
    },
  });

  const createRewardMutation = useMutation({
    mutationFn: (reward: Partial<Reward>) => createReward(shop, reward),
    onSuccess: () => {
      setMutationError(null);
      queryClient.invalidateQueries({ queryKey: ['rewards'] });
      setRewardModalOpen(false);
      setRewardForm({
        name: '',
        description: '',
        reward_type: 'store_credit',
        points_cost: '100',
        credit_value: '1',
      });
    },
    onError: (error: Error) => {
      setMutationError(error.message);
    },
  });

  const toggleRuleMutation = useMutation({
    mutationFn: (ruleId: number) => toggleRule(shop, ruleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['earning-rules'] });
    },
  });

  const toggleRewardMutation = useMutation({
    mutationFn: (rewardId: number) => toggleReward(shop, rewardId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rewards'] });
    },
  });

  const handleCreateRule = useCallback(() => {
    const rule = {
      name: ruleForm.name,
      description: ruleForm.description || undefined,
      rule_type: ruleForm.rule_type,
      points_per_dollar: parseInt(ruleForm.points_per_dollar) || 1,
      trigger_source: ruleForm.trigger_source,
      min_order_value: ruleForm.min_order_value ? parseFloat(ruleForm.min_order_value) : undefined,
      max_points_per_order: ruleForm.max_points_per_order ? parseInt(ruleForm.max_points_per_order) : undefined,
    };
    createRuleMutation.mutate(rule);
  }, [ruleForm, createRuleMutation]);

  const handleCreateReward = useCallback(() => {
    const reward = {
      name: rewardForm.name,
      description: rewardForm.description || undefined,
      reward_type: rewardForm.reward_type,
      points_cost: parseInt(rewardForm.points_cost) || 100,
      credit_value: parseFloat(rewardForm.credit_value) || 1,
    };
    createRewardMutation.mutate(reward);
  }, [rewardForm, createRewardMutation]);

  const tabs = [
    {
      id: 'earning-rules',
      content: 'Earning Rules',
      accessibilityLabel: 'Earning rules',
      panelID: 'earning-rules-panel',
    },
    {
      id: 'rewards',
      content: 'Rewards Catalog',
      accessibilityLabel: 'Rewards catalog',
      panelID: 'rewards-panel',
    },
  ];

  if (!shop) {
    return (
      <Page title="Points & Rewards">
        <Banner tone="warning">
          <p>No shop connected. Please install the app from the Shopify App Store.</p>
        </Banner>
      </Page>
    );
  }

  const isLoading = rulesLoading || rewardsLoading;

  if (isLoading) {
    return (
      <Page title="Points & Rewards">
        <Box padding="1600">
          <InlineStack align="center">
            <Spinner size="large" />
          </InlineStack>
        </Box>
      </Page>
    );
  }

  return (
    <>
      <TitleBar title="Points & Rewards" />
      <Page
        title="Points & Rewards"
        subtitle="Configure how customers earn and redeem loyalty points"
        primaryAction={{
          content: selectedTab === 0 ? 'Add Earning Rule' : 'Add Reward',
          icon: PlusIcon,
          onAction: () => selectedTab === 0 ? setRuleModalOpen(true) : setRewardModalOpen(true),
        }}
      >
        <Layout>
          {(rulesError || rewardsError) && (
            <Layout.Section>
              <Banner tone="critical">
                <p>Failed to load data. Please try refreshing the page.</p>
              </Banner>
            </Layout.Section>
          )}

          {mutationError && (
            <Layout.Section>
              <Banner tone="critical" onDismiss={() => setMutationError(null)}>
                <p>{mutationError}</p>
              </Banner>
            </Layout.Section>
          )}

          <Layout.Section>
            <Card padding="0">
              <Tabs tabs={tabs} selected={selectedTab} onSelect={setSelectedTab}>
                {selectedTab === 0 ? (
                  // Earning Rules Tab
                  earningRules && earningRules.length > 0 ? (
                    <ResourceList
                      resourceName={{ singular: 'rule', plural: 'rules' }}
                      items={earningRules}
                      renderItem={(rule) => (
                        <ResourceItem
                          id={String(rule.id)}
                          accessibilityLabel={rule.name}
                          onClick={() => {}}
                          media={
                            <Avatar
                              customer={false}
                              size="md"
                              name={rule.name}
                              initials={rule.name.charAt(0)}
                            />
                          }
                          shortcutActions={[
                            {
                              content: rule.is_active ? 'Disable' : 'Enable',
                              onAction: () => toggleRuleMutation.mutate(rule.id),
                            },
                          ]}
                        >
                          <InlineStack align="space-between" blockAlign="center" wrap={false}>
                            <BlockStack gap="100">
                              <InlineStack gap="200" blockAlign="center">
                                <Text as="h3" variant="bodyMd" fontWeight="bold">
                                  {rule.name}
                                </Text>
                                {rule.is_base_rule && (
                                  <Badge tone="info">Base Rule</Badge>
                                )}
                                {!rule.is_active && (
                                  <Badge tone="warning">Inactive</Badge>
                                )}
                              </InlineStack>
                              <Text as="span" variant="bodySm" tone="subdued">
                                {rule.description || `${rule.points_per_dollar || 0} points per $1 spent`}
                              </Text>
                            </BlockStack>
                            <Badge tone="success">
                              {rule.rule_type === 'base_rate' ? `${rule.points_per_dollar} pts/$1` :
                               rule.rule_type === 'multiplier' ? `${rule.multiplier}x multiplier` :
                               `${rule.bonus_points} bonus pts`}
                            </Badge>
                          </InlineStack>
                        </ResourceItem>
                      )}
                    />
                  ) : (
                    <EmptyState
                      heading="Set up your earning rules"
                      action={{
                        content: 'Add Earning Rule',
                        onAction: () => setRuleModalOpen(true),
                      }}
                      image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                    >
                      <p>
                        Earning rules define how customers earn points on purchases, trade-ins, referrals, and more.
                      </p>
                    </EmptyState>
                  )
                ) : (
                  // Rewards Tab
                  rewards && rewards.length > 0 ? (
                    <ResourceList
                      resourceName={{ singular: 'reward', plural: 'rewards' }}
                      items={rewards}
                      renderItem={(reward) => (
                        <ResourceItem
                          id={String(reward.id)}
                          accessibilityLabel={reward.name}
                          onClick={() => {}}
                          media={
                            <Avatar
                              customer={false}
                              size="md"
                              name={reward.name}
                              initials={reward.name.charAt(0)}
                            />
                          }
                          shortcutActions={[
                            {
                              content: reward.is_active ? 'Disable' : 'Enable',
                              onAction: () => toggleRewardMutation.mutate(reward.id),
                            },
                          ]}
                        >
                          <InlineStack align="space-between" blockAlign="center" wrap={false}>
                            <BlockStack gap="100">
                              <InlineStack gap="200" blockAlign="center">
                                <Text as="h3" variant="bodyMd" fontWeight="bold">
                                  {reward.name}
                                </Text>
                                {reward.is_featured && (
                                  <Badge tone="success">Featured</Badge>
                                )}
                                {!reward.is_active && (
                                  <Badge tone="warning">Inactive</Badge>
                                )}
                              </InlineStack>
                              <Text as="span" variant="bodySm" tone="subdued">
                                {reward.description || `${reward.reward_type} reward`}
                              </Text>
                            </BlockStack>
                            <BlockStack gap="100" inlineAlign="end">
                              <Badge>{`${reward.points_cost.toLocaleString()} points`}</Badge>
                              {reward.credit_value && (
                                <Text as="span" variant="bodySm" tone="success">
                                  ${reward.credit_value} value
                                </Text>
                              )}
                            </BlockStack>
                          </InlineStack>
                        </ResourceItem>
                      )}
                    />
                  ) : (
                    <EmptyState
                      heading="Create your rewards catalog"
                      action={{
                        content: 'Add Reward',
                        onAction: () => setRewardModalOpen(true),
                      }}
                      image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                    >
                      <p>
                        Rewards are what customers can redeem their points for - store credit, discounts, free products, and more.
                      </p>
                    </EmptyState>
                  )
                )}
              </Tabs>
            </Card>
          </Layout.Section>

          <Layout.Section variant="oneThird">
            <Card>
              <BlockStack gap="400">
                <InlineStack gap="200" blockAlign="center">
                  <StarIcon />
                  <Text as="h3" variant="headingMd">How Points Work</Text>
                </InlineStack>
                <Divider />
                <BlockStack gap="200">
                  <Text as="p" variant="bodySm">
                    <strong>Earning:</strong> Customers earn points based on your earning rules - per dollar spent, on trade-ins, referrals, and more.
                  </Text>
                  <Text as="p" variant="bodySm">
                    <strong>Redeeming:</strong> Points are redeemed for rewards in your catalog - typically store credit that syncs to Shopify.
                  </Text>
                  <Text as="p" variant="bodySm">
                    <strong>Default:</strong> 1 point per $1 spent, 100 points = $1 store credit.
                  </Text>
                </BlockStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>

        {/* Create Earning Rule Modal */}
        <Modal
          open={ruleModalOpen}
          onClose={() => setRuleModalOpen(false)}
          title="Create Earning Rule"
          primaryAction={{
            content: 'Create',
            onAction: handleCreateRule,
            loading: createRuleMutation.isPending,
            disabled: !ruleForm.name.trim(),
          }}
          secondaryActions={[{ content: 'Cancel', onAction: () => setRuleModalOpen(false) }]}
        >
          <Modal.Section>
            <FormLayout>
              <TextField
                label="Rule Name"
                value={ruleForm.name}
                onChange={(value) => setRuleForm({ ...ruleForm, name: value })}
                placeholder="e.g., Base Purchase Rate, Double Points Day"
                autoComplete="off"
              />
              <TextField
                label="Description"
                value={ruleForm.description}
                onChange={(value) => setRuleForm({ ...ruleForm, description: value })}
                placeholder="Brief description of this rule"
                autoComplete="off"
              />
              <Select
                label="Trigger"
                options={[
                  { label: 'Purchase', value: 'purchase' },
                  { label: 'Trade-in', value: 'trade_in' },
                  { label: 'Referral', value: 'referral' },
                  { label: 'Signup', value: 'signup' },
                  { label: 'Birthday', value: 'birthday' },
                ]}
                value={ruleForm.trigger_source}
                onChange={(value) => setRuleForm({ ...ruleForm, trigger_source: value })}
              />
              <TextField
                label="Points per Dollar"
                type="number"
                value={ruleForm.points_per_dollar}
                onChange={(value) => setRuleForm({ ...ruleForm, points_per_dollar: value })}
                autoComplete="off"
                helpText="How many points to award per $1 spent"
              />
              <TextField
                label="Minimum Order Value (optional)"
                type="number"
                value={ruleForm.min_order_value}
                onChange={(value) => setRuleForm({ ...ruleForm, min_order_value: value })}
                prefix="$"
                autoComplete="off"
                helpText="Order must be at least this amount to qualify"
              />
            </FormLayout>
          </Modal.Section>
        </Modal>

        {/* Create Reward Modal */}
        <Modal
          open={rewardModalOpen}
          onClose={() => setRewardModalOpen(false)}
          title="Create Reward"
          primaryAction={{
            content: 'Create',
            onAction: handleCreateReward,
            loading: createRewardMutation.isPending,
            disabled: !rewardForm.name.trim(),
          }}
          secondaryActions={[{ content: 'Cancel', onAction: () => setRewardModalOpen(false) }]}
        >
          <Modal.Section>
            <FormLayout>
              <TextField
                label="Reward Name"
                value={rewardForm.name}
                onChange={(value) => setRewardForm({ ...rewardForm, name: value })}
                placeholder="e.g., $5 Store Credit, Free Shipping"
                autoComplete="off"
              />
              <TextField
                label="Description"
                value={rewardForm.description}
                onChange={(value) => setRewardForm({ ...rewardForm, description: value })}
                placeholder="Brief description of this reward"
                autoComplete="off"
              />
              <Select
                label="Reward Type"
                options={[
                  { label: 'Store Credit', value: 'store_credit' },
                  { label: 'Discount Code', value: 'discount_code' },
                  { label: 'Free Product', value: 'free_product' },
                  { label: 'Free Shipping', value: 'free_shipping' },
                ]}
                value={rewardForm.reward_type}
                onChange={(value) => setRewardForm({ ...rewardForm, reward_type: value })}
              />
              <TextField
                label="Points Cost"
                type="number"
                value={rewardForm.points_cost}
                onChange={(value) => setRewardForm({ ...rewardForm, points_cost: value })}
                autoComplete="off"
                helpText="Points required to redeem this reward"
              />
              {rewardForm.reward_type === 'store_credit' && (
                <TextField
                  label="Credit Value"
                  type="number"
                  value={rewardForm.credit_value}
                  onChange={(value) => setRewardForm({ ...rewardForm, credit_value: value })}
                  prefix="$"
                  autoComplete="off"
                  helpText="Store credit amount to issue"
                />
              )}
            </FormLayout>
          </Modal.Section>
        </Modal>
      </Page>
    </>
  );
}
