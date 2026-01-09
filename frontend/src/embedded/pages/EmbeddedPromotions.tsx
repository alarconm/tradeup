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
  Tag,
  Autocomplete,
  Icon,
  LegacyStack,
} from '@shopify/polaris';
import { PlusIcon, DeleteIcon, EditIcon, SearchIcon, PlayIcon, RefreshIcon } from '@shopify/polaris-icons';
import { useState, useCallback, useMemo, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';
import { useCollections, useVendors, useProductTypes, useTags } from '../../hooks/useShopifyData';

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
  active_days: string | null;  // "0,1,2,3,4" for Mon-Fri
  channel: 'all' | 'in_store' | 'online';
  category_ids: string[] | null;  // Legacy field
  // New Shopify filter fields
  collection_ids: string[] | null;
  vendor_filter: string[] | null;
  product_type_filter: string[] | null;
  product_tags_filter: string[] | null;
  tier_restriction: string[] | null;
  min_value: number;
  stackable: boolean;
  max_uses: number | null;
  current_uses: number;
  active: boolean;
  is_active_now: boolean;
  credit_expiration_days: number | null;
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

// Store Credit Events types
interface StoreCreditEventPreview {
  event_config: {
    start_datetime: string;
    end_datetime: string;
    sources: string[];
    credit_percent: number;
  };
  summary: {
    total_orders: number;
    unique_customers: number;
    total_order_value: number;
    total_credit_to_issue: number;
  };
  top_customers: Array<{
    customer_id: string;
    email: string;
    name: string;
    order_count: number;
    total_spent: number;
    credit_amount: number;
  }>;
  orders_by_source: Record<string, number>;
}

interface StoreCreditEventResult {
  job_id: string;
  success_count: number;
  failure_count: number;
  total_credit_issued: number;
  errors: string[];
}

interface OrderSource {
  name: string;
  count: number;
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

const DAY_OPTIONS = [
  { label: 'Monday', value: '0' },
  { label: 'Tuesday', value: '1' },
  { label: 'Wednesday', value: '2' },
  { label: 'Thursday', value: '3' },
  { label: 'Friday', value: '4' },
  { label: 'Saturday', value: '5' },
  { label: 'Sunday', value: '6' },
];

const CREDIT_EXPIRATION_OPTIONS = [
  { label: 'Never expires', value: '' },
  { label: '30 days', value: '30' },
  { label: '60 days', value: '60' },
  { label: '90 days', value: '90' },
  { label: '180 days', value: '180' },
  { label: '1 year (365 days)', value: '365' },
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

// Store Credit Events API functions
async function fetchEventSources(
  shop: string | null,
  startDatetime: string,
  endDatetime: string
): Promise<{ sources: OrderSource[]; total_orders: number }> {
  const params = new URLSearchParams({
    start_datetime: startDatetime,
    end_datetime: endDatetime,
  });
  const response = await authFetch(
    `${getApiUrl()}/store_credit_events/sources?${params}`,
    shop
  );
  if (!response.ok) throw new Error('Failed to fetch order sources');
  return response.json();
}

async function previewCreditEvent(
  shop: string | null,
  data: {
    start_datetime: string;
    end_datetime: string;
    sources: string[];
    credit_percent: number;
    include_authorized?: boolean;
  }
): Promise<StoreCreditEventPreview> {
  const response = await authFetch(
    `${getApiUrl()}/store_credit_events/preview`,
    shop,
    {
      method: 'POST',
      body: JSON.stringify(data),
    }
  );
  if (!response.ok) throw new Error('Failed to preview event');
  return response.json();
}

async function runCreditEvent(
  shop: string | null,
  data: {
    start_datetime: string;
    end_datetime: string;
    sources: string[];
    credit_percent: number;
    include_authorized?: boolean;
    expires_at?: string;
  }
): Promise<StoreCreditEventResult> {
  const response = await authFetch(
    `${getApiUrl()}/store_credit_events/run`,
    shop,
    {
      method: 'POST',
      body: JSON.stringify(data),
    }
  );
  if (!response.ok) throw new Error('Failed to run event');
  return response.json();
}

async function fetchEventTemplates(shop: string | null): Promise<{
  templates: Array<{
    id: string;
    name: string;
    description: string;
    default_sources: string[];
    default_credit_percent: number;
    duration_hours: number;
  }>;
}> {
  const response = await authFetch(`${getApiUrl()}/store_credit_events/templates`, shop);
  if (!response.ok) throw new Error('Failed to fetch templates');
  return response.json();
}

export function EmbeddedPromotions({ shop }: PromotionsProps) {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [editingPromo, setEditingPromo] = useState<Promotion | null>(null);
  const [promoToDelete, setPromoToDelete] = useState<Promotion | null>(null);
  const [activeTab, setActiveTab] = useState<'promotions' | 'tiers' | 'events'>('promotions');
  const isMobile = useIsMobile();

  // Store Credit Events state
  const [eventModalOpen, setEventModalOpen] = useState(false);
  const [eventPreview, setEventPreview] = useState<StoreCreditEventPreview | null>(null);
  const [eventResult, setEventResult] = useState<StoreCreditEventResult | null>(null);
  const [eventForm, setEventForm] = useState({
    start_datetime: '',
    end_datetime: '',
    sources: [] as string[],
    credit_percent: 10,
    include_authorized: true,
    credit_expiration_days: '',
  });
  const [availableSources, setAvailableSources] = useState<OrderSource[]>([]);

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
    daily_start_time: '',
    daily_end_time: '',
    active_days: [] as string[],
    channel: 'all' as Promotion['channel'],
    // Shopify filter fields
    collection_ids: [] as string[],
    vendor_filter: [] as string[],
    product_type_filter: [] as string[],
    product_tags_filter: [] as string[],
    tier_restriction: [] as string[],
    min_value: '',
    stackable: true,
    max_uses: '',
    active: true,
    credit_expiration_days: '',
  });

  // Search input states for autocomplete pickers
  const [collectionSearch, setCollectionSearch] = useState('');
  const [vendorSearch, setVendorSearch] = useState('');
  const [productTypeSearch, setProductTypeSearch] = useState('');
  const [tagSearch, setTagSearch] = useState('');

  // Fetch Shopify data for pickers
  const { data: collectionsData } = useCollections(shop);
  const { data: vendorsData } = useVendors(shop);
  const { data: productTypesData } = useProductTypes(shop);
  const { data: tagsData } = useTags(shop);

  // Memoized options for autocomplete pickers
  const collectionOptions = useMemo(() => {
    if (!collectionsData?.collections) return [];
    const filtered = collectionSearch
      ? collectionsData.collections.filter(c =>
          c.title.toLowerCase().includes(collectionSearch.toLowerCase())
        )
      : collectionsData.collections;
    return filtered.map(c => ({ value: c.id, label: c.title }));
  }, [collectionsData, collectionSearch]);

  const vendorOptions = useMemo(() => {
    if (!vendorsData?.vendors) return [];
    const filtered = vendorSearch
      ? vendorsData.vendors.filter(v =>
          v.toLowerCase().includes(vendorSearch.toLowerCase())
        )
      : vendorsData.vendors;
    return filtered.map(v => ({ value: v, label: v }));
  }, [vendorsData, vendorSearch]);

  const productTypeOptions = useMemo(() => {
    if (!productTypesData?.product_types) return [];
    const filtered = productTypeSearch
      ? productTypesData.product_types.filter(pt =>
          pt.toLowerCase().includes(productTypeSearch.toLowerCase())
        )
      : productTypesData.product_types;
    return filtered.map(pt => ({ value: pt, label: pt }));
  }, [productTypesData, productTypeSearch]);

  const tagOptions = useMemo(() => {
    if (!tagsData?.tags) return [];
    const filtered = tagSearch
      ? tagsData.tags.filter(t =>
          t.toLowerCase().includes(tagSearch.toLowerCase())
        )
      : tagsData.tags;
    return filtered.map(t => ({ value: t, label: t }));
  }, [tagsData, tagSearch]);

  const { data: promotionsData, isLoading: promotionsLoading, error: promotionsError } = useQuery({
    queryKey: ['promotions', shop],
    queryFn: () => fetchPromotions(shop),
    enabled: !!shop,
    staleTime: 30000, // Cache for 30s
    gcTime: 60000, // Keep in cache for 60s
    retry: 1, // Only retry once to fail faster
  });

  const { data: tiersData, isLoading: tiersLoading } = useQuery({
    queryKey: ['tiers', shop],
    queryFn: () => fetchTiers(shop),
    enabled: !!shop,
    staleTime: 60000, // Tiers change less often - cache for 60s
    gcTime: 120000,
    retry: 1,
  });

  const { data: stats } = useQuery({
    queryKey: ['promotions-stats', shop],
    queryFn: () => fetchStats(shop),
    enabled: !!shop,
    staleTime: 30000,
    gcTime: 60000,
    retry: 1,
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

  // Store Credit Events mutations
  const previewEventMutation = useMutation({
    mutationFn: () =>
      previewCreditEvent(shop, {
        start_datetime: eventForm.start_datetime,
        end_datetime: eventForm.end_datetime,
        sources: eventForm.sources,
        credit_percent: eventForm.credit_percent,
        include_authorized: eventForm.include_authorized,
      }),
    onSuccess: (data) => {
      setEventPreview(data);
      setEventResult(null);
    },
  });

  const runEventMutation = useMutation({
    mutationFn: () =>
      runCreditEvent(shop, {
        start_datetime: eventForm.start_datetime,
        end_datetime: eventForm.end_datetime,
        sources: eventForm.sources,
        credit_percent: eventForm.credit_percent,
        include_authorized: eventForm.include_authorized,
        expires_at: eventForm.credit_expiration_days
          ? new Date(Date.now() + parseInt(eventForm.credit_expiration_days) * 24 * 60 * 60 * 1000).toISOString()
          : undefined,
      }),
    onSuccess: (data) => {
      setEventResult(data);
      setEventPreview(null);
      queryClient.invalidateQueries({ queryKey: ['promotions-stats'] });
    },
  });

  // Fetch available order sources when dates change
  const fetchSourcesMutation = useMutation({
    mutationFn: () =>
      fetchEventSources(shop, eventForm.start_datetime, eventForm.end_datetime),
    onSuccess: (data) => {
      setAvailableSources(data.sources);
    },
  });

  // Reset event form
  const resetEventForm = useCallback(() => {
    setEventForm({
      start_datetime: '',
      end_datetime: '',
      sources: [],
      credit_percent: 10,
      include_authorized: true,
      credit_expiration_days: '',
    });
    setEventPreview(null);
    setEventResult(null);
    setAvailableSources([]);
  }, []);

  // Open event modal with preset times (e.g., for Trade Night)
  const openEventModal = useCallback((templateHours?: number) => {
    const now = new Date();
    const endTime = templateHours
      ? new Date(now.getTime() + templateHours * 60 * 60 * 1000)
      : new Date(now.getTime() + 3 * 60 * 60 * 1000); // Default 3 hours

    setEventForm({
      start_datetime: now.toISOString().slice(0, 16),
      end_datetime: endTime.toISOString().slice(0, 16),
      sources: [],
      credit_percent: 10,
      include_authorized: true,
      credit_expiration_days: '',
    });
    setEventPreview(null);
    setEventResult(null);
    setAvailableSources([]);
    setEventModalOpen(true);
  }, []);

  // Handle date change - fetch available sources
  const handleEventDateChange = useCallback(
    (field: 'start_datetime' | 'end_datetime', value: string) => {
      const newForm = { ...eventForm, [field]: value };
      setEventForm(newForm);

      // If both dates are set, fetch available sources
      if (newForm.start_datetime && newForm.end_datetime) {
        fetchSourcesMutation.mutate();
      }
    },
    [eventForm, fetchSourcesMutation]
  );

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
      daily_start_time: '',
      daily_end_time: '',
      active_days: [],
      channel: 'all',
      collection_ids: [],
      vendor_filter: [],
      product_type_filter: [],
      product_tags_filter: [],
      tier_restriction: [],
      min_value: '',
      stackable: true,
      max_uses: '',
      active: true,
      credit_expiration_days: '',
    });
    // Reset search states
    setCollectionSearch('');
    setVendorSearch('');
    setProductTypeSearch('');
    setTagSearch('');
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
      daily_start_time: promo.daily_start_time || '',
      daily_end_time: promo.daily_end_time || '',
      active_days: promo.active_days ? promo.active_days.split(',') : [],
      channel: promo.channel,
      collection_ids: promo.collection_ids || [],
      vendor_filter: promo.vendor_filter || [],
      product_type_filter: promo.product_type_filter || [],
      product_tags_filter: promo.product_tags_filter || promo.category_ids || [],
      tier_restriction: promo.tier_restriction || [],
      min_value: promo.min_value?.toString() || '',
      stackable: promo.stackable,
      max_uses: promo.max_uses?.toString() || '',
      active: promo.active,
      credit_expiration_days: promo.credit_expiration_days?.toString() || '',
    });
    // Reset search states
    setCollectionSearch('');
    setVendorSearch('');
    setProductTypeSearch('');
    setTagSearch('');
    setModalOpen(true);
  }, []);

  const confirmDelete = useCallback((promo: Promotion) => {
    setPromoToDelete(promo);
    setDeleteModalOpen(true);
  }, []);

  const handleSubmit = useCallback(() => {
    const data = {
      name: formData.name,
      description: formData.description || null,
      code: formData.code || null,
      promo_type: formData.promo_type,
      bonus_percent: formData.bonus_percent,
      bonus_flat: formData.bonus_flat,
      multiplier: formData.multiplier,
      starts_at: formData.starts_at,
      ends_at: formData.ends_at,
      channel: formData.channel,
      stackable: formData.stackable,
      active: formData.active,
      // Convert active_days array to comma-separated string
      active_days: formData.active_days.length > 0 ? formData.active_days.join(',') : null,
      // Time-based scheduling
      daily_start_time: formData.daily_start_time || null,
      daily_end_time: formData.daily_end_time || null,
      // Shopify filter fields
      collection_ids: formData.collection_ids.length > 0 ? formData.collection_ids : null,
      vendor_filter: formData.vendor_filter.length > 0 ? formData.vendor_filter : null,
      product_type_filter: formData.product_type_filter.length > 0 ? formData.product_type_filter : null,
      product_tags_filter: formData.product_tags_filter.length > 0 ? formData.product_tags_filter : null,
      tier_restriction: formData.tier_restriction.length > 0 ? formData.tier_restriction : null,
      // Numeric fields
      min_value: formData.min_value ? parseFloat(formData.min_value) : 0,
      max_uses: formData.max_uses ? parseInt(formData.max_uses) : null,
      credit_expiration_days: formData.credit_expiration_days ? parseInt(formData.credit_expiration_days) : null,
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
      <Page
        title="Promotions & Bonuses"
        subtitle="Loading your promotions..."
      >
        <Layout>
          {/* Stats skeleton */}
          <Layout.Section>
            <InlineGrid columns={isMobile ? 2 : 4} gap="400">
              {[1, 2, 3, 4].map((i) => (
                <Card key={i}>
                  <BlockStack gap="200">
                    <Box background="bg-surface-secondary" borderRadius="100" minHeight="16px" maxWidth="80px" />
                    <Box background="bg-surface-secondary" borderRadius="100" minHeight="32px" maxWidth="60px" />
                  </BlockStack>
                </Card>
              ))}
            </InlineGrid>
          </Layout.Section>

          {/* Tab skeleton */}
          <Layout.Section>
            <InlineStack gap="200">
              <Box background="bg-surface-secondary" borderRadius="200" minHeight="32px" minWidth="120px" />
              <Box background="bg-surface-secondary" borderRadius="200" minHeight="32px" minWidth="120px" />
            </InlineStack>
          </Layout.Section>

          {/* Table skeleton */}
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                {[1, 2, 3].map((i) => (
                  <Box key={i} paddingBlock="300">
                    <InlineStack gap="400" blockAlign="center">
                      <Box background="bg-surface-secondary" borderRadius="100" minHeight="20px" minWidth="150px" />
                      <Box background="bg-surface-secondary" borderRadius="100" minHeight="20px" minWidth="100px" />
                      <Box background="bg-surface-secondary" borderRadius="100" minHeight="20px" minWidth="80px" />
                      <Box background="bg-surface-secondary" borderRadius="100" minHeight="20px" minWidth="60px" />
                    </InlineStack>
                  </Box>
                ))}
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
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
          <InlineGrid columns={isMobile ? 2 : 4} gap="400">
            <Card>
              <BlockStack gap="200">
                <Text as="h3" variant="headingSm" tone="subdued">Active Promos</Text>
                <Text as="p" variant={isMobile ? "headingLg" : "headingXl"}>{stats?.active_promotions || 0}</Text>
              </BlockStack>
            </Card>
            <Card>
              <BlockStack gap="200">
                <Text as="h3" variant="headingSm" tone="subdued">Ending Soon</Text>
                <Text as="p" variant={isMobile ? "headingLg" : "headingXl"}>{stats?.promotions_ending_soon || 0}</Text>
              </BlockStack>
            </Card>
            <Card>
              <BlockStack gap="200">
                <Text as="h3" variant="headingSm" tone="subdued">Cashback (30d)</Text>
                <Text as="p" variant={isMobile ? "headingLg" : "headingXl"}>{formatCurrency(stats?.total_cashback_30d || 0)}</Text>
              </BlockStack>
            </Card>
            <Card>
              <BlockStack gap="200">
                <Text as="h3" variant="headingSm" tone="subdued">Bulk Credits (30d)</Text>
                <Text as="p" variant={isMobile ? "headingLg" : "headingXl"}>{formatCurrency(stats?.total_bulk_credits_30d || 0)}</Text>
              </BlockStack>
            </Card>
          </InlineGrid>
        </Layout.Section>

        {/* Tab Navigation */}
        <Layout.Section>
          <InlineStack gap="200" wrap>
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
            <Button
              pressed={activeTab === 'events'}
              onClick={() => setActiveTab('events')}
            >
              Store Credit Events
            </Button>
          </InlineStack>
        </Layout.Section>

        {/* Promotions List */}
        {activeTab === 'promotions' && (
          <Layout.Section>
            <Card>
              {promotions.length > 0 ? (
                isMobile ? (
                  /* Mobile: Card-based layout */
                  <Box padding="300">
                    <BlockStack gap="300">
                      {promotions.map((promo, index) => (
                        <Box key={promo.id}>
                          {index > 0 && <Divider />}
                          <Box paddingBlock="300">
                            <BlockStack gap="200">
                              <InlineStack align="space-between" blockAlign="start">
                                <BlockStack gap="100">
                                  <Text as="span" fontWeight="semibold">{promo.name}</Text>
                                  {promo.code && <Badge size="small">{promo.code}</Badge>}
                                </BlockStack>
                                {getStatusBadge(promo)}
                              </InlineStack>
                              <InlineStack gap="200" wrap>
                                <Badge tone="info">
                                  {PROMO_TYPE_OPTIONS.find(o => o.value === promo.promo_type)?.label || promo.promo_type}
                                </Badge>
                                <Text as="span" variant="bodySm" fontWeight="medium">
                                  {getPromoValue(promo)}
                                </Text>
                              </InlineStack>
                              <Text as="span" variant="bodySm" tone="subdued">
                                {new Date(promo.starts_at).toLocaleDateString()} - {new Date(promo.ends_at).toLocaleDateString()}
                              </Text>
                              <InlineStack gap="200">
                                <Button
                                  size="slim"
                                  icon={EditIcon}
                                  onClick={() => openEditModal(promo)}
                                  accessibilityLabel={`Edit ${promo.name}`}
                                >
                                  Edit
                                </Button>
                                <Button
                                  size="slim"
                                  icon={DeleteIcon}
                                  tone="critical"
                                  onClick={() => confirmDelete(promo)}
                                  accessibilityLabel={`Delete ${promo.name}`}
                                >
                                  Delete
                                </Button>
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
                )
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
            <InlineGrid columns={isMobile ? 1 : 3} gap="400">
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

        {/* Store Credit Events */}
        {activeTab === 'events' && (
          <Layout.Section>
            <BlockStack gap="400">
              {/* Event Templates */}
              <Card>
                <BlockStack gap="400">
                  <InlineStack align="space-between" blockAlign="center">
                    <BlockStack gap="100">
                      <Text as="h3" variant="headingMd">Quick Start Templates</Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Use a template or create a custom event
                      </Text>
                    </BlockStack>
                    <Button
                      icon={PlusIcon}
                      variant="primary"
                      onClick={() => openEventModal()}
                    >
                      Custom Event
                    </Button>
                  </InlineStack>

                  <InlineGrid columns={isMobile ? 1 : 3} gap="300">
                    <Card>
                      <BlockStack gap="200">
                        <Text as="h4" variant="headingSm">Trade Night</Text>
                        <Text as="p" variant="bodySm" tone="subdued">
                          10% store credit on all purchases during Trade Night hours
                        </Text>
                        <Text as="p" variant="bodySm">Duration: 3 hours</Text>
                        <Button
                          size="slim"
                          onClick={() => {
                            openEventModal(3);
                            setEventForm(prev => ({ ...prev, credit_percent: 10 }));
                          }}
                        >
                          Use Template
                        </Button>
                      </BlockStack>
                    </Card>
                    <Card>
                      <BlockStack gap="200">
                        <Text as="h4" variant="headingSm">Grand Opening</Text>
                        <Text as="p" variant="bodySm" tone="subdued">
                          15% store credit on opening day purchases
                        </Text>
                        <Text as="p" variant="bodySm">Duration: 24 hours</Text>
                        <Button
                          size="slim"
                          onClick={() => {
                            openEventModal(24);
                            setEventForm(prev => ({ ...prev, credit_percent: 15 }));
                          }}
                        >
                          Use Template
                        </Button>
                      </BlockStack>
                    </Card>
                    <Card>
                      <BlockStack gap="200">
                        <Text as="h4" variant="headingSm">Weekend Sale</Text>
                        <Text as="p" variant="bodySm" tone="subdued">
                          5% store credit on weekend purchases
                        </Text>
                        <Text as="p" variant="bodySm">Duration: 48 hours</Text>
                        <Button
                          size="slim"
                          onClick={() => {
                            openEventModal(48);
                            setEventForm(prev => ({ ...prev, credit_percent: 5 }));
                          }}
                        >
                          Use Template
                        </Button>
                      </BlockStack>
                    </Card>
                  </InlineGrid>
                </BlockStack>
              </Card>

              {/* How It Works */}
              <Card>
                <BlockStack gap="300">
                  <Text as="h3" variant="headingMd">How Store Credit Events Work</Text>
                  <BlockStack gap="200">
                    <InlineStack gap="200" blockAlign="start">
                      <Badge tone="info">1</Badge>
                      <Text as="p" variant="bodySm">
                        <strong>Set Date Range:</strong> Choose the start and end time for your event
                      </Text>
                    </InlineStack>
                    <InlineStack gap="200" blockAlign="start">
                      <Badge tone="info">2</Badge>
                      <Text as="p" variant="bodySm">
                        <strong>Select Sources:</strong> Choose which order sources (POS, Web, etc.) to include
                      </Text>
                    </InlineStack>
                    <InlineStack gap="200" blockAlign="start">
                      <Badge tone="info">3</Badge>
                      <Text as="p" variant="bodySm">
                        <strong>Preview (Dry Run):</strong> See exactly how much credit will be issued before applying
                      </Text>
                    </InlineStack>
                    <InlineStack gap="200" blockAlign="start">
                      <Badge tone="success">4</Badge>
                      <Text as="p" variant="bodySm">
                        <strong>Run Event:</strong> Apply store credit to all qualifying customers
                      </Text>
                    </InlineStack>
                  </BlockStack>
                </BlockStack>
              </Card>
            </BlockStack>
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

            <Divider />
            <Text as="h3" variant="headingSm">Advanced Scheduling</Text>

            <FormLayout.Group>
              <TextField
                label="Daily Start Time"
                type="time"
                value={formData.daily_start_time}
                onChange={(value) => setFormData({ ...formData, daily_start_time: value })}
                autoComplete="off"
                helpText="e.g., 18:00 for 6 PM"
              />
              <TextField
                label="Daily End Time"
                type="time"
                value={formData.daily_end_time}
                onChange={(value) => setFormData({ ...formData, daily_end_time: value })}
                autoComplete="off"
                helpText="e.g., 21:00 for 9 PM"
              />
            </FormLayout.Group>

            <ChoiceList
              title="Active Days (optional)"
              choices={DAY_OPTIONS}
              selected={formData.active_days}
              onChange={(value) => setFormData({ ...formData, active_days: value })}
              allowMultiple
            />

            <Divider />
            <Text as="h3" variant="headingSm">Product Eligibility Filters</Text>
            <Text as="p" variant="bodySm" tone="subdued">
              Leave empty to apply to all products. Multiple selections use AND logic.
            </Text>

            {/* Collections Picker */}
            <BlockStack gap="200">
              <Autocomplete
                options={collectionOptions}
                selected={formData.collection_ids}
                onSelect={(selected) => setFormData({ ...formData, collection_ids: selected })}
                textField={
                  <Autocomplete.TextField
                    label="Collections"
                    value={collectionSearch}
                    onChange={setCollectionSearch}
                    placeholder="Search collections..."
                    prefix={<Icon source={SearchIcon} />}
                    autoComplete="off"
                  />
                }
                allowMultiple
              />
              {formData.collection_ids.length > 0 && (
                <InlineStack gap="100" wrap>
                  {formData.collection_ids.map(id => {
                    const collection = collectionsData?.collections.find(c => c.id === id);
                    return (
                      <Tag
                        key={id}
                        onRemove={() =>
                          setFormData({
                            ...formData,
                            collection_ids: formData.collection_ids.filter(c => c !== id),
                          })
                        }
                      >
                        {collection?.title || id}
                      </Tag>
                    );
                  })}
                </InlineStack>
              )}
            </BlockStack>

            {/* Vendors Picker */}
            <BlockStack gap="200">
              <Autocomplete
                options={vendorOptions}
                selected={formData.vendor_filter}
                onSelect={(selected) => setFormData({ ...formData, vendor_filter: selected })}
                textField={
                  <Autocomplete.TextField
                    label="Vendors/Brands"
                    value={vendorSearch}
                    onChange={setVendorSearch}
                    placeholder="Search vendors..."
                    prefix={<Icon source={SearchIcon} />}
                    autoComplete="off"
                  />
                }
                allowMultiple
              />
              {formData.vendor_filter.length > 0 && (
                <InlineStack gap="100" wrap>
                  {formData.vendor_filter.map(v => (
                    <Tag
                      key={v}
                      onRemove={() =>
                        setFormData({
                          ...formData,
                          vendor_filter: formData.vendor_filter.filter(x => x !== v),
                        })
                      }
                    >
                      {v}
                    </Tag>
                  ))}
                </InlineStack>
              )}
            </BlockStack>

            {/* Product Types Picker */}
            <BlockStack gap="200">
              <Autocomplete
                options={productTypeOptions}
                selected={formData.product_type_filter}
                onSelect={(selected) => setFormData({ ...formData, product_type_filter: selected })}
                textField={
                  <Autocomplete.TextField
                    label="Product Types"
                    value={productTypeSearch}
                    onChange={setProductTypeSearch}
                    placeholder="Search product types..."
                    prefix={<Icon source={SearchIcon} />}
                    autoComplete="off"
                  />
                }
                allowMultiple
              />
              {formData.product_type_filter.length > 0 && (
                <InlineStack gap="100" wrap>
                  {formData.product_type_filter.map(pt => (
                    <Tag
                      key={pt}
                      onRemove={() =>
                        setFormData({
                          ...formData,
                          product_type_filter: formData.product_type_filter.filter(x => x !== pt),
                        })
                      }
                    >
                      {pt}
                    </Tag>
                  ))}
                </InlineStack>
              )}
            </BlockStack>

            {/* Product Tags Picker */}
            <BlockStack gap="200">
              <Autocomplete
                options={tagOptions}
                selected={formData.product_tags_filter}
                onSelect={(selected) => setFormData({ ...formData, product_tags_filter: selected })}
                textField={
                  <Autocomplete.TextField
                    label="Product Tags"
                    value={tagSearch}
                    onChange={setTagSearch}
                    placeholder="Search tags..."
                    prefix={<Icon source={SearchIcon} />}
                    autoComplete="off"
                  />
                }
                allowMultiple
              />
              {formData.product_tags_filter.length > 0 && (
                <InlineStack gap="100" wrap>
                  {formData.product_tags_filter.map(t => (
                    <Tag
                      key={t}
                      onRemove={() =>
                        setFormData({
                          ...formData,
                          product_tags_filter: formData.product_tags_filter.filter(x => x !== t),
                        })
                      }
                    >
                      {t}
                    </Tag>
                  ))}
                </InlineStack>
              )}
            </BlockStack>

            <Divider />
            <Text as="h3" variant="headingSm">Additional Restrictions</Text>

            <Select
              label="Channel"
              options={CHANNEL_OPTIONS}
              value={formData.channel}
              onChange={(value) => setFormData({ ...formData, channel: value as Promotion['channel'] })}
            />

            {tiersData?.tiers && tiersData.tiers.length > 0 && (
              <ChoiceList
                title="Tier Restriction (optional)"
                choices={tiersData.tiers
                  .filter(tier => tier.tier_name)
                  .map(tier => ({
                    label: tier.tier_name,
                    value: tier.tier_name.toUpperCase(),
                  }))}
                selected={formData.tier_restriction}
                onChange={(value) => setFormData({ ...formData, tier_restriction: value })}
                allowMultiple
              />
            )}

            <FormLayout.Group>
              <TextField
                label="Min Order Value"
                type="number"
                value={formData.min_value}
                onChange={(value) => setFormData({ ...formData, min_value: value })}
                prefix="$"
                autoComplete="off"
                helpText="Minimum order to apply promo"
              />
              <TextField
                label="Max Uses (optional)"
                type="number"
                value={formData.max_uses}
                onChange={(value) => setFormData({ ...formData, max_uses: value })}
                autoComplete="off"
                helpText="Total uses allowed"
              />
            </FormLayout.Group>

            <Divider />
            <Text as="h3" variant="headingSm">Credit Settings</Text>

            <Select
              label="Credit Expiration"
              options={CREDIT_EXPIRATION_OPTIONS}
              value={formData.credit_expiration_days}
              onChange={(value) => setFormData({ ...formData, credit_expiration_days: value })}
              helpText="How long before credits from this promotion expire"
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

      {/* Store Credit Event Modal */}
      <Modal
        open={eventModalOpen}
        onClose={() => {
          setEventModalOpen(false);
          resetEventForm();
        }}
        title="Create Store Credit Event"
        size="large"
        primaryAction={
          eventPreview && !eventResult
            ? {
                content: 'Apply Credits',
                icon: PlayIcon,
                onAction: () => runEventMutation.mutate(),
                loading: runEventMutation.isPending,
              }
            : eventResult
            ? {
                content: 'Done',
                onAction: () => {
                  setEventModalOpen(false);
                  resetEventForm();
                },
              }
            : {
                content: 'Preview (Dry Run)',
                icon: RefreshIcon,
                onAction: () => previewEventMutation.mutate(),
                loading: previewEventMutation.isPending,
                disabled: !eventForm.start_datetime || !eventForm.end_datetime || eventForm.sources.length === 0,
              }
        }
        secondaryActions={
          eventResult
            ? []
            : [
                {
                  content: 'Cancel',
                  onAction: () => {
                    setEventModalOpen(false);
                    resetEventForm();
                  },
                },
              ]
        }
      >
        <Modal.Section>
          {eventResult ? (
            /* Event Result */
            <BlockStack gap="400">
              <Banner
                title={eventResult.success_count > 0 ? 'Event Completed Successfully!' : 'Event Completed'}
                tone={eventResult.failure_count > 0 ? 'warning' : 'success'}
              >
                <p>
                  Issued {formatCurrency(eventResult.total_credit_issued)} in store credit to {eventResult.success_count} customers.
                  {eventResult.failure_count > 0 && ` ${eventResult.failure_count} failed.`}
                </p>
              </Banner>

              {eventResult.errors && eventResult.errors.length > 0 && (
                <Card>
                  <BlockStack gap="200">
                    <Text as="h4" variant="headingSm" tone="critical">Errors</Text>
                    {eventResult.errors.map((error, i) => (
                      <Text as="p" variant="bodySm" key={i}>{error}</Text>
                    ))}
                  </BlockStack>
                </Card>
              )}
            </BlockStack>
          ) : eventPreview ? (
            /* Event Preview (Dry Run Results) */
            <BlockStack gap="400">
              <Banner title="Preview Results" tone="info">
                <p>
                  This is a dry run. No credits have been issued yet. Review the data below and click "Apply Credits" to proceed.
                </p>
              </Banner>

              {/* Summary Stats */}
              <InlineGrid columns={isMobile ? 2 : 4} gap="300">
                <Card>
                  <BlockStack gap="100">
                    <Text as="span" variant="bodySm" tone="subdued">Total Orders</Text>
                    <Text as="p" variant="headingLg">{eventPreview.summary.total_orders}</Text>
                  </BlockStack>
                </Card>
                <Card>
                  <BlockStack gap="100">
                    <Text as="span" variant="bodySm" tone="subdued">Unique Customers</Text>
                    <Text as="p" variant="headingLg">{eventPreview.summary.unique_customers}</Text>
                  </BlockStack>
                </Card>
                <Card>
                  <BlockStack gap="100">
                    <Text as="span" variant="bodySm" tone="subdued">Total Order Value</Text>
                    <Text as="p" variant="headingLg">{formatCurrency(eventPreview.summary.total_order_value)}</Text>
                  </BlockStack>
                </Card>
                <Card>
                  <BlockStack gap="100">
                    <Text as="span" variant="bodySm" tone="subdued">Credit to Issue</Text>
                    <Text as="p" variant="headingLg" tone="success">
                      {formatCurrency(eventPreview.summary.total_credit_to_issue)}
                    </Text>
                  </BlockStack>
                </Card>
              </InlineGrid>

              {/* Top Customers */}
              {eventPreview.top_customers && eventPreview.top_customers.length > 0 && (
                <Card>
                  <BlockStack gap="300">
                    <Text as="h4" variant="headingSm">Top Customers by Credit Amount</Text>
                    <DataTable
                      columnContentTypes={['text', 'text', 'numeric', 'numeric', 'numeric']}
                      headings={['Customer', 'Email', 'Orders', 'Spent', 'Credit']}
                      rows={eventPreview.top_customers.slice(0, 10).map((customer) => [
                        customer.name || 'Guest',
                        customer.email || '-',
                        customer.order_count,
                        formatCurrency(customer.total_spent),
                        <Badge key={customer.customer_id} tone="success">
                          {formatCurrency(customer.credit_amount)}
                        </Badge>,
                      ])}
                    />
                  </BlockStack>
                </Card>
              )}

              {/* Orders by Source */}
              {eventPreview.orders_by_source && Object.keys(eventPreview.orders_by_source).length > 0 && (
                <Card>
                  <BlockStack gap="200">
                    <Text as="h4" variant="headingSm">Orders by Source</Text>
                    <InlineStack gap="200" wrap>
                      {Object.entries(eventPreview.orders_by_source).map(([source, count]) => (
                        <Badge key={source} tone="info">
                          {`${source}: ${count}`}
                        </Badge>
                      ))}
                    </InlineStack>
                  </BlockStack>
                </Card>
              )}

              <Button
                onClick={() => setEventPreview(null)}
                variant="plain"
              >
                ← Back to Edit
              </Button>
            </BlockStack>
          ) : (
            /* Event Configuration Form */
            <FormLayout>
              <Banner tone="info">
                <p>
                  Set up your store credit event. After configuring, click "Preview (Dry Run)" to see exactly how much credit will be issued before applying.
                </p>
              </Banner>

              <FormLayout.Group>
                <TextField
                  label="Start Date & Time"
                  type="datetime-local"
                  value={eventForm.start_datetime}
                  onChange={(value) => handleEventDateChange('start_datetime', value)}
                  autoComplete="off"
                  requiredIndicator
                  helpText="When should orders start qualifying?"
                />
                <TextField
                  label="End Date & Time"
                  type="datetime-local"
                  value={eventForm.end_datetime}
                  onChange={(value) => handleEventDateChange('end_datetime', value)}
                  autoComplete="off"
                  requiredIndicator
                  helpText="When should orders stop qualifying?"
                />
              </FormLayout.Group>

              <TextField
                label="Credit Percentage"
                type="number"
                value={eventForm.credit_percent.toString()}
                onChange={(value) => setEventForm({ ...eventForm, credit_percent: parseFloat(value) || 0 })}
                suffix="%"
                autoComplete="off"
                helpText="Percentage of order total to issue as store credit"
              />

              {/* Order Sources Selection */}
              <BlockStack gap="200">
                <Text as="span" variant="bodyMd">
                  Order Sources <Text as="span" tone="critical">*</Text>
                </Text>
                {fetchSourcesMutation.isPending ? (
                  <InlineStack gap="200" blockAlign="center">
                    <Spinner size="small" />
                    <Text as="span" variant="bodySm" tone="subdued">Loading available sources...</Text>
                  </InlineStack>
                ) : availableSources.length > 0 ? (
                  <ChoiceList
                    title=""
                    choices={availableSources.map((source) => ({
                      label: `${source.name} (${source.count} orders)`,
                      value: source.name,
                    }))}
                    selected={eventForm.sources}
                    onChange={(selected) => setEventForm({ ...eventForm, sources: selected })}
                    allowMultiple
                  />
                ) : eventForm.start_datetime && eventForm.end_datetime ? (
                  <Banner tone="warning">
                    <p>No orders found in this date range. Try adjusting the dates.</p>
                  </Banner>
                ) : (
                  <Text as="p" variant="bodySm" tone="subdued">
                    Select start and end dates to see available order sources.
                  </Text>
                )}
              </BlockStack>

              <Divider />

              <Select
                label="Credit Expiration"
                options={CREDIT_EXPIRATION_OPTIONS}
                value={eventForm.credit_expiration_days}
                onChange={(value) => setEventForm({ ...eventForm, credit_expiration_days: value })}
                helpText="How long before issued credits expire"
              />

              <Checkbox
                label="Include authorized (unpaid) orders"
                checked={eventForm.include_authorized}
                onChange={(checked) => setEventForm({ ...eventForm, include_authorized: checked })}
                helpText="Include orders that are authorized but not yet captured"
              />

              {previewEventMutation.isError && (
                <Banner tone="critical">
                  <p>Failed to preview event. Please check your configuration and try again.</p>
                </Banner>
              )}
            </FormLayout>
          )}
        </Modal.Section>
      </Modal>
    </Page>
  );
}
