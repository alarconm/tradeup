/**
 * TradeUp Members - Shopify Embedded Version
 *
 * View and manage program members.
 */
import { useState, useCallback, useEffect } from 'react';
import {
  Page,
  Layout,
  Card,
  Text,
  InlineStack,
  BlockStack,
  Badge,
  Button,
  TextField,
  Filters,
  DataTable,
  Pagination,
  Banner,
  Spinner,
  EmptyState,
  Modal,
  ChoiceList,
  Box,
  FormLayout,
  Select,
  DropZone,
  List,
  Thumbnail,
  Divider,
} from '@shopify/polaris';
import { ExportIcon, EmailIcon, PlusIcon, SearchIcon, ImportIcon } from '@shopify/polaris-icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

// Credit expiration options
const CREDIT_EXPIRATION_OPTIONS = [
  { label: 'Never expires', value: '' },
  { label: '30 days', value: '30' },
  { label: '60 days', value: '60' },
  { label: '90 days', value: '90' },
  { label: '180 days', value: '180' },
  { label: '1 year (365 days)', value: '365' },
];

interface MembersProps {
  shop: string | null;
}

interface Member {
  id: number;
  shopify_customer_id: string;
  first_name: string;
  last_name: string;
  email: string;
  tier: {
    id: number;
    name: string;
    color: string;
  };
  total_trade_in_value: number;
  total_credits_issued: number;
  trade_in_count: number;
  status: string;
  created_at: string;
  last_trade_in_at: string | null;
}

interface MembersResponse {
  members: Member[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
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

async function fetchMembers(
  shop: string | null,
  page: number,
  search: string,
  tier: string
): Promise<MembersResponse> {
  const params = new URLSearchParams();
  params.set('page', String(page));
  params.set('per_page', '20');
  if (search) params.set('search', search);
  if (tier) params.set('tier', tier);

  const response = await authFetch(`${getApiUrl()}/members?${params}`, shop);
  if (!response.ok) throw new Error('Failed to fetch members');
  return response.json();
}

// Hook to detect mobile viewport
function useIsMobile(breakpoint: number = 768) {
  const [isMobile, setIsMobile] = useState(
    typeof window !== 'undefined' ? window.innerWidth < breakpoint : false
  );

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < breakpoint);
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, [breakpoint]);

  return isMobile;
}

