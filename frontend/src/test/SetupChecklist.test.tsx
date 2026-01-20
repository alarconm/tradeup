/**
 * Tests for SetupChecklist component
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { AppProvider } from '@shopify/polaris'
import enTranslations from '@shopify/polaris/locales/en.json'

// Mock the hooks module
vi.mock('../hooks/useShopifyBridge', () => ({
  getApiUrl: () => 'http://localhost:5000/api',
  authFetch: vi.fn()
}))

// Import after mocking
import { authFetch } from '../hooks/useShopifyBridge'
import { SetupChecklist, SetupChecklistCompact } from '../embedded/components/SetupChecklist'

const mockAuthFetch = vi.mocked(authFetch)

const mockSetupStatus = {
  checklist: [
    {
      id: 'configure_tiers',
      title: 'Configure membership tiers',
      description: 'Set up your tier structure and benefits',
      completed: true,
      fully_complete: true,
      action_url: '/app/tiers',
      action_label: 'Configure',
      priority: 1,
      category: 'setup'
    },
    {
      id: 'setup_store_credit',
      title: 'Enable store credit',
      description: 'Connect to Shopify store credit system',
      completed: false,
      action_url: '/app/settings',
      action_label: 'Set up',
      priority: 2,
      category: 'setup'
    },
    {
      id: 'first_member',
      title: 'Enroll first member',
      description: 'Get your first loyalty member',
      completed: false,
      action_url: '/app/members',
      action_label: 'Add member',
      priority: 1,
      category: 'milestone'
    }
  ],
  completion: {
    setup_percentage: 50,
    setup_completed: 1,
    setup_total: 2,
    all_complete: false
  },
  next_action: {
    id: 'setup_store_credit',
    title: 'Enable store credit',
    description: 'Connect to Shopify store credit system',
    completed: false,
    action_url: '/app/settings',
    action_label: 'Set up',
    priority: 2,
    category: 'setup'
  },
  milestones: {},
  uncelebrated_milestones: []
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })
  return ({ children }: { children: React.ReactNode }) => (
    <AppProvider i18n={enTranslations}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>{children}</BrowserRouter>
      </QueryClientProvider>
    </AppProvider>
  )
}

describe('SetupChecklist', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    mockAuthFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockSetupStatus)
    } as Response)
  })

  it('shows loading state initially', async () => {
    mockAuthFetch.mockImplementation(() => new Promise(() => {}))

    render(<SetupChecklist shop="test-shop.myshopify.com" />, {
      wrapper: createWrapper()
    })

    // Should show skeleton loading state
    expect(screen.getByText('Setup Progress')).toBeInTheDocument()
  })

  it('displays progress percentage when data loads', async () => {
    render(<SetupChecklist shop="test-shop.myshopify.com" />, {
      wrapper: createWrapper()
    })

    await waitFor(() => {
      // Multiple elements show 50% (heading and progress bar), check at least one exists
      const percentElements = screen.getAllByText('50%')
      expect(percentElements.length).toBeGreaterThan(0)
    })
  })

  it('shows completion count', async () => {
    render(<SetupChecklist shop="test-shop.myshopify.com" />, {
      wrapper: createWrapper()
    })

    await waitFor(() => {
      expect(screen.getByText(/1 of 2 steps completed/i)).toBeInTheDocument()
    })
  })

  it('displays checklist items with correct status', async () => {
    render(<SetupChecklist shop="test-shop.myshopify.com" />, {
      wrapper: createWrapper()
    })

    await waitFor(() => {
      // Completed item
      expect(screen.getByText('Configure membership tiers')).toBeInTheDocument()
      // Incomplete item with action button
      expect(screen.getByText('Enable store credit')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Set up' })).toBeInTheDocument()
    })
  })

  it('shows milestones section in non-compact mode', async () => {
    render(<SetupChecklist shop="test-shop.myshopify.com" compact={false} />, {
      wrapper: createWrapper()
    })

    await waitFor(() => {
      expect(screen.getByText('Milestones')).toBeInTheDocument()
      expect(screen.getByText('Enroll first member')).toBeInTheDocument()
    })
  })

  it('shows "Setup Complete!" when all steps are done', async () => {
    const completeStatus = {
      ...mockSetupStatus,
      completion: {
        setup_percentage: 100,
        setup_completed: 2,
        setup_total: 2,
        all_complete: true
      },
      next_action: null,
      checklist: mockSetupStatus.checklist.map(item => ({ ...item, completed: true }))
    }

    mockAuthFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(completeStatus)
    } as Response)

    render(<SetupChecklist shop="test-shop.myshopify.com" />, {
      wrapper: createWrapper()
    })

    await waitFor(() => {
      expect(screen.getByText('Setup Complete!')).toBeInTheDocument()
    })
  })

  it('does not render checklist content when complete and compact', async () => {
    const completeStatus = {
      ...mockSetupStatus,
      completion: {
        setup_percentage: 100,
        setup_completed: 2,
        setup_total: 2,
        all_complete: true
      },
      next_action: null,
      checklist: mockSetupStatus.checklist.map(item => ({ ...item, completed: true }))
    }

    mockAuthFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(completeStatus)
    } as Response)

    render(<SetupChecklist shop="test-shop.myshopify.com" compact />, {
      wrapper: createWrapper()
    })

    await waitFor(() => {
      // Component returns null when all_complete and compact, so no checklist card visible
      expect(screen.queryByText('Setup Progress')).not.toBeInTheDocument()
      expect(screen.queryByText('Setup Complete!')).not.toBeInTheDocument()
    })
  })

  it('shows milestone celebration banner', async () => {
    const statusWithMilestone = {
      ...mockSetupStatus,
      uncelebrated_milestones: [
        {
          id: 'first_member',
          achieved: true,
          celebrated: false,
          title: 'First Member Enrolled!',
          message: 'Congratulations on your first loyalty member!',
          icon: 'trophy'
        }
      ]
    }

    mockAuthFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(statusWithMilestone)
    } as Response)

    render(<SetupChecklist shop="test-shop.myshopify.com" />, {
      wrapper: createWrapper()
    })

    await waitFor(() => {
      expect(screen.getByText('First Member Enrolled!')).toBeInTheDocument()
      expect(screen.getByText(/Congratulations on your first loyalty member/i)).toBeInTheDocument()
    })
  })

  it('calls onMilestoneShow callback when milestone appears', async () => {
    const onMilestoneShow = vi.fn()
    const statusWithMilestone = {
      ...mockSetupStatus,
      uncelebrated_milestones: [
        {
          id: 'first_member',
          achieved: true,
          celebrated: false,
          title: 'First Member!',
          message: 'Congrats!',
          icon: 'trophy'
        }
      ]
    }

    mockAuthFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(statusWithMilestone)
    } as Response)

    render(
      <SetupChecklist
        shop="test-shop.myshopify.com"
        onMilestoneShow={onMilestoneShow}
      />, {
        wrapper: createWrapper()
      }
    )

    await waitFor(() => {
      expect(onMilestoneShow).toHaveBeenCalledWith(
        expect.objectContaining({
          id: 'first_member',
          title: 'First Member!'
        })
      )
    })
  })
})

describe('SetupChecklistCompact', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    mockAuthFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockSetupStatus)
    } as Response)
  })

  it('renders compact version', async () => {
    render(<SetupChecklistCompact shop="test-shop.myshopify.com" />, {
      wrapper: createWrapper()
    })

    await waitFor(() => {
      // Multiple elements show 50%, check at least one exists
      const percentElements = screen.getAllByText('50%')
      expect(percentElements.length).toBeGreaterThan(0)
    })
  })
})

describe('SetupChecklist with null shop', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading state when shop is null', async () => {
    render(<SetupChecklist shop={null} />, {
      wrapper: createWrapper()
    })

    // Shows loading/skeleton state since query is disabled without shop
    expect(screen.getByText('Setup Progress')).toBeInTheDocument()

    // API should NOT be called when shop is null
    expect(mockAuthFetch).not.toHaveBeenCalled()
  })
})
