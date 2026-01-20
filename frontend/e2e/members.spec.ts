import { test, expect } from '@playwright/test';

/**
 * E2E tests for member enrollment and management
 *
 * Note: These tests require a running backend with test data.
 * In CI, mock the API responses or use a test database.
 */

test.describe('Member Enrollment', () => {
  test.beforeEach(async ({ page }) => {
    // Mock the Shopify embedded context
    await page.addInitScript(() => {
      // @ts-ignore
      window.__TRADEUP_CONFIG__ = {
        shop: 'test-shop.myshopify.com',
        host: 'dGVzdC1zaG9w',
        apiKey: 'test-api-key',
        appUrl: 'http://localhost:5000'
      };
      // @ts-ignore
      window.shopify = {
        config: {
          shop: 'test-shop.myshopify.com',
          apiKey: 'test-api-key'
        },
        environment: {
          embedded: false
        },
        idToken: () => Promise.resolve('test-token')
      };
    });
  });

  test('should display the members page', async ({ page }) => {
    // Mock the members API
    await page.route('**/api/members*', async (route) => {
      if (route.request().url().includes('/tiers')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            tiers: [
              { id: 1, name: 'Bronze', description: 'Entry tier', color: '#CD7F32', active: true },
              { id: 2, name: 'Silver', description: 'Mid tier', color: '#C0C0C0', active: true },
              { id: 3, name: 'Gold', description: 'Top tier', color: '#FFD700', active: true }
            ]
          })
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            members: [
              {
                id: 1,
                shopify_customer_id: 'gid://shopify/Customer/123',
                first_name: 'John',
                last_name: 'Doe',
                email: 'john@example.com',
                tier: { id: 1, name: 'Bronze', color: '#CD7F32' },
                total_trade_in_value: 100,
                total_credits_issued: 90,
                trade_in_count: 2,
                status: 'active',
                created_at: '2026-01-01T00:00:00Z',
                last_trade_in_at: '2026-01-15T00:00:00Z'
              }
            ],
            total: 1,
            page: 1,
            per_page: 20,
            pages: 1
          })
        });
      }
    });

    await page.route('**/api/settings', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          settings: {
            general: { program_name: 'Rewards', timezone: 'UTC' },
            credits: { expiration_days: 365 }
          }
        })
      });
    });

    await page.goto('/app/members');
    await page.waitForLoadState('networkidle');

    // Should see Members page
    await expect(page.getByRole('heading', { name: /members/i })).toBeVisible();
  });

  test('should display member list', async ({ page }) => {
    await page.route('**/api/members*', async (route) => {
      if (route.request().url().includes('/tiers')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            tiers: [
              { id: 1, name: 'Bronze', description: 'Entry tier', color: '#CD7F32', active: true }
            ]
          })
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            members: [
              {
                id: 1,
                shopify_customer_id: 'gid://shopify/Customer/123',
                first_name: 'John',
                last_name: 'Doe',
                email: 'john@example.com',
                tier: { id: 1, name: 'Bronze', color: '#CD7F32' },
                total_trade_in_value: 100,
                total_credits_issued: 90,
                trade_in_count: 2,
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
                tier: { id: 1, name: 'Bronze', color: '#CD7F32' },
                total_trade_in_value: 200,
                total_credits_issued: 180,
                trade_in_count: 5,
                status: 'active',
                created_at: '2026-01-05T00:00:00Z',
                last_trade_in_at: '2026-01-18T00:00:00Z'
              }
            ],
            total: 2,
            page: 1,
            per_page: 20,
            pages: 1
          })
        });
      }
    });

    await page.route('**/api/settings', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          settings: {
            general: { program_name: 'Rewards' },
            credits: { expiration_days: 365 }
          }
        })
      });
    });

    await page.goto('/app/members');
    await page.waitForLoadState('networkidle');

    // Should show member names
    await expect(page.getByText('John Doe')).toBeVisible();
    await expect(page.getByText('Jane Smith')).toBeVisible();
  });

  test('should have search functionality', async ({ page }) => {
    await page.route('**/api/members*', async (route) => {
      if (route.request().url().includes('/tiers')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            tiers: [{ id: 1, name: 'Bronze', description: 'Entry', color: '#CD7F32', active: true }]
          })
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            members: [],
            total: 0,
            page: 1,
            per_page: 20,
            pages: 0
          })
        });
      }
    });

    await page.route('**/api/settings', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          settings: { general: { program_name: 'Rewards' }, credits: { expiration_days: 365 } }
        })
      });
    });

    await page.goto('/app/members');
    await page.waitForLoadState('networkidle');

    // Should have a search input
    const searchInput = page.getByPlaceholder(/search/i);
    await expect(searchInput).toBeVisible();
  });

  test('should show empty state when no members', async ({ page }) => {
    await page.route('**/api/members*', async (route) => {
      if (route.request().url().includes('/tiers')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            tiers: [{ id: 1, name: 'Bronze', description: 'Entry', color: '#CD7F32', active: true }]
          })
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            members: [],
            total: 0,
            page: 1,
            per_page: 20,
            pages: 0
          })
        });
      }
    });

    await page.route('**/api/settings', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          settings: { general: { program_name: 'Rewards' }, credits: { expiration_days: 365 } }
        })
      });
    });

    await page.goto('/app/members');
    await page.waitForLoadState('networkidle');

    // Should show no members found message
    await expect(page.getByText(/no members found/i)).toBeVisible();
  });

  test('should have Add Member button', async ({ page }) => {
    await page.route('**/api/members*', async (route) => {
      if (route.request().url().includes('/tiers')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            tiers: [{ id: 1, name: 'Bronze', description: 'Entry', color: '#CD7F32', active: true }]
          })
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            members: [],
            total: 0,
            page: 1,
            per_page: 20,
            pages: 0
          })
        });
      }
    });

    await page.route('**/api/settings', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          settings: { general: { program_name: 'Rewards' }, credits: { expiration_days: 365 } }
        })
      });
    });

    await page.goto('/app/members');
    await page.waitForLoadState('networkidle');

    // Should have an Add Member button
    await expect(page.getByRole('button', { name: /add member/i })).toBeVisible();
  });
});