export function EmbeddedMembers({ shop }: MembersProps) {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [selectedTier, setSelectedTier] = useState<string[]>([]);
  const [detailMember, setDetailMember] = useState<Member | null>(null);
  const [emailModalOpen, setEmailModalOpen] = useState(false);
  const [addMemberModalOpen, setAddMemberModalOpen] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const isMobile = useIsMobile();

  const { data, isLoading, error } = useQuery({
    queryKey: ['members', shop, page, search, selectedTier[0]],
    queryFn: () => fetchMembers(shop, page, search, selectedTier[0] || ''),
    enabled: !!shop,
  });

  // Fetch tiers for filter dropdown
  const { data: tiersData } = useQuery({
    queryKey: ['tiers', shop],
    queryFn: () => fetchTiers(shop),
    enabled: !!shop,
    staleTime: 60000, // Tiers don't change often
  });

  const handleSearchChange = useCallback((value: string) => {
    setSearch(value);
    setPage(1);
  }, []);

  const handleTierChange = useCallback((value: string[]) => {
    setSelectedTier(value);
    setPage(1);
  }, []);

  const handleClearFilters = useCallback(() => {
    setSearch('');
    setSelectedTier([]);
    setPage(1);
  }, []);

  if (!shop) {
    return (
      <Page title="Members">
        <Banner tone="warning">
          <p>No shop connected. Please install the app from the Shopify App Store.</p>
        </Banner>
      </Page>
    );
  }

  const formatCurrency = (amount: number | null | undefined) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount || 0);
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleDateString();
  };

  // Build tier filter choices from backend data
  // IMPORTANT: Check t exists first to prevent "Cannot read properties of undefined" errors
  const tierChoices = tiersData?.tiers
    ? tiersData.tiers.filter(t => t && t.active && t.name).map(tier => ({
        label: tier.name || '',
        value: String(tier.name || '').toLowerCase(),
      }))
    : [];

  const filters = tierChoices.length > 0
    ? [
        {
          key: 'tier',
          label: 'Tier',
          filter: (
            <ChoiceList
              title="Tier"
              titleHidden
              choices={tierChoices}
              selected={selectedTier}
              onChange={handleTierChange}
            />
          ),
          shortcut: true,
        },
      ]
    : [];

  const appliedFilters = selectedTier.length > 0
    ? [
        {
          key: 'tier',
          label: `Tier: ${selectedTier[0]}`,
          onRemove: () => setSelectedTier([]),
        },
      ]
    : [];

  return (
    <Page
      title="Members"
      subtitle={`${data?.total || 0} total members`}
      primaryAction={{
        content: 'Add Member',
        icon: PlusIcon,
        onAction: () => setAddMemberModalOpen(true),
      }}
      secondaryActions={[
        {
          content: 'Import CSV',
          icon: ImportIcon,
          onAction: () => setImportModalOpen(true),
        },
        {
          content: 'Email Members',
          icon: EmailIcon,
          onAction: () => setEmailModalOpen(true),
        },
        {
          content: 'Export',
          icon: ExportIcon,
          disabled: !data?.members?.length,
        },
      ]}
    >
      <Layout>
        {error && (
          <Layout.Section>
            <Banner tone="critical">
              <p>Failed to load members. Please try refreshing the page.</p>
            </Banner>
          </Layout.Section>
        )}

        <Layout.Section>
          <Card padding="0">
            <Box padding="400">
              <Filters
                queryValue={search}
                queryPlaceholder="Search by name or email"
                onQueryChange={handleSearchChange}
                onQueryClear={() => setSearch('')}
                filters={filters}
                appliedFilters={appliedFilters}
                onClearAll={handleClearFilters}
              />
            </Box>

            {isLoading ? (
              <Box padding="1600">
                <InlineStack align="center">
                  <Spinner size="large" />
                </InlineStack>
              </Box>
            ) : data?.members && data.members.length > 0 ? (
              <>
                {isMobile ? (
                  /* Mobile: Card-based layout */
                  <Box padding="300">
                    <BlockStack gap="300">
                      {data.members.filter(m => m && m.id != null).map((member, index) => (
                        <Box key={member.id}>
                          {index > 0 && <Divider />}
                          <Box paddingBlock="300">
                            <BlockStack gap="200">
                              <InlineStack align="space-between" blockAlign="start">
                                <BlockStack gap="050">
                                  <Button
                                    variant="plain"
                                    onClick={() => setDetailMember(member)}
                                  >
                                    {member.first_name} {member.last_name}
                                  </Button>
                                  <Text as="p" variant="bodySm" tone="subdued">
                                    {member.email}
                                  </Text>
                                </BlockStack>
                                <BlockStack gap="100" inlineAlign="end">
                                  <Badge tone="info">{member.tier?.name || 'None'}</Badge>
                                  <Badge tone={member.status === 'active' ? 'success' : undefined}>
                                    {member.status || 'unknown'}
                                  </Badge>
                                </BlockStack>
                              </InlineStack>
                              <InlineStack gap="400" wrap>
                                <BlockStack gap="050">
                                  <Text as="span" variant="bodySm" tone="subdued">Trade-Ins</Text>
                                  <Text as="span" fontWeight="medium">{member.trade_in_count}</Text>
                                </BlockStack>
                                <BlockStack gap="050">
                                  <Text as="span" variant="bodySm" tone="subdued">Credits</Text>
                                  <Text as="span" fontWeight="medium">{formatCurrency(member.total_credits_issued)}</Text>
                                </BlockStack>
                                <BlockStack gap="050">
                                  <Text as="span" variant="bodySm" tone="subdued">Last Active</Text>
                                  <Text as="span" fontWeight="medium">{formatDate(member.last_trade_in_at)}</Text>
                                </BlockStack>
                              </InlineStack>
                            </BlockStack>
                          </Box>
                        </Box>
                      ))}
                    </BlockStack>
                  </Box>
                ) : (
                  /* Desktop: DataTable layout */
                  <DataTable
                    columnContentTypes={[
                      'text',
                      'text',
                      'text',
                      'numeric',
                      'numeric',
                      'text',
                    ]}
                    headings={[
                      'Member',
                      'Tier',
                      'Status',
                      'Trade-Ins',
                      'Credits Issued',
                      'Last Activity',
                    ]}
                    rows={data.members.filter(m => m && m.id != null).map((member) => [
                      <BlockStack gap="100" key={member.id}>
                        <Button
                          variant="plain"
                          onClick={() => setDetailMember(member)}
                        >
                          {member.first_name || ''} {member.last_name || ''}
                        </Button>
                        <Text as="p" variant="bodySm" tone="subdued">
                          {member.email}
                        </Text>
                      </BlockStack>,
                      <Badge key={`tier-${member.id}`} tone="info">
                        {member.tier?.name || 'None'}
                      </Badge>,
                      <Badge
                        key={`status-${member.id}`}
                        tone={member.status === 'active' ? 'success' : undefined}
                      >
                        {member.status || 'unknown'}
                      </Badge>,
                      member.trade_in_count,
                      formatCurrency(member.total_credits_issued),
                      formatDate(member.last_trade_in_at),
                    ])}
                  />
                )}

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
                  heading="No members found"
                  image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                >
                  <p>
                    {search || selectedTier.length > 0
                      ? 'Try adjusting your search or filters.'
                      : 'Members will appear here when customers join your program.'}
                  </p>
                </EmptyState>
              </Box>
            )}
          </Card>
        </Layout.Section>
      </Layout>

      {/* Member Detail Modal */}
      <MemberDetailModal
        member={detailMember}
        shop={shop}
        onClose={() => setDetailMember(null)}
        formatCurrency={formatCurrency}
        formatDate={formatDate}
      />

      {/* Bulk Email Modal */}
      <BulkEmailModal
        open={emailModalOpen}
        onClose={() => setEmailModalOpen(false)}
        shop={shop}
        tiers={tiersData?.tiers}
      />

      {/* Add Member Modal */}
      <AddMemberModal
        open={addMemberModalOpen}
        onClose={() => setAddMemberModalOpen(false)}
        shop={shop}
      />

      {/* Import CSV Modal */}
      <ImportCSVModal
        open={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        shop={shop}
      />
    </Page>
  );
}

/**
 * Member Detail Modal with Tier Management
 */
interface MemberDetailModalProps {
  member: Member | null;
  shop: string | null;
  onClose: () => void;
  formatCurrency: (amount: number) => string;
  formatDate: (dateStr: string | null) => string;
}

interface TierOption {
  id: number;
  name: string;
}

interface TierHistoryItem {
  id: number;
  previous_tier: string | null;
  new_tier: string | null;
  change_type: string;
  source_type: string;
  reason: string | null;
  created_at: string;
  created_by: string | null;
}

interface CreditHistoryItem {
  id: number;
  amount: number;
  event_type: string;
  description: string | null;
  created_at: string;
  synced_to_shopify: boolean;
}

