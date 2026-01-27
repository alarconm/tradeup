/**
 * TradeUp Points Configuration - Shopify Embedded Version
 *
 * Manage points earning rules and rewards catalog:
 * - View/create/edit earning rules
 * - View/create/edit rewards
 * - Configure points program settings
 */
import { useState, useCallback, useEffect, useMemo } from 'react';
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
  Thumbnail,
  Button,
  Autocomplete,
  Icon,
} from '@shopify/polaris';
import { PlusIcon, StarIcon, SearchIcon, XSmallIcon } from '@shopify/polaris-icons';
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
  product_id: string | null;
  is_active: boolean;
  is_featured: boolean;
  available_quantity: number | null;
  redeemed_quantity: number;
  remaining_quantity: number | null;
  tier_restriction: string[] | null;
  max_redemptions_per_member: number | null;
  starts_at: string | null;
  ends_at: string | null;
  created_at: string;
}

interface MembershipTier {
  id: number;
  name: string;
  is_active: boolean;
}

interface ShopifyProductVariant {
  id: string;
  title: string;
  price: string;
  sku: string | null;
  inventoryQuantity: number | null;
}

interface ShopifyProduct {
  id: string;
  title: string;
  handle: string;
  status: string;
  productType: string | null;
  vendor: string | null;
  imageUrl: string | null;
  variants: ShopifyProductVariant[];
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

async function fetchTiers(shop: string | null): Promise<MembershipTier[]> {
  const response = await authFetch(
    `${getApiUrl()}/members/tiers`,
    shop
  );
  if (!response.ok) {
    return [];
  }
  const data = await response.json();
  return data.tiers || [];
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

async function updateReward(shop: string | null, rewardId: number, reward: Partial<Reward>): Promise<Reward> {
  const response = await authFetch(
    `${getApiUrl()}/rewards/${rewardId}`,
    shop,
    {
      method: 'PUT',
      body: JSON.stringify(reward),
    }
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || `Failed to update reward (${response.status})`);
  }
  return response.json();
}

async function searchProducts(shop: string | null, query: string): Promise<ShopifyProduct[]> {
  if (!query.trim()) return [];

  const response = await authFetch(
    `${getApiUrl()}/shopify-data/products/search?q=${encodeURIComponent(query)}`,
    shop
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || `Failed to search products (${response.status})`);
  }
  const data = await response.json();
  return data.products || [];
}

async function getProductById(shop: string | null, productId: string): Promise<ShopifyProduct | null> {
  const response = await authFetch(
    `${getApiUrl()}/shopify-data/products/${encodeURIComponent(productId)}`,
    shop
  );
  if (!response.ok) {
    return null;
  }
  const data = await response.json();
  return data.product || null;
}

