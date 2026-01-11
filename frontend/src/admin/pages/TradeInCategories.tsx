/**
 * TradeInCategories.tsx - Manage trade-in categories
 * Allows adding, editing, and removing categories for trade-in batches
 */
import { useState, useEffect } from 'react'
import { Plus, Edit2, Trash2, Loader2, AlertCircle, X, Check, Package } from 'lucide-react'
import { useTheme } from '../../contexts/ThemeContext'
import { radius, typography, spacing } from '../styles/tokens'
import {
  getTradeInCategories,
  createTradeInCategory,
  updateTradeInCategory,
  deleteTradeInCategory,
  type TradeInCategory
} from '../api/adminApi'

// Common emoji icons for trade-in categories
const EMOJI_OPTIONS = [
  { emoji: '🏈', label: 'Sports' },
  { emoji: '⚡', label: 'Pokemon' },
  { emoji: '🔮', label: 'Magic' },
  { emoji: '🌀', label: 'Riftbound' },
  { emoji: '🎴', label: 'TCG' },
  { emoji: '📦', label: 'Other' },
  { emoji: '⭐', label: 'Premium' },
  { emoji: '💎', label: 'Graded' },
  { emoji: '🃏', label: 'Cards' },
  { emoji: '🎮', label: 'Gaming' },
  { emoji: '🎯', label: 'Target' },
  { emoji: '🏆', label: 'Trophy' },
  { emoji: '🎁', label: 'Special' },
  { emoji: '🔥', label: 'Hot' },
  { emoji: '❄️', label: 'Cold' },
  { emoji: '🌟', label: 'Star' },
]

