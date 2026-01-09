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
  Select,
  FormLayout,
  Banner,
  Spinner,
  Autocomplete,
  Icon,
  Tag,
  Divider,
  ButtonGroup,
  ChoiceList,
} from '@shopify/polaris';
import {
  SearchIcon,
  PlusIcon,
  DeleteIcon,
  PersonIcon,
  CheckIcon,
} from '@shopify/polaris-icons';
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

// Default categories if none are configured
const DEFAULT_CATEGORIES: TradeInCategory[] = [
  { id: 'sports', name: 'Sports', icon: '🏈' },
  { id: 'pokemon', name: 'Pokemon', icon: '⚡' },
  { id: 'magic', name: 'Magic', icon: '🔮' },
  { id: 'riftbound', name: 'Riftbound', icon: '🌀' },
  { id: 'tcg_other', name: 'TCG Other', icon: '🎴' },
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

export function EmbeddedNewTradeIn({ shop }: NewTradeInProps) {
  const navigate = useNavigate();

  // Member search state
  const [memberSearch, setMemberSearch] = useState('');
  const [selectedMember, setSelectedMember] = useState<Member | null>(null);
  const [memberOptions, setMemberOptions] = useState<Array<{ value: string; label: string }>>([]);
  const [searchLoading, setSearchLoading] = useState(false);

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
      } catch (err) {
        console.error('Search failed:', err);
        setMemberOptions([]);
      } finally {
        setSearchLoading(false);
      }
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [memberSearch, shop, selectedMember]);

  // Create trade-in mutation
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

      return batch;
    },
    onSuccess: () => {
      navigate('/app/trade-ins');
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
  const categoryChoices = categories.map((cat) => ({
    label: `${cat.icon} ${cat.name}`,
    value: cat.id,
  }));

  return (
    <Page
      title="New Trade-In"
      subtitle="Create a new trade-in batch for a member"
      backAction={{ content: 'Trade-Ins', url: '/app/trade-ins' }}
      primaryAction={{
        content: `Create Trade-In ${formatCurrency(totalTradeValue)}`,
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
                        <Text as="p" tone="subdued" alignment="center">
                          No members found
                        </Text>
                      </Box>
                    ) : undefined
                  }
                />
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
              Create Trade-In {formatCurrency(totalTradeValue)}
            </Button>
          </InlineStack>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
