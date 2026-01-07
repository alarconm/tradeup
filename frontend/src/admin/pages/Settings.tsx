/**
 * Settings Page
 * Configure auto-enrollment, notifications, and branding
 */
import { useState, useEffect } from 'react';
import {
  UserPlus,
  Bell,
  Palette,
  Save,
  Loader2,
  AlertCircle,
  Check,
} from 'lucide-react';
import {
  getSettings,
  updateAutoEnrollment,
  updateNotifications,
  getTiers,
  type TenantSettings,
  type Tier,
} from '../api/adminApi';

export default function Settings() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [settings, setSettings] = useState<TenantSettings | null>(null);
  const [tiers, setTiers] = useState<Tier[]>([]);
  const [activeTab, setActiveTab] = useState<'enrollment' | 'notifications' | 'branding'>('enrollment');

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      const [settingsResult, tiersResult] = await Promise.all([
        getSettings(),
        getTiers(),
      ]);
      setSettings(settingsResult.settings);
      setTiers(tiersResult.tiers || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  }

  async function handleAutoEnrollmentSave() {
    if (!settings) return;

    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await updateAutoEnrollment(settings.auto_enrollment);
      setSettings(result.settings);
      setSuccess('Auto-enrollment settings saved');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  }

  async function handleNotificationsSave() {
    if (!settings) return;

    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await updateNotifications(settings.notifications);
      setSettings(result.settings);
      setSuccess('Notification settings saved');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-orange-500" />
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="glass-card p-8 text-center">
        <AlertCircle className="w-16 h-16 text-red-400 mx-auto mb-4" />
        <p className="text-red-400">{error || 'Failed to load settings'}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Settings</h1>
      </div>

      {/* Success/Error Messages */}
      {success && (
        <div className="flex items-center gap-2 px-4 py-3 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400">
          <Check className="w-5 h-5" />
          {success}
        </div>
      )}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400">
          <AlertCircle className="w-5 h-5" />
          {error}
        </div>
      )}

      {/* Tab Navigation */}
      <div className="flex gap-2 border-b border-slate-700/50">
        <button
          onClick={() => setActiveTab('enrollment')}
          className={`flex items-center gap-2 px-4 py-3 font-medium transition-colors ${
            activeTab === 'enrollment'
              ? 'text-orange-500 border-b-2 border-orange-500'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <UserPlus className="w-4 h-4" />
          Auto-Enrollment
        </button>
        <button
          onClick={() => setActiveTab('notifications')}
          className={`flex items-center gap-2 px-4 py-3 font-medium transition-colors ${
            activeTab === 'notifications'
              ? 'text-orange-500 border-b-2 border-orange-500'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <Bell className="w-4 h-4" />
          Notifications
        </button>
        <button
          onClick={() => setActiveTab('branding')}
          className={`flex items-center gap-2 px-4 py-3 font-medium transition-colors ${
            activeTab === 'branding'
              ? 'text-orange-500 border-b-2 border-orange-500'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <Palette className="w-4 h-4" />
          Branding
        </button>
      </div>

      {/* Auto-Enrollment Settings */}
      {activeTab === 'enrollment' && (
        <div className="glass-card p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">Auto-Enrollment</h2>
              <p className="text-sm text-slate-400">
                Automatically enroll customers when they make their first purchase
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings.auto_enrollment.enabled}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    auto_enrollment: {
                      ...settings.auto_enrollment,
                      enabled: e.target.checked,
                    },
                  })
                }
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-orange-500"></div>
            </label>
          </div>

          {settings.auto_enrollment.enabled && (
            <>
              <div className="border-t border-slate-700/50 pt-6 space-y-4">
                {/* Default Tier */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Default Tier
                  </label>
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
                    className="w-full px-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-orange-500/50"
                  >
                    <option value="">Lowest tier (auto)</option>
                    {tiers.map((tier) => (
                      <option key={tier.id} value={tier.id}>
                        {tier.name} ({(tier.bonus_rate * 100).toFixed(0)}% bonus)
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-slate-500 mt-1">
                    The tier new members will be assigned to
                  </p>
                </div>

                {/* Minimum Order Value */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Minimum Order Value
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-2 text-slate-400">$</span>
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
                      className="w-full pl-8 pr-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-orange-500/50"
                    />
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    Only enroll on orders above this value (0 = any order)
                  </p>
                </div>

                {/* Excluded Tags */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Excluded Customer Tags
                  </label>
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
                    className="w-full px-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-orange-500/50"
                  />
                  <p className="text-xs text-slate-500 mt-1">
                    Customers with these tags won't be auto-enrolled
                  </p>
                </div>
              </div>
            </>
          )}

          <div className="flex justify-end pt-4 border-t border-slate-700/50">
            <button
              onClick={handleAutoEnrollmentSave}
              disabled={saving}
              className="flex items-center gap-2 px-6 py-2 bg-orange-500 hover:bg-orange-600 rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              {saving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              Save Changes
            </button>
          </div>
        </div>
      )}

      {/* Notification Settings */}
      {activeTab === 'notifications' && (
        <div className="glass-card p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">Email Notifications</h2>
              <p className="text-sm text-slate-400">
                Configure which emails are sent to members
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings.notifications.enabled}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    notifications: {
                      ...settings.notifications,
                      enabled: e.target.checked,
                    },
                  })
                }
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-orange-500"></div>
            </label>
          </div>

          {settings.notifications.enabled && (
            <div className="border-t border-slate-700/50 pt-6 space-y-4">
              {/* Email Types */}
              <div className="space-y-3">
                {[
                  { key: 'welcome_email', label: 'Welcome Email', desc: 'Sent when a new member is enrolled' },
                  { key: 'trade_in_updates', label: 'Trade-in Updates', desc: 'Sent when trade-ins are submitted and completed (includes credit details)' },
                  { key: 'tier_change', label: 'Tier Changes', desc: 'Sent when a member\'s tier is upgraded' },
                  { key: 'credit_issued', label: 'Credit Issued', desc: 'For non-trade-in credits (promotions, manual adjustments)' },
                ].map(({ key, label, desc }) => (
                  <div
                    key={key}
                    className="flex items-center justify-between p-3 bg-slate-800/30 rounded-lg"
                  >
                    <div>
                      <p className="font-medium text-white">{label}</p>
                      <p className="text-xs text-slate-400">{desc}</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={settings.notifications[key as keyof typeof settings.notifications] as boolean}
                        onChange={(e) =>
                          setSettings({
                            ...settings,
                            notifications: {
                              ...settings.notifications,
                              [key]: e.target.checked,
                            },
                          })
                        }
                        className="sr-only peer"
                      />
                      <div className="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-orange-500"></div>
                    </label>
                  </div>
                ))}
              </div>

              {/* From Settings */}
              <div className="grid grid-cols-2 gap-4 pt-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    From Name
                  </label>
                  <input
                    type="text"
                    placeholder="Shop name (default)"
                    value={settings.notifications.from_name || ''}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        notifications: {
                          ...settings.notifications,
                          from_name: e.target.value || null,
                        },
                      })
                    }
                    className="w-full px-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-orange-500/50"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    From Email
                  </label>
                  <input
                    type="email"
                    placeholder="noreply@yourshop.com"
                    value={settings.notifications.from_email || ''}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        notifications: {
                          ...settings.notifications,
                          from_email: e.target.value || null,
                        },
                      })
                    }
                    className="w-full px-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-orange-500/50"
                  />
                </div>
              </div>
              <p className="text-xs text-slate-500">
                Email must be verified in SendGrid to use as sender
              </p>
            </div>
          )}

          <div className="flex justify-end pt-4 border-t border-slate-700/50">
            <button
              onClick={handleNotificationsSave}
              disabled={saving}
              className="flex items-center gap-2 px-6 py-2 bg-orange-500 hover:bg-orange-600 rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              {saving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              Save Changes
            </button>
          </div>
        </div>
      )}

      {/* Branding Settings */}
      {activeTab === 'branding' && (
        <div className="glass-card p-6 space-y-6">
          <div>
            <h2 className="text-lg font-semibold text-white">Branding</h2>
            <p className="text-sm text-slate-400">
              Customize the look and feel of your TradeUp experience
            </p>
          </div>

          <div className="border-t border-slate-700/50 pt-6">
            <div className="flex items-center justify-center p-12 bg-slate-800/30 rounded-lg border border-dashed border-slate-600">
              <div className="text-center">
                <Palette className="w-12 h-12 text-slate-500 mx-auto mb-3" />
                <p className="text-slate-400">Branding customization coming soon</p>
                <p className="text-sm text-slate-500 mt-1">
                  Logo upload, colors, and themes
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
