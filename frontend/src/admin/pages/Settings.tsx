/**
 * Settings - Premium Admin Settings with Dark Mode Support
 * Shopify Polaris-inspired design system
 */
import { useState, useEffect } from 'react'
import {
  UserPlus,
  Bell,
  Palette,
  Save,
  Loader2,
  AlertCircle,
  Check,
  Image as ImageIcon,
  Type,
  Droplets,
  Layout,
  ExternalLink,
} from 'lucide-react'
import {
  getSettings,
  updateAutoEnrollment,
  updateNotifications,
  updateSettings,
  getTiers,
  type TenantSettings,
  type Tier,
} from '../api/adminApi'
import { useTheme } from '../../contexts/ThemeContext'
import { radius, typography, spacing, useResponsive } from '../styles/tokens'

// Toggle Switch Component
function ToggleSwitch({
  checked,
  onChange,
  size = 'normal',
  colors,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  size?: 'normal' | 'small'
  colors: ReturnType<typeof useTheme>['colors']
}) {
  const width = size === 'small' ? 36 : 44
  const height = size === 'small' ? 20 : 24
  const knobSize = size === 'small' ? 16 : 20

  return (
    <div
      onClick={() => onChange(!checked)}
      style={{
        position: 'relative',
        width,
        height,
        backgroundColor: checked ? colors.primary : colors.borderSubdued,
        borderRadius: height / 2,
        cursor: 'pointer',
        transition: 'background-color 200ms ease',
        flexShrink: 0,
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: checked ? width - knobSize - 2 : 2,
          transform: 'translateY(-50%)',
          width: knobSize,
          height: knobSize,
          backgroundColor: '#fff',
          borderRadius: '50%',
          transition: 'left 200ms ease',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.2)',
        }}
      />
    </div>
  )
}

// Color Picker Component
function ColorPicker({
  label,
  value,
  onChange,
  colors,
}: {
  label: string
  value: string
  onChange: (color: string) => void
  colors: ReturnType<typeof useTheme>['colors']
}) {
  return (
    <div>
      <label
        style={{
          display: 'block',
          fontSize: typography.sm,
          fontWeight: typography.medium,
          color: colors.text,
          marginBottom: spacing[2],
        }}
      >
        {label}
      </label>
      <div style={{ display: 'flex', alignItems: 'center', gap: spacing[3] }}>
        <div
          style={{
            position: 'relative',
            width: 44,
            height: 44,
            borderRadius: radius.md,
            border: `2px solid ${colors.border}`,
            overflow: 'hidden',
            cursor: 'pointer',
          }}
        >
          <input
            type="color"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            style={{
              position: 'absolute',
              inset: -8,
              width: 'calc(100% + 16px)',
              height: 'calc(100% + 16px)',
              cursor: 'pointer',
              border: 'none',
            }}
          />
        </div>
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          style={{
            flex: 1,
            padding: '10px 12px',
            backgroundColor: colors.bgSurface,
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
            fontSize: typography.sm,
            color: colors.text,
            fontFamily: 'monospace',
            outline: 'none',
          }}
        />
      </div>
    </div>
  )
}