function MemberDetailModal({
  member,
  shop,
  onClose,
  formatCurrency,
  formatDate,
}: MemberDetailModalProps) {
  const [changeTierOpen, setChangeTierOpen] = useState(false);
  const [selectedTierId, setSelectedTierId] = useState<string>('');
  const [tierReason, setTierReason] = useState('');
  const [showHistory, setShowHistory] = useState(false);
  const [issueCreditOpen, setIssueCreditOpen] = useState(false);
  const [creditAmount, setCreditAmount] = useState('');
  const [creditDescription, setCreditDescription] = useState('');
  const [creditExpiration, setCreditExpiration] = useState('');
  const [cancelConfirmOpen, setCancelConfirmOpen] = useState(false);
  const [showCreditHistory, setShowCreditHistory] = useState(false);
  const queryClient = useQueryClient();

  // Fetch available tiers
  const { data: tiers } = useQuery<TierOption[]>({
    queryKey: ['tiers-list', shop],
    queryFn: async () => {
      const response = await authFetch(`${getApiUrl()}/membership/tiers`, shop);
      if (!response.ok) throw new Error('Failed to fetch tiers');
      const data = await response.json();
      return data.tiers || [];
    },
    enabled: !!shop && !!member,
  });

  // Fetch tier history
  const { data: history, isLoading: historyLoading } = useQuery<{ history: TierHistoryItem[] }>({
    queryKey: ['tier-history', shop, member?.id],
    queryFn: async () => {
      const response = await authFetch(
        `${getApiUrl()}/membership/tiers/history/${member?.id}`,
        shop
      );
      if (!response.ok) throw new Error('Failed to fetch history');
      return response.json();
    },
    enabled: !!shop && !!member && showHistory,
  });

  // Change tier mutation
  const changeTierMutation = useMutation({
    mutationFn: async () => {
      const response = await authFetch(`${getApiUrl()}/membership/tiers/assign`, shop, {
        method: 'POST',
        body: JSON.stringify({
          member_id: member?.id,
          tier_id: selectedTierId ? parseInt(selectedTierId) : null,
          reason: tierReason || 'Staff assigned',
        }),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to change tier');
      }
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['members'] });
      queryClient.invalidateQueries({ queryKey: ['tier-history', shop, member?.id] });
      setChangeTierOpen(false);
      setSelectedTierId('');
      setTierReason('');
    },
  });

  // Fetch credit history
  const { data: creditHistory, isLoading: creditHistoryLoading } = useQuery<{ bonuses: CreditHistoryItem[] }>({
    queryKey: ['credit-history', shop, member?.id],
    queryFn: async () => {
      const response = await authFetch(
        `${getApiUrl()}/bonuses?member_id=${member?.id}&per_page=10`,
        shop
      );
      if (!response.ok) throw new Error('Failed to fetch credit history');
      return response.json();
    },
    enabled: !!shop && !!member && showCreditHistory,
  });

  // Issue credit mutation
  const issueCreditMutation = useMutation({
    mutationFn: async () => {
      const response = await authFetch(`${getApiUrl()}/membership/store-credit/add`, shop, {
        method: 'POST',
        body: JSON.stringify({
          member_id: member?.id,
          amount: parseFloat(creditAmount),
          description: creditDescription || 'Manual credit adjustment',
          expiration_days: creditExpiration ? parseInt(creditExpiration) : null,
        }),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to issue credit');
      }
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['members'] });
      queryClient.invalidateQueries({ queryKey: ['credit-history', shop, member?.id] });
      setIssueCreditOpen(false);
      setCreditAmount('');
      setCreditDescription('');
      setCreditExpiration('');
    },
  });

  // Cancel membership mutation
  const cancelMembershipMutation = useMutation({
    mutationFn: async () => {
      const response = await authFetch(`${getApiUrl()}/members/${member?.id}`, shop, {
        method: 'PUT',
        body: JSON.stringify({
          status: 'cancelled',
        }),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to cancel membership');
      }
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['members'] });
      setCancelConfirmOpen(false);
      onClose();
    },
  });

  if (!member) return null;

  const tierOptions = [
    { label: 'No Tier', value: '' },
    ...(tiers?.filter(t => t && t.name).map((t) => ({ label: t.name || '', value: String(t.id) })) || []),
  ];

  return (
    <>
      <Modal
        open={member !== null}
        onClose={onClose}
        title={`${member.first_name} ${member.last_name}`}
        primaryAction={{
          content: 'Issue Credit',
          onAction: () => setIssueCreditOpen(true),
        }}
        secondaryActions={[
          {
            content: 'Change Tier',
            onAction: () => setChangeTierOpen(true),
          },
          {
            content: 'Cancel Membership',
            onAction: () => setCancelConfirmOpen(true),
            destructive: true,
            disabled: member.status === 'cancelled',
          },
        ]}
      >
        <Modal.Section>
          <BlockStack gap="400">
            <InlineStack gap="400">
              <BlockStack gap="100">
                <Text as="span" variant="bodySm" tone="subdued">
                  Email
                </Text>
                <Text as="span">{member.email}</Text>
              </BlockStack>
              <BlockStack gap="100">
                <Text as="span" variant="bodySm" tone="subdued">
                  Tier
                </Text>
                <Badge tone="info">{member.tier?.name || 'None'}</Badge>
              </BlockStack>
            </InlineStack>

            <InlineStack gap="400">
              <BlockStack gap="100">
                <Text as="span" variant="bodySm" tone="subdued">
                  Total Trade-Ins
                </Text>
                <Text as="span">{member.trade_in_count}</Text>
              </BlockStack>
              <BlockStack gap="100">
                <Text as="span" variant="bodySm" tone="subdued">
                  Trade-In Value
                </Text>
                <Text as="span">
                  {formatCurrency(member.total_trade_in_value)}
                </Text>
              </BlockStack>
              <BlockStack gap="100">
                <Text as="span" variant="bodySm" tone="subdued">
                  Credits Issued
                </Text>
                <Text as="span">
                  {formatCurrency(member.total_credits_issued)}
                </Text>
              </BlockStack>
            </InlineStack>

            <InlineStack gap="400">
              <BlockStack gap="100">
                <Text as="span" variant="bodySm" tone="subdued">
                  Member Since
                </Text>
                <Text as="span">{formatDate(member.created_at)}</Text>
              </BlockStack>
              <BlockStack gap="100">
                <Text as="span" variant="bodySm" tone="subdued">
                  Last Activity
                </Text>
                <Text as="span">
                  {formatDate(member.last_trade_in_at)}
                </Text>
              </BlockStack>
            </InlineStack>
          </BlockStack>
        </Modal.Section>

        <Modal.Section>
          <BlockStack gap="300">
            <InlineStack align="space-between">
              <Text as="h3" variant="headingSm">Tier History</Text>
              <Button
                variant="plain"
                onClick={() => setShowHistory(!showHistory)}
              >
                {showHistory ? 'Hide' : 'Show'} History
              </Button>
            </InlineStack>

            {showHistory && (
              historyLoading ? (
                <InlineStack align="center">
                  <Spinner size="small" />
                </InlineStack>
              ) : history?.history && history.history.length > 0 ? (
                <BlockStack gap="200">
                  {history.history.slice(0, 5).filter(item => item && item.id != null).map((item) => (
                    <Box
                      key={item.id}
                      padding="200"
                      background="bg-surface-secondary"
                      borderRadius="100"
                    >
                      <InlineStack align="space-between">
                        <BlockStack gap="050">
                          <Text as="span" variant="bodySm">
                            {String(item.previous_tier || 'None')} → {String(item.new_tier || 'None')}
                          </Text>
                          <Text as="span" variant="bodySm" tone="subdued">
                            {String(item.change_type || 'change')} • {String(item.source_type || 'system')}
                          </Text>
                        </BlockStack>
                        <Text as="span" variant="bodySm" tone="subdued">
                          {item.created_at ? formatDate(item.created_at) : '-'}
                        </Text>
                      </InlineStack>
                    </Box>
                  ))}
                </BlockStack>
              ) : (
                <Text as="p" tone="subdued">No tier changes recorded</Text>
              )
            )}
          </BlockStack>
        </Modal.Section>

        <Modal.Section>
          <BlockStack gap="300">
            <InlineStack align="space-between">
              <Text as="h3" variant="headingSm">Credit History</Text>
              <Button
                variant="plain"
                onClick={() => setShowCreditHistory(!showCreditHistory)}
              >
                {showCreditHistory ? 'Hide' : 'Show'} History
              </Button>
            </InlineStack>

            {showCreditHistory && (
              creditHistoryLoading ? (
                <InlineStack align="center">
                  <Spinner size="small" />
                </InlineStack>
              ) : creditHistory?.bonuses && creditHistory.bonuses.length > 0 ? (
                <BlockStack gap="200">
                  {creditHistory.bonuses.filter(item => item && item.id != null).map((item) => (
                    <Box
                      key={item.id}
                      padding="200"
                      background="bg-surface-secondary"
                      borderRadius="100"
                    >
                      <InlineStack align="space-between">
                        <BlockStack gap="050">
                          <InlineStack gap="200">
                            <Text as="span" variant="bodySm" fontWeight="semibold">
                              {item.amount > 0 ? '+' : ''}{formatCurrency(item.amount)}
                            </Text>
                            {item.synced_to_shopify && (
                              <Badge tone="success" size="small">Synced</Badge>
                            )}
                          </InlineStack>
                          <Text as="span" variant="bodySm" tone="subdued">
                            {String(item.description || item.event_type || 'credit')}
                          </Text>
                        </BlockStack>
                        <Text as="span" variant="bodySm" tone="subdued">
                          {formatDate(item.created_at)}
                        </Text>
                      </InlineStack>
                    </Box>
                  ))}
                </BlockStack>
              ) : (
                <Text as="p" tone="subdued">No credit transactions recorded</Text>
              )
            )}
          </BlockStack>
        </Modal.Section>
      </Modal>

      {/* Change Tier Modal */}
      <Modal
        open={changeTierOpen}
        onClose={() => setChangeTierOpen(false)}
        title="Change Member Tier"
        primaryAction={{
          content: 'Save',
          onAction: () => changeTierMutation.mutate(),
          loading: changeTierMutation.isPending,
        }}
        secondaryActions={[
          { content: 'Cancel', onAction: () => setChangeTierOpen(false) },
        ]}
      >
        <Modal.Section>
          {changeTierMutation.isError && (
            <Box paddingBlockEnd="400">
              <Banner tone="critical">
                <p>{changeTierMutation.error?.message || 'Failed to change tier'}</p>
              </Banner>
            </Box>
          )}
          <FormLayout>
            <Select
              label="New Tier"
              options={tierOptions}
              value={selectedTierId}
              onChange={setSelectedTierId}
            />
            <TextField
              label="Reason (optional)"
              value={tierReason}
              onChange={setTierReason}
              placeholder="e.g., VIP upgrade, loyalty reward"
              autoComplete="off"
            />
          </FormLayout>
        </Modal.Section>
      </Modal>

      {/* Issue Credit Modal */}
      <Modal
        open={issueCreditOpen}
        onClose={() => setIssueCreditOpen(false)}
        title="Issue Store Credit"
        primaryAction={{
          content: 'Issue Credit',
          onAction: () => issueCreditMutation.mutate(),
          loading: issueCreditMutation.isPending,
          disabled: !creditAmount || parseFloat(creditAmount) <= 0,
        }}
        secondaryActions={[
          { content: 'Cancel', onAction: () => setIssueCreditOpen(false) },
        ]}
      >
        <Modal.Section>
          {issueCreditMutation.isError && (
            <Box paddingBlockEnd="400">
              <Banner tone="critical">
                <p>{issueCreditMutation.error?.message || 'Failed to issue credit'}</p>
              </Banner>
            </Box>
          )}
          {issueCreditMutation.isSuccess && (
            <Box paddingBlockEnd="400">
              <Banner tone="success">
                <p>Credit issued successfully!</p>
              </Banner>
            </Box>
          )}
          <FormLayout>
            <TextField
              label="Credit Amount"
              type="number"
              value={creditAmount}
              onChange={setCreditAmount}
              prefix="$"
              min={0.01}
              step={0.01}
              autoComplete="off"
              helpText="Amount to add to member's store credit balance"
            />
            <TextField
              label="Description (optional)"
              value={creditDescription}
              onChange={setCreditDescription}
              placeholder="e.g., Loyalty bonus, Price adjustment"
              autoComplete="off"
              helpText="Reason for the credit (visible in history)"
            />
            <Select
              label="Credit Expiration"
              options={CREDIT_EXPIRATION_OPTIONS}
              value={creditExpiration}
              onChange={setCreditExpiration}
              helpText="When this credit should expire"
            />
          </FormLayout>
        </Modal.Section>
      </Modal>

      {/* Cancel Membership Confirmation Modal */}
      <Modal
        open={cancelConfirmOpen}
        onClose={() => setCancelConfirmOpen(false)}
        title="Cancel Membership"
        primaryAction={{
          content: 'Cancel Membership',
          onAction: () => cancelMembershipMutation.mutate(),
          loading: cancelMembershipMutation.isPending,
          destructive: true,
        }}
        secondaryActions={[
          { content: 'Keep Active', onAction: () => setCancelConfirmOpen(false) },
        ]}
      >
        <Modal.Section>
          {cancelMembershipMutation.isError && (
            <Box paddingBlockEnd="400">
              <Banner tone="critical">
                <p>{cancelMembershipMutation.error?.message || 'Failed to cancel membership'}</p>
              </Banner>
            </Box>
          )}
          <Banner tone="warning">
            <BlockStack gap="200">
              <Text as="p" fontWeight="semibold">
                Are you sure you want to cancel this membership?
              </Text>
              <Text as="p">
                {member.first_name} {member.last_name} will no longer receive member benefits.
                Their existing store credit will remain available.
              </Text>
            </BlockStack>
          </Banner>
        </Modal.Section>
      </Modal>
    </>
  );
}

