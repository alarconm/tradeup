/**
 * BulkCredit.tsx - Theme-aware Bulk Credit Operations
 * Shopify Polaris-inspired design
 */
import { useState, useEffect } from 'react'
import { Plus, Zap, CheckCircle, DollarSign, Users, X, Loader2 } from 'lucide-react'
import { useTheme } from '../../contexts/ThemeContext'
import { radius, typography, spacing } from '../styles/tokens'
import {
  createBulkCreditOperation,
  previewBulkCredit,
  executeBulkCredit,
  getBulkCreditOperations,
  type BulkCreditOperation
} from '../api'

export default function BulkCredit() {
  const { colors, shadows } = useTheme()
  const [operations, setOperations] = useState<BulkCreditOperation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [previewData, setPreviewData] = useState<{
    operation: BulkCreditOperation
    member_count: number
    total_amount: number
    members: Array<{ id: number; email: string; tier: string }>
  } | null>(null)
  const [executing, setExecuting] = useState(false)

  const [form, setForm] = useState({
    name: '',
    description: '',
    amount_per_member: 5,
    tier_filter: '',
  })

  useEffect(() => {
    loadOperations()
  }, [])

  const loadOperations = async () => {
    try {
      setLoading(true)
      const data = await getBulkCreditOperations()
      setOperations(data.operations)
    } catch (err) {
      setError('Failed to load operations')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateAndPreview = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setError('')
      const operation = await createBulkCreditOperation({
        ...form,
        tier_filter: form.tier_filter || undefined,
        created_by: 'admin',
      })
      const preview = await previewBulkCredit(operation.id)
      setPreviewData({ operation, ...preview })
      setShowModal(false)
    } catch (err) {
      setError('Failed to create operation')
    }
  }

  const handleExecute = async () => {
    if (!previewData) return
    try {
      setExecuting(true)
      await executeBulkCredit(previewData.operation.id)
      setPreviewData(null)
      loadOperations()
    } catch (err) {
      setError('Failed to execute bulk credit')
    } finally {
      setExecuting(false)
    }
  }

  // Styles
  const cardStyle: React.CSSProperties = {
    backgroundColor: colors.bgSurface,
    borderRadius: radius.lg,
    border: `1px solid ${colors.border}`,
    boxShadow: shadows.card,
    overflow: 'hidden',
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

  const getStatusBadge = (status: string) => {
    const styles: Record<string, { bg: string; color: string }> = {
      pending: { bg: colors.warningLight, color: colors.warning },
      processing: { bg: colors.primaryLight, color: colors.primary },
      completed: { bg: colors.successLight, color: colors.success },
      failed: { bg: colors.criticalLight, color: colors.critical },
    }
    const s = styles[status] || styles.pending
    return (
      <span style={{
        padding: '4px 10px',
        fontSize: typography.xs,
        fontWeight: typography.medium,
        borderRadius: radius.full,
        backgroundColor: s.bg,
        color: s.color,
      }}>
        {status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Unknown'}
      </span>
    )
  }

  if (loading && operations.length === 0) {
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
            Bulk Credit Operations
          </h1>
          <p style={{ color: colors.textSecondary, marginTop: 4, fontSize: typography.base }}>
            Issue store credit to multiple members at once
          </p>
        </div>
        <button
          onClick={() => {
            setForm({ name: '', description: '', amount_per_member: 5, tier_filter: '' })
            setShowModal(true)
          }}
          style={primaryButtonStyle}
        >
          <Plus size={18} />
          New Bulk Credit
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

      {/* Preview Panel */}
      {previewData && (
        <div style={{
          ...cardStyle,
          border: `1px solid ${colors.success}`,
        }}>
          <div style={{ padding: spacing[6], borderBottom: `1px solid ${colors.border}` }}>
            <h2 style={{
              fontSize: typography.xl,
              fontWeight: typography.semibold,
              color: colors.text,
              margin: 0,
              display: 'flex',
              alignItems: 'center',
              gap: spacing[2],
            }}>
              <CheckCircle size={24} color={colors.success} />
              Ready to Execute: {previewData.operation.name}
            </h2>
            <p style={{ color: colors.textSecondary, marginTop: 4 }}>
              {previewData.operation.description}
            </p>
          </div>

          <div style={{ padding: spacing[6], display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: spacing[6] }}>
            <div style={{
              backgroundColor: colors.bgSubdued,
              borderRadius: radius.lg,
              padding: spacing[4],
              textAlign: 'center',
            }}>
              <div style={{ fontSize: typography['3xl'], fontWeight: typography.bold, color: colors.text }}>
                {previewData.member_count}
              </div>
              <div style={{ fontSize: typography.sm, color: colors.textSecondary, marginTop: 4 }}>
                Members
              </div>
            </div>
            <div style={{
              backgroundColor: colors.bgSubdued,
              borderRadius: radius.lg,
              padding: spacing[4],
              textAlign: 'center',
            }}>
              <div style={{ fontSize: typography['3xl'], fontWeight: typography.bold, color: colors.success }}>
                ${previewData.operation.amount_per_member.toFixed(2)}
              </div>
              <div style={{ fontSize: typography.sm, color: colors.textSecondary, marginTop: 4 }}>
                Per Member
              </div>
            </div>
            <div style={{
              backgroundColor: colors.bgSubdued,
              borderRadius: radius.lg,
              padding: spacing[4],
              textAlign: 'center',
            }}>
              <div style={{ fontSize: typography['3xl'], fontWeight: typography.bold, color: colors.warning }}>
                ${previewData.total_amount.toFixed(2)}
              </div>
              <div style={{ fontSize: typography.sm, color: colors.textSecondary, marginTop: 4 }}>
                Total Credit
              </div>
            </div>
          </div>

          {previewData.members.length > 0 && (
            <div style={{ paddingLeft: spacing[6], paddingRight: spacing[6], paddingBottom: spacing[4] }}>
              <h4 style={{ fontSize: typography.sm, fontWeight: typography.medium, color: colors.textSecondary, marginBottom: spacing[2] }}>
                Sample Recipients ({previewData.members.length} of {previewData.member_count})
              </h4>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: spacing[2] }}>
                {previewData.members.map(m => (
                  <span key={m.id} style={{
                    padding: '4px 8px',
                    backgroundColor: colors.bgSubdued,
                    borderRadius: radius.md,
                    fontSize: typography.sm,
                    color: colors.textSecondary,
                  }}>
                    {m.email} ({m.tier})
                  </span>
                ))}
              </div>
            </div>
          )}

          <div style={{
            padding: spacing[6],
            borderTop: `1px solid ${colors.border}`,
            display: 'flex',
            gap: spacing[3],
            justifyContent: 'flex-end',
          }}>
            <button
              onClick={() => setPreviewData(null)}
              style={{ ...secondaryButtonStyle, backgroundColor: 'transparent', border: 'none' }}
            >
              Cancel
            </button>
            <button
              onClick={handleExecute}
              disabled={executing}
              style={{
                ...primaryButtonStyle,
                backgroundColor: colors.success,
                opacity: executing ? 0.5 : 1,
                cursor: executing ? 'not-allowed' : 'pointer',
              }}
            >
              {executing ? (
                <>
                  <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                  Executing...
                </>
              ) : (
                <>
                  <Zap size={18} />
                  Execute Now
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Operations History */}
      <div style={cardStyle}>
        <div style={{ padding: spacing[6], borderBottom: `1px solid ${colors.border}` }}>
          <h2 style={{ fontSize: typography.lg, fontWeight: typography.semibold, color: colors.text, margin: 0 }}>
            Operation History
          </h2>
        </div>

        <div>
          {operations.map((op, index) => (
            <div
              key={op.id}
              style={{
                padding: spacing[4],
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                borderBottom: index < operations.length - 1 ? `1px solid ${colors.border}` : 'none',
                transition: 'background-color 150ms ease',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = colors.bgSurfaceHover }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
            >
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: spacing[3] }}>
                  <h3 style={{ fontWeight: typography.medium, color: colors.text, margin: 0 }}>{op.name}</h3>
                  {getStatusBadge(op.status)}
                  {op.tier_filter && (
                    <span style={{
                      padding: '2px 8px',
                      fontSize: typography.xs,
                      borderRadius: radius.md,
                      backgroundColor: colors.bgSubdued,
                      color: colors.textSecondary,
                    }}>
                      {op.tier_filter.split(',').join(', ')}
                    </span>
                  )}
                </div>
                {op.description && (
                  <p style={{ fontSize: typography.sm, color: colors.textSecondary, marginTop: 2, marginBottom: 0 }}>
                    {op.description}
                  </p>
                )}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: spacing[4],
                  marginTop: spacing[2],
                  fontSize: typography.sm,
                  color: colors.textSubdued,
                }}>
                  <span>{new Date(op.created_at).toLocaleDateString()}</span>
                  <span>by {op.created_by}</span>
                </div>
              </div>

              <div style={{ textAlign: 'right' }}>
                {op.status === 'completed' ? (
                  <>
                    <div style={{ color: colors.success, fontWeight: typography.semibold }}>
                      ${op.total_amount.toFixed(2)}
                    </div>
                    <div style={{ fontSize: typography.sm, color: colors.textSecondary }}>
                      {op.member_count} members @ ${op.amount_per_member}/ea
                    </div>
                  </>
                ) : (
                  <div style={{ color: colors.textSecondary }}>
                    ${op.amount_per_member}/member
                  </div>
                )}
              </div>
            </div>
          ))}

          {operations.length === 0 && (
            <div style={{ padding: `${spacing[12]}px 0`, textAlign: 'center', color: colors.textSecondary }}>
              <DollarSign size={48} style={{ opacity: 0.5, marginBottom: spacing[4] }} />
              <p style={{ margin: 0 }}>No bulk credit operations yet</p>
            </div>
          )}
        </div>
      </div>

      {/* Create Modal */}
      {showModal && (
        <div style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: spacing[4],
          zIndex: 50,
        }}>
          <div style={{
            backgroundColor: colors.bgSurface,
            borderRadius: radius.xl,
            maxWidth: 448,
            width: '100%',
            boxShadow: shadows.xl,
          }}>
            <div style={{
              padding: spacing[6],
              borderBottom: `1px solid ${colors.border}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <h2 style={{ fontSize: typography.xl, fontWeight: typography.semibold, color: colors.text, margin: 0 }}>
                New Bulk Credit
              </h2>
              <button
                onClick={() => setShowModal(false)}
                style={{ color: colors.textSecondary, background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}
              >
                <X size={24} />
              </button>
            </div>

            <form onSubmit={handleCreateAndPreview} style={{ padding: spacing[6], display: 'flex', flexDirection: 'column', gap: spacing[4] }}>
              <div>
                <label style={labelStyle}>Operation Name *</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  style={inputStyle}
                  placeholder="Holiday Thank You Bonus"
                  required
                />
              </div>

              <div>
                <label style={labelStyle}>Description</label>
                <textarea
                  value={form.description}
                  onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                  style={{ ...inputStyle, resize: 'vertical' }}
                  rows={2}
                  placeholder="Thank you for being a loyal member!"
                />
              </div>

              <div>
                <label style={labelStyle}>Amount Per Member ($) *</label>
                <input
                  type="number"
                  value={form.amount_per_member}
                  onChange={e => setForm(f => ({ ...f, amount_per_member: parseFloat(e.target.value) || 0 }))}
                  style={inputStyle}
                  min="0.01"
                  step="0.01"
                  required
                />
              </div>

              <div>
                <label style={labelStyle}>Filter by Tier (optional)</label>
                <select
                  value={form.tier_filter}
                  onChange={e => setForm(f => ({ ...f, tier_filter: e.target.value }))}
                  style={selectStyle}
                >
                  <option value="">All Active Members</option>
                  <option value="SILVER">Silver Only</option>
                  <option value="GOLD">Gold Only</option>
                  <option value="PLATINUM">Platinum Only</option>
                  <option value="GOLD,PLATINUM">Gold & Platinum</option>
                </select>
              </div>

              <div style={{
                display: 'flex',
                gap: spacing[3],
                justifyContent: 'flex-end',
                paddingTop: spacing[4],
                borderTop: `1px solid ${colors.border}`,
              }}>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  style={{ ...secondaryButtonStyle, backgroundColor: 'transparent', border: 'none' }}
                >
                  Cancel
                </button>
                <button type="submit" style={primaryButtonStyle}>
                  Preview
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
