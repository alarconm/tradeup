/**
 * Tests for EmbeddedDashboard component
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
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
import { EmbeddedDashboard } from '../embedded/pages/EmbeddedDashboard'

const mockAuthFetch = vi.mocked(authFetch)

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

describe('EmbeddedDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading state while fetching data', async () => {
    // Mock a pending promise
    mockAuthFetch.mockImplementation(() => new Promise(() => {}))

    render(<EmbeddedDashboard shop="test-shop.myshopify.com" />, {
      wrapper: createWrapper()
    })

    // Dashboard shows skeleton loaders during loading, check for loading subtitle
    await waitFor(() => {
      expect(screen.getByText(/Loading your membership program data/i)).toBeInTheDocument()
    })
  })

  it('displays dashboard stats when data loads', async () => {
    const mockStats = {
      total_members: 100,
      active_members: 85,
      pending_trade_ins: 5,
      completed_trade_ins: 50,
      total_trade_in_value: 5000,
      total_credits_issued: 4500,
      subscription: {
        plan: 'growth',
        status: 'active',
        active: true,
        usage: {
          members: { current: 85, limit: 1000, percentage: 8.5 },
          tiers: { current: 3, limit: 5, percentage: 60 }
        }
      }
    }

    mockAuthFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockStats)
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([])
      } as Response)

    render(<EmbeddedDashboard shop="test-shop.myshopify.com" />, {
      wrapper: createWrapper()
    })

    await waitFor(() => {
      // Check that member count is displayed somewhere
      const elements = screen.getAllByText(/100/)
      expect(elements.length).toBeGreaterThan(0)
    })
  })

  it('handles API errors gracefully', async () => {
    mockAuthFetch.mockResolvedValue({
      ok: false,
      status: 500
    } as Response)

    render(<EmbeddedDashboard shop="test-shop.myshopify.com" />, {
      wrapper: createWrapper()
    })

    // Component should show error banner on API failure
    await waitFor(() => {
      expect(screen.getByText(/Failed to load dashboard data/i)).toBeInTheDocument()
    }, { timeout: 5000 })
  })

  it('passes shop prop to API calls', async () => {
    mockAuthFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        total_members: 0,
        active_members: 0,
        pending_trade_ins: 0,
        completed_trade_ins: 0,
        total_trade_in_value: 0,
        total_credits_issued: 0,
        subscription: {
          plan: 'free',
          status: 'active',
          active: true,
          usage: {
            members: { current: 0, limit: 50, percentage: 0 },
            tiers: { current: 0, limit: 2, percentage: 0 }
          }
        }
      })
    } as Response)

    render(<EmbeddedDashboard shop="my-test-shop.myshopify.com" />, {
      wrapper: createWrapper()
    })

    await waitFor(() => {
      expect(mockAuthFetch).toHaveBeenCalled()
      const [, shopArg] = mockAuthFetch.mock.calls[0]
      expect(shopArg).toBe('my-test-shop.myshopify.com')
    })
  })
})

describe('EmbeddedDashboard with null shop', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows warning banner when shop is null', async () => {
    render(<EmbeddedDashboard shop={null} />, {
      wrapper: createWrapper()
    })

    // Should show a warning banner about no shop connected
    await waitFor(() => {
      expect(screen.getByText(/No shop connected/i)).toBeInTheDocument()
    })

    // API should NOT be called when shop is null
    expect(mockAuthFetch).not.toHaveBeenCalled()
  })
})
