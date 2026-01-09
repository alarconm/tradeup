/**
 * Card Setup Queue - Members awaiting physical card setup
 * Shows members who haven't completed card setup with resend capabilities
 */
import { useState, useEffect, useCallback } from 'react'
import {
  CreditCard,
  Mail,
  MailCheck,
  RefreshCw,
  Search,
  Clock,
  AlertCircle,
  CheckCircle,
  User,
  Calendar,
  Send,
  Loader2,
} from 'lucide-react'
import { useTheme } from '../../contexts/ThemeContext'
import { radius, typography, spacing } from '../styles/tokens'

// Types for card setup queue
interface CardSetupMember {
  id: number
  member_number: string
  email: string
  name: string | null
  tier_name: string | null
  status: 'active' | 'pending' | 'paused' | 'cancelled'
  membership_start_date: string
  card_setup_sent_at: string | null
  card_setup_completed_at: string | null
  days_waiting: number
}

interface CardSetupStats {
  total_pending: number
  sent_today: number
  completed_today: number
  avg_wait_days: number
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000'

// Mock data for development until backend endpoint exists
const MOCK_MEMBERS: CardSetupMember[] = [
  {
    id: 1,
    member_number: 'ORB-2025-0042',
    email: 'john.smith@example.com',
    name: 'John Smith',
    tier_name: 'Gold',
    status: 'active',
    membership_start_date: '2025-01-02',
    card_setup_sent_at: '2025-01-02T10:00:00Z',
    card_setup_completed_at: null,
    days_waiting: 4,
  },
  {
    id: 2,
    member_number: 'ORB-2025-0038',
    email: 'sarah.johnson@example.com',
    name: 'Sarah Johnson',
    tier_name: 'Platinum',
    status: 'active',
    membership_start_date: '2024-12-28',
    card_setup_sent_at: '2024-12-28T14:30:00Z',
    card_setup_completed_at: null,
    days_waiting: 9,
  },
  {
    id: 3,
    member_number: 'ORB-2025-0045',
    email: 'mike.wilson@example.com',
    name: 'Mike Wilson',
    tier_name: 'Silver',
    status: 'active',
    membership_start_date: '2025-01-04',
    card_setup_sent_at: null,
    card_setup_completed_at: null,
    days_waiting: 2,
  },
]

const MOCK_STATS: CardSetupStats = {
  total_pending: 3,
  sent_today: 1,
  completed_today: 2,
  avg_wait_days: 5,
}

export default function CardSetupQueue() {
  const { colors, shadows } = useTheme()

  const [members, setMembers] = useState<CardSetupMember[]>([])
  const [stats, setStats] = useState<CardSetupStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [sendingId, setSendingId] = useState<number | null>(null)
  const [resendingAll, setResendingAll] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const fetchPendingMembers = useCallback(async () => {
    setLoading(true)
    try {
      const token = localStorage.getItem('admin_token')
      const response = await fetch(`${API_BASE}/api/members/card-setup-pending`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': '1',
          ...(token && { Authorization: `Bearer ${token}` }),
        },
      })

      if (response.ok) {
        const data = await response.json()
        setMembers(data.members || [])
        setStats(data.stats || null)
      } else {
        // Use mock data if endpoint not available
        setMembers(MOCK_MEMBERS)
        setStats(MOCK_STATS)
      }
    } catch (err) {
      console.error('Failed to fetch card setup queue:', err)
      // Use mock data on error
      setMembers(MOCK_MEMBERS)
      setStats(MOCK_STATS)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPendingMembers()
  }, [fetchPendingMembers])

  const sendSetupEmail = async (memberId: number) => {
    setSendingId(memberId)
    setSuccessMessage(null)
    setErrorMessage(null)

    try {
      const token = localStorage.getItem('admin_token')
      const response = await fetch(`${API_BASE}/api/members/${memberId}/send-card-setup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': '1',
          ...(token && { Authorization: `Bearer ${token}` }),
        },
      })

      if (response.ok) {
        setSuccessMessage('Setup email sent successfully!')
        // Update the member's sent_at in local state
        setMembers(prev =>
          prev.map(m =>
            m.id === memberId
              ? { ...m, card_setup_sent_at: new Date().toISOString() }
              : m
          )
        )
      } else {
        const error = await response.json()
        setErrorMessage(error.error || 'Failed to send email')
      }
    } catch (err) {
      console.error('Failed to send setup email:', err)
      setErrorMessage('Failed to send email. Please try again.')
    } finally {
      setSendingId(null)
      setTimeout(() => {
        setSuccessMessage(null)
        setErrorMessage(null)
      }, 3000)
    }
  }

  const resendAllEmails = async () => {
    setResendingAll(true)
    setSuccessMessage(null)
    setErrorMessage(null)

    try {
      const token = localStorage.getItem('admin_token')
      const response = await fetch(`${API_BASE}/api/members/resend-all-card-setup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': '1',
          ...(token && { Authorization: `Bearer ${token}` }),
        },
      })

