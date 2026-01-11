/**
 * Promotions.tsx - Theme-aware Promotions Management
 * Shopify Polaris-inspired design
 */
import { useState, useEffect } from 'react'
import { Plus, Calendar, Clock, DollarSign, Users, Tag, X, Loader2 } from 'lucide-react'
import { useTheme } from '../../contexts/ThemeContext'
import { radius, typography, spacing } from '../styles/tokens'
import {
  getPromotions,
  createPromotion,
  updatePromotion,
  deletePromotion,
  getTradeInCategories,
  getPromotionFilterOptions,
  type Promotion,
  type PromotionType,
  type PromotionChannel,
  type TradeInCategory
} from '../api/adminApi'

interface ShopifyCollection {
  id: string
  title: string
  handle: string
  productsCount: number
  isSmart: boolean
}

interface FilterOptions {
  collections: ShopifyCollection[]
  vendors: string[]
  productTypes: string[]
  productTags: string[]
}

const PROMO_TYPE_LABELS: Record<PromotionType, string> = {
  trade_in_bonus: 'Trade-In Bonus',
  purchase_cashback: 'Purchase Cashback',
  flat_bonus: 'Flat Bonus',
  multiplier: 'Credit Multiplier',
}

const CHANNEL_LABELS: Record<PromotionChannel, string> = {
  all: 'All Channels',
  in_store: 'In-Store Only',
  online: 'Online Only',
}

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

