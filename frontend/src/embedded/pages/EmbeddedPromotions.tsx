/**
 * TradeUp Promotions - Shopify Embedded Version
 *
 * Manage store credit promotions, bonuses, and tier configurations.
 * Uses Shopify Polaris for consistent UX within the admin.
 */
import {
  Page,
  Layout,
  Card,
  Text,
  InlineStack,
  BlockStack,
  Box,
  Badge,
  Button,
  DataTable,
  EmptyState,
  Spinner,
  Banner,
  Modal,
  TextField,
  Select,
  Checkbox,
  FormLayout,
  Divider,
  ChoiceList,
  InlineGrid,
} from '@shopify/polaris';
import { PlusIcon, DeleteIcon, EditIcon } from '@shopify/polaris-icons';
import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface PromotionsProps {
  shop: string | null;
}

interface Promotion {
  id: number;
  name: string;
  description: string | null;
  code: string | null;
  promo_type: 'trade_in_bonus' | 'purchase_cashback' | 'flat_bonus' | 'multiplier';
  bonus_percent: number;
  bonus_flat: number;
  multiplier: number;
  starts_at: string;
  ends_at: string;
  daily_start_time: string | null;
  daily_end_time: string | null;
  channel: 'all' | 'in_store' | 'online';
  tier_restriction: string[] | null;
  stackable: boolean;
  max_uses: number | null;
  current_uses: number;
  active: boolean;
  is_active_now: boolean;
}

interface TierConfiguration {
  id: number;
  tier_name: string;
  monthly_price: number;
  yearly_price: number | null;
  trade_in_bonus_pct: number;
  purchase_cashback_pct: number;
  store_discount_pct: number;
  color: string;
  icon: string;
  features: string[];
  active: boolean;
}

interface PromotionsStats {
  active_promotions: number;
  promotions_ending_soon: number;
  total_cashback_30d: number;
  total_bulk_credits_30d: number;
}

const PROMO_TYPE_OPTIONS = [
  { label: 'Trade-In Bonus', value: 'trade_in_bonus' },
  { label: 'Purchase Cashback', value: 'purchase_cashback' },
  { label: 'Flat Bonus', value: 'flat_bonus' },
  { label: 'Credit Multiplier', value: 'multiplier' },
];

const CHANNEL_OPTIONS = [
  { label: 'All Channels', value: 'all' },
  { label: 'In-Store Only', value: 'in_store' },
  { label: 'Online Only', value: 'online' },
];

async function fetchPromotions(shop: string | null): Promise<{ promotions: Promotion[]; total: number }> {
  const response = await authFetch(`${getApiUrl()}/promotions/promotions`, shop);
  if (!response.ok) throw new Error('Failed to fetch promotions');
  return response.json();
}

async function fetchTiers(shop: string | null): Promise<{ tiers: TierConfiguration[] }> {
  const response = await authFetch(`${getApiUrl()}/promotions/tiers`, shop);
  if (!response.ok) throw new Error('Failed to fetch tiers');
  return response.json();
}

async function fetchStats(shop: string | null): Promise<PromotionsStats> {
  const response = await authFetch(`${getApiUrl()}/promotions/dashboard/stats`, shop);
  if (!response.ok) throw new Error('Failed to fetch stats');
  return response.json();
}

