/**
 * TradeUp Admin API Client
 * Handles all admin operations: members, events, Shopify lookups
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000';

// Helper for authenticated requests
async function adminFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem('admin_token');

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-ID': '1', // ORB Sports Cards tenant
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(error.error || error.message || 'Request failed');
  }

  return response.json();
}

// ================== Types ==================

export interface Member {
  id: number;
  member_number: string;
  email: string;
  name: string | null;
  phone: string | null;
  tier_id: number | null;
  tier: Tier | null;
  shopify_customer_id: string | null;
  status: 'active' | 'pending' | 'paused' | 'cancelled';
  membership_start_date: string;
  membership_end_date: string | null;
  total_credit_earned: number;
  total_trade_ins: number;
  total_trade_value: number;
  created_at: string;
  updated_at: string;
}

export interface Tier {
  id: number;
  name: string;
  monthly_price: number;
  bonus_rate: number;
  benefits: Record<string, unknown>;
}

export interface ShopifyCustomer {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  phone: string | null;
  tags: string[];
  ordersCount: number;
  totalSpent: number;
  storeCreditBalance: number;
  currency: string;
  createdAt: string;
}

export interface StoreCreditEvent {
  id: string;
  name: string;
  description?: string;
  credit_amount: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  filters: EventFilters;
  customers_affected?: number;
  total_credited?: number;
  created_at: string;
  executed_at?: string;
  created_by?: string;
}

export interface EventFilters {
  date_range?: { start: string; end: string };
  sources?: string[];
  collections?: string[];
  product_tags?: string[];
  customer_tags?: string[];
  tiers?: string[];
  min_spend?: number;
}

export interface EventPreview {
  customer_count: number;
  total_credit: number;
  breakdown_by_tier?: Record<string, number>;
  sample_customers?: {
    id: string;
    email: string;
    name?: string;
    tier?: string;
  }[];
}

export interface EventRunResult {
  success: boolean;
  event_id: string;
  customers_processed: number;
  total_credited: number;
  errors?: string[];
}

export interface ShopifyCollection {
  id: string;
  title: string;
  handle: string;
  productsCount: number;
}

export interface DashboardStats {
  total_members: number;
  active_members: number;
  members_this_month: number;
  total_events_this_month: number;
  total_credited_this_month: number;
  members_by_tier: Record<string, number>;
  recent_activity: ActivityItem[];
}

export interface ActivityItem {
  id: string;
  type: 'member_joined' | 'member_upgraded' | 'event_completed' | 'credit_issued';
  description: string;
  timestamp: string;
  meta: Record<string, unknown>;
}

// ================== Member APIs ==================

export async function getMembers(params?: {
  page?: number;
  limit?: number;
  search?: string;
  status?: string;
  tier_id?: number;
}): Promise<{ members: Member[]; total: number; page: number; pages: number }> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set('page', String(params.page));
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.search) searchParams.set('search', params.search);
  if (params?.status) searchParams.set('status', params.status);
  if (params?.tier_id) searchParams.set('tier_id', String(params.tier_id));

  return adminFetch(`/api/members?${searchParams}`);
}

export async function getMember(id: number): Promise<Member> {
  return adminFetch(`/api/members/${id}`);
}

export async function createMember(data: {
  email: string;
  name?: string;
  phone?: string;
  tier_id?: number;
  shopify_customer_id?: string;
  notes?: string;
}): Promise<Member> {
  return adminFetch('/api/members', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateMember(
  id: number,
  data: Partial<Member>
): Promise<Member> {
  return adminFetch(`/api/members/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function updateMemberTier(
  memberId: number,
  tierId: number
): Promise<Member> {
  return adminFetch(`/api/members/${memberId}/tier`, {
    method: 'PUT',
    body: JSON.stringify({ tier_id: tierId }),
  });
}

// ================== Tier APIs ==================

export async function getTiers(): Promise<{ tiers: Tier[] }> {
  return adminFetch('/api/membership/tiers');
}

// ================== Shopify APIs ==================

export async function lookupShopifyCustomer(
  email: string
): Promise<ShopifyCustomer | null> {
  try {
    const result = await adminFetch<{ customer: ShopifyCustomer | null }>(
      `/api/admin/shopify/customer?email=${encodeURIComponent(email)}`
    );
    return result.customer;
  } catch {
    return null;
  }
}

export async function getShopifyCollections(): Promise<ShopifyCollection[]> {
  const result = await adminFetch<{ collections: ShopifyCollection[] }>(
    '/api/admin/shopify/collections'
  );
  return result.collections;
}

export async function getShopifyProductTags(): Promise<string[]> {
  const result = await adminFetch<{ tags: string[] }>(
    '/api/admin/shopify/product-tags'
  );
  return result.tags;
}

// ================== Store Credit Event APIs ==================

export async function getStoreCreditEvents(params?: {
  page?: number;
  limit?: number;
  status?: string;
}): Promise<{ events: StoreCreditEvent[]; total: number; page: number; pages: number }> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set('page', String(params.page));
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.status) searchParams.set('status', params.status);

  return adminFetch(`/api/admin/events?${searchParams}`);
}

export async function previewEvent(params: {
  credit_amount: number;
  filters: EventFilters;
}): Promise<EventPreview> {
  return adminFetch('/api/admin/events/preview', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function runEvent(params: {
  name: string;
  description?: string;
  credit_amount: number;
  filters: EventFilters;
}): Promise<EventRunResult> {
  return adminFetch('/api/admin/events/run', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

// ================== Filter Option APIs ==================

export async function getCollections(): Promise<{ collections: { id: string; title: string }[] }> {
  return adminFetch('/api/admin/shopify/collections');
}

export async function getProductTags(): Promise<{ tags: string[] }> {
  return adminFetch('/api/admin/shopify/product-tags');
}

export async function getCustomerTags(): Promise<{ tags: string[] }> {
  return adminFetch('/api/admin/shopify/customer-tags');
}

// ================== Dashboard APIs ==================

export async function getDashboardStats(): Promise<DashboardStats> {
  return adminFetch('/api/admin/dashboard');
}

// ================== Admin Auth ==================

export async function adminLogin(credentials: {
  email: string;
  password: string;
}): Promise<{ token: string; admin: { email: string; name: string } }> {
  const result = await adminFetch<{
    token: string;
    admin: { email: string; name: string };
  }>('/api/admin/login', {
    method: 'POST',
    body: JSON.stringify(credentials),
  });

  localStorage.setItem('admin_token', result.token);
  return result;
}

export function adminLogout(): void {
  localStorage.removeItem('admin_token');
}

export function isAdminLoggedIn(): boolean {
  return !!localStorage.getItem('admin_token');
}

// ================== Trade-In Types ==================

export interface TradeInBatch {
  id: number;
  member_id: number;
  member_number: string;
  member_name: string | null;
  member_tier: string | null;
  batch_reference: string;
  trade_in_date: string;
  total_items: number;
  total_trade_value: number;
  bonus_amount: number;
  status: 'pending' | 'listed' | 'completed' | 'cancelled';
  category: string;
  notes: string | null;
  created_by: string | null;
  created_at: string;
  completed_at: string | null;
  completed_by: string | null;
  items?: TradeInItem[];
}

export interface TradeInItem {
  id: number;
  batch_id: number;
  shopify_product_id: string | null;
  product_title: string | null;
  product_sku: string | null;
  trade_value: number;
  market_value: number | null;
  listing_price: number | null;
  listed_date: string | null;
  sold_date: string | null;
  sold_price: number | null;
  days_to_sell: number | null;
}

export interface TradeInCategory {
  id: string;
  icon: string;
  name: string;
}

export interface BonusPreview {
  batch_id: number;
  batch_reference: string;
  status: string;
  total_items: number;
  trade_value: number;
  bonus: {
    eligible: boolean;
    reason: string;
    tier_name: string | null;
    tier_id?: number;
    bonus_percent: number;
    bonus_rate?: number;
    bonus_amount: number;
    trade_value: number;
  };
}

export interface CompleteResult {
  success: boolean;
  batch_id: number;
  batch_reference: string;
  trade_value: number;
  bonus: {
    eligible: boolean;
    reason: string;
    tier_name: string | null;
    bonus_percent: number;
    bonus_amount: number;
  };
  member: {
    id: number;
    member_number: string;
    total_credit_earned: number;
  };
}

// ================== Trade-In APIs ==================

export async function getTradeInBatches(params?: {
  page?: number;
  per_page?: number;
  status?: string;
  member_id?: number;
}): Promise<{ batches: TradeInBatch[]; total: number; page: number; per_page: number }> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set('page', String(params.page));
  if (params?.per_page) searchParams.set('per_page', String(params.per_page));
  if (params?.status) searchParams.set('status', params.status);
  if (params?.member_id) searchParams.set('member_id', String(params.member_id));

  return adminFetch(`/api/trade-ins?${searchParams}`);
}

export async function getTradeInBatch(batchId: number): Promise<TradeInBatch> {
  return adminFetch(`/api/trade-ins/${batchId}`);
}

export async function getTradeInCategories(): Promise<{ categories: TradeInCategory[] }> {
  return adminFetch('/api/trade-ins/categories');
}

export async function createTradeInBatch(data: {
  member_id: number;
  category?: string;
  notes?: string;
  created_by?: string;
}): Promise<TradeInBatch> {
  return adminFetch('/api/trade-ins', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function addTradeInItems(
  batchId: number,
  items: {
    product_title?: string;
    product_sku?: string;
    trade_value: number;
    market_value?: number;
    notes?: string;
  }[]
): Promise<{ items: TradeInItem[]; batch: TradeInBatch }> {
  return adminFetch(`/api/trade-ins/${batchId}/items`, {
    method: 'POST',
    body: JSON.stringify({ items }),
  });
}

export async function previewBatchBonus(batchId: number): Promise<BonusPreview> {
  return adminFetch(`/api/trade-ins/${batchId}/preview-bonus`);
}

export async function completeBatch(
  batchId: number,
  createdBy?: string
): Promise<CompleteResult> {
  return adminFetch(`/api/trade-ins/${batchId}/complete`, {
    method: 'POST',
    body: JSON.stringify({ created_by: createdBy }),
  });
}

// ================== Settings Types ==================

export interface AutoEnrollmentSettings {
  enabled: boolean;
  default_tier_id: number | null;
  min_order_value: number;
  excluded_tags: string[];
}

export interface NotificationSettings {
  enabled: boolean;
  welcome_email: boolean;
  trade_in_updates: boolean;
  tier_change: boolean;
  credit_issued: boolean;
  from_name: string | null;
  from_email: string | null;
}

export interface BrandingSettings {
  app_name: string;
  tagline: string;
  logo_url: string | null;
  logo_dark_url: string | null;
  colors: {
    primary: string;
    primary_hover: string;
    secondary: string;
    accent: string;
  };
  style: 'glass' | 'solid' | 'minimal';
}

export interface TenantSettings {
  branding: BrandingSettings;
  features: {
    points_enabled: boolean;
    referrals_enabled: boolean;
    self_signup_enabled: boolean;
  };
  auto_enrollment: AutoEnrollmentSettings;
  notifications: NotificationSettings;
  contact: {
    support_email: string | null;
    support_phone: string | null;
  };
}

// ================== Settings APIs ==================

export async function getSettings(): Promise<{
  settings: TenantSettings;
  tenant: { id: number; shop_name: string; shop_slug: string };
}> {
  return adminFetch('/api/settings');
}

export async function updateSettings(
  settings: Partial<TenantSettings>
): Promise<{ success: boolean; settings: TenantSettings }> {
  return adminFetch('/api/settings', {
    method: 'PATCH',
    body: JSON.stringify(settings),
  });
}

export async function updateAutoEnrollment(
  settings: Partial<AutoEnrollmentSettings>
): Promise<{ success: boolean; settings: TenantSettings }> {
  return adminFetch('/api/settings', {
    method: 'PATCH',
    body: JSON.stringify({ auto_enrollment: settings }),
  });
}

export async function updateNotifications(
  settings: Partial<NotificationSettings>
): Promise<{ success: boolean; settings: TenantSettings }> {
  return adminFetch('/api/settings', {
    method: 'PATCH',
    body: JSON.stringify({ notifications: settings }),
  });
}
