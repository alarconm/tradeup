import axios from 'axios'

// Use relative URL in development (goes through Vite proxy) or env-provided URL in production
const API_BASE = import.meta.env.VITE_API_URL || ''

// Get shop domain from URL params, localStorage, or env for development
function getShopDomain(): string | null {
  // Check URL params first (Shopify embeds include ?shop=xxx)
  const urlParams = new URLSearchParams(window.location.search)
  const shopFromUrl = urlParams.get('shop')
  if (shopFromUrl) {
    localStorage.setItem('shopify_shop', shopFromUrl)
    return shopFromUrl
  }

  // Check localStorage (persisted from previous visit)
  const shopFromStorage = localStorage.getItem('shopify_shop')
  if (shopFromStorage) return shopFromStorage

  // Development fallback
  const devShop = import.meta.env.VITE_SHOPIFY_SHOP
  if (devShop) return devShop

  // Default for local development testing
  if (import.meta.env.DEV) {
    return 'uy288y-nx.myshopify.com'
  }

  return null
}

export const api = axios.create({
  baseURL: `${API_BASE}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add shop domain and tenant ID to all requests
api.interceptors.request.use((config) => {
  const shop = getShopDomain()
  if (shop) {
    config.headers['X-Shopify-Shop-Domain'] = shop
  }
  // Also send X-Tenant-ID for endpoints that use it directly
  // Default to 1 for development (matches most endpoint defaults)
  config.headers['X-Tenant-ID'] = '1'
  return config
})

// API Error type for standardized error responses
export interface ApiError {
  message: string
  code: string
}

// Extract user-friendly error message from API response
export function getErrorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'response' in error) {
    const response = (error as { response?: { data?: { error?: ApiError | string } } }).response
    if (response?.data?.error) {
      // New standardized format: { error: { message: '...', code: '...' } }
      if (typeof response.data.error === 'object' && 'message' in response.data.error) {
        return response.data.error.message
      }
      // Legacy format: { error: '...' }
      if (typeof response.data.error === 'string') {
        return response.data.error
      }
    }
  }
  // Fallback for network errors or unknown errors
  if (error instanceof Error) {
    return error.message
  }
  return 'An unexpected error occurred'
}

// Get error code from API response (for programmatic handling)
export function getErrorCode(error: unknown): string | null {
  if (error && typeof error === 'object' && 'response' in error) {
    const response = (error as { response?: { data?: { error?: ApiError } } }).response
    if (response?.data?.error && typeof response.data.error === 'object') {
      return response.data.error.code || null
    }
  }
  return null
}

// Types
export interface Member {
  id: number
  shopify_customer_id: string
  email: string
  first_name: string | null
  last_name: string | null
  full_name: string
  phone: string | null
  tier: 'SILVER' | 'GOLD' | 'PLATINUM'
  status: 'active' | 'paused' | 'cancelled' | 'past_due'
  discount_percentage: number
  monthly_price: number
  joined_at: string | null
  current_period_start: string | null
  tier_assigned_by: string | null
  tier_assigned_at: string | null
  tier_expires_at: string | null
  subscription_status: string
}

export interface DashboardStats {
  total_members: number
  active_members: number
  paused_members: number
  cancelled_members: number
  past_due_members: number
  tier_breakdown: Record<string, number>
  new_members_30d: number
  needs_card_setup: number
  mrr: number
}

export interface MemberListResponse {
  members: Member[]
  total: number
  limit: number
  offset: number
}

// API Functions
export const getStats = () =>
  api.get<DashboardStats>('/admin/stats').then(r => r.data)

export const getMembers = (params?: {
  status?: string
  tier?: string
  search?: string
  sort?: string
  order?: string
  limit?: number
  offset?: number
}) => api.get<MemberListResponse>('/admin/members', { params }).then(r => r.data)

export const getMember = (id: number) =>
  api.get<Member>(`/admin/members/${id}`).then(r => r.data)

export const createMember = (data: {
  email: string
  first_name?: string
  last_name?: string
  phone?: string
  tier?: string
  shopify_customer_id?: string
}) => api.post<Member>('/admin/members', data).then(r => r.data)

export const updateMember = (id: number, data: Partial<Member>) =>
  api.patch<Member>(`/admin/members/${id}`, data).then(r => r.data)

export const resendWelcomeEmail = (id: number) =>
  api.post<{ sent: boolean }>(`/admin/members/${id}/resend-welcome`).then(r => r.data)

export const getMembersNeedingCardSetup = () =>
  api.get<{ members: Member[]; total: number }>('/admin/members/needs-card-setup').then(r => r.data)

export const getMembersExpiringSoon = () =>
  api.get<{ members: Member[]; total: number }>('/admin/members/expiring-soon').then(r => r.data)

// ==================== Trade-In Types ====================

export interface TradeInCategory {
  id: number
  name: string
  description: string | null
  icon: string
  color: string
  base_payout_pct: number
  min_value: number
  bulk_bonus_eligible: boolean
  active: boolean
  display_order: number
}

export interface TradeInItem {
  id: number
  tradein_id: number
  category_id: number
  category_name: string | null
  name: string
  set_name: string | null
  collector_number: string | null
  variant: string | null
  condition: string
  quantity: number
  market_value: number
  total_market_value: number
  condition_modifier: number
  category_payout_pct: number
  payout_value: number
  total_payout_value: number
  price_source: string
  price_verified: boolean
  notes: string | null
}

export interface TradeIn {
  id: number
  reference: string
  member_id: number
  member_name: string | null
  member_email: string | null
  member_tier_at_trade: string | null
  status: 'draft' | 'pending_review' | 'approved' | 'completed' | 'rejected' | 'cancelled'
  item_count: number
  subtotal_market_value: number
  subtotal_base_payout: number
  tier_bonus_pct: number
  tier_bonus_amount: number
  bulk_bonus_pct: number
  bulk_bonus_amount: number
  adjustment_amount: number
  adjustment_reason: string | null
  total_credit: number
  credit_type: string | null
  credit_issued_at: string | null
  staff_notes: string | null
  created_by: string | null
  reviewed_by: string | null
  reviewed_at: string | null
  created_at: string | null
  updated_at: string | null
  items?: TradeInItem[]
}

export interface ConditionInfo {
  code: string
  name: string
  modifier: number
}

export interface TradeInStats {
  by_status: Record<string, number>
  pending_review: number
  drafts: number
  completed_30d: {
    count: number
    total_credit: number
    total_items: number
  }
  top_categories: Array<{
    name: string
    item_count: number
    total_value: number
  }>
}

// ==================== Trade-In Category API ====================

export const getTradeInCategories = (activeOnly = false) =>
  api.get<{ categories: TradeInCategory[]; total: number }>(
    '/tradein/categories',
    { params: { active_only: activeOnly } }
  ).then(r => r.data)

export const createTradeInCategory = (data: Partial<TradeInCategory>) =>
  api.post<TradeInCategory>('/tradein/categories', data).then(r => r.data)

export const updateTradeInCategory = (id: number, data: Partial<TradeInCategory>) =>
  api.put<TradeInCategory>(`/tradein/categories/${id}`, data).then(r => r.data)

export const deleteTradeInCategory = (id: number) =>
  api.delete(`/tradein/categories/${id}`).then(r => r.data)

export const reorderTradeInCategories = (order: number[]) =>
  api.post('/tradein/categories/reorder', { order }).then(r => r.data)

// ==================== Trade-In API ====================

export const getTradeIns = (params?: {
  status?: string
  member_id?: number
  search?: string
  date_from?: string
  date_to?: string
  sort?: string
  order?: string
  limit?: number
  offset?: number
}) =>
  api.get<{ tradeins: TradeIn[]; total: number; limit: number; offset: number }>(
    '/tradein/tradeins',
    { params }
  ).then(r => r.data)

export const getTradeIn = (id: number) =>
  api.get<TradeIn>(`/tradein/tradeins/${id}`).then(r => r.data)

export const createTradeIn = (data: {
  member_id: number
  staff_notes?: string
  created_by?: string
}) =>
  api.post<TradeIn>('/tradein/tradeins', data).then(r => r.data)

export const updateTradeIn = (id: number, data: {
  staff_notes?: string
  adjustment_amount?: number
  adjustment_reason?: string
}) =>
  api.patch<{ item: TradeInItem; tradein: TradeIn }>(`/tradein/tradeins/${id}`, data).then(r => r.data)

// Trade-In Items
export const addTradeInItem = (tradeinId: number, data: {
  category_id: number
  name: string
  set_name?: string
  collector_number?: string
  variant?: string
  condition?: string
  quantity?: number
  market_value: number
  price_source?: string
  notes?: string
}) =>
  api.post<{ item: TradeInItem; tradein: TradeIn }>(
    `/tradein/tradeins/${tradeinId}/items`,
    data
  ).then(r => r.data)

export const updateTradeInItem = (tradeinId: number, itemId: number, data: Partial<TradeInItem>) =>
  api.put<{ item: TradeInItem; tradein: TradeIn }>(
    `/tradein/tradeins/${tradeinId}/items/${itemId}`,
    data
  ).then(r => r.data)

export const deleteTradeInItem = (tradeinId: number, itemId: number) =>
  api.delete<{ deleted: boolean; tradein: TradeIn }>(
    `/tradein/tradeins/${tradeinId}/items/${itemId}`
  ).then(r => r.data)

// Trade-In Workflow
export const submitTradeIn = (id: number) =>
  api.post<TradeIn>(`/tradein/tradeins/${id}/submit`).then(r => r.data)

export const approveTradeIn = (id: number, reviewedBy?: string) =>
  api.post<TradeIn>(`/tradein/tradeins/${id}/approve`, { reviewed_by: reviewedBy }).then(r => r.data)

export const rejectTradeIn = (id: number, data: { reviewed_by?: string; reason?: string }) =>
  api.post<TradeIn>(`/tradein/tradeins/${id}/reject`, data).then(r => r.data)

export const completeTradeIn = (id: number, data: {
  credit_type: 'gift_card' | 'store_credit' | 'cash'
  completed_by?: string
}) =>
  api.post<TradeIn>(`/tradein/tradeins/${id}/complete`, data).then(r => r.data)

export const cancelTradeIn = (id: number, reason?: string) =>
  api.post<TradeIn>(`/tradein/tradeins/${id}/cancel`, { reason }).then(r => r.data)

// Trade-In Stats & Utils
export const getTradeInStats = () =>
  api.get<TradeInStats>('/tradein/stats').then(r => r.data)

export const getConditions = () =>
  api.get<{
    conditions: ConditionInfo[]
    bulk_bonuses: Array<{ threshold: number; bonus_pct: number }>
    tier_bonuses: Array<{ tier: string; bonus_pct: number }>
  }>('/tradein/conditions').then(r => r.data)

export const calculatePayout = (data: {
  member_tier: string
  items: Array<{
    category_id: number
    name?: string
    market_value: number
    condition: string
    quantity: number
  }>
}) =>
  api.post<{
    items: Array<{
      name: string
      category: string
      market_value: number
      condition: string
      condition_modifier: number
      category_payout_pct: number
      quantity: number
      payout_per_unit: number
      total_payout: number
    }>
    summary: {
      item_count: number
      total_market_value: number
      subtotal_base_payout: number
      tier: string
      tier_bonus_pct: number
      tier_bonus_amount: number
      bulk_bonus_pct: number
      bulk_bonus_amount: number
      total_credit: number
    }
  }>('/tradein/calculate-payout', data).then(r => r.data)

// ==================== Promotions Types ====================

export type PromotionType = 'trade_in_bonus' | 'purchase_cashback' | 'flat_bonus' | 'multiplier'
export type PromotionChannel = 'all' | 'in_store' | 'online'

export interface Promotion {
  id: number
  name: string
  description: string | null
  code: string | null
  promo_type: PromotionType
  bonus_percent: number
  bonus_flat: number
  multiplier: number
  starts_at: string
  ends_at: string
  daily_start_time: string | null
  daily_end_time: string | null
  active_days: string | null
  channel: PromotionChannel
  // Shopify-based product filters
  collection_ids: string[] | null
  vendor_filter: string[] | null
  product_type_filter: string[] | null
  product_tags_filter: string[] | null
  // Legacy category filter (now uses product_tags_filter)
  category_ids: string[] | null
  // Member restrictions
  tier_restriction: string[] | null
  min_items: number
  min_value: number
  stackable: boolean
  priority: number
  max_uses: number | null
  max_uses_per_member: number | null
  current_uses: number
  active: boolean
  is_active_now: boolean
  created_by: string | null
  created_at: string | null
}

export interface StoreCreditLedgerEntry {
  id: number
  member_id: number
  event_type: string
  amount: number
  balance_after: number
  description: string
  source_type: string | null
  source_id: string | null
  source_reference: string | null
  promotion_id: number | null
  promotion_name: string | null
  channel: string | null
  created_by: string | null
  created_at: string | null
  expires_at: string | null
  synced_to_shopify: boolean
}

export interface MemberCreditBalance {
  member_id: number
  total_balance: number
  available_balance: number
  pending_balance: number
  total_earned: number
  total_spent: number
  cashback_earned: number
  trade_in_earned: number
  promo_bonus_earned: number
  last_credit_at: string | null
  last_redemption_at: string | null
}

export interface BulkCreditOperation {
  id: number
  name: string
  description: string | null
  amount_per_member: number
  total_amount: number
  member_count: number | null
  tier_filter: string | null
  status_filter: string | null
  status: 'pending' | 'processing' | 'completed' | 'failed'
  created_by: string
  created_at: string
  completed_at: string | null
}

export interface TierConfiguration {
  id: number
  tier_name: string
  monthly_price: number
  trade_in_bonus_pct: number
  purchase_cashback_pct: number
  store_discount_pct: number
  display_order: number
  color: string
  icon: string
  badge_text: string | null
  features: string[]
  active: boolean
}

export interface PromotionTemplate {
  name: string
  description: string
  promo_type: PromotionType
  bonus_percent?: number
  bonus_flat?: number
  multiplier?: number
  channel?: PromotionChannel
}

// ==================== Promotions API ====================

export const getPromotions = (params?: {
  active_only?: boolean
  promo_type?: string
  limit?: number
  offset?: number
}) =>
  api.get<{ promotions: Promotion[]; total: number }>(
    '/promotions/promotions',
    { params }
  ).then(r => r.data)

export const getPromotion = (id: number) =>
  api.get<Promotion>(`/promotions/promotions/${id}`).then(r => r.data)

export const createPromotion = (data: Partial<Promotion>) =>
  api.post<Promotion>('/promotions/promotions', data).then(r => r.data)

export const updatePromotion = (id: number, data: Partial<Promotion>) =>
  api.put<Promotion>(`/promotions/promotions/${id}`, data).then(r => r.data)

export const deletePromotion = (id: number) =>
  api.delete(`/promotions/promotions/${id}`).then(r => r.data)

export const getPromotionTemplates = () =>
  api.get<{ templates: PromotionTemplate[] }>('/promotions/promotions/templates').then(r => r.data)

// Promotion Filter Options (Shopify-based)
interface PromotionFilterOptions {
  collections: Array<{
    id: string
    title: string
    handle: string
    productsCount: number
    isSmart: boolean
  }>
  vendors: string[]
  productTypes: string[]
  productTags: string[]
}

export const getPromotionFilterOptions = () =>
  api.get<PromotionFilterOptions>('/promotions/filter-options').then(r => r.data)

// ==================== Store Credit API ====================

export const getMemberCreditBalance = (memberId: number) =>
  api.get<{ balance: MemberCreditBalance; transactions: StoreCreditLedgerEntry[] }>(
    `/promotions/credit/balance/${memberId}`
  ).then(r => r.data)

export const addCredit = (data: {
  member_id: number
  amount: number
  description: string
  created_by?: string
}) =>
  api.post<StoreCreditLedgerEntry>('/promotions/credit/add', data).then(r => r.data)

export const deductCredit = (data: {
  member_id: number
  amount: number
  description: string
  created_by?: string
}) =>
  api.post<StoreCreditLedgerEntry>('/promotions/credit/deduct', data).then(r => r.data)

// ==================== Bulk Credit API ====================

export const createBulkCreditOperation = (data: {
  name: string
  description?: string
  amount_per_member: number
  tier_filter?: string
  created_by: string
}) =>
  api.post<BulkCreditOperation>('/promotions/credit/bulk', data).then(r => r.data)

export const previewBulkCredit = (id: number) =>
  api.get<{
    member_count: number
    total_amount: number
    members: Array<{ id: number; email: string; tier: string }>
  }>(`/promotions/credit/bulk/${id}/preview`).then(r => r.data)

export const executeBulkCredit = (id: number) =>
  api.post<{ status: string; member_count: number; total_amount: number }>(
    `/promotions/credit/bulk/${id}/execute`
  ).then(r => r.data)

export const getBulkCreditOperations = (params?: {
  status?: string
  limit?: number
  offset?: number
}) =>
  api.get<{ operations: BulkCreditOperation[]; total: number }>(
    '/promotions/credit/bulk',
    { params }
  ).then(r => r.data)

// ==================== Tier Configuration API ====================

export const getTierConfigurations = () =>
  api.get<{ tiers: TierConfiguration[] }>('/promotions/tiers').then(r => r.data)

export const updateTierConfiguration = (tierName: string, data: Partial<TierConfiguration>) =>
  api.put<TierConfiguration>(`/promotions/tiers/${tierName}`, data).then(r => r.data)

// ==================== Dashboard Stats ====================

export const getPromotionsStats = () =>
  api.get<{
    active_promotions: number
    promotions_ending_soon: number
    total_cashback_30d: number
    total_bulk_credits_30d: number
    credit_by_type: Record<string, number>
  }>('/promotions/dashboard/stats').then(r => r.data)

// ==================== Onboarding Types ====================

export interface OnboardingStep {
  id: number
  name: string
  description: string
  status: 'complete' | 'pending' | 'in_progress'
  action: string | null
}

export interface OnboardingStatus {
  setup_complete: boolean
  current_step: number
  steps: OnboardingStep[]
  subscription_plan: string
  subscription_active: boolean
}

export interface StoreCreditCheck {
  enabled: boolean
  status: 'ready' | 'not_enabled' | 'error'
  message: string
  instructions?: string[]
  settings_url?: string
  shop_name?: string
  currency?: string
}

export interface TierTemplateTier {
  name: string
  slug: string
  trade_in_rate: number
  monthly_fee: number
  color: string
  icon: string
  benefits: string[]
  is_default?: boolean
  min_spend_requirement?: number
}

export interface TierTemplate {
  key: string
  name: string
  description: string
  tier_count: number
  tiers: TierTemplateTier[]
}

export interface TemplateApplyResult {
  success: boolean
  template: string
  tiers_created: number
  tiers: Array<{
    id: number
    name: string
    slug: string
    trade_in_rate: number
  }>
}

// ==================== Onboarding API ====================

export const getOnboardingStatus = () =>
  api.get<OnboardingStatus>('/onboarding/status').then(r => r.data)

export const checkStoreCredit = () =>
  api.get<StoreCreditCheck>('/onboarding/store-credit-check').then(r => r.data)

export const getOnboardingTemplates = () =>
  api.get<{
    templates: TierTemplate[]
    subscription_plan: string
    can_upgrade: boolean
  }>('/onboarding/templates').then(r => r.data)

export const previewTemplate = (templateKey: string) =>
  api.get<TierTemplate>(`/onboarding/templates/${templateKey}/preview`).then(r => r.data)

export const applyTemplate = (templateKey: string) =>
  api.post<TemplateApplyResult>(`/onboarding/templates/${templateKey}/apply`).then(r => r.data)

export const completeOnboarding = () =>
  api.post<{ success: boolean; message: string }>('/onboarding/complete').then(r => r.data)

export const skipOnboarding = () =>
  api.post<{ success: boolean; message: string }>('/onboarding/skip').then(r => r.data)

// ==================== Review Prompt API ====================

export interface ReviewPromptTimingContext {
  can_show: boolean
  blocking_reasons: string[]
  context: string
  session_count: number
  min_sessions_required: number
  is_in_onboarding: boolean
  is_optimal_time: boolean
  timezone_offset_hours: number | null
  optimal_hours: string
  eligibility: {
    eligible: boolean
    reason: string
    criteria: Record<string, unknown>
  }
}

export interface ReviewPromptCheck {
  should_show: boolean
  timing_context?: ReviewPromptTimingContext
  eligibility?: {
    eligible: boolean
    criteria: Record<string, unknown>
    reason: string
  }
  prompt_id?: number
  reason?: string
}

export interface ReviewPromptResponse {
  success: boolean
  prompt_id?: number
  response?: string
  error?: string
}

export interface ReviewPromptCheckOptions {
  context?: 'dashboard' | 'trade_in_approved' | 'member_enrolled' | 'onboarding'
  timezoneOffset?: number
  hasError?: boolean
}

export interface SessionCountResponse {
  success: boolean
  session_count: number
  min_sessions_required: number
  has_sufficient_sessions: boolean
}

/**
 * Check if a review prompt should be shown to the merchant.
 *
 * Story RC-006: Implements timing logic to show prompts at optimal times:
 * - Not during onboarding
 * - Not after errors
 * - After 5+ successful sessions on dashboard
 * - During optimal hours (9am-5pm local time)
 *
 * @param options - Optional timing parameters
 * @returns ReviewPromptCheck with should_show and timing_context
 */
export const checkReviewPrompt = (options?: ReviewPromptCheckOptions) => {
  const params = new URLSearchParams()
  if (options?.context) params.append('context', options.context)
  if (options?.timezoneOffset !== undefined) {
    params.append('timezone_offset', options.timezoneOffset.toString())
  }
  if (options?.hasError) params.append('has_error', 'true')

  const queryString = params.toString()
  const url = queryString ? `/review-prompt/check?${queryString}` : '/review-prompt/check'

  return api.get<ReviewPromptCheck>(url).then(r => r.data)
}

/**
 * Get the user's timezone offset in hours from UTC.
 * Positive values are ahead of UTC (e.g., +5 for IST), negative are behind (e.g., -5 for EST).
 */
export const getUserTimezoneOffset = (): number => {
  // JavaScript's getTimezoneOffset returns minutes, and is inverted
  // (negative for timezones ahead of UTC, positive for behind)
  const offsetMinutes = new Date().getTimezoneOffset()
  return -offsetMinutes / 60
}

/**
 * Check review prompt with automatic timezone detection.
 * Convenience wrapper around checkReviewPrompt.
 */
export const checkReviewPromptWithTiming = (
  context?: ReviewPromptCheckOptions['context'],
  hasError?: boolean
) => {
  return checkReviewPrompt({
    context,
    timezoneOffset: getUserTimezoneOffset(),
    hasError,
  })
}

export const recordReviewPromptShown = () =>
  api.post<{ prompt_id: number }>('/review-prompt/shown').then(r => r.data)

export const recordReviewPromptResponse = (promptId: number, response: string) =>
  api.post<ReviewPromptResponse>('/review-prompt/response', {
    prompt_id: promptId,
    response,
  }).then(r => r.data)

/**
 * Get the successful session count for the current tenant.
 */
export const getReviewPromptSessionCount = () =>
  api.get<SessionCountResponse>('/review-prompt/session-count').then(r => r.data)

/**
 * Record a successful action for session tracking.
 * Call this after trade-in approval, member enrollment, or credit issuance.
 */
export const recordSuccessfulAction = (
  actionType: 'trade_in_approved' | 'member_enrolled' | 'credit_issued'
) =>
  api.post<{ success: boolean; action_type: string }>('/review-prompt/action', {
    action_type: actionType,
  }).then(r => r.data)
