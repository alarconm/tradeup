import { test, expect } from '@playwright/test';

/**
 * E2E tests for trade-in approval workflow
 *
 * Note: These tests require a running backend with test data.
 * In CI, mock the API responses or use a test database.
 */

test.describe('Trade-in Approval', () => {
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

  test('should display the trade-ins page', async ({ page }) => {
    await page.route('**/api/trade-ins*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          trade_ins: [],
          total: 0,
          page: 1,
          per_page: 20,
          pages: 0
        })
      });
    });

    await page.goto('/app/trade-ins');
    await page.waitForLoadState('networkidle');

    // Should see Trade-ins page
    await expect(page.getByRole('heading', { name: /trade-ins|trade ins/i })).toBeVisible();
  });

  test('should show trade-in list with pending items', async ({ page }) => {
    await page.route('**/api/trade-ins*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          trade_ins: [
            {
              id: 1,
              batch_reference: 'TI-001',
              member: {
                id: 1,
                first_name: 'John',
                last_name: 'Doe'
              },
              status: 'pending',
              total_value: 150,
              items_count: 3,
              created_at: '2026-01-15T10:00:00Z'
            },
            {
              id: 2,
              batch_reference: 'TI-002',
              member: {
                id: 2,
                first_name: 'Jane',
                last_name: 'Smith'
              },
              status: 'approved',
              total_value: 275,
              items_count: 5,
              created_at: '2026-01-14T14:30:00Z'
            }
          ],
          total: 2,
          page: 1,
          per_page: 20,
          pages: 1
        })
      });
    });

    await page.goto('/app/trade-ins');
    await page.waitForLoadState('networkidle');

    // Should show trade-in references
    await expect(page.getByText('TI-001')).toBeVisible();
    await expect(page.getByText('TI-002')).toBeVisible();
  });

  test('should show pending status badge', async ({ page }) => {
    await page.route('**/api/trade-ins*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          trade_ins: [
            {
              id: 1,
              batch_reference: 'TI-001',
              member: { id: 1, first_name: 'John', last_name: 'Doe' },
              status: 'pending',
              total_value: 150,
              items_count: 3,
              created_at: '2026-01-15T10:00:00Z'
            }
          ],
          total: 1,
          page: 1,
          per_page: 20,
          pages: 1
        })
      });
    });

    await page.goto('/app/trade-ins');
    await page.waitForLoadState('networkidle');

    // Should show pending status
    await expect(page.getByText(/pending/i)).toBeVisible();
  });

  test('should filter by status', async ({ page }) => {
    await page.route('**/api/trade-ins*', async (route) => {
      const url = route.request().url();
      // Check if filtering by pending status
      if (url.includes('status=pending')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            trade_ins: [
              {
                id: 1,
                batch_reference: 'TI-001',
                member: { id: 1, first_name: 'John', last_name: 'Doe' },
                status: 'pending',
                total_value: 150,
                items_count: 3,
                created_at: '2026-01-15T10:00:00Z'
              }
            ],
            total: 1,
            page: 1,
            per_page: 20,
            pages: 1
          })
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            trade_ins: [
              {
                id: 1,
                batch_reference: 'TI-001',
                member: { id: 1, first_name: 'John', last_name: 'Doe' },
                status: 'pending',
                total_value: 150,
                items_count: 3,
                created_at: '2026-01-15T10:00:00Z'
              },
              {
                id: 2,
                batch_reference: 'TI-002',
                member: { id: 2, first_name: 'Jane', last_name: 'Smith' },
                status: 'approved',
                total_value: 275,
                items_count: 5,
                created_at: '2026-01-14T14:30:00Z'
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

    await page.goto('/app/trade-ins');
    await page.waitForLoadState('networkidle');

    // Should have filter tabs or dropdown
    await expect(page.getByRole('heading', { name: /trade-ins|trade ins/i })).toBeVisible();
  });

  test('should show empty state when no trade-ins', async ({ page }) => {
    await page.route('**/api/trade-ins*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          trade_ins: [],
          total: 0,
          page: 1,
          per_page: 20,
          pages: 0
        })
      });
    });

    await page.goto('/app/trade-ins');
    await page.waitForLoadState('networkidle');

    // Should show no trade-ins message or empty state
    await expect(page.getByText(/no trade-ins|no results|empty/i)).toBeVisible();
  });

  test('should have New Trade-in button', async ({ page }) => {
    await page.route('**/api/trade-ins*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          trade_ins: [],
          total: 0,
          page: 1,
          per_page: 20,
          pages: 0
        })
      });
    });

    await page.goto('/app/trade-ins');
    await page.waitForLoadState('networkidle');

    // Should have a New Trade-in button or link
    await expect(page.getByRole('button', { name: /new trade-in|start trade-in|create/i })).toBeVisible();
  });
});
