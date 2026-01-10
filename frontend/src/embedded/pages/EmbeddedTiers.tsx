/**
 * TradeUp Membership Tiers - Shopify Embedded Version
 *
 * Comprehensive tier configuration including:
 * - Basic tier info (name, pricing)
 * - Trade-in bonus rates
 * - Purchase cashback percentages
 * - Recurring monthly credits
 * - Credit expiration settings
 * - Benefits (discounts, free shipping)
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
  Divider,
  Collapsible,
  Button,
  RangeSlider,
} from '@shopify/polaris';
import { PlusIcon, ChevronDownIcon, ChevronUpIcon } from '@shopify/polaris-icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface TiersProps {
  shop: string | null;
}

interface TierBenefits {
  discount_percent?: number;
  free_shipping_threshold?: number;
  monthly_credit?: number;
  features?: string[];
}

interface MembershipTier {
  id: number;
  name: string;
  monthly_price: number;
  yearly_price: number | null;
  bonus_rate: number;
  purchase_cashback_pct: number;
  monthly_credit_amount: number;
  credit_expiration_days: number | null;
  benefits: TierBenefits;
  display_order: number;
  is_active: boolean;
  color?: string;
}

async function fetchTiers(shop: string | null): Promise<MembershipTier[]> {
  const response = await authFetch(
    `${getApiUrl()}/members/tiers`,
    shop
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || data.message || `Failed to fetch tiers (${response.status})`);
  }
  const data = await response.json();
  return data.tiers || [];
}

async function createTier(
  shop: string | null,
  tier: Partial<MembershipTier>
): Promise<MembershipTier> {
  const response = await authFetch(
    `${getApiUrl()}/members/tiers`,
    shop,
    {
      method: 'POST',
      body: JSON.stringify(tier),
    }
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || data.message || `Failed to create tier (${response.status})`);
  }
  return response.json();
}

async function updateTier(
  shop: string | null,
  tierId: number,
  tier: Partial<MembershipTier>
): Promise<MembershipTier> {
  const response = await authFetch(
    `${getApiUrl()}/members/tiers/${tierId}`,
    shop,
    {
      method: 'PUT',
      body: JSON.stringify(tier),
    }
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || data.message || `Failed to update tier (${response.status})`);
  }
  return response.json();
}

async function deleteTier(shop: string | null, tierId: number): Promise<void> {
  const response = await authFetch(
    `${getApiUrl()}/members/tiers/${tierId}`,
    shop,
    { method: 'DELETE' }
  );
  if (!response.ok) {
    const data = await response.json();
    throw new Error(data.error || 'Failed to delete tier');
  }
}

export function EmbeddedTiers({ shop }: TiersProps) {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingTier, setEditingTier] = useState<MembershipTier | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    monthly_price: '0',
    yearly_price: '',
    bonus_rate: 5, // Stored as percentage (5 = 5%)
    purchase_cashback_pct: 0,
    monthly_credit_amount: '0',
    credit_expiration_days: '',
    discount_percent: '0',
    free_shipping_threshold: '',
  });

  const { data: tiers, isLoading, error } = useQuery({
    queryKey: ['tiers', shop],
    queryFn: () => fetchTiers(shop),
    enabled: !!shop,
  });

  const createMutation = useMutation({
    mutationFn: (tier: Partial<MembershipTier>) => createTier(shop, tier),
    onSuccess: () => {
      setMutationError(null);
      queryClient.invalidateQueries({ queryKey: ['tiers'] });
      closeModal();
    },
    onError: (error: Error) => {
      setMutationError(error.message || 'Failed to create tier. Please try again.');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, tier }: { id: number; tier: Partial<MembershipTier> }) =>
      updateTier(shop, id, tier),
    onSuccess: () => {
      setMutationError(null);
      queryClient.invalidateQueries({ queryKey: ['tiers'] });
      closeModal();
    },
    onError: (error: Error) => {
      setMutationError(error.message || 'Failed to update tier. Please try again.');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteTier(shop, id),
    onSuccess: () => {
      setMutationError(null);
      queryClient.invalidateQueries({ queryKey: ['tiers'] });
      setDeleteConfirm(null);
    },
    onError: (error: Error) => {
      setMutationError(error.message || 'Failed to delete tier. Please try again.');
      setDeleteConfirm(null);
    },
  });

  const openModal = useCallback((tier?: MembershipTier) => {
    if (tier) {
      setEditingTier(tier);
      setFormData({
        name: tier.name,
        monthly_price: String(tier.monthly_price || 0),
        yearly_price: tier.yearly_price ? String(tier.yearly_price) : '',
        bonus_rate: (tier.bonus_rate || 0) * 100, // Convert from decimal to percentage
        purchase_cashback_pct: tier.purchase_cashback_pct || 0,
        monthly_credit_amount: String(tier.monthly_credit_amount || 0),
        credit_expiration_days: tier.credit_expiration_days ? String(tier.credit_expiration_days) : '',
        discount_percent: String(tier.benefits?.discount_percent || 0),
        free_shipping_threshold: tier.benefits?.free_shipping_threshold ? String(tier.benefits.free_shipping_threshold) : '',
      });
      // Show advanced if any advanced settings have values
      setShowAdvanced(
        (tier.purchase_cashback_pct || 0) > 0 ||
        (tier.monthly_credit_amount || 0) > 0 ||
        !!tier.credit_expiration_days ||
        (tier.benefits?.discount_percent || 0) > 0 ||
        !!tier.benefits?.free_shipping_threshold
      );
    } else {
      setEditingTier(null);
      setFormData({
        name: '',
        monthly_price: '0',
        yearly_price: '',
        bonus_rate: 5,
        purchase_cashback_pct: 0,
        monthly_credit_amount: '0',
        credit_expiration_days: '',
        discount_percent: '0',
        free_shipping_threshold: '',
      });
      setShowAdvanced(false);
    }
    setModalOpen(true);
  }, []);

  const closeModal = useCallback(() => {
    setModalOpen(false);
    setEditingTier(null);
    setShowAdvanced(false);
    setMutationError(null);
  }, []);

  const handleSubmit = useCallback(() => {
    const tierData: Partial<MembershipTier> = {
      name: formData.name,
      monthly_price: parseFloat(formData.monthly_price) || 0,
      yearly_price: formData.yearly_price ? parseFloat(formData.yearly_price) : null,
      bonus_rate: formData.bonus_rate / 100, // Convert percentage to decimal
      purchase_cashback_pct: formData.purchase_cashback_pct || 0,
      monthly_credit_amount: parseFloat(formData.monthly_credit_amount) || 0,
      credit_expiration_days: formData.credit_expiration_days ? parseInt(formData.credit_expiration_days) : null,
      benefits: {
        discount_percent: parseFloat(formData.discount_percent) || 0,
        free_shipping_threshold: formData.free_shipping_threshold ? parseFloat(formData.free_shipping_threshold) : undefined,
      },
    };

    if (editingTier) {
      updateMutation.mutate({ id: editingTier.id, tier: tierData });
    } else {
      createMutation.mutate(tierData);
    }
  }, [formData, editingTier, createMutation, updateMutation]);

  if (!shop) {
    return (
      <Page title="Membership Tiers">
        <Banner tone="warning">
          <p>No shop connected. Please install the app from the Shopify App Store.</p>
        </Banner>
      </Page>
    );
  }

  if (isLoading) {
    return (
      <Page title="Membership Tiers">
        <Box padding="1600">
          <InlineStack align="center">
            <Spinner size="large" />
          </InlineStack>
        </Box>
      </Page>
    );
  }

  return (
    <Page
      title="Membership Tiers"
      subtitle="Configure tier benefits, pricing, and trade-in bonuses"
      primaryAction={{
        content: 'Add Tier',
        icon: PlusIcon,
        onAction: () => openModal(),
      }}
    >
      <Layout>
        {error && (
          <Layout.Section>
            <Banner tone="critical">
              <p>Failed to load tiers. Please try refreshing the page.</p>
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
            {tiers && tiers.length > 0 ? (
              <ResourceList
                resourceName={{ singular: 'tier', plural: 'tiers' }}
                items={tiers.filter(t => t && t.id != null)}
                renderItem={(tier) => (
                  <ResourceItem
                    id={String(tier.id)}
                    accessibilityLabel={tier.name || 'Tier'}
                    onClick={() => openModal(tier)}
                    media={
                      <Avatar
                        customer
                        size="md"
                        name={tier.name || 'Tier'}
                        initials={(tier.name || 'T').charAt(0)}
                        source={undefined}
                      />
                    }
                    shortcutActions={[
                      {
                        content: 'Edit',
                        onAction: () => openModal(tier),
                      },
                      {
                        content: 'Delete',
                        onAction: () => setDeleteConfirm(tier.id),
                      },
                    ]}
                  >
                    <InlineStack align="space-between" blockAlign="center" wrap={false}>
                      <BlockStack gap="100">
                        <InlineStack gap="200" blockAlign="center">
                          <Text as="h3" variant="bodyMd" fontWeight="bold">
                            {tier.name}
                          </Text>
                          {!tier.is_active && (
                            <Badge tone="warning">Inactive</Badge>
                          )}
                        </InlineStack>
                        <InlineStack gap="300" wrap>
                          <Text as="span" variant="bodySm" tone="subdued">
                            ${(tier.monthly_price || 0).toFixed(2)}/mo
                          </Text>
                          <Text as="span" variant="bodySm" tone="subdued">
                            Bonus: {((tier.bonus_rate || 0) * 100).toFixed(0)}%
                          </Text>
                          {(tier.purchase_cashback_pct || 0) > 0 && (
                            <Text as="span" variant="bodySm" tone="success">
                              Cashback: {tier.purchase_cashback_pct}%
                            </Text>
                          )}
                          {(tier.monthly_credit_amount || 0) > 0 && (
                            <Text as="span" variant="bodySm" tone="subdued">
                              Monthly: ${tier.monthly_credit_amount}
                            </Text>
                          )}
                        </InlineStack>
                      </BlockStack>
                      <Badge tone="success">
                        {`${((tier.bonus_rate || 0) * 100).toFixed(0)}% trade-in bonus`}
                      </Badge>
                    </InlineStack>
                  </ResourceItem>
                )}
              />
            ) : (
              <EmptyState
                heading="Create your first membership tier"
                action={{
                  content: 'Add Tier',
                  onAction: () => openModal(),
                }}
                image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
              >
                <p>
                  Membership tiers define the trade-in bonuses and benefits customers receive.
                  Higher tiers can offer better rates to reward loyal customers.
                </p>
              </EmptyState>
            )}
          </Card>
        </Layout.Section>

        <Layout.Section variant="oneThird">
          <Card>
            <BlockStack gap="400">
              <Text as="h3" variant="headingMd">How Tiers Work</Text>
              <BlockStack gap="200">
                <Text as="p" variant="bodySm">
                  <strong>Trade-in Bonus:</strong> Extra credit given on top of trade-in value.
                  A 10% bonus on a $100 trade-in = $10 extra credit.
                </Text>
                <Text as="p" variant="bodySm">
                  <strong>Purchase Cashback:</strong> Store credit earned on every purchase.
                  2% cashback on a $50 order = $1 credit.
                </Text>
                <Text as="p" variant="bodySm">
                  <strong>Monthly Credit:</strong> Auto-issued store credit on the 1st of each month
                  for active members.
                </Text>
              </BlockStack>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>

      {/* Create/Edit Modal */}
      <Modal
        open={modalOpen}
        onClose={closeModal}
        title={editingTier ? 'Edit Tier' : 'Create Tier'}
        primaryAction={{
          content: editingTier ? 'Save' : 'Create',
          onAction: handleSubmit,
          loading: createMutation.isPending || updateMutation.isPending,
          disabled: !formData.name.trim(),
        }}
        secondaryActions={[{ content: 'Cancel', onAction: closeModal }]}
      >
        <Modal.Section>
          <FormLayout>
            <TextField
              label="Tier Name"
              value={formData.name}
              onChange={(value) => setFormData({ ...formData, name: value })}
              placeholder="e.g., Gold, Platinum, VIP"
              autoComplete="off"
              helpText="Choose a memorable name for this tier"
            />

            <InlineStack gap="400" wrap={false}>
              <Box minWidth="45%">
                <TextField
                  label="Monthly Price"
                  type="number"
                  value={formData.monthly_price}
                  onChange={(value) => setFormData({ ...formData, monthly_price: value })}
                  prefix="$"
                  helpText="Set to $0 for free tiers"
                  autoComplete="off"
                />
              </Box>
              <Box minWidth="45%">
                <TextField
                  label="Yearly Price (optional)"
                  type="number"
                  value={formData.yearly_price}
                  onChange={(value) => setFormData({ ...formData, yearly_price: value })}
                  prefix="$"
                  placeholder="Optional"
                  helpText="Discounted annual option"
                  autoComplete="off"
                />
              </Box>
            </InlineStack>

            <BlockStack gap="200">
              <Text as="p" variant="bodyMd" fontWeight="semibold">
                Trade-in Bonus Rate
              </Text>
              <RangeSlider
                label=""
                value={formData.bonus_rate}
                onChange={(value) => setFormData({ ...formData, bonus_rate: value as number })}
                min={0}
                max={30}
                step={1}
                output
                suffix={<Text as="span" variant="bodyMd">{formData.bonus_rate}%</Text>}
              />
              <Text as="p" variant="bodySm" tone="subdued">
                Extra credit given on top of trade-in value (e.g., 10% bonus on $100 trade = $10 extra)
              </Text>
            </BlockStack>

            <Divider />

            {/* Advanced Settings Toggle */}
            <Button
              onClick={() => setShowAdvanced(!showAdvanced)}
              icon={showAdvanced ? ChevronUpIcon : ChevronDownIcon}
              variant="plain"
              fullWidth
              textAlign="left"
            >
              {showAdvanced ? 'Hide Advanced Settings' : 'Show Advanced Settings'}
            </Button>

            <Collapsible
              open={showAdvanced}
              id="advanced-settings"
              transition={{ duration: '200ms', timingFunction: 'ease-in-out' }}
            >
              <BlockStack gap="400">
                <BlockStack gap="200">
                  <Text as="p" variant="bodyMd" fontWeight="semibold">
                    Purchase Cashback %
                  </Text>
                  <RangeSlider
                    label=""
                    value={formData.purchase_cashback_pct}
                    onChange={(value) => setFormData({ ...formData, purchase_cashback_pct: value as number })}
                    min={0}
                    max={10}
                    step={0.5}
                    output
                    suffix={<Text as="span" variant="bodyMd">{formData.purchase_cashback_pct}%</Text>}
                  />
                  <Text as="p" variant="bodySm" tone="subdued">
                    Store credit earned on every purchase (e.g., 2% = $2 back per $100)
                  </Text>
                </BlockStack>

                <TextField
                  label="Recurring Monthly Credit"
                  type="number"
                  value={formData.monthly_credit_amount}
                  onChange={(value) => setFormData({ ...formData, monthly_credit_amount: value })}
                  prefix="$"
                  helpText="Auto-issued store credit on 1st of each month"
                  autoComplete="off"
                />

                <TextField
                  label="Credit Expiration (Days)"
                  type="number"
                  value={formData.credit_expiration_days}
                  onChange={(value) => setFormData({ ...formData, credit_expiration_days: value })}
                  placeholder="Never expires"
                  helpText="Days until issued credit expires (leave blank for no expiration)"
                  autoComplete="off"
                />

                <TextField
                  label="Store Discount (%)"
                  type="number"
                  value={formData.discount_percent}
                  onChange={(value) => setFormData({ ...formData, discount_percent: value })}
                  suffix="%"
                  helpText="Automatic discount on all purchases for tier members"
                  autoComplete="off"
                />

                <TextField
                  label="Free Shipping Threshold"
                  type="number"
                  value={formData.free_shipping_threshold}
                  onChange={(value) => setFormData({ ...formData, free_shipping_threshold: value })}
                  prefix="$"
                  placeholder="No free shipping"
                  helpText="Order minimum for free shipping (0 = always free, blank = no benefit)"
                  autoComplete="off"
                />
              </BlockStack>
            </Collapsible>
          </FormLayout>
        </Modal.Section>
      </Modal>

      {/* Delete Confirmation */}
      <Modal
        open={deleteConfirm !== null}
        onClose={() => setDeleteConfirm(null)}
        title="Delete Tier"
        primaryAction={{
          content: 'Delete',
          destructive: true,
          onAction: () => deleteConfirm && deleteMutation.mutate(deleteConfirm),
          loading: deleteMutation.isPending,
        }}
        secondaryActions={[
          { content: 'Cancel', onAction: () => setDeleteConfirm(null) },
        ]}
      >
        <Modal.Section>
          <Text as="p">
            Are you sure you want to delete this tier? This action cannot be undone.
            Members currently in this tier will need to be reassigned.
          </Text>
        </Modal.Section>
      </Modal>
    </Page>
  );
}
