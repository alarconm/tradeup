/**
 * Layout.tsx - Premium Admin Layout with Dark Mode Support
 * Shopify Polaris-inspired design system
 */
import { useState, useEffect } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import {
  LayoutDashboard,
  Users,
  UserPlus,
  CreditCard,
  Settings,
  Zap,
  ArrowRightLeft,
  Layers,
  Sparkles,
  Gift,
  Menu,
  X,
  ChevronRight,
  Moon,
  Sun,
} from 'lucide-react'
import { useTheme } from '../../contexts/ThemeContext'

const membershipNav = [
  { to: '/admin', icon: LayoutDashboard, label: 'Dashboard', end: true },
  { to: '/admin/members', icon: Users, label: 'Members' },
  { to: '/admin/members/new', icon: UserPlus, label: 'New Member' },
  { to: '/admin/card-setup', icon: CreditCard, label: 'Card Setup' },
]

const tradeUpNav = [
  { to: '/admin/tradeins', icon: ArrowRightLeft, label: 'Trade-Ins' },
  { to: '/admin/tradeins/categories', icon: Layers, label: 'Categories' },
]

const promotionsNav = [
  { to: '/admin/promotions', icon: Sparkles, label: 'Promotions' },
  { to: '/admin/bulk-credit', icon: Gift, label: 'Bulk Credit' },
]

const settingsNav = [
  { to: '/admin/settings', icon: Settings, label: 'Settings' },
]