      if (response.ok) {
        const data = await response.json()
        setSuccessMessage(`Sent ${data.sent_count || 0} setup emails!`)
        fetchPendingMembers()
      } else {
        const error = await response.json()
        setErrorMessage(error.error || 'Failed to resend emails')
      }
    } catch (err) {
      console.error('Failed to resend all emails:', err)
      setErrorMessage('Failed to resend emails. Please try again.')
    } finally {
      setResendingAll(false)
      setTimeout(() => {
        setSuccessMessage(null)
        setErrorMessage(null)
      }, 5000)
    }
  }

  // Filter members based on search
  const filteredMembers = members.filter(member => {
    if (!searchQuery) return true
    const query = searchQuery.toLowerCase()
    return (
      (member.member_number && member.member_number.toLowerCase().includes(query)) ||
      (member.email && member.email.toLowerCase().includes(query)) ||
      (member.name && member.name.toLowerCase().includes(query))
    )
  })

  // Styles
  const pageStyles: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: spacing[6],
  }

  const headerStyles: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: spacing[4],
  }

  const titleRowStyles: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    flexWrap: 'wrap',
    gap: spacing[4],
  }

  const titleStyles: React.CSSProperties = {
    fontSize: typography['2xl'],
    fontWeight: typography.bold,
    color: colors.text,
    display: 'flex',
    alignItems: 'center',
    gap: spacing[3],
  }

  const statsGridStyles: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
    gap: spacing[4],
  }

  const statCardStyles: React.CSSProperties = {
    backgroundColor: colors.bgSurface,
    borderRadius: radius.lg,
    border: `1px solid ${colors.border}`,
    padding: spacing[4],
    boxShadow: shadows.card,
  }

  const statLabelStyles: React.CSSProperties = {
    fontSize: typography.xs,
    fontWeight: typography.medium,
    color: colors.textSubdued,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  }

  const statValueStyles: React.CSSProperties = {
    fontSize: typography['2xl'],
    fontWeight: typography.bold,
    color: colors.text,
    marginTop: spacing[1],
  }

  const searchContainerStyles: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: spacing[3],
    flexWrap: 'wrap',
  }

  const searchInputStyles: React.CSSProperties = {
    flex: 1,
    minWidth: 200,
    padding: '10px 12px 10px 40px',
    backgroundColor: colors.bgSurface,
    border: `1px solid ${colors.border}`,
    borderRadius: radius.md,
    fontSize: typography.base,
    color: colors.text,
    outline: 'none',
  }

  const buttonPrimaryStyles: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing[2],
    padding: '10px 16px',
    backgroundColor: colors.primary,
    color: colors.textOnPrimary,
    border: 'none',
    borderRadius: radius.md,
    fontSize: typography.base,
    fontWeight: typography.medium,
    cursor: 'pointer',
    transition: 'background-color 150ms ease',
  }

  const buttonSecondaryStyles: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing[2],
    padding: '10px 16px',
    backgroundColor: colors.bgSurface,
    color: colors.text,
    border: `1px solid ${colors.border}`,
    borderRadius: radius.md,
    fontSize: typography.base,
    fontWeight: typography.medium,
    cursor: 'pointer',
    transition: 'all 150ms ease',
  }

  const tableContainerStyles: React.CSSProperties = {
    backgroundColor: colors.bgSurface,
    borderRadius: radius.lg,
    border: `1px solid ${colors.border}`,
    boxShadow: shadows.card,
    overflow: 'hidden',
  }

  const tableStyles: React.CSSProperties = {
    width: '100%',
    borderCollapse: 'collapse',
  }

  const thStyles: React.CSSProperties = {
    padding: spacing[4],
    textAlign: 'left',
    fontSize: typography.xs,
    fontWeight: typography.semibold,
    color: colors.textSubdued,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    borderBottom: `1px solid ${colors.border}`,
    backgroundColor: colors.bgSubdued,
  }

  const tdStyles: React.CSSProperties = {
    padding: spacing[4],
    fontSize: typography.base,
    color: colors.text,
    borderBottom: `1px solid ${colors.borderSubdued}`,
  }

  const memberInfoStyles: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: spacing[1],
  }

  const memberNameStyles: React.CSSProperties = {
    fontWeight: typography.medium,
    color: colors.text,
  }

  const memberEmailStyles: React.CSSProperties = {
    fontSize: typography.sm,
    color: colors.textSecondary,
  }

  const badgeStyles = (variant: 'warning' | 'success' | 'critical' | 'default'): React.CSSProperties => {
    const variants = {
      warning: { bg: colors.warningLight, color: colors.warning },
      success: { bg: colors.successLight, color: colors.success },
      critical: { bg: colors.criticalLight, color: colors.critical },
      default: { bg: colors.bgSubdued, color: colors.textSecondary },
    }
    const v = variants[variant]
    return {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
      padding: '4px 10px',
      backgroundColor: v.bg,
      color: v.color,
      borderRadius: radius.full,
      fontSize: typography.xs,
      fontWeight: typography.medium,
    }
  }

  const getWaitingBadgeVariant = (days: number): 'warning' | 'success' | 'critical' | 'default' => {
    if (days >= 7) return 'critical'
    if (days >= 3) return 'warning'
    return 'default'
  }

  const emptyStateStyles: React.CSSProperties = {
    padding: spacing[16],
    textAlign: 'center',
    color: colors.textSecondary,
  }

  const alertStyles = (type: 'success' | 'error'): React.CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    gap: spacing[2],
    padding: spacing[4],
    borderRadius: radius.md,
    backgroundColor: type === 'success' ? colors.successLight : colors.criticalLight,
    color: type === 'success' ? colors.success : colors.critical,
    fontSize: typography.sm,
    fontWeight: typography.medium,
  })

  return (
    <div style={pageStyles}>
      {/* Header */}
      <div style={headerStyles}>
        <div style={titleRowStyles}>
          <h1 style={titleStyles}>
            <CreditCard size={28} style={{ color: colors.primary }} />
            Card Setup Queue
          </h1>
          <div style={{ display: 'flex', gap: spacing[3] }}>
            <button
              onClick={fetchPendingMembers}
              style={buttonSecondaryStyles}
              disabled={loading}
              onMouseEnter={e => {
                e.currentTarget.style.backgroundColor = colors.bgSurfaceHover
              }}
              onMouseLeave={e => {
                e.currentTarget.style.backgroundColor = colors.bgSurface
              }}
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
              Refresh
            </button>
            <button
              onClick={resendAllEmails}
              style={buttonPrimaryStyles}
              disabled={resendingAll || filteredMembers.length === 0}
              onMouseEnter={e => {
                e.currentTarget.style.backgroundColor = colors.primaryHover
              }}
              onMouseLeave={e => {
                e.currentTarget.style.backgroundColor = colors.primary
              }}
            >
              {resendingAll ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Send size={16} />
              )}
              Resend All
            </button>
          </div>
        </div>

        {/* Alerts */}
        {successMessage && (
          <div style={alertStyles('success')}>
            <CheckCircle size={16} />
            {successMessage}
          </div>
        )}
        {errorMessage && (
          <div style={alertStyles('error')}>
            <AlertCircle size={16} />
            {errorMessage}
          </div>
        )}

        {/* Stats */}
        {stats && (
          <div style={statsGridStyles}>
            <div style={statCardStyles}>
              <div style={statLabelStyles}>Pending Setup</div>
              <div style={statValueStyles}>{stats.total_pending}</div>
            </div>
            <div style={statCardStyles}>
              <div style={statLabelStyles}>Sent Today</div>
              <div style={statValueStyles}>{stats.sent_today}</div>
            </div>
            <div style={statCardStyles}>
              <div style={statLabelStyles}>Completed Today</div>
              <div style={statValueStyles}>{stats.completed_today}</div>
            </div>
            <div style={statCardStyles}>
              <div style={statLabelStyles}>Avg. Wait (Days)</div>
              <div style={statValueStyles}>{stats.avg_wait_days}</div>
            </div>
          </div>
        )}

        {/* Search */}
        <div style={searchContainerStyles}>
          <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
            <Search
              size={18}
              style={{
                position: 'absolute',
                left: 12,
                top: '50%',
                transform: 'translateY(-50%)',
                color: colors.textSubdued,
              }}
            />
            <input
              type="text"
              placeholder="Search by name, email, or member number..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={searchInputStyles}
            />
          </div>
        </div>
      </div>

      {/* Table */}
      <div style={tableContainerStyles}>
        {loading ? (
          <div style={{ ...emptyStateStyles, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: spacing[3] }}>
            <Loader2 size={24} className="animate-spin" style={{ color: colors.primary }} />
            <span>Loading queue...</span>
          </div>
        ) : filteredMembers.length === 0 ? (
          <div style={emptyStateStyles}>
            <MailCheck size={48} style={{ color: colors.success, marginBottom: spacing[4], opacity: 0.5 }} />
            <p style={{ fontSize: typography.lg, fontWeight: typography.medium, marginBottom: spacing[2] }}>
              {searchQuery ? 'No matching members found' : 'All caught up!'}
            </p>
            <p style={{ color: colors.textSubdued }}>
              {searchQuery
                ? 'Try adjusting your search terms'
                : 'All members have completed their card setup.'}
            </p>
          </div>
        ) : (
          <table style={tableStyles}>
            <thead>
              <tr>
                <th style={thStyles}>Member</th>
                <th style={thStyles}>Member #</th>
                <th style={thStyles}>Tier</th>
                <th style={thStyles}>Email Status</th>
                <th style={thStyles}>Waiting</th>
                <th style={{ ...thStyles, textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredMembers.map(member => (
                <tr
                  key={member.id}
                  style={{ transition: 'background-color 150ms ease' }}
                  onMouseEnter={e => {
                    e.currentTarget.style.backgroundColor = colors.bgSurfaceHover
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.backgroundColor = 'transparent'
                  }}
                >
                  <td style={tdStyles}>
                    <div style={memberInfoStyles}>
                      <div style={memberNameStyles}>
                        <User size={14} style={{ marginRight: 6, verticalAlign: 'middle', opacity: 0.5 }} />
                        {member.name || 'No name'}
                      </div>
                      <div style={memberEmailStyles}>{member.email}</div>
                    </div>
                  </td>
                  <td style={tdStyles}>
                    <span style={{ fontFamily: 'monospace', fontSize: typography.sm }}>
                      {member.member_number}
                    </span>
                  </td>
                  <td style={tdStyles}>
                    <span style={badgeStyles('default')}>{member.tier_name || 'No tier'}</span>
                  </td>
                  <td style={tdStyles}>
                    {member.card_setup_sent_at ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: spacing[2] }}>
                        <Mail size={14} style={{ color: colors.success }} />
                        <span style={{ fontSize: typography.sm, color: colors.textSecondary }}>
                          Sent {new Date(member.card_setup_sent_at).toLocaleDateString()}
                        </span>
                      </div>
                    ) : (
                      <span style={badgeStyles('warning')}>
                        <AlertCircle size={12} />
                        Not sent
                      </span>
                    )}
                  </td>
                  <td style={tdStyles}>
                    <span style={badgeStyles(getWaitingBadgeVariant(member.days_waiting))}>
                      <Clock size={12} />
                      {member.days_waiting} day{member.days_waiting !== 1 ? 's' : ''}
                    </span>
                  </td>
                  <td style={{ ...tdStyles, textAlign: 'right' }}>
                    <button
                      onClick={() => sendSetupEmail(member.id)}
                      disabled={sendingId === member.id}
                      style={{
                        ...buttonSecondaryStyles,
                        padding: '6px 12px',
                        fontSize: typography.sm,
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.backgroundColor = colors.bgSurfaceHover
                        e.currentTarget.style.borderColor = colors.borderHover
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.backgroundColor = colors.bgSurface
                        e.currentTarget.style.borderColor = colors.border
                      }}
                    >
                      {sendingId === member.id ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <Mail size={14} />
                      )}
                      {member.card_setup_sent_at ? 'Resend' : 'Send'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Info footer */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: spacing[2],
          padding: spacing[4],
          backgroundColor: colors.bgSubdued,
          borderRadius: radius.md,
          fontSize: typography.sm,
          color: colors.textSecondary,
        }}
      >
        <Calendar size={16} />
        <span>
          Members are added to this queue when they join and need to complete card setup.
          Setup emails contain instructions for collecting shipping information for their physical membership card.
        </span>
      </div>
    </div>
  )
}