async function createPromotion(shop: string | null, data: Partial<Promotion>): Promise<Promotion> {
  const response = await authFetch(`${getApiUrl()}/promotions/promotions`, shop, {
    method: 'POST',
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to create promotion');
  return response.json();
}

async function updatePromotion(shop: string | null, id: number, data: Partial<Promotion>): Promise<Promotion> {
  const response = await authFetch(`${getApiUrl()}/promotions/promotions/${id}`, shop, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to update promotion');
  return response.json();
}

async function deletePromotion(shop: string | null, id: number): Promise<void> {
  const response = await authFetch(`${getApiUrl()}/promotions/promotions/${id}`, shop, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to delete promotion');
}

export function EmbeddedPromotions({ shop }: PromotionsProps) {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [editingPromo, setEditingPromo] = useState<Promotion | null>(null);
  const [promoToDelete, setPromoToDelete] = useState<Promotion | null>(null);
  const [activeTab, setActiveTab] = useState<'promotions' | 'tiers'>('promotions');

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    code: '',
    promo_type: 'trade_in_bonus' as Promotion['promo_type'],
    bonus_percent: 10,
    bonus_flat: 0,
    multiplier: 1,
    starts_at: new Date().toISOString().slice(0, 16),
    ends_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 16),
    channel: 'all' as Promotion['channel'],
    tier_restriction: [] as string[],
    stackable: true,
    max_uses: '',
    active: true,
  });

  const { data: promotionsData, isLoading: promotionsLoading, error: promotionsError } = useQuery({
    queryKey: ['promotions', shop],
    queryFn: () => fetchPromotions(shop),
    enabled: !!shop,
  });

  const { data: tiersData, isLoading: tiersLoading } = useQuery({
    queryKey: ['tiers', shop],
    queryFn: () => fetchTiers(shop),
    enabled: !!shop,
  });

  const { data: stats } = useQuery({
    queryKey: ['promotions-stats', shop],
    queryFn: () => fetchStats(shop),
    enabled: !!shop,
  });

  const createMutation = useMutation({
    mutationFn: (data: Partial<Promotion>) => createPromotion(shop, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['promotions'] });
      setModalOpen(false);
      resetForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Promotion> }) =>
      updatePromotion(shop, id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['promotions'] });
      setModalOpen(false);
      setEditingPromo(null);
      resetForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deletePromotion(shop, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['promotions'] });
      setDeleteModalOpen(false);
      setPromoToDelete(null);
    },
  });

  const resetForm = useCallback(() => {
    setFormData({
      name: '',
      description: '',
      code: '',
      promo_type: 'trade_in_bonus',
      bonus_percent: 10,
      bonus_flat: 0,
      multiplier: 1,
      starts_at: new Date().toISOString().slice(0, 16),
      ends_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 16),
      channel: 'all',
      tier_restriction: [],
      stackable: true,
      max_uses: '',
      active: true,
    });
  }, []);

  const openCreateModal = useCallback(() => {
    setEditingPromo(null);
    resetForm();
    setModalOpen(true);
  }, [resetForm]);

  const openEditModal = useCallback((promo: Promotion) => {
    setEditingPromo(promo);
    setFormData({
      name: promo.name,
      description: promo.description || '',
      code: promo.code || '',
      promo_type: promo.promo_type,
      bonus_percent: promo.bonus_percent,
      bonus_flat: promo.bonus_flat,
      multiplier: promo.multiplier,
      starts_at: promo.starts_at?.slice(0, 16) || '',
      ends_at: promo.ends_at?.slice(0, 16) || '',
      channel: promo.channel,
      tier_restriction: promo.tier_restriction || [],
      stackable: promo.stackable,
      max_uses: promo.max_uses?.toString() || '',
      active: promo.active,
    });
    setModalOpen(true);
  }, []);

  const confirmDelete = useCallback((promo: Promotion) => {
    setPromoToDelete(promo);
    setDeleteModalOpen(true);
  }, []);

  const handleSubmit = useCallback(() => {
    const data = {
      ...formData,
      max_uses: formData.max_uses ? parseInt(formData.max_uses) : null,
      tier_restriction: formData.tier_restriction.length > 0 ? formData.tier_restriction : null,
    };

    if (editingPromo) {
      updateMutation.mutate({ id: editingPromo.id, data });
    } else {
      createMutation.mutate(data);
    }
  }, [formData, editingPromo, createMutation, updateMutation]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const getStatusBadge = (promo: Promotion) => {
    if (!promo.active) return <Badge>Disabled</Badge>;
    if (promo.is_active_now) return <Badge tone="success">Active Now</Badge>;
    if (new Date(promo.starts_at) > new Date()) return <Badge tone="info">Scheduled</Badge>;
    return <Badge tone="warning">Ended</Badge>;
  };

  const getPromoValue = (promo: Promotion) => {
    if (promo.promo_type === 'flat_bonus') return `${formatCurrency(promo.bonus_flat)} flat`;
    if (promo.promo_type === 'multiplier') return `${promo.multiplier}x multiplier`;
    return `+${promo.bonus_percent}% bonus`;
  };

  if (!shop) {
    return (
      <Page title="Promotions">
        <Banner tone="warning">
          <p>No shop connected. Please install the app from the Shopify App Store.</p>
        </Banner>
      </Page>
    );
  }

  if (promotionsLoading || tiersLoading) {
    return (
      <Page title="Promotions">
        <Box padding="1600">
          <InlineStack align="center">
            <Spinner size="large" />
          </InlineStack>
        </Box>
      </Page>
    );
  }

  if (promotionsError) {
    return (
      <Page title="Promotions">
        <Banner tone="critical">
          <p>Failed to load promotions. Please try refreshing the page.</p>
        </Banner>
      </Page>
    );
  }

  const promotions = promotionsData?.promotions || [];
  const tiers = tiersData?.tiers || [];

  return (
    <Page
      title="Promotions & Bonuses"
      subtitle="Create special offers and manage tier benefits"
      primaryAction={{
        content: 'New Promotion',
        icon: PlusIcon,
        onAction: openCreateModal,
      }}
    >
      <Layout>
        {/* Stats Cards */}
        <Layout.Section>
          <InlineGrid columns={4} gap="400">
            <Card>
              <BlockStack gap="200">
                <Text as="h3" variant="headingSm" tone="subdued">Active Promotions</Text>
                <Text as="p" variant="headingXl">{stats?.active_promotions || 0}</Text>
              </BlockStack>
            </Card>
            <Card>
              <BlockStack gap="200">
                <Text as="h3" variant="headingSm" tone="subdued">Ending Soon</Text>
                <Text as="p" variant="headingXl">{stats?.promotions_ending_soon || 0}</Text>
              </BlockStack>
            </Card>
            <Card>
              <BlockStack gap="200">
                <Text as="h3" variant="headingSm" tone="subdued">Cashback (30d)</Text>
                <Text as="p" variant="headingXl">{formatCurrency(stats?.total_cashback_30d || 0)}</Text>
              </BlockStack>
            </Card>
            <Card>
              <BlockStack gap="200">
                <Text as="h3" variant="headingSm" tone="subdued">Bulk Credits (30d)</Text>
                <Text as="p" variant="headingXl">{formatCurrency(stats?.total_bulk_credits_30d || 0)}</Text>
              </BlockStack>
            </Card>
          </InlineGrid>
        </Layout.Section>

        {/* Tab Navigation */}
        <Layout.Section>
          <InlineStack gap="200">
            <Button
              pressed={activeTab === 'promotions'}
              onClick={() => setActiveTab('promotions')}
            >
              {`Promotions (${promotions.length})`}
            </Button>
            <Button
              pressed={activeTab === 'tiers'}
              onClick={() => setActiveTab('tiers')}
            >
              {`Tier Benefits (${tiers.length})`}
            </Button>
          </InlineStack>
        </Layout.Section>

        {/* Promotions List */}
        {activeTab === 'promotions' && (
          <Layout.Section>
            <Card>
              {promotions.length > 0 ? (
                <DataTable
                  columnContentTypes={['text', 'text', 'text', 'text', 'text', 'text']}
                  headings={['Name', 'Type', 'Value', 'Schedule', 'Status', 'Actions']}
                  rows={promotions.map((promo) => [
                    <BlockStack gap="100" key={promo.id}>
                      <Text as="span" variant="bodyMd" fontWeight="semibold">{promo.name}</Text>
                      {promo.code && <Badge>{promo.code}</Badge>}
                    </BlockStack>,
                    PROMO_TYPE_OPTIONS.find(o => o.value === promo.promo_type)?.label || promo.promo_type,
                    getPromoValue(promo),
                    <Text as="span" variant="bodySm" key={promo.id}>
                      {new Date(promo.starts_at).toLocaleDateString()} - {new Date(promo.ends_at).toLocaleDateString()}
                    </Text>,
                    getStatusBadge(promo),
                    <InlineStack gap="200" key={promo.id}>
                      <Button
                        size="slim"
                        icon={EditIcon}
                        onClick={() => openEditModal(promo)}
                        accessibilityLabel={`Edit ${promo.name}`}
                      />
                      <Button
                        size="slim"
                        icon={DeleteIcon}
                        tone="critical"
                        onClick={() => confirmDelete(promo)}
                        accessibilityLabel={`Delete ${promo.name}`}
                      />
                    </InlineStack>,
                  ])}
                />
              ) : (
                <EmptyState
                  heading="No promotions yet"
                  action={{
                    content: 'Create your first promotion',
                    onAction: openCreateModal,
                  }}
                  image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                >
                  <p>Create promotions to offer bonuses and special deals to your members.</p>
                </EmptyState>
              )}
            </Card>
          </Layout.Section>
        )}

        {/* Tier Benefits */}
        {activeTab === 'tiers' && (
          <Layout.Section>
            <InlineGrid columns={3} gap="400">
              {tiers.map((tier) => (
                <Card key={tier.id}>
                  <BlockStack gap="300">
                    <InlineStack align="space-between">
                      <Text as="h3" variant="headingMd">{tier.tier_name}</Text>
                      <Badge tone={tier.active ? 'success' : undefined}>
                        {tier.active ? 'Active' : 'Inactive'}
                      </Badge>
                    </InlineStack>

                    <Text as="p" variant="headingLg">
                      {formatCurrency(tier.monthly_price)}/mo
                    </Text>

                    <Divider />

                    <BlockStack gap="200">
                      <InlineStack align="space-between">
                        <Text as="span" variant="bodySm">Trade-In Bonus</Text>
                        <Badge tone="success">{`+${tier.trade_in_bonus_pct}%`}</Badge>
                      </InlineStack>
                      <InlineStack align="space-between">
                        <Text as="span" variant="bodySm">Purchase Cashback</Text>
                        <Badge tone="info">{`${tier.purchase_cashback_pct}%`}</Badge>
                      </InlineStack>
                      <InlineStack align="space-between">
                        <Text as="span" variant="bodySm">Store Discount</Text>
                        <Badge>{`${tier.store_discount_pct}%`}</Badge>
                      </InlineStack>
                    </BlockStack>

                    {tier.features && tier.features.length > 0 && (
                      <>
                        <Divider />
                        <BlockStack gap="100">
                          {tier.features.map((feature, i) => (
                            <Text as="p" variant="bodySm" key={i}>
                              {feature}
                            </Text>
                          ))}
                        </BlockStack>
                      </>
                    )}
                  </BlockStack>
                </Card>
              ))}
            </InlineGrid>
          </Layout.Section>
        )}
      </Layout>

      {/* Create/Edit Promotion Modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingPromo ? 'Edit Promotion' : 'New Promotion'}
        primaryAction={{
          content: editingPromo ? 'Save Changes' : 'Create Promotion',
          onAction: handleSubmit,
          loading: createMutation.isPending || updateMutation.isPending,
        }}
        secondaryActions={[
          {
            content: 'Cancel',
            onAction: () => setModalOpen(false),
          },
        ]}
      >
        <Modal.Section>
          <FormLayout>
            <TextField
              label="Promotion Name"
              value={formData.name}
              onChange={(value) => setFormData({ ...formData, name: value })}
              autoComplete="off"
              requiredIndicator
            />

            <TextField
              label="Description"
              value={formData.description}
              onChange={(value) => setFormData({ ...formData, description: value })}
              multiline={2}
              autoComplete="off"
            />

            <TextField
              label="Promo Code (optional)"
              value={formData.code}
              onChange={(value) => setFormData({ ...formData, code: value.toUpperCase() })}
              autoComplete="off"
              helpText="Leave empty for automatic promotions"
            />

            <Select
              label="Promotion Type"
              options={PROMO_TYPE_OPTIONS}
              value={formData.promo_type}
              onChange={(value) => setFormData({ ...formData, promo_type: value as Promotion['promo_type'] })}
            />

            {formData.promo_type === 'flat_bonus' ? (
              <TextField
                label="Flat Bonus Amount"
                type="number"
                value={formData.bonus_flat.toString()}
                onChange={(value) => setFormData({ ...formData, bonus_flat: parseFloat(value) || 0 })}
                prefix="$"
                autoComplete="off"
              />
            ) : formData.promo_type === 'multiplier' ? (
              <TextField
                label="Multiplier"
                type="number"
                value={formData.multiplier.toString()}
                onChange={(value) => setFormData({ ...formData, multiplier: parseFloat(value) || 1 })}
                suffix="x"
                autoComplete="off"
              />
            ) : (
              <TextField
                label="Bonus Percentage"
                type="number"
                value={formData.bonus_percent.toString()}
                onChange={(value) => setFormData({ ...formData, bonus_percent: parseFloat(value) || 0 })}
                suffix="%"
                autoComplete="off"
              />
            )}

            <FormLayout.Group>
              <TextField
                label="Starts At"
                type="datetime-local"
                value={formData.starts_at}
                onChange={(value) => setFormData({ ...formData, starts_at: value })}
                autoComplete="off"
                requiredIndicator
              />
              <TextField
                label="Ends At"
                type="datetime-local"
                value={formData.ends_at}
                onChange={(value) => setFormData({ ...formData, ends_at: value })}
                autoComplete="off"
                requiredIndicator
              />
            </FormLayout.Group>

            <Select
              label="Channel"
              options={CHANNEL_OPTIONS}
              value={formData.channel}
              onChange={(value) => setFormData({ ...formData, channel: value as Promotion['channel'] })}
            />

            <ChoiceList
              title="Tier Restriction (optional)"
              choices={[
                { label: 'Silver', value: 'SILVER' },
                { label: 'Gold', value: 'GOLD' },
                { label: 'Platinum', value: 'PLATINUM' },
              ]}
              selected={formData.tier_restriction}
              onChange={(value) => setFormData({ ...formData, tier_restriction: value })}
              allowMultiple
            />

            <TextField
              label="Max Uses (optional)"
              type="number"
              value={formData.max_uses}
              onChange={(value) => setFormData({ ...formData, max_uses: value })}
              autoComplete="off"
              helpText="Leave empty for unlimited uses"
            />

            <Checkbox
              label="Stackable with other promotions"
              checked={formData.stackable}
              onChange={(value) => setFormData({ ...formData, stackable: value })}
            />

            <Checkbox
              label="Active"
              checked={formData.active}
              onChange={(value) => setFormData({ ...formData, active: value })}
            />
          </FormLayout>
        </Modal.Section>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        open={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        title="Delete Promotion"
        primaryAction={{
          content: 'Delete',
          destructive: true,
          onAction: () => promoToDelete && deleteMutation.mutate(promoToDelete.id),
          loading: deleteMutation.isPending,
        }}
        secondaryActions={[
          {
            content: 'Cancel',
            onAction: () => setDeleteModalOpen(false),
          },
        ]}
      >
        <Modal.Section>
          <Text as="p">
            Are you sure you want to delete "{promoToDelete?.name}"? This action cannot be undone.
          </Text>
        </Modal.Section>
      </Modal>
    </Page>
  );
}
