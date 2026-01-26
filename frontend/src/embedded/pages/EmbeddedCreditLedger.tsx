/**
 * TradeUp Credit Ledger - World-Class Store Credit Reporting
 *
 * Full-featured credit ledger view with:
 * - Filterable/searchable transactions
 * - Date range selection
 * - Export to CSV
 * - Summary statistics
 * - Event type breakdown
 */
import { useState, useCallback, useMemo } from 'react';
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
  DataTable,
  Pagination,
  Filters,
  ChoiceList,
  DatePicker,
  Popover,
  Icon,
  InlineGrid,
  Divider,
  EmptyState,
} from '@shopify/polaris';
import {
  ExportIcon,
  FilterIcon,
  SearchIcon,
  CalendarIcon,
  ArrowUpIcon,
  ArrowDownIcon,
} from '@shopify/polaris-icons';
import { useQuery } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface CreditLedgerProps {
  shop: string | null;
}

interface LedgerEntry {
  id: number;
  member_id: number;
  member_email?: string;
  member_name?: string;
  event_type: string;
  amount: number;
  balance_after: number;
  description: string | null;
  source_type: string | null;
  source_reference: string | null;
  promotion_name: string | null;
  channel: string | null;
  created_by: string | null;
  created_at: string | null;
}

interface LedgerResponse {
  entries: LedgerEntry[];
  pagination: {
    page: number;
    per_page: number;
    total_pages: number;
    total_items: number;
    has_next: boolean;
    has_prev: boolean;
  };
  summary: {
    total_credited: number;
    total_debited: number;
    net_change: number;
    total_transactions: number;
    unique_members: number;
  };
  filters_applied: Record<string, string | number | null>;
}

interface EventTypeInfo {
  type: string;
  count: number;
  total: number;
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  trade_in: 'Trade-In',
  purchase: 'Purchase Cashback',
  promotion: 'Promotion Bonus',
  adjustment: 'Manual Adjustment',
  bulk: 'Bulk Credit',
  referral: 'Referral Bonus',
  redemption: 'Redemption',
  expiration: 'Expired',
  birthday: 'Birthday Reward',
  anniversary: 'Anniversary Reward',
};

const EVENT_TYPE_TONES: Record<string, 'success' | 'warning' | 'critical' | 'info' | undefined> = {
  trade_in: 'success',
  purchase: 'success',
  promotion: 'info',
  adjustment: 'warning',
  bulk: 'info',
  referral: 'success',
  redemption: 'critical',
  expiration: 'critical',
  birthday: 'success',
  anniversary: 'success',
};

async function fetchLedger(
  shop: string | null,
  params: Record<string, string | number | undefined>
): Promise<LedgerResponse> {
  const queryParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') {
      queryParams.append(key, String(value));
    }
  });

  const response = await authFetch(
    `${getApiUrl()}/promotions/credit/ledger?${queryParams.toString()}`,
    shop
  );
  if (!response.ok) throw new Error('Failed to fetch ledger');
  return response.json();
}

async function fetchEventTypes(shop: string | null): Promise<{ event_types: EventTypeInfo[] }> {
  const response = await authFetch(`${getApiUrl()}/promotions/credit/ledger/event-types`, shop);
  if (!response.ok) throw new Error('Failed to fetch event types');
  return response.json();
}

