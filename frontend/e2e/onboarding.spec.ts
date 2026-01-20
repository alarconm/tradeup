import { test, expect } from '@playwright/test';

/**
 * E2E tests for the onboarding flow
 *
 * Note: These tests require a running backend with test data.
 * In CI, mock the API responses or use a test database.
 */

test.describe('Onboarding Flow', () => {
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

  test('should display the dashboard page', async ({ page }) => {
    await page.goto('/app');

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Should see the Dashboard title
    await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible();
  });

  test('should navigate to settings page', async ({ page }) => {
    await page.goto('/app/settings');

    await page.waitForLoadState('networkidle');

    // Should see Settings page content
    await expect(page.getByRole('heading', { name: /settings/i })).toBeVisible();
  });

  test('should navigate to tiers page', async ({ page }) => {
    await page.goto('/app/tiers');

    await page.waitForLoadState('networkidle');

    // Should see Tiers page content
    await expect(page.getByRole('heading', { name: /tiers|membership/i })).toBeVisible();
  });

  test('should navigate to billing page', async ({ page }) => {
    await page.goto('/app/billing');

    await page.waitForLoadState('networkidle');

    // Should see Billing page content
    await expect(page.getByRole('heading', { name: /billing|subscription|plan/i })).toBeVisible();
  });

  test('should show setup checklist on dashboard', async ({ page }) => {
    // Mock the setup status API response
    await page.route('**/api/setup/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          checklist: [
            {
              id: 'configure_tiers',
              title: 'Configure membership tiers',
              description: 'Set up your tier structure',
              completed: false,
              action_url: '/app/tiers',
              action_label: 'Configure',
              priority: 1,
              category: 'setup'
            }
          ],
          completion: {
            setup_percentage: 0,
            setup_completed: 0,
            setup_total: 5,
            all_complete: false
          },
          next_action: {
            id: 'configure_tiers',
            title: 'Configure membership tiers',
            action_url: '/app/tiers',
            action_label: 'Configure'
          },
          milestones: {},
          uncelebrated_milestones: []
        })
      });
    });

    // Also mock dashboard stats
    await page.route('**/api/dashboard/stats', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
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
      });
    });

    await page.route('**/api/dashboard/activity', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    });

    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    // Should see setup checklist
    await expect(page.getByText(/setup progress/i)).toBeVisible();
    await expect(page.getByText(/0 of 5 steps completed/i)).toBeVisible();
  });
});
