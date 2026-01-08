/**
 * TradeUp Trade-Ins - Shopify Embedded Version
 *
 * View and manage trade-in submissions.
 */
import { useState, useCallback } from 'react';
import {
  Page,
  Layout,
  Card,
  Text,
  InlineStack,
  BlockStack,
  Badge,
  Button,
  DataTable,
  Pagination,
  Banner,
  Spinner,
  EmptyState,
  Modal,
  Box,
  Tabs,
} from '@shopify/polaris';
import { ViewIcon, PlusIcon, CheckIcon, XIcon } from '@shopify/polaris-icons';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface TradeInsProps {
  shop: string | null;
}

interface TradeInItem {
  id: number;
  product_title: string;
  product_sku: string | null;
  trade_value: number;
  market_value: number | null;
  listing_price: number | null;
  listed_date: string | null;
  sold_date: string | null;
  sold_price: number | null;
}

interface TradeInBatch {
  id: number;
  member_id: number | null;
  is_member: boolean;
  member_number: string | null;
  member_name: string | null;
  member_tier: string | null;
  guest_name: string | null;
  guest_email: string | null;
  guest_phone: string | null;
  batch_reference: string;
  trade_in_date: string;
  total_items: number;
  total_trade_value: number;
  bonus_amount: number;
  status: string;
  category: string;
  notes: string | null;
  created_by: string | null;
  created_at: string;
  completed_at: string | null;
  completed_by: string | null;
  items?: TradeInItem[];
}

interface TradeInsResponse {
  batches: TradeInBatch[];
  total: number;
  page: number;
  per_page: number;
}

async function fetchTradeIns(
  shop: string | null,
  page: number,
  status: string
): Promise<TradeInsResponse> {
  const params = new URLSearchParams();
  params.set('page', String(page));
  params.set('per_page', '20');
  if (status && status !== 'all') params.set('status', status);

  const response = await authFetch(`${getApiUrl()}/trade-ins?${params}`, shop);
  if (!response.ok) throw new Error('Failed to fetch trade-ins');
  return response.json();
}