export default function Promotions() {
  const { colors, shadows } = useTheme()
  const [promotions, setPromotions] = useState<Promotion[]>([])
  const [categories, setCategories] = useState<TradeInCategory[]>([])
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({
    collections: [], vendors: [], productTypes: [], productTags: []
  })
  const [loadingFilterOptions, setLoadingFilterOptions] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editingPromo, setEditingPromo] = useState<Promotion | null>(null)
  const [filter, setFilter] = useState<'all' | 'active'>('all')

  const [form, setForm] = useState({
    name: '', description: '', code: '',
    promo_type: 'trade_in_bonus' as PromotionType,
    bonus_percent: 10, bonus_flat: 0, multiplier: 1,
    starts_at: '', ends_at: '',
    daily_start_time: '', daily_end_time: '',
    active_days: [] as number[],
    channel: 'all' as PromotionChannel,
    collection_ids: [] as string[],
    vendor_filter: [] as string[],
    product_type_filter: [] as string[],
    product_tags_filter: [] as string[],
    category_ids: [] as string[],
    tier_restriction: [] as string[],
    min_items: 0, min_value: 0,
    stackable: true, priority: 0,
    max_uses: undefined as number | undefined,
    max_uses_per_member: undefined as number | undefined,
    active: true,
  })

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadData() }, [filter])
  useEffect(() => { loadFilterOptions() }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      const [promoData, catData] = await Promise.all([
        getPromotions({ active_only: filter === 'active' }),
        getTradeInCategories(),
      ])
      setPromotions(promoData.promotions)
      setCategories(catData.categories)
    } catch {
      setError('Failed to load promotions')
    } finally {
      setLoading(false)
    }
  }

  const loadFilterOptions = async () => {
    try {
      setLoadingFilterOptions(true)
      const options = await getPromotionFilterOptions()
      setFilterOptions({
        collections: options.collections || [],
        vendors: options.vendors || [],
        productTypes: options.productTypes || [],
        productTags: options.productTags || []
      })
    } catch (err) {
      console.error('Failed to load filter options:', err)
    } finally {
      setLoadingFilterOptions(false)
    }
  }

  const openNewModal = () => {
    const now = new Date()
    const nextWeek = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000)
    setForm({
      name: '', description: '', code: '',
      promo_type: 'trade_in_bonus', bonus_percent: 10, bonus_flat: 0, multiplier: 1,
      starts_at: now.toISOString().slice(0, 16),
      ends_at: nextWeek.toISOString().slice(0, 16),
      daily_start_time: '', daily_end_time: '', active_days: [],
      channel: 'all', collection_ids: [], vendor_filter: [],
      product_type_filter: [], product_tags_filter: [],
      category_ids: [], tier_restriction: [],
      min_items: 0, min_value: 0, stackable: true, priority: 0,
      max_uses: undefined, max_uses_per_member: undefined, active: true,
    })
    setEditingPromo(null)
    setShowModal(true)
  }

  const openEditModal = (promo: Promotion) => {
    setForm({
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
      active_days: promo.active_days ? promo.active_days.split(',').map(Number) : [],
      channel: promo.channel,
      collection_ids: promo.collection_ids || [],
      vendor_filter: promo.vendor_filter || [],
      product_type_filter: promo.product_type_filter || [],
      product_tags_filter: promo.product_tags_filter || [],
      category_ids: promo.category_ids || [],
      tier_restriction: promo.tier_restriction || [],
      min_items: promo.min_items,
      min_value: promo.min_value,
      stackable: promo.stackable,
      priority: promo.priority,
      max_uses: promo.max_uses || undefined,
      max_uses_per_member: promo.max_uses_per_member || undefined,
      active: promo.active,
    })
    setEditingPromo(promo)
    setShowModal(true)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const data = {
        ...form,
        active_days: form.active_days.length > 0 ? form.active_days.join(',') : null,
        collection_ids: form.collection_ids.length > 0 ? form.collection_ids : null,
        vendor_filter: form.vendor_filter.length > 0 ? form.vendor_filter : null,
        product_type_filter: form.product_type_filter.length > 0 ? form.product_type_filter : null,
        product_tags_filter: form.product_tags_filter.length > 0 ? form.product_tags_filter : null,
        category_ids: form.category_ids.length > 0 ? form.category_ids : null,
        tier_restriction: form.tier_restriction.length > 0 ? form.tier_restriction : null,
        max_uses: form.max_uses || null,
        max_uses_per_member: form.max_uses_per_member || null,
      }
      if (editingPromo) {
        await updatePromotion(editingPromo.id, data)
      } else {
        await createPromotion(data)
      }
      setShowModal(false)
      loadData()
    } catch {
      setError('Failed to save promotion')
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this promotion?')) return
    try {
      await deletePromotion(id)
      loadData()
    } catch {
      setError('Failed to delete promotion')
    }
  }

  const toggleDay = (day: number) => {
    setForm(f => ({
      ...f,
      active_days: f.active_days.includes(day)
        ? f.active_days.filter(d => d !== day)
        : [...f.active_days, day].sort()
    }))
  }

  const toggleTier = (tier: string) => {
    setForm(f => ({
      ...f,
      tier_restriction: f.tier_restriction.includes(tier)
        ? f.tier_restriction.filter(t => t !== tier)
        : [...f.tier_restriction, tier]
    }))
  }

  const toggleCategory = (id: string) => {
    setForm(f => ({
      ...f,
      category_ids: f.category_ids.includes(id)
        ? f.category_ids.filter(c => c !== id)
        : [...f.category_ids, id]
    }))
  }

  const toggleCollection = (id: string) => {
    setForm(f => ({
      ...f,
      collection_ids: f.collection_ids.includes(id)
        ? f.collection_ids.filter(c => c !== id)
        : [...f.collection_ids, id]
    }))
  }

  const toggleVendor = (vendor: string) => {
    setForm(f => ({
      ...f,
      vendor_filter: f.vendor_filter.includes(vendor)
        ? f.vendor_filter.filter(v => v !== vendor)
        : [...f.vendor_filter, vendor]
    }))
  }

  const toggleProductType = (productType: string) => {
    setForm(f => ({
      ...f,
      product_type_filter: f.product_type_filter.includes(productType)
        ? f.product_type_filter.filter(t => t !== productType)
        : [...f.product_type_filter, productType]
    }))
  }

  const toggleProductTag = (tag: string) => {
    setForm(f => ({
      ...f,
      product_tags_filter: f.product_tags_filter.includes(tag)
        ? f.product_tags_filter.filter(t => t !== tag)
        : [...f.product_tags_filter, tag]
    }))
  }

  const formatDateRange = (promo: Promotion) => {
    const start = new Date(promo.starts_at).toLocaleDateString()
    const end = new Date(promo.ends_at).toLocaleDateString()
    return `${start} - ${end}`
  }

  // Styles
  const cardStyle: React.CSSProperties = {
    backgroundColor: colors.bgSurface,
    borderRadius: radius.lg,
    border: `1px solid ${colors.border}`,
    boxShadow: shadows.card,
    padding: spacing[5],
    transition: 'border-color 150ms ease, box-shadow 150ms ease',
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '10px 12px',
    backgroundColor: colors.bgSurface,
    border: `1px solid ${colors.border}`,
    borderRadius: radius.md,
    fontSize: typography.base,
    color: colors.text,
    outline: 'none',
  }

  const selectStyle: React.CSSProperties = {
    ...inputStyle,
    cursor: 'pointer',
  }

  const labelStyle: React.CSSProperties = {
    display: 'block',
    fontSize: typography.sm,
    fontWeight: typography.medium,
    color: colors.textSecondary,
    marginBottom: 4,
  }

  const primaryButtonStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: '10px 16px',
    backgroundColor: colors.primary,
    color: colors.textOnPrimary,
    border: 'none',
    borderRadius: radius.md,
    fontSize: typography.base,
    fontWeight: typography.medium,
    cursor: 'pointer',
  }

  const secondaryButtonStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: '10px 16px',
    backgroundColor: colors.bgSurface,
    color: colors.text,
    border: `1px solid ${colors.border}`,
    borderRadius: radius.md,
    fontSize: typography.base,
    fontWeight: typography.medium,
    cursor: 'pointer',
  }

  const chipStyle = (isActive: boolean, variant: 'default' | 'success' | 'primary' = 'default'): React.CSSProperties => {
    const bg = isActive
      ? variant === 'success' ? colors.success
        : variant === 'primary' ? colors.primary
        : colors.primary
      : colors.bgSubdued
    const textColor = isActive ? colors.textOnPrimary : colors.textSecondary
    return {
      padding: '6px 12px',
      borderRadius: radius.md,
      fontSize: typography.sm,
      fontWeight: typography.medium,
      backgroundColor: bg,
      color: textColor,
      border: 'none',
      cursor: 'pointer',
      transition: 'all 150ms ease',
    }
  }

  const getStatusBadge = (promo: Promotion) => {
    const baseStyle: React.CSSProperties = {
      padding: '4px 10px',
      fontSize: typography.xs,
      fontWeight: typography.medium,
      borderRadius: radius.full,
    }
    if (!promo.active) {
      return <span style={{ ...baseStyle, backgroundColor: colors.bgSubdued, color: colors.textSecondary }}>Disabled</span>
    }
    if (promo.is_active_now) {
      return <span style={{ ...baseStyle, backgroundColor: colors.successLight, color: colors.success }}>Active Now</span>
    }
    const now = new Date()
    if (new Date(promo.starts_at) > now) {
      return <span style={{ ...baseStyle, backgroundColor: colors.primaryLight, color: colors.primary }}>Scheduled</span>
    }
    return <span style={{ ...baseStyle, backgroundColor: colors.warningLight, color: colors.warning }}>Ended</span>
  }

  if (loading && promotions.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 256 }}>
        <Loader2 size={32} color={colors.primary} style={{ animation: 'spin 1s linear infinite' }} />
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing[6] }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: spacing[4] }}>
        <div>
          <h1 style={{ fontSize: typography['2xl'], fontWeight: typography.bold, color: colors.text, margin: 0 }}>
            Promotions
          </h1>
          <p style={{ color: colors.textSecondary, marginTop: 4, fontSize: typography.base }}>
            Manage store credit events and bonuses
          </p>
        </div>
        <button onClick={openNewModal} style={primaryButtonStyle}>
          <Plus size={18} />
          New Promotion
        </button>
      </div>

      {error && (
        <div style={{
          backgroundColor: colors.criticalLight,
          border: `1px solid ${colors.critical}`,
          borderRadius: radius.lg,
          padding: spacing[4],
          color: colors.critical,
        }}>
          {error}
        </div>
      )}

      {/* Filter Tabs */}
      <div style={{ display: 'flex', gap: spacing[2] }}>
        <button
          onClick={() => setFilter('all')}
          style={chipStyle(filter === 'all')}
        >
          All Promotions
        </button>
        <button
          onClick={() => setFilter('active')}
          style={chipStyle(filter === 'active', 'success')}
        >
          Active Now
        </button>
      </div>

      {/* Promotions Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: spacing[4] }}>
        {promotions.map(promo => (
          <div key={promo.id} style={cardStyle}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: spacing[3] }}>
              <div>
                <h3 style={{ fontWeight: typography.semibold, color: colors.text, margin: 0 }}>{promo.name}</h3>
                <p style={{ fontSize: typography.sm, color: colors.textSecondary, margin: 0 }}>
                  {PROMO_TYPE_LABELS[promo.promo_type]}
                </p>
              </div>
              {getStatusBadge(promo)}
            </div>

            {promo.description && (
              <p style={{ fontSize: typography.sm, color: colors.textSecondary, marginBottom: spacing[3],
                overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                {promo.description}
              </p>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: spacing[2], fontSize: typography.sm }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: spacing[2], color: colors.success }}>
                <DollarSign size={16} />
                {promo.promo_type === 'flat_bonus' ? (
                  <span>${promo.bonus_flat} flat bonus</span>
                ) : promo.promo_type === 'multiplier' ? (
                  <span>{promo.multiplier}x multiplier</span>
                ) : (
                  <span>+{promo.bonus_percent}% bonus</span>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: spacing[2], color: colors.textSecondary }}>
                <Calendar size={16} />
                <span>{formatDateRange(promo)}</span>
              </div>

              {promo.daily_start_time && promo.daily_end_time && (
                <div style={{ display: 'flex', alignItems: 'center', gap: spacing[2], color: colors.textSecondary }}>
                  <Clock size={16} />
                  <span>{promo.daily_start_time} - {promo.daily_end_time}</span>
                </div>
              )}

              <div style={{ display: 'flex', alignItems: 'center', gap: spacing[2], color: colors.textSecondary }}>
                <Tag size={16} />
                <span>{CHANNEL_LABELS[promo.channel]}</span>
              </div>

              {promo.max_uses && (
                <div style={{ display: 'flex', alignItems: 'center', gap: spacing[2], color: colors.textSecondary }}>
                  <Users size={16} />
                  <span>{promo.current_uses} / {promo.max_uses} uses</span>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: spacing[2], marginTop: spacing[4], paddingTop: spacing[4],
              borderTop: `1px solid ${colors.border}` }}>
              <button onClick={() => openEditModal(promo)} style={{ ...secondaryButtonStyle, flex: 1, padding: '8px 12px' }}>
                Edit
              </button>
              <button
                onClick={() => handleDelete(promo.id)}
                style={{ padding: '8px 12px', fontSize: typography.sm, color: colors.critical,
                  backgroundColor: 'transparent', border: 'none', borderRadius: radius.md, cursor: 'pointer' }}
              >
                Delete
              </button>
            </div>
          </div>
        ))}

        {promotions.length === 0 && (
          <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: `${spacing[12]}px 0`, color: colors.textSecondary }}>
            <DollarSign size={48} style={{ opacity: 0.5, marginBottom: spacing[4] }} />
            <p>No promotions found</p>
            <button onClick={openNewModal} style={{ marginTop: spacing[2], color: colors.primary, background: 'none',
              border: 'none', cursor: 'pointer', fontSize: typography.base }}>
              Create your first promotion
            </button>
          </div>
        )}
      </div>

      {/* Modal */}
      {showModal && (
        <div style={{
          position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', padding: spacing[4], zIndex: 50, overflowY: 'auto',
        }}>
          <div style={{
            backgroundColor: colors.bgSurface, borderRadius: radius.xl, maxWidth: 672, width: '100%',
            maxHeight: '90vh', overflowY: 'auto', boxShadow: shadows.xl,
          }}>
            {/* Modal Header */}
            <div style={{
              position: 'sticky', top: 0, backgroundColor: colors.bgSurface, padding: spacing[6],
              borderBottom: `1px solid ${colors.border}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              zIndex: 10,
            }}>
              <h2 style={{ fontSize: typography.xl, fontWeight: typography.semibold, color: colors.text, margin: 0 }}>
                {editingPromo ? 'Edit Promotion' : 'New Promotion'}
              </h2>
              <button onClick={() => setShowModal(false)} style={{ color: colors.textSecondary, background: 'none',
                border: 'none', cursor: 'pointer', padding: 4 }}>
                <X size={24} />
              </button>
            </div>

            <form onSubmit={handleSubmit} style={{ padding: spacing[6], display: 'flex', flexDirection: 'column', gap: spacing[6] }}>
              {/* Basic Info */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: spacing[4] }}>
                <div style={{ gridColumn: '1 / -1' }}>
                  <label style={labelStyle}>Name *</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                    style={inputStyle}
                    placeholder="Holiday Weekend Bonus"
                    required
                  />
                </div>

                <div style={{ gridColumn: '1 / -1' }}>
                  <label style={labelStyle}>Description</label>
                  <textarea
                    value={form.description}
                    onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                    style={{ ...inputStyle, resize: 'vertical' }}
                    rows={2}
                    placeholder="Get extra store credit during the holiday weekend!"
                  />
                </div>

                <div>
                  <label style={labelStyle}>Promo Code (optional)</label>
                  <input
                    type="text"
                    value={form.code}
                    onChange={e => setForm(f => ({ ...f, code: e.target.value.toUpperCase() }))}
                    style={{ ...inputStyle, textTransform: 'uppercase' }}
                    placeholder="HOLIDAY2024"
                  />
                </div>

                <div>
                  <label style={labelStyle}>Promotion Type *</label>
                  <select
                    value={form.promo_type}
                    onChange={e => setForm(f => ({ ...f, promo_type: e.target.value as PromotionType }))}
                    style={selectStyle}
                  >
                    {Object.entries(PROMO_TYPE_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Value Section */}
              <div style={{ padding: spacing[4], backgroundColor: colors.bgSubdued, borderRadius: radius.lg }}>
                <h3 style={{ fontWeight: typography.medium, color: colors.text, marginBottom: spacing[3], fontSize: typography.base }}>
                  Bonus Value
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: spacing[4] }}>
                  {form.promo_type !== 'multiplier' && form.promo_type !== 'flat_bonus' && (
                    <div>
                      <label style={labelStyle}>Bonus Percent (%)</label>
                      <input
                        type="number"
                        value={form.bonus_percent}
                        onChange={e => setForm(f => ({ ...f, bonus_percent: parseFloat(e.target.value) || 0 }))}
                        style={inputStyle}
                        min="0" max="100" step="0.5"
                      />
                    </div>
                  )}
                  {form.promo_type === 'flat_bonus' && (
                    <div>
                      <label style={labelStyle}>Flat Bonus ($)</label>
                      <input
                        type="number"
                        value={form.bonus_flat}
                        onChange={e => setForm(f => ({ ...f, bonus_flat: parseFloat(e.target.value) || 0 }))}
                        style={inputStyle}
                        min="0" step="0.01"
                      />
                    </div>
                  )}
                  {form.promo_type === 'multiplier' && (
                    <div>
                      <label style={labelStyle}>Multiplier (e.g. 2x)</label>
                      <input
                        type="number"
                        value={form.multiplier}
                        onChange={e => setForm(f => ({ ...f, multiplier: parseFloat(e.target.value) || 1 }))}
                        style={inputStyle}
                        min="1" max="10" step="0.1"
                      />
                    </div>
                  )}
                </div>
              </div>

              {/* Schedule Section */}
              <div style={{ padding: spacing[4], backgroundColor: colors.bgSubdued, borderRadius: radius.lg }}>
                <h3 style={{ fontWeight: typography.medium, color: colors.text, marginBottom: spacing[3], fontSize: typography.base }}>
                  Schedule
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: spacing[4] }}>
                  <div>
                    <label style={labelStyle}>Starts At *</label>
                    <input
                      type="datetime-local"
                      value={form.starts_at}
                      onChange={e => setForm(f => ({ ...f, starts_at: e.target.value }))}
                      style={inputStyle}
                      required
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Ends At *</label>
                    <input
                      type="datetime-local"
                      value={form.ends_at}
                      onChange={e => setForm(f => ({ ...f, ends_at: e.target.value }))}
                      style={inputStyle}
                      required
                    />
                  </div>
                </div>

                <div style={{ marginTop: spacing[4], paddingTop: spacing[4], borderTop: `1px solid ${colors.border}` }}>
                  <h4 style={{ fontSize: typography.sm, fontWeight: typography.medium, color: colors.textSecondary, marginBottom: spacing[2] }}>
                    Daily Time Window (optional)
                  </h4>
                  <p style={{ fontSize: typography.xs, color: colors.textSubdued, marginBottom: spacing[2] }}>
                    Only active during these hours each day
                  </p>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: spacing[4] }}>
                    <div>
                      <label style={labelStyle}>Start Time</label>
                      <input
                        type="time"
                        value={form.daily_start_time}
                        onChange={e => setForm(f => ({ ...f, daily_start_time: e.target.value }))}
                        style={inputStyle}
                      />
                    </div>
                    <div>
                      <label style={labelStyle}>End Time</label>
                      <input
                        type="time"
                        value={form.daily_end_time}
                        onChange={e => setForm(f => ({ ...f, daily_end_time: e.target.value }))}
                        style={inputStyle}
                      />
                    </div>
                  </div>
                </div>

                <div style={{ marginTop: spacing[4], paddingTop: spacing[4], borderTop: `1px solid ${colors.border}` }}>
                  <h4 style={{ fontSize: typography.sm, fontWeight: typography.medium, color: colors.textSecondary, marginBottom: spacing[2] }}>
                    Active Days (optional)
                  </h4>
                  <p style={{ fontSize: typography.xs, color: colors.textSubdued, marginBottom: spacing[2] }}>
                    Only active on selected days (leave empty for all days)
                  </p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: spacing[2] }}>
                    {DAY_NAMES.map((day, i) => (
                      <button
                        key={day}
                        type="button"
                        onClick={() => toggleDay(i)}
                        style={chipStyle(form.active_days.includes(i))}
                      >
                        {day}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Restrictions Section */}
              <div style={{ padding: spacing[4], backgroundColor: colors.bgSubdued, borderRadius: radius.lg }}>
                <h3 style={{ fontWeight: typography.medium, color: colors.text, marginBottom: spacing[3], fontSize: typography.base }}>
                  Restrictions
                </h3>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: spacing[4], marginBottom: spacing[4] }}>
                  <div>
                    <label style={labelStyle}>Channel</label>
                    <select
                      value={form.channel}
                      onChange={e => setForm(f => ({ ...f, channel: e.target.value as PromotionChannel }))}
                      style={selectStyle}
                    >
                      {Object.entries(CHANNEL_LABELS).map(([value, label]) => (
                        <option key={value} value={value}>{label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label style={labelStyle}>Minimum Value ($)</label>
                    <input
                      type="number"
                      value={form.min_value}
                      onChange={e => setForm(f => ({ ...f, min_value: parseFloat(e.target.value) || 0 }))}
                      style={inputStyle}
                      min="0" step="0.01"
                    />
                  </div>
                </div>

                <div style={{ marginBottom: spacing[4] }}>
                  <h4 style={{ fontSize: typography.sm, fontWeight: typography.medium, color: colors.textSecondary, marginBottom: spacing[2] }}>
                    Member Tiers (optional)
                  </h4>
                  <p style={{ fontSize: typography.xs, color: colors.textSubdued, marginBottom: spacing[2] }}>
                    Leave empty for all tiers
                  </p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: spacing[2] }}>
                    {['SILVER', 'GOLD', 'PLATINUM'].map(tier => (
                      <button
                        key={tier}
                        type="button"
                        onClick={() => toggleTier(tier)}
                        style={chipStyle(form.tier_restriction.includes(tier))}
                      >
                        {tier}
                      </button>
                    ))}
                  </div>
                </div>

                {form.promo_type === 'trade_in_bonus' && categories.length > 0 && (
                  <div>
                    <h4 style={{ fontSize: typography.sm, fontWeight: typography.medium, color: colors.textSecondary, marginBottom: spacing[2] }}>
                      Categories (optional)
                    </h4>
                    <p style={{ fontSize: typography.xs, color: colors.textSubdued, marginBottom: spacing[2] }}>
                      Leave empty for all categories
                    </p>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: spacing[2] }}>
                      {categories.map(cat => (
                        <button
                          key={cat.id}
                          type="button"
                          onClick={() => toggleCategory(String(cat.id))}
                          style={chipStyle(form.category_ids.includes(String(cat.id)))}
                        >
                          {cat.name}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Product Filters (for purchase_cashback) */}
              {form.promo_type === 'purchase_cashback' && (
                <div style={{ padding: spacing[4], backgroundColor: colors.bgSubdued, borderRadius: radius.lg }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing[3] }}>
                    <h3 style={{ fontWeight: typography.medium, color: colors.text, fontSize: typography.base, margin: 0 }}>
                      Product Filters
                    </h3>
                    {loadingFilterOptions && (
                      <span style={{ fontSize: typography.xs, color: colors.textSecondary }}>Loading options...</span>
                    )}
                  </div>
                  <p style={{ fontSize: typography.xs, color: colors.textSubdued, marginBottom: spacing[4] }}>
                    Filter which products qualify. Leave all empty to include all products.
                  </p>

                  {filterOptions.collections.length > 0 && (
                    <div style={{ marginBottom: spacing[4] }}>
                      <h4 style={{ fontSize: typography.sm, fontWeight: typography.medium, color: colors.textSecondary, marginBottom: spacing[2] }}>
                        Collections ({form.collection_ids.length} selected)
                      </h4>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: spacing[2], maxHeight: 128, overflowY: 'auto' }}>
                        {filterOptions.collections.map(col => (
                          <button
                            key={col.id}
                            type="button"
                            onClick={() => toggleCollection(col.id)}
                            style={chipStyle(form.collection_ids.includes(col.id))}
                            title={`${col.productsCount} products`}
                          >
                            {col.title}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {filterOptions.vendors.length > 0 && (
                    <div style={{ marginBottom: spacing[4] }}>
                      <h4 style={{ fontSize: typography.sm, fontWeight: typography.medium, color: colors.textSecondary, marginBottom: spacing[2] }}>
                        Vendors/Brands ({form.vendor_filter.length} selected)
                      </h4>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: spacing[2], maxHeight: 128, overflowY: 'auto' }}>
                        {filterOptions.vendors.map(vendor => (
                          <button key={vendor} type="button" onClick={() => toggleVendor(vendor)}
                            style={chipStyle(form.vendor_filter.includes(vendor))}>
                            {vendor}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {filterOptions.productTypes.length > 0 && (
                    <div style={{ marginBottom: spacing[4] }}>
                      <h4 style={{ fontSize: typography.sm, fontWeight: typography.medium, color: colors.textSecondary, marginBottom: spacing[2] }}>
                        Product Types ({form.product_type_filter.length} selected)
                      </h4>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: spacing[2], maxHeight: 128, overflowY: 'auto' }}>
                        {filterOptions.productTypes.map(pType => (
                          <button key={pType} type="button" onClick={() => toggleProductType(pType)}
                            style={chipStyle(form.product_type_filter.includes(pType))}>
                            {pType}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {filterOptions.productTags.length > 0 && (
                    <div>
                      <h4 style={{ fontSize: typography.sm, fontWeight: typography.medium, color: colors.textSecondary, marginBottom: spacing[2] }}>
                        Product Tags ({form.product_tags_filter.length} selected)
                      </h4>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: spacing[2], maxHeight: 128, overflowY: 'auto' }}>
                        {filterOptions.productTags.slice(0, 50).map(tag => (
                          <button key={tag} type="button" onClick={() => toggleProductTag(tag)}
                            style={chipStyle(form.product_tags_filter.includes(tag))}>
                            {tag}
                          </button>
                        ))}
                        {filterOptions.productTags.length > 50 && (
                          <span style={{ fontSize: typography.xs, color: colors.textSubdued, alignSelf: 'center' }}>
                            +{filterOptions.productTags.length - 50} more
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Limits Section */}
              <div style={{ padding: spacing[4], backgroundColor: colors.bgSubdued, borderRadius: radius.lg }}>
                <h3 style={{ fontWeight: typography.medium, color: colors.text, marginBottom: spacing[3], fontSize: typography.base }}>
                  Limits
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: spacing[4] }}>
                  <div>
                    <label style={labelStyle}>Max Total Uses</label>
                    <input
                      type="number"
                      value={form.max_uses || ''}
                      onChange={e => setForm(f => ({ ...f, max_uses: e.target.value ? parseInt(e.target.value) : undefined }))}
                      style={inputStyle}
                      min="1"
                      placeholder="Unlimited"
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Max Per Member</label>
                    <input
                      type="number"
                      value={form.max_uses_per_member || ''}
                      onChange={e => setForm(f => ({ ...f, max_uses_per_member: e.target.value ? parseInt(e.target.value) : undefined }))}
                      style={inputStyle}
                      min="1"
                      placeholder="Unlimited"
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Priority</label>
                    <input
                      type="number"
                      value={form.priority}
                      onChange={e => setForm(f => ({ ...f, priority: parseInt(e.target.value) || 0 }))}
                      style={inputStyle}
                      min="0"
                    />
                    <p style={{ fontSize: typography.xs, color: colors.textSubdued, marginTop: 4 }}>Higher = applied first</p>
                  </div>
                </div>

                <div style={{ marginTop: spacing[4], display: 'flex', alignItems: 'center', gap: spacing[6] }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: spacing[2], cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={form.stackable}
                      onChange={e => setForm(f => ({ ...f, stackable: e.target.checked }))}
                      style={{ width: 16, height: 16, accentColor: colors.primary }}
                    />
                    <span style={{ fontSize: typography.sm, color: colors.textSecondary }}>
                      Stackable (can combine with other promos)
                    </span>
                  </label>

                  <label style={{ display: 'flex', alignItems: 'center', gap: spacing[2], cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={form.active}
                      onChange={e => setForm(f => ({ ...f, active: e.target.checked }))}
                      style={{ width: 16, height: 16, accentColor: colors.primary }}
                    />
                    <span style={{ fontSize: typography.sm, color: colors.textSecondary }}>Active</span>
                  </label>
                </div>
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', gap: spacing[3], justifyContent: 'flex-end', paddingTop: spacing[4],
                borderTop: `1px solid ${colors.border}` }}>
                <button type="button" onClick={() => setShowModal(false)}
                  style={{ ...secondaryButtonStyle, backgroundColor: 'transparent', border: 'none' }}>
                  Cancel
                </button>
                <button type="submit" style={primaryButtonStyle}>
                  {editingPromo ? 'Save Changes' : 'Create Promotion'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
