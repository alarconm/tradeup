/**
 * TradeUp Membership Tiers - Shopify Embedded Version
 *
 * Configure membership tiers with trade-in rates.
 * This is the core feature of TradeUp.
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
  Select,
  Banner,
  Spinner,
  EmptyState,
  ResourceList,
  ResourceItem,
  Avatar,
} from '@shopify/polaris';
import { PlusIcon } from '@shopify/polaris-icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface TiersProps {
  shop: string | null;
}

interface MembershipTier {
  id: number;
  name: string;
  slug: string;
  trade_in_rate: number;
  monthly_fee: number;
  min_spend_requirement: number | null;
  color: string;
  icon: string;
  benefits: string[];
  member_count: number;
  is_default: boolean;
  is_active: boolean;
}

async function fetchTiers(shop: string | null): Promise<MembershipTier[]> {
  const response = await authFetch(
    `${getApiUrl()}/membership/tiers`,
    shop
  );
  if (!response.ok) throw new Error('Failed to fetch tiers');
  return response.json();
}

async function createTier(
  shop: string | null,
  tier: Partial<MembershipTier>
): Promise<MembershipTier> {
  const response = await authFetch(
    `${getApiUrl()}/membership/tiers`,
    shop,
    {
      method: 'POST',
      body: JSON.stringify(tier),
    }
  );
  if (!response.ok) throw new Error('Failed to create tier');
  return response.json();
}

async function updateTier(
  shop: string | null,
  tierId: number,
  tier: Partial<MembershipTier>
): Promise<MembershipTier> {
  const response = await authFetch(
    `${getApiUrl()}/membership/tiers/${tierId}`,
    shop,
    {
      method: 'PUT',
      body: JSON.stringify(tier),
    }
  );
  if (!response.ok) throw new Error('Failed to update tier');
  return response.json();
}

async function deleteTier(shop: string | null, tierId: number): Promise<void> {
  const response = await authFetch(
    `${getApiUrl()}/membership/tiers/${tierId}`,
    shop,
    { method: 'DELETE' }
  );
  if (!response.ok) throw new Error('Failed to delete tier');
}

export function EmbeddedTiers({ shop }: TiersProps) {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingTier, setEditingTier] = useState<MembershipTier | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    trade_in_rate: '60',
    monthly_fee: '0',
    color: '#e85d27',
  });

  const { data: tiers, isLoading, error } = useQuery({
    queryKey: ['tiers', shop],
    queryFn: () => fetchTiers(shop),
    enabled: !!shop,
  });

  const createMutation = useMutation({
    mutationFn: (tier: Partial<MembershipTier>) => createTier(shop, tier),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tiers'] });
      closeModal();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, tier }: { id: number; tier: Partial<MembershipTier> }) =>
      updateTier(shop, id, tier),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tiers'] });
      closeModal();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteTier(shop, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tiers'] });
      setDeleteConfirm(null);
    },
  });

  const openModal = useCallback((tier?: MembershipTier) => {
    if (tier) {
      setEditingTier(tier);
      setFormData({
        name: tier.name,
        trade_in_rate: String(tier.trade_in_rate),
        monthly_fee: String(tier.monthly_fee),
        color: tier.color,
      });
    } else {
      setEditingTier(null);
      setFormData({
        name: '',
        trade_in_rate: '60',
        monthly_fee: '0',
        color: '#e85d27',
      });
    }
    setModalOpen(true);
  }, []);

  const closeModal = useCallback(() => {
    setModalOpen(false);
    setEditingTier(null);
  }, []);

  const handleSubmit = useCallback(() => {
    const tierData = {
      name: formData.name,
      trade_in_rate: parseFloat(formData.trade_in_rate),
      monthly_fee: parseFloat(formData.monthly_fee),
      color: formData.color,
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

  const colorOptions = [
    { label: 'Orange', value: '#e85d27' },
    { label: 'Bronze', value: '#cd7f32' },
    { label: 'Silver', value: '#c0c0c0' },
    { label: 'Gold', value: '#ffd700' },
    { label: 'Platinum', value: '#e5e4e2' },
    { label: 'Diamond', value: '#b9f2ff' },
  ];

  return (
    <Page
      title="Membership Tiers"
      subtitle="Configure the trade-in rates for each membership level"
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
                    <InlineStack align="space-between" blockAlign="center">
                      <BlockStack gap="100">
                        <InlineStack gap="200" blockAlign="center">
                          <Text as="h3" variant="bodyMd" fontWeight="bold">
                            {tier.name}
                          </Text>
                          {tier.is_default && (
                            <Badge tone="info">Default</Badge>
                          )}
                        </InlineStack>
                        <Text as="p" variant="bodySm" tone="subdued">
                          {tier.member_count} members
                        </Text>
                      </BlockStack>
                      <BlockStack gap="100" inlineAlign="end">
                        <Badge tone="success">
                          {`${tier.trade_in_rate}% trade-in rate`}
                        </Badge>
                        {tier.monthly_fee > 0 && (
                          <Text as="p" variant="bodySm" tone="subdued">
                            ${tier.monthly_fee}/month
                          </Text>
                        )}
                      </BlockStack>
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
                  Membership tiers define the trade-in rates customers receive.
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
              <Text as="p" variant="bodySm">
                Each tier has a trade-in rate (percentage of market value).
                When customers bring items to trade in, they receive store
                credit based on their tier's rate.
              </Text>
              <Text as="p" variant="bodySm">
                <strong>Example:</strong> A Gold tier member with a 70% rate
                trading in a $100 card receives $70 in store credit.
              </Text>
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
        }}
        secondaryActions={[{ content: 'Cancel', onAction: closeModal }]}
      >
        <Modal.Section>
          <FormLayout>
            <TextField
              label="Tier Name"
              value={formData.name}
              onChange={(value) => setFormData({ ...formData, name: value })}
              placeholder="e.g., Gold, Premium, VIP"
              autoComplete="off"
            />
            <TextField
              label="Trade-In Rate (%)"
              type="number"
              value={formData.trade_in_rate}
              onChange={(value) =>
                setFormData({ ...formData, trade_in_rate: value })
              }
              suffix="%"
              helpText="Percentage of market value customers receive as store credit"
              autoComplete="off"
            />
            <TextField
              label="Monthly Fee"
              type="number"
              value={formData.monthly_fee}
              onChange={(value) =>
                setFormData({ ...formData, monthly_fee: value })
              }
              prefix="$"
              helpText="Leave at $0 for free tiers"
              autoComplete="off"
            />
            <Select
              label="Color"
              options={colorOptions}
              value={formData.color}
              onChange={(value) => setFormData({ ...formData, color: value })}
            />
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
            Are you sure you want to delete this tier? Members in this tier
            will need to be reassigned.
          </Text>
        </Modal.Section>
      </Modal>
    </Page>
  );
}
