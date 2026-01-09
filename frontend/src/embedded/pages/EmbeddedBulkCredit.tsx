/**
 * TradeUp Bulk Credit - Shopify Embedded Version
 *
 * Issue store credit to multiple members at once.
 * Uses Shopify Polaris for consistent UX.
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
  Button,
  TextField,
  Select,
  Banner,
  Spinner,
  EmptyState,
  Modal,
  ResourceList,
  ResourceItem,
  InlineGrid,
  Tag,
  Divider,
} from '@shopify/polaris';
import { PlusIcon, CheckIcon } from '@shopify/polaris-icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface BulkCreditProps {
  shop: string | null;
}

interface BulkCreditOperation {
  id: number;
  name: string;
  description: string | null;
  amount_per_member: number;
  total_amount: number;
  member_count: number;
  tier_filter: string | null;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  created_by: string;
  created_at: string;
  executed_at: string | null;
}

interface PreviewData {
  operation: BulkCreditOperation;
  member_count: number;
  total_amount: number;
  members: Array<{ id: number; email: string; tier: string }>;
}

interface MembershipTier {
  id: number;
  name: string;
  description: string | null;
  color: string;
  active: boolean;
}

interface TiersResponse {
  tiers: MembershipTier[];
}

async function fetchTiers(shop: string | null): Promise<TiersResponse> {
  const response = await authFetch(`${getApiUrl()}/members/tiers`, shop);
  if (!response.ok) throw new Error('Failed to fetch tiers');
  return response.json();
}

async function fetchOperations(
  shop: string | null
): Promise<{ operations: BulkCreditOperation[] }> {
  const response = await authFetch(`${getApiUrl()}/promotions/credit/bulk`, shop);
  if (!response.ok) throw new Error('Failed to fetch operations');
  return response.json();
}

async function createOperation(
  shop: string | null,
  data: {
    name: string;
    description?: string;
    amount_per_member: number;
    tier_filter?: string;
  }
): Promise<BulkCreditOperation> {
  const response = await authFetch(`${getApiUrl()}/promotions/credit/bulk`, shop, {
    method: 'POST',
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to create operation');
  return response.json();
}

async function previewOperation(
  shop: string | null,
  operationId: number
): Promise<{ member_count: number; total_amount: number; members: Array<{ id: number; email: string; tier: string }> }> {
  const response = await authFetch(`${getApiUrl()}/promotions/credit/bulk/${operationId}/preview`, shop);
  if (!response.ok) throw new Error('Failed to preview operation');
  return response.json();
}

async function executeOperation(
  shop: string | null,
  operationId: number
): Promise<void> {
  const response = await authFetch(`${getApiUrl()}/promotions/credit/bulk/${operationId}/execute`, shop, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to execute operation');
}

export function EmbeddedBulkCredit({ shop }: BulkCreditProps) {
  const queryClient = useQueryClient();
  const [showModal, setShowModal] = useState(false);
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);
  const [error, setError] = useState('');

  // Form state
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formAmount, setFormAmount] = useState('5.00');
  const [formTierFilter, setFormTierFilter] = useState('');

  const { data, isLoading, error: fetchError } = useQuery({
    queryKey: ['bulk-credit', shop],
    queryFn: () => fetchOperations(shop),
    enabled: !!shop,
  });

  // Fetch tiers for filter dropdown
  const { data: tiersData } = useQuery({
    queryKey: ['tiers', shop],
    queryFn: () => fetchTiers(shop),
    enabled: !!shop,
    staleTime: 60000, // Tiers don't change often
  });

  // Build tier filter options from backend data
  const tierFilterOptions = [
    { label: 'All Active Members', value: '' },
    ...(tiersData?.tiers
      ? tiersData.tiers.filter(t => t.active && t.name).map(tier => ({
          label: `${tier.name} Only`,
          value: tier.name?.toUpperCase() || '',
        }))
      : []),
  ];

  // Create mutation
  const createMutation = useMutation({
    mutationFn: async () => {
      const operation = await createOperation(shop, {
        name: formName,
        description: formDescription || undefined,
        amount_per_member: parseFloat(formAmount),
        tier_filter: formTierFilter || undefined,
      });
      const preview = await previewOperation(shop, operation.id);
      return { operation, ...preview };
    },
    onSuccess: (result) => {
      setPreviewData(result);
      setShowModal(false);
    },
    onError: (err: Error) => setError(err.message),
  });

  // Execute mutation
  const executeMutation = useMutation({
    mutationFn: (operationId: number) => executeOperation(shop, operationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bulk-credit'] });
      setPreviewData(null);
    },
    onError: (err: Error) => setError(err.message),
  });

  const openNewModal = useCallback(() => {
    setFormName('');
    setFormDescription('');
    setFormAmount('5.00');
    setFormTierFilter('');
    setError('');
    setShowModal(true);
  }, []);

  const handleSubmit = useCallback(() => {
    if (!formName.trim()) {
      setError('Operation name is required');
      return;
    }
    if (parseFloat(formAmount) <= 0) {
      setError('Amount must be greater than 0');
      return;
    }
    createMutation.mutate();
  }, [formName, formAmount, createMutation]);

  const handleExecute = useCallback(() => {
    if (previewData) {
      executeMutation.mutate(previewData.operation.id);
    }
  }, [previewData, executeMutation]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString();
  };

  const getStatusBadge = (status: string) => {
    const tones: Record<string, 'success' | 'warning' | 'critical' | 'info' | undefined> = {
      pending: 'warning',
      processing: 'info',
      completed: 'success',
      failed: 'critical',
    };
    return <Badge tone={tones[status]}>{status}</Badge>;
  };

  if (!shop) {
    return (
      <Page title="Bulk Credit">
        <Banner tone="warning">
          <p>No shop connected. Please install the app from the Shopify App Store.</p>
        </Banner>
      </Page>
    );
  }

  const operations = data?.operations || [];

  return (
    <Page
      title="Bulk Credit Operations"
      subtitle="Issue store credit to multiple members at once"
      primaryAction={{
        content: 'New Bulk Credit',
        icon: PlusIcon,
        onAction: openNewModal,
      }}
    >
      <Layout>
        {fetchError && (
          <Layout.Section>
            <Banner tone="critical">
              <p>Failed to load operations. Please try refreshing the page.</p>
            </Banner>
          </Layout.Section>
        )}

        {error && (
          <Layout.Section>
            <Banner tone="critical" onDismiss={() => setError('')}>
              <p>{error}</p>
            </Banner>
          </Layout.Section>
        )}

        {/* Preview Panel */}
        {previewData && (
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <InlineStack gap="200" blockAlign="center">
                  <Badge tone="success">Ready to Execute</Badge>
                  <Text as="h2" variant="headingMd">
                    {previewData.operation.name}
                  </Text>
                </InlineStack>

                {previewData.operation.description && (
                  <Text as="p" tone="subdued">
                    {previewData.operation.description}
                  </Text>
                )}

                <InlineGrid columns={3} gap="400">
                  <Card background="bg-surface-secondary">
                    <BlockStack gap="100" inlineAlign="center">
                      <Text as="p" variant="headingXl" fontWeight="bold">
                        {previewData.member_count}
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Members
                      </Text>
                    </BlockStack>
                  </Card>
                  <Card background="bg-surface-secondary">
                    <BlockStack gap="100" inlineAlign="center">
                      <Text as="p" variant="headingXl" fontWeight="bold" tone="success">
                        {formatCurrency(previewData.operation.amount_per_member)}
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Per Member
                      </Text>
                    </BlockStack>
                  </Card>
                  <Card background="bg-surface-secondary">
                    <BlockStack gap="100" inlineAlign="center">
                      <Text as="p" variant="headingXl" fontWeight="bold" tone="caution">
                        {formatCurrency(previewData.total_amount)}
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Total Credit
                      </Text>
                    </BlockStack>
                  </Card>
                </InlineGrid>

                {previewData.members.length > 0 && (
                  <BlockStack gap="200">
                    <Text as="h3" variant="headingSm">
                      Sample Recipients ({previewData.members.length} of {previewData.member_count})
                    </Text>
                    <InlineStack gap="200" wrap>
                      {previewData.members.map((m) => (
                        <Tag key={m.id}>
                          {m.email} ({m.tier})
                        </Tag>
                      ))}
                    </InlineStack>
                  </BlockStack>
                )}

                <Divider />

                <InlineStack gap="300" align="end">
                  <Button onClick={() => setPreviewData(null)}>Cancel</Button>
                  <Button
                    variant="primary"
                    tone="success"
                    icon={CheckIcon}
                    onClick={handleExecute}
                    loading={executeMutation.isPending}
                  >
                    Execute Now
                  </Button>
                </InlineStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        )}

        {/* Operations History */}
        <Layout.Section>
          <Card padding="0">
            <Box padding="400" borderBlockEndWidth="025" borderColor="border">
              <Text as="h2" variant="headingMd">
                Operation History
              </Text>
            </Box>

            {isLoading ? (
              <Box padding="1600">
                <InlineStack align="center">
                  <Spinner size="large" />
                </InlineStack>
              </Box>
            ) : operations.length > 0 ? (
              <ResourceList
                resourceName={{ singular: 'operation', plural: 'operations' }}
                items={operations}
                renderItem={(op) => (
                  <ResourceItem id={String(op.id)} onClick={() => {}}>
                    <InlineStack align="space-between" blockAlign="center">
                      <BlockStack gap="100">
                        <InlineStack gap="200" blockAlign="center">
                          <Text as="h3" variant="bodyMd" fontWeight="semibold">
                            {op.name}
                          </Text>
                          {getStatusBadge(op.status)}
                          {op.tier_filter && (
                            <Tag>{op.tier_filter.split(',').join(', ')}</Tag>
                          )}
                        </InlineStack>
                        {op.description && (
                          <Text as="p" variant="bodySm" tone="subdued">
                            {op.description}
                          </Text>
                        )}
                        <Text as="p" variant="bodySm" tone="subdued">
                          {formatDate(op.created_at)} by {op.created_by}
                        </Text>
                      </BlockStack>

                      <BlockStack gap="100" inlineAlign="end">
                        {op.status === 'completed' ? (
                          <>
                            <Text as="span" variant="bodyMd" fontWeight="semibold" tone="success">
                              {formatCurrency(op.total_amount)}
                            </Text>
                            <Text as="span" variant="bodySm" tone="subdued">
                              {op.member_count} members @ {formatCurrency(op.amount_per_member)}/ea
                            </Text>
                          </>
                        ) : (
                          <Text as="span" variant="bodySm" tone="subdued">
                            {formatCurrency(op.amount_per_member)}/member
                          </Text>
                        )}
                      </BlockStack>
                    </InlineStack>
                  </ResourceItem>
                )}
              />
            ) : (
              <Box padding="1600">
                <EmptyState
                  heading="No bulk credit operations yet"
                  image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                  action={{
                    content: 'Create Operation',
                    icon: PlusIcon,
                    onAction: openNewModal,
                  }}
                >
                  <p>
                    Issue store credit to multiple members at once for promotions, thank you
                    bonuses, or loyalty rewards.
                  </p>
                </EmptyState>
              </Box>
            )}
          </Card>
        </Layout.Section>
      </Layout>

      {/* Create Modal */}
      <Modal
        open={showModal}
        onClose={() => setShowModal(false)}
        title="New Bulk Credit"
        primaryAction={{
          content: 'Preview',
          onAction: handleSubmit,
          loading: createMutation.isPending,
          disabled: !formName.trim() || parseFloat(formAmount) <= 0,
        }}
        secondaryActions={[{ content: 'Cancel', onAction: () => setShowModal(false) }]}
      >
        <Modal.Section>
          <BlockStack gap="400">
            <TextField
              label="Operation Name"
              value={formName}
              onChange={setFormName}
              placeholder="Holiday Thank You Bonus"
              autoComplete="off"
              requiredIndicator
              autoFocus
            />

            <TextField
              label="Description"
              value={formDescription}
              onChange={setFormDescription}
              placeholder="Thank you for being a loyal member!"
              autoComplete="off"
              multiline={2}
            />

            <TextField
              label="Amount Per Member"
              type="number"
              value={formAmount}
              onChange={setFormAmount}
              prefix="$"
              autoComplete="off"
              requiredIndicator
            />

            <Select
              label="Filter by Tier"
              options={tierFilterOptions}
              value={formTierFilter}
              onChange={setFormTierFilter}
            />
          </BlockStack>
        </Modal.Section>
      </Modal>
    </Page>
  );
}
