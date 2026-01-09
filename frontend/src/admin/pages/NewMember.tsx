/**
 * New Member Page - Create new TradeUp membership
 * Features: Shopify customer search, tier selection, payment method
 */
import { useState, useCallback, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search,
  Check,
  User,
  DollarSign,
  CreditCard,
  Banknote,
  ArrowLeft,
  Loader2,
  ShoppingBag,
  AlertCircle,
  Award,
  X,
  UserPlus,
  Store,
} from 'lucide-react'
import {
  searchShopifyCustomers,
  createMember,
  getTiers,
  type ShopifyCustomer,
  type Tier,
} from '../api/adminApi'
import { useTheme } from '../../contexts/ThemeContext'
import { radius, typography, spacing, useResponsive } from '../styles/tokens'
import { debounce } from '../utils/debounce'

type PaymentMethod = 'store_credit' | 'card' | 'cash'

// Extended Shopify customer search result
interface SearchResult {
  customer: ShopifyCustomer | null
  isNew: boolean
}

export default function NewMember() {
  const navigate = useNavigate()
  const { colors, shadows } = useTheme()
  const breakpoint = useResponsive()
  const searchDropdownRef = useRef<HTMLDivElement>(null)

  // State
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [selectedTier, setSelectedTier] = useState<Tier | null>(null)
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('cash')
  const [tiers, setTiers] = useState<Tier[]>([])

  // Shopify customer lookup state
  const [shopifyCustomer, setShopifyCustomer] = useState<ShopifyCustomer | null>(null)
  const [searchResults, setSearchResults] = useState<ShopifyCustomer[]>([])
  const [showSearchDropdown, setShowSearchDropdown] = useState(false)
  const [lookupLoading, setLookupLoading] = useState(false)
  const [customerConfirmed, setCustomerConfirmed] = useState(false)

  // Form state
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  // Fetch tiers on mount
  useEffect(() => {
    getTiers()
      .then((res) => {
        setTiers(res.tiers)
        if (res.tiers.length > 0) {
          setSelectedTier(res.tiers[0])
        }
      })
      .catch(console.error)
  }, [])

  // Click outside to close dropdown
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (searchDropdownRef.current && !searchDropdownRef.current.contains(event.target as Node)) {
        setShowSearchDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Debounced Shopify customer search
  const searchCustomers = useCallback(
    debounce(async (query: string) => {
      if (!query || query.length < 2) {
        setSearchResults([])
        setShowSearchDropdown(false)
        return
      }

      setLookupLoading(true)

      try {
        // Search customers by name, email, phone, or ORB#
        const customers = await searchShopifyCustomers(query, 10)
        setSearchResults(customers)
        setShowSearchDropdown(true)
      } catch (err) {
        console.error('Search failed:', err)
        setSearchResults([])
        setShowSearchDropdown(true) // Show "no results" / "create new" option
      } finally {
        setLookupLoading(false)
      }
    }, 300),
    []
  )

  // Handle email/search change
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setEmail(value)
    setCustomerConfirmed(false)
    setShopifyCustomer(null)
    searchCustomers(value)
  }

  // Select customer from search results
  const selectCustomer = (customer: ShopifyCustomer) => {
    setShopifyCustomer(customer)
    setEmail(customer.email)
    setCustomerConfirmed(true)
    setShowSearchDropdown(false)

    // Auto-fill name and phone
    const fullName = `${customer.firstName || ''} ${customer.lastName || ''}`.trim()
    if (fullName) setName(fullName)
    if (customer.phone) setPhone(customer.phone)
  }

  // Clear selected customer
  const clearCustomer = () => {
    setShopifyCustomer(null)
    setCustomerConfirmed(false)
    setEmail('')
    setName('')
    setPhone('')
  }

  // Mark as new customer (not in Shopify)
  const markAsNewCustomer = () => {
    setShopifyCustomer(null)
    setCustomerConfirmed(true)
    setShowSearchDropdown(false)
  }

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!email || !email.includes('@')) {
      setError('Please enter a valid email address')
      return
    }

    if (!selectedTier) {
      setError('Please select a membership tier')
      return
    }

    setCreating(true)

    try {
      const member = await createMember({
        email,
        name: name || undefined,
        phone: phone || undefined,
        tier_id: selectedTier.id,
        shopify_customer_id: shopifyCustomer?.id || undefined,
        notes: `Payment: ${paymentMethod}`,
      })

      navigate(`/admin/members/${member.id}?created=1`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create member')
    } finally {
      setCreating(false)
    }
  }

  const canPayWithStoreCredit =
    shopifyCustomer && selectedTier && shopifyCustomer.storeCreditBalance >= selectedTier.monthly_price

  // Tier colors helper
  const getTierColors = (tierName: string) => {
    const tierColorMap: Record<string, { bg: string; color: string }> = {
      bronze: { bg: colors.tierBronzeLight, color: colors.tierBronze },
      silver: { bg: colors.tierSilverLight, color: colors.tierSilver },
      gold: { bg: colors.tierGoldLight, color: colors.tierGold },
      platinum: { bg: colors.tierPlatinumLight, color: colors.tierPlatinum },
    }
    return tierColorMap[tierName?.toLowerCase() || 'silver'] || tierColorMap.silver
  }

  // Styles
  const containerStyle: React.CSSProperties = {
    maxWidth: '48rem',
    margin: '0 auto',
  }

  const headerStyle: React.CSSProperties = {
    marginBottom: spacing[6],
  }

  const backButtonStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: spacing[2],
    color: colors.textSecondary,
    background: 'transparent',
    border: 'none',
    cursor: 'pointer',
    marginBottom: spacing[4],
    padding: 0,
    fontSize: typography.base,
    fontWeight: typography.medium,
    transition: 'color 150ms ease',
  }

  const titleStyle: React.CSSProperties = {
    fontSize: typography['2xl'],
    fontWeight: typography.bold,
    color: colors.text,
    margin: 0,
  }

  const subtitleStyle: React.CSSProperties = {
    color: colors.textSecondary,
    marginTop: spacing[1],
    fontSize: typography.base,
  }

  const formStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: spacing[5],
  }

  const cardStyle: React.CSSProperties = {
    padding: spacing[5],
    backgroundColor: colors.bgSurface,
    borderRadius: radius.lg,
    border: `1px solid ${colors.border}`,
    boxShadow: shadows.card,
  }

  const stepHeaderStyle: React.CSSProperties = {
    fontSize: typography.md,
    fontWeight: typography.semibold,
    color: colors.text,
    marginBottom: spacing[4],
    display: 'flex',
    alignItems: 'center',
    gap: spacing[3],
  }

  const stepBadgeStyle: React.CSSProperties = {
    width: 28,
    height: 28,
    borderRadius: '50%',
    background: colors.primarySubtle,
    color: colors.primary,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: typography.sm,
    fontWeight: typography.semibold,
  }

  const inputWrapperStyle: React.CSSProperties = {
    position: 'relative',
  }

  const inputIconStyle: React.CSSProperties = {
    position: 'absolute',
    left: 12,
    top: '50%',
    transform: 'translateY(-50%)',
    color: colors.textSubdued,
    pointerEvents: 'none',
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '10px 12px 10px 40px',
    backgroundColor: colors.bgSurface,
    border: `1px solid ${colors.border}`,
    borderRadius: radius.md,
    color: colors.text,
    fontSize: typography.base,
    outline: 'none',
    transition: 'border-color 150ms ease, box-shadow 150ms ease',
  }

  const smallInputStyle: React.CSSProperties = {
    width: '100%',
    padding: '10px 12px',
    backgroundColor: colors.bgSurface,
    border: `1px solid ${colors.border}`,
    borderRadius: radius.md,
    color: colors.text,
    fontSize: typography.base,
    outline: 'none',
    transition: 'border-color 150ms ease, box-shadow 150ms ease',
  }

  const gridStyle: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: breakpoint === 'mobile' ? '1fr' : '1fr 1fr',
    gap: spacing[4],
  }

  const tierGridStyle: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: breakpoint === 'mobile' ? '1fr' : 'repeat(3, 1fr)',
    gap: spacing[3],
  }

  const paymentGridStyle: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: breakpoint === 'mobile' ? '1fr' : 'repeat(3, 1fr)',
    gap: spacing[3],
  }

  const labelStyle: React.CSSProperties = {
    display: 'block',
    fontSize: typography.sm,
    fontWeight: typography.medium,
    color: colors.text,
    marginBottom: spacing[2],
  }

  const buttonRowStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: breakpoint === 'mobile' ? 'column' : 'row',
    gap: spacing[3],
    marginTop: spacing[2],
  }

  const primaryButtonStyle: React.CSSProperties = {
    flex: 1,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing[2],
    padding: '12px 20px',
    backgroundColor: colors.primary,
    color: colors.textOnPrimary,
    border: 'none',
    borderRadius: radius.md,
    fontSize: typography.base,
    fontWeight: typography.medium,
    cursor: 'pointer',
    transition: 'background-color 150ms ease',
  }

  const secondaryButtonStyle: React.CSSProperties = {
    flex: 1,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing[2],
    padding: '12px 20px',
    backgroundColor: colors.bgSurface,
    color: colors.text,
    border: `1px solid ${colors.border}`,
    borderRadius: radius.md,
    fontSize: typography.base,
    fontWeight: typography.medium,
    cursor: 'pointer',
    transition: 'background-color 150ms ease, border-color 150ms ease',
  }

  const dropdownStyle: React.CSSProperties = {
    position: 'absolute',
    top: '100%',
    left: 0,
    right: 0,
    marginTop: spacing[1],
    backgroundColor: colors.bgSurface,
    border: `1px solid ${colors.border}`,
    borderRadius: radius.md,
    boxShadow: shadows.lg,
    zIndex: 50,
    maxHeight: 300,
    overflowY: 'auto',
  }

  const dropdownItemStyle: React.CSSProperties = {
    padding: spacing[3],
    display: 'flex',
    alignItems: 'center',
    gap: spacing[3],
    cursor: 'pointer',
    borderBottom: `1px solid ${colors.borderSubdued}`,
    transition: 'background-color 150ms ease',
  }

  const selectedCustomerCardStyle: React.CSSProperties = {
    marginTop: spacing[4],
    padding: spacing[4],
    borderRadius: radius.md,
    border: `1px solid rgba(0, 128, 96, 0.3)`,
    backgroundColor: colors.successLight,
    display: 'flex',
    alignItems: 'flex-start',
    gap: spacing[3],
  }

  return (
    <div style={containerStyle}>
      {/* Header */}
      <div style={headerStyle}>
        <button
          onClick={() => navigate('/admin/members')}
          style={backButtonStyle}
          onMouseEnter={(e) => (e.currentTarget.style.color = colors.primary)}
          onMouseLeave={(e) => (e.currentTarget.style.color = colors.textSecondary)}
        >
          <ArrowLeft size={18} />
          Back to Members
        </button>
        <h1 style={titleStyle}>New Member</h1>
        <p style={subtitleStyle}>Register a new TradeUp membership</p>
      </div>

      <form onSubmit={handleSubmit} style={formStyle}>
        {/* Step 1: Customer Search */}
        <div style={cardStyle}>
          <h2 style={stepHeaderStyle}>
            <span style={stepBadgeStyle}>1</span>
            Find Customer
          </h2>

          {/* Search input with dropdown */}
          <div style={inputWrapperStyle} ref={searchDropdownRef}>
            <span style={inputIconStyle}>
              {lookupLoading ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Search size={18} />
              )}
            </span>
            <input
              type="text"
              placeholder="Search by email, name, or phone..."
              value={email}
              onChange={handleSearchChange}
              disabled={customerConfirmed}
              style={{
                ...inputStyle,
                paddingRight: customerConfirmed ? 40 : 12,
                backgroundColor: customerConfirmed ? colors.bgSubdued : colors.bgSurface,
              }}
              autoFocus
              onFocus={(e) => {
                if (!customerConfirmed) {
                  e.target.style.borderColor = colors.primary
                  e.target.style.boxShadow = shadows.focus
                  if (searchResults.length > 0 || email.length >= 2) {
                    setShowSearchDropdown(true)
                  }
                }
              }}
              onBlur={(e) => {
                e.target.style.borderColor = colors.border
                e.target.style.boxShadow = 'none'
              }}
            />
            {customerConfirmed && (
              <button
                type="button"
                onClick={clearCustomer}
                style={{
                  position: 'absolute',
                  right: 12,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  color: colors.textSubdued,
                  padding: 0,
                  display: 'flex',
                }}
              >
                <X size={18} />
              </button>
            )}

            {/* Search Dropdown */}
            {showSearchDropdown && !customerConfirmed && (
              <div style={dropdownStyle}>
                {lookupLoading ? (
                  <div style={{ padding: spacing[4], textAlign: 'center', color: colors.textSecondary }}>
                    <Loader2 size={20} className="animate-spin" style={{ marginBottom: spacing[2] }} />
                    <p style={{ margin: 0, fontSize: typography.sm }}>Searching Shopify...</p>
                  </div>
                ) : searchResults.length > 0 ? (
                  <>
                    {searchResults.map((customer) => (
                      <div
                        key={customer.id}
                        onClick={() => selectCustomer(customer)}
                        style={dropdownItemStyle}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = colors.bgSurfaceHover
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = 'transparent'
                        }}
                      >
                        <div
                          style={{
                            width: 36,
                            height: 36,
                            borderRadius: '50%',
                            background: colors.primarySubtle,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                          }}
                        >
                          <Store size={16} style={{ color: colors.primary }} />
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <p style={{ fontWeight: typography.medium, color: colors.text, margin: 0, fontSize: typography.base }}>
                            {customer.firstName} {customer.lastName}
                          </p>
                          <p style={{ color: colors.textSecondary, fontSize: typography.sm, margin: 0 }}>
                            {customer.email}
                          </p>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: spacing[2], color: colors.success, fontSize: typography.xs }}>
                          <DollarSign size={14} />
                          <span>${(customer.storeCreditBalance || 0).toFixed(2)}</span>
                        </div>
                      </div>
                    ))}
                    <div
                      onClick={markAsNewCustomer}
                      style={{
                        ...dropdownItemStyle,
                        borderBottom: 'none',
                        color: colors.textSecondary,
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = colors.bgSurfaceHover
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = 'transparent'
                      }}
                    >
                      <div
                        style={{
                          width: 36,
                          height: 36,
                          borderRadius: '50%',
                          background: colors.warningLight,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                        }}
                      >
                        <UserPlus size={16} style={{ color: colors.warning }} />
                      </div>
                      <div>
                        <p style={{ fontWeight: typography.medium, color: colors.text, margin: 0 }}>
                          Create as New Customer
                        </p>
                        <p style={{ color: colors.textSecondary, fontSize: typography.sm, margin: 0 }}>
                          Use "{email}" for a new member
                        </p>
                      </div>
                    </div>
                  </>
                ) : email.length >= 2 ? (
                  <div
                    onClick={markAsNewCustomer}
                    style={{
                      ...dropdownItemStyle,
                      borderBottom: 'none',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = colors.bgSurfaceHover
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'transparent'
                    }}
                  >
                    <div
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: '50%',
                        background: colors.warningLight,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                      }}
                    >
                      <UserPlus size={16} style={{ color: colors.warning }} />
                    </div>
                    <div>
                      <p style={{ fontWeight: typography.medium, color: colors.text, margin: 0 }}>
                        No Shopify customer found
                      </p>
                      <p style={{ color: colors.textSecondary, fontSize: typography.sm, margin: 0 }}>
                        Click to create as new member with "{email}"
                      </p>
                    </div>
                  </div>
                ) : null}
              </div>
            )}
          </div>

          {/* Selected Customer Card */}
          {customerConfirmed && shopifyCustomer && (
            <div style={selectedCustomerCardStyle}>
              <div
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: '50%',
                  background: 'rgba(0, 128, 96, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  color: colors.success,
                }}
              >
                <Check size={20} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontWeight: typography.semibold, color: colors.success, margin: 0, fontSize: typography.base }}>
                  Shopify Customer Selected
                </p>
                <p style={{ color: colors.text, marginTop: 2, fontSize: typography.base }}>
                  {shopifyCustomer.firstName} {shopifyCustomer.lastName}
                </p>
                <div
                  style={{
                    marginTop: spacing[3],
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: spacing[4],
                    fontSize: typography.sm,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: colors.textSecondary }}>
                    <ShoppingBag size={16} />
                    <span>{shopifyCustomer.ordersCount} orders</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: colors.textSecondary }}>
                    <DollarSign size={16} />
                    <span>${(shopifyCustomer.totalSpent || 0).toFixed(2)} spent</span>
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      color: colors.success,
                      fontWeight: typography.semibold,
                    }}
                  >
                    <CreditCard size={16} />
                    <span>${(shopifyCustomer.storeCreditBalance || 0).toFixed(2)} credit</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* New Customer Indicator */}
          {customerConfirmed && !shopifyCustomer && (
            <div
              style={{
                marginTop: spacing[4],
                padding: spacing[4],
                borderRadius: radius.md,
                border: `1px solid rgba(185, 137, 0, 0.3)`,
                backgroundColor: colors.warningLight,
                display: 'flex',
                alignItems: 'flex-start',
                gap: spacing[3],
              }}
            >
              <div
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: '50%',
                  background: 'rgba(185, 137, 0, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  color: colors.warning,
                }}
              >
                <User size={20} />
              </div>
              <div>
                <p style={{ fontWeight: typography.semibold, color: colors.warning, margin: 0, fontSize: typography.base }}>
                  New Customer
                </p>
                <p style={{ color: colors.textSecondary, fontSize: typography.sm, marginTop: 4 }}>
                  A Shopify customer will be created when they make their first purchase.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Step 2: Customer Details */}
        <div style={cardStyle}>
          <h2 style={stepHeaderStyle}>
            <span style={stepBadgeStyle}>2</span>
            Customer Details
          </h2>

          <div style={gridStyle}>
            <div>
              <label style={labelStyle}>Name</label>
              <input
                type="text"
                placeholder="Full name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                style={smallInputStyle}
                onFocus={(e) => {
                  e.target.style.borderColor = colors.primary
                  e.target.style.boxShadow = shadows.focus
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = colors.border
                  e.target.style.boxShadow = 'none'
                }}
              />
            </div>
            <div>
              <label style={labelStyle}>Phone</label>
              <input
                type="tel"
                placeholder="Phone number"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                style={smallInputStyle}
                onFocus={(e) => {
                  e.target.style.borderColor = colors.primary
                  e.target.style.boxShadow = shadows.focus
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = colors.border
                  e.target.style.boxShadow = 'none'
                }}
              />
            </div>
          </div>
        </div>

        {/* Step 3: Select Tier */}
        <div style={cardStyle}>
          <h2 style={stepHeaderStyle}>
            <span style={stepBadgeStyle}>3</span>
            Select Tier
          </h2>

          <div style={tierGridStyle}>
            {tiers.map((tier) => {
              const tierColors = getTierColors(tier.name)
              const isSelected = selectedTier?.id === tier.id

              return (
                <button
                  key={tier.id}
                  type="button"
                  onClick={() => setSelectedTier(tier)}
                  style={{
                    position: 'relative',
                    padding: spacing[4],
                    borderRadius: radius.lg,
                    background: isSelected ? colors.primarySubtle : colors.bgSurface,
                    border: isSelected ? `2px solid ${colors.primary}` : `1px solid ${colors.border}`,
                    boxShadow: isSelected ? shadows.focus : shadows.card,
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'all 150ms ease',
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.borderColor = colors.primary
                      e.currentTarget.style.transform = 'translateY(-1px)'
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.borderColor = colors.border
                      e.currentTarget.style.transform = 'translateY(0)'
                    }
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing[3] }}>
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                        padding: '4px 10px',
                        backgroundColor: tierColors.bg,
                        color: tierColors.color,
                        borderRadius: radius.full,
                        fontSize: typography.xs,
                        fontWeight: typography.semibold,
                        textTransform: 'capitalize',
                      }}
                    >
                      <Award size={12} />
                      {tier.name}
                    </span>
                    {isSelected && <Check size={18} style={{ color: colors.primary }} />}
                  </div>
                  <p style={{ fontSize: typography.xl, fontWeight: typography.bold, color: colors.text, marginBottom: spacing[2] }}>
                    ${tier.monthly_price}
                    <span style={{ fontSize: typography.sm, color: colors.textSecondary, fontWeight: typography.normal }}>/mo</span>
                  </p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: typography.sm, color: colors.textSecondary }}>
                    <Check size={14} style={{ color: colors.success }} />
                    <span>{Math.round(tier.bonus_rate * 100)}% Cashback</span>
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        {/* Step 4: Payment */}
        <div style={cardStyle}>
          <h2 style={stepHeaderStyle}>
            <span style={stepBadgeStyle}>4</span>
            Payment Method
          </h2>

          <div style={paymentGridStyle}>
            {/* Store Credit */}
            <button
              type="button"
              onClick={() => canPayWithStoreCredit && setPaymentMethod('store_credit')}
              disabled={!canPayWithStoreCredit}
              style={{
                padding: spacing[4],
                borderRadius: radius.md,
                border: paymentMethod === 'store_credit' ? `2px solid ${colors.primary}` : `1px solid ${colors.border}`,
                background: paymentMethod === 'store_credit' ? colors.primarySubtle : colors.bgSurface,
                textAlign: 'left',
                cursor: canPayWithStoreCredit ? 'pointer' : 'not-allowed',
                opacity: canPayWithStoreCredit ? 1 : 0.5,
                transition: 'all 150ms ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: spacing[3], marginBottom: 6 }}>
                <DollarSign size={18} style={{ color: paymentMethod === 'store_credit' ? colors.primary : colors.textSecondary }} />
                <span style={{ fontWeight: typography.semibold, color: colors.text, fontSize: typography.base }}>Store Credit</span>
              </div>
              <p style={{ fontSize: typography.xs, color: colors.textSecondary, margin: 0 }}>
                {shopifyCustomer ? `$${(shopifyCustomer.storeCreditBalance || 0).toFixed(2)} available` : 'Not available'}
              </p>
            </button>

            {/* Card */}
            <button
              type="button"
              onClick={() => setPaymentMethod('card')}
              style={{
                padding: spacing[4],
                borderRadius: radius.md,
                border: paymentMethod === 'card' ? `2px solid ${colors.primary}` : `1px solid ${colors.border}`,
                background: paymentMethod === 'card' ? colors.primarySubtle : colors.bgSurface,
                textAlign: 'left',
                cursor: 'pointer',
                transition: 'all 150ms ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: spacing[3], marginBottom: 6 }}>
                <CreditCard size={18} style={{ color: paymentMethod === 'card' ? colors.primary : colors.textSecondary }} />
                <span style={{ fontWeight: typography.semibold, color: colors.text, fontSize: typography.base }}>Card</span>
              </div>
              <p style={{ fontSize: typography.xs, color: colors.textSecondary, margin: 0 }}>Process later</p>
            </button>

            {/* Cash */}
            <button
              type="button"
              onClick={() => setPaymentMethod('cash')}
              style={{
                padding: spacing[4],
                borderRadius: radius.md,
                border: paymentMethod === 'cash' ? `2px solid ${colors.primary}` : `1px solid ${colors.border}`,
                background: paymentMethod === 'cash' ? colors.primarySubtle : colors.bgSurface,
                textAlign: 'left',
                cursor: 'pointer',
                transition: 'all 150ms ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: spacing[3], marginBottom: 6 }}>
                <Banknote size={18} style={{ color: paymentMethod === 'cash' ? colors.primary : colors.textSecondary }} />
                <span style={{ fontWeight: typography.semibold, color: colors.text, fontSize: typography.base }}>Cash</span>
              </div>
              <p style={{ fontSize: typography.xs, color: colors.textSecondary, margin: 0 }}>Mark as paid</p>
            </button>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: spacing[3],
              padding: spacing[4],
              borderRadius: radius.md,
              background: colors.criticalLight,
              border: `1px solid rgba(215, 44, 13, 0.3)`,
              color: colors.critical,
              fontSize: typography.base,
            }}
          >
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        {/* Submit */}
        <div style={buttonRowStyle}>
          <button
            type="button"
            onClick={() => navigate('/admin/members')}
            style={secondaryButtonStyle}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = colors.bgSurfaceHover
              e.currentTarget.style.borderColor = colors.borderHover
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = colors.bgSurface
              e.currentTarget.style.borderColor = colors.border
            }}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={creating || !email || !selectedTier}
            style={{
              ...primaryButtonStyle,
              opacity: creating || !email || !selectedTier ? 0.5 : 1,
              cursor: creating || !email || !selectedTier ? 'not-allowed' : 'pointer',
            }}
            onMouseEnter={(e) => {
              if (!creating && email && selectedTier) {
                e.currentTarget.style.backgroundColor = colors.primaryHover
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = colors.primary
            }}
          >
            {creating ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Check size={18} />
                Create Membership
                {selectedTier && ` · $${selectedTier.monthly_price}`}
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  )
}