export function EmbeddedCreditLedger({ shop }: CreditLedgerProps) {
  // Filter state
  const [page, setPage] = useState(1);
  const [perPage] = useState(25);
  const [search, setSearch] = useState('');
  const [eventTypeFilter, setEventTypeFilter] = useState<string[]>([]);
  const [dateRange, setDateRange] = useState<{ start?: Date; end?: Date }>({});
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [sortBy, setSortBy] = useState('created_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  // Build query params
  const queryParams = useMemo(() => {
    const params: Record<string, string | number | undefined> = {
      page,
      per_page: perPage,
      sort_by: sortBy,
      sort_dir: sortDir,
    };

    if (search) params.search = search;
    if (eventTypeFilter.length === 1) params.event_type = eventTypeFilter[0];
    if (dateRange.start) params.start_date = dateRange.start.toISOString();
    if (dateRange.end) params.end_date = dateRange.end.toISOString();

    return params;
  }, [page, perPage, search, eventTypeFilter, dateRange, sortBy, sortDir]);

  // Fetch data
  const { data, isLoading, error } = useQuery({
    queryKey: ['credit-ledger', shop, queryParams],
    queryFn: () => fetchLedger(shop, queryParams),
    enabled: !!shop,
  });

  const { data: eventTypesData } = useQuery({
    queryKey: ['credit-event-types', shop],
    queryFn: () => fetchEventTypes(shop),
    enabled: !!shop,
    staleTime: 60000,
  });

  // Handlers
  const handleSearchChange = useCallback((value: string) => {
    setSearch(value);
    setPage(1);
  }, []);

  const handleEventTypeChange = useCallback((selected: string[]) => {
    setEventTypeFilter(selected);
    setPage(1);
  }, []);

  const handleDateRangeChange = useCallback(
    (range: { start: Date; end: Date }) => {
      setDateRange(range);
      setPage(1);
      setShowDatePicker(false);
    },
    []
  );

  const handleClearFilters = useCallback(() => {
    setSearch('');
    setEventTypeFilter([]);
    setDateRange({});
    setPage(1);
  }, []);

  const handleExport = useCallback(() => {
    const queryString = new URLSearchParams();
    if (dateRange.start) queryString.append('start_date', dateRange.start.toISOString());
    if (dateRange.end) queryString.append('end_date', dateRange.end.toISOString());
    if (eventTypeFilter.length === 1) queryString.append('event_type', eventTypeFilter[0]);

    window.open(`${getApiUrl()}/promotions/credit/ledger/export?${queryString.toString()}`, '_blank');
  }, [dateRange, eventTypeFilter]);

  const handleSort = useCallback((column: string) => {
    setSortBy(prev => {
      if (prev === column) {
        setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
        return column;
      }
      setSortDir('desc');
      return column;
    });
  }, []);

  // Format helpers
  const formatCurrency = (amount: number) => {
    const formatted = new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(Math.abs(amount));
    return amount < 0 ? `-${formatted}` : formatted;
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const getEventTypeBadge = (type: string) => {
    const label = EVENT_TYPE_LABELS[type] || type;
    const tone = EVENT_TYPE_TONES[type];
    return <Badge tone={tone}>{label}</Badge>;
  };

  // Build table rows
  const rows = useMemo(() => {
    if (!data?.entries) return [];
    return data.entries.map((entry) => [
      formatDate(entry.created_at),
      entry.member_email || entry.member_name || `Member #${entry.member_id}`,
      getEventTypeBadge(entry.event_type),
      <Text
        as="span"
        tone={entry.amount >= 0 ? 'success' : 'critical'}
        fontWeight="semibold"
      >
        {entry.amount >= 0 ? '+' : ''}{formatCurrency(entry.amount)}
      </Text>,
      formatCurrency(entry.balance_after),
      entry.description || '-',
      entry.source_reference || '-',
    ]);
  }, [data?.entries]);

  // Event type filter options
  const eventTypeOptions = useMemo(() => {
    if (!eventTypesData?.event_types) return [];
    return eventTypesData.event_types.map((et) => ({
      label: `${EVENT_TYPE_LABELS[et.type] || et.type} (${et.count})`,
      value: et.type,
    }));
  }, [eventTypesData]);

  // Check if filters are applied
  const hasFilters = search || eventTypeFilter.length > 0 || dateRange.start || dateRange.end;

  if (!shop) {
    return (
      <Page title="Credit Ledger">
        <Banner tone="warning">
          <p>No shop connected. Please install the app from the Shopify App Store.</p>
        </Banner>
      </Page>
    );
  }

  return (
    <Page
      title="Store Credit Ledger"
      subtitle="Complete history of all store credit transactions"
      primaryAction={{
        content: 'Export CSV',
        icon: ExportIcon,
        onAction: handleExport,
      }}
    >
      <Layout>
        {error && (
          <Layout.Section>
            <Banner tone="critical">
              <p>Failed to load credit ledger. Please try refreshing the page.</p>
            </Banner>
          </Layout.Section>
        )}

        {/* Summary Stats */}
        {data?.summary && (
          <Layout.Section>
            <InlineGrid columns={{ xs: 2, sm: 4, lg: 5 }} gap="400">
              <Card padding="400">
                <BlockStack gap="100">
                  <Text as="p" variant="bodySm" tone="subdued">
                    Total Credited
                  </Text>
                  <Text as="p" variant="headingLg" tone="success" fontWeight="bold">
                    {formatCurrency(data.summary.total_credited)}
                  </Text>
                </BlockStack>
              </Card>
              <Card padding="400">
                <BlockStack gap="100">
                  <Text as="p" variant="bodySm" tone="subdued">
                    Total Debited
                  </Text>
                  <Text as="p" variant="headingLg" tone="critical" fontWeight="bold">
                    {formatCurrency(data.summary.total_debited)}
                  </Text>
                </BlockStack>
              </Card>
              <Card padding="400">
                <BlockStack gap="100">
                  <Text as="p" variant="bodySm" tone="subdued">
                    Net Change
                  </Text>
                  <Text
                    as="p"
                    variant="headingLg"
                    tone={data.summary.net_change >= 0 ? 'success' : 'critical'}
                    fontWeight="bold"
                  >
                    {formatCurrency(data.summary.net_change)}
                  </Text>
                </BlockStack>
              </Card>
              <Card padding="400">
                <BlockStack gap="100">
                  <Text as="p" variant="bodySm" tone="subdued">
                    Transactions
                  </Text>
                  <Text as="p" variant="headingLg" fontWeight="bold">
                    {data.summary.total_transactions.toLocaleString()}
                  </Text>
                </BlockStack>
              </Card>
              <Card padding="400">
                <BlockStack gap="100">
                  <Text as="p" variant="bodySm" tone="subdued">
                    Unique Members
                  </Text>
                  <Text as="p" variant="headingLg" fontWeight="bold">
                    {data.summary.unique_members.toLocaleString()}
                  </Text>
                </BlockStack>
              </Card>
            </InlineGrid>
          </Layout.Section>
        )}

        {/* Filters */}
        <Layout.Section>
          <Card padding="400">
            <InlineStack gap="300" blockAlign="center" wrap>
              <Box minWidth="250px">
                <TextField
                  label="Search"
                  labelHidden
                  placeholder="Search by email, description..."
                  value={search}
                  onChange={handleSearchChange}
                  autoComplete="off"
                  prefix={<Icon source={SearchIcon} />}
                  clearButton
                  onClearButtonClick={() => handleSearchChange('')}
                />
              </Box>

              <Box minWidth="200px">
                <Select
                  label="Event Type"
                  labelHidden
                  placeholder="All event types"
                  options={[
                    { label: 'All event types', value: '' },
                    ...eventTypeOptions,
                  ]}
                  value={eventTypeFilter[0] || ''}
                  onChange={(val) => handleEventTypeChange(val ? [val] : [])}
                />
              </Box>

              <Popover
                active={showDatePicker}
                activator={
                  <Button
                    icon={CalendarIcon}
                    onClick={() => setShowDatePicker(!showDatePicker)}
                  >
                    {dateRange.start
                      ? `${dateRange.start.toLocaleDateString()} - ${dateRange.end?.toLocaleDateString() || 'Now'}`
                      : 'Select dates'}
                  </Button>
                }
                onClose={() => setShowDatePicker(false)}
              >
                <Box padding="400">
                  <DatePicker
                    month={new Date().getMonth()}
                    year={new Date().getFullYear()}
                    onChange={handleDateRangeChange}
                    selected={dateRange.start ? { start: dateRange.start, end: dateRange.end || dateRange.start } : undefined}
                    allowRange
                  />
                  <Box paddingBlockStart="300">
                    <InlineStack gap="200">
                      <Button
                        size="slim"
                        onClick={() => {
                          const today = new Date();
                          const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
                          handleDateRangeChange({ start: weekAgo, end: today });
                        }}
                      >
                        Last 7 days
                      </Button>
                      <Button
                        size="slim"
                        onClick={() => {
                          const today = new Date();
                          const monthAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
                          handleDateRangeChange({ start: monthAgo, end: today });
                        }}
                      >
                        Last 30 days
                      </Button>
                      <Button
                        size="slim"
                        onClick={() => {
                          const today = new Date();
                          today.setHours(0, 0, 0, 0);
                          const tomorrow = new Date(today.getTime() + 24 * 60 * 60 * 1000);
                          handleDateRangeChange({ start: today, end: tomorrow });
                        }}
                      >
                        Today
                      </Button>
                    </InlineStack>
                  </Box>
                </Box>
              </Popover>

              {hasFilters && (
                <Button onClick={handleClearFilters} plain>
                  Clear all
                </Button>
              )}
            </InlineStack>
          </Card>
        </Layout.Section>

        {/* Data Table */}
        <Layout.Section>
          <Card padding="0">
            {isLoading ? (
              <Box padding="1600">
                <InlineStack align="center">
                  <Spinner size="large" />
                </InlineStack>
              </Box>
            ) : data && data.entries.length > 0 ? (
              <>
                <DataTable
                  columnContentTypes={['text', 'text', 'text', 'numeric', 'numeric', 'text', 'text']}
                  headings={[
                    <InlineStack gap="100" blockAlign="center">
                      Date
                      <Button
                        plain
                        icon={sortBy === 'created_at' ? (sortDir === 'desc' ? ArrowDownIcon : ArrowUpIcon) : undefined}
                        onClick={() => handleSort('created_at')}
                      />
                    </InlineStack>,
                    'Member',
                    'Type',
                    <InlineStack gap="100" blockAlign="center">
                      Amount
                      <Button
                        plain
                        icon={sortBy === 'amount' ? (sortDir === 'desc' ? ArrowDownIcon : ArrowUpIcon) : undefined}
                        onClick={() => handleSort('amount')}
                      />
                    </InlineStack>,
                    'Balance After',
                    'Description',
                    'Reference',
                  ]}
                  rows={rows}
                  hoverable
                />
                <Box padding="400" borderBlockStartWidth="025" borderColor="border">
                  <InlineStack align="center">
                    <Pagination
                      hasPrevious={data.pagination.has_prev}
                      hasNext={data.pagination.has_next}
                      onPrevious={() => setPage((p) => Math.max(1, p - 1))}
                      onNext={() => setPage((p) => p + 1)}
                    />
                    <Text as="span" tone="subdued" variant="bodySm">
                      Page {data.pagination.page} of {data.pagination.total_pages} ({data.pagination.total_items.toLocaleString()} total)
                    </Text>
                  </InlineStack>
                </Box>
              </>
            ) : (
              <Box padding="1600">
                <EmptyState
                  heading="No credit transactions found"
                  image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                >
                  <p>
                    {hasFilters
                      ? 'Try adjusting your filters to see more results.'
                      : 'Store credit transactions will appear here as members earn and redeem credits.'}
                  </p>
                </EmptyState>
              </Box>
            )}
          </Card>
        </Layout.Section>
      </Layout>
    </Page>
  );
}

export default EmbeddedCreditLedger;
