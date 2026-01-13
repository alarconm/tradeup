/**
 * MemberDetail.tsx - Comprehensive member view
 * Shows member info, trade history, credit ledger
 */
import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Mail, Phone, Calendar, CreditCard, TrendingUp,
  Package, DollarSign, Award, Edit2, Loader2, AlertCircle, Check,
  ChevronRight
} from 'lucide-react'
import { useTheme } from '../../contexts/ThemeContext'
import { radius, typography, spacing } from '../styles/tokens'
import {
  getMember,
  getTradeInBatches,
  getMemberCreditHistory,
  getTiers,
  updateMember,
  updateMemberTier,
  type Member,
  type TradeInBatch,
  type StoreCreditEntry,
  type MemberCreditBalance,
  type Tier
} from '../api/adminApi'

type TabId = 'overview' | 'tradeins' | 'credits' | 'settings'

const STATUS_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  active: { label: 'Active', color: '#059669', bg: 'rgba(5, 150, 105, 0.1)' },
  pending: { label: 'Pending', color: '#d97706', bg: 'rgba(217, 119, 6, 0.1)' },
  suspended: { label: 'Suspended', color: '#6b7280', bg: 'rgba(107, 114, 128, 0.1)' },
  paused: { label: 'Suspended', color: '#6b7280', bg: 'rgba(107, 114, 128, 0.1)' },  // Legacy alias
  cancelled: { label: 'Cancelled', color: '#dc2626', bg: 'rgba(220, 38, 38, 0.1)' },
  expired: { label: 'Expired', color: '#9ca3af', bg: 'rgba(156, 163, 175, 0.1)' },
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  trade_in: 'Trade-In Bonus',
  purchase_cashback: 'Purchase Cashback',
  promotion_bonus: 'Promotion',
  bulk_credit: 'Bulk Credit',
  manual_adjustment: 'Manual Adjustment',
  redemption: 'Redemption',
  signup_bonus: 'Signup Bonus',
}

