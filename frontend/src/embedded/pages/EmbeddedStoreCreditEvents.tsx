/**
 * Store Credit Events - Dedicated Page
 *
 * Prominent feature for scheduling store credit bonus events:
 * - Scheduled future promotions (e.g., "Black Friday +10%")
 * - Time-based recurring bonuses (e.g., "Saturday 6-9pm Trade Night")
 * - Retroactive bulk credit events
 *
 * Moved from EmbeddedPromotions tab to its own menu item for visibility.
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
  Tabs,
} from '@shopify/polaris';
import { PlusIcon, CalendarIcon, ClockIcon, PlayIcon, RefreshIcon, DeleteIcon, EditIcon, SearchIcon } from '@shopify/polaris-icons';
import { TitleBar } from '@shopify/app-bridge-react';
import { useState, useCallback, useMemo, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';
import { useTags, useCollections } from '../../hooks/useShopifyData';

// Hook to detect viewport size with tablet support
function useResponsive() {
  const [screenSize, setScreenSize] = useState(() => {
    if (typeof window === 'undefined') return { isMobile: false, isTablet: false };
    const width = window.innerWidth;
    return {
      isMobile: width < 768,
      isTablet: width >= 768 && width < 1024,
    };
  });

  useEffect(() => {
    const checkSize = () => {
      const width = window.innerWidth;
      setScreenSize({
        isMobile: width < 768,
        isTablet: width >= 768 && width < 1024,
      });
    };
    window.addEventListener('resize', checkSize);
    return () => window.removeEventListener('resize', checkSize);
  }, []);

  return screenSize;
}

interface StoreCreditEventsProps {
  shop: string | null;
}

// Scheduled Event (Promotion)
interface ScheduledEvent {
  id: number;
  name: string;
  description: string | null;
  promo_type: 'purchase_cashback' | 'trade_in_bonus';
  bonus_percent: number;
  starts_at: string;
  ends_at: string;
  daily_start_time: string | null;
  daily_end_time: string | null;
  active_days: string | null;
  product_tags_filter: string[] | null;
  collection_ids: string[] | null;
  tier_restriction: string[] | null;
  active: boolean;
  is_active_now: boolean;
}

// Bulk Credit Event Result
interface BulkEventPreview {
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

interface BulkEventResult {
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
  { label: '1 year', value: '365' },
];

// Fetch scheduled events (promotions of type purchase_cashback or trade_in_bonus)
async function fetchScheduledEvents(shop: string | null): Promise<{ events: ScheduledEvent[] }> {
  const response = await authFetch(`${getApiUrl()}/promotions/promotions`, shop);
  if (!response.ok) throw new Error('Failed to fetch events');
  const data = await response.json();
  // Filter to only show cashback/bonus type promotions
  const events = (data.promotions || []).filter((p: any) =>
    p.promo_type === 'purchase_cashback' || p.promo_type === 'trade_in_bonus'
  );
  return { events };
}

async function createScheduledEvent(shop: string | null, data: Partial<ScheduledEvent>): Promise<ScheduledEvent> {
  const response = await authFetch(`${getApiUrl()}/promotions/promotions`, shop, {
    method: 'POST',
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to create event');
  return response.json();
}

async function updateScheduledEvent(shop: string | null, id: number, data: Partial<ScheduledEvent>): Promise<ScheduledEvent> {
  const response = await authFetch(`${getApiUrl()}/promotions/promotions/${id}`, shop, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to update event');
  return response.json();
}

async function deleteScheduledEvent(shop: string | null, id: number): Promise<void> {
  const response = await authFetch(`${getApiUrl()}/promotions/promotions/${id}`, shop, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to delete event');
}

// Bulk event APIs
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

async function previewBulkEvent(
  shop: string | null,
  data: {
    start_datetime: string;
    end_datetime: string;
    sources: string[];
    credit_percent: number;
    include_authorized?: boolean;
    collection_ids?: string[];
    product_tags?: string[];
  }
): Promise<BulkEventPreview> {
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

async function runBulkEvent(
  shop: string | null,
  data: {
    start_datetime: string;
    end_datetime: string;
    sources: string[];
    credit_percent: number;
    include_authorized?: boolean;
    expires_at?: string;
    collection_ids?: string[];
    product_tags?: string[];
  }
): Promise<BulkEventResult> {
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

export function EmbeddedStoreCreditEvents({ shop }: StoreCreditEventsProps) {
  const queryClient = useQueryClient();
  const { isMobile, isTablet } = useResponsive();
  const [activeTab, setActiveTab] = useState(0);

  // Scheduled events state
  const [scheduledModalOpen, setScheduledModalOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState<ScheduledEvent | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [eventToDelete, setEventToDelete] = useState<ScheduledEvent | null>(null);

  // Bulk event state
  const [bulkModalOpen, setBulkModalOpen] = useState(false);
  const [bulkPreview, setBulkPreview] = useState<BulkEventPreview | null>(null);
  const [bulkResult, setBulkResult] = useState<BulkEventResult | null>(null);
  const [availableSources, setAvailableSources] = useState<OrderSource[]>([]);

  // Form states
  const [scheduledForm, setScheduledForm] = useState({
    name: '',
    description: '',
    promo_type: 'purchase_cashback' as 'purchase_cashback' | 'trade_in_bonus',
    bonus_percent: 10,
    starts_at: '',
    ends_at: '',
    daily_start_time: '',
    daily_end_time: '',
    active_days: [] as string[],
    product_tags_filter: [] as string[],
    collection_ids: [] as string[],
    tier_restriction: [] as string[],
    active: true,
    credit_expiration_days: '',
  });

  const [bulkForm, setBulkForm] = useState({
    start_datetime: '',
    end_datetime: '',
    sources: [] as string[],
    credit_percent: 10,
    include_authorized: true,
    credit_expiration_days: '',
    collection_ids: [] as string[],
    product_tags: [] as string[],
  });

  // Search states for bulk form pickers
  const [bulkTagSearch, setBulkTagSearch] = useState('');
  const [bulkCollectionSearch, setBulkCollectionSearch] = useState('');

  // Search states for pickers
  const [tagSearch, setTagSearch] = useState('');
  const [collectionSearch, setCollectionSearch] = useState('');

  // Fetch data
  const { data: tagsData } = useTags(shop);
  const { data: collectionsData } = useCollections(shop);

  const { data: eventsData, isLoading } = useQuery({
    queryKey: ['scheduled-events', shop],
    queryFn: () => fetchScheduledEvents(shop),
    enabled: !!shop,
  });

  // Memoized options
  const tagOptions = useMemo(() => {
    if (!tagsData?.tags) return [];
    const searchLower = (tagSearch || '').toLowerCase();
    const filtered = searchLower
      ? tagsData.tags.filter(t => (t || '').toLowerCase().includes(searchLower))
      : tagsData.tags;
    return filtered.filter(t => t).map(t => ({ value: t, label: t }));
  }, [tagsData, tagSearch]);

  const collectionOptions = useMemo(() => {
    if (!collectionsData?.collections) return [];
    const searchLower = (collectionSearch || '').toLowerCase();
    const filtered = searchLower
      ? collectionsData.collections.filter(c => (c?.title || '').toLowerCase().includes(searchLower))
      : collectionsData.collections;
    return filtered.filter(c => c?.title).map(c => ({ value: c.id, label: c.title }));
  }, [collectionsData, collectionSearch]);

  // Memoized options for bulk form (separate search states)
  const bulkTagOptions = useMemo(() => {
    if (!tagsData?.tags) return [];
    const searchLower = (bulkTagSearch || '').toLowerCase();
    const filtered = searchLower
      ? tagsData.tags.filter(t => (t || '').toLowerCase().includes(searchLower))
      : tagsData.tags;
    return filtered.filter(t => t).map(t => ({ value: t, label: t }));
  }, [tagsData, bulkTagSearch]);

  const bulkCollectionOptions = useMemo(() => {
    if (!collectionsData?.collections) return [];
    const searchLower = (bulkCollectionSearch || '').toLowerCase();
    const filtered = searchLower
      ? collectionsData.collections.filter(c => (c?.title || '').toLowerCase().includes(searchLower))
      : collectionsData.collections;
    return filtered.filter(c => c?.title).map(c => ({ value: c.id, label: c.title }));
  }, [collectionsData, bulkCollectionSearch]);

  // Mutations
  const createMutation = useMutation({
    mutationFn: (data: Partial<ScheduledEvent>) => createScheduledEvent(shop, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-events'] });
      setScheduledModalOpen(false);
      resetScheduledForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<ScheduledEvent> }) =>
      updateScheduledEvent(shop, id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-events'] });
      setScheduledModalOpen(false);
      setEditingEvent(null);
      resetScheduledForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteScheduledEvent(shop, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-events'] });
      setDeleteModalOpen(false);
      setEventToDelete(null);
    },
  });

  // Bulk event mutations
  const fetchSourcesMutation = useMutation({
    mutationFn: () => fetchEventSources(shop, bulkForm.start_datetime, bulkForm.end_datetime),
    onSuccess: (data) => setAvailableSources(data.sources),
  });

  const previewBulkMutation = useMutation({
    mutationFn: () => previewBulkEvent(shop, {
      start_datetime: bulkForm.start_datetime,
      end_datetime: bulkForm.end_datetime,
      sources: bulkForm.sources,
      credit_percent: bulkForm.credit_percent,
      include_authorized: bulkForm.include_authorized,
      collection_ids: bulkForm.collection_ids.length > 0 ? bulkForm.collection_ids : undefined,
      product_tags: bulkForm.product_tags.length > 0 ? bulkForm.product_tags : undefined,
    }),
    onSuccess: (data) => {
      setBulkPreview(data);
      setBulkResult(null);
    },
  });

  const runBulkMutation = useMutation({
    mutationFn: () => runBulkEvent(shop, {
      start_datetime: bulkForm.start_datetime,
      end_datetime: bulkForm.end_datetime,
      sources: bulkForm.sources,
      credit_percent: bulkForm.credit_percent,
      include_authorized: bulkForm.include_authorized,
      expires_at: bulkForm.credit_expiration_days
        ? new Date(Date.now() + parseInt(bulkForm.credit_expiration_days) * 24 * 60 * 60 * 1000).toISOString()
        : undefined,
      collection_ids: bulkForm.collection_ids.length > 0 ? bulkForm.collection_ids : undefined,
      product_tags: bulkForm.product_tags.length > 0 ? bulkForm.product_tags : undefined,
    }),
    onSuccess: (data) => {
      setBulkResult(data);
      setBulkPreview(null);
    },
  });

  // Form helpers
  const resetScheduledForm = useCallback(() => {
    const now = new Date();
    const nextWeek = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
    setScheduledForm({
      name: '',
      description: '',
      promo_type: 'purchase_cashback',
      bonus_percent: 10,
      starts_at: now.toISOString().slice(0, 16),
      ends_at: nextWeek.toISOString().slice(0, 16),
      daily_start_time: '',
      daily_end_time: '',
      active_days: [],
      product_tags_filter: [],
      collection_ids: [],
      tier_restriction: [],
      active: true,
      credit_expiration_days: '',
    });
    setTagSearch('');
    setCollectionSearch('');
  }, []);

  const resetBulkForm = useCallback(() => {
    setBulkForm({
      start_datetime: '',
      end_datetime: '',
      sources: [],
      credit_percent: 10,
      include_authorized: true,
      credit_expiration_days: '',
      collection_ids: [],
      product_tags: [],
    });
    setBulkPreview(null);
    setBulkResult(null);
    setAvailableSources([]);
    setBulkTagSearch('');
    setBulkCollectionSearch('');
  }, []);

  // Open create modal with optional template
  const openCreateModal = useCallback((template?: {
    name: string;
    description: string;
    bonus_percent: number;
    daily_start_time?: string;
    daily_end_time?: string;
    active_days?: string[];
    duration_hours?: number;
  }) => {
    resetScheduledForm();
    if (template) {
      const now = new Date();
      const endTime = template.duration_hours
        ? new Date(now.getTime() + template.duration_hours * 60 * 60 * 1000)
        : new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);

      setScheduledForm(prev => ({
        ...prev,
        name: template.name,
        description: template.description,
        bonus_percent: template.bonus_percent,
        daily_start_time: template.daily_start_time || '',
        daily_end_time: template.daily_end_time || '',
        active_days: template.active_days || [],
        starts_at: now.toISOString().slice(0, 16),
        ends_at: endTime.toISOString().slice(0, 16),
      }));
    }
    setEditingEvent(null);
    setScheduledModalOpen(true);
  }, [resetScheduledForm]);

  const openEditModal = useCallback((event: ScheduledEvent) => {
    setEditingEvent(event);
    setScheduledForm({
      name: event.name,
      description: event.description || '',
      promo_type: event.promo_type,
      bonus_percent: event.bonus_percent,
      starts_at: event.starts_at?.slice(0, 16) || '',
      ends_at: event.ends_at?.slice(0, 16) || '',
      daily_start_time: event.daily_start_time || '',
      daily_end_time: event.daily_end_time || '',
      active_days: event.active_days ? event.active_days.split(',') : [],
      product_tags_filter: event.product_tags_filter || [],
      collection_ids: event.collection_ids || [],
      tier_restriction: event.tier_restriction || [],
      active: event.active,
      credit_expiration_days: '',
    });
    setScheduledModalOpen(true);
  }, []);

  const openBulkModal = useCallback((templateHours?: number, percent?: number) => {
    const now = new Date();
    const endTime = templateHours
      ? new Date(now.getTime() + templateHours * 60 * 60 * 1000)
      : new Date(now.getTime() + 3 * 60 * 60 * 1000);

    setBulkForm({
      start_datetime: now.toISOString().slice(0, 16),
      end_datetime: endTime.toISOString().slice(0, 16),
      sources: [],
      credit_percent: percent || 10,
      include_authorized: true,
      credit_expiration_days: '',
      collection_ids: [],
      product_tags: [],
    });
    setBulkPreview(null);
    setBulkResult(null);
    setAvailableSources([]);
    setBulkModalOpen(true);
  }, []);

  const handleBulkDateChange = useCallback((field: 'start_datetime' | 'end_datetime', value: string) => {
    const newForm = { ...bulkForm, [field]: value };
    setBulkForm(newForm);
    if (newForm.start_datetime && newForm.end_datetime) {
      fetchSourcesMutation.mutate();
    }
  }, [bulkForm, fetchSourcesMutation]);

  const handleScheduledSubmit = useCallback(() => {
    const data = {
      name: scheduledForm.name,
      description: scheduledForm.description || null,
      promo_type: scheduledForm.promo_type,
      bonus_percent: scheduledForm.bonus_percent,
      bonus_flat: 0,
      multiplier: 1,
      starts_at: scheduledForm.starts_at,
      ends_at: scheduledForm.ends_at,
      daily_start_time: scheduledForm.daily_start_time || null,
      daily_end_time: scheduledForm.daily_end_time || null,
      active_days: scheduledForm.active_days.length > 0 ? scheduledForm.active_days.join(',') : null,
      product_tags_filter: scheduledForm.product_tags_filter.length > 0 ? scheduledForm.product_tags_filter : null,
      collection_ids: scheduledForm.collection_ids.length > 0 ? scheduledForm.collection_ids : null,
      tier_restriction: scheduledForm.tier_restriction.length > 0 ? scheduledForm.tier_restriction : null,
      channel: 'all',
      stackable: true,
      active: scheduledForm.active,
      credit_expiration_days: scheduledForm.credit_expiration_days ? parseInt(scheduledForm.credit_expiration_days) : null,
    };

    if (editingEvent) {
      updateMutation.mutate({ id: editingEvent.id, data });
    } else {
      createMutation.mutate(data);
    }
  }, [scheduledForm, editingEvent, createMutation, updateMutation]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const getStatusBadge = (event: ScheduledEvent) => {
    if (!event.active) return <Badge>Disabled</Badge>;
    if (event.is_active_now) return <Badge tone="success">Active Now</Badge>;
    if (event.starts_at && new Date(event.starts_at) > new Date()) return <Badge tone="info">Scheduled</Badge>;
    return <Badge tone="warning">Ended</Badge>;
  };

  const getScheduleDescription = (event: ScheduledEvent) => {
    const parts = [];
    if (event.daily_start_time && event.daily_end_time) {
      parts.push(`${event.daily_start_time} - ${event.daily_end_time}`);
    }
    if (event.active_days) {
      const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
      const days = event.active_days.split(',').map(d => dayNames[parseInt(d)]);
      parts.push(days.join(', '));
    }
    return parts.length > 0 ? parts.join(' on ') : 'All times';
  };

  const tabs = [
    { id: 'scheduled', content: 'Live Promotions', panelID: 'scheduled-panel' },
    { id: 'bulk', content: 'Post-Event Rewards', panelID: 'bulk-panel' },
  ];

  if (!shop) {
    return (
      <Page title="Store Credit Events">
        <Banner tone="warning">
          <p>No shop connected. Please install the app from the Shopify App Store.</p>
        </Banner>
      </Page>
    );
  }

  const events = eventsData?.events || [];

  return (
    <>
      <TitleBar title="Store Credit Events">
        <button variant="primary" onClick={() => openCreateModal()}>
          New Event
        </button>
      </TitleBar>
      <Page
        title="Store Credit Events"
        subtitle="Create bonus events to reward customers with store credit"
        primaryAction={{
          content: 'New Live Promotion',
          icon: PlusIcon,
          onAction: () => openCreateModal(),
        }}
        secondaryActions={[
          {
            content: 'Run Bulk Event',
            icon: PlayIcon,
            onAction: () => openBulkModal(),
          },
        ]}
      >
        <Layout>
          {/* Quick Templates */}
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <Text as="h3" variant="headingMd">Quick Start Templates</Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  Use a template to quickly create common bonus events
                </Text>

                <InlineGrid columns={isMobile ? 1 : isTablet ? 2 : 4} gap="300">
                  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <Card>
                      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '140px' }}>
                        <BlockStack gap="200">
                          <InlineStack gap="200" blockAlign="center">
                            <Icon source={CalendarIcon} />
                            <Text as="h4" variant="headingSm">Black Friday</Text>
                          </InlineStack>
                          <Text as="p" variant="bodySm" tone="subdued">
                            +10% store credit on all purchases during Black Friday weekend
                          </Text>
                        </BlockStack>
                        <div style={{ marginTop: 'auto', paddingTop: '12px' }}>
                          <Button
                            size="slim"
                            onClick={() => openCreateModal({
                              name: 'Black Friday Bonus',
                              description: 'Earn 10% store credit on all purchases this Black Friday weekend!',
                              bonus_percent: 10,
                              duration_hours: 72,
                            })}
                          >
                            Use Template
                          </Button>
                        </div>
                      </div>
                    </Card>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <Card>
                      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '140px' }}>
                        <BlockStack gap="200">
                          <InlineStack gap="200" blockAlign="center">
                            <Icon source={ClockIcon} />
                            <Text as="h4" variant="headingSm">Trade Night</Text>
                          </InlineStack>
                          <Text as="p" variant="bodySm" tone="subdued">
                            Saturday 6-9pm bonus for in-store trades and purchases
                          </Text>
                        </BlockStack>
                        <div style={{ marginTop: 'auto', paddingTop: '12px' }}>
                          <Button
                            size="slim"
                            onClick={() => openCreateModal({
                              name: 'Saturday Trade Night',
                              description: 'Extra 10% store credit on Saturday evening purchases!',
                              bonus_percent: 10,
                              daily_start_time: '18:00',
                              daily_end_time: '21:00',
                              active_days: ['5'], // Saturday
                            })}
                          >
                            Use Template
                          </Button>
                        </div>
                      </div>
                    </Card>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <Card>
                      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '140px' }}>
                        <BlockStack gap="200">
                          <InlineStack gap="200" blockAlign="center">
                            <Icon source={CalendarIcon} />
                            <Text as="h4" variant="headingSm">Weekend Warrior</Text>
                          </InlineStack>
                          <Text as="p" variant="bodySm" tone="subdued">
                            +5% store credit on all weekend purchases
                          </Text>
                        </BlockStack>
                        <div style={{ marginTop: 'auto', paddingTop: '12px' }}>
                          <Button
                            size="slim"
                            onClick={() => openCreateModal({
                              name: 'Weekend Bonus',
                              description: 'Earn 5% store credit on all weekend purchases!',
                              bonus_percent: 5,
                              active_days: ['5', '6'], // Saturday, Sunday
                            })}
                          >
                            Use Template
                          </Button>
                        </div>
                      </div>
                    </Card>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <Card>
                      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '140px' }}>
                        <BlockStack gap="200">
                          <InlineStack gap="200" blockAlign="center">
                            <Icon source={CalendarIcon} />
                            <Text as="h4" variant="headingSm">Grand Opening</Text>
                          </InlineStack>
                          <Text as="p" variant="bodySm" tone="subdued">
                            +15% store credit on opening day purchases
                          </Text>
                        </BlockStack>
                        <div style={{ marginTop: 'auto', paddingTop: '12px' }}>
                          <Button
                            size="slim"
                            onClick={() => openCreateModal({
                              name: 'Grand Opening Bonus',
                              description: 'Celebrate our grand opening with 15% store credit!',
                              bonus_percent: 15,
                              duration_hours: 24,
                            })}
                          >
                            Use Template
                          </Button>
                        </div>
                      </div>
                    </Card>
                  </div>
                </InlineGrid>
              </BlockStack>
            </Card>
          </Layout.Section>

          {/* Tabs for Scheduled vs Bulk */}
          <Layout.Section>
            <Tabs tabs={tabs} selected={activeTab} onSelect={setActiveTab}>
              {/* Scheduled Events Tab */}
              {activeTab === 0 && (
                <Card>
                  {isLoading ? (
                    <BlockStack gap="400">
                      {[1, 2, 3].map((i) => (
                        <Box key={i} paddingBlock="300">
                          <InlineStack gap="400" blockAlign="center">
                            <Box background="bg-surface-secondary" borderRadius="100" minHeight="20px" minWidth="150px" />
                            <Box background="bg-surface-secondary" borderRadius="100" minHeight="20px" minWidth="100px" />
                          </InlineStack>
                        </Box>
                      ))}
                    </BlockStack>
                  ) : events.length > 0 ? (
                    <DataTable
                      columnContentTypes={['text', 'text', 'text', 'text', 'text', 'text']}
                      headings={['Event Name', 'Bonus', 'Schedule', 'Date Range', 'Status', 'Actions']}
                      rows={events.map((event) => [
                        <BlockStack gap="100" key={event.id}>
                          <Text as="span" fontWeight="semibold">{event.name}</Text>
                          {event.product_tags_filter && event.product_tags_filter.length > 0 && (
                            <InlineStack gap="100">
                              {event.product_tags_filter.slice(0, 2).map(tag => (
                                <Badge key={tag} size="small">{tag}</Badge>
                              ))}
                            </InlineStack>
                          )}
                        </BlockStack>,
                        <Badge tone="success" key={event.id}>{`+${event.bonus_percent}%`}</Badge>,
                        getScheduleDescription(event),
                        <Text as="span" variant="bodySm" key={event.id}>
                          {event.starts_at ? new Date(event.starts_at).toLocaleDateString() : '—'} - {event.ends_at ? new Date(event.ends_at).toLocaleDateString() : '—'}
                        </Text>,
                        getStatusBadge(event),
                        <InlineStack gap="200" key={event.id}>
                          <Button
                            size="slim"
                            icon={EditIcon}
                            onClick={() => openEditModal(event)}
                            accessibilityLabel={`Edit ${event.name}`}
                          />
                          <Button
                            size="slim"
                            icon={DeleteIcon}
                            tone="critical"
                            onClick={() => {
                              setEventToDelete(event);
                              setDeleteModalOpen(true);
                            }}
                            accessibilityLabel={`Delete ${event.name}`}
                          />
                        </InlineStack>,
                      ])}
                    />
                  ) : (
                    <EmptyState
                      heading="No live promotions yet"
                      action={{
                        content: 'Create your first event',
                        onAction: () => openCreateModal(),
                      }}
                      image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                    >
                      <p>Schedule store credit bonus events to reward your customers during special periods.</p>
                    </EmptyState>
                  )}
                </Card>
              )}

              {/* Bulk Events Tab */}
              {activeTab === 1 && (
                <BlockStack gap="400">
                  <Card>
                    <BlockStack gap="300">
                      <Text as="h3" variant="headingMd">Send Post-Event Rewards</Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Issue store credit to customers based on their past orders. Great for rewarding customers after a busy sales period.
                      </Text>

                      <InlineGrid columns={isMobile ? 1 : isTablet ? 2 : 3} gap="300">
                        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                          <Card>
                            <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '100px' }}>
                              <BlockStack gap="200">
                                <Text as="h4" variant="headingSm">Trade Night Recap</Text>
                                <Text as="p" variant="bodySm" tone="subdued">
                                  Issue 10% credit for orders from the last 3 hours
                                </Text>
                              </BlockStack>
                              <div style={{ marginTop: 'auto', paddingTop: '12px' }}>
                                <Button
                                  size="slim"
                                  onClick={() => openBulkModal(3, 10)}
                                >
                                  Run Event
                                </Button>
                              </div>
                            </div>
                          </Card>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                          <Card>
                            <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '100px' }}>
                              <BlockStack gap="200">
                                <Text as="h4" variant="headingSm">Weekend Recap</Text>
                                <Text as="p" variant="bodySm" tone="subdued">
                                  Issue 5% credit for orders from the last 48 hours
                                </Text>
                              </BlockStack>
                              <div style={{ marginTop: 'auto', paddingTop: '12px' }}>
                                <Button
                                  size="slim"
                                  onClick={() => openBulkModal(48, 5)}
                                >
                                  Run Event
                                </Button>
                              </div>
                            </div>
                          </Card>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                          <Card>
                            <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '100px' }}>
                              <BlockStack gap="200">
                                <Text as="h4" variant="headingSm">Custom Event</Text>
                                <Text as="p" variant="bodySm" tone="subdued">
                                  Configure your own date range and credit percentage
                                </Text>
                              </BlockStack>
                              <div style={{ marginTop: 'auto', paddingTop: '12px' }}>
                                <Button
                                  size="slim"
                                  variant="primary"
                                  onClick={() => openBulkModal()}
                                >
                                  Create Custom
                                </Button>
                              </div>
                            </div>
                          </Card>
                        </div>
                      </InlineGrid>
                    </BlockStack>
                  </Card>

                  <Card>
                    <BlockStack gap="300">
                      <Text as="h3" variant="headingMd">How Bulk Events Work</Text>
                      <BlockStack gap="200">
                        <InlineStack gap="200" blockAlign="start">
                          <Badge tone="info">1</Badge>
                          <Text as="p" variant="bodySm">
                            <strong>Set Date Range:</strong> Choose the period to include orders from
                          </Text>
                        </InlineStack>
                        <InlineStack gap="200" blockAlign="start">
                          <Badge tone="info">2</Badge>
                          <Text as="p" variant="bodySm">
                            <strong>Select Sources:</strong> Filter by POS, Web, or all channels
                          </Text>
                        </InlineStack>
                        <InlineStack gap="200" blockAlign="start">
                          <Badge tone="info">3</Badge>
                          <Text as="p" variant="bodySm">
                            <strong>Preview:</strong> See exactly how much credit will be issued
                          </Text>
                        </InlineStack>
                        <InlineStack gap="200" blockAlign="start">
                          <Badge tone="success">4</Badge>
                          <Text as="p" variant="bodySm">
                            <strong>Apply:</strong> Issue store credit to all qualifying customers
                          </Text>
                        </InlineStack>
                      </BlockStack>
                    </BlockStack>
                  </Card>
                </BlockStack>
              )}
            </Tabs>
          </Layout.Section>
        </Layout>

        {/* Scheduled Event Modal */}
        <Modal
          open={scheduledModalOpen}
          onClose={() => setScheduledModalOpen(false)}
          title={editingEvent ? 'Edit Live Promotion' : 'New Live Promotion'}
          primaryAction={{
            content: editingEvent ? 'Save Changes' : 'Create Event',
            onAction: handleScheduledSubmit,
            loading: createMutation.isPending || updateMutation.isPending,
          }}
          secondaryActions={[
            { content: 'Cancel', onAction: () => setScheduledModalOpen(false) },
          ]}
        >
          <Modal.Section>
            <FormLayout>
              <TextField
                label="Event Name"
                value={scheduledForm.name}
                onChange={(value) => setScheduledForm({ ...scheduledForm, name: value })}
                autoComplete="off"
                requiredIndicator
                placeholder="e.g., Black Friday Bonus, Saturday Trade Night"
              />

              <TextField
                label="Description"
                value={scheduledForm.description}
                onChange={(value) => setScheduledForm({ ...scheduledForm, description: value })}
                multiline={2}
                autoComplete="off"
                helpText="Shown to customers in their account"
              />

              <Select
                label="Bonus Type"
                options={[
                  { label: 'Purchase Cashback (% of order total)', value: 'purchase_cashback' },
                  { label: 'Trade-In Bonus (% extra on trade-ins)', value: 'trade_in_bonus' },
                ]}
                value={scheduledForm.promo_type}
                onChange={(value) => setScheduledForm({ ...scheduledForm, promo_type: value as 'purchase_cashback' | 'trade_in_bonus' })}
              />

              <TextField
                label="Bonus Percentage"
                type="number"
                value={scheduledForm.bonus_percent.toString()}
                onChange={(value) => setScheduledForm({ ...scheduledForm, bonus_percent: parseFloat(value) || 0 })}
                suffix="%"
                autoComplete="off"
                helpText="Percentage of order/trade-in value to credit"
              />

              <Divider />
              <Text as="h3" variant="headingSm">Date Range</Text>
              <Text as="p" variant="bodySm" tone="subdued">
                The event will be active from start date through end date
              </Text>

              <FormLayout.Group>
                <TextField
                  label="Start Date"
                  type="date"
                  value={scheduledForm.starts_at.split('T')[0]}
                  onChange={(value) => setScheduledForm({ ...scheduledForm, starts_at: value + 'T00:00' })}
                  autoComplete="off"
                  requiredIndicator
                />
                <TextField
                  label="End Date"
                  type="date"
                  value={scheduledForm.ends_at.split('T')[0]}
                  onChange={(value) => setScheduledForm({ ...scheduledForm, ends_at: value + 'T23:59' })}
                  autoComplete="off"
                  requiredIndicator
                />
              </FormLayout.Group>

              <Divider />
              <Text as="h3" variant="headingSm">Daily Time Window (Optional)</Text>
              <Text as="p" variant="bodySm" tone="subdued">
                Limit this bonus to specific hours each day (e.g., 6-9pm trade nights)
              </Text>

              <FormLayout.Group>
                <TextField
                  label="Daily Start Time"
                  type="time"
                  value={scheduledForm.daily_start_time}
                  onChange={(value) => setScheduledForm({ ...scheduledForm, daily_start_time: value })}
                  autoComplete="off"
                  helpText="e.g., 18:00 for 6 PM"
                />
                <TextField
                  label="Daily End Time"
                  type="time"
                  value={scheduledForm.daily_end_time}
                  onChange={(value) => setScheduledForm({ ...scheduledForm, daily_end_time: value })}
                  autoComplete="off"
                  helpText="e.g., 21:00 for 9 PM"
                />
              </FormLayout.Group>

              <ChoiceList
                title="Active Days"
                choices={DAY_OPTIONS}
                selected={scheduledForm.active_days}
                onChange={(value) => setScheduledForm({ ...scheduledForm, active_days: value })}
                allowMultiple
              />

              <Divider />
              <Text as="h3" variant="headingSm">Product Filters (Optional)</Text>
              <Text as="p" variant="bodySm" tone="subdued">
                Only apply this bonus to specific products
              </Text>

              <BlockStack gap="200">
                <Autocomplete
                  options={tagOptions}
                  selected={scheduledForm.product_tags_filter}
                  onSelect={(selected) => setScheduledForm({ ...scheduledForm, product_tags_filter: selected })}
                  textField={
                    <Autocomplete.TextField
                      label="Product Tags"
                      value={tagSearch}
                      onChange={setTagSearch}
                      placeholder="e.g., pokemon, sports-cards"
                      prefix={<Icon source={SearchIcon} />}
                      autoComplete="off"
                    />
                  }
                  allowMultiple
                />
                {scheduledForm.product_tags_filter.length > 0 && (
                  <InlineStack gap="100" wrap>
                    {scheduledForm.product_tags_filter.map(tag => (
                      <Tag
                        key={tag}
                        onRemove={() => setScheduledForm({
                          ...scheduledForm,
                          product_tags_filter: scheduledForm.product_tags_filter.filter(t => t !== tag),
                        })}
                      >
                        {tag}
                      </Tag>
                    ))}
                  </InlineStack>
                )}
              </BlockStack>

              <BlockStack gap="200">
                <Autocomplete
                  options={collectionOptions}
                  selected={scheduledForm.collection_ids}
                  onSelect={(selected) => setScheduledForm({ ...scheduledForm, collection_ids: selected })}
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
                {scheduledForm.collection_ids.length > 0 && (
                  <InlineStack gap="100" wrap>
                    {scheduledForm.collection_ids.map(id => {
                      const collection = collectionsData?.collections?.find(c => c?.id === id);
                      return (
                        <Tag
                          key={id}
                          onRemove={() => setScheduledForm({
                            ...scheduledForm,
                            collection_ids: scheduledForm.collection_ids.filter(c => c !== id),
                          })}
                        >
                          {collection?.title || id}
                        </Tag>
                      );
                    })}
                  </InlineStack>
                )}
              </BlockStack>

              <Divider />

              <Select
                label="Credit Expiration"
                options={CREDIT_EXPIRATION_OPTIONS}
                value={scheduledForm.credit_expiration_days}
                onChange={(value) => setScheduledForm({ ...scheduledForm, credit_expiration_days: value })}
                helpText="How long before credited amounts expire"
              />

              <Checkbox
                label="Event is active"
                checked={scheduledForm.active}
                onChange={(checked) => setScheduledForm({ ...scheduledForm, active: checked })}
              />
            </FormLayout>
          </Modal.Section>
        </Modal>

        {/* Delete Confirmation Modal */}
        <Modal
          open={deleteModalOpen}
          onClose={() => setDeleteModalOpen(false)}
          title="Delete Event"
          primaryAction={{
            content: 'Delete',
            destructive: true,
            onAction: () => eventToDelete && deleteMutation.mutate(eventToDelete.id),
            loading: deleteMutation.isPending,
          }}
          secondaryActions={[
            { content: 'Cancel', onAction: () => setDeleteModalOpen(false) },
          ]}
        >
          <Modal.Section>
            <Text as="p">
              Are you sure you want to delete "{eventToDelete?.name}"? This action cannot be undone.
            </Text>
          </Modal.Section>
        </Modal>

        {/* Bulk Event Modal */}
        <Modal
          open={bulkModalOpen}
          onClose={() => {
            setBulkModalOpen(false);
            resetBulkForm();
          }}
          title="Run Bulk Store Credit Event"
          size="large"
          primaryAction={
            bulkPreview && !bulkResult
              ? {
                  content: 'Apply Credits',
                  icon: PlayIcon,
                  onAction: () => runBulkMutation.mutate(),
                  loading: runBulkMutation.isPending,
                }
              : bulkResult
              ? {
                  content: 'Done',
                  onAction: () => {
                    setBulkModalOpen(false);
                    resetBulkForm();
                  },
                }
              : {
                  content: 'Preview (Dry Run)',
                  icon: RefreshIcon,
                  onAction: () => previewBulkMutation.mutate(),
                  loading: previewBulkMutation.isPending,
                  disabled: !bulkForm.start_datetime || !bulkForm.end_datetime || bulkForm.sources.length === 0,
                }
          }
          secondaryActions={
            bulkResult
              ? []
              : [{ content: 'Cancel', onAction: () => { setBulkModalOpen(false); resetBulkForm(); } }]
          }
        >
          <Modal.Section>
            {bulkResult ? (
              <BlockStack gap="400">
                <Banner
                  title={bulkResult.success_count > 0 ? 'Event Completed Successfully!' : 'Event Completed'}
                  tone={bulkResult.failure_count > 0 ? 'warning' : 'success'}
                >
                  <p>
                    Issued {formatCurrency(bulkResult.total_credit_issued)} in store credit to {bulkResult.success_count} customers.
                    {bulkResult.failure_count > 0 && ` ${bulkResult.failure_count} failed.`}
                  </p>
                </Banner>

                {bulkResult.errors && bulkResult.errors.length > 0 && (
                  <Card>
                    <BlockStack gap="200">
                      <Text as="h4" variant="headingSm" tone="critical">Errors</Text>
                      {bulkResult.errors.slice(0, 10).map((error, i) => (
                        <Text as="p" variant="bodySm" key={i}>{error}</Text>
                      ))}
                    </BlockStack>
                  </Card>
                )}
              </BlockStack>
            ) : bulkPreview ? (
              <BlockStack gap="400">
                <Banner title="Preview Results" tone="info">
                  <p>This is a dry run. No credits have been issued yet. Review the data below and click "Apply Credits" to proceed.</p>
                </Banner>

                <InlineGrid columns={isMobile ? 2 : isTablet ? 2 : 4} gap="300">
                  <Card>
                    <BlockStack gap="100">
                      <Text as="span" variant="bodySm" tone="subdued">Total Orders</Text>
                      <Text as="p" variant="headingLg">{bulkPreview.summary.total_orders}</Text>
                    </BlockStack>
                  </Card>
                  <Card>
                    <BlockStack gap="100">
                      <Text as="span" variant="bodySm" tone="subdued">Unique Customers</Text>
                      <Text as="p" variant="headingLg">{bulkPreview.summary.unique_customers}</Text>
                    </BlockStack>
                  </Card>
                  <Card>
                    <BlockStack gap="100">
                      <Text as="span" variant="bodySm" tone="subdued">Total Order Value</Text>
                      <Text as="p" variant="headingLg">{formatCurrency(bulkPreview.summary.total_order_value)}</Text>
                    </BlockStack>
                  </Card>
                  <Card>
                    <BlockStack gap="100">
                      <Text as="span" variant="bodySm" tone="subdued">Credit to Issue</Text>
                      <Text as="p" variant="headingLg" tone="success">{formatCurrency(bulkPreview.summary.total_credit_to_issue)}</Text>
                    </BlockStack>
                  </Card>
                </InlineGrid>

                {bulkPreview.top_customers && bulkPreview.top_customers.length > 0 && (
                  <Card>
                    <BlockStack gap="300">
                      <Text as="h4" variant="headingSm">Top Customers by Credit</Text>
                      <DataTable
                        columnContentTypes={['text', 'text', 'numeric', 'numeric', 'numeric']}
                        headings={['Customer', 'Email', 'Orders', 'Spent', 'Credit']}
                        rows={bulkPreview.top_customers.slice(0, 5).map((customer) => [
                          customer.name || 'Guest',
                          customer.email || '-',
                          customer.order_count || 0,
                          formatCurrency(customer.total_spent || 0),
                          <Badge key={customer.customer_id} tone="success">{formatCurrency(customer.credit_amount || 0)}</Badge>,
                        ])}
                      />
                    </BlockStack>
                  </Card>
                )}

                <Button onClick={() => setBulkPreview(null)} variant="plain">
                  Back to Edit
                </Button>
              </BlockStack>
            ) : (
              <FormLayout>
                <Banner tone="info">
                  <p>Reward customers for past purchases. Set your date range and filters, then click "Preview" to see who qualifies before sending credits.</p>
                </Banner>

                <FormLayout.Group>
                  <TextField
                    label="Start Date & Time"
                    type="datetime-local"
                    value={bulkForm.start_datetime}
                    onChange={(value) => handleBulkDateChange('start_datetime', value)}
                    autoComplete="off"
                    requiredIndicator
                    helpText="Include orders created after this time"
                  />
                  <TextField
                    label="End Date & Time"
                    type="datetime-local"
                    value={bulkForm.end_datetime}
                    onChange={(value) => handleBulkDateChange('end_datetime', value)}
                    autoComplete="off"
                    requiredIndicator
                    helpText="Include orders created before this time"
                  />
                </FormLayout.Group>

                <TextField
                  label="Credit Percentage"
                  type="number"
                  value={bulkForm.credit_percent.toString()}
                  onChange={(value) => setBulkForm({ ...bulkForm, credit_percent: parseFloat(value) || 0 })}
                  suffix="%"
                  autoComplete="off"
                  helpText="Percentage of order total to issue as store credit"
                />

                <BlockStack gap="200">
                  <Text as="span" variant="bodyMd">Order Sources <Text as="span" tone="critical">*</Text></Text>
                  {fetchSourcesMutation.isPending ? (
                    <Text as="p" variant="bodySm" tone="subdued">Loading available sources...</Text>
                  ) : availableSources.length > 0 ? (
                    <ChoiceList
                      title=""
                      choices={availableSources.map((source) => ({
                        label: `${source.name} (${source.count} orders)`,
                        value: source.name,
                      }))}
                      selected={bulkForm.sources}
                      onChange={(selected) => setBulkForm({ ...bulkForm, sources: selected })}
                      allowMultiple
                    />
                  ) : bulkForm.start_datetime && bulkForm.end_datetime ? (
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

                <Text as="h3" variant="headingSm">Product Filters (Optional)</Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  Narrow down to orders containing specific products. Leave empty to include all orders.
                </Text>

                <BlockStack gap="200">
                  <Text as="span" variant="bodyMd">Collections</Text>
                  <Autocomplete
                    options={bulkCollectionOptions}
                    selected={bulkForm.collection_ids}
                    onSelect={(selected) => setBulkForm({ ...bulkForm, collection_ids: selected })}
                    textField={
                      <Autocomplete.TextField
                        label=""
                        onChange={setBulkCollectionSearch}
                        value={bulkCollectionSearch}
                        placeholder="Search collections..."
                        autoComplete="off"
                      />
                    }
                    allowMultiple
                    listTitle="Available Collections"
                  />
                  {bulkForm.collection_ids.length > 0 && (
                    <InlineStack gap="100" wrap>
                      {bulkForm.collection_ids.map((id) => {
                        const col = collectionsData?.collections?.find((c: any) => c.id === id);
                        return (
                          <Tag
                            key={id}
                            onRemove={() => setBulkForm({
                              ...bulkForm,
                              collection_ids: bulkForm.collection_ids.filter((c) => c !== id),
                            })}
                          >
                            {col?.title || id}
                          </Tag>
                        );
                      })}
                    </InlineStack>
                  )}
                </BlockStack>

                <BlockStack gap="200">
                  <Text as="span" variant="bodyMd">Product Tags</Text>
                  <Autocomplete
                    options={bulkTagOptions}
                    selected={bulkForm.product_tags}
                    onSelect={(selected) => setBulkForm({ ...bulkForm, product_tags: selected })}
                    textField={
                      <Autocomplete.TextField
                        label=""
                        onChange={setBulkTagSearch}
                        value={bulkTagSearch}
                        placeholder="Search tags..."
                        autoComplete="off"
                      />
                    }
                    allowMultiple
                    listTitle="Available Tags"
                  />
                  {bulkForm.product_tags.length > 0 && (
                    <InlineStack gap="100" wrap>
                      {bulkForm.product_tags.map((tag) => (
                        <Tag
                          key={tag}
                          onRemove={() => setBulkForm({
                            ...bulkForm,
                            product_tags: bulkForm.product_tags.filter((t) => t !== tag),
                          })}
                        >
                          {tag}
                        </Tag>
                      ))}
                    </InlineStack>
                  )}
                </BlockStack>

                <Divider />

                <Select
                  label="Credit Expiration"
                  options={CREDIT_EXPIRATION_OPTIONS}
                  value={bulkForm.credit_expiration_days}
                  onChange={(value) => setBulkForm({ ...bulkForm, credit_expiration_days: value })}
                  helpText="How long before issued credits expire"
                />

                <Checkbox
                  label="Include authorized (unpaid) orders"
                  checked={bulkForm.include_authorized}
                  onChange={(checked) => setBulkForm({ ...bulkForm, include_authorized: checked })}
                />
              </FormLayout>
            )}
          </Modal.Section>
        </Modal>
      </Page>
    </>
  );
}

export default EmbeddedStoreCreditEvents;