export default function Layout() {
  const { colors, shadows, isDark, toggleTheme } = useTheme()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [isDesktop, setIsDesktop] = useState(typeof window !== 'undefined' ? window.innerWidth >= 1024 : true)

  const closeSidebar = () => setSidebarOpen(false)

  useEffect(() => {
    const handleResize = () => {
      setIsDesktop(window.innerWidth >= 1024)
      if (window.innerWidth >= 1024) {
        setSidebarOpen(false)
      }
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  // Root container
  const rootStyles: React.CSSProperties = {
    minHeight: '100vh',
    display: 'flex',
    position: 'relative',
    backgroundColor: colors.bgPage,
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  }

  // Mobile menu button
  const menuButtonStyles: React.CSSProperties = {
    position: 'fixed',
    top: 16,
    left: 16,
    zIndex: 50,
    width: 40,
    height: 40,
    display: isDesktop ? 'none' : 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 8,
    backgroundColor: colors.bgSurface,
    border: `1px solid ${colors.border}`,
    boxShadow: shadows.md,
    color: colors.text,
    cursor: 'pointer',
  }

  // Mobile overlay
  const overlayStyles: React.CSSProperties = {
    position: 'fixed',
    inset: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    zIndex: 30,
    opacity: sidebarOpen ? 1 : 0,
    pointerEvents: sidebarOpen ? 'auto' : 'none',
    transition: 'opacity 200ms ease',
  }

  // Sidebar
  const sidebarStyles: React.CSSProperties = {
    position: isDesktop ? 'sticky' : 'fixed',
    top: 0,
    left: 0,
    zIndex: 40,
    height: '100vh',
    width: 240,
    backgroundColor: colors.bgSurface,
    borderRight: `1px solid ${colors.border}`,
    transform: isDesktop || sidebarOpen ? 'translateX(0)' : 'translateX(-100%)',
    transition: 'transform 200ms ease',
    flexShrink: 0,
    display: 'flex',
    flexDirection: 'column',
  }

  const sidebarInnerStyles: React.CSSProperties = {
    padding: 16,
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    overflowY: 'auto',
  }

  // Logo
  const logoStyles: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '8px 12px',
    marginBottom: 24,
    textDecoration: 'none',
    borderRadius: 8,
    transition: 'background 150ms ease',
  }

  const logoIconStyles: React.CSSProperties = {
    width: 36,
    height: 36,
    borderRadius: 8,
    background: `linear-gradient(135deg, ${colors.primary}, ${colors.primaryHover})`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    boxShadow: '0 2px 4px rgba(92, 106, 196, 0.3)',
  }

  // Navigation
  const navStyles: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 24,
    flex: 1,
  }

  const navSectionStyles: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  }

  const navLabelStyles: React.CSSProperties = {
    fontSize: 12,
    fontWeight: 600,
    color: colors.textSubdued,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    marginBottom: 8,
    paddingLeft: 12,
  }

  const getNavItemStyles = (isActive: boolean): React.CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '10px 12px',
    borderRadius: 8,
    textDecoration: 'none',
    transition: 'all 150ms ease',
    backgroundColor: isActive ? colors.bgSurfaceSelected : 'transparent',
    color: isActive ? colors.interactive : colors.textSecondary,
    fontWeight: isActive ? 600 : 500,
    fontSize: 14,
  })

  // Footer
  const footerStyles: React.CSSProperties = {
    marginTop: 'auto',
    paddingTop: 16,
    borderTop: `1px solid ${colors.border}`,
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  }

  const footerCardStyles: React.CSSProperties = {
    padding: 12,
    borderRadius: 8,
    backgroundColor: colors.bgSubdued,
  }

  // Theme toggle
  const themeToggleStyles: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '8px 12px',
    borderRadius: 8,
    backgroundColor: 'transparent',
    border: 'none',
    cursor: 'pointer',
    transition: 'background-color 150ms ease',
    width: '100%',
  }

  const toggleSwitchStyles: React.CSSProperties = {
    width: 44,
    height: 24,
    borderRadius: 12,
    backgroundColor: isDark ? colors.primary : colors.border,
    position: 'relative',
    transition: 'background-color 150ms ease',
    cursor: 'pointer',
  }

  const toggleKnobStyles: React.CSSProperties = {
    position: 'absolute',
    top: 2,
    left: isDark ? 22 : 2,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: '#ffffff',
    boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
    transition: 'left 150ms ease',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  }

  // Main content
  const mainStyles: React.CSSProperties = {
    flex: 1,
    minHeight: '100vh',
    overflowX: 'hidden',
  }

  const mainInnerStyles: React.CSSProperties = {
    padding: isDesktop ? 32 : 16,
    paddingTop: isDesktop ? 32 : 72,
    maxWidth: 1400,
    margin: '0 auto',
  }

  return (
    <div style={rootStyles} className="admin-root">
      {/* Mobile Menu Button */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        style={menuButtonStyles}
        aria-label="Toggle menu"
      >
        {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* Mobile Overlay */}
      {!isDesktop && (
        <div
          style={overlayStyles}
          onClick={closeSidebar}
        />
      )}

      {/* Sidebar */}
      <aside style={sidebarStyles}>
        <div style={sidebarInnerStyles}>
          {/* Logo */}
          <Link to="/admin" style={logoStyles} onClick={closeSidebar}>
            <div style={logoIconStyles}>
              <Zap size={20} color="white" strokeWidth={2.5} />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16, color: colors.text, letterSpacing: '-0.3px' }}>
                TradeUp
              </div>
              <div style={{ fontSize: 11, color: colors.textSubdued }}>
                Loyalty Program
              </div>
            </div>
          </Link>

          {/* Navigation */}
          <nav style={navStyles}>
            {/* Membership */}
            <div style={navSectionStyles}>
              <div style={navLabelStyles}>Membership</div>
              {membershipNav.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  onClick={closeSidebar}
                  style={({ isActive }) => getNavItemStyles(isActive)}
                  onMouseEnter={(e) => {
                    const target = e.currentTarget as HTMLAnchorElement
                    if (!target.classList.contains('active')) {
                      target.style.backgroundColor = colors.bgSurfaceHover
                    }
                  }}
                  onMouseLeave={(e) => {
                    const target = e.currentTarget as HTMLAnchorElement
                    if (!target.classList.contains('active')) {
                      target.style.backgroundColor = 'transparent'
                    }
                  }}
                >
                  <item.icon size={18} strokeWidth={2} />
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>

            {/* Trade-Ins */}
            <div style={navSectionStyles}>
              <div style={navLabelStyles}>Trade-Ins</div>
              {tradeUpNav.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={closeSidebar}
                  style={({ isActive }) => getNavItemStyles(isActive)}
                  onMouseEnter={(e) => {
                    const target = e.currentTarget as HTMLAnchorElement
                    if (!target.classList.contains('active')) {
                      target.style.backgroundColor = colors.bgSurfaceHover
                    }
                  }}
                  onMouseLeave={(e) => {
                    const target = e.currentTarget as HTMLAnchorElement
                    if (!target.classList.contains('active')) {
                      target.style.backgroundColor = 'transparent'
                    }
                  }}
                >
                  <item.icon size={18} strokeWidth={2} />
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>

            {/* Store Credit */}
            <div style={navSectionStyles}>
              <div style={navLabelStyles}>Store Credit</div>
              {promotionsNav.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={closeSidebar}
                  style={({ isActive }) => getNavItemStyles(isActive)}
                  onMouseEnter={(e) => {
                    const target = e.currentTarget as HTMLAnchorElement
                    if (!target.classList.contains('active')) {
                      target.style.backgroundColor = colors.bgSurfaceHover
                    }
                  }}
                  onMouseLeave={(e) => {
                    const target = e.currentTarget as HTMLAnchorElement
                    if (!target.classList.contains('active')) {
                      target.style.backgroundColor = 'transparent'
                    }
                  }}
                >
                  <item.icon size={18} strokeWidth={2} />
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>

            {/* Settings */}
            <div style={navSectionStyles}>
              {settingsNav.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={closeSidebar}
                  style={({ isActive }) => getNavItemStyles(isActive)}
                  onMouseEnter={(e) => {
                    const target = e.currentTarget as HTMLAnchorElement
                    if (!target.classList.contains('active')) {
                      target.style.backgroundColor = colors.bgSurfaceHover
                    }
                  }}
                  onMouseLeave={(e) => {
                    const target = e.currentTarget as HTMLAnchorElement
                    if (!target.classList.contains('active')) {
                      target.style.backgroundColor = 'transparent'
                    }
                  }}
                >
                  <item.icon size={18} strokeWidth={2} />
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          </nav>

          {/* Footer */}
          <div style={footerStyles}>
            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              style={themeToggleStyles}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.backgroundColor = colors.bgSurfaceHover
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {isDark ? <Moon size={16} /> : <Sun size={16} />}
                <span style={{ fontSize: 13, color: colors.textSecondary, fontWeight: 500 }}>
                  {isDark ? 'Dark Mode' : 'Light Mode'}
                </span>
              </div>
              <div style={toggleSwitchStyles}>
                <div style={toggleKnobStyles}>
                  {isDark ? <Moon size={12} color={colors.primary} /> : <Sun size={12} color="#f59e0b" />}
                </div>
              </div>
            </button>

            {/* Store Card */}
            <div style={footerCardStyles}>
              <div style={{
                fontSize: 13,
                fontWeight: 600,
                color: colors.text,
                marginBottom: 4,
              }}>
                ORB Sports Cards
              </div>
              <div style={{
                fontSize: 12,
                color: colors.textSubdued,
                display: 'flex',
                alignItems: 'center',
                gap: 4,
              }}>
                orbsportscards.com
                <ChevronRight size={14} />
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main style={mainStyles}>
        <div style={mainInnerStyles}>
          <Outlet />
        </div>
      </main>
    </div>
  )
}
