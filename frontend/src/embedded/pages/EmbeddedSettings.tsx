/**
 * TradeUp Settings - Shopify Embedded Version
 *
 * Configure program settings with Polaris components.
 * Uses the nested settings API structure.
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
  TextField,
  Checkbox,
  Button,
  Banner,
  Spinner,
  Box,
  Select,
  Divider,
  Badge,
  List,
  Modal,
  FormLayout,
  ResourceList,
  ResourceItem,
  Icon,
} from '@shopify/polaris';
import { RefreshIcon, PlusIcon, EmailIcon, ClockIcon, CalendarIcon, ViewIcon, ChatIcon, StarIcon, GiftIcon, NotificationIcon, SendIcon } from '@shopify/polaris-icons';
import { SaveBar, useAppBridge } from '@shopify/app-bridge-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';
import { BugReportModal } from '../../components';

interface SettingsProps {
  shop: string | null;
}

// Match the backend API structure
interface SettingsResponse {
  settings: {
    branding: {
      app_name: string;
      tagline: string;
      logo_url: string | null;
      colors: {
        primary: string;
        primary_hover: string;
        secondary: string;
        accent: string;
      };
      style: string;
    };
    features: {
      points_enabled: boolean;
      referrals_enabled: boolean;
      self_signup_enabled: boolean;
      advanced_features_enabled: boolean;
    };
    auto_enrollment: {
      enabled: boolean;
      default_tier_id: number | null;
      min_order_value: number;
      excluded_tags: string[];
    };
    cashback: {
      method: string;
      purchase_cashback_enabled: boolean;
      trade_in_credit_enabled: boolean;
      same_transaction_bonus: boolean;
      rounding_mode: string;
      min_cashback_amount: number;
    };
    subscriptions: {
      monthly_enabled: boolean;
      yearly_enabled: boolean;
      trial_days: number;
      grace_period_days: number;
    };
    notifications: {
      enabled: boolean;
      welcome_email: boolean;
      trade_in_updates: boolean;
      tier_change: boolean;
      credit_issued: boolean;
      from_name: string | null;
      from_email: string | null;
    };
    contact: {
      support_email: string | null;
      support_phone: string | null;
    };
    trade_ins: {
      enabled: boolean;
      auto_approve_under: number;
      require_review_over: number;
      allow_guest_trade_ins: boolean;
      default_category: string;
      require_photos: boolean;
    };
    general: {
      currency: string;
      timezone: string;
    };
    anniversary: {
      enabled: boolean;
      reward_type: string;
      reward_amount: number;
      email_days_before: number;
      message: string;
      tiered_rewards_enabled: boolean;
      tiered_rewards: Record<string, number>;
    };
  };
  tenant: {
    id: number;
    shop_name: string;
    shop_slug: string;
  };
}

async function fetchSettings(shop: string | null): Promise<SettingsResponse> {
  const response = await authFetch(`${getApiUrl()}/settings`, shop);
  if (!response.ok) throw new Error('Failed to fetch settings');
  return response.json();
}

async function updateSettings(
  shop: string | null,
  section: string,
  data: Record<string, unknown>
): Promise<{ success: boolean }> {
  // Convert underscores to hyphens for URL (auto_enrollment -> auto-enrollment)
  const urlSection = section.replace(/_/g, '-');
  const endpoint = section === 'root' ? '' : `/${urlSection}`;
  const response = await authFetch(`${getApiUrl()}/settings${endpoint}`, shop, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to update settings');
  return response.json();
}

// Shopify Customer Segments
interface Segment {
  id: string;
  name: string;
  query: string;
  creationDate?: string;
  lastEditDate?: string;
}

interface SegmentsResponse {
  success: boolean;
  tradeup_segments: Segment[];
  other_segments: Segment[];
  total_count: number;
  error?: string;
}

interface SyncSegmentsResponse {
  success: boolean;
  segments: Array<{
    name: string;
    action: 'created' | 'updated';
    id: string;
    query: string;
  }>;
  errors: Array<{
    name: string;
    error: string;
  }>;
}

async function fetchSegments(shop: string | null): Promise<SegmentsResponse> {
  const response = await authFetch(`${getApiUrl()}/settings/segments`, shop);
  if (!response.ok) throw new Error('Failed to fetch segments');
  return response.json();
}

async function syncSegments(shop: string | null): Promise<SyncSegmentsResponse> {
  const response = await authFetch(`${getApiUrl()}/settings/segments/sync`, shop, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to sync segments');
  return response.json();
}

// Shopify Membership Products
interface MembershipProduct {
  id: string;
  title: string;
  handle: string;
  status: string;
  variants: Array<{
    id: string;
    title: string;
    price: string;
    sku: string;
  }>;
}

interface ProductsResponse {
  success: boolean;
  products: MembershipProduct[];
  count: number;
  error?: string;
}

interface SyncProductsResponse {
  success: boolean;
  products: Array<{
    tier: string;
    action: 'created' | 'updated';
    product_id: string;
    variants?: Array<{ id: string; title: string; price: string; sku: string }>;
  }>;
  errors: Array<{
    tier: string;
    error: string;
  }>;
}

async function fetchMembershipProducts(shop: string | null): Promise<ProductsResponse> {
  const response = await authFetch(`${getApiUrl()}/settings/products`, shop);
  if (!response.ok) throw new Error('Failed to fetch products');
  return response.json();
}

async function syncMembershipProducts(shop: string | null): Promise<SyncProductsResponse> {
  const response = await authFetch(`${getApiUrl()}/settings/products/sync`, shop, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to sync products');
  return response.json();
}

// Membership Tiers
interface MembershipTier {
  id: number;
  name: string;
  monthly_price: number;
  yearly_price?: number;
  bonus_rate: number;
  purchase_cashback_pct: number;
  monthly_credit_amount: number;
  credit_expiration_days?: number | null;
  benefits: {
    discount_percent?: number;
    free_shipping_threshold?: number;
    priority_support?: boolean;
    exclusive_access?: boolean;
    // New benefit fields
    free_shipping?: boolean;
    early_access?: boolean;
    exclusive_events?: boolean;
    signup_bonus?: number;
  };
  is_active: boolean;
  shopify_selling_plan_id?: string;
}

// Credit expiration options
const CREDIT_EXPIRATION_OPTIONS = [
  { label: 'Never expires', value: '' },
  { label: '30 days', value: '30' },
  { label: '60 days', value: '60' },
  { label: '90 days', value: '90' },
  { label: '180 days', value: '180' },
  { label: '1 year (365 days)', value: '365' },
];

interface TiersResponse {
  tiers: MembershipTier[];
}

// Email Templates
interface EmailTemplate {
  id: string;
  name: string;
  subject: string;
  body: string;
  category: string;
  is_custom: boolean;
}

interface EmailTemplatesResponse {
  templates: EmailTemplate[];
  by_category: Record<string, EmailTemplate[]>;
  categories: string[];
}

interface EmailPreviewResponse {
  template_id: string;
  template_name: string;
  subject: string;
  body: string;
  html_body: string;
}

async function fetchEmailTemplates(shop: string | null): Promise<EmailTemplatesResponse> {
  const response = await authFetch(`${getApiUrl()}/email/templates`, shop);
  if (!response.ok) throw new Error('Failed to fetch templates');
  return response.json();
}

async function previewEmailTemplate(
  shop: string | null,
  templateId: string
): Promise<EmailPreviewResponse> {
  const response = await authFetch(`${getApiUrl()}/email/preview`, shop, {
    method: 'POST',
    body: JSON.stringify({ template_id: templateId }),
  });
  if (!response.ok) throw new Error('Failed to preview template');
  return response.json();
}

async function sendTestEmail(
  shop: string | null,
  templateId: string,
  toEmail: string,
  toName: string
): Promise<{ success: boolean; message?: string; error?: string }> {
  const response = await authFetch(`${getApiUrl()}/email/send-test`, shop, {
    method: 'POST',
    body: JSON.stringify({ template_id: templateId, to_email: toEmail, to_name: toName }),
  });
  if (!response.ok) throw new Error('Failed to send test email');
  return response.json();
}

async function fetchTiers(shop: string | null): Promise<TiersResponse> {
  const response = await authFetch(`${getApiUrl()}/members/tiers`, shop);
  if (!response.ok) throw new Error('Failed to fetch tiers');
  return response.json();
}

// Review Prompt Metrics (RC-007)
interface ReviewMetrics {
  period_days: number | string;
  tenant_id: number | null;
  total_impressions: number;
  clicked_count: number;
  dismissed_count: number;
  reminded_later_count: number;
  no_response_count: number;
  click_rate: number;
  dismiss_rate: number;
  remind_later_rate: number;
  response_rate: number;
  funnel: {
    impressions: number;
    engaged: number;
    converted: number;
    engagement_rate: number;
    conversion_rate: number;
  };
  unique_tenants: number;
  daily_trend: Array<{
    date: string;
    impressions: number;
    clicked: number;
    dismissed: number;
    reminded_later: number;
  }>;
  summary: string;
}

interface ReviewMetricsResponse {
  success: boolean;
  metrics: ReviewMetrics;
}

async function fetchReviewMetrics(shop: string | null, days: number = 30): Promise<ReviewMetricsResponse> {
  const response = await authFetch(`${getApiUrl()}/review-prompt/metrics?days=${days}`, shop);
  if (!response.ok) throw new Error('Failed to fetch review metrics');
  return response.json();
}

async function createTier(shop: string | null, data: Partial<MembershipTier>): Promise<MembershipTier> {
  const response = await authFetch(`${getApiUrl()}/members/tiers`, shop, {
    method: 'POST',
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to create tier');
  return response.json();
}

async function updateTier(shop: string | null, tierId: number, data: Partial<MembershipTier>): Promise<MembershipTier> {
  const response = await authFetch(`${getApiUrl()}/members/tiers/${tierId}`, shop, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to update tier');
  return response.json();
}

async function deleteTier(shop: string | null, tierId: number): Promise<void> {
  const response = await authFetch(`${getApiUrl()}/members/tiers/${tierId}`, shop, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to delete tier');
  }
}

// Scheduled Tasks - Monthly Credits
interface MonthlyCreditPreview {
  processed: number;
  credited: number;
  skipped: number;
  total_amount: number;
  errors: Array<{ member_id: number; error: string }>;
  details: Array<{
    member_id: number;
    member_number: string;
    tier: string;
    amount: number;
    status: string;
    expires_at?: string | null;
  }>;
  dry_run: boolean;
  run_date: string;
}

interface ExpirationPreview {
  days_ahead: number;
  members_with_expiring_credits: number;
  total_amount_expiring: number;
  members: Array<{
    member_id: number;
    member_number: string;
    email: string | null;
    total_expiring: number;
    credits: Array<{
      id: number;
      amount: number;
      expires_at: string;
      description: string;
    }>;
  }>;
}

interface RunTaskResponse {
  success: boolean;
  message: string;
  result: MonthlyCreditPreview;
}

// Nudge Configuration Types
interface NudgeConfig {
  id: number;
  tenant_id: number;
  nudge_type: string;
  is_enabled: boolean;
  frequency_days: number;
  message_template: string;
  config_options: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

interface NudgeConfigsResponse {
  success: boolean;
  configs: NudgeConfig[];
}

interface TestNudgeResponse {
  success: boolean;
  message?: string;
  error?: string;
  nudge_type?: string;
}

// Nudge type labels for display
const NUDGE_TYPE_LABELS: Record<string, { label: string; description: string; icon: string }> = {
  points_expiring: {
    label: 'Points Expiring',
    description: 'Remind members when their points are about to expire',
    icon: 'clock',
  },
  tier_progress: {
    label: 'Tier Progress',
    description: 'Notify members when they are close to reaching the next tier',
    icon: 'trending-up',
  },
  inactive_reminder: {
    label: 'Inactive Re-engagement',
    description: 'Re-engage members who have been inactive for a while',
    icon: 'refresh',
  },
  trade_in_reminder: {
    label: 'Trade-In Reminder',
    description: 'Remind members to bring in items for trade-in',
    icon: 'exchange',
  },
};

async function fetchNudgeConfigs(shop: string | null): Promise<NudgeConfigsResponse> {
  const response = await authFetch(`${getApiUrl()}/nudges/configs`, shop);
  if (!response.ok) throw new Error('Failed to fetch nudge configs');
  return response.json();
}

async function updateNudgeConfig(
  shop: string | null,
  nudgeType: string,
  data: Partial<NudgeConfig>
): Promise<{ success: boolean; config: NudgeConfig }> {
  const response = await authFetch(`${getApiUrl()}/nudges/configs/${nudgeType}`, shop, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to update nudge config');
  return response.json();
}

async function sendTestNudge(
  shop: string | null,
  nudgeType: string,
  toEmail?: string,
  toName?: string
): Promise<TestNudgeResponse> {
  const response = await authFetch(`${getApiUrl()}/nudges/test-send`, shop, {
    method: 'POST',
    body: JSON.stringify({ nudge_type: nudgeType, to_email: toEmail, to_name: toName }),
  });
  if (!response.ok) throw new Error('Failed to send test nudge');
  return response.json();
}

async function fetchMonthlyCreditsPreview(shop: string | null): Promise<MonthlyCreditPreview> {
  const response = await authFetch(`${getApiUrl()}/scheduled-tasks/monthly-credits/preview`, shop);
  if (!response.ok) throw new Error('Failed to fetch preview');
  return response.json();
}

async function runMonthlyCredits(shop: string | null): Promise<RunTaskResponse> {
  const response = await authFetch(`${getApiUrl()}/scheduled-tasks/monthly-credits/run`, shop, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to run monthly credits');
  return response.json();
}

async function fetchExpiringCredits(shop: string | null, days: number = 7): Promise<ExpirationPreview> {
  const response = await authFetch(`${getApiUrl()}/scheduled-tasks/expiration/upcoming?days=${days}`, shop);
  if (!response.ok) throw new Error('Failed to fetch expiring credits');
  return response.json();
}

async function runExpiration(shop: string | null): Promise<RunTaskResponse> {
  const response = await authFetch(`${getApiUrl()}/scheduled-tasks/expiration/run`, shop, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to run expiration');
  return response.json();
}

export function EmbeddedSettings({ shop }: SettingsProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [hasChanges, setHasChanges] = useState(false);
  const [pendingChanges, setPendingChanges] = useState<Record<string, Record<string, unknown>>>({});
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Shopify App Bridge for SaveBar control
  const shopify = useAppBridge();

  const { data, isLoading, error } = useQuery({
    queryKey: ['settings', shop],
    queryFn: () => fetchSettings(shop),
    enabled: !!shop,
  });

  // Shopify Customer Segments
  const {
    data: segmentsData,
    isLoading: segmentsLoading,
    refetch: refetchSegments,
  } = useQuery({
    queryKey: ['segments', shop],
    queryFn: () => fetchSegments(shop),
    enabled: !!shop,
  });

  const syncSegmentsMutation = useMutation({
    mutationFn: () => syncSegments(shop),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segments'] });
    },
  });

  // Shopify Membership Products
  const {
    data: productsData,
    isLoading: productsLoading,
    refetch: refetchProducts,
  } = useQuery({
    queryKey: ['membership-products', shop],
    queryFn: () => fetchMembershipProducts(shop),
    enabled: !!shop,
  });

  const syncProductsMutation = useMutation({
    mutationFn: () => syncMembershipProducts(shop),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['membership-products'] });
    },
  });

  // Membership Tiers
  const {
    data: tiersData,
    isLoading: tiersLoading,
  } = useQuery({
    queryKey: ['tiers', shop],
    queryFn: () => fetchTiers(shop),
    enabled: !!shop,
  });

  const [tierModalOpen, setTierModalOpen] = useState(false);
  const [editingTier, setEditingTier] = useState<MembershipTier | null>(null);
  const [tierToDelete, setTierToDelete] = useState<MembershipTier | null>(null);
  const [tierForm, setTierForm] = useState({
    name: '',
    monthly_price: '9.99',
    yearly_price: '',
    bonus_rate: '0.05',
    discount_percent: '0',
    purchase_cashback_pct: '0',
    monthly_credit: '0',
    credit_expiration_days: '',
    // Additional benefits (stored in benefits JSON)
    free_shipping: false,
    priority_support: false,
    early_access: false,
    exclusive_events: false,
    signup_bonus: '0',
  });
  const [tierError, setTierError] = useState('');

  const openTierModal = useCallback((tier?: MembershipTier) => {
    if (tier) {
      setEditingTier(tier);
      setTierForm({
        name: tier.name,
        monthly_price: String(tier.monthly_price),
        yearly_price: tier.yearly_price ? String(tier.yearly_price) : '',
        // Convert decimal to percentage for display (0.05 -> 5)
        bonus_rate: String((tier.bonus_rate || 0) * 100),
        discount_percent: String(tier.benefits?.discount_percent || 0),
        purchase_cashback_pct: String(tier.purchase_cashback_pct || 0),
        monthly_credit: String(tier.monthly_credit_amount || 0),
        credit_expiration_days: tier.credit_expiration_days ? String(tier.credit_expiration_days) : '',
        // Additional benefits
        free_shipping: tier.benefits?.free_shipping || false,
        priority_support: tier.benefits?.priority_support || false,
        early_access: tier.benefits?.early_access || false,
        exclusive_events: tier.benefits?.exclusive_events || false,
        signup_bonus: String(tier.benefits?.signup_bonus || 0),
      });
    } else {
      setEditingTier(null);
      setTierForm({
        name: '',
        monthly_price: '9.99',
        yearly_price: '',
        bonus_rate: '5', // 5% default (displayed as percentage)
        discount_percent: '0',
        purchase_cashback_pct: '0',
        monthly_credit: '0',
        credit_expiration_days: '',
        // Additional benefits defaults
        free_shipping: false,
        priority_support: false,
        early_access: false,
        exclusive_events: false,
        signup_bonus: '0',
      });
    }
    setTierError('');
    setTierModalOpen(true);
  }, []);

  const closeTierModal = useCallback(() => {
    setTierModalOpen(false);
    setEditingTier(null);
    setTierError('');
  }, []);

  const createTierMutation = useMutation({
    mutationFn: (data: Partial<MembershipTier>) => createTier(shop, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tiers'] });
      closeTierModal();
    },
    onError: (err: Error) => setTierError(err.message),
  });

  const updateTierMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<MembershipTier> }) => updateTier(shop, id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tiers'] });
      closeTierModal();
    },
    onError: (err: Error) => setTierError(err.message),
  });

  const deleteTierMutation = useMutation({
    mutationFn: (id: number) => deleteTier(shop, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tiers'] });
    },
    onError: (err: Error) => setTierError(err.message),
  });

  // Scheduled Tasks - Monthly Credits
  const [scheduledTaskSuccess, setScheduledTaskSuccess] = useState('');
  const [scheduledTaskError, setScheduledTaskError] = useState('');

  const {
    data: monthlyCreditsPreview,
    isLoading: monthlyCreditsLoading,
    refetch: refetchMonthlyPreview,
  } = useQuery({
    queryKey: ['monthly-credits-preview', shop],
    queryFn: () => fetchMonthlyCreditsPreview(shop),
    enabled: !!shop,
  });

  const {
    data: expiringCredits,
    isLoading: expiringCreditsLoading,
    refetch: refetchExpiringCredits,
  } = useQuery({
    queryKey: ['expiring-credits', shop],
    queryFn: () => fetchExpiringCredits(shop, 7),
    enabled: !!shop,
  });

  const runMonthlyCreditsMutation = useMutation({
    mutationFn: () => runMonthlyCredits(shop),
    onSuccess: (data) => {
      setScheduledTaskSuccess(data.message);
      setScheduledTaskError('');
      queryClient.invalidateQueries({ queryKey: ['monthly-credits-preview'] });
      setTimeout(() => setScheduledTaskSuccess(''), 5000);
    },
    onError: (err: Error) => {
      setScheduledTaskError(err.message);
      setScheduledTaskSuccess('');
    },
  });

  const runExpirationMutation = useMutation({
    mutationFn: () => runExpiration(shop),
    onSuccess: (data) => {
      setScheduledTaskSuccess(data.message);
      setScheduledTaskError('');
      queryClient.invalidateQueries({ queryKey: ['expiring-credits'] });
      setTimeout(() => setScheduledTaskSuccess(''), 5000);
    },
    onError: (err: Error) => {
      setScheduledTaskError(err.message);
      setScheduledTaskSuccess('');
    },
  });

  // Email Templates
  const {
    data: emailTemplatesData,
    isLoading: emailTemplatesLoading,
  } = useQuery({
    queryKey: ['email-templates', shop],
    queryFn: () => fetchEmailTemplates(shop),
    enabled: !!shop,
  });

  // Nudge Configurations (NR-006)
  const {
    data: nudgeConfigsData,
    isLoading: nudgeConfigsLoading,
    refetch: refetchNudgeConfigs,
  } = useQuery({
    queryKey: ['nudge-configs', shop],
    queryFn: () => fetchNudgeConfigs(shop),
    enabled: !!shop,
  });

  const [nudgeTestOpen, setNudgeTestOpen] = useState(false);
  const [selectedNudgeType, setSelectedNudgeType] = useState<string | null>(null);
  const [nudgeTestEmail, setNudgeTestEmail] = useState('');
  const [nudgeTestName, setNudgeTestName] = useState('');
  const [nudgeSuccess, setNudgeSuccess] = useState('');
  const [nudgeError, setNudgeError] = useState('');

  const updateNudgeConfigMutation = useMutation({
    mutationFn: ({ nudgeType, data }: { nudgeType: string; data: Partial<NudgeConfig> }) =>
      updateNudgeConfig(shop, nudgeType, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['nudge-configs'] });
      setNudgeSuccess('Nudge settings updated');
      setTimeout(() => setNudgeSuccess(''), 3000);
    },
    onError: (err: Error) => {
      setNudgeError(err.message);
    },
  });

  const sendTestNudgeMutation = useMutation({
    mutationFn: () => {
      if (!selectedNudgeType) throw new Error('No nudge type selected');
      return sendTestNudge(shop, selectedNudgeType, nudgeTestEmail || undefined, nudgeTestName || undefined);
    },
    onSuccess: (data) => {
      if (data.success) {
        setNudgeSuccess(data.message || 'Test nudge sent');
        setNudgeTestOpen(false);
        setNudgeTestEmail('');
        setNudgeTestName('');
        setTimeout(() => setNudgeSuccess(''), 5000);
      } else {
        setNudgeError(data.error || 'Failed to send test nudge');
      }
    },
    onError: (err: Error) => setNudgeError(err.message),
  });

  const openNudgeTest = useCallback((nudgeType: string) => {
    setSelectedNudgeType(nudgeType);
    setNudgeError('');
    setNudgeTestOpen(true);
  }, []);

  // Review Prompt Metrics (RC-007)
  const [reviewMetricsDays, setReviewMetricsDays] = useState(30);
  const {
    data: reviewMetricsData,
    isLoading: reviewMetricsLoading,
    refetch: refetchReviewMetrics,
  } = useQuery({
    queryKey: ['review-metrics', shop, reviewMetricsDays],
    queryFn: () => fetchReviewMetrics(shop, reviewMetricsDays),
    enabled: !!shop,
  });

  const [emailPreviewOpen, setEmailPreviewOpen] = useState(false);
  const [emailTestOpen, setEmailTestOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<EmailTemplate | null>(null);
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewSubject, setPreviewSubject] = useState('');
  const [testEmail, setTestEmail] = useState('');
  const [testName, setTestName] = useState('');
  const [emailSuccess, setEmailSuccess] = useState('');
  const [emailError, setEmailError] = useState('');
  const [bugReportOpen, setBugReportOpen] = useState(false);

  const previewMutation = useMutation({
    mutationFn: (templateId: string) => previewEmailTemplate(shop, templateId),
    onSuccess: (data) => {
      setPreviewHtml(data.html_body);
      setPreviewSubject(data.subject);
      setEmailPreviewOpen(true);
    },
  });

  const sendTestMutation = useMutation({
    mutationFn: () => {
      if (!selectedTemplate) throw new Error('No template selected');
      return sendTestEmail(shop, selectedTemplate.id, testEmail, testName);
    },
    onSuccess: (data) => {
      if (data.success) {
        setEmailSuccess(`Test email sent to ${testEmail}`);
        setEmailTestOpen(false);
        setTestEmail('');
        setTestName('');
        setTimeout(() => setEmailSuccess(''), 5000);
      } else {
        setEmailError(data.error || 'Failed to send test email');
      }
    },
    onError: (err: Error) => setEmailError(err.message),
  });

  const openEmailPreview = useCallback((template: EmailTemplate) => {
    setSelectedTemplate(template);
    previewMutation.mutate(template.id);
  }, [previewMutation]);

  const openEmailTest = useCallback((template: EmailTemplate) => {
    setSelectedTemplate(template);
    setEmailError('');
    setEmailTestOpen(true);
  }, []);

  const handleTierSubmit = useCallback(() => {
    if (!tierForm.name.trim()) {
      setTierError('Tier name is required');
      return;
    }

    const tierData: Partial<MembershipTier> = {
      name: tierForm.name.trim(),
      monthly_price: parseFloat(tierForm.monthly_price) || 0,
      yearly_price: tierForm.yearly_price ? parseFloat(tierForm.yearly_price) : undefined,
      // Convert percentage to decimal for storage (5 -> 0.05)
      bonus_rate: (parseFloat(tierForm.bonus_rate) || 0) / 100,
      purchase_cashback_pct: parseFloat(tierForm.purchase_cashback_pct) || 0,
      monthly_credit_amount: parseFloat(tierForm.monthly_credit) || 0,
      credit_expiration_days: tierForm.credit_expiration_days ? parseInt(tierForm.credit_expiration_days) : null,
      benefits: {
        discount_percent: parseFloat(tierForm.discount_percent) || 0,
        // Additional benefits
        free_shipping: tierForm.free_shipping,
        priority_support: tierForm.priority_support,
        early_access: tierForm.early_access,
        exclusive_events: tierForm.exclusive_events,
        signup_bonus: parseFloat(tierForm.signup_bonus) || 0,
      },
    };

    if (editingTier) {
      updateTierMutation.mutate({ id: editingTier.id, data: tierData });
    } else {
      createTierMutation.mutate(tierData);
    }
  }, [tierForm, editingTier, createTierMutation, updateTierMutation]);

  const updateMutation = useMutation({
    mutationFn: async () => {
      // Save each section that has changes
      for (const [section, changes] of Object.entries(pendingChanges)) {
        if (Object.keys(changes).length > 0) {
          await updateSettings(shop, section, changes);
        }
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      setHasChanges(false);
      setPendingChanges({});
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    },
  });

  const handleChange = useCallback(
    (section: string, field: string, value: unknown) => {
      setPendingChanges((prev) => ({
        ...prev,
        [section]: {
          ...(prev[section] || {}),
          [field]: value,
        },
      }));
      setHasChanges(true);
    },
    []
  );

  const handleSave = useCallback(() => {
    updateMutation.mutate();
  }, [updateMutation]);

  const handleDiscard = useCallback(() => {
    setPendingChanges({});
    setHasChanges(false);
  }, []);

  // Show/hide Shopify App Bridge Save Bar based on changes
  useEffect(() => {
    if (hasChanges) {
      shopify.saveBar.show('settings-save-bar');
    } else {
      shopify.saveBar.hide('settings-save-bar');
    }
  }, [hasChanges, shopify.saveBar]);

  // Helper to get current value (pending change or stored value)
  const getValue = useCallback(
    <T,>(section: keyof SettingsResponse['settings'], field: string, fallback: T): T => {
      const pending = pendingChanges[section]?.[field];
      if (pending !== undefined) return pending as T;
      const stored = data?.settings?.[section]?.[field as keyof typeof data.settings[typeof section]];
      return (stored as T) ?? fallback;
    },
    [data, pendingChanges]
  );

  if (!shop) {
    return (
      <Page title="Settings">
        <Banner tone="warning">
          <p>No shop connected. Please install the app from the Shopify App Store.</p>
        </Banner>
      </Page>
    );
  }

  if (isLoading) {
    return (
      <Page title="Settings">
        <Box padding="1600">
          <InlineStack align="center">
            <Spinner size="large" />
          </InlineStack>
        </Box>
      </Page>
    );
  }

  return (
    <Page title="Settings" subtitle="Configure your TradeUp loyalty program">
      {saveSuccess && (
        <Box paddingBlockEnd="400">
          <Banner tone="success" onDismiss={() => setSaveSuccess(false)}>
            <p>Settings saved successfully.</p>
          </Banner>
        </Box>
      )}

      <Layout>
        {error && (
          <Layout.Section>
            <Banner tone="critical">
              <p>Failed to load settings. Please try refreshing the page.</p>
            </Banner>
          </Layout.Section>
        )}

        {/* Branding */}
        <Layout.AnnotatedSection
          id="branding"
          title="Branding"
          description="Customize your program's appearance"
        >
          <Card>
            <BlockStack gap="400">
              <TextField
                label="Program Name"
                value={getValue('branding', 'app_name', 'TradeUp')}
                onChange={(value) => handleChange('branding', 'app_name', value)}
                helpText="Shown to customers in their membership dashboard"
                autoComplete="off"
              />

              <TextField
                label="Tagline"
                value={getValue('branding', 'tagline', '')}
                onChange={(value) => handleChange('branding', 'tagline', value)}
                helpText="A short description of your loyalty program"
                autoComplete="off"
              />

              <Select
                label="Style"
                options={[
                  { label: 'Glass (Modern)', value: 'glass' },
                  { label: 'Solid', value: 'solid' },
                  { label: 'Minimal', value: 'minimal' },
                ]}
                value={getValue('branding', 'style', 'glass')}
                onChange={(value) => handleChange('branding', 'style', value)}
              />
            </BlockStack>
          </Card>
        </Layout.AnnotatedSection>

        {/* General Settings */}
        <Layout.AnnotatedSection
          id="general"
          title="General"
          description="Basic program configuration"
        >
          <Card>
            <BlockStack gap="400">
              <Select
                label="Currency"
                options={[
                  { label: 'USD ($)', value: 'USD' },
                  { label: 'CAD (C$)', value: 'CAD' },
                  { label: 'EUR (€)', value: 'EUR' },
                  { label: 'GBP (£)', value: 'GBP' },
                  { label: 'AUD (A$)', value: 'AUD' },
                ]}
                value={getValue('general', 'currency', 'USD')}
                onChange={(value) => handleChange('general', 'currency', value)}
              />

              <Select
                label="Timezone"
                options={[
                  { label: 'Pacific Time (US)', value: 'America/Los_Angeles' },
                  { label: 'Mountain Time (US)', value: 'America/Denver' },
                  { label: 'Central Time (US)', value: 'America/Chicago' },
                  { label: 'Eastern Time (US)', value: 'America/New_York' },
                  { label: 'UTC', value: 'UTC' },
                  { label: 'London (GMT)', value: 'Europe/London' },
                ]}
                value={getValue('general', 'timezone', 'America/Los_Angeles')}
                onChange={(value) => handleChange('general', 'timezone', value)}
              />
            </BlockStack>
          </Card>
        </Layout.AnnotatedSection>

        {/* Features */}
        <Layout.AnnotatedSection
          id="features"
          title="Features"
          description="Enable or disable program features"
        >
          <Card>
            <BlockStack gap="400">
              <Checkbox
                label="Enable self-signup"
                checked={getValue('features', 'self_signup_enabled', true)}
                onChange={(value) => handleChange('features', 'self_signup_enabled', value)}
                helpText="Allow customers to sign up for membership themselves"
              />

              <Checkbox
                label="Enable points system"
                checked={getValue('features', 'points_enabled', false)}
                onChange={(value) => handleChange('features', 'points_enabled', value)}
                helpText="Award points for purchases that can be redeemed for rewards"
              />

              <Checkbox
                label="Enable referral program"
                checked={getValue('features', 'referrals_enabled', false)}
                onChange={(value) => handleChange('features', 'referrals_enabled', value)}
                helpText="Allow members to earn rewards by referring new customers"
              />

              <Divider />

              <Checkbox
                label="Show advanced features"
                checked={getValue('features', 'advanced_features_enabled', false)}
                onChange={(value) => handleChange('features', 'advanced_features_enabled', value)}
                helpText="Shows Promotions, Points & Rewards, and Membership Tiers in the navigation sidebar. Perfect for power users."
              />
            </BlockStack>
          </Card>
        </Layout.AnnotatedSection>

        {/* Quick Tiers Access - Show when advanced features OFF */}
        {!getValue('features', 'advanced_features_enabled', false) && (
          <Layout.AnnotatedSection
            id="tiers-shortcut"
            title="Membership Tiers"
            description="Configure your membership tiers and benefits"
          >
            <Card>
              <BlockStack gap="400">
                <Text as="p" variant="bodyMd">
                  Set up tier pricing, trade-in bonuses, and member benefits for your loyalty program.
                </Text>
                <Button url="/app/tiers" fullWidth>
                  Manage Membership Tiers
                </Button>
              </BlockStack>
            </Card>
          </Layout.AnnotatedSection>
        )}

        {/* Auto-Enrollment */}
        <Layout.AnnotatedSection
          id="auto-enrollment"
          title="Auto-Enrollment"
          description="Automatically enroll customers on first purchase"
        >
          <Card>
            <BlockStack gap="400">
              <Checkbox
                label="Enable auto-enrollment"
                checked={getValue('auto_enrollment', 'enabled', true)}
                onChange={(value) => handleChange('auto_enrollment', 'enabled', value)}
                helpText="Automatically enroll customers when they make their first purchase"
              />

              <TextField
                label="Minimum Order Value"
                type="number"
                value={String(getValue('auto_enrollment', 'min_order_value', 0))}
                onChange={(value) =>
                  handleChange('auto_enrollment', 'min_order_value', parseFloat(value) || 0)
                }
                prefix="$"
                helpText="Only auto-enroll if order is at least this amount (0 = any order)"
                autoComplete="off"
              />
            </BlockStack>
          </Card>
        </Layout.AnnotatedSection>

        {/* Cashback Settings */}
        <Layout.AnnotatedSection
          id="cashback"
          title="Cashback & Rewards"
          description="Configure how rewards are delivered"
        >
          <Card>
            <BlockStack gap="400">
              <Select
                label="Reward Delivery Method"
                options={[
                  { label: 'Shopify Native Store Credit (Recommended)', value: 'native_store_credit' },
                  { label: 'Unique Discount Codes', value: 'discount_code' },
                  { label: 'Shopify Gift Cards', value: 'gift_card' },
                  { label: 'Manual Fulfillment', value: 'manual' },
                ]}
                value={getValue('cashback', 'method', 'native_store_credit')}
                onChange={(value) => handleChange('cashback', 'method', value)}
                helpText="How store credit and rewards are delivered to customers"
              />

              <Divider />

              <Checkbox
                label="Enable purchase cashback"
                checked={getValue('cashback', 'purchase_cashback_enabled', true)}
                onChange={(value) => handleChange('cashback', 'purchase_cashback_enabled', value)}
                helpText="Award cashback percentage on purchases based on tier"
              />

              <Checkbox
                label="Enable trade-in credit"
                checked={getValue('cashback', 'trade_in_credit_enabled', true)}
                onChange={(value) => handleChange('cashback', 'trade_in_credit_enabled', value)}
                helpText="Award bonus credit on trade-ins based on tier"
              />

              <Checkbox
                label="Same-transaction bonus"
                checked={getValue('cashback', 'same_transaction_bonus', true)}
                onChange={(value) => handleChange('cashback', 'same_transaction_bonus', value)}
                helpText="Apply tier benefits to the order that includes membership purchase"
              />
            </BlockStack>
          </Card>
        </Layout.AnnotatedSection>

        {/* Trade-In Rules */}
        <Layout.AnnotatedSection
          id="trade-ins"
          title="Trade-In Rules"
          description="Configure automatic approval thresholds"
        >
          <Card>
            <BlockStack gap="400">
              <Checkbox
                label="Enable trade-ins"
                checked={getValue('trade_ins', 'enabled', true)}
                onChange={(value) => handleChange('trade_ins', 'enabled', value)}
              />

              <Checkbox
                label="Allow guest trade-ins"
                checked={getValue('trade_ins', 'allow_guest_trade_ins', true)}
                onChange={(value) => handleChange('trade_ins', 'allow_guest_trade_ins', value)}
                helpText="Allow non-members to submit trade-ins (no tier bonus)"
              />

              <Divider />

              <TextField
                label="Auto-Approve Under"
                type="number"
                value={String(getValue('trade_ins', 'auto_approve_under', 50))}
                onChange={(value) =>
                  handleChange('trade_ins', 'auto_approve_under', parseFloat(value) || 0)
                }
                prefix="$"
                helpText="Trade-ins under this amount will be automatically approved"
                autoComplete="off"
              />

              <TextField
                label="Require Review Over"
                type="number"
                value={String(getValue('trade_ins', 'require_review_over', 500))}
                onChange={(value) =>
                  handleChange('trade_ins', 'require_review_over', parseFloat(value) || 0)
                }
                prefix="$"
                helpText="Trade-ins over this amount will require manual review"
                autoComplete="off"
              />

              <Checkbox
                label="Require photo uploads"
                checked={getValue('trade_ins', 'require_photos', false)}
                onChange={(value) => handleChange('trade_ins', 'require_photos', value)}
                helpText="Customers must upload photos when submitting trade-ins"
              />
            </BlockStack>
          </Card>
        </Layout.AnnotatedSection>

        {/* Subscriptions */}
        <Layout.AnnotatedSection
          id="subscriptions"
          title="Subscriptions"
          description="Membership subscription options"
        >
          <Card>
            <BlockStack gap="400">
              <BlockStack gap="200">
                <Checkbox
                  label="Enable monthly subscriptions"
                  checked={getValue('subscriptions', 'monthly_enabled', true)}
                  onChange={(value) => handleChange('subscriptions', 'monthly_enabled', value)}
                />
                <Checkbox
                  label="Enable yearly subscriptions"
                  checked={getValue('subscriptions', 'yearly_enabled', true)}
                  onChange={(value) => handleChange('subscriptions', 'yearly_enabled', value)}
                />
              </BlockStack>

              <TextField
                label="Free Trial Days"
                type="number"
                value={String(getValue('subscriptions', 'trial_days', 0))}
                onChange={(value) =>
                  handleChange('subscriptions', 'trial_days', parseInt(value) || 0)
                }
                suffix="days"
                helpText="Number of free trial days (0 = no trial)"
                autoComplete="off"
              />

              <TextField
                label="Grace Period"
                type="number"
                value={String(getValue('subscriptions', 'grace_period_days', 3))}
                onChange={(value) =>
                  handleChange('subscriptions', 'grace_period_days', parseInt(value) || 0)
                }
                suffix="days"
                helpText="Days to retry failed payments before downgrading tier"
                autoComplete="off"
              />
            </BlockStack>
          </Card>
        </Layout.AnnotatedSection>

        {/* Anniversary Rewards */}
        <Layout.AnnotatedSection
          id="anniversary-rewards"
          title="Anniversary Rewards"
          description="Automatically reward members on their membership anniversary"
        >
          <Card>
            <BlockStack gap="400">
              <InlineStack gap="200" blockAlign="center">
                <Icon source={GiftIcon} tone="base" />
                <Text as="h3" variant="headingSm">
                  Member Anniversary Rewards
                </Text>
              </InlineStack>

              <Checkbox
                label="Enable anniversary rewards"
                checked={getValue('anniversary', 'enabled', false)}
                onChange={(value) => handleChange('anniversary', 'enabled', value)}
                helpText="Automatically send rewards to members on their membership anniversary"
              />

              <Divider />

              <Select
                label="Reward Type"
                options={[
                  { label: 'Points', value: 'points' },
                  { label: 'Store Credit', value: 'credit' },
                  { label: 'Discount Code', value: 'discount_code' },
                ]}
                value={getValue('anniversary', 'reward_type', 'points')}
                onChange={(value) => handleChange('anniversary', 'reward_type', value)}
                helpText="Choose how to reward members on their anniversary"
                disabled={!getValue('anniversary', 'enabled', false)}
              />

              <TextField
                label="Reward Amount"
                type="number"
                value={String(getValue('anniversary', 'reward_amount', 100))}
                onChange={(value) =>
                  handleChange('anniversary', 'reward_amount', parseFloat(value) || 0)
                }
                prefix={getValue('anniversary', 'reward_type', 'points') === 'points' ? '' : '$'}
                suffix={getValue('anniversary', 'reward_type', 'points') === 'points' ? 'points' : ''}
                helpText={
                  getValue('anniversary', 'reward_type', 'points') === 'points'
                    ? 'Number of bonus points to award'
                    : getValue('anniversary', 'reward_type', 'points') === 'credit'
                    ? 'Dollar amount of store credit to award'
                    : 'Discount percentage for the code'
                }
                autoComplete="off"
                disabled={!getValue('anniversary', 'enabled', false)}
              />

              <Select
                label="Send Email"
                options={[
                  { label: 'On anniversary day', value: '0' },
                  { label: '1 day before', value: '1' },
                  { label: '3 days before', value: '3' },
                  { label: '7 days before', value: '7' },
                ]}
                value={String(getValue('anniversary', 'email_days_before', 0))}
                onChange={(value) => handleChange('anniversary', 'email_days_before', parseInt(value))}
                helpText="When to send the anniversary reward email"
                disabled={!getValue('anniversary', 'enabled', false)}
              />

              <Divider />

              <Checkbox
                label="Enable tiered anniversary rewards"
                checked={getValue('anniversary', 'tiered_rewards_enabled', false)}
                onChange={(value) => handleChange('anniversary', 'tiered_rewards_enabled', value)}
                helpText="Give different reward amounts based on anniversary year (e.g., Year 1 = $5, Year 2 = $10, Year 5 = $25)"
                disabled={!getValue('anniversary', 'enabled', false)}
              />

              {getValue('anniversary', 'tiered_rewards_enabled', false) && getValue('anniversary', 'enabled', false) && (
                <BlockStack gap="300">
                  <Text as="h4" variant="headingSm">Tiered Reward Amounts</Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Set custom reward amounts for specific anniversary years. Years not configured will use the default amount above.
                  </Text>
                  <BlockStack gap="200">
                    {[1, 2, 3, 5, 10].map((year) => {
                      const tieredRewards = getValue('anniversary', 'tiered_rewards', {}) as Record<string, number>;
                      const currentValue = tieredRewards[String(year)] ?? '';
                      const rewardType = getValue('anniversary', 'reward_type', 'points');
                      return (
                        <InlineStack key={year} gap="200" blockAlign="center">
                          <Box minWidth="100px">
                            <Text as="span" variant="bodyMd" fontWeight="semibold">
                              Year {year}:
                            </Text>
                          </Box>
                          <Box width="150px">
                            <TextField
                              label={`Year ${year} reward`}
                              labelHidden
                              type="number"
                              value={String(currentValue)}
                              onChange={(value) => {
                                const newTieredRewards = { ...tieredRewards };
                                if (value === '' || value === '0') {
                                  delete newTieredRewards[String(year)];
                                } else {
                                  newTieredRewards[String(year)] = parseFloat(value) || 0;
                                }
                                handleChange('anniversary', 'tiered_rewards', newTieredRewards);
                              }}
                              prefix={rewardType === 'points' ? '' : '$'}
                              suffix={rewardType === 'points' ? 'pts' : ''}
                              placeholder={`${getValue('anniversary', 'reward_amount', 100)}`}
                              autoComplete="off"
                            />
                          </Box>
                          <Text as="span" variant="bodySm" tone="subdued">
                            {currentValue ? '' : '(uses default)'}
                          </Text>
                        </InlineStack>
                      );
                    })}
                  </BlockStack>
                  <Banner tone="info">
                    <p>
                      {(() => {
                        const tieredRewards = getValue('anniversary', 'tiered_rewards', {}) as Record<string, number>;
                        const rewardType = getValue('anniversary', 'reward_type', 'points');
                        const defaultAmount = getValue('anniversary', 'reward_amount', 100);
                        const formatAmount = (amount: number) =>
                          rewardType === 'points' ? `${amount} points` : `$${amount}`;
                        const examples = [];
                        for (const year of [1, 2, 5]) {
                          const amount = tieredRewards[String(year)] ?? defaultAmount;
                          examples.push(`Year ${year}: ${formatAmount(amount)}`);
                        }
                        return `Example: ${examples.join(', ')}`;
                      })()}
                    </p>
                  </Banner>
                </BlockStack>
              )}

              <Divider />

              <BlockStack gap="200">
                <Text as="h4" variant="headingSm">How Anniversary Rewards Work</Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  When enabled, members will automatically receive their reward on the anniversary
                  of their membership enrollment. The reward is delivered based on the reward type
                  you select above. A celebratory email is sent according to your timing preference.
                  {getValue('anniversary', 'tiered_rewards_enabled', false) && (
                    ' With tiered rewards enabled, members receive different amounts based on their anniversary year.'
                  )}
                </Text>
              </BlockStack>
            </BlockStack>
          </Card>
        </Layout.AnnotatedSection>

        {/* Membership Tiers Configuration - Only show when advanced features ON */}
        {getValue('features', 'advanced_features_enabled', false) && (
        <Layout.AnnotatedSection
          id="tiers"
          title="Membership Tiers"
          description="Configure tier benefits and pricing"
        >
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between" blockAlign="center">
                <Text as="h3" variant="headingSm">
                  Your Tiers
                </Text>
                <Button onClick={() => openTierModal()} icon={PlusIcon}>
                  Add Tier
                </Button>
              </InlineStack>

              {tierError && !tierModalOpen && (
                <Banner tone="critical" onDismiss={() => setTierError('')}>
                  <p>{tierError}</p>
                </Banner>
              )}

              {tiersLoading ? (
                <InlineStack align="center">
                  <Spinner size="small" />
                  <Text as="span" variant="bodySm" tone="subdued">Loading tiers...</Text>
                </InlineStack>
              ) : tiersData?.tiers && tiersData.tiers.length > 0 ? (
                <ResourceList
                  resourceName={{ singular: 'tier', plural: 'tiers' }}
                  items={tiersData.tiers.filter(t => t && t.id != null)}
                  renderItem={(tier) => (
                    <ResourceItem
                      id={String(tier.id)}
                      onClick={() => openTierModal(tier)}
                      shortcutActions={[
                        {
                          content: 'Edit',
                          onAction: () => openTierModal(tier),
                        },
                        {
                          content: 'Delete',
                          onAction: () => setTierToDelete(tier),
                        },
                      ]}
                    >
                      <InlineStack align="space-between" blockAlign="center">
                        <BlockStack gap="100">
                          <InlineStack gap="200" blockAlign="center">
                            <Text as="h4" variant="bodyMd" fontWeight="semibold">
                              {tier.name}
                            </Text>
                            {tier.is_active ? (
                              <Badge tone="success">Active</Badge>
                            ) : (
                              <Badge>Inactive</Badge>
                            )}
                          </InlineStack>
                          <InlineStack gap="300">
                            <Text as="span" variant="bodySm" tone="subdued">
                              ${tier.monthly_price}/mo
                              {tier.yearly_price ? ` · $${tier.yearly_price}/yr` : ''}
                            </Text>
                            <Text as="span" variant="bodySm" tone="subdued">
                              +{((tier.bonus_rate || 0) * 100).toFixed(1).replace(/\.0$/, '')}% trade-in bonus
                            </Text>
                            {tier.purchase_cashback_pct ? (
                              <Text as="span" variant="bodySm" tone="subdued">
                                {tier.purchase_cashback_pct}% cashback
                              </Text>
                            ) : null}
                            {tier.monthly_credit_amount ? (
                              <Text as="span" variant="bodySm" tone="subdued">
                                ${tier.monthly_credit_amount}/mo credit
                              </Text>
                            ) : null}
                            {tier.benefits?.free_shipping && (
                              <Badge tone="success">Free Shipping</Badge>
                            )}
                            {tier.benefits?.early_access && (
                              <Badge>Early Access</Badge>
                            )}
                          </InlineStack>
                        </BlockStack>
                      </InlineStack>
                    </ResourceItem>
                  )}
                />
              ) : (
                <Box padding="400" background="bg-surface-secondary" borderRadius="200">
                  <BlockStack gap="200" inlineAlign="center">
                    <Text as="p" tone="subdued">No tiers configured yet.</Text>
                    <Button onClick={() => openTierModal()} icon={PlusIcon}>
                      Create Your First Tier
                    </Button>
                  </BlockStack>
                </Box>
              )}

              <Divider />

              <Text as="h3" variant="headingSm">
                Tier Benefits Explained
              </Text>
              <List type="bullet">
                <List.Item>
                  <strong>Trade-In Bonus:</strong> Extra percentage added to trade-in value (e.g., +5% on $100 = $5 bonus)
                </List.Item>
                <List.Item>
                  <strong>Purchase Cashback:</strong> Percentage of order total credited back after purchase
                </List.Item>
                <List.Item>
                  <strong>Monthly Credit:</strong> Fixed store credit awarded on the 1st of each month
                </List.Item>
                <List.Item>
                  <strong>Credit Expiration:</strong> How long before issued credits expire (optional)
                </List.Item>
              </List>
            </BlockStack>
          </Card>
        </Layout.AnnotatedSection>
        )}

        {/* Notifications */}
        <Layout.AnnotatedSection
          id="notifications"
          title="Notifications"
          description="Email notification settings"
        >
          <Card>
            <BlockStack gap="400">
              {emailSuccess && (
                <Banner tone="success" onDismiss={() => setEmailSuccess('')}>
                  <p>{emailSuccess}</p>
                </Banner>
              )}

              <Checkbox
                label="Enable email notifications"
                checked={getValue('notifications', 'enabled', true)}
                onChange={(value) => handleChange('notifications', 'enabled', value)}
              />

              <Divider />

              <Text as="h3" variant="headingSm">
                Notification Types
              </Text>

              <Checkbox
                label="Welcome email on enrollment"
                checked={getValue('notifications', 'welcome_email', true)}
                onChange={(value) => handleChange('notifications', 'welcome_email', value)}
              />

              <Checkbox
                label="Trade-in status updates"
                checked={getValue('notifications', 'trade_in_updates', true)}
                onChange={(value) => handleChange('notifications', 'trade_in_updates', value)}
              />

              <Checkbox
                label="Tier upgrade/downgrade"
                checked={getValue('notifications', 'tier_change', true)}
                onChange={(value) => handleChange('notifications', 'tier_change', value)}
              />

              <Checkbox
                label="Store credit issued"
                checked={getValue('notifications', 'credit_issued', true)}
                onChange={(value) => handleChange('notifications', 'credit_issued', value)}
              />

              <Divider />

              <TextField
                label="From Name"
                value={getValue('notifications', 'from_name', '') || ''}
                onChange={(value) => handleChange('notifications', 'from_name', value)}
                placeholder="Your Store Name"
                helpText="Sender name for emails (defaults to shop name)"
                autoComplete="off"
              />

              <TextField
                label="From Email"
                type="email"
                value={getValue('notifications', 'from_email', '') || ''}
                onChange={(value) => handleChange('notifications', 'from_email', value)}
                placeholder="noreply@yourstore.com"
                helpText="Sender email (must be verified with SendGrid)"
                autoComplete="email"
              />
            </BlockStack>
          </Card>
        </Layout.AnnotatedSection>

        {/* Nudges & Reminders (NR-006) */}
        <Layout.AnnotatedSection
          id="nudges"
          title="Nudges & Reminders"
          description="Automated messages to engage members and drive activity"
        >
          <Card>
            <BlockStack gap="400">
              {nudgeSuccess && (
                <Banner tone="success" onDismiss={() => setNudgeSuccess('')}>
                  <p>{nudgeSuccess}</p>
                </Banner>
              )}
              {nudgeError && (
                <Banner tone="critical" onDismiss={() => setNudgeError('')}>
                  <p>{nudgeError}</p>
                </Banner>
              )}

              <InlineStack align="space-between" blockAlign="center">
                <BlockStack gap="100">
                  <InlineStack gap="200" blockAlign="center">
                    <Icon source={NotificationIcon} tone="base" />
                    <Text as="h3" variant="headingMd">
                      Engagement Nudges
                    </Text>
                  </InlineStack>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Configure automated reminders to keep members engaged with your loyalty program.
                  </Text>
                </BlockStack>
                <Button
                  onClick={() => refetchNudgeConfigs()}
                  loading={nudgeConfigsLoading}
                  icon={RefreshIcon}
                >
                  Refresh
                </Button>
              </InlineStack>

              <Divider />

              {nudgeConfigsLoading ? (
                <InlineStack align="center">
                  <Spinner size="small" />
                  <Text as="span" variant="bodySm" tone="subdued">Loading nudge settings...</Text>
                </InlineStack>
              ) : nudgeConfigsData?.configs && nudgeConfigsData.configs.length > 0 ? (
                <BlockStack gap="400">
                  {nudgeConfigsData.configs.map((config) => {
                    const typeInfo = NUDGE_TYPE_LABELS[config.nudge_type] || {
                      label: config.nudge_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                      description: 'Configure this nudge type',
                    };
                    return (
                      <Box
                        key={config.id || config.nudge_type}
                        padding="400"
                        background="bg-surface-secondary"
                        borderRadius="200"
                      >
                        <BlockStack gap="300">
                          <InlineStack align="space-between" blockAlign="center">
                            <BlockStack gap="050">
                              <Text as="h4" variant="bodyMd" fontWeight="semibold">
                                {typeInfo.label}
                              </Text>
                              <Text as="p" variant="bodySm" tone="subdued">
                                {typeInfo.description}
                              </Text>
                            </BlockStack>
                            <InlineStack gap="200">
                              <Checkbox
                                label=""
                                labelHidden
                                checked={config.is_enabled}
                                onChange={(value) => {
                                  updateNudgeConfigMutation.mutate({
                                    nudgeType: config.nudge_type,
                                    data: { is_enabled: value },
                                  });
                                }}
                              />
                              <Badge tone={config.is_enabled ? 'success' : undefined}>
                                {config.is_enabled ? 'Enabled' : 'Disabled'}
                              </Badge>
                            </InlineStack>
                          </InlineStack>

                          {config.is_enabled && (
                            <>
                              <Divider />
                              <InlineStack gap="400" wrap>
                                <Box minWidth="200px">
                                  <TextField
                                    label="Frequency"
                                    type="number"
                                    value={String(config.frequency_days)}
                                    onChange={(value) => {
                                      updateNudgeConfigMutation.mutate({
                                        nudgeType: config.nudge_type,
                                        data: { frequency_days: parseInt(value) || 7 },
                                      });
                                    }}
                                    suffix="days"
                                    autoComplete="off"
                                    helpText="Time between nudges"
                                  />
                                </Box>
                              </InlineStack>

                              <BlockStack gap="200">
                                <Text as="h5" variant="bodySm" fontWeight="semibold">
                                  Message Preview
                                </Text>
                                <Box
                                  padding="300"
                                  background="bg-surface"
                                  borderRadius="100"
                                  borderWidth="025"
                                  borderColor="border"
                                >
                                  <Text as="p" variant="bodySm" tone="subdued">
                                    {config.message_template || 'No message template configured'}
                                  </Text>
                                </Box>
                              </BlockStack>

                              <InlineStack gap="200">
                                <Button
                                  icon={SendIcon}
                                  onClick={() => openNudgeTest(config.nudge_type)}
                                  size="slim"
                                >
                                  Send Test
                                </Button>
                              </InlineStack>
                            </>
                          )}
                        </BlockStack>
                      </Box>
                    );
                  })}
                </BlockStack>
              ) : (
                <Box padding="400" background="bg-surface-secondary" borderRadius="200">
                  <BlockStack gap="200" inlineAlign="center">
                    <Text as="p" tone="subdued">No nudge configurations found.</Text>
                    <Button onClick={() => refetchNudgeConfigs()}>
                      Load Default Configurations
                    </Button>
                  </BlockStack>
                </Box>
              )}

              <Divider />

              <BlockStack gap="200">
                <Text as="h3" variant="headingSm">How Nudges Work</Text>
                <List type="bullet">
                  <List.Item>
                    <strong>Points Expiring:</strong> Reminds members before their points expire
                  </List.Item>
                  <List.Item>
                    <strong>Tier Progress:</strong> Encourages members who are close to the next tier
                  </List.Item>
                  <List.Item>
                    <strong>Inactive Re-engagement:</strong> Reaches out to members who have not visited recently
                  </List.Item>
                  <List.Item>
                    <strong>Trade-In Reminder:</strong> Prompts members to bring in items for trade-in
                  </List.Item>
                </List>
              </BlockStack>
            </BlockStack>
          </Card>
        </Layout.AnnotatedSection>

        {/* Email Templates */}
        <Layout.AnnotatedSection
          id="email-templates"
          title="Email Templates"
          description="Preview and test your email notifications"
        >
          <Card>
            <BlockStack gap="400">
              <Text as="p" variant="bodySm" tone="subdued">
                TradeUp sends automatic emails for key events. Preview each template below
                and send test emails to verify your setup.
              </Text>

              {emailTemplatesLoading ? (
                <InlineStack align="center">
                  <Spinner size="small" />
                  <Text as="span" variant="bodySm" tone="subdued">Loading templates...</Text>
                </InlineStack>
              ) : emailTemplatesData?.by_category ? (
                <BlockStack gap="500">
                  {Object.entries(emailTemplatesData.by_category || {}).filter(([cat]) => cat).map(([category, templates]) => (
                    <BlockStack key={category || 'unknown'} gap="200">
                      <Text as="h4" variant="headingSm">
                        {String(category || 'General').replace('_', ' ').split(' ').filter(w => w).map(word => String(word).charAt(0).toUpperCase() + String(word).slice(1)).join(' ')} Emails
                      </Text>
                      <BlockStack gap="100">
                        {templates.filter(template => template && template.id).map((template) => (
                          <Box
                            key={template.id}
                            padding="300"
                            background="bg-surface-secondary"
                            borderRadius="200"
                          >
                            <InlineStack align="space-between" blockAlign="center">
                              <BlockStack gap="050">
                                <Text as="span" variant="bodyMd" fontWeight="semibold">
                                  {template.name}
                                </Text>
                                <Text as="span" variant="bodySm" tone="subdued">
                                  Subject: {(template.subject || '').substring(0, 50)}...
                                </Text>
                              </BlockStack>
                              <InlineStack gap="200">
                                <Button
                                  icon={ViewIcon}
                                  variant="plain"
                                  onClick={() => openEmailPreview(template)}
                                  loading={previewMutation.isPending && selectedTemplate?.id === template.id}
                                >
                                  Preview
                                </Button>
                                <Button
                                  icon={EmailIcon}
                                  variant="plain"
                                  onClick={() => openEmailTest(template)}
                                >
                                  Send Test
                                </Button>
                              </InlineStack>
                            </InlineStack>
                          </Box>
                        ))}
                      </BlockStack>
                    </BlockStack>
                  ))}
                </BlockStack>
              ) : (
                <Text as="p" variant="bodySm" tone="subdued">
                  No email templates available.
                </Text>
              )}

              <Divider />

              <BlockStack gap="200">
                <Text as="h3" variant="headingSm">
                  Email Setup Requirements
                </Text>
                <List type="bullet">
                  <List.Item>
                    <strong>SendGrid API Key:</strong> Configure in your environment variables
                  </List.Item>
                  <List.Item>
                    <strong>Sender Verification:</strong> Verify your sending domain with SendGrid
                  </List.Item>
                  <List.Item>
                    <strong>From Email:</strong> Set above to match your verified domain
                  </List.Item>
                </List>
              </BlockStack>
            </BlockStack>
          </Card>
        </Layout.AnnotatedSection>

        {/* Contact */}
        <Layout.AnnotatedSection
          id="contact"
          title="Support Contact"
          description="Contact information shown to customers"
        >
          <Card>
            <BlockStack gap="400">
              <TextField
                label="Support Email"
                type="email"
                value={getValue('contact', 'support_email', '') || ''}
                onChange={(value) => handleChange('contact', 'support_email', value)}
                placeholder="support@yourstore.com"
                autoComplete="email"
              />

              <TextField
                label="Support Phone"
                type="tel"
                value={getValue('contact', 'support_phone', '') || ''}
                onChange={(value) => handleChange('contact', 'support_phone', value)}
                placeholder="+1 (555) 123-4567"
                autoComplete="tel"
              />
            </BlockStack>
          </Card>
        </Layout.AnnotatedSection>

        {/* Shopify Customer Segments */}
        <Layout.AnnotatedSection
          id="segments"
          title="Shopify Customer Segments"
          description="Auto-create segments for tier-based marketing with Shopify Email"
        >
          <Card>
            <BlockStack gap="400">
              <Text as="p" variant="bodySm" tone="subdued">
                TradeUp can automatically create customer segments in Shopify based on your membership tiers.
                Use these segments with Shopify Email to send targeted campaigns to specific member groups.
              </Text>

              <InlineStack align="space-between" blockAlign="center">
                <BlockStack gap="100">
                  <Text as="h3" variant="headingSm">
                    Sync Tier Segments
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Creates "TradeUp Members" (all) + one segment per tier
                  </Text>
                </BlockStack>
                <Button
                  onClick={() => syncSegmentsMutation.mutate()}
                  loading={syncSegmentsMutation.isPending}
                  icon={RefreshIcon}
                >
                  Sync Segments
                </Button>
              </InlineStack>

              {syncSegmentsMutation.isSuccess && syncSegmentsMutation.data && (
                <Banner tone="success" onDismiss={() => syncSegmentsMutation.reset()}>
                  <BlockStack gap="200">
                    <Text as="p" variant="bodySm">
                      {syncSegmentsMutation.data.segments.length} segments synced successfully!
                    </Text>
                    <List type="bullet">
                      {syncSegmentsMutation.data.segments.filter(s => s && s.id != null).map((seg) => (
                        <List.Item key={seg.id}>
                          {seg.name || 'Unknown'} ({seg.action || 'unknown'})
                        </List.Item>
                      ))}
                    </List>
                  </BlockStack>
                </Banner>
              )}

              {syncSegmentsMutation.isError && (
                <Banner tone="critical">
                  <p>Failed to sync segments. Please try again.</p>
                </Banner>
              )}

              <Divider />

              <BlockStack gap="300">
                <Text as="h3" variant="headingSm">
                  Current TradeUp Segments
                </Text>

                {segmentsLoading ? (
                  <InlineStack align="center">
                    <Spinner size="small" />
                    <Text as="span" variant="bodySm" tone="subdued">Loading segments...</Text>
                  </InlineStack>
                ) : segmentsData?.tradeup_segments && segmentsData.tradeup_segments.length > 0 ? (
                  <BlockStack gap="200">
                    {segmentsData.tradeup_segments.map((segment) => (
                      <InlineStack key={segment.id} align="space-between" blockAlign="center">
                        <InlineStack gap="200">
                          <Badge tone="success">Active</Badge>
                          <Text as="span" variant="bodySm" fontWeight="semibold">
                            {segment.name}
                          </Text>
                        </InlineStack>
                        <Text as="span" variant="bodySm" tone="subdued">
                          {segment.query}
                        </Text>
                      </InlineStack>
                    ))}
                  </BlockStack>
                ) : (
                  <Text as="p" variant="bodySm" tone="subdued">
                    No TradeUp segments found. Click "Sync Segments" to create them.
                  </Text>
                )}

                <InlineStack gap="200">
                  <Button
                    variant="plain"
                    onClick={() => refetchSegments()}
                  >
                    Refresh
                  </Button>
                  <Button
                    variant="plain"
                    url="https://admin.shopify.com/store/segments"
                    external
                  >
                    View in Shopify →
                  </Button>
                </InlineStack>
              </BlockStack>

              <Divider />

              <BlockStack gap="200">
                <Text as="h3" variant="headingSm">
                  How to Use with Shopify Email
                </Text>
                <List type="number">
                  <List.Item>Go to Marketing → Campaigns in Shopify Admin</List.Item>
                  <List.Item>Create a new email campaign</List.Item>
                  <List.Item>Under "Recipients", select your TradeUp segment (e.g., "TradeUp Gold Members")</List.Item>
                  <List.Item>Design and send your campaign - only those members will receive it!</List.Item>
                </List>
              </BlockStack>
            </BlockStack>
          </Card>
        </Layout.AnnotatedSection>

        {/* Shopify Membership Products */}
        <Layout.AnnotatedSection
          id="products"
          title="Membership Products"
          description="Sync tiers as purchasable products in your Shopify store"
        >
          <Card>
            <BlockStack gap="400">
              <Text as="p" variant="bodySm" tone="subdued">
                Create Shopify products for each membership tier. Customers can purchase these
                products to join a tier directly through your Shopify checkout.
              </Text>

              {/* Product Setup Wizard - Recommended for first-time setup */}
              <Box
                padding="400"
                background="bg-surface-secondary"
                borderRadius="200"
              >
                <InlineStack align="space-between" blockAlign="center">
                  <BlockStack gap="100">
                    <Text as="h3" variant="headingSm">
                      Product Setup Wizard
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Guided setup with templates, previews, and customization options
                    </Text>
                  </BlockStack>
                  <Button
                    variant="primary"
                    onClick={() => navigate('/app/products/wizard')}
                  >
                    Launch Wizard
                  </Button>
                </InlineStack>
              </Box>

              <Divider />

              <InlineStack align="space-between" blockAlign="center">
                <BlockStack gap="100">
                  <Text as="h3" variant="headingSm">
                    Quick Sync (Advanced)
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Automatically creates products with default settings for each tier
                  </Text>
                </BlockStack>
                <Button
                  onClick={() => syncProductsMutation.mutate()}
                  loading={syncProductsMutation.isPending}
                  icon={RefreshIcon}
                >
                  Sync Products
                </Button>
              </InlineStack>

              {syncProductsMutation.isSuccess && syncProductsMutation.data && (
                <Banner tone="success" onDismiss={() => syncProductsMutation.reset()}>
                  <BlockStack gap="200">
                    <Text as="p" variant="bodySm">
                      {syncProductsMutation.data.products.length} membership products synced!
                    </Text>
                    <List type="bullet">
                      {syncProductsMutation.data.products.filter(p => p && p.product_id != null).map((prod) => (
                        <List.Item key={prod.product_id}>
                          {prod.tier || 'Unknown'} Membership ({prod.action || 'unknown'})
                        </List.Item>
                      ))}
                    </List>
                  </BlockStack>
                </Banner>
              )}

              {syncProductsMutation.isError && (
                <Banner tone="critical">
                  <p>Failed to sync products. Please try again.</p>
                </Banner>
              )}

              <Divider />

              <BlockStack gap="300">
                <Text as="h3" variant="headingSm">
                  Current Membership Products
                </Text>

                {productsLoading ? (
                  <InlineStack align="center">
                    <Spinner size="small" />
                    <Text as="span" variant="bodySm" tone="subdued">Loading products...</Text>
                  </InlineStack>
                ) : productsData?.products && productsData.products.length > 0 ? (
                  <BlockStack gap="300">
                    {productsData.products.filter(p => p && p.id).map((product) => (
                      <BlockStack key={product.id} gap="100">
                        <InlineStack align="space-between" blockAlign="center">
                          <InlineStack gap="200">
                            <Badge tone={product.status === 'ACTIVE' ? 'success' : 'attention'}>
                              {String(product.status || 'DRAFT')}
                            </Badge>
                            <Text as="span" variant="bodySm" fontWeight="semibold">
                              {product.title || 'Untitled'}
                            </Text>
                          </InlineStack>
                        </InlineStack>
                        <InlineStack gap="200">
                          {(product.variants || []).filter(v => v && v.id).map((variant) => (
                            <Badge key={variant.id} tone="info">
                              {`${variant.title || 'Variant'}: $${variant.price || '0'}`}
                            </Badge>
                          ))}
                        </InlineStack>
                      </BlockStack>
                    ))}
                  </BlockStack>
                ) : (
                  <Text as="p" variant="bodySm" tone="subdued">
                    No membership products found. Click "Sync Products" to create them.
                  </Text>
                )}

                <InlineStack gap="200">
                  <Button
                    variant="plain"
                    onClick={() => refetchProducts()}
                  >
                    Refresh
                  </Button>
                  <Button
                    variant="plain"
                    url="https://admin.shopify.com/products"
                    external
                  >
                    View in Shopify →
                  </Button>
                </InlineStack>
              </BlockStack>

              <Divider />

              <BlockStack gap="200">
                <Text as="h3" variant="headingSm">
                  How Membership Purchases Work
                </Text>
                <List type="number">
                  <List.Item>Customer purchases a membership product in your store</List.Item>
                  <List.Item>TradeUp receives the order webhook and automatically enrolls the customer</List.Item>
                  <List.Item>Customer is tagged with their tier (e.g., tu-gold) and gains benefits</List.Item>
                  <List.Item>For subscriptions, tier continues until subscription is cancelled</List.Item>
                </List>
              </BlockStack>
            </BlockStack>
          </Card>
        </Layout.AnnotatedSection>

        {/* Partner Integrations */}
        <Layout.AnnotatedSection
          id="integrations"
          title="Partner Integrations"
          description="Connect external systems and POS for data sync"
        >
          <Card>
            <BlockStack gap="400">
              <Text as="p" variant="bodySm" tone="subdued">
                Connect TradeUp with external systems to sync member data, trade-ins,
                and store credit across platforms.
              </Text>

              <BlockStack gap="300">
                <Box padding="400" background="bg-surface-secondary" borderRadius="200">
                  <InlineStack align="space-between" blockAlign="center">
                    <InlineStack gap="300">
                      <Box padding="200" background="bg-surface" borderRadius="100">
                        <Text as="span" variant="headingMd">POS</Text>
                      </Box>
                      <BlockStack gap="050">
                        <Text as="h4" variant="bodyMd" fontWeight="semibold">
                          Point of Sale Integration
                        </Text>
                        <Text as="p" variant="bodySm" tone="subdued">
                          Sync members and credit with Shopify POS
                        </Text>
                      </BlockStack>
                    </InlineStack>
                    <Badge tone="success">Connected</Badge>
                  </InlineStack>
                </Box>

                <Box padding="400" background="bg-surface-secondary" borderRadius="200">
                  <InlineStack align="space-between" blockAlign="center">
                    <InlineStack gap="300">
                      <Box padding="200" background="bg-surface" borderRadius="100">
                        <Text as="span" variant="headingMd">API</Text>
                      </Box>
                      <BlockStack gap="050">
                        <Text as="h4" variant="bodyMd" fontWeight="semibold">
                          API Access
                        </Text>
                        <Text as="p" variant="bodySm" tone="subdued">
                          Use the TradeUp API for custom integrations
                        </Text>
                      </BlockStack>
                    </InlineStack>
                    <Button variant="secondary">Get API Key</Button>
                  </InlineStack>
                </Box>

                <Box padding="400" background="bg-surface-secondary" borderRadius="200">
                  <InlineStack align="space-between" blockAlign="center">
                    <InlineStack gap="300">
                      <Box padding="200" background="bg-surface" borderRadius="100">
                        <Text as="span" variant="headingMd">ERP</Text>
                      </Box>
                      <BlockStack gap="050">
                        <Text as="h4" variant="bodyMd" fontWeight="semibold">
                          ERP/Accounting System
                        </Text>
                        <Text as="p" variant="bodySm" tone="subdued">
                          Export transaction data for accounting
                        </Text>
                      </BlockStack>
                    </InlineStack>
                    <Badge>Coming Soon</Badge>
                  </InlineStack>
                </Box>

                <Box padding="400" background="bg-surface-secondary" borderRadius="200">
                  <InlineStack align="space-between" blockAlign="center">
                    <InlineStack gap="300">
                      <Box padding="200" background="bg-surface" borderRadius="100">
                        <Text as="span" variant="headingMd">CRM</Text>
                      </Box>
                      <BlockStack gap="050">
                        <Text as="h4" variant="bodyMd" fontWeight="semibold">
                          CRM Integration
                        </Text>
                        <Text as="p" variant="bodySm" tone="subdued">
                          Sync member data with your CRM
                        </Text>
                      </BlockStack>
                    </InlineStack>
                    <Badge>Coming Soon</Badge>
                  </InlineStack>
                </Box>
              </BlockStack>

              <Divider />

              <BlockStack gap="200">
                <Text as="h3" variant="headingSm">Webhook Endpoints</Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  Receive real-time notifications when events occur in TradeUp.
                </Text>
                <List type="bullet">
                  <List.Item>member.created - New member enrolled</List.Item>
                  <List.Item>member.tier_changed - Member tier upgraded/downgraded</List.Item>
                  <List.Item>trade_in.submitted - New trade-in received</List.Item>
                  <List.Item>trade_in.approved - Trade-in approved, credit issued</List.Item>
                  <List.Item>credit.issued - Store credit added to member</List.Item>
                </List>
                <Button variant="plain" url="https://docs.tradeup.io/webhooks" external>
                  View Webhook Documentation →
                </Button>
              </BlockStack>
            </BlockStack>
          </Card>
        </Layout.AnnotatedSection>

        {/* Scheduled Tasks - Monthly Credits */}
        <Layout.AnnotatedSection
          id="scheduled-tasks"
          title="Monthly Credits & Automation"
          description="Manage automated credit distribution and expiration"
        >
          <BlockStack gap="400">
            {scheduledTaskSuccess && (
              <Banner tone="success" onDismiss={() => setScheduledTaskSuccess('')}>
                <p>{scheduledTaskSuccess}</p>
              </Banner>
            )}
            {scheduledTaskError && (
              <Banner tone="critical" onDismiss={() => setScheduledTaskError('')}>
                <p>{scheduledTaskError}</p>
              </Banner>
            )}

            {/* Monthly Credit Distribution */}
            <Card>
              <BlockStack gap="400">
                <InlineStack align="space-between" blockAlign="center">
                  <BlockStack gap="100">
                    <InlineStack gap="200" blockAlign="center">
                      <Icon source={CalendarIcon} tone="base" />
                      <Text as="h3" variant="headingMd">
                        Monthly Credit Distribution
                      </Text>
                    </InlineStack>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Automatically issues store credit to members based on their tier benefits on the 1st of each month.
                    </Text>
                  </BlockStack>
                  <InlineStack gap="200">
                    <Button
                      onClick={() => refetchMonthlyPreview()}
                      loading={monthlyCreditsLoading}
                      icon={RefreshIcon}
                    >
                      Refresh
                    </Button>
                  </InlineStack>
                </InlineStack>

                <Divider />

                {monthlyCreditsLoading ? (
                  <InlineStack align="center">
                    <Spinner size="small" />
                    <Text as="span" variant="bodySm">Loading preview...</Text>
                  </InlineStack>
                ) : monthlyCreditsPreview ? (
                  <BlockStack gap="300">
                    <InlineStack gap="400" wrap>
                      <BlockStack gap="100">
                        <Text as="p" variant="bodySm" tone="subdued">Eligible Members</Text>
                        <Text as="p" variant="headingLg">{monthlyCreditsPreview.credited}</Text>
                      </BlockStack>
                      <BlockStack gap="100">
                        <Text as="p" variant="bodySm" tone="subdued">Total Amount</Text>
                        <Text as="p" variant="headingLg">${(monthlyCreditsPreview.total_amount || 0).toFixed(2)}</Text>
                      </BlockStack>
                      <BlockStack gap="100">
                        <Text as="p" variant="bodySm" tone="subdued">Already Received</Text>
                        <Text as="p" variant="headingLg">{monthlyCreditsPreview.skipped}</Text>
                      </BlockStack>
                    </InlineStack>

                    {monthlyCreditsPreview.credited > 0 && (
                      <Box paddingBlockStart="200">
                        <BlockStack gap="200">
                          <Text as="h4" variant="headingSm">Preview (first 5 members):</Text>
                          {monthlyCreditsPreview.details.slice(0, 5).filter(detail => detail && detail.member_number).map((detail, idx) => (
                            <InlineStack key={idx} gap="200" align="space-between">
                              <Text as="span" variant="bodySm">
                                {detail.member_number || 'Unknown'} ({detail.tier || 'No tier'})
                              </Text>
                              <Badge tone="success">{`$${(detail.amount || 0).toFixed(2)}`}</Badge>
                            </InlineStack>
                          ))}
                        </BlockStack>
                      </Box>
                    )}

                    <Box paddingBlockStart="200">
                      <InlineStack gap="200">
                        <Button
                          variant="primary"
                          onClick={() => runMonthlyCreditsMutation.mutate()}
                          loading={runMonthlyCreditsMutation.isPending}
                          disabled={monthlyCreditsPreview.credited === 0}
                        >
                          Distribute Credits Now
                        </Button>
                        {monthlyCreditsPreview.credited === 0 && (
                          <Text as="span" variant="bodySm" tone="subdued">
                            All eligible members have already received credits this month
                          </Text>
                        )}
                      </InlineStack>
                    </Box>
                  </BlockStack>
                ) : (
                  <Text as="p" variant="bodySm" tone="subdued">
                    No members with tier monthly credits configured
                  </Text>
                )}
              </BlockStack>
            </Card>

            {/* Credit Expiration */}
            <Card>
              <BlockStack gap="400">
                <InlineStack align="space-between" blockAlign="center">
                  <BlockStack gap="100">
                    <InlineStack gap="200" blockAlign="center">
                      <Icon source={ClockIcon} tone="base" />
                      <Text as="h3" variant="headingMd">
                        Credit Expiration
                      </Text>
                    </InlineStack>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Credits with expiration dates are automatically expired. View upcoming expirations and process expired credits.
                    </Text>
                  </BlockStack>
                  <InlineStack gap="200">
                    <Button
                      onClick={() => refetchExpiringCredits()}
                      loading={expiringCreditsLoading}
                      icon={RefreshIcon}
                    >
                      Refresh
                    </Button>
                  </InlineStack>
                </InlineStack>

                <Divider />

                {expiringCreditsLoading ? (
                  <InlineStack align="center">
                    <Spinner size="small" />
                    <Text as="span" variant="bodySm">Loading...</Text>
                  </InlineStack>
                ) : expiringCredits ? (
                  <BlockStack gap="300">
                    <InlineStack gap="400" wrap>
                      <BlockStack gap="100">
                        <Text as="p" variant="bodySm" tone="subdued">Expiring in {expiringCredits.days_ahead} days</Text>
                        <Text as="p" variant="headingLg">{expiringCredits.members_with_expiring_credits} members</Text>
                      </BlockStack>
                      <BlockStack gap="100">
                        <Text as="p" variant="bodySm" tone="subdued">Total Amount Expiring</Text>
                        <Text as="p" variant="headingLg">${(expiringCredits.total_amount_expiring || 0).toFixed(2)}</Text>
                      </BlockStack>
                    </InlineStack>

                    {expiringCredits.members.length > 0 && (
                      <Box paddingBlockStart="200">
                        <BlockStack gap="200">
                          <Text as="h4" variant="headingSm">Members with expiring credits:</Text>
                          {expiringCredits.members.slice(0, 5).filter(member => member && member.member_number).map((member, idx) => (
                            <InlineStack key={idx} gap="200" align="space-between">
                              <Text as="span" variant="bodySm">
                                {member.member_number || 'Unknown'} ({member.email || 'No email'})
                              </Text>
                              <Badge tone="warning">{`$${(member.total_expiring || 0).toFixed(2)}`}</Badge>
                            </InlineStack>
                          ))}
                        </BlockStack>
                      </Box>
                    )}

                    <Box paddingBlockStart="200">
                      <Button
                        onClick={() => runExpirationMutation.mutate()}
                        loading={runExpirationMutation.isPending}
                      >
                        Process Expired Credits
                      </Button>
                    </Box>
                  </BlockStack>
                ) : (
                  <Text as="p" variant="bodySm" tone="subdued">
                    No credits with expiration dates
                  </Text>
                )}
              </BlockStack>
            </Card>

            {/* Cron Job Info */}
            <Card>
              <BlockStack gap="200">
                <Text as="h3" variant="headingSm">Automation Schedule</Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  These tasks run automatically on a schedule:
                </Text>
                <List>
                  <List.Item>
                    <Text as="span" fontWeight="semibold">Monthly credits:</Text> 1st of each month at 6:00 AM UTC
                  </List.Item>
                  <List.Item>
                    <Text as="span" fontWeight="semibold">Credit expiration:</Text> Daily at midnight UTC
                  </List.Item>
                  <List.Item>
                    <Text as="span" fontWeight="semibold">Expiration warnings:</Text> Daily at 9:00 AM UTC (7-day warning)
                  </List.Item>
                </List>
              </BlockStack>
            </Card>
          </BlockStack>
        </Layout.AnnotatedSection>

        {/* Review Prompt Metrics (RC-007) */}
        <Layout.AnnotatedSection
          id="review-metrics"
          title="Review Prompt Metrics"
          description="Track how many prompts convert to actual reviews"
        >
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between" blockAlign="center">
                <BlockStack gap="100">
                  <InlineStack gap="200" blockAlign="center">
                    <Icon source={StarIcon} tone="base" />
                    <Text as="h3" variant="headingMd">
                      Review Collection Performance
                    </Text>
                  </InlineStack>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Metrics for in-app review prompts shown to merchants.
                  </Text>
                </BlockStack>
                <InlineStack gap="200">
                  <Select
                    label=""
                    labelHidden
                    options={[
                      { label: 'Last 7 days', value: '7' },
                      { label: 'Last 30 days', value: '30' },
                      { label: 'Last 90 days', value: '90' },
                      { label: 'All time', value: '0' },
                    ]}
                    value={String(reviewMetricsDays)}
                    onChange={(value) => setReviewMetricsDays(parseInt(value))}
                  />
                  <Button
                    onClick={() => refetchReviewMetrics()}
                    loading={reviewMetricsLoading}
                    icon={RefreshIcon}
                  >
                    Refresh
                  </Button>
                </InlineStack>
              </InlineStack>

              <Divider />

              {reviewMetricsLoading ? (
                <InlineStack align="center">
                  <Spinner size="small" />
                  <Text as="span" variant="bodySm">Loading metrics...</Text>
                </InlineStack>
              ) : reviewMetricsData?.metrics ? (
                <BlockStack gap="400">
                  {/* Key Metrics Grid */}
                  <InlineStack gap="400" wrap>
                    <BlockStack gap="100">
                      <Text as="p" variant="bodySm" tone="subdued">Prompt Impressions</Text>
                      <Text as="p" variant="headingLg">{reviewMetricsData.metrics.total_impressions}</Text>
                    </BlockStack>
                    <BlockStack gap="100">
                      <Text as="p" variant="bodySm" tone="subdued">Rate Now Clicks</Text>
                      <InlineStack gap="100" blockAlign="center">
                        <Text as="p" variant="headingLg">{reviewMetricsData.metrics.clicked_count}</Text>
                        <Badge tone="success">{reviewMetricsData.metrics.click_rate}%</Badge>
                      </InlineStack>
                    </BlockStack>
                    <BlockStack gap="100">
                      <Text as="p" variant="bodySm" tone="subdued">Dismissed</Text>
                      <InlineStack gap="100" blockAlign="center">
                        <Text as="p" variant="headingLg">{reviewMetricsData.metrics.dismissed_count}</Text>
                        <Badge>{reviewMetricsData.metrics.dismiss_rate}%</Badge>
                      </InlineStack>
                    </BlockStack>
                    <BlockStack gap="100">
                      <Text as="p" variant="bodySm" tone="subdued">Remind Later</Text>
                      <InlineStack gap="100" blockAlign="center">
                        <Text as="p" variant="headingLg">{reviewMetricsData.metrics.reminded_later_count}</Text>
                        <Badge tone="info">{reviewMetricsData.metrics.remind_later_rate}%</Badge>
                      </InlineStack>
                    </BlockStack>
                  </InlineStack>

                  <Divider />

                  {/* Conversion Funnel */}
                  <BlockStack gap="200">
                    <Text as="h4" variant="headingSm">Conversion Funnel</Text>
                    <InlineStack gap="400" wrap>
                      <BlockStack gap="100">
                        <Text as="p" variant="bodySm" tone="subdued">Impressions</Text>
                        <Text as="p" variant="bodyMd" fontWeight="semibold">
                          {reviewMetricsData.metrics.funnel.impressions}
                        </Text>
                      </BlockStack>
                      <Text as="span" variant="bodyMd" tone="subdued">→</Text>
                      <BlockStack gap="100">
                        <Text as="p" variant="bodySm" tone="subdued">Engaged</Text>
                        <Text as="p" variant="bodyMd" fontWeight="semibold">
                          {reviewMetricsData.metrics.funnel.engaged} ({reviewMetricsData.metrics.funnel.engagement_rate}%)
                        </Text>
                      </BlockStack>
                      <Text as="span" variant="bodyMd" tone="subdued">→</Text>
                      <BlockStack gap="100">
                        <Text as="p" variant="bodySm" tone="subdued">Converted (Clicked)</Text>
                        <Text as="p" variant="bodyMd" fontWeight="semibold">
                          {reviewMetricsData.metrics.funnel.converted} ({reviewMetricsData.metrics.funnel.conversion_rate}%)
                        </Text>
                      </BlockStack>
                    </InlineStack>
                  </BlockStack>

                  {/* Summary */}
                  <Box padding="300" background="bg-surface-secondary" borderRadius="200">
                    <Text as="p" variant="bodySm">
                      {reviewMetricsData.metrics.summary}
                    </Text>
                  </Box>

                  {/* Link to Full Dashboard */}
                  <InlineStack align="end">
                    <Button url="/app/review-dashboard" variant="plain">
                      View Full Review Dashboard
                    </Button>
                  </InlineStack>
                </BlockStack>
              ) : (
                <Text as="p" variant="bodySm" tone="subdued">
                  No review prompt data available yet. Prompts will be tracked once merchants start seeing them.
                </Text>
              )}
            </BlockStack>
          </Card>
        </Layout.AnnotatedSection>

        {/* Support & Feedback */}
        <Layout.AnnotatedSection
          id="support"
          title="Support & Feedback"
          description="Get help or submit feedback about TradeUp"
        >
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between" blockAlign="center">
                <BlockStack gap="100">
                  <InlineStack gap="200" blockAlign="center">
                    <Icon source={ChatIcon} tone="base" />
                    <Text as="h3" variant="headingSm">
                      Report an Issue or Request a Feature
                    </Text>
                  </InlineStack>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Let us know if you encounter any issues or have ideas for improvements.
                  </Text>
                </BlockStack>
                <Button onClick={() => setBugReportOpen(true)}>
                  Submit Feedback
                </Button>
              </InlineStack>

              <Divider />

              <BlockStack gap="200">
                <Text as="h3" variant="headingSm">Contact Support</Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  Need help? Reach out to our support team.
                </Text>
                <InlineStack gap="200">
                  <Button variant="plain" url="mailto:mike@orbsportscards.com" external>
                    Email Support
                  </Button>
                  <Button variant="plain" url="https://docs.tradeup.io" external>
                    Documentation
                  </Button>
                </InlineStack>
              </BlockStack>
            </BlockStack>
          </Card>
        </Layout.AnnotatedSection>

        {/* Danger Zone */}
        <Layout.AnnotatedSection
          id="danger"
          title="Danger Zone"
          description="Irreversible actions"
        >
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between" blockAlign="center">
                <BlockStack gap="100">
                  <Text as="h3" variant="headingSm">
                    Reset Program Data
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    This will delete all members and trade-in history. This action cannot be undone.
                  </Text>
                </BlockStack>
                <Button variant="primary" tone="critical" disabled>
                  Reset Data
                </Button>
              </InlineStack>
            </BlockStack>
          </Card>
        </Layout.AnnotatedSection>
      </Layout>

      {/* Tier Edit Modal */}
      <Modal
        open={tierModalOpen}
        onClose={closeTierModal}
        title={editingTier ? `Edit ${editingTier.name} Tier` : 'Create New Tier'}
        primaryAction={{
          content: editingTier ? 'Save Changes' : 'Create Tier',
          onAction: handleTierSubmit,
          loading: createTierMutation.isPending || updateTierMutation.isPending,
        }}
        secondaryActions={[
          { content: 'Cancel', onAction: closeTierModal },
        ]}
      >
        <Modal.Section>
          {tierError && (
            <Box paddingBlockEnd="400">
              <Banner tone="critical" onDismiss={() => setTierError('')}>
                <p>{tierError}</p>
              </Banner>
            </Box>
          )}
          <FormLayout>
            <TextField
              label="Tier Name"
              value={tierForm.name}
              onChange={(value) => setTierForm({ ...tierForm, name: value })}
              placeholder="Gold, Platinum, VIP, etc."
              autoComplete="off"
              requiredIndicator
            />

            <FormLayout.Group>
              <TextField
                label="Monthly Price"
                type="number"
                value={tierForm.monthly_price}
                onChange={(value) => setTierForm({ ...tierForm, monthly_price: value })}
                prefix="$"
                suffix="/mo"
                autoComplete="off"
                helpText="Set to 0 for free tier"
              />
              <TextField
                label="Yearly Price"
                type="number"
                value={tierForm.yearly_price}
                onChange={(value) => setTierForm({ ...tierForm, yearly_price: value })}
                prefix="$"
                suffix="/yr"
                autoComplete="off"
                helpText="Optional discount for annual"
              />
            </FormLayout.Group>

            <Divider />

            <Text as="h3" variant="headingSm">
              Tier Benefits
            </Text>

            <TextField
              label="Trade-In Bonus"
              type="number"
              value={tierForm.bonus_rate}
              onChange={(value) => setTierForm({ ...tierForm, bonus_rate: value })}
              suffix="%"
              autoComplete="off"
              helpText="Extra percentage added to trade-in value. E.g., 5% bonus on $100 trade = $5 extra credit."
            />

            <TextField
              label="Purchase Cashback"
              type="number"
              value={tierForm.purchase_cashback_pct}
              onChange={(value) => setTierForm({ ...tierForm, purchase_cashback_pct: value })}
              suffix="%"
              autoComplete="off"
              helpText="Percentage of purchase total credited back"
            />

            <TextField
              label="Monthly Credit"
              type="number"
              value={tierForm.monthly_credit}
              onChange={(value) => setTierForm({ ...tierForm, monthly_credit: value })}
              prefix="$"
              suffix="/month"
              autoComplete="off"
              helpText="Fixed store credit awarded on 1st of each month"
            />

            <Select
              label="Credit Expiration"
              options={CREDIT_EXPIRATION_OPTIONS}
              value={tierForm.credit_expiration_days}
              onChange={(value) => setTierForm({ ...tierForm, credit_expiration_days: value })}
              helpText="How long before awarded credits expire"
            />

            <TextField
              label="Store Discount"
              type="number"
              value={tierForm.discount_percent}
              onChange={(value) => setTierForm({ ...tierForm, discount_percent: value })}
              suffix="%"
              autoComplete="off"
              helpText="Discount applied to all purchases (optional)"
            />

            <TextField
              label="Signup Bonus"
              type="number"
              value={tierForm.signup_bonus}
              onChange={(value) => setTierForm({ ...tierForm, signup_bonus: value })}
              prefix="$"
              autoComplete="off"
              helpText="One-time store credit bonus when member joins this tier"
            />

            <Divider />

            <Text as="h3" variant="headingSm">
              Feature Benefits
            </Text>

            <Checkbox
              label="Free Shipping"
              checked={tierForm.free_shipping}
              onChange={(value) => setTierForm({ ...tierForm, free_shipping: value })}
              helpText="Members get free shipping on all orders"
            />

            <Checkbox
              label="Early Access"
              checked={tierForm.early_access}
              onChange={(value) => setTierForm({ ...tierForm, early_access: value })}
              helpText="Early access to new product releases"
            />

            <Checkbox
              label="Exclusive Events"
              checked={tierForm.exclusive_events}
              onChange={(value) => setTierForm({ ...tierForm, exclusive_events: value })}
              helpText="Access to member-only events and sales"
            />

            <Checkbox
              label="Priority Support"
              checked={tierForm.priority_support}
              onChange={(value) => setTierForm({ ...tierForm, priority_support: value })}
              helpText="Priority customer support queue"
            />
          </FormLayout>
        </Modal.Section>
      </Modal>

      {/* Email Preview Modal */}
      <Modal
        open={emailPreviewOpen}
        onClose={() => setEmailPreviewOpen(false)}
        title={`Preview: ${selectedTemplate?.name || 'Email Template'}`}
        size="large"
        secondaryActions={[
          { content: 'Close', onAction: () => setEmailPreviewOpen(false) },
        ]}
      >
        <Modal.Section>
          <BlockStack gap="400">
            <Box padding="300" background="bg-surface-secondary" borderRadius="200">
              <InlineStack gap="200">
                <Text as="span" variant="bodySm" fontWeight="semibold">Subject:</Text>
                <Text as="span" variant="bodySm">{previewSubject}</Text>
              </InlineStack>
            </Box>
            <Box
              padding="400"
              background="bg-surface"
              borderRadius="200"
              borderWidth="025"
              borderColor="border"
            >
              <div
                dangerouslySetInnerHTML={{ __html: previewHtml }}
                style={{ fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif' }}
              />
            </Box>
            <Text as="p" variant="bodySm" tone="subdued">
              This is a preview with sample data. Actual emails will include real member information.
            </Text>
          </BlockStack>
        </Modal.Section>
      </Modal>

      {/* Send Test Email Modal */}
      <Modal
        open={emailTestOpen}
        onClose={() => {
          setEmailTestOpen(false);
          setEmailError('');
        }}
        title={`Send Test: ${selectedTemplate?.name || 'Email'}`}
        primaryAction={{
          content: 'Send Test Email',
          onAction: () => sendTestMutation.mutate(),
          loading: sendTestMutation.isPending,
          disabled: !testEmail,
        }}
        secondaryActions={[
          {
            content: 'Cancel',
            onAction: () => {
              setEmailTestOpen(false);
              setEmailError('');
            },
          },
        ]}
      >
        <Modal.Section>
          <BlockStack gap="400">
            {emailError && (
              <Banner tone="critical" onDismiss={() => setEmailError('')}>
                <p>{emailError}</p>
              </Banner>
            )}
            <Text as="p" variant="bodySm" tone="subdued">
              Send a test email to verify your email configuration is working correctly.
            </Text>
            <TextField
              label="Recipient Email"
              type="email"
              value={testEmail}
              onChange={setTestEmail}
              placeholder="you@example.com"
              autoComplete="email"
              requiredIndicator
            />
            <TextField
              label="Recipient Name"
              value={testName}
              onChange={setTestName}
              placeholder="John Doe"
              autoComplete="name"
              helpText="Name used in the email greeting"
            />
          </BlockStack>
        </Modal.Section>
      </Modal>

      {/* Delete Tier Confirmation Modal */}
      <Modal
        open={tierToDelete !== null}
        onClose={() => setTierToDelete(null)}
        title="Delete tier?"
        primaryAction={{
          content: 'Delete',
          destructive: true,
          onAction: () => {
            if (tierToDelete) {
              deleteTierMutation.mutate(tierToDelete.id);
              setTierToDelete(null);
            }
          },
          loading: deleteTierMutation.isPending,
        }}
        secondaryActions={[
          { content: 'Cancel', onAction: () => setTierToDelete(null) },
        ]}
      >
        <Modal.Section>
          <Text as="p">
            Are you sure you want to delete the "{tierToDelete?.name}" tier? This action cannot be undone.
          </Text>
        </Modal.Section>
      </Modal>

      {/* Shopify App Bridge Save Bar */}
      <SaveBar id="settings-save-bar">
        <button variant="primary" onClick={handleSave} disabled={updateMutation.isPending}>
          {updateMutation.isPending ? 'Saving...' : 'Save'}
        </button>
        <button onClick={handleDiscard}>Discard</button>
      </SaveBar>

      {/* Test Nudge Modal (NR-006) */}
      <Modal
        open={nudgeTestOpen}
        onClose={() => {
          setNudgeTestOpen(false);
          setNudgeError('');
        }}
        title={`Send Test: ${selectedNudgeType ? NUDGE_TYPE_LABELS[selectedNudgeType]?.label || selectedNudgeType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'Nudge'}`}
        primaryAction={{
          content: 'Send Test Nudge',
          onAction: () => sendTestNudgeMutation.mutate(),
          loading: sendTestNudgeMutation.isPending,
        }}
        secondaryActions={[
          {
            content: 'Cancel',
            onAction: () => {
              setNudgeTestOpen(false);
              setNudgeError('');
            },
          },
        ]}
      >
        <Modal.Section>
          <BlockStack gap="400">
            {nudgeError && (
              <Banner tone="critical" onDismiss={() => setNudgeError('')}>
                <p>{nudgeError}</p>
              </Banner>
            )}
            <Text as="p" variant="bodySm" tone="subdued">
              Send a test nudge to verify your configuration. The test will use sample data
              and will be clearly marked as a test message.
            </Text>
            <TextField
              label="Recipient Email"
              type="email"
              value={nudgeTestEmail}
              onChange={setNudgeTestEmail}
              placeholder="you@example.com (defaults to store email)"
              autoComplete="email"
              helpText="Leave blank to send to your store's email address"
            />
            <TextField
              label="Recipient Name"
              value={nudgeTestName}
              onChange={setNudgeTestName}
              placeholder="Store Owner"
              autoComplete="name"
              helpText="Name used in the greeting"
            />
          </BlockStack>
        </Modal.Section>
      </Modal>

      {/* Bug Report Modal */}
      <BugReportModal
        open={bugReportOpen}
        onClose={() => setBugReportOpen(false)}
      />
    </Page>
  );
}
