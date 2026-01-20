/**
 * Tests for EmbeddedMembers component
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

// Mock Shopify App Bridge TitleBar
vi.mock('@shopify/app-bridge-react', () => ({
  TitleBar: ({ title }: { title: string }) => <div data-testid="title-bar">{title}</div>
}))

// Import after mocking
import { authFetch } from '../hooks/useShopifyBridge'
import { EmbeddedMembers } from '../embedded/pages/EmbeddedMembers'

const mockAuthFetch = vi.mocked(authFetch)

const mockMembersResponse = {
  members: [
    {
      id: 1,
      shopify_customer_id: 'gid://shopify/Customer/123',
      first_name: 'John',
      last_name: 'Doe',
      email: 'john@example.com',
      tier: { id: 1, name: 'Gold', color: '#FFD700' },
      total_trade_in_value: 500,
      total_credits_issued: 450,
      trade_in_count: 5,
      status: 'active',
      created_at: '2026-01-01T00:00:00Z',
      last_trade_in_at: '2026-01-15T00:00:00Z'
    },
    {
      id: 2,
      shopify_customer_id: 'gid://shopify/Customer/456',
      first_name: 'Jane',
      last_name: 'Smith',
      email: 'jane@example.com',
      tier: { id: 2, name: 'Silver', color: '#C0C0C0' },
      total_trade_in_value: 200,
      total_credits_issued: 180,
      trade_in_count: 2,
      status: 'active',
      created_at: '2026-01-05T00:00:00Z',
      last_trade_in_at: '2026-01-10T00:00:00Z'
    }
  ],
  total: 2,
  page: 1,
  per_page: 20,
  pages: 1
}

const mockTiersResponse = {
  tiers: [
    { id: 1, name: 'Gold', description: 'Top tier', color: '#FFD700', active: true },
    { id: 2, name: 'Silver', description: 'Mid tier', color: '#C0C0C0', active: true }
  ]
}

const mockSettingsResponse = {
  settings: {
    general: { program_name: 'Rewards' },
    credits: { expiration_days: 365 }
  }
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

describe('EmbeddedMembers', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    // Default mocks
    mockAuthFetch.mockImplementation((url: string) => {
      if (url.includes('/members/tiers')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockTiersResponse)
        } as Response)
      }
      if (url.includes('/settings')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockSettingsResponse)
        } as Response)
      }
      if (url.includes('/members')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockMembersResponse)
        } as Response)
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      } as Response)
    })
  })

  it('shows loading spinner while fetching members', async () => {
    // Override to return pending promise
    mockAuthFetch.mockImplementation(() => new Promise(() => {}))

    render(<EmbeddedMembers shop="test-shop.myshopify.com" />, {
      wrapper: createWrapper()
    })

    // Check for the Spinner component (Polaris renders it with specific SVG)
    await waitFor(() => {
      const spinners = document.querySelectorAll('.Polaris-Spinner')
      expect(spinners.length).toBeGreaterThan(0)
    })
  })

  it('displays members list when data loads', async () => {
    render(<EmbeddedMembers shop="test-shop.myshopify.com" />, {
      wrapper: createWrapper()
    })

    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument()
      expect(screen.getByText('Jane Smith')).toBeInTheDocument()
    }, { timeout: 5000 })
  })

  it('displays member tiers', async () => {
    render(<EmbeddedMembers shop="test-shop.myshopify.com" />, {
      wrapper: createWrapper()
    })

    await waitFor(() => {
      expect(screen.getByText('Gold')).toBeInTheDocument()
      expect(screen.getByText('Silver')).toBeInTheDocument()
    }, { timeout: 5000 })
  })

  it('shows empty state when no members', async () => {
    mockAuthFetch.mockImplementation((url: string) => {
      if (url.includes('/members/tiers')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockTiersResponse)
        } as Response)
      }
      if (url.includes('/settings')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockSettingsResponse)
        } as Response)
      }
      if (url.includes('/members')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            members: [],
            total: 0,
            page: 1,
            per_page: 20,
            pages: 0
          })
        } as Response)
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      } as Response)
    })

    render(<EmbeddedMembers shop="test-shop.myshopify.com" />, {
      wrapper: createWrapper()
    })

    await waitFor(() => {
      expect(screen.getByText(/No members found/i)).toBeInTheDocument()
    }, { timeout: 5000 })
  })

  it('handles API errors gracefully', async () => {
    mockAuthFetch.mockResolvedValue({
      ok: false,
      status: 500
    } as Response)

    render(<EmbeddedMembers shop="test-shop.myshopify.com" />, {
      wrapper: createWrapper()
    })

    // Should show error banner on API failure
    await waitFor(() => {
      expect(screen.getByText(/Failed to load members/i)).toBeInTheDocument()
    }, { timeout: 5000 })
  })
})

describe('EmbeddedMembers search', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    mockAuthFetch.mockImplementation((url: string) => {
      if (url.includes('/members/tiers')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockTiersResponse)
        } as Response)
      }
      if (url.includes('/settings')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockSettingsResponse)
        } as Response)
      }
      if (url.includes('/members')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockMembersResponse)
        } as Response)
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      } as Response)
    })
  })

  it('has search input', async () => {
    render(<EmbeddedMembers shop="test-shop.myshopify.com" />, {
      wrapper: createWrapper()
    })

    await waitFor(() => {
      const searchInputs = screen.getAllByRole('textbox')
      expect(searchInputs.length).toBeGreaterThan(0)
    }, { timeout: 5000 })
  })
})

describe('EmbeddedMembers with null shop', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows warning banner when shop is null', async () => {
    render(<EmbeddedMembers shop={null} />, {
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
