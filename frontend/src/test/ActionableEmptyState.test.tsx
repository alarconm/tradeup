/**
 * Tests for ActionableEmptyState component
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { AppProvider } from '@shopify/polaris'
import enTranslations from '@shopify/polaris/locales/en.json'
import {
  ActionableEmptyState,
  QuickActionCard,
  GettingStartedSection,
} from '../embedded/components/ActionableEmptyState'
import { PersonAddIcon } from '@shopify/polaris-icons'

// Mock useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

function createWrapper() {
  return ({ children }: { children: React.ReactNode }) => (
    <AppProvider i18n={enTranslations}>
      <BrowserRouter>{children}</BrowserRouter>
    </AppProvider>
  )
}

describe('ActionableEmptyState', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders members empty state correctly', () => {
    render(
      <ActionableEmptyState type="members" shop="test-shop.myshopify.com" />,
      { wrapper: createWrapper() }
    )

    expect(screen.getByText('Start Building Your Loyalty Community')).toBeInTheDocument()
    expect(screen.getByText(/Members earn rewards on purchases/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add Your First Member' })).toBeInTheDocument()
  })

  it('renders trade-ins empty state correctly', () => {
    render(
      <ActionableEmptyState type="trade-ins" />,
      { wrapper: createWrapper() }
    )

    expect(screen.getByText('Ready to Accept Trade-Ins')).toBeInTheDocument()
    expect(screen.getByText(/Process trade-ins to issue store credit/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start a Trade-In' })).toBeInTheDocument()
  })

  it('renders promotions empty state correctly', () => {
    render(
      <ActionableEmptyState type="promotions" />,
      { wrapper: createWrapper() }
    )

    expect(screen.getByText('Boost Engagement with Promotions')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create a Promotion' })).toBeInTheDocument()
  })

  it('renders tiers empty state correctly', () => {
    render(
      <ActionableEmptyState type="tiers" />,
      { wrapper: createWrapper() }
    )

    expect(screen.getByText('Set Up Membership Tiers')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create Your First Tier' })).toBeInTheDocument()
  })

  it('renders products empty state correctly', () => {
    render(
      <ActionableEmptyState type="products" />,
      { wrapper: createWrapper() }
    )

    expect(screen.getByText('Create Membership Products')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Launch Product Wizard' })).toBeInTheDocument()
  })

  it('displays quick tips section', () => {
    render(
      <ActionableEmptyState type="members" />,
      { wrapper: createWrapper() }
    )

    expect(screen.getByText('Quick Tips')).toBeInTheDocument()
    expect(screen.getByText(/Members automatically earn rewards/i)).toBeInTheDocument()
  })

  it('navigates when primary action is clicked', () => {
    render(
      <ActionableEmptyState type="members" />,
      { wrapper: createWrapper() }
    )

    const button = screen.getByRole('button', { name: 'Add Your First Member' })
    fireEvent.click(button)

    expect(mockNavigate).toHaveBeenCalledWith('/app/members?action=add')
  })
})

describe('QuickActionCard', () => {
  const mockOnClick = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders with title and description', () => {
    render(
      <QuickActionCard
        title="Add Members"
        description="Import your first members"
        icon={PersonAddIcon}
        onClick={mockOnClick}
      />,
      { wrapper: createWrapper() }
    )

    expect(screen.getByText('Add Members')).toBeInTheDocument()
    expect(screen.getByText('Import your first members')).toBeInTheDocument()
  })

  it('calls onClick when clicked', () => {
    render(
      <QuickActionCard
        title="Add Members"
        description="Import your first members"
        icon={PersonAddIcon}
        onClick={mockOnClick}
      />,
      { wrapper: createWrapper() }
    )

    const card = screen.getByRole('button')
    fireEvent.click(card)

    expect(mockOnClick).toHaveBeenCalledTimes(1)
  })

  it('calls onClick when Enter key is pressed', () => {
    render(
      <QuickActionCard
        title="Add Members"
        description="Import your first members"
        icon={PersonAddIcon}
        onClick={mockOnClick}
      />,
      { wrapper: createWrapper() }
    )

    const card = screen.getByRole('button')
    fireEvent.keyDown(card, { key: 'Enter' })

    expect(mockOnClick).toHaveBeenCalledTimes(1)
  })

  it('renders with reduced opacity when completed', () => {
    render(
      <QuickActionCard
        title="Add Members"
        description="Import your first members"
        icon={PersonAddIcon}
        onClick={mockOnClick}
        completed={true}
      />,
      { wrapper: createWrapper() }
    )

    const card = screen.getByRole('button')
    expect(card).toHaveStyle({ opacity: '0.6' })
  })
})

describe('GettingStartedSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders getting started heading', () => {
    render(<GettingStartedSection />, { wrapper: createWrapper() })

    expect(screen.getByText('Getting Started')).toBeInTheDocument()
  })

  it('renders all three quick action cards', () => {
    render(<GettingStartedSection />, { wrapper: createWrapper() })

    expect(screen.getByText('Add Members')).toBeInTheDocument()
    expect(screen.getByText('Process Trade-In')).toBeInTheDocument()
    expect(screen.getByText('Create Promotion')).toBeInTheDocument()
  })

  it('navigates when Add Members card is clicked', () => {
    render(<GettingStartedSection />, { wrapper: createWrapper() })

    const card = screen.getByText('Add Members').closest('[role="button"]')
    if (card) {
      fireEvent.click(card)
    }

    expect(mockNavigate).toHaveBeenCalledWith('/app/members?action=add')
  })

  it('navigates when Process Trade-In card is clicked', () => {
    render(<GettingStartedSection />, { wrapper: createWrapper() })

    const card = screen.getByText('Process Trade-In').closest('[role="button"]')
    if (card) {
      fireEvent.click(card)
    }

    expect(mockNavigate).toHaveBeenCalledWith('/app/trade-ins/new')
  })

  it('navigates when Create Promotion card is clicked', () => {
    render(<GettingStartedSection />, { wrapper: createWrapper() })

    const card = screen.getByText('Create Promotion').closest('[role="button"]')
    if (card) {
      fireEvent.click(card)
    }

    expect(mockNavigate).toHaveBeenCalledWith('/app/promotions?action=create')
  })
})
