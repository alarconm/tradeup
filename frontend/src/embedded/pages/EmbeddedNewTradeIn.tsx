/**
 * TradeUp New Trade-In - Shopify Embedded Version
 *
 * Create new trade-in batches with member search, category selection,
 * and item entry. Uses Shopify Polaris for consistent UX.
 */
import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
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
  FormLayout,
  Banner,
  Autocomplete,
  Icon,
  Divider,
  ChoiceList,
  Modal,
} from '@shopify/polaris';
import {
  SearchIcon,
  PlusIcon,
  DeleteIcon,
  CheckIcon,
  AlertCircleIcon,
} from '@shopify/polaris-icons';
import { useQueryClient } from '@tanstack/react-query';
import { useMutation, useQuery } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface NewTradeInProps {
  shop: string | null;
}

interface Member {
  id: number;
  member_number: string;
  name: string | null;
  email: string;
  tier: {
    id: number;
    name: string;
  } | null;
}

interface TradeInCategory {
  id: string;
  name: string;
  icon: string;
}

interface TradeInItem {
  id: string;
  product_title: string;
  trade_value: string;
  market_value: string;
  notes: string;
}

interface ShopifyCustomer {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  displayName?: string;
  phone: string | null;
  ordersCount: number;
  totalSpent: number | string;
}

// Default categories if none are configured (TCGs and collectibles)
const DEFAULT_CATEGORIES: TradeInCategory[] = [
  { id: 'pokemon', name: 'Pokemon', icon: '⚡' },
  { id: 'magic', name: 'Magic: The Gathering', icon: '🔮' },
  { id: 'yugioh', name: 'Yu-Gi-Oh!', icon: '🃏' },
  { id: 'sports', name: 'Sports Cards', icon: '🏈' },
  { id: 'one_piece', name: 'One Piece', icon: '🏴‍☠️' },
  { id: 'disney_lorcana', name: 'Disney Lorcana', icon: '✨' },
  { id: 'tcg_other', name: 'Other TCG', icon: '🎴' },
  { id: 'other', name: 'Other', icon: '📦' },
];

async function searchMembers(shop: string | null, query: string): Promise<{ members: Member[] }> {
  const params = new URLSearchParams({ search: query, limit: '10' });
  const response = await authFetch(`${getApiUrl()}/members?${params}`, shop);
  if (!response.ok) throw new Error('Failed to search members');
  return response.json();
}

async function fetchCategories(shop: string | null): Promise<{ categories: TradeInCategory[] }> {
  const response = await authFetch(`${getApiUrl()}/trade-ins/categories`, shop);
  if (!response.ok) throw new Error('Failed to fetch categories');
  return response.json();
}