export default function TradeInCategories() {
  const { colors, shadows } = useTheme()
  const [categories, setCategories] = useState<TradeInCategory[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editingCategory, setEditingCategory] = useState<TradeInCategory | null>(null)
  const [saving, setSaving] = useState(false)

  const [form, setForm] = useState({
    name: '',
    icon: '📦',
  })

  useEffect(() => {
    loadCategories()
  }, [])

  const loadCategories = async () => {
    try {
      setLoading(true)
      const data = await getTradeInCategories()
      setCategories(data.categories)
    } catch {
      setError('Failed to load categories')
    } finally {
      setLoading(false)
    }
  }

  const openNewModal = () => {
    setForm({ name: '', icon: '📦' })
    setEditingCategory(null)
    setShowModal(true)
  }

  const openEditModal = (category: TradeInCategory) => {
    setForm({
      name: category.name,
      icon: category.icon,
    })
    setEditingCategory(category)
    setShowModal(true)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim()) {
      setError('Category name is required')
      return
    }

    try {
      setSaving(true)
      setError('')

      if (editingCategory) {
        await updateTradeInCategory(editingCategory.id, {
          name: form.name.trim(),
          icon: form.icon,
        })
      } else {
        await createTradeInCategory({
          name: form.name.trim(),
          icon: form.icon,
        })
      }

      setShowModal(false)
      loadCategories()
    } catch {
      setError('Failed to save category')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (category: TradeInCategory) => {
    if (!confirm(`Delete category "${category.name}"? Trade-ins using this category will be set to "Other".`)) {
      return
    }

    try {
      await deleteTradeInCategory(category.id)
      loadCategories()
    } catch {
      setError('Failed to delete category')
    }
  }

  // Styles
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

  const labelStyle: React.CSSProperties = {
    display: 'block',
    fontSize: typography.sm,
    fontWeight: typography.medium,
    color: colors.textSecondary,
    marginBottom: 4,
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
    fontSize: typography.base,
    fontWeight: typography.medium,
    cursor: 'pointer',
  }

  const secondaryButtonStyle: React.CSSProperties = {
    ...buttonStyle,
    backgroundColor: colors.bgSurface,
    color: colors.text,
    border: `1px solid ${colors.border}`,
  }

  const categoryCardStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: spacing[4],
    padding: spacing[4],
    backgroundColor: colors.bgSurface,
    borderRadius: radius.lg,
    border: `1px solid ${colors.border}`,
    boxShadow: shadows.card,
    transition: 'border-color 150ms ease, box-shadow 150ms ease',
  }

  if (loading) {
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
            Trade-In Categories
          </h1>
          <p style={{ color: colors.textSecondary, marginTop: 4, fontSize: typography.base }}>
            Organize trade-ins by product type
          </p>
        </div>
        <button onClick={openNewModal} style={buttonStyle}>
          <Plus size={18} />
          Add Category
        </button>
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
          <button
            onClick={() => setError('')}
            style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: colors.critical }}
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* Categories Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: spacing[4] }}>
        {categories.map(category => (
          <div key={category.id} style={categoryCardStyle}>
            <div style={{
              width: 56,
              height: 56,
              backgroundColor: colors.primaryLight,
              borderRadius: radius.lg,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '28px',
            }}>
              {category.icon}
            </div>

            <div style={{ flex: 1 }}>
              <h3 style={{ fontSize: typography.lg, fontWeight: typography.semibold, color: colors.text, margin: 0 }}>
                {category.name}
              </h3>
              <p style={{ color: colors.textSecondary, fontSize: typography.sm, margin: 0 }}>
                ID: {category.id}
              </p>
            </div>

            <div style={{ display: 'flex', gap: spacing[2] }}>
              <button
                onClick={() => openEditModal(category)}
                style={{
                  padding: spacing[2],
                  backgroundColor: colors.bgSubdued,
                  border: 'none',
                  borderRadius: radius.md,
                  cursor: 'pointer',
                  color: colors.textSecondary,
                }}
              >
                <Edit2 size={18} />
              </button>
              <button
                onClick={() => handleDelete(category)}
                style={{
                  padding: spacing[2],
                  backgroundColor: colors.criticalLight,
                  border: 'none',
                  borderRadius: radius.md,
                  cursor: 'pointer',
                  color: colors.critical,
                }}
              >
                <Trash2 size={18} />
              </button>
            </div>
          </div>
        ))}

        {categories.length === 0 && (
          <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: spacing[12], color: colors.textSecondary }}>
            <Package size={48} style={{ opacity: 0.5, marginBottom: spacing[4] }} />
            <p style={{ margin: 0 }}>No categories created yet</p>
            <button
              onClick={openNewModal}
              style={{ marginTop: spacing[4], color: colors.primary, background: 'none', border: 'none', cursor: 'pointer' }}
            >
              Create your first category
            </button>
          </div>
        )}
      </div>

      {/* Modal */}
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
            maxWidth: 480,
            width: '100%',
            boxShadow: shadows.xl,
          }}>
            {/* Modal Header */}
            <div style={{
              padding: spacing[6],
              borderBottom: `1px solid ${colors.border}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <h2 style={{ fontSize: typography.xl, fontWeight: typography.semibold, color: colors.text, margin: 0 }}>
                {editingCategory ? 'Edit Category' : 'New Category'}
              </h2>
              <button
                onClick={() => setShowModal(false)}
                style={{ color: colors.textSecondary, background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}
              >
                <X size={24} />
              </button>
            </div>

            <form onSubmit={handleSubmit} style={{ padding: spacing[6], display: 'flex', flexDirection: 'column', gap: spacing[5] }}>
              {/* Name */}
              <div>
                <label style={labelStyle}>Category Name *</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  style={inputStyle}
                  placeholder="e.g., Pokemon, Sports Cards"
                  required
                  autoFocus
                />
              </div>

              {/* Icon Picker */}
              <div>
                <label style={labelStyle}>Icon</label>
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(8, 1fr)',
                  gap: spacing[2],
                  padding: spacing[3],
                  backgroundColor: colors.bgSubdued,
                  borderRadius: radius.lg,
                  border: `1px solid ${colors.border}`,
                }}>
                  {EMOJI_OPTIONS.map(({ emoji, label }) => (
                    <button
                      key={emoji}
                      type="button"
                      onClick={() => setForm(f => ({ ...f, icon: emoji }))}
                      title={label}
                      style={{
                        padding: spacing[2],
                        fontSize: '24px',
                        backgroundColor: form.icon === emoji ? colors.primaryLight : 'transparent',
                        border: form.icon === emoji ? `2px solid ${colors.primary}` : '2px solid transparent',
                        borderRadius: radius.md,
                        cursor: 'pointer',
                        transition: 'all 150ms ease',
                      }}
                    >
                      {emoji}
                    </button>
                  ))}
                </div>
                <p style={{ fontSize: typography.xs, color: colors.textSecondary, marginTop: spacing[2] }}>
                  Or type a custom emoji in the field below
                </p>
                <input
                  type="text"
                  value={form.icon}
                  onChange={e => setForm(f => ({ ...f, icon: e.target.value }))}
                  style={{ ...inputStyle, width: 80, textAlign: 'center', fontSize: '20px', marginTop: spacing[2] }}
                  maxLength={2}
                />
              </div>

              {/* Preview */}
              <div style={{ padding: spacing[4], backgroundColor: colors.bgSubdued, borderRadius: radius.lg }}>
                <label style={{ ...labelStyle, marginBottom: spacing[3] }}>Preview</label>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: spacing[3],
                  padding: spacing[3],
                  backgroundColor: colors.bgSurface,
                  borderRadius: radius.md,
                  border: `1px solid ${colors.border}`,
                }}>
                  <span style={{ fontSize: '32px' }}>{form.icon}</span>
                  <span style={{ fontWeight: typography.medium, color: colors.text }}>
                    {form.name || 'Category Name'}
                  </span>
                </div>
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', gap: spacing[3], justifyContent: 'flex-end', paddingTop: spacing[4], borderTop: `1px solid ${colors.border}` }}>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  style={{ ...secondaryButtonStyle, backgroundColor: 'transparent', border: 'none' }}
                >
                  Cancel
                </button>
                <button type="submit" disabled={saving} style={buttonStyle}>
                  {saving ? (
                    <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                  ) : (
                    <Check size={16} />
                  )}
                  {editingCategory ? 'Save Changes' : 'Create Category'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