async function updateTradeInStatus(
  shop: string | null,
  tradeInId: number,
  status: string
): Promise<void> {
  const response = await authFetch(`${getApiUrl()}/trade-ins/${tradeInId}/status`, shop, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
  if (!response.ok) throw new Error(`Failed to ${status} trade-in`);
}

export function EmbeddedTradeIns({ shop }: TradeInsProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [selectedTab, setSelectedTab] = useState(0);
  const [detailBatch, setDetailBatch] = useState<TradeInBatch | null>(null);
  const [actionError, setActionError] = useState('');

  const statusMap = ['all', 'pending', 'listed', 'completed', 'cancelled'];
  const currentStatus = statusMap[selectedTab];

  const { data, isLoading, error } = useQuery({
    queryKey: ['trade-ins', shop, page, currentStatus],
    queryFn: () => fetchTradeIns(shop, page, currentStatus),
    enabled: !!shop,
  });

  // Status update mutation
  const statusMutation = useMutation({
    mutationFn: ({ batchId, newStatus }: { batchId: number; newStatus: string }) =>
      updateTradeInStatus(shop, batchId, newStatus),
    onSuccess: (_, variables) => {
      // Update local state
      if (detailBatch) {
        setDetailBatch({ ...detailBatch, status: variables.newStatus });
      }
      // Invalidate queries to refresh the list
      queryClient.invalidateQueries({ queryKey: ['trade-ins'] });
      setActionError('');
    },
    onError: (err: Error) => {
      setActionError(err.message);
    },
  });

  const handleStatusChange = useCallback(
    (newStatus: string) => {
      if (detailBatch) {
        statusMutation.mutate({ batchId: detailBatch.id, newStatus });
      }
    },
    [detailBatch, statusMutation]
  );

  const handleTabChange = useCallback((index: number) => {
    setSelectedTab(index);
    setPage(1);
  }, []);

  if (!shop) {
    return (
      <Page title="Trade-Ins">
        <Banner tone="warning">
          <p>No shop connected. Please install the app from the Shopify App Store.</p>
        </Banner>
      </Page>
    );
  }

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
      listed: 'info',
      completed: 'success',
      cancelled: 'critical',
    };
    return <Badge tone={tones[status]}>{status}</Badge>;
  };

  const tabs = [
    { id: 'all', content: 'All', accessibilityLabel: 'All trade-ins' },
    { id: 'pending', content: 'Pending', accessibilityLabel: 'Pending trade-ins' },
    { id: 'listed', content: 'Listed', accessibilityLabel: 'Listed trade-ins' },
    { id: 'completed', content: 'Completed', accessibilityLabel: 'Completed trade-ins' },
    { id: 'cancelled', content: 'Cancelled', accessibilityLabel: 'Cancelled trade-ins' },
  ];

  return (
    <Page
      title="Trade-Ins"
      subtitle={`${data?.total || 0} total trade-ins`}
      primaryAction={{
        content: 'New Trade-In',
        icon: PlusIcon,
        onAction: () => navigate('/app/trade-ins/new'),
      }}
      secondaryActions={[
        {
          content: 'Manage Categories',
          onAction: () => navigate('/app/trade-ins/categories'),
        },
      ]}
    >
      <Layout>
        {error && (
          <Layout.Section>
            <Banner tone="critical">
              <p>Failed to load trade-ins. Please try refreshing the page.</p>
            </Banner>
          </Layout.Section>
        )}

        <Layout.Section>
          <Card padding="0">
            <Tabs tabs={tabs} selected={selectedTab} onSelect={handleTabChange}>
              {isLoading ? (
                <Box padding="1600">
                  <InlineStack align="center">
                    <Spinner size="large" />
                  </InlineStack>
                </Box>
              ) : data?.batches && data.batches.length > 0 ? (
                <>
                  <DataTable
                    columnContentTypes={[
                      'text',
                      'text',
                      'numeric',
                      'text',
                      'text',
                      'text',
                    ]}
                    headings={[
                      'Customer',
                      'Reference',
                      'Trade Value',
                      'Category',
                      'Status',
                      '',
                    ]}
                    rows={data.batches.map((batch) => [
                      <BlockStack gap="100" key={batch.id}>
                        <Text as="span" fontWeight="bold">
                          {batch.member_name || batch.guest_name || 'Unknown'}
                        </Text>
                        <Text as="p" variant="bodySm" tone="subdued">
                          {batch.is_member ? batch.member_tier || 'Member' : 'Guest'} • {formatDate(batch.created_at)}
                        </Text>
                      </BlockStack>,
                      <Text as="span" variant="bodySm" tone="subdued" key={`ref-${batch.id}`}>
                        {batch.batch_reference}
                      </Text>,
                      formatCurrency(batch.total_trade_value),
                      <Badge key={`cat-${batch.id}`}>{batch.category}</Badge>,
                      getStatusBadge(batch.status),
                      <Button
                        key={`view-${batch.id}`}
                        icon={ViewIcon}
                        variant="plain"
                        onClick={() => setDetailBatch(batch)}
                      >
                        View
                      </Button>,
                    ])}
                  />

                  <Box padding="400">
                    <InlineStack align="center">
                      <Pagination
                        hasPrevious={page > 1}
                        onPrevious={() => setPage(page - 1)}
                        hasNext={page < (data?.pages || 1)}
                        onNext={() => setPage(page + 1)}
                      />
                    </InlineStack>
                  </Box>
                </>
              ) : (
                <Box padding="1600">
                  <EmptyState
                    heading="No trade-ins found"
                    image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                  >
                    <p>
                      Trade-ins will appear here when members submit items.
                    </p>
                  </EmptyState>
                </Box>
              )}
            </Tabs>
          </Card>
        </Layout.Section>
      </Layout>

      {/* Trade-In Detail Modal */}
      <Modal
        open={detailBatch !== null}
        onClose={() => setDetailBatch(null)}
        title={`Trade-In ${detailBatch?.batch_reference || ''}`}
        secondaryActions={[
          { content: 'Close', onAction: () => setDetailBatch(null) },
        ]}
        size="large"
      >
        {detailBatch && (
          <Modal.Section>
            <BlockStack gap="400">
              {actionError && (
                <Banner tone="critical" onDismiss={() => setActionError('')}>
                  <p>{actionError}</p>
                </Banner>
              )}

              <InlineStack gap="800">
                <BlockStack gap="100">
                  <Text as="span" variant="bodySm" tone="subdued">
                    Customer
                  </Text>
                  <Text as="span">
                    {detailBatch.member_name || detailBatch.guest_name || 'Unknown'}
                  </Text>
                  <Text as="span" variant="bodySm" tone="subdued">
                    {detailBatch.is_member ? detailBatch.member_tier || 'Member' : 'Guest'}
                  </Text>
                </BlockStack>
                <BlockStack gap="100">
                  <Text as="span" variant="bodySm" tone="subdued">
                    Status
                  </Text>
                  {getStatusBadge(detailBatch.status)}
                </BlockStack>
                <BlockStack gap="100">
                  <Text as="span" variant="bodySm" tone="subdued">
                    Category
                  </Text>
                  <Badge>{detailBatch.category}</Badge>
                </BlockStack>
                <BlockStack gap="100">
                  <Text as="span" variant="bodySm" tone="subdued">
                    Trade Value
                  </Text>
                  <Text as="span" fontWeight="bold">
                    {formatCurrency(detailBatch.total_trade_value)}
                  </Text>
                </BlockStack>
              </InlineStack>

              {/* Status Action Buttons */}
              {detailBatch.status !== 'completed' && detailBatch.status !== 'rejected' && detailBatch.status !== 'cancelled' && (
                <Card>
                  <BlockStack gap="300">
                    <Text as="h3" variant="headingSm">
                      Actions
                    </Text>
                    <InlineStack gap="300">
                      {detailBatch.status === 'pending' && (
                        <>
                          <Button
                            variant="primary"
                            icon={CheckIcon}
                            onClick={() => handleStatusChange('listed')}
                            loading={statusMutation.isPending}
                          >
                            Mark Listed
                          </Button>
                          <Button
                            tone="critical"
                            icon={XIcon}
                            onClick={() => handleStatusChange('cancelled')}
                            loading={statusMutation.isPending}
                          >
                            Cancel
                          </Button>
                        </>
                      )}
                      {detailBatch.status === 'listed' && (
                        <>
                          <Button
                            variant="primary"
                            tone="success"
                            icon={CheckIcon}
                            onClick={() => handleStatusChange('completed')}
                            loading={statusMutation.isPending}
                          >
                            Complete & Issue Bonus
                          </Button>
                          <Button
                            tone="critical"
                            icon={XIcon}
                            onClick={() => handleStatusChange('cancelled')}
                            loading={statusMutation.isPending}
                          >
                            Cancel
                          </Button>
                        </>
                      )}
                    </InlineStack>
                  </BlockStack>
                </Card>
              )}

              {detailBatch.items && detailBatch.items.length > 0 && (
                <Card>
                  <Text as="h3" variant="headingSm">
                    Items ({detailBatch.items.length})
                  </Text>
                  <DataTable
                    columnContentTypes={['text', 'numeric', 'numeric']}
                    headings={['Item', 'Trade Value', 'Market Value']}
                    rows={detailBatch.items.map((item) => [
                      item.product_title || item.product_sku || 'Untitled item',
                      formatCurrency(item.trade_value),
                      item.market_value ? formatCurrency(item.market_value) : '—',
                    ])}
                    totals={[
                      'Total',
                      formatCurrency(detailBatch.total_trade_value),
                      '',
                    ]}
                  />
                </Card>
              )}

              {detailBatch.bonus_amount > 0 && (
                <Card>
                  <InlineStack gap="400" align="space-between">
                    <Text as="h3" variant="headingSm">
                      Tier Bonus Issued
                    </Text>
                    <Text as="span" fontWeight="bold" tone="success">
                      {formatCurrency(detailBatch.bonus_amount)}
                    </Text>
                  </InlineStack>
                </Card>
              )}

              {detailBatch.notes && (
                <Card>
                  <Text as="h3" variant="headingSm">
                    Notes
                  </Text>
                  <Text as="p">{detailBatch.notes}</Text>
                </Card>
              )}

              <Box paddingBlockStart="200">
                <Text as="p" variant="bodySm" tone="subdued">
                  Created {formatDate(detailBatch.created_at)}
                  {detailBatch.created_by && ` by ${detailBatch.created_by}`}
                  {detailBatch.completed_at && ` • Completed ${formatDate(detailBatch.completed_at)}`}
                </Text>
              </Box>
            </BlockStack>
          </Modal.Section>
        )}
      </Modal>
    </Page>
  );
}
