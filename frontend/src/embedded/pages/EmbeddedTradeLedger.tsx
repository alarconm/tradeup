/**
 * TradeUp Trade-In Ledger - Simplified Version
 *
 * Simple ledger for recording trade-in transactions.
 * All trade-ins are tied to Shopify customer accounts.
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
  DataTable,
  Pagination,
  Banner,
  EmptyState,
  Modal,
  TextField,
  Select,
  FormLayout,
  Divider,
  Box,
  InlineGrid,
  Spinner,
  Icon,
} from '@shopify/polaris';
import { PlusIcon, DeleteIcon, SearchIcon, CheckIcon } from '@shopify/polaris-icons';
import { TitleBar } from '@shopify/app-bridge-react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';
import { useCollections } from '../../hooks/useShopifyData';

interface TradeLedgerProps {
  shop: string | null;
}

interface TradeLedgerEntry {
  id: number;
  reference: string;
  trade_date: string;
  customer_name: string | null;
  customer_email: string | null;
  member_id: number | null;
  guest_name: string | null;
  total_value: number;
  cash_amount: number;
  credit_amount: number;
  category: string | null;
  collection_name: string | null;
  notes: string | null;
  created_by: string | null;
  created_at: string;
}

interface TradeLedgerSummary {
  total_entries: number;
  total_value: number;
  total_cash: number;
  total_credit: number;
}

interface ShopifyCustomer {
  id: string;
  gid?: string;
  email: string;
  firstName: string;
  lastName: string;
  displayName?: string;
  name?: string;
  phone: string | null;
  ordersCount?: number;
  numberOfOrders?: number;
  totalSpent?: number | string;
  amountSpent?: number | string;
  storeCredit?: number;
  is_member?: boolean;
  member_id?: number;
  member_number?: string;
}

// Custom hook for debouncing a value
function useDebouncedValue<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
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

async function fetchEntries(shop: string | null, page: number, search: string = ''): Promise<{
  entries: TradeLedgerEntry[];
  total: number;
  page: number;
  pages: number;
}> {
  const params = new URLSearchParams({
    page: String(page),
    per_page: '20',
  });
  if (search) params.append('search', search);

  const response = await authFetch(
    `${getApiUrl()}/trade-ledger/?${params.toString()}`,
    shop
  );
  if (!response.ok) throw new Error('Failed to fetch entries');
  return response.json();
}

async function fetchSummary(shop: string | null): Promise<TradeLedgerSummary> {
  const response = await authFetch(`${getApiUrl()}/trade-ledger/summary`, shop);
  if (!response.ok) throw new Error('Failed to fetch summary');
  return response.json();
}

async function fetchCategories(shop: string | null): Promise<{ categories: string[] }> {
  const response = await authFetch(`${getApiUrl()}/trade-ledger/categories`, shop);
  if (!response.ok) throw new Error('Failed to fetch categories');
  return response.json();
}


async function createEntry(shop: string | null, data: Record<string, unknown>): Promise<TradeLedgerEntry> {
  const response = await authFetch(`${getApiUrl()}/trade-ledger/`, shop, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to create entry');
  }
  return response.json();
}

async function deleteEntry(shop: string | null, id: number): Promise<void> {
  const response = await authFetch(`${getApiUrl()}/trade-ledger/${id}`, shop, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to delete entry');
}

export function EmbeddedTradeLedger({ shop }: TradeLedgerProps) {
  const isMobile = useIsMobile();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [entryToDelete, setEntryToDelete] = useState<TradeLedgerEntry | null>(null);

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPage(1); // Reset to first page when search changes
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Customer search state (instant search like Add Member modal)
  const [customerSearch, setCustomerSearch] = useState('');
  const [selectedCustomer, setSelectedCustomer] = useState<ShopifyCustomer | null>(null);
  const [searchResults, setSearchResults] = useState<ShopifyCustomer[]>([]);
  const [searching, setSearching] = useState(false);

  // Fast debounce for instant search feel
  const debouncedCustomerSearch = useDebouncedValue(customerSearch, 150);

  // Create new customer mode
  const [createNewMode, setCreateNewMode] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [newFirstName, setNewFirstName] = useState('');
  const [newLastName, setNewLastName] = useState('');
  const [newPhone, setNewPhone] = useState('');

  // Form state
  const [totalValue, setTotalValue] = useState('');
  const [cashAmount, setCashAmount] = useState('');
  const [creditAmount, setCreditAmount] = useState('');
  const [category, setCategory] = useState('');
  const [customCategory, setCustomCategory] = useState('');
  const [notes, setNotes] = useState('');

  // Fetch data
  const { data: entriesData, isLoading } = useQuery({
    queryKey: ['trade-ledger', shop, page, debouncedSearch],
    queryFn: () => fetchEntries(shop, page, debouncedSearch),
    enabled: !!shop,
  });

  const { data: summary } = useQuery({
    queryKey: ['trade-ledger-summary', shop],
    queryFn: () => fetchSummary(shop),
    enabled: !!shop,
  });

  const { data: categoriesData } = useQuery({
    queryKey: ['trade-ledger-categories', shop],
    queryFn: () => fetchCategories(shop),
    enabled: !!shop,
  });

  const { data: collectionsData } = useCollections(shop);

  // Mutations
  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => createEntry(shop, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trade-ledger'] });
      queryClient.invalidateQueries({ queryKey: ['trade-ledger-summary'] });
      closeModal();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteEntry(shop, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trade-ledger'] });
      queryClient.invalidateQueries({ queryKey: ['trade-ledger-summary'] });
      setDeleteModalOpen(false);
      setEntryToDelete(null);
    },
  });

  // Instant Shopify customer search
  useEffect(() => {
    const searchCustomers = async () => {
      if (!debouncedCustomerSearch || debouncedCustomerSearch.length < 2 || selectedCustomer) {
        if (!selectedCustomer) setSearchResults([]);
        return;
      }

      setSearching(true);
      try {
        const response = await authFetch(
          `${getApiUrl()}/members/search-shopify?q=${encodeURIComponent(debouncedCustomerSearch)}`,
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
    };

    searchCustomers();
  }, [debouncedCustomerSearch, shop, selectedCustomer]);

  // Auto-calculate credit when total changes
  useEffect(() => {
    const total = parseFloat(totalValue) || 0;
    const cash = parseFloat(cashAmount) || 0;
    const credit = total - cash;
    if (credit >= 0) {
      setCreditAmount(credit.toFixed(2));
    }
  }, [totalValue, cashAmount]);

  const closeModal = useCallback(() => {
    setModalOpen(false);
    setSelectedCustomer(null);
    setCustomerSearch('');
    setSearchResults([]);
    setCreateNewMode(false);
    setNewEmail('');
    setNewFirstName('');
    setNewLastName('');
    setNewPhone('');
    setTotalValue('');
    setCashAmount('');
    setCreditAmount('');
    setCategory('');
    setCustomCategory('');
    setNotes('');
  }, []);

  // Create new Shopify customer mutation
  const createCustomerMutation = useMutation({
    mutationFn: async () => {
      if (!newEmail) throw new Error('Email is required');

      const response = await authFetch(`${getApiUrl()}/members/create-and-enroll`, shop, {
        method: 'POST',
        body: JSON.stringify({
          email: newEmail,
          first_name: newFirstName || undefined,
          last_name: newLastName || undefined,
          phone: newPhone || undefined,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to create customer');
      }
      return response.json();
    },
    onSuccess: (data) => {
      setSelectedCustomer({
        id: data.shopify_customer_id || data.id,
        email: newEmail,
        firstName: newFirstName,
        lastName: newLastName,
        phone: newPhone || null,
        is_member: true,
        member_id: data.id,
        member_number: data.member_number,
      });
      setCreateNewMode(false);
      setNewEmail('');
      setNewFirstName('');
      setNewLastName('');
      setNewPhone('');
      queryClient.invalidateQueries({ queryKey: ['members'] });
    },
  });

  const handleSubmit = useCallback(async () => {
    if (!selectedCustomer) return;

    const data: Record<string, unknown> = {
      total_value: parseFloat(totalValue) || 0,
      cash_amount: parseFloat(cashAmount) || 0,
      credit_amount: parseFloat(creditAmount) || 0,
      notes: notes || null,
    };

    // Get or create member_id for the customer
    let memberId = selectedCustomer.member_id;

    if (!memberId && !selectedCustomer.is_member) {
      // Enroll the customer as a member first
      try {
        const enrollResponse = await authFetch(`${getApiUrl()}/members/enroll`, shop, {
          method: 'POST',
          body: JSON.stringify({
            shopify_customer_id: selectedCustomer.id,
          }),
        });

        if (!enrollResponse.ok) {
          const error = await enrollResponse.json();
          throw new Error(error.error || 'Failed to enroll customer');
        }

        const enrollData = await enrollResponse.json();
        memberId = enrollData.id || enrollData.member_id;

        // Update selected customer
        setSelectedCustomer({
          ...selectedCustomer,
          is_member: true,
          member_id: memberId,
          member_number: enrollData.member_number,
        });
      } catch (err) {
        console.error('Failed to enroll customer:', err);
        return;
      }
    }

    data.member_id = memberId;

    // Handle category
    if (category === 'custom' && customCategory) {
      data.category = customCategory;
    } else if (category && category !== 'none') {
      const collection = collectionsData?.collections?.find(c => c.id === category);
      if (collection) {
        data.collection_id = collection.id;
        data.collection_name = collection.title;
        data.category = collection.title;
      } else {
        data.category = category;
      }
    }

    createMutation.mutate(data);
  }, [selectedCustomer, totalValue, cashAmount, creditAmount, category, customCategory, notes, collectionsData, createMutation, shop]);

  // Determine if we can create a new customer
  const canCreateNew = newEmail && newEmail.includes('@') && newEmail.includes('.');

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  // Build category options
  const categoryOptions = [
    { label: 'None', value: 'none' },
    ...(categoriesData?.categories || []).map(cat => ({ label: cat, value: cat })),
    ...(collectionsData?.collections || []).map(col => ({
      label: `📁 ${col.title}`,
      value: col.id
    })),
    { label: '+ Custom Category', value: 'custom' },
  ];

  if (!shop) {
    return (
      <Page title="Trade-In Ledger">
        <Banner tone="warning">
          <p>No shop connected. Please install the app from the Shopify App Store.</p>
        </Banner>
      </Page>
    );
  }

  const entries = entriesData?.entries || [];
  const totalPages = entriesData?.pages || 1;

  return (
    <>
      <TitleBar title="Trade-In Ledger">
        <button variant="primary" onClick={() => setModalOpen(true)}>
          New Trade-In
        </button>
      </TitleBar>

      <Page
        title="Trade-In Ledger"
        subtitle="Simple record of all trade-in transactions"
        primaryAction={{
          content: 'New Trade-In',
          icon: PlusIcon,
          onAction: () => setModalOpen(true),
        }}
      >
        <Layout>
          {/* Summary Cards */}
          <Layout.Section>
            <InlineGrid columns={isMobile ? 2 : 4} gap="400">
              <Card>
                <BlockStack gap="200">
                  <Text as="h3" variant="headingSm" tone="subdued">Total Trade-Ins</Text>
                  <Text as="p" variant="headingXl">{summary?.total_entries || 0}</Text>
                </BlockStack>
              </Card>
              <Card>
                <BlockStack gap="200">
                  <Text as="h3" variant="headingSm" tone="subdued">Total Value</Text>
                  <Text as="p" variant="headingXl">{formatCurrency(summary?.total_value || 0)}</Text>
                </BlockStack>
              </Card>
              <Card>
                <BlockStack gap="200">
                  <Text as="h3" variant="headingSm" tone="subdued">Paid Cash</Text>
                  <Text as="p" variant="headingXl">{formatCurrency(summary?.total_cash || 0)}</Text>
                </BlockStack>
              </Card>
              <Card>
                <BlockStack gap="200">
                  <Text as="h3" variant="headingSm" tone="subdued">Paid Credit</Text>
                  <Text as="p" variant="headingXl">{formatCurrency(summary?.total_credit || 0)}</Text>
                </BlockStack>
              </Card>
            </InlineGrid>
          </Layout.Section>

          {/* Search and Entries List */}
          <Layout.Section>
            <Card>
              <Box paddingBlockEnd="400">
                <TextField
                  label=""
                  labelHidden
                  value={searchQuery}
                  onChange={setSearchQuery}
                  placeholder="Search by reference, customer name, or email..."
                  autoComplete="off"
                  clearButton
                  onClearButtonClick={() => setSearchQuery('')}
                />
              </Box>

              {isLoading ? (
                <Box padding="800">
                  <InlineStack align="center">
                    <Text as="p">Loading...</Text>
                  </InlineStack>
                </Box>
              ) : entries.length === 0 ? (
                debouncedSearch ? (
                  <EmptyState
                    heading="No trade-ins found"
                    image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                  >
                    <p>No trade-ins match your search for "{debouncedSearch}". Try a different search term.</p>
                  </EmptyState>
                ) : (
                  <EmptyState
                    heading="No trade-ins recorded yet"
                    action={{
                      content: 'Record First Trade-In',
                      onAction: () => setModalOpen(true),
                    }}
                    image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                  >
                    <p>Start recording trade-in transactions to track your store's activity.</p>
                  </EmptyState>
                )
              ) : isMobile ? (
                // Mobile card view
                <BlockStack gap="300">
                  {entries.map((entry, index) => (
                    <Box key={entry.id} padding="300">
                      {index > 0 && <Divider />}
                      <BlockStack gap="200">
                        <InlineStack align="space-between">
                          <Text as="span" fontWeight="semibold">{entry.reference}</Text>
                          <Text as="span" variant="bodySm" tone="subdued">
                            {formatDate(entry.trade_date)}
                          </Text>
                        </InlineStack>
                        <Text as="p">{entry.customer_name || 'Guest'}</Text>
                        <InlineStack gap="200">
                          <Badge tone="success">{formatCurrency(entry.total_value)}</Badge>
                          {entry.category && <Badge>{String(entry.category)}</Badge>}
                        </InlineStack>
                        <InlineStack gap="200">
                          <Text as="span" variant="bodySm">
                            Cash: {formatCurrency(entry.cash_amount)}
                          </Text>
                          <Text as="span" variant="bodySm">
                            Credit: {formatCurrency(entry.credit_amount)}
                          </Text>
                        </InlineStack>
                        <Button
                          size="slim"
                          icon={DeleteIcon}
                          tone="critical"
                          onClick={() => {
                            setEntryToDelete(entry);
                            setDeleteModalOpen(true);
                          }}
                        >
                          Delete
                        </Button>
                      </BlockStack>
                    </Box>
                  ))}
                </BlockStack>
              ) : (
                // Desktop table view
                <DataTable
                  columnContentTypes={['text', 'text', 'text', 'numeric', 'numeric', 'numeric', 'text']}
                  headings={['Reference', 'Date', 'Customer', 'Total', 'Cash', 'Credit', 'Category']}
                  rows={entries.map((entry) => [
                    entry.reference,
                    formatDate(entry.trade_date),
                    entry.customer_name || 'Guest',
                    formatCurrency(entry.total_value),
                    formatCurrency(entry.cash_amount),
                    formatCurrency(entry.credit_amount),
                    entry.category || '-',
                  ])}
                />
              )}

              {totalPages > 1 && (
                <Box padding="400">
                  <InlineStack align="center">
                    <Pagination
                      hasPrevious={page > 1}
                      hasNext={page < totalPages}
                      onPrevious={() => setPage(p => p - 1)}
                      onNext={() => setPage(p => p + 1)}
                    />
                  </InlineStack>
                </Box>
              )}
            </Card>
          </Layout.Section>
        </Layout>
      </Page>

      {/* New Entry Modal */}
      <Modal
        open={modalOpen}
        onClose={closeModal}
        title="Record Trade-In"
        primaryAction={{
          content: 'Save Trade-In',
          onAction: handleSubmit,
          loading: createMutation.isPending,
          disabled: !selectedCustomer || !totalValue || parseFloat(totalValue) <= 0,
        }}
        secondaryActions={[{ content: 'Cancel', onAction: closeModal }]}
      >
        <Modal.Section>
          <FormLayout>
            {/* Customer Selection */}
            <BlockStack gap="300">
              <Text as="h3" variant="headingSm">Customer</Text>

              {selectedCustomer ? (
                <Box
                  padding="300"
                  background="bg-surface-success"
                  borderRadius="200"
                  borderColor="border-success"
                  borderWidth="025"
                >
                  <InlineStack align="space-between" blockAlign="center">
                    <InlineStack gap="200" blockAlign="center">
                      <Box padding="100" background="bg-fill-success" borderRadius="full">
                        <Icon source={CheckIcon} tone="success" />
                      </Box>
                      <BlockStack gap="050">
                        <InlineStack gap="200" blockAlign="center">
                          <Text as="span" variant="bodyMd" fontWeight="semibold">
                            {selectedCustomer.name || `${selectedCustomer.firstName || ''} ${selectedCustomer.lastName || ''}`.trim() || selectedCustomer.email}
                          </Text>
                          {selectedCustomer.is_member && (
                            <Badge tone="success" size="small">Member</Badge>
                          )}
                        </InlineStack>
                        <Text as="span" variant="bodySm" tone="subdued">
                          {selectedCustomer.email}
                          {selectedCustomer.member_number && ` · ${selectedCustomer.member_number}`}
                        </Text>
                      </BlockStack>
                    </InlineStack>
                    <Button
                      variant="plain"
                      onClick={() => {
                        setSelectedCustomer(null);
                        setCustomerSearch('');
                      }}
                    >
                      Change
                    </Button>
                  </InlineStack>
                </Box>
              ) : createNewMode ? (
                <BlockStack gap="300">
                  <Banner tone="info">
                    <Text as="p">Create a new customer. They will be automatically enrolled in your loyalty program.</Text>
                  </Banner>

                  <TextField
                    label="Email"
                    type="email"
                    value={newEmail}
                    onChange={setNewEmail}
                    autoComplete="email"
                    placeholder="customer@example.com"
                    requiredIndicator
                    error={newEmail && !canCreateNew ? 'Please enter a valid email' : undefined}
                  />

                  <InlineGrid columns={2} gap="300">
                    <TextField
                      label="First Name"
                      value={newFirstName}
                      onChange={setNewFirstName}
                      autoComplete="given-name"
                    />
                    <TextField
                      label="Last Name"
                      value={newLastName}
                      onChange={setNewLastName}
                      autoComplete="family-name"
                    />
                  </InlineGrid>

                  <TextField
                    label="Phone (optional)"
                    type="tel"
                    value={newPhone}
                    onChange={setNewPhone}
                    autoComplete="tel"
                  />

                  <InlineStack gap="200">
                    <Button
                      variant="primary"
                      onClick={() => createCustomerMutation.mutate()}
                      loading={createCustomerMutation.isPending}
                      disabled={!canCreateNew}
                    >
                      Create Customer
                    </Button>
                    <Button
                      variant="plain"
                      onClick={() => {
                        setCreateNewMode(false);
                        setNewEmail('');
                        setNewFirstName('');
                        setNewLastName('');
                        setNewPhone('');
                      }}
                    >
                      Back to Search
                    </Button>
                  </InlineStack>
                </BlockStack>
              ) : (
                <BlockStack gap="200">
                  <TextField
                    label="Search Shopify Customers"
                    labelHidden
                    value={customerSearch}
                    onChange={setCustomerSearch}
                    placeholder="Type to search by name, email, or phone..."
                    autoComplete="off"
                    clearButton
                    onClearButtonClick={() => setCustomerSearch('')}
                    prefix={<Icon source={SearchIcon} />}
                    suffix={searching ? <Spinner size="small" /> : null}
                    helpText={customerSearch.length > 0 && customerSearch.length < 2 ? "Type at least 2 characters" : undefined}
                  />

                  {searchResults.length > 0 ? (
                    <BlockStack gap="100">
                      {searchResults.map((customer) => (
                        <div
                          key={customer.id}
                          onClick={() => {
                            setSelectedCustomer(customer);
                            setCustomerSearch('');
                            setSearchResults([]);
                          }}
                          role="button"
                          tabIndex={0}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              setSelectedCustomer(customer);
                              setCustomerSearch('');
                              setSearchResults([]);
                            }
                          }}
                          style={{ cursor: 'pointer' }}
                        >
                          <Box padding="200" background="bg-surface-secondary" borderRadius="100">
                            <InlineStack align="space-between" blockAlign="center">
                              <BlockStack gap="050">
                                <InlineStack gap="200" blockAlign="center">
                                  <Text as="span" fontWeight="semibold">
                                    {customer.name || `${customer.firstName || ''} ${customer.lastName || ''}`.trim() || 'Unknown'}
                                  </Text>
                                  {customer.is_member && (
                                    <Badge tone="success" size="small">Member</Badge>
                                  )}
                                </InlineStack>
                                <Text as="span" variant="bodySm" tone="subdued">{customer.email}</Text>
                              </BlockStack>
                              <Text as="span" variant="bodySm">
                                {customer.numberOfOrders || customer.ordersCount || 0} orders
                              </Text>
                            </InlineStack>
                          </Box>
                        </div>
                      ))}
                      <Button variant="plain" onClick={() => setCreateNewMode(true)}>
                        Or create a new customer
                      </Button>
                    </BlockStack>
                  ) : debouncedCustomerSearch.length >= 2 && !searching ? (
                    <BlockStack gap="200">
                      <Text as="p" tone="subdued" alignment="center">
                        No customers found matching "{debouncedCustomerSearch}"
                      </Text>
                      <Button
                        onClick={() => {
                          setCreateNewMode(true);
                          if (customerSearch.includes('@')) setNewEmail(customerSearch);
                        }}
                        fullWidth
                      >
                        Create New Customer
                      </Button>
                    </BlockStack>
                  ) : (
                    <BlockStack gap="200">
                      <Text as="p" tone="subdued" alignment="center">
                        {searching ? 'Searching...' : 'Search for a Shopify customer or create a new one'}
                      </Text>
                      <Button variant="plain" onClick={() => setCreateNewMode(true)}>
                        Create new customer instead
                      </Button>
                    </BlockStack>
                  )}
                </BlockStack>
              )}
            </BlockStack>

            <Divider />

            {/* Amounts */}
            <TextField
              label="Total Trade-In Value"
              type="number"
              prefix="$"
              value={totalValue}
              onChange={setTotalValue}
              autoComplete="off"
              requiredIndicator
            />

            <InlineGrid columns={2} gap="300">
              <TextField
                label="Paid in Cash"
                type="number"
                prefix="$"
                value={cashAmount}
                onChange={setCashAmount}
                autoComplete="off"
              />
              <TextField
                label="Paid as Store Credit"
                type="number"
                prefix="$"
                value={creditAmount}
                onChange={setCreditAmount}
                autoComplete="off"
                helpText="Auto-calculated from total - cash"
              />
            </InlineGrid>

            <Divider />

            {/* Category */}
            <Select
              label="Category (Optional)"
              options={categoryOptions}
              value={category}
              onChange={setCategory}
            />

            {category === 'custom' && (
              <TextField
                label="Custom Category"
                value={customCategory}
                onChange={setCustomCategory}
                placeholder="e.g., Pokemon, Sports Cards"
                autoComplete="off"
              />
            )}

            {/* Notes */}
            <TextField
              label="Notes (Optional)"
              value={notes}
              onChange={setNotes}
              multiline={3}
              autoComplete="off"
            />
          </FormLayout>
        </Modal.Section>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        open={deleteModalOpen}
        onClose={() => {
          setDeleteModalOpen(false);
          setEntryToDelete(null);
        }}
        title="Delete Trade-In Entry"
        primaryAction={{
          content: 'Delete',
          destructive: true,
          onAction: () => entryToDelete && deleteMutation.mutate(entryToDelete.id),
          loading: deleteMutation.isPending,
        }}
        secondaryActions={[{
          content: 'Cancel',
          onAction: () => {
            setDeleteModalOpen(false);
            setEntryToDelete(null);
          },
        }]}
      >
        <Modal.Section>
          <Text as="p">
            Are you sure you want to delete trade-in <strong>{entryToDelete?.reference}</strong>?
            This action cannot be undone.
          </Text>
        </Modal.Section>
      </Modal>
    </>
  );
}