export function EmbeddedPoints({ shop }: PointsProps) {
  const queryClient = useQueryClient();
  const [selectedTab, setSelectedTab] = useState(0);
  const [ruleModalOpen, setRuleModalOpen] = useState(false);
  const [rewardModalOpen, setRewardModalOpen] = useState(false);
  const [editingReward, setEditingReward] = useState<Reward | null>(null);
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
    discount_percent: '',
    discount_amount: '',
    product_id: '',
    tier_restriction: [] as string[],
    available_quantity: '',
    max_redemptions_per_member: '',
    starts_at: '',
    ends_at: '',
  });

  // Product search state for Free Product rewards
  const [productSearchQuery, setProductSearchQuery] = useState('');
  const [productSearchResults, setProductSearchResults] = useState<ShopifyProduct[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<ShopifyProduct | null>(null);
  const [isSearchingProducts, setIsSearchingProducts] = useState(false);

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

  const { data: tiers } = useQuery({
    queryKey: ['tiers', shop],
    queryFn: () => fetchTiers(shop),
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
      setEditingReward(null);
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

  const updateRewardMutation = useMutation({
    mutationFn: ({ rewardId, reward }: { rewardId: number; reward: Partial<Reward> }) =>
      updateReward(shop, rewardId, reward),
    onSuccess: () => {
      setMutationError(null);
      queryClient.invalidateQueries({ queryKey: ['rewards'] });
      setRewardModalOpen(false);
      setEditingReward(null);
      resetRewardForm();
    },
    onError: (error: Error) => {
      setMutationError(error.message);
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

  const resetRewardForm = useCallback(() => {
    setRewardForm({
      name: '',
      description: '',
      reward_type: 'store_credit',
      points_cost: '100',
      credit_value: '1',
      discount_percent: '',
      discount_amount: '',
      product_id: '',
      tier_restriction: [],
      available_quantity: '',
      max_redemptions_per_member: '',
      starts_at: '',
      ends_at: '',
    });
    setProductSearchQuery('');
    setProductSearchResults([]);
    setSelectedProduct(null);
  }, []);

  const handleEditReward = useCallback(async (reward: Reward) => {
    setEditingReward(reward);
    setRewardForm({
      name: reward.name,
      description: reward.description || '',
      reward_type: reward.reward_type,
      points_cost: String(reward.points_cost),
      credit_value: reward.credit_value ? String(reward.credit_value) : '1',
      discount_percent: reward.discount_percent ? String(reward.discount_percent) : '',
      discount_amount: reward.discount_amount ? String(reward.discount_amount) : '',
      product_id: reward.product_id || '',
      tier_restriction: reward.tier_restriction || [],
      available_quantity: reward.available_quantity ? String(reward.available_quantity) : '',
      max_redemptions_per_member: reward.max_redemptions_per_member ? String(reward.max_redemptions_per_member) : '',
      starts_at: reward.starts_at ? reward.starts_at.split('T')[0] : '',
      ends_at: reward.ends_at ? reward.ends_at.split('T')[0] : '',
    });

    // Load the selected product if this is a free product reward
    if (reward.reward_type === 'free_product' && reward.product_id) {
      const product = await getProductById(shop, reward.product_id);
      setSelectedProduct(product);
    } else {
      setSelectedProduct(null);
    }

    setProductSearchQuery('');
    setProductSearchResults([]);
    setRewardModalOpen(true);
  }, [shop]);

  const handleSaveReward = useCallback(() => {
    const reward: Partial<Reward> & { product_id?: string; tier_restriction?: string[] } = {
      name: rewardForm.name,
      description: rewardForm.description || undefined,
      reward_type: rewardForm.reward_type,
      points_cost: parseInt(rewardForm.points_cost) || 100,
    };

    // Add type-specific fields
    if (rewardForm.reward_type === 'store_credit') {
      reward.credit_value = parseFloat(rewardForm.credit_value) || 1;
    } else if (rewardForm.reward_type === 'discount_code') {
      // Support either percentage or fixed amount discount
      if (rewardForm.discount_percent) {
        reward.discount_percent = parseFloat(rewardForm.discount_percent);
      }
      if (rewardForm.discount_amount) {
        reward.discount_amount = parseFloat(rewardForm.discount_amount);
      }
    } else if (rewardForm.reward_type === 'free_product') {
      // Include the selected product ID
      if (selectedProduct) {
        reward.product_id = selectedProduct.id;
      }
    }

    // Add restriction fields
    if (rewardForm.tier_restriction && rewardForm.tier_restriction.length > 0) {
      reward.tier_restriction = rewardForm.tier_restriction;
    }
    if (rewardForm.available_quantity) {
      reward.available_quantity = parseInt(rewardForm.available_quantity);
    }
    if (rewardForm.max_redemptions_per_member) {
      reward.max_redemptions_per_member = parseInt(rewardForm.max_redemptions_per_member);
    }
    if (rewardForm.starts_at) {
      reward.starts_at = rewardForm.starts_at;
    }
    if (rewardForm.ends_at) {
      reward.ends_at = rewardForm.ends_at;
    }

    if (editingReward) {
      updateRewardMutation.mutate({ rewardId: editingReward.id, reward });
    } else {
      createRewardMutation.mutate(reward);
    }
  }, [rewardForm, editingReward, selectedProduct, createRewardMutation, updateRewardMutation]);

  const handleCloseRewardModal = useCallback(() => {
    setRewardModalOpen(false);
    setEditingReward(null);
    resetRewardForm();
  }, [resetRewardForm]);

  // Product search handler with debounce
  const handleProductSearch = useCallback(async (query: string) => {
    setProductSearchQuery(query);

    if (!query.trim()) {
      setProductSearchResults([]);
      return;
    }

    // Debounce: only search after typing stops
    setIsSearchingProducts(true);
    try {
      const results = await searchProducts(shop, query);
      setProductSearchResults(results);
    } catch (error) {
      console.error('Product search failed:', error);
      setProductSearchResults([]);
    } finally {
      setIsSearchingProducts(false);
    }
  }, [shop]);

  const handleSelectProduct = useCallback((product: ShopifyProduct) => {
    setSelectedProduct(product);
    setRewardForm((prev) => ({ ...prev, product_id: product.id }));
    setProductSearchQuery('');
    setProductSearchResults([]);
  }, []);

  const handleRemoveProduct = useCallback(() => {
    setSelectedProduct(null);
    setRewardForm((prev) => ({ ...prev, product_id: '' }));
  }, []);

  // Convert product search results to Autocomplete options
  const productOptions = useMemo(() => {
    return productSearchResults.map((product) => ({
      value: product.id,
      label: product.title,
      media: product.imageUrl ? (
        <Thumbnail source={product.imageUrl} alt={product.title} size="small" />
      ) : (
        <Avatar customer={false} size="sm" name={product.title} />
      ),
    }));
  }, [productSearchResults]);

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
          onAction: () => {
            if (selectedTab === 0) {
              setRuleModalOpen(true);
            } else {
              setEditingReward(null);
              resetRewardForm();
              setRewardModalOpen(true);
            }
          },
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
                          <BlockStack gap="200">
                            <InlineStack gap="200" blockAlign="center" wrap>
                              <Text as="h3" variant="bodyMd" fontWeight="bold">
                                {rule.name}
                              </Text>
                              {rule.is_base_rule && (
                                <Badge tone="info">Base Rule</Badge>
                              )}
                              {!rule.is_active && (
                                <Badge tone="warning">Inactive</Badge>
                              )}
                              <Badge tone="success">
                                {rule.rule_type === 'base_rate' ? `${rule.points_per_dollar} pts/$1` :
                                 rule.rule_type === 'multiplier' ? `${rule.multiplier}x multiplier` :
                                 `${rule.bonus_points} bonus pts`}
                              </Badge>
                            </InlineStack>
                            <Text as="span" variant="bodySm" tone="subdued">
                              {rule.description || `${rule.points_per_dollar || 0} points per $1 spent`}
                            </Text>
                          </BlockStack>
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
                          onClick={() => handleEditReward(reward)}
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
                              content: 'Edit',
                              onAction: () => handleEditReward(reward),
                            },
                            {
                              content: reward.is_active ? 'Disable' : 'Enable',
                              onAction: () => toggleRewardMutation.mutate(reward.id),
                            },
                          ]}
                        >
                          <BlockStack gap="200">
                            <InlineStack gap="200" blockAlign="center" wrap>
                              <Text as="h3" variant="bodyMd" fontWeight="bold">
                                {reward.name}
                              </Text>
                              {reward.is_featured && (
                                <Badge tone="success">Featured</Badge>
                              )}
                              {!reward.is_active && (
                                <Badge tone="warning">Inactive</Badge>
                              )}
                              <Badge>{`${reward.points_cost.toLocaleString()} points`}</Badge>
                              {reward.credit_value && (
                                <Badge tone="info">{`$${reward.credit_value} value`}</Badge>
                              )}
                              {reward.discount_percent && (
                                <Badge tone="info">{`${reward.discount_percent}% off`}</Badge>
                              )}
                              {reward.discount_amount && !reward.discount_percent && (
                                <Badge tone="info">{`$${reward.discount_amount} off`}</Badge>
                              )}
                            </InlineStack>
                            <Text as="span" variant="bodySm" tone="subdued">
                              {reward.description || `${reward.reward_type} reward`}
                            </Text>
                            {/* Show restrictions if any are set */}
                            {(reward.tier_restriction?.length || reward.available_quantity || reward.max_redemptions_per_member || reward.starts_at || reward.ends_at) && (
                              <InlineStack gap="200" wrap>
                                {reward.tier_restriction && reward.tier_restriction.length > 0 && (
                                  <Badge>{reward.tier_restriction.join(', ')} only</Badge>
                                )}
                                {reward.available_quantity && (
                                  <Badge tone="attention">
                                    {reward.remaining_quantity !== null ? `${reward.remaining_quantity}/${reward.available_quantity} left` : `Limit: ${reward.available_quantity}`}
                                  </Badge>
                                )}
                                {reward.max_redemptions_per_member && (
                                  <Badge>Max {reward.max_redemptions_per_member}/member</Badge>
                                )}
                                {(reward.starts_at || reward.ends_at) && (
                                  <Badge tone="attention">
                                    {reward.starts_at && reward.ends_at
                                      ? `${new Date(reward.starts_at).toLocaleDateString()} - ${new Date(reward.ends_at).toLocaleDateString()}`
                                      : reward.starts_at
                                        ? `From ${new Date(reward.starts_at).toLocaleDateString()}`
                                        : `Until ${new Date(reward.ends_at!).toLocaleDateString()}`
                                    }
                                  </Badge>
                                )}
                              </InlineStack>
                            )}
                          </BlockStack>
                        </ResourceItem>
                      )}
                    />
                  ) : (
                    <EmptyState
                      heading="Create your rewards catalog"
                      action={{
                        content: 'Add Reward',
                        onAction: () => {
                          setEditingReward(null);
                          resetRewardForm();
                          setRewardModalOpen(true);
                        },
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
                  { label: 'Anniversary', value: 'anniversary' },
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

        {/* Create/Edit Reward Modal */}
        <Modal
          open={rewardModalOpen}
          onClose={handleCloseRewardModal}
          title={editingReward ? 'Edit Reward' : 'Create Reward'}
          primaryAction={{
            content: editingReward ? 'Save' : 'Create',
            onAction: handleSaveReward,
            loading: createRewardMutation.isPending || updateRewardMutation.isPending,
            disabled: !rewardForm.name.trim(),
          }}
          secondaryActions={[{ content: 'Cancel', onAction: handleCloseRewardModal }]}
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
              {rewardForm.reward_type === 'discount_code' && (
                <>
                  <TextField
                    label="Discount Percentage"
                    type="number"
                    value={rewardForm.discount_percent}
                    onChange={(value) => setRewardForm({ ...rewardForm, discount_percent: value })}
                    suffix="%"
                    autoComplete="off"
                    helpText="Percentage off (e.g., 10 for 10% off). Leave empty if using fixed amount."
                  />
                  <TextField
                    label="Discount Amount"
                    type="number"
                    value={rewardForm.discount_amount}
                    onChange={(value) => setRewardForm({ ...rewardForm, discount_amount: value })}
                    prefix="$"
                    autoComplete="off"
                    helpText="Fixed dollar amount off. Leave empty if using percentage."
                  />
                </>
              )}
              {rewardForm.reward_type === 'free_product' && (
                <BlockStack gap="300">
                  <Text as="span" variant="bodyMd" fontWeight="semibold">
                    Select Product
                  </Text>

                  {selectedProduct ? (
                    <Card padding="400">
                      <InlineStack gap="400" align="space-between" blockAlign="center">
                        <InlineStack gap="300" blockAlign="center">
                          {selectedProduct.imageUrl ? (
                            <Thumbnail
                              source={selectedProduct.imageUrl}
                              alt={selectedProduct.title}
                              size="small"
                            />
                          ) : (
                            <Avatar customer={false} size="md" name={selectedProduct.title} />
                          )}
                          <BlockStack gap="100">
                            <Text as="span" variant="bodyMd" fontWeight="semibold">
                              {selectedProduct.title}
                            </Text>
                            {selectedProduct.variants.length > 0 && (
                              <Text as="span" variant="bodySm" tone="subdued">
                                {selectedProduct.variants.length === 1
                                  ? `$${selectedProduct.variants[0].price}`
                                  : `${selectedProduct.variants.length} variants - from $${selectedProduct.variants[0].price}`
                                }
                              </Text>
                            )}
                          </BlockStack>
                        </InlineStack>
                        <Button
                          variant="plain"
                          icon={XSmallIcon}
                          onClick={handleRemoveProduct}
                          accessibilityLabel="Remove selected product"
                        />
                      </InlineStack>
                    </Card>
                  ) : (
                    <Autocomplete
                      options={productOptions}
                      selected={[]}
                      onSelect={(selected) => {
                        const productId = selected[0];
                        const product = productSearchResults.find((p) => p.id === productId);
                        if (product) {
                          handleSelectProduct(product);
                        }
                      }}
                      textField={
                        <Autocomplete.TextField
                          onChange={handleProductSearch}
                          label="Search products"
                          labelHidden
                          value={productSearchQuery}
                          prefix={<Icon source={SearchIcon} />}
                          placeholder="Search for a product by name..."
                          autoComplete="off"
                          loading={isSearchingProducts}
                        />
                      }
                      listTitle="Products"
                      emptyState={
                        productSearchQuery.trim() && !isSearchingProducts ? (
                          <Box padding="200">
                            <Text as="span" tone="subdued">
                              No products found for "{productSearchQuery}"
                            </Text>
                          </Box>
                        ) : null
                      }
                    />
                  )}

                  <Text as="span" variant="bodySm" tone="subdued">
                    The selected product will be given to customers when they redeem this reward.
                  </Text>
                </BlockStack>
              )}

              <Divider />
              <Text as="h3" variant="headingSm">Restrictions (Optional)</Text>

              {tiers && tiers.length > 0 && (
                <Select
                  label="Tier Restriction"
                  options={[
                    { label: 'All tiers can redeem', value: '' },
                    ...tiers.filter(t => t.is_active).map(t => ({
                      label: `${t.name} only`,
                      value: t.name
                    }))
                  ]}
                  value={rewardForm.tier_restriction.length > 0 ? rewardForm.tier_restriction[0] : ''}
                  onChange={(value) => setRewardForm({
                    ...rewardForm,
                    tier_restriction: value ? [value] : []
                  })}
                  helpText="Limit this reward to a specific tier"
                />
              )}

              <TextField
                label="Total Redemption Limit"
                type="number"
                value={rewardForm.available_quantity}
                onChange={(value) => setRewardForm({ ...rewardForm, available_quantity: value })}
                autoComplete="off"
                helpText="Maximum total redemptions allowed (leave empty for unlimited)"
                placeholder="Unlimited"
              />

              <TextField
                label="Per-Member Limit"
                type="number"
                value={rewardForm.max_redemptions_per_member}
                onChange={(value) => setRewardForm({ ...rewardForm, max_redemptions_per_member: value })}
                autoComplete="off"
                helpText="Maximum redemptions per member (leave empty for unlimited)"
                placeholder="Unlimited"
              />

              <InlineStack gap="400">
                <Box minWidth="200px">
                  <TextField
                    label="Available From"
                    type="date"
                    value={rewardForm.starts_at}
                    onChange={(value) => setRewardForm({ ...rewardForm, starts_at: value })}
                    autoComplete="off"
                    helpText="When reward becomes available"
                  />
                </Box>
                <Box minWidth="200px">
                  <TextField
                    label="Available Until"
                    type="date"
                    value={rewardForm.ends_at}
                    onChange={(value) => setRewardForm({ ...rewardForm, ends_at: value })}
                    autoComplete="off"
                    helpText="When reward expires"
                  />
                </Box>
              </InlineStack>
            </FormLayout>
          </Modal.Section>
        </Modal>
      </Page>
    </>
  );
}