export default function MemberDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { colors, shadows } = useTheme()

  const [member, setMember] = useState<Member | null>(null)
  const [tradeIns, setTradeIns] = useState<TradeInBatch[]>([])
  const [creditHistory, setCreditHistory] = useState<StoreCreditEntry[]>([])
  const [creditBalance, setCreditBalance] = useState<MemberCreditBalance | null>(null)
  const [tiers, setTiers] = useState<Tier[]>([])
  const [activeTab, setActiveTab] = useState<TabId>('overview')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [editingTier, setEditingTier] = useState(false)
  const [selectedTierId, setSelectedTierId] = useState<number | null>(null)

  const memberId = parseInt(id || '0')

  useEffect(() => {
    if (memberId) loadMemberData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [memberId])

  const loadMemberData = async () => {
    try {
      setLoading(true)
      setError('')

      const [memberData, tiersData] = await Promise.all([
        getMember(memberId),
        getTiers()
      ])

      setMember(memberData)
      setTiers(tiersData.tiers)
      setSelectedTierId(memberData.tier_id)

      // Load trade-ins and credit history
      const [tradeInData, creditData] = await Promise.all([
        getTradeInBatches({ member_id: memberId }),
        getMemberCreditHistory(memberId, { limit: 50 }).catch(() => null)
      ])

      setTradeIns(tradeInData.batches)
      if (creditData) {
        setCreditHistory(creditData.transactions)
        setCreditBalance(creditData.balance)
      }
    } catch {
      setError('Failed to load member details')
    } finally {
      setLoading(false)
    }
  }

  const handleTierChange = async () => {
    if (!member || selectedTierId === null) return
    try {
      setSaving(true)
      await updateMemberTier(member.id, selectedTierId)
      await loadMemberData()
      setEditingTier(false)
    } catch {
      setError('Failed to update tier')
    } finally {
      setSaving(false)
    }
  }

  const handleStatusChange = async (newStatus: string) => {
    if (!member) return
    try {
      setSaving(true)
      await updateMember(member.id, { status: newStatus as Member['status'] })
      await loadMemberData()
    } catch {
      setError('Failed to update status')
    } finally {
      setSaving(false)
    }
  }

  const formatDate = (date: string) => {
    return new Date(date).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric'
    })
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency', currency: 'USD'
    }).format(amount)
  }

  // Styles
  const cardStyle: React.CSSProperties = {
    backgroundColor: colors.bgSurface,
    borderRadius: radius.lg,
    border: `1px solid ${colors.border}`,
    boxShadow: shadows.card,
    padding: spacing[5],
  }

  const tabStyle = (isActive: boolean): React.CSSProperties => ({
    padding: `${spacing[3]}px ${spacing[4]}px`,
    backgroundColor: isActive ? colors.primary : 'transparent',
    color: isActive ? colors.textOnPrimary : colors.textSecondary,
    border: 'none',
    borderRadius: radius.md,
    fontSize: typography.sm,
    fontWeight: typography.medium,
    cursor: 'pointer',
    transition: 'all 150ms ease',
  })

  const statCardStyle: React.CSSProperties = {
    ...cardStyle,
    display: 'flex',
    flexDirection: 'column',
    gap: spacing[2],
  }

  const buttonStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: '10px 16px',
    backgroundColor: colors.primary,
    color: colors.textOnPrimary,
    border: 'none',
    borderRadius: radius.md,
    fontSize: typography.sm,
    fontWeight: typography.medium,
    cursor: 'pointer',
  }

  const secondaryButtonStyle: React.CSSProperties = {
    ...buttonStyle,
    backgroundColor: colors.bgSurface,
    color: colors.text,
    border: `1px solid ${colors.border}`,
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 400 }}>
        <Loader2 size={32} color={colors.primary} style={{ animation: 'spin 1s linear infinite' }} />
      </div>
    )
  }

  if (!member) {
    return (
      <div style={{ textAlign: 'center', padding: spacing[12] }}>
        <AlertCircle size={48} color={colors.critical} style={{ marginBottom: spacing[4] }} />
        <p style={{ color: colors.textSecondary }}>Member not found</p>
        <Link to="/admin/members" style={{ color: colors.primary, marginTop: spacing[2], display: 'inline-block' }}>
          Back to Members
        </Link>
      </div>
    )
  }

  const statusInfo = STATUS_LABELS[member.status] || STATUS_LABELS.active

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing[6] }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: spacing[4] }}>
        <Link
          to="/admin/members"
          style={{
            padding: spacing[2],
            backgroundColor: colors.bgSurface,
            borderRadius: radius.md,
            border: `1px solid ${colors.border}`,
            color: colors.textSecondary,
            display: 'flex',
          }}
        >
          <ArrowLeft size={20} />
        </Link>
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: typography['2xl'], fontWeight: typography.bold, color: colors.text, margin: 0 }}>
            {member.name || member.email}
          </h1>
          <p style={{ color: colors.textSecondary, margin: 0, fontSize: typography.sm }}>
            {member.member_number}
          </p>
        </div>
        <span style={{
          padding: '6px 12px',
          backgroundColor: statusInfo.bg,
          color: statusInfo.color,
          borderRadius: radius.full,
          fontSize: typography.sm,
          fontWeight: typography.medium,
        }}>
          {statusInfo.label}
        </span>
      </div>

      {error && (
        <div style={{
          backgroundColor: colors.criticalLight,
          border: `1px solid ${colors.critical}`,
          borderRadius: radius.lg,
          padding: spacing[4],
          color: colors.critical,
          display: 'flex',
          alignItems: 'center',
          gap: spacing[2],
        }}>
          <AlertCircle size={18} />
          {error}
        </div>
      )}

      {/* Stats Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: spacing[4] }}>
        <div style={statCardStyle}>
          <div style={{ display: 'flex', alignItems: 'center', gap: spacing[2], color: colors.success }}>
            <DollarSign size={20} />
            <span style={{ fontSize: typography.sm, color: colors.textSecondary }}>Credit Balance</span>
          </div>
          <span style={{ fontSize: typography['2xl'], fontWeight: typography.bold, color: colors.text }}>
            {formatCurrency(creditBalance?.total_balance || member.total_credit_earned || 0)}
          </span>
        </div>

        <div style={statCardStyle}>
          <div style={{ display: 'flex', alignItems: 'center', gap: spacing[2], color: colors.primary }}>
            <Package size={20} />
            <span style={{ fontSize: typography.sm, color: colors.textSecondary }}>Trade-Ins</span>
          </div>
          <span style={{ fontSize: typography['2xl'], fontWeight: typography.bold, color: colors.text }}>
            {member.total_trade_ins || 0}
          </span>
        </div>

        <div style={statCardStyle}>
          <div style={{ display: 'flex', alignItems: 'center', gap: spacing[2], color: colors.warning }}>
            <TrendingUp size={20} />
            <span style={{ fontSize: typography.sm, color: colors.textSecondary }}>Total Trade Value</span>
          </div>
          <span style={{ fontSize: typography['2xl'], fontWeight: typography.bold, color: colors.text }}>
            {formatCurrency(member.total_trade_value || 0)}
          </span>
        </div>

        <div style={statCardStyle}>
          <div style={{ display: 'flex', alignItems: 'center', gap: spacing[2], color: colors.interactive }}>
            <Award size={20} />
            <span style={{ fontSize: typography.sm, color: colors.textSecondary }}>Current Tier</span>
          </div>
          <span style={{ fontSize: typography['2xl'], fontWeight: typography.bold, color: colors.text }}>
            {member.tier?.name || 'None'}
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: spacing[2], borderBottom: `1px solid ${colors.border}`, paddingBottom: spacing[2] }}>
        {(['overview', 'tradeins', 'credits', 'settings'] as TabId[]).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={tabStyle(activeTab === tab)}
          >
            {tab === 'overview' && 'Overview'}
            {tab === 'tradeins' && `Trade-Ins (${tradeIns.length})`}
            {tab === 'credits' && `Credit History (${creditHistory.length})`}
            {tab === 'settings' && 'Settings'}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: spacing[4] }}>
          {/* Contact Info */}
          <div style={cardStyle}>
            <h3 style={{ fontSize: typography.lg, fontWeight: typography.semibold, color: colors.text, marginBottom: spacing[4] }}>
              Contact Information
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: spacing[3] }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: spacing[3] }}>
                <Mail size={18} color={colors.textSecondary} />
                <span style={{ color: colors.text }}>{member.email}</span>
              </div>
              {member.phone && (
                <div style={{ display: 'flex', alignItems: 'center', gap: spacing[3] }}>
                  <Phone size={18} color={colors.textSecondary} />
                  <span style={{ color: colors.text }}>{member.phone}</span>
                </div>
              )}
              <div style={{ display: 'flex', alignItems: 'center', gap: spacing[3] }}>
                <Calendar size={18} color={colors.textSecondary} />
                <span style={{ color: colors.textSecondary }}>
                  Member since {formatDate(member.membership_start_date || member.created_at)}
                </span>
              </div>
              {member.shopify_customer_id && (
                <div style={{ display: 'flex', alignItems: 'center', gap: spacing[3] }}>
                  <CreditCard size={18} color={colors.textSecondary} />
                  <span style={{ color: colors.textSecondary, fontSize: typography.sm }}>
                    Shopify ID: {member.shopify_customer_id.replace('gid://shopify/Customer/', '')}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Membership Details */}
          <div style={cardStyle}>
            <h3 style={{ fontSize: typography.lg, fontWeight: typography.semibold, color: colors.text, marginBottom: spacing[4] }}>
              Membership Details
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: spacing[3] }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: colors.textSecondary }}>Tier</span>
                <span style={{
                  padding: '4px 12px',
                  backgroundColor: colors.primaryLight,
                  color: colors.primary,
                  borderRadius: radius.full,
                  fontSize: typography.sm,
                  fontWeight: typography.medium,
                }}>
                  {member.tier?.name || 'No Tier'}
                </span>
              </div>
              {member.tier && (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: colors.textSecondary }}>Bonus Rate</span>
                    <span style={{ color: colors.success, fontWeight: typography.medium }}>
                      +{((member.tier.bonus_rate || 0) * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: colors.textSecondary }}>Monthly Price</span>
                    <span style={{ color: colors.text }}>
                      {formatCurrency(member.tier.monthly_price || 0)}/mo
                    </span>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Credit Summary */}
          {creditBalance && (
            <div style={cardStyle}>
              <h3 style={{ fontSize: typography.lg, fontWeight: typography.semibold, color: colors.text, marginBottom: spacing[4] }}>
                Credit Summary
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: spacing[3] }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: colors.textSecondary }}>Trade-In Earned</span>
                  <span style={{ color: colors.success }}>{formatCurrency(creditBalance.trade_in_earned || 0)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: colors.textSecondary }}>Cashback Earned</span>
                  <span style={{ color: colors.success }}>{formatCurrency(creditBalance.cashback_earned || 0)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: colors.textSecondary }}>Promo Bonuses</span>
                  <span style={{ color: colors.success }}>{formatCurrency(creditBalance.promo_bonus_earned || 0)}</span>
                </div>
                <div style={{
                  paddingTop: spacing[3],
                  borderTop: `1px solid ${colors.border}`,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}>
                  <span style={{ color: colors.text, fontWeight: typography.medium }}>Total Earned</span>
                  <span style={{ color: colors.success, fontWeight: typography.bold }}>
                    {formatCurrency(creditBalance.total_earned || 0)}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: colors.text, fontWeight: typography.medium }}>Total Spent</span>
                  <span style={{ color: colors.critical }}>{formatCurrency(creditBalance.total_spent || 0)}</span>
                </div>
              </div>
            </div>
          )}

          {/* Recent Activity */}
          <div style={cardStyle}>
            <h3 style={{ fontSize: typography.lg, fontWeight: typography.semibold, color: colors.text, marginBottom: spacing[4] }}>
              Recent Trade-Ins
            </h3>
            {tradeIns.length === 0 ? (
              <p style={{ color: colors.textSecondary, textAlign: 'center', padding: spacing[4] }}>
                No trade-ins yet
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: spacing[2] }}>
                {tradeIns.slice(0, 5).map(ti => (
                  <Link
                    key={ti.id}
                    to={`/admin/tradeins/${ti.id}`}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: spacing[3],
                      backgroundColor: colors.bgSubdued,
                      borderRadius: radius.md,
                      textDecoration: 'none',
                      transition: 'background-color 150ms ease',
                    }}
                  >
                    <div>
                      <p style={{ color: colors.text, margin: 0, fontWeight: typography.medium }}>
                        {ti.batch_reference}
                      </p>
                      <p style={{ color: colors.textSecondary, margin: 0, fontSize: typography.sm }}>
                        {ti.total_items} items • {formatDate(ti.trade_in_date)}
                      </p>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <p style={{ color: colors.success, margin: 0, fontWeight: typography.medium }}>
                        {formatCurrency(ti.total_trade_value)}
                      </p>
                      <ChevronRight size={16} color={colors.textSecondary} />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'tradeins' && (
        <div style={cardStyle}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing[4] }}>
            <h3 style={{ fontSize: typography.lg, fontWeight: typography.semibold, color: colors.text, margin: 0 }}>
              Trade-In History
            </h3>
            <button
              onClick={() => navigate('/admin/tradeins/new', { state: { memberId: member.id } })}
              style={buttonStyle}
            >
              <Package size={16} />
              New Trade-In
            </button>
          </div>

          {tradeIns.length === 0 ? (
            <div style={{ textAlign: 'center', padding: spacing[8], color: colors.textSecondary }}>
              <Package size={48} style={{ opacity: 0.5, marginBottom: spacing[4] }} />
              <p>No trade-ins recorded for this member</p>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${colors.border}` }}>
                    <th style={{ textAlign: 'left', padding: spacing[3], color: colors.textSecondary, fontSize: typography.sm }}>Reference</th>
                    <th style={{ textAlign: 'left', padding: spacing[3], color: colors.textSecondary, fontSize: typography.sm }}>Date</th>
                    <th style={{ textAlign: 'left', padding: spacing[3], color: colors.textSecondary, fontSize: typography.sm }}>Items</th>
                    <th style={{ textAlign: 'left', padding: spacing[3], color: colors.textSecondary, fontSize: typography.sm }}>Category</th>
                    <th style={{ textAlign: 'right', padding: spacing[3], color: colors.textSecondary, fontSize: typography.sm }}>Value</th>
                    <th style={{ textAlign: 'right', padding: spacing[3], color: colors.textSecondary, fontSize: typography.sm }}>Bonus</th>
                    <th style={{ textAlign: 'center', padding: spacing[3], color: colors.textSecondary, fontSize: typography.sm }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {tradeIns.map(ti => (
                    <tr
                      key={ti.id}
                      onClick={() => navigate(`/admin/tradeins/${ti.id}`)}
                      style={{ borderBottom: `1px solid ${colors.border}`, cursor: 'pointer' }}
                    >
                      <td style={{ padding: spacing[3], color: colors.primary, fontWeight: typography.medium }}>
                        {ti.batch_reference}
                      </td>
                      <td style={{ padding: spacing[3], color: colors.text }}>{formatDate(ti.trade_in_date)}</td>
                      <td style={{ padding: spacing[3], color: colors.text }}>{ti.total_items}</td>
                      <td style={{ padding: spacing[3], color: colors.textSecondary }}>
                        <span style={{
                          padding: '2px 8px',
                          backgroundColor: colors.bgSubdued,
                          borderRadius: radius.sm,
                          fontSize: typography.sm,
                        }}>
                          {ti.category || 'Other'}
                        </span>
                      </td>
                      <td style={{ padding: spacing[3], color: colors.text, textAlign: 'right' }}>
                        {formatCurrency(ti.total_trade_value)}
                      </td>
                      <td style={{ padding: spacing[3], color: colors.success, textAlign: 'right' }}>
                        +{formatCurrency(ti.bonus_amount || 0)}
                      </td>
                      <td style={{ padding: spacing[3], textAlign: 'center' }}>
                        <span style={{
                          padding: '4px 8px',
                          borderRadius: radius.full,
                          fontSize: typography.xs,
                          fontWeight: typography.medium,
                          backgroundColor: ti.status === 'completed' ? colors.successLight : colors.warningLight,
                          color: ti.status === 'completed' ? colors.success : colors.warning,
                        }}>
                          {ti.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === 'credits' && (
        <div style={cardStyle}>
          <h3 style={{ fontSize: typography.lg, fontWeight: typography.semibold, color: colors.text, marginBottom: spacing[4] }}>
            Credit Ledger
          </h3>

          {creditHistory.length === 0 ? (
            <div style={{ textAlign: 'center', padding: spacing[8], color: colors.textSecondary }}>
              <DollarSign size={48} style={{ opacity: 0.5, marginBottom: spacing[4] }} />
              <p>No credit transactions recorded</p>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${colors.border}` }}>
                    <th style={{ textAlign: 'left', padding: spacing[3], color: colors.textSecondary, fontSize: typography.sm }}>Date</th>
                    <th style={{ textAlign: 'left', padding: spacing[3], color: colors.textSecondary, fontSize: typography.sm }}>Type</th>
                    <th style={{ textAlign: 'left', padding: spacing[3], color: colors.textSecondary, fontSize: typography.sm }}>Description</th>
                    <th style={{ textAlign: 'right', padding: spacing[3], color: colors.textSecondary, fontSize: typography.sm }}>Amount</th>
                    <th style={{ textAlign: 'right', padding: spacing[3], color: colors.textSecondary, fontSize: typography.sm }}>Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {creditHistory.map(entry => (
                    <tr key={entry.id} style={{ borderBottom: `1px solid ${colors.border}` }}>
                      <td style={{ padding: spacing[3], color: colors.textSecondary, fontSize: typography.sm }}>
                        {formatDate(entry.created_at)}
                      </td>
                      <td style={{ padding: spacing[3] }}>
                        <span style={{
                          padding: '2px 8px',
                          backgroundColor: colors.bgSubdued,
                          borderRadius: radius.sm,
                          fontSize: typography.xs,
                          color: colors.text,
                        }}>
                          {EVENT_TYPE_LABELS[entry.event_type] || entry.event_type}
                        </span>
                      </td>
                      <td style={{ padding: spacing[3], color: colors.text, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {entry.description}
                      </td>
                      <td style={{
                        padding: spacing[3],
                        textAlign: 'right',
                        fontWeight: typography.medium,
                        color: entry.amount >= 0 ? colors.success : colors.critical,
                      }}>
                        {entry.amount >= 0 ? '+' : ''}{formatCurrency(entry.amount)}
                      </td>
                      <td style={{ padding: spacing[3], textAlign: 'right', color: colors.text }}>
                        {formatCurrency(entry.balance_after)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === 'settings' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: spacing[4] }}>
          {/* Tier Management */}
          <div style={cardStyle}>
            <h3 style={{ fontSize: typography.lg, fontWeight: typography.semibold, color: colors.text, marginBottom: spacing[4] }}>
              Membership Tier
            </h3>

            {editingTier ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: spacing[4] }}>
                <select
                  value={selectedTierId || ''}
                  onChange={e => setSelectedTierId(e.target.value ? parseInt(e.target.value) : null)}
                  style={{
                    padding: '10px 12px',
                    backgroundColor: colors.bgSurface,
                    border: `1px solid ${colors.border}`,
                    borderRadius: radius.md,
                    color: colors.text,
                    fontSize: typography.base,
                  }}
                >
                  <option value="">No Tier</option>
                  {tiers.map(tier => (
                    <option key={tier.id} value={tier.id}>
                      {tier.name} - {formatCurrency(tier.monthly_price || 0)}/mo (+{((tier.bonus_rate || 0) * 100).toFixed(0)}% bonus)
                    </option>
                  ))}
                </select>
                <div style={{ display: 'flex', gap: spacing[2] }}>
                  <button
                    onClick={handleTierChange}
                    disabled={saving}
                    style={{ ...buttonStyle, flex: 1 }}
                  >
                    {saving ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
                    Save
                  </button>
                  <button
                    onClick={() => {
                      setEditingTier(false)
                      setSelectedTierId(member.tier_id)
                    }}
                    style={{ ...secondaryButtonStyle, flex: 1 }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <p style={{ color: colors.text, fontWeight: typography.medium, margin: 0 }}>
                    {member.tier?.name || 'No Tier Assigned'}
                  </p>
                  {member.tier && (
                    <p style={{ color: colors.textSecondary, fontSize: typography.sm, margin: 0 }}>
                      +{((member.tier.bonus_rate || 0) * 100).toFixed(0)}% trade-in bonus
                    </p>
                  )}
                </div>
                <button onClick={() => setEditingTier(true)} style={secondaryButtonStyle}>
                  <Edit2 size={16} />
                  Change
                </button>
              </div>
            )}
          </div>

          {/* Status Management */}
          <div style={cardStyle}>
            <h3 style={{ fontSize: typography.lg, fontWeight: typography.semibold, color: colors.text, marginBottom: spacing[4] }}>
              Membership Status
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: spacing[3] }}>
              {Object.entries(STATUS_LABELS).map(([status, info]) => (
                <button
                  key={status}
                  onClick={() => handleStatusChange(status)}
                  disabled={saving || member.status === status}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: spacing[3],
                    backgroundColor: member.status === status ? info.bg : colors.bgSubdued,
                    border: member.status === status ? `2px solid ${info.color}` : `1px solid ${colors.border}`,
                    borderRadius: radius.md,
                    cursor: member.status === status ? 'default' : 'pointer',
                    textAlign: 'left',
                  }}
                >
                  <span style={{
                    color: member.status === status ? info.color : colors.text,
                    fontWeight: member.status === status ? typography.medium : typography.normal,
                  }}>
                    {info.label}
                  </span>
                  {member.status === status && <Check size={18} color={info.color} />}
                </button>
              ))}
            </div>
          </div>

          {/* Danger Zone */}
          <div style={{ ...cardStyle, borderColor: colors.critical }}>
            <h3 style={{ fontSize: typography.lg, fontWeight: typography.semibold, color: colors.critical, marginBottom: spacing[4] }}>
              Danger Zone
            </h3>
            <p style={{ color: colors.textSecondary, marginBottom: spacing[4], fontSize: typography.sm }}>
              These actions are irreversible. Please proceed with caution.
            </p>
            <button
              onClick={() => {
                if (window.confirm(`Are you sure you want to cancel ${member.name || member.email}'s membership?`)) {
                  handleStatusChange('cancelled')
                }
              }}
              disabled={saving || member.status === 'cancelled'}
              style={{
                ...buttonStyle,
                backgroundColor: colors.critical,
                opacity: member.status === 'cancelled' ? 0.5 : 1,
              }}
            >
              Cancel Membership
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