/**
 * Bulk Email Modal for Tier-Based Communication
 */
interface BulkEmailModalProps {
  open: boolean;
  onClose: () => void;
  shop: string | null;
  tiers?: MembershipTier[];
}

interface EmailTemplate {
  id: string;
  name: string;
  subject: string;
  message: string;
  category: string;
}

interface PreviewResponse {
  tier_names: string[];
  member_counts: Record<string, number>;
  total_recipients: number;
}

function BulkEmailModal({ open, onClose, shop, tiers }: BulkEmailModalProps) {
  const [selectedTiers, setSelectedTiers] = useState<string[]>([]);
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [sendSuccess, setSendSuccess] = useState(false);
  const [sendResult, setSendResult] = useState<{ sent: number; failed: number } | null>(null);

  // Fetch email templates
  const { data: templates } = useQuery<{ templates: EmailTemplate[] }>({
    queryKey: ['email-templates', shop],
    queryFn: async () => {
      const response = await authFetch(`${getApiUrl()}/members/email/templates`, shop);
      if (!response.ok) throw new Error('Failed to fetch templates');
      return response.json();
    },
    enabled: !!shop && open,
  });

  // Preview mutation (get recipient counts)
  const previewMutation = useMutation({
    mutationFn: async () => {
      const response = await authFetch(`${getApiUrl()}/members/email/preview`, shop, {
        method: 'POST',
        body: JSON.stringify({ tier_names: selectedTiers }),
      });
      if (!response.ok) throw new Error('Failed to preview');
      return response.json() as Promise<PreviewResponse>;
    },
  });

  // Send email mutation
  const sendMutation = useMutation({
    mutationFn: async () => {
      const response = await authFetch(`${getApiUrl()}/members/email/send`, shop, {
        method: 'POST',
        body: JSON.stringify({
          tier_names: selectedTiers,
          subject,
          message,
        }),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to send emails');
      }
      return response.json();
    },
    onSuccess: (data) => {
      setSendSuccess(true);
      setSendResult({ sent: data.sent, failed: data.failed });
    },
  });

  // Preview when tiers change
  const handleTierChange = useCallback((value: string[]) => {
    setSelectedTiers(value);
    if (value.length > 0) {
      previewMutation.mutate();
    }
  }, []);

  // Apply template
  const applyTemplate = useCallback((template: EmailTemplate) => {
    setSubject(template.subject);
    setMessage(template.message);
  }, []);

  // Reset and close
  const handleClose = useCallback(() => {
    setSelectedTiers([]);
    setSubject('');
    setMessage('');
    setSendSuccess(false);
    setSendResult(null);
    onClose();
  }, [onClose]);

  const canSend = selectedTiers.length > 0 && subject.trim() && message.trim();
  const recipientCount = previewMutation.data?.total_recipients || 0;

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Email Members by Tier"
      primaryAction={
        sendSuccess
          ? { content: 'Done', onAction: handleClose }
          : {
              content: `Send to ${recipientCount} ${recipientCount === 1 ? 'Member' : 'Members'}`,
              onAction: () => sendMutation.mutate(),
              disabled: !canSend || recipientCount === 0,
              loading: sendMutation.isPending,
            }
      }
      secondaryActions={
        sendSuccess ? [] : [{ content: 'Cancel', onAction: handleClose }]
      }
      size="large"
    >
      {sendSuccess ? (
        <Modal.Section>
          <Banner tone="success">
            <BlockStack gap="200">
              <Text as="p" variant="headingMd">Email Sent Successfully!</Text>
              <Text as="p">
                Sent {sendResult?.sent} emails
                {sendResult?.failed ? ` (${sendResult.failed} failed)` : ''}.
              </Text>
            </BlockStack>
          </Banner>
        </Modal.Section>
      ) : (
        <>
          <Modal.Section>
            <BlockStack gap="400">
              {sendMutation.isError && (
                <Banner tone="critical">
                  <p>{sendMutation.error?.message || 'Failed to send emails'}</p>
                </Banner>
              )}

              <ChoiceList
                title="Select Tiers to Email"
                choices={tiers
                  ? tiers.filter(t => t && t.active && t.name).map(tier => ({
                      label: tier.name || '',
                      value: String(tier.name || '').toUpperCase(),
                    }))
                  : []
                }
                selected={selectedTiers}
                onChange={handleTierChange}
                allowMultiple
              />

              {previewMutation.data && (
                <Banner>
                  <Text as="p">
                    <strong>{recipientCount}</strong> active members will receive this email:
                    {Object.entries(previewMutation.data.member_counts).map(([tier, count]) => (
                      <span key={tier}> {tier}: {count}</span>
                    ))}
                  </Text>
                </Banner>
              )}
            </BlockStack>
          </Modal.Section>

          <Modal.Section>
            <BlockStack gap="400">
              <Text as="h3" variant="headingSm">Quick Templates</Text>
              <InlineStack gap="200" wrap>
                {templates?.templates?.filter(t => t && t.id).map((t) => (
                  <Button
                    key={t.id}
                    size="slim"
                    onClick={() => applyTemplate(t)}
                  >
                    {t.name || 'Template'}
                  </Button>
                ))}
              </InlineStack>
            </BlockStack>
          </Modal.Section>

          <Modal.Section>
            <FormLayout>
              <TextField
                label="Subject"
                value={subject}
                onChange={setSubject}
                autoComplete="off"
                placeholder="e.g., Exclusive Member Offer!"
                requiredIndicator
              />

              <TextField
                label="Message"
                value={message}
                onChange={setMessage}
                multiline={8}
                autoComplete="off"
                placeholder="Write your message here..."
                helpText="Use {member_name}, {member_number}, and {tier_name} for personalization"
                requiredIndicator
              />
            </FormLayout>
          </Modal.Section>
        </>
      )}
    </Modal>
  );
}

