/**
 * TradeUp Trade-In Ledger - Simplified Version
 *
 * Simple ledger for recording trade-in transactions.
 * No complex workflows - just records what was traded and how it was paid.
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
} from '@shopify/polaris';
import { PlusIcon, DeleteIcon, EditIcon } from '@shopify/polaris-icons';
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

interface Member {
  id: number;
  name: string;
  email: string;
  member_number: string;
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

async function fetchEntries(shop: string | null, page: number): Promise<{
  entries: TradeLedgerEntry[];
  total: number;
  page: number;
  pages: number;
}> {
  const response = await authFetch(
    `${getApiUrl()}/trade-ledger/?page=${page}&per_page=20`,
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

async function searchMembers(shop: string | null, query: string): Promise<{ members: Member[] }> {
  const response = await authFetch(
    `${getApiUrl()}/members/?search=${encodeURIComponent(query)}&limit=10`,
    shop
  );
  if (!response.ok) throw new Error('Failed to search members');
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
  const [modalOpen, setModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [entryToDelete, setEntryToDelete] = useState<TradeLedgerEntry | null>(null);

  // Form state
  const [customerType, setCustomerType] = useState<'member' | 'guest'>('guest');
  const [selectedMember, setSelectedMember] = useState<Member | null>(null);
  const [memberSearch, setMemberSearch] = useState('');
  const [memberResults, setMemberResults] = useState<Member[]>([]);
  const [guestName, setGuestName] = useState('');
  const [guestEmail, setGuestEmail] = useState('');
  const [guestPhone, setGuestPhone] = useState('');
  const [totalValue, setTotalValue] = useState('');
  const [cashAmount, setCashAmount] = useState('');
  const [creditAmount, setCreditAmount] = useState('');
  const [category, setCategory] = useState('');
  const [customCategory, setCustomCategory] = useState('');
  const [notes, setNotes] = useState('');

  // Fetch data
  const { data: entriesData, isLoading } = useQuery({
    queryKey: ['trade-ledger', shop, page],
    queryFn: () => fetchEntries(shop, page),
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

  // Member search
  useEffect(() => {
    if (memberSearch.length >= 2 && customerType === 'member') {
      searchMembers(shop, memberSearch).then((data) => {
        setMemberResults(data.members || []);
      });
    } else {
      setMemberResults([]);
    }
  }, [memberSearch, shop, customerType]);

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
    setCustomerType('guest');
    setSelectedMember(null);
    setMemberSearch('');
    setMemberResults([]);
    setGuestName('');
    setGuestEmail('');
    setGuestPhone('');
    setTotalValue('');
    setCashAmount('');
    setCreditAmount('');
    setCategory('');
    setCustomCategory('');
    setNotes('');
  }, []);

  const handleSubmit = useCallback(() => {
    const data: Record<string, unknown> = {
      total_value: parseFloat(totalValue) || 0,
      cash_amount: parseFloat(cashAmount) || 0,
      credit_amount: parseFloat(creditAmount) || 0,
      notes: notes || null,
    };

    if (customerType === 'member' && selectedMember) {
      data.member_id = selectedMember.id;
    } else {
      data.guest_name = guestName || null;
      data.guest_email = guestEmail || null;
      data.guest_phone = guestPhone || null;
    }

    // Handle category
    if (category === 'custom' && customCategory) {
      data.category = customCategory;
    } else if (category && category !== 'none') {
      // Check if it's a collection
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
  }, [customerType, selectedMember, guestName, guestEmail, guestPhone, totalValue, cashAmount, creditAmount, category, customCategory, notes, collectionsData, createMutation]);

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

          {/* Entries List */}
          <Layout.Section>
            <Card>
              {isLoading ? (
                <Box padding="800">
                  <InlineStack align="center">
                    <Text as="p">Loading...</Text>
                  </InlineStack>
                </Box>
              ) : entries.length === 0 ? (
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
          disabled: !totalValue || parseFloat(totalValue) <= 0,
        }}
        secondaryActions={[{ content: 'Cancel', onAction: closeModal }]}
      >
        <Modal.Section>
          <FormLayout>
            {/* Customer Type Selection */}
            <Select
              label="Customer Type"
              options={[
                { label: 'Guest (Walk-in)', value: 'guest' },
                { label: 'Member', value: 'member' },
              ]}
              value={customerType}
              onChange={(v) => setCustomerType(v as 'member' | 'guest')}
            />

            {customerType === 'member' ? (
              <BlockStack gap="200">
                <TextField
                  label="Search Member"
                  value={memberSearch}
                  onChange={setMemberSearch}
                  placeholder="Search by name or email..."
                  autoComplete="off"
                />
                {memberResults.length > 0 && (
                  <Card>
                    <BlockStack gap="100">
                      {memberResults.map((member) => (
                        <Box
                          key={member.id}
                          padding="200"
                          background={selectedMember?.id === member.id ? 'bg-surface-selected' : undefined}
                        >
                          <div
                            role="button"
                            tabIndex={0}
                            style={{ cursor: 'pointer' }}
                            onClick={() => {
                              setSelectedMember(member);
                              setMemberSearch(member.name || member.email);
                              setMemberResults([]);
                            }}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                setSelectedMember(member);
                                setMemberSearch(member.name || member.email);
                                setMemberResults([]);
                              }
                            }}
                          >
                            <BlockStack gap="050">
                              <Text as="span" fontWeight="semibold">{member.name || member.email}</Text>
                              <Text as="span" variant="bodySm" tone="subdued">{member.member_number}</Text>
                            </BlockStack>
                          </div>
                        </Box>
                      ))}
                    </BlockStack>
                  </Card>
                )}
                {selectedMember && (
                  <Banner tone="success">
                    Selected: {selectedMember.name || selectedMember.email} ({selectedMember.member_number})
                  </Banner>
                )}
              </BlockStack>
            ) : (
              <BlockStack gap="300">
                <TextField
                  label="Guest Name"
                  value={guestName}
                  onChange={setGuestName}
                  autoComplete="off"
                />
                <TextField
                  label="Guest Email"
                  type="email"
                  value={guestEmail}
                  onChange={setGuestEmail}
                  autoComplete="off"
                />
                <TextField
                  label="Guest Phone"
                  type="tel"
                  value={guestPhone}
                  onChange={setGuestPhone}
                  autoComplete="off"
                />
              </BlockStack>
            )}

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