async function createTradeInBatch(
  shop: string | null,
  data: { member_id: number; category: string; notes?: string }
): Promise<{ id: number; batch_reference: string }> {
  const response = await authFetch(`${getApiUrl()}/trade-ins`, shop, {
    method: 'POST',
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to create trade-in batch');
  return response.json();
}

async function addTradeInItems(
  shop: string | null,
  batchId: number,
  items: Array<{
    product_title?: string;
    trade_value: number;
    market_value?: number;
    notes?: string;
  }>
): Promise<void> {
  const response = await authFetch(`${getApiUrl()}/trade-ins/${batchId}/items`, shop, {
    method: 'POST',
    body: JSON.stringify({ items }),
  });
  if (!response.ok) throw new Error('Failed to add items');
}

interface CompleteBatchResult {
  success: boolean;
  batch_reference: string;
  trade_value: number;
  bonus?: {
    eligible: boolean;
    bonus_amount: number;
    bonus_percent?: number;
    tier_name?: string;
  };
}

async function completeBatch(shop: string | null, batchId: number): Promise<CompleteBatchResult> {
  const response = await authFetch(`${getApiUrl()}/trade-ins/${batchId}/complete`, shop, {
    method: 'POST',
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Failed to complete batch' }));
    throw new Error(error.error || 'Failed to complete batch');
  }
  return response.json();
}

export function EmbeddedNewTradeIn({ shop }: NewTradeInProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Member search state
  const [memberSearch, setMemberSearch] = useState('');
  const [selectedMember, setSelectedMember] = useState<Member | null>(null);
  const [memberOptions, setMemberOptions] = useState<Array<{ value: string; label: string }>>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [, setSearchPerformed] = useState(false);

  // Inline add member modal state
  const [addMemberModalOpen, setAddMemberModalOpen] = useState(false);
  const [customerSearchQuery, setCustomerSearchQuery] = useState('');
  const [customerSearchResults, setCustomerSearchResults] = useState<ShopifyCustomer[]>([]);
  const [customerSearching, setCustomerSearching] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState<ShopifyCustomer | null>(null);
  const [enrolling, setEnrolling] = useState(false);
  const [enrollError, setEnrollError] = useState('');

  // Category state
  const [selectedCategory, setSelectedCategory] = useState('other');

  // Items state
  const [items, setItems] = useState<TradeInItem[]>([
    { id: '1', product_title: '', trade_value: '', market_value: '', notes: '' },
  ]);

  // Notes
  const [batchNotes, setBatchNotes] = useState('');

  // Form state
  const [error, setError] = useState('');

  // Fetch categories
  const { data: categoriesData } = useQuery({
    queryKey: ['categories', shop],
    queryFn: () => fetchCategories(shop),
    enabled: !!shop,
  });

  const categories = categoriesData?.categories?.length
    ? categoriesData.categories
    : DEFAULT_CATEGORIES;

  // Member search with debounce
  useEffect(() => {
    if (!memberSearch || memberSearch.length < 2 || selectedMember) {
      setMemberOptions([]);
      if (!memberSearch) setSearchPerformed(false);
      return;
    }

    const timeoutId = setTimeout(async () => {
      setSearchLoading(true);
      try {
        const result = await searchMembers(shop, memberSearch);
        setMemberOptions(
          result.members.filter(m => m && m.id != null).map((m) => ({
            value: String(m.id),
            label: `${m.name || m.email || 'Unknown'} (${m.member_number || 'N/A'})`,
            member: m,
          }))
        );
        setSearchPerformed(true);
      } catch (err) {
        console.error('Search failed:', err);
        setMemberOptions([]);
        setSearchPerformed(true);
      } finally {
        setSearchLoading(false);
      }
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [memberSearch, shop, selectedMember]);

  // Search Shopify customers for inline add member
  const searchShopifyCustomers = useCallback(async () => {
    if (!customerSearchQuery || customerSearchQuery.length < 2) return;

    setCustomerSearching(true);
    try {
      const response = await authFetch(
        `${getApiUrl()}/admin/shopify/customers/search?q=${encodeURIComponent(customerSearchQuery)}`,
        shop
      );
      if (response.ok) {
        const data = await response.json();
        setCustomerSearchResults(data.customers || []);
      }
    } catch (err) {
      console.error('Customer search failed:', err);
    } finally {
      setCustomerSearching(false);
    }
  }, [customerSearchQuery, shop]);

  // Enroll customer as member
  const enrollCustomerAsMember = useCallback(async () => {
    if (!selectedCustomer) return;

    setEnrolling(true);
    setEnrollError('');
    try {
      const response = await authFetch(`${getApiUrl()}/members`, shop, {
        method: 'POST',
        body: JSON.stringify({
          shopify_customer_id: selectedCustomer.id,
          email: selectedCustomer.email,
          first_name: selectedCustomer.firstName,
          last_name: selectedCustomer.lastName,
          phone: selectedCustomer.phone,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to enroll member');
      }

      const newMember = await response.json();

      // Set the new member as selected
      setSelectedMember({
        id: newMember.id,
        member_number: newMember.member_number || '',
        name: `${selectedCustomer.firstName} ${selectedCustomer.lastName}`.trim() || null,
        email: selectedCustomer.email,
        tier: newMember.tier || null,
      });

      // Invalidate members query for future searches
      queryClient.invalidateQueries({ queryKey: ['members'] });

      // Close modal and reset state
      setAddMemberModalOpen(false);
      setCustomerSearchQuery('');
      setCustomerSearchResults([]);
      setSelectedCustomer(null);
    } catch (err) {
      setEnrollError(err instanceof Error ? err.message : 'Failed to enroll member');
    } finally {
      setEnrolling(false);
    }
  }, [selectedCustomer, shop, queryClient]);

  // Close add member modal and reset
  const closeAddMemberModal = useCallback(() => {
    setAddMemberModalOpen(false);
    setCustomerSearchQuery('');
    setCustomerSearchResults([]);
    setSelectedCustomer(null);
    setEnrollError('');
  }, []);

  // Success state for showing completion result
  const [completionResult, setCompletionResult] = useState<CompleteBatchResult | null>(null);

  // Create trade-in mutation - now auto-completes and issues store credit
  const createMutation = useMutation({
    mutationFn: async () => {
      if (!selectedMember) throw new Error('Please select a member');

      const validItems = items.filter((item) => item.trade_value && parseFloat(item.trade_value) > 0);
      if (validItems.length === 0) {
        throw new Error('Please add at least one item with a trade value');
      }

      // Create batch
      const batch = await createTradeInBatch(shop, {
        member_id: selectedMember.id,
        category: selectedCategory,
        notes: batchNotes || undefined,
      });

      // Add items
      await addTradeInItems(
        shop,
        batch.id,
        validItems.map((item) => ({
          product_title: item.product_title || undefined,
          trade_value: parseFloat(item.trade_value),
          market_value: item.market_value ? parseFloat(item.market_value) : undefined,
          notes: item.notes || undefined,
        }))
      );

      // Auto-complete batch to issue store credit immediately
      const result = await completeBatch(shop, batch.id);
      return result;
    },
    onSuccess: (result) => {
      setCompletionResult(result);
      queryClient.invalidateQueries({ queryKey: ['trade-ins'] });
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  // Handle member selection
  const handleMemberSelect = useCallback((selected: string[]) => {
    const memberId = selected[0];
    if (!memberId) return;

    // Find the member from options
    const option = memberOptions.find((o) => o.value === memberId);
    if (option && 'member' in option) {
      setSelectedMember((option as { member: Member }).member);
      setMemberSearch('');
      setMemberOptions([]);
    }
  }, [memberOptions]);

  // Clear member selection
  const clearMember = useCallback(() => {
    setSelectedMember(null);
    setMemberSearch('');
  }, []);

  // Add item
  const addItem = useCallback(() => {
    setItems((prev) => [
      ...prev,
      { id: Date.now().toString(), product_title: '', trade_value: '', market_value: '', notes: '' },
    ]);
  }, []);

  // Remove item
  const removeItem = useCallback((id: string) => {
    setItems((prev) => (prev.length > 1 ? prev.filter((item) => item.id !== id) : prev));
  }, []);

  // Update item field
  const updateItem = useCallback((id: string, field: keyof TradeInItem, value: string) => {
    setItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, [field]: value } : item))
    );
  }, []);

  // Calculate totals
  const totalTradeValue = items.reduce((sum, item) => {
    const val = parseFloat(item.trade_value) || 0;
    return sum + val;
  }, 0);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  // Handle form submit
  const handleSubmit = useCallback(() => {
    setError('');
    createMutation.mutate();
  }, [createMutation]);

  if (!shop) {
    return (
      <Page title="New Trade-In">
        <Banner tone="warning">
          <p>No shop connected. Please install the app from the Shopify App Store.</p>
        </Banner>
      </Page>
    );
  }

  // Build category choices for ChoiceList
  // IMPORTANT: Filter out null/undefined categories to prevent "Cannot read properties of undefined" errors
  const categoryChoices = categories.filter(cat => cat && cat.id && cat.name).map((cat) => ({
    label: `${cat.icon || ''} ${cat.name}`,
    value: cat.id,
  }));

  return (
    <Page
      title="New Trade-In"
      subtitle="Create a new trade-in batch for a member"
      backAction={{ content: 'Trade-Ins', onAction: () => navigate('/app/trade-ins') }}
      primaryAction={{
        content: `Complete Trade-In & Issue ${formatCurrency(totalTradeValue)}`,
        onAction: handleSubmit,
        loading: createMutation.isPending,
        disabled: !selectedMember || totalTradeValue <= 0,
      }}
    >
      <Layout>
        {error && (
          <Layout.Section>
            <Banner tone="critical" onDismiss={() => setError('')}>
              <p>{error}</p>
            </Banner>
          </Layout.Section>
        )}

        {/* Warning when no member selected but items added */}
        {!selectedMember && totalTradeValue > 0 && (
          <Layout.Section>
            <Banner tone="warning" icon={AlertCircleIcon}>
              <p>Please select a member before creating the trade-in. Use the search above or add a new member from your Shopify customers.</p>
            </Banner>
          </Layout.Section>
        )}

        {/* Step 1: Select Member */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <InlineStack gap="200" blockAlign="center">
                <Badge tone="info">1</Badge>
                <Text as="h2" variant="headingMd">Select Member</Text>
              </InlineStack>

              {selectedMember ? (
                <Box
                  padding="400"
                  background="bg-surface-success"
                  borderRadius="200"
                  borderColor="border-success"
                  borderWidth="025"
                >
                  <InlineStack align="space-between" blockAlign="center">
                    <InlineStack gap="300" blockAlign="center">
                      <Box
                        padding="200"
                        background="bg-fill-success"
                        borderRadius="full"
                      >
                        <Icon source={CheckIcon} tone="success" />
                      </Box>
                      <BlockStack gap="050">
                        <Text as="span" variant="bodyMd" fontWeight="semibold">
                          {selectedMember.name || selectedMember.email}
                        </Text>
                        <Text as="span" variant="bodySm" tone="subdued">
                          {selectedMember.member_number} · {selectedMember.tier?.name || 'No tier'}
                        </Text>
                      </BlockStack>
                    </InlineStack>
                    <Button variant="plain" onClick={clearMember}>
                      Change
                    </Button>
                  </InlineStack>
                </Box>
              ) : (
                <BlockStack gap="300">
                  <Autocomplete
                    options={memberOptions}
                    selected={[]}
                    onSelect={handleMemberSelect}
                    loading={searchLoading}
                    textField={
                      <Autocomplete.TextField
                        label="Search members"
                        labelHidden
                        onChange={setMemberSearch}
                        value={memberSearch}
                        prefix={<Icon source={SearchIcon} />}
                        placeholder="Search by member number, name, or email..."
                        autoComplete="off"
                      />
                    }
                    emptyState={
                      memberSearch.length >= 2 ? (
                        <Box padding="400">
                          <BlockStack gap="200" inlineAlign="center">
                            <Text as="p" tone="subdued" alignment="center">
                              No members found matching "{memberSearch}"
                            </Text>
                            <Button
                              size="slim"
                              onClick={() => setAddMemberModalOpen(true)}
                            >
                              Add New Member
                            </Button>
                          </BlockStack>
                        </Box>
                      ) : undefined
                    }
                  />
                  {!selectedMember && !memberSearch && (
                    <InlineStack gap="200" blockAlign="center">
                      <Text as="span" variant="bodySm" tone="subdued">
                        Don't see the customer?
                      </Text>
                      <Button
                        variant="plain"
                        size="slim"
                        onClick={() => setAddMemberModalOpen(true)}
                      >
                        Add new member from Shopify
                      </Button>
                    </InlineStack>
                  )}
                </BlockStack>
              )}
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Step 2: Select Category */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <InlineStack gap="200" blockAlign="center">
                <Badge tone="info">2</Badge>
                <Text as="h2" variant="headingMd">Category</Text>
              </InlineStack>

              <ChoiceList
                title="Select category"
                titleHidden
                choices={categoryChoices}
                selected={[selectedCategory]}
                onChange={(value) => setSelectedCategory(value[0])}
              />
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Step 3: Add Items */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between" blockAlign="center">
                <InlineStack gap="200" blockAlign="center">
                  <Badge tone="info">3</Badge>
                  <Text as="h2" variant="headingMd">Items</Text>
                </InlineStack>
                <Button icon={PlusIcon} onClick={addItem}>
                  Add Item
                </Button>
              </InlineStack>

              <BlockStack gap="300">
                {items.map((item, index) => (
                  <Box
                    key={item.id}
                    padding="400"
                    background="bg-surface-secondary"
                    borderRadius="200"
                  >
                    <BlockStack gap="300">
                      <InlineStack align="space-between">
                        <Text as="span" variant="bodySm" tone="subdued">
                          Item {index + 1}
                        </Text>
                        {items.length > 1 && (
                          <Button
                            icon={DeleteIcon}
                            variant="plain"
                            tone="critical"
                            onClick={() => removeItem(item.id)}
                            accessibilityLabel="Remove item"
                          />
                        )}
                      </InlineStack>

                      <FormLayout>
                        <FormLayout.Group>
                          <TextField
                            label="Product Title"
                            value={item.product_title}
                            onChange={(value) => updateItem(item.id, 'product_title', value)}
                            placeholder="Card name, set, etc."
                            autoComplete="off"
                          />
                        </FormLayout.Group>
                        <FormLayout.Group condensed>
                          <TextField
                            label="Trade Value"
                            type="number"
                            value={item.trade_value}
                            onChange={(value) => updateItem(item.id, 'trade_value', value)}
                            prefix="$"
                            placeholder="0.00"
                            autoComplete="off"
                            requiredIndicator
                          />
                          <TextField
                            label="Market Value"
                            type="number"
                            value={item.market_value}
                            onChange={(value) => updateItem(item.id, 'market_value', value)}
                            prefix="$"
                            placeholder="0.00"
                            autoComplete="off"
                          />
                        </FormLayout.Group>
                      </FormLayout>
                    </BlockStack>
                  </Box>
                ))}
              </BlockStack>

              <Divider />

              <Box padding="400" background="bg-surface-info" borderRadius="200">
                <InlineStack align="space-between" blockAlign="center">
                  <Text as="span" variant="bodyMd" fontWeight="semibold">
                    Total Trade Value
                  </Text>
                  <Text as="span" variant="headingLg" fontWeight="bold">
                    {formatCurrency(totalTradeValue)}
                  </Text>
                </InlineStack>
              </Box>
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Step 4: Notes */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <InlineStack gap="200" blockAlign="center">
                <Badge>4</Badge>
                <Text as="h2" variant="headingMd">Notes (Optional)</Text>
              </InlineStack>

              <TextField
                label="Batch Notes"
                labelHidden
                value={batchNotes}
                onChange={setBatchNotes}
                multiline={3}
                placeholder="Add any notes about this trade-in..."
                autoComplete="off"
              />
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Mobile Submit Button */}
        <Layout.Section>
          <InlineStack align="end" gap="300">
            <Button url="/app/trade-ins">Cancel</Button>
            <Button
              variant="primary"
              onClick={handleSubmit}
              loading={createMutation.isPending}
              disabled={!selectedMember || totalTradeValue <= 0}
            >
              Complete Trade-In & Issue {formatCurrency(totalTradeValue)}
            </Button>
          </InlineStack>
        </Layout.Section>
      </Layout>

      {/* Inline Add Member Modal */}
      <Modal
        open={addMemberModalOpen}
        onClose={closeAddMemberModal}
        title="Add New Member"
        primaryAction={
          selectedCustomer
            ? {
                content: 'Enroll as Member',
                onAction: enrollCustomerAsMember,
                loading: enrolling,
              }
            : undefined
        }
        secondaryActions={
          selectedCustomer
            ? [{ content: 'Back', onAction: () => setSelectedCustomer(null) }]
            : [{ content: 'Cancel', onAction: closeAddMemberModal }]
        }
      >
        <Modal.Section>
          {enrollError && (
            <Box paddingBlockEnd="400">
              <Banner tone="critical">
                <p>{enrollError}</p>
              </Banner>
            </Box>
          )}

          {selectedCustomer ? (
            <BlockStack gap="400">
              <Text as="p">Enroll this Shopify customer as a TradeUp member:</Text>
              <Card background="bg-surface-secondary">
                <BlockStack gap="200">
                  <Text as="h3" variant="headingSm">
                    {selectedCustomer.firstName} {selectedCustomer.lastName}
                  </Text>
                  <Text as="p" tone="subdued">
                    {selectedCustomer.email}
                  </Text>
                  <InlineStack gap="400">
                    <Text as="span" variant="bodySm">
                      {selectedCustomer.ordersCount} orders
                    </Text>
                    <Text as="span" variant="bodySm">
                      ${selectedCustomer.totalSpent} spent
                    </Text>
                  </InlineStack>
                </BlockStack>
              </Card>
            </BlockStack>
          ) : (
            <BlockStack gap="400">
              <Text as="p">Search your Shopify customers to add them as members:</Text>

              <TextField
                label="Search customers"
                labelHidden
                value={customerSearchQuery}
                onChange={(value) => {
                  setCustomerSearchQuery(value);
                }}
                placeholder="Search by name, email, or phone..."
                autoComplete="off"
                prefix={<Icon source={SearchIcon} />}
                connectedRight={
                  <Button onClick={searchShopifyCustomers} loading={customerSearching}>
                    Search
                  </Button>
                }
              />

              {customerSearchResults.length > 0 ? (
                <BlockStack gap="200">
                  <Text as="h3" variant="headingSm">
                    Results ({customerSearchResults.length})
                  </Text>
                  {customerSearchResults.map((customer) => (
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
                              {customer.firstName} {customer.lastName}
                            </Text>
                            <Text as="span" variant="bodySm" tone="subdued">
                              {customer.email}
                            </Text>
                          </BlockStack>
                          <BlockStack gap="050" inlineAlign="end">
                            <Text as="span" variant="bodySm">
                              {customer.ordersCount} orders
                            </Text>
                            <Text as="span" variant="bodySm" tone="subdued">
                              ${customer.totalSpent}
                            </Text>
                          </BlockStack>
                        </InlineStack>
                      </Box>
                    </div>
                  ))}
                </BlockStack>
              ) : customerSearchQuery.length >= 2 && !customerSearching ? (
                <Text as="p" tone="subdued" alignment="center">
                  No customers found. Try a different search.
                </Text>
              ) : null}
            </BlockStack>
          )}
        </Modal.Section>
      </Modal>

      {/* Success Modal - Shows after trade-in is completed */}
      <Modal
        open={!!completionResult}
        onClose={() => navigate('/app/trade-ins')}
        title="Trade-In Complete!"
        primaryAction={{
          content: 'View Trade-Ins',
          onAction: () => navigate('/app/trade-ins'),
        }}
        secondaryActions={[
          {
            content: 'Create Another',
            onAction: () => {
              setCompletionResult(null);
              setSelectedMember(null);
              setItems([{ id: '1', product_title: '', trade_value: '', market_value: '', notes: '' }]);
              setBatchNotes('');
            },
          },
        ]}
      >
        <Modal.Section>
          <BlockStack gap="400">
            <Banner tone="success">
              <p>Trade-in {completionResult?.batch_reference} has been completed and store credit has been issued.</p>
            </Banner>

            <Card>
              <BlockStack gap="300">
                <InlineStack align="space-between">
                  <Text as="span" tone="subdued">Trade Value</Text>
                  <Text as="span" fontWeight="semibold">{formatCurrency(completionResult?.trade_value || 0)}</Text>
                </InlineStack>

                {completionResult?.bonus?.eligible && (completionResult?.bonus?.bonus_amount || 0) > 0 && (
                  <>
                    <Divider />
                    <InlineStack align="space-between">
                      <Text as="span" tone="subdued">
                        Tier Bonus ({completionResult?.bonus?.tier_name} +{completionResult?.bonus?.bonus_percent}%)
                      </Text>
                      <Badge tone="success">{String(`+${formatCurrency(completionResult?.bonus?.bonus_amount || 0)}`)}</Badge>
                    </InlineStack>
                  </>
                )}

                <Divider />

                <InlineStack align="space-between">
                  <Text as="span" fontWeight="bold">Total Store Credit Issued</Text>
                  <Text as="span" fontWeight="bold" tone="success">
                    {formatCurrency(
                      (completionResult?.trade_value || 0) +
                      (completionResult?.bonus?.bonus_amount || 0)
                    )}
                  </Text>
                </InlineStack>
              </BlockStack>
            </Card>

            <Text as="p" variant="bodySm" tone="subdued" alignment="center">
              The member's store credit balance has been updated in Shopify.
            </Text>
          </BlockStack>
        </Modal.Section>
      </Modal>
    </Page>
  );
}