export default function Settings() {
  const { colors, shadows } = useTheme()
  const breakpoint = useResponsive()

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [settings, setSettings] = useState<TenantSettings | null>(null)
  const [tiers, setTiers] = useState<Tier[]>([])
  const [activeTab, setActiveTab] = useState<'enrollment' | 'notifications' | 'branding'>('enrollment')

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    try {
      const [settingsResult, tiersResult] = await Promise.all([
        getSettings(),
        getTiers(),
      ])
      setSettings(settingsResult.settings)
      setTiers(tiersResult.tiers || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings')
    } finally {
      setLoading(false)
    }
  }

  async function handleAutoEnrollmentSave() {
    if (!settings) return
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      const result = await updateAutoEnrollment(settings.auto_enrollment)
      setSettings(result.settings)
      setSuccess('Auto-enrollment settings saved')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  async function handleNotificationsSave() {
    if (!settings) return
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      const result = await updateNotifications(settings.notifications)
      setSettings(result.settings)
      setSuccess('Notification settings saved')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  async function handleBrandingSave() {
    if (!settings) return
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      const result = await updateSettings({ branding: settings.branding })
      setSettings(result.settings)
      setSuccess('Branding settings saved')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  // Styles
  const cardStyle: React.CSSProperties = {
    backgroundColor: colors.bgSurface,
    borderRadius: radius.lg,
    border: `1px solid ${colors.border}`,
    boxShadow: shadows.card,
    padding: breakpoint === 'mobile' ? spacing[4] : spacing[6],
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
    transition: 'border-color 150ms ease, box-shadow 150ms ease',
  }

  const selectStyle: React.CSSProperties = {
    ...inputStyle,
    cursor: 'pointer',
  }

  const labelStyle: React.CSSProperties = {
    display: 'block',
    fontSize: typography.sm,
    fontWeight: typography.medium,
    color: colors.text,
    marginBottom: spacing[2],
  }

  const getTabStyle = (isActive: boolean): React.CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    gap: spacing[2],
    padding: '12px 16px',
    fontWeight: typography.medium,
    fontSize: typography.base,
    color: isActive ? colors.primary : colors.textSecondary,
    backgroundColor: isActive ? colors.primaryLight : 'transparent',
    borderRadius: radius.md,
    border: 'none',
    cursor: 'pointer',
    transition: 'all 150ms ease',
    whiteSpace: 'nowrap',
  })

  const saveButtonStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: spacing[2],
    padding: '10px 20px',
    backgroundColor: saving ? colors.bgSubdued : colors.primary,
    color: saving ? colors.textSubdued : colors.textOnPrimary,
    border: 'none',
    borderRadius: radius.md,
    fontSize: typography.base,
    fontWeight: typography.medium,
    cursor: saving ? 'not-allowed' : 'pointer',
    transition: 'background 150ms ease',
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 256 }}>
        <Loader2 size={32} style={{ color: colors.primary }} className="animate-spin" />
      </div>
    )
  }

  if (!settings) {
    return (
      <div style={{ ...cardStyle, textAlign: 'center', padding: spacing[12] }}>
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: 28,
            backgroundColor: colors.criticalLight,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 16px',
          }}
        >
          <AlertCircle size={28} style={{ color: colors.critical }} />
        </div>
        <div style={{ fontSize: typography.md, fontWeight: typography.semibold, color: colors.text, marginBottom: 4 }}>
          Failed to load settings
        </div>
        <div style={{ fontSize: typography.base, color: colors.textSecondary }}>{error || 'Please try again'}</div>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: spacing[6] }}>
        <h1
          style={{
            fontSize: typography['2xl'],
            fontWeight: typography.bold,
            color: colors.text,
            margin: 0,
            letterSpacing: '-0.5px',
          }}
        >
          Settings
        </h1>
        <p style={{ fontSize: typography.base, color: colors.textSecondary, margin: '4px 0 0 0' }}>
          Manage your TradeUp configuration
        </p>
      </div>

      {/* Alerts */}
      {success && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: spacing[2],
            padding: spacing[4],
            backgroundColor: colors.successLight,
            border: `1px solid ${colors.success}`,
            borderRadius: radius.md,
            color: colors.success,
            fontSize: typography.base,
            marginBottom: spacing[4],
          }}
        >
          <Check size={18} />
          {success}
        </div>
      )}
      {error && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: spacing[2],
            padding: spacing[4],
            backgroundColor: colors.criticalLight,
            border: `1px solid ${colors.critical}`,
            borderRadius: radius.md,
            color: colors.critical,
            fontSize: typography.base,
            marginBottom: spacing[4],
          }}
        >
          <AlertCircle size={18} />
          {error}
        </div>
      )}

      {/* Tab Navigation */}
      <div
        style={{
          display: 'flex',
          gap: spacing[2],
          marginBottom: spacing[6],
          overflowX: 'auto',
          paddingBottom: 4,
        }}
      >
        <button
          onClick={() => setActiveTab('enrollment')}
          style={getTabStyle(activeTab === 'enrollment')}
          onMouseEnter={(e) => {
            if (activeTab !== 'enrollment') {
              e.currentTarget.style.backgroundColor = colors.bgSurfaceHover
            }
          }}
          onMouseLeave={(e) => {
            if (activeTab !== 'enrollment') {
              e.currentTarget.style.backgroundColor = 'transparent'
            }
          }}
        >
          <UserPlus size={18} />
          Auto-Enrollment
        </button>
        <button
          onClick={() => setActiveTab('notifications')}
          style={getTabStyle(activeTab === 'notifications')}
          onMouseEnter={(e) => {
            if (activeTab !== 'notifications') {
              e.currentTarget.style.backgroundColor = colors.bgSurfaceHover
            }
          }}
          onMouseLeave={(e) => {
            if (activeTab !== 'notifications') {
              e.currentTarget.style.backgroundColor = 'transparent'
            }
          }}
        >
          <Bell size={18} />
          Notifications
        </button>
        <button
          onClick={() => setActiveTab('branding')}
          style={getTabStyle(activeTab === 'branding')}
          onMouseEnter={(e) => {
            if (activeTab !== 'branding') {
              e.currentTarget.style.backgroundColor = colors.bgSurfaceHover
            }
          }}
          onMouseLeave={(e) => {
            if (activeTab !== 'branding') {
              e.currentTarget.style.backgroundColor = 'transparent'
            }
          }}
        >
          <Palette size={18} />
          Branding
        </button>
      </div>

      {/* Auto-Enrollment Settings */}
      {activeTab === 'enrollment' && (
        <div style={cardStyle}>
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              gap: spacing[4],
              marginBottom: spacing[6],
            }}
          >
            <div>
              <h2 style={{ fontSize: typography.md, fontWeight: typography.semibold, color: colors.text, margin: 0 }}>
                Auto-Enrollment
              </h2>
              <p style={{ fontSize: typography.base, color: colors.textSecondary, margin: '4px 0 0 0' }}>
                Automatically enroll customers when they make their first purchase
              </p>
            </div>
            <ToggleSwitch
              colors={colors}
              checked={settings.auto_enrollment.enabled}
              onChange={(checked) =>
                setSettings({
                  ...settings,
                  auto_enrollment: { ...settings.auto_enrollment, enabled: checked },
                })
              }
            />
          </div>

          {settings.auto_enrollment.enabled && (
            <div style={{ borderTop: `1px solid ${colors.border}`, paddingTop: spacing[6] }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: spacing[5] }}>
                {/* Default Tier */}
                <div>
                  <label style={labelStyle}>Default Tier</label>
                  <select
                    value={settings.auto_enrollment.default_tier_id || ''}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        auto_enrollment: {
                          ...settings.auto_enrollment,
                          default_tier_id: e.target.value ? parseInt(e.target.value) : null,
                        },
                      })
                    }
                    style={selectStyle}
                  >
                    <option value="">Lowest tier (auto)</option>
                    {tiers.map((tier) => (
                      <option key={tier.id} value={tier.id}>
                        {tier.name} ({((tier.bonus_rate || 0) * 100).toFixed(0)}% bonus)
                      </option>
                    ))}
                  </select>
                  <p style={{ fontSize: typography.xs, color: colors.textSubdued, marginTop: 4 }}>
                    The tier new members will be assigned to
                  </p>
                </div>

                {/* Minimum Order Value */}
                <div>
                  <label style={labelStyle}>Minimum Order Value</label>
                  <div style={{ position: 'relative', maxWidth: 200 }}>
                    <span
                      style={{
                        position: 'absolute',
                        left: 12,
                        top: '50%',
                        transform: 'translateY(-50%)',
                        color: colors.textSubdued,
                        fontSize: typography.base,
                      }}
                    >
                      $
                    </span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={settings.auto_enrollment.min_order_value}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          auto_enrollment: {
                            ...settings.auto_enrollment,
                            min_order_value: parseFloat(e.target.value) || 0,
                          },
                        })
                      }
                      style={{ ...inputStyle, paddingLeft: 28 }}
                    />
                  </div>
                  <p style={{ fontSize: typography.xs, color: colors.textSubdued, marginTop: 4 }}>
                    Only enroll on orders above this value (0 = any order)
                  </p>
                </div>

                {/* Excluded Tags */}
                <div>
                  <label style={labelStyle}>Excluded Customer Tags</label>
                  <input
                    type="text"
                    placeholder="wholesale, staff, test (comma-separated)"
                    value={settings.auto_enrollment.excluded_tags.join(', ')}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        auto_enrollment: {
                          ...settings.auto_enrollment,
                          excluded_tags: e.target.value
                            .split(',')
                            .map((t) => t.trim())
                            .filter((t) => t),
                        },
                      })
                    }
                    style={inputStyle}
                  />
                  <p style={{ fontSize: typography.xs, color: colors.textSubdued, marginTop: 4 }}>
                    Customers with these tags won't be auto-enrolled
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Save Button */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              paddingTop: spacing[6],
              borderTop: `1px solid ${colors.border}`,
              marginTop: spacing[6],
            }}
          >
            <button
              onClick={handleAutoEnrollmentSave}
              disabled={saving}
              style={saveButtonStyle}
              onMouseEnter={(e) => {
                if (!saving) e.currentTarget.style.backgroundColor = colors.primaryHover
              }}
              onMouseLeave={(e) => {
                if (!saving) e.currentTarget.style.backgroundColor = colors.primary
              }}
            >
              {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              Save Changes
            </button>
          </div>
        </div>
      )}

      {/* Notification Settings */}
      {activeTab === 'notifications' && (
        <div style={cardStyle}>
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              gap: spacing[4],
              marginBottom: spacing[6],
            }}
          >
            <div>
              <h2 style={{ fontSize: typography.md, fontWeight: typography.semibold, color: colors.text, margin: 0 }}>
                Email Notifications
              </h2>
              <p style={{ fontSize: typography.base, color: colors.textSecondary, margin: '4px 0 0 0' }}>
                Configure which emails are sent to members
              </p>
            </div>
            <ToggleSwitch
              colors={colors}
              checked={settings.notifications.enabled}
              onChange={(checked) =>
                setSettings({
                  ...settings,
                  notifications: { ...settings.notifications, enabled: checked },
                })
              }
            />
          </div>

          {settings.notifications.enabled && (
            <div style={{ borderTop: `1px solid ${colors.border}`, paddingTop: spacing[6] }}>
              {/* Email Types */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: spacing[3], marginBottom: spacing[6] }}>
                {[
                  { key: 'welcome_email', label: 'Welcome Email', desc: 'Sent when a new member is enrolled' },
                  { key: 'trade_in_updates', label: 'Trade-in Updates', desc: 'Sent when trade-ins are submitted and completed' },
                  { key: 'tier_change', label: 'Tier Changes', desc: "Sent when a member's tier is upgraded" },
                  { key: 'credit_issued', label: 'Credit Issued', desc: 'For non-trade-in credits (promotions, adjustments)' },
                ].map(({ key, label, desc }) => (
                  <div
                    key={key}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: spacing[4],
                      backgroundColor: colors.bgSubdued,
                      borderRadius: radius.md,
                      gap: spacing[4],
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: typography.base, fontWeight: typography.medium, color: colors.text }}>{label}</div>
                      <div style={{ fontSize: typography.sm, color: colors.textSubdued, marginTop: 2 }}>{desc}</div>
                    </div>
                    <ToggleSwitch
                      colors={colors}
                      size="small"
                      checked={settings.notifications[key as keyof typeof settings.notifications] as boolean}
                      onChange={(checked) =>
                        setSettings({
                          ...settings,
                          notifications: { ...settings.notifications, [key]: checked },
                        })
                      }
                    />
                  </div>
                ))}
              </div>

              {/* From Settings */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: breakpoint === 'mobile' ? '1fr' : '1fr 1fr',
                  gap: spacing[4],
                }}
              >
                <div>
                  <label style={labelStyle}>From Name</label>
                  <input
                    type="text"
                    placeholder="Shop name (default)"
                    value={settings.notifications.from_name || ''}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        notifications: { ...settings.notifications, from_name: e.target.value || null },
                      })
                    }
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label style={labelStyle}>From Email</label>
                  <input
                    type="email"
                    placeholder="noreply@yourshop.com"
                    value={settings.notifications.from_email || ''}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        notifications: { ...settings.notifications, from_email: e.target.value || null },
                      })
                    }
                    style={inputStyle}
                  />
                </div>
              </div>
              <p style={{ fontSize: typography.xs, color: colors.textSubdued, marginTop: spacing[2] }}>
                Email must be verified in SendGrid to use as sender
              </p>
            </div>
          )}

          {/* Save Button */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              paddingTop: spacing[6],
              borderTop: `1px solid ${colors.border}`,
              marginTop: spacing[6],
            }}
          >
            <button
              onClick={handleNotificationsSave}
              disabled={saving}
              style={saveButtonStyle}
              onMouseEnter={(e) => {
                if (!saving) e.currentTarget.style.backgroundColor = colors.primaryHover
              }}
              onMouseLeave={(e) => {
                if (!saving) e.currentTarget.style.backgroundColor = colors.primary
              }}
            >
              {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              Save Changes
            </button>
          </div>
        </div>
      )}

      {/* Branding Settings */}
      {activeTab === 'branding' && (
        <div style={cardStyle}>
          <div style={{ marginBottom: spacing[6] }}>
            <h2 style={{ fontSize: typography.md, fontWeight: typography.semibold, color: colors.text, margin: 0 }}>
              Branding
            </h2>
            <p style={{ fontSize: typography.base, color: colors.textSecondary, margin: '4px 0 0 0' }}>
              Customize the look and feel of your TradeUp experience
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing[6] }}>
            {/* App Name */}
            <div>
              <label style={labelStyle}>
                <Type size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                Program Name
              </label>
              <input
                type="text"
                placeholder="TradeUp Rewards"
                value={settings.branding.app_name}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    branding: { ...settings.branding, app_name: e.target.value },
                  })
                }
                style={inputStyle}
              />
              <p style={{ fontSize: typography.xs, color: colors.textSubdued, marginTop: 4 }}>
                Displayed in emails and the customer portal
              </p>
            </div>

            {/* Tagline */}
            <div>
              <label style={labelStyle}>Tagline</label>
              <input
                type="text"
                placeholder="Earn rewards on every trade-in"
                value={settings.branding.tagline}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    branding: { ...settings.branding, tagline: e.target.value },
                  })
                }
                style={inputStyle}
              />
            </div>

            {/* Logo URLs */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: breakpoint === 'mobile' ? '1fr' : '1fr 1fr',
                gap: spacing[4],
              }}
            >
              <div>
                <label style={labelStyle}>
                  <ImageIcon size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                  Logo URL (Light Mode)
                </label>
                <div style={{ display: 'flex', gap: spacing[2] }}>
                  <input
                    type="url"
                    placeholder="https://..."
                    value={settings.branding.logo_url || ''}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        branding: { ...settings.branding, logo_url: e.target.value || null },
                      })
                    }
                    style={{ ...inputStyle, flex: 1 }}
                  />
                  {settings.branding.logo_url && (
                    <a
                      href={settings.branding.logo_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: 42,
                        backgroundColor: colors.bgSurface,
                        border: `1px solid ${colors.border}`,
                        borderRadius: radius.md,
                        color: colors.textSecondary,
                      }}
                    >
                      <ExternalLink size={16} />
                    </a>
                  )}
                </div>
              </div>
              <div>
                <label style={labelStyle}>
                  <ImageIcon size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                  Logo URL (Dark Mode)
                </label>
                <div style={{ display: 'flex', gap: spacing[2] }}>
                  <input
                    type="url"
                    placeholder="https://... (optional)"
                    value={settings.branding.logo_dark_url || ''}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        branding: { ...settings.branding, logo_dark_url: e.target.value || null },
                      })
                    }
                    style={{ ...inputStyle, flex: 1 }}
                  />
                  {settings.branding.logo_dark_url && (
                    <a
                      href={settings.branding.logo_dark_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: 42,
                        backgroundColor: colors.bgSurface,
                        border: `1px solid ${colors.border}`,
                        borderRadius: radius.md,
                        color: colors.textSecondary,
                      }}
                    >
                      <ExternalLink size={16} />
                    </a>
                  )}
                </div>
              </div>
            </div>

            {/* Colors */}
            <div>
              <div
                style={{
                  fontSize: typography.sm,
                  fontWeight: typography.medium,
                  color: colors.text,
                  marginBottom: spacing[4],
                  display: 'flex',
                  alignItems: 'center',
                  gap: spacing[2],
                }}
              >
                <Droplets size={14} />
                Brand Colors
              </div>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: breakpoint === 'mobile' ? '1fr' : 'repeat(2, 1fr)',
                  gap: spacing[4],
                }}
              >
                <ColorPicker
                  label="Primary Color"
                  value={settings.branding.colors.primary}
                  onChange={(color) =>
                    setSettings({
                      ...settings,
                      branding: {
                        ...settings.branding,
                        colors: { ...settings.branding.colors, primary: color },
                      },
                    })
                  }
                  colors={colors}
                />
                <ColorPicker
                  label="Accent Color"
                  value={settings.branding.colors.accent}
                  onChange={(color) =>
                    setSettings({
                      ...settings,
                      branding: {
                        ...settings.branding,
                        colors: { ...settings.branding.colors, accent: color },
                      },
                    })
                  }
                  colors={colors}
                />
              </div>
            </div>

            {/* Style Preference */}
            <div>
              <label style={labelStyle}>
                <Layout size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                UI Style
              </label>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: breakpoint === 'mobile' ? '1fr' : 'repeat(3, 1fr)',
                  gap: spacing[3],
                }}
              >
                {[
                  { value: 'glass', label: 'Glass', desc: 'Translucent panels with blur effects' },
                  { value: 'solid', label: 'Solid', desc: 'Clean opaque backgrounds' },
                  { value: 'minimal', label: 'Minimal', desc: 'Subtle borders, flat design' },
                ].map(({ value, label, desc }) => {
                  const isSelected = settings.branding.style === value
                  return (
                    <button
                      key={value}
                      type="button"
                      onClick={() =>
                        setSettings({
                          ...settings,
                          branding: { ...settings.branding, style: value as 'glass' | 'solid' | 'minimal' },
                        })
                      }
                      style={{
                        padding: spacing[4],
                        borderRadius: radius.md,
                        border: isSelected ? `2px solid ${colors.primary}` : `1px solid ${colors.border}`,
                        backgroundColor: isSelected ? colors.primarySubtle : colors.bgSurface,
                        textAlign: 'left',
                        cursor: 'pointer',
                        transition: 'all 150ms ease',
                      }}
                      onMouseEnter={(e) => {
                        if (!isSelected) {
                          e.currentTarget.style.borderColor = colors.primary
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!isSelected) {
                          e.currentTarget.style.borderColor = colors.border
                        }
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          marginBottom: 4,
                        }}
                      >
                        <span style={{ fontWeight: typography.medium, color: colors.text, fontSize: typography.base }}>
                          {label}
                        </span>
                        {isSelected && <Check size={16} style={{ color: colors.primary }} />}
                      </div>
                      <p style={{ fontSize: typography.xs, color: colors.textSecondary, margin: 0 }}>{desc}</p>
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Preview */}
            <div
              style={{
                padding: spacing[4],
                backgroundColor: colors.bgSubdued,
                borderRadius: radius.md,
                border: `1px solid ${colors.borderSubdued}`,
              }}
            >
              <div style={{ fontSize: typography.xs, fontWeight: typography.medium, color: colors.textSubdued, marginBottom: spacing[3], textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Preview
              </div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: spacing[3],
                  padding: spacing[4],
                  backgroundColor: colors.bgSurface,
                  borderRadius: radius.md,
                  border: `1px solid ${colors.border}`,
                }}
              >
                {settings.branding.logo_url ? (
                  <img
                    src={settings.branding.logo_url}
                    alt="Logo"
                    style={{ width: 40, height: 40, objectFit: 'contain', borderRadius: radius.sm }}
                    onError={(e) => {
                      e.currentTarget.style.display = 'none'
                    }}
                  />
                ) : (
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: radius.sm,
                      backgroundColor: settings.branding.colors.primary,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#fff',
                      fontWeight: typography.bold,
                      fontSize: typography.lg,
                    }}
                  >
                    {settings.branding.app_name.charAt(0)}
                  </div>
                )}
                <div>
                  <div style={{ fontWeight: typography.semibold, color: colors.text, fontSize: typography.md }}>
                    {settings.branding.app_name || 'TradeUp'}
                  </div>
                  <div style={{ fontSize: typography.sm, color: colors.textSecondary }}>
                    {settings.branding.tagline || 'Loyalty Program'}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Save Button */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              paddingTop: spacing[6],
              borderTop: `1px solid ${colors.border}`,
              marginTop: spacing[6],
            }}
          >
            <button
              onClick={handleBrandingSave}
              disabled={saving}
              style={saveButtonStyle}
              onMouseEnter={(e) => {
                if (!saving) e.currentTarget.style.backgroundColor = colors.primaryHover
              }}
              onMouseLeave={(e) => {
                if (!saving) e.currentTarget.style.backgroundColor = colors.primary
              }}
            >
              {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              Save Changes
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