/**
 * Add Member Modal - Search Shopify customers and enroll as members
 */
interface AddMemberModalProps {
  open: boolean;
  onClose: () => void;
  shop: string | null;
}

interface ShopifyCustomer {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  orders_count: number;
  total_spent: string;
}

function AddMemberModal({ open, onClose, shop }: AddMemberModalProps) {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCustomer, setSelectedCustomer] = useState<ShopifyCustomer | null>(null);
  const [selectedTierId, setSelectedTierId] = useState<string>('');
  const [searchResults, setSearchResults] = useState<ShopifyCustomer[]>([]);
  const [searching, setSearching] = useState(false);
  const [success, setSuccess] = useState(false);

  // Fetch available tiers
  const { data: tiers } = useQuery<{ id: number; name: string }[]>({
    queryKey: ['tiers-list', shop],
    queryFn: async () => {
      const response = await authFetch(`${getApiUrl()}/membership/tiers`, shop);
      if (!response.ok) throw new Error('Failed to fetch tiers');
      const data = await response.json();
      return data.tiers || [];
    },
    enabled: !!shop && open,
  });

  // Search Shopify customers
  const handleSearch = useCallback(async () => {
    if (!searchQuery || searchQuery.length < 2) return;

    setSearching(true);
    try {
      const response = await authFetch(
        `${getApiUrl()}/shopify/customers/search?q=${encodeURIComponent(searchQuery)}`,
        shop
      );
      if (response.ok) {
        const data = await response.json();
        setSearchResults(data.customers || []);
      }
    } catch (err) {
      console.error('Search failed:', err);
    } finally {
      setSearching(false);
    }
  }, [searchQuery, shop]);

  // Enroll customer as member
  const enrollMutation = useMutation({
    mutationFn: async () => {
      if (!selectedCustomer) throw new Error('No customer selected');

      const response = await authFetch(`${getApiUrl()}/members`, shop, {
        method: 'POST',
        body: JSON.stringify({
          shopify_customer_id: selectedCustomer.id,
          email: selectedCustomer.email,
          first_name: selectedCustomer.first_name,
          last_name: selectedCustomer.last_name,
          phone: selectedCustomer.phone,
          tier_id: selectedTierId ? parseInt(selectedTierId) : null,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to enroll member');
      }
      return response.json();
    },
    onSuccess: () => {
      setSuccess(true);
      queryClient.invalidateQueries({ queryKey: ['members'] });
    },
  });

  const handleClose = useCallback(() => {
    setSearchQuery('');
    setSelectedCustomer(null);
    setSelectedTierId('');
    setSearchResults([]);
    setSuccess(false);
    onClose();
  }, [onClose]);

  const tierOptions = [
    { label: 'No Tier (Start at base)', value: '' },
    ...(tiers?.filter(t => t && t.name).map((t) => ({ label: t.name || '', value: String(t.id) })) || []),
  ];

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Add Member"
      primaryAction={
        success
          ? { content: 'Done', onAction: handleClose }
          : selectedCustomer
          ? {
              content: 'Enroll Member',
              onAction: () => enrollMutation.mutate(),
              loading: enrollMutation.isPending,
            }
          : undefined
      }
      secondaryActions={
        success
          ? []
          : selectedCustomer
          ? [
              {
                content: 'Back',
                onAction: () => setSelectedCustomer(null),
              },
            ]
          : [{ content: 'Cancel', onAction: handleClose }]
      }
    >
      {success ? (
        <Modal.Section>
          <Banner tone="success">
            <BlockStack gap="200">
              <Text as="p" variant="headingMd">Member Enrolled!</Text>
              <Text as="p">
                {selectedCustomer?.first_name} {selectedCustomer?.last_name} has been enrolled
                in your loyalty program.
              </Text>
            </BlockStack>
          </Banner>
        </Modal.Section>
      ) : selectedCustomer ? (
        <Modal.Section>
          <BlockStack gap="400">
            {enrollMutation.isError && (
              <Banner tone="critical">
                <p>{enrollMutation.error?.message || 'Failed to enroll member'}</p>
              </Banner>
            )}

            <Card background="bg-surface-secondary">
              <BlockStack gap="200">
                <Text as="h3" variant="headingSm">
                  {selectedCustomer.first_name} {selectedCustomer.last_name}
                </Text>
                <Text as="p" tone="subdued">
                  {selectedCustomer.email}
                </Text>
                <InlineStack gap="400">
                  <Text as="span" variant="bodySm">
                    {selectedCustomer.orders_count} orders
                  </Text>
                  <Text as="span" variant="bodySm">
                    ${selectedCustomer.total_spent} spent
                  </Text>
                </InlineStack>
              </BlockStack>
            </Card>

            <Select
              label="Starting Tier"
              options={tierOptions}
              value={selectedTierId}
              onChange={setSelectedTierId}
              helpText="Select an initial tier or leave at base level"
            />
          </BlockStack>
        </Modal.Section>
      ) : (
        <Modal.Section>
          <BlockStack gap="400">
            <InlineStack gap="200">
              <div style={{ flex: 1 }}>
                <TextField
                  label="Search Shopify Customers"
                  value={searchQuery}
                  onChange={setSearchQuery}
                  placeholder="Search by name or email..."
                  autoComplete="off"
                  onBlur={() => {}}
                  connectedRight={
                    <Button
                      onClick={handleSearch}
                      loading={searching}
                      icon={SearchIcon}
                    >
                      Search
                    </Button>
                  }
                />
              </div>
            </InlineStack>

            {searchResults.length > 0 ? (
              <BlockStack gap="200">
                <Text as="h3" variant="headingSm">
                  Search Results ({searchResults.length})
                </Text>
                {searchResults.map((customer) => (
                  <div
                    key={customer.id}
                    onClick={() => setSelectedCustomer(customer)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && setSelectedCustomer(customer)}
                    style={{ cursor: 'pointer' }}
                  >
                    <Box
                      padding="300"
                      background="bg-surface-secondary"
                      borderRadius="200"
                    >
                    <InlineStack align="space-between" blockAlign="center">
                      <BlockStack gap="100">
                        <Text as="span" fontWeight="semibold">
                          {customer.first_name} {customer.last_name}
                        </Text>
                        <Text as="span" variant="bodySm" tone="subdued">
                          {customer.email}
                        </Text>
                      </BlockStack>
                      <BlockStack gap="050" inlineAlign="end">
                        <Text as="span" variant="bodySm">
                          {customer.orders_count} orders
                        </Text>
                        <Text as="span" variant="bodySm" tone="subdued">
                          ${customer.total_spent}
                        </Text>
                      </BlockStack>
                    </InlineStack>
                    </Box>
                  </div>
                ))}
              </BlockStack>
            ) : searchQuery.length >= 2 && !searching ? (
              <Text as="p" tone="subdued" alignment="center">
                No customers found. Try a different search.
              </Text>
            ) : (
              <Text as="p" tone="subdued" alignment="center">
                Search for a Shopify customer to enroll as a member.
              </Text>
            )}
          </BlockStack>
        </Modal.Section>
      )}
    </Modal>
  );
}

/**
 * Import CSV Modal - Bulk import members from CSV file
 */
interface ImportCSVModalProps {
  open: boolean;
  onClose: () => void;
  shop: string | null;
}

interface ImportPreview {
  total_rows: number;
  valid_count: number;
  invalid_count: number;
  duplicate_count: number;
  valid_rows: Array<{
    row: number;
    email: string;
    first_name: string;
    last_name: string;
    tier_name: string;
  }>;
  invalid_rows: Array<{
    row: number;
    email: string;
    errors: string[];
  }>;
  duplicate_rows: Array<{
    row: number;
    email: string;
    reason: string;
  }>;
  available_tiers: string[];
}

function ImportCSVModal({ open, onClose, shop }: ImportCSVModalProps) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [importing, setImporting] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState<{ imported: number; skipped: number } | null>(null);

  const handleDropZoneDrop = useCallback(
    (_dropFiles: File[], acceptedFiles: File[], _rejectedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        setFile(acceptedFiles[0]);
        setPreview(null);
        setError('');
        setSuccess(null);
      }
    },
    []
  );

  const handlePreview = useCallback(async () => {
    if (!file || !shop) return;

    setPreviewLoading(true);
    setError('');

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${getApiUrl()}/members/import/preview`, {
        method: 'POST',
        headers: {
          'X-Shop-Domain': shop,
        },
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || 'Failed to preview CSV');
      }

      const data = await response.json();
      setPreview(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to preview CSV');
    } finally {
      setPreviewLoading(false);
    }
  }, [file, shop]);

  const handleImport = useCallback(async () => {
    if (!file || !shop) return;

    setImporting(true);
    setError('');

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('skip_duplicates', 'true');

      const response = await fetch(`${getApiUrl()}/members/import/import`, {
        method: 'POST',
        headers: {
          'X-Shop-Domain': shop,
        },
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || 'Failed to import members');
      }

      const data = await response.json();
      setSuccess({ imported: data.imported, skipped: data.skipped });
      queryClient.invalidateQueries({ queryKey: ['members'] });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to import members');
    } finally {
      setImporting(false);
    }
  }, [file, shop, queryClient]);

  const handleClose = useCallback(() => {
    setFile(null);
    setPreview(null);
    setError('');
    setSuccess(null);
    onClose();
  }, [onClose]);

  const validImageTypes = ['text/csv', 'application/vnd.ms-excel'];

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Import Members from CSV"
      primaryAction={
        success
          ? { content: 'Done', onAction: handleClose }
          : preview
          ? {
              content: `Import ${preview.valid_count} Members`,
              onAction: handleImport,
              loading: importing,
              disabled: preview.valid_count === 0,
            }
          : file
          ? {
              content: 'Preview Import',
              onAction: handlePreview,
              loading: previewLoading,
            }
          : undefined
      }
      secondaryActions={
        success
          ? []
          : preview
          ? [
              {
                content: 'Back',
                onAction: () => {
                  setPreview(null);
                  setFile(null);
                },
              },
            ]
          : [{ content: 'Cancel', onAction: handleClose }]
      }
      size="large"
    >
      {success ? (
        <Modal.Section>
          <Banner tone="success">
            <BlockStack gap="200">
              <Text as="p" variant="headingMd">Import Complete!</Text>
              <Text as="p">
                Successfully imported {success.imported} members
                {success.skipped > 0 && ` (${success.skipped} duplicates skipped)`}.
              </Text>
            </BlockStack>
          </Banner>
        </Modal.Section>
      ) : preview ? (
        <>
          <Modal.Section>
            {error && (
              <Box paddingBlockEnd="400">
                <Banner tone="critical" onDismiss={() => setError('')}>
                  <p>{error}</p>
                </Banner>
              </Box>
            )}

            <BlockStack gap="400">
              <InlineStack gap="400">
                <Card>
                  <BlockStack gap="100">
                    <Text as="span" variant="headingLg" tone="success">
                      {preview.valid_count}
                    </Text>
                    <Text as="span" variant="bodySm">Ready to import</Text>
                  </BlockStack>
                </Card>
                <Card>
                  <BlockStack gap="100">
                    <Text as="span" variant="headingLg" tone="critical">
                      {preview.invalid_count}
                    </Text>
                    <Text as="span" variant="bodySm">Invalid rows</Text>
                  </BlockStack>
                </Card>
                <Card>
                  <BlockStack gap="100">
                    <Text as="span" variant="headingLg" tone="caution">
                      {preview.duplicate_count}
                    </Text>
                    <Text as="span" variant="bodySm">Duplicates (skipped)</Text>
                  </BlockStack>
                </Card>
              </InlineStack>

              {preview.valid_rows.length > 0 && (
                <BlockStack gap="200">
                  <Text as="h3" variant="headingSm">Preview (first 10 rows)</Text>
                  <DataTable
                    columnContentTypes={['numeric', 'text', 'text', 'text', 'text']}
                    headings={['Row', 'Email', 'First Name', 'Last Name', 'Tier']}
                    rows={preview.valid_rows.map((row) => [
                      row.row,
                      row.email,
                      row.first_name,
                      row.last_name,
                      row.tier_name || '-',
                    ])}
                  />
                </BlockStack>
              )}

              {preview.invalid_rows.length > 0 && (
                <BlockStack gap="200">
                  <Text as="h3" variant="headingSm" tone="critical">
                    Invalid Rows
                  </Text>
                  {preview.invalid_rows.map((row) => (
                    <Box
                      key={row.row}
                      padding="200"
                      background="bg-surface-critical"
                      borderRadius="100"
                    >
                      <InlineStack align="space-between">
                        <Text as="span" variant="bodySm">
                          Row {row.row}: {row.email || '(no email)'}
                        </Text>
                        <Text as="span" variant="bodySm" tone="critical">
                          {row.errors.join(', ')}
                        </Text>
                      </InlineStack>
                    </Box>
                  ))}
                </BlockStack>
              )}
            </BlockStack>
          </Modal.Section>
        </>
      ) : (
        <Modal.Section>
          <BlockStack gap="400">
            {error && (
              <Banner tone="critical" onDismiss={() => setError('')}>
                <p>{error}</p>
              </Banner>
            )}

            <DropZone
              accept=".csv"
              type="file"
              onDrop={handleDropZoneDrop}
              variableHeight
            >
              {file ? (
                <Box padding="400">
                  <InlineStack gap="300" blockAlign="center">
                    <Thumbnail
                      source="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                      alt="CSV file"
                      size="small"
                    />
                    <BlockStack gap="050">
                      <Text as="span" variant="bodyMd" fontWeight="semibold">
                        {file.name}
                      </Text>
                      <Text as="span" variant="bodySm" tone="subdued">
                        {(file.size / 1024).toFixed(1)} KB
                      </Text>
                    </BlockStack>
                  </InlineStack>
                </Box>
              ) : (
                <DropZone.FileUpload actionHint="or drop a CSV file to upload" />
              )}
            </DropZone>

            <Card background="bg-surface-secondary">
              <BlockStack gap="300">
                <Text as="h3" variant="headingSm">CSV Format Requirements</Text>
                <List type="bullet">
                  <List.Item>First row must be column headers</List.Item>
                  <List.Item>Required columns: email, first_name</List.Item>
                  <List.Item>Optional: last_name, phone, tier_name</List.Item>
                  <List.Item>Tier names must match existing tiers exactly</List.Item>
                </List>
                <Text as="p" variant="bodySm" tone="subdued">
                  Example: email,first_name,last_name,tier_name
                </Text>
              </BlockStack>
            </Card>
          </BlockStack>
        </Modal.Section>
      )}
    </Modal>
  );
}
