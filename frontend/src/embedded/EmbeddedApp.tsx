/**
 * TradeUp Shopify Embedded App
 *
 * This component renders inside the Shopify Admin when merchants
 * access the TradeUp app. Uses Shopify Polaris for consistent UX.
 *
 * Navigation is handled by App Bridge NavMenu component.
 * App Bridge CDN is loaded in index.html with the API key.
 *
 * PERFORMANCE: All page components are lazy-loaded to reduce initial bundle size.
 * Only the code for the current page is downloaded, improving Time to Interactive.
 */
import { Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import { NavMenu } from '@shopify/app-bridge-react';
import { useQuery } from '@tanstack/react-query';
import { lazy, Suspense } from 'react';
import { Spinner, Frame } from '@shopify/polaris';
import { getApiUrl, authFetch } from '../hooks/useShopifyBridge';
import { I18nProvider } from '../hooks/useI18n';

// Lazy-loaded page components - only loaded when route is accessed
// This reduces initial bundle from ~1MB to ~200KB
const EmbeddedDashboard = lazy(() => import('./pages/EmbeddedDashboard').then(m => ({ default: m.EmbeddedDashboard })));
const EmbeddedTiers = lazy(() => import('./pages/EmbeddedTiers').then(m => ({ default: m.EmbeddedTiers })));
const EmbeddedMembers = lazy(() => import('./pages/EmbeddedMembers').then(m => ({ default: m.EmbeddedMembers })));
const EmbeddedTradeLedger = lazy(() => import('./pages/EmbeddedTradeLedger').then(m => ({ default: m.EmbeddedTradeLedger })));
const EmbeddedBulkCredit = lazy(() => import('./pages/EmbeddedBulkCredit').then(m => ({ default: m.EmbeddedBulkCredit })));
const EmbeddedPromotions = lazy(() => import('./pages/EmbeddedPromotions').then(m => ({ default: m.EmbeddedPromotions })));
const EmbeddedSettings = lazy(() => import('./pages/EmbeddedSettings').then(m => ({ default: m.EmbeddedSettings })));
const EmbeddedBilling = lazy(() => import('./pages/EmbeddedBilling').then(m => ({ default: m.EmbeddedBilling })));
const EmbeddedReferrals = lazy(() => import('./pages/EmbeddedReferrals').then(m => ({ default: m.EmbeddedReferrals })));
const EmbeddedAnalytics = lazy(() => import('./pages/EmbeddedAnalytics').then(m => ({ default: m.EmbeddedAnalytics })));
const EmbeddedOnboarding = lazy(() => import('./pages/EmbeddedOnboarding').then(m => ({ default: m.EmbeddedOnboarding })));
const EmbeddedProductWizard = lazy(() => import('./pages/EmbeddedProductWizard').then(m => ({ default: m.EmbeddedProductWizard })));
const EmbeddedThemeBlocks = lazy(() => import('./pages/EmbeddedThemeBlocks').then(m => ({ default: m.EmbeddedThemeBlocks })));
const EmbeddedPoints = lazy(() => import('./pages/EmbeddedPoints').then(m => ({ default: m.EmbeddedPoints })));
const EmbeddedIntegrations = lazy(() => import('./pages/EmbeddedIntegrations').then(m => ({ default: m.EmbeddedIntegrations })));
const EmbeddedCashback = lazy(() => import('./pages/EmbeddedCashback').then(m => ({ default: m.EmbeddedCashback })));
const EmbeddedBenchmarks = lazy(() => import('./pages/EmbeddedBenchmarks').then(m => ({ default: m.EmbeddedBenchmarks })));
const EmbeddedGamification = lazy(() => import('./pages/EmbeddedGamification').then(m => ({ default: m.EmbeddedGamification })));
const EmbeddedPageBuilder = lazy(() => import('./pages/EmbeddedPageBuilder').then(m => ({ default: m.EmbeddedPageBuilder })));
const EmbeddedWidgetBuilder = lazy(() => import('./pages/EmbeddedWidgetBuilder').then(m => ({ default: m.EmbeddedWidgetBuilder })));
const EmbeddedWidgets = lazy(() => import('./pages/EmbeddedWidgets').then(m => ({ default: m.EmbeddedWidgets })));
const EmbeddedStoreCreditEvents = lazy(() => import('./pages/EmbeddedStoreCreditEvents').then(m => ({ default: m.EmbeddedStoreCreditEvents })));
const EmbeddedPendingDistributions = lazy(() => import('./pages/EmbeddedPendingDistributions').then(m => ({ default: m.EmbeddedPendingDistributions })));
const EmbeddedReviewDashboard = lazy(() => import('./pages/EmbeddedReviewDashboard').then(m => ({ default: m.EmbeddedReviewDashboard })));

// Components - SupportButton is small, can load sync
import { SupportButton } from './components/SupportChatWidget';

// Loading fallback component
function PageLoader() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
      <Spinner accessibilityLabel="Loading page" size="large" />
    </div>
  );
}

interface EmbeddedAppProps {
  shop: string | null;
}

interface Settings {
  features?: {
    advanced_features_enabled?: boolean;
    points_enabled?: boolean;
    referrals_enabled?: boolean;
    self_signup_enabled?: boolean;
  };
}

async function fetchSettings(shop: string | null): Promise<Settings> {
  const response = await authFetch(`${getApiUrl()}/settings`, shop);
  if (!response.ok) throw new Error('Failed to fetch settings');
  const data = await response.json();
  return data.settings;
}

export function EmbeddedApp({ shop }: EmbeddedAppProps) {
  // Fetch settings to check if advanced features are enabled
  const { data: settings } = useQuery({
    queryKey: ['settings', shop],
    queryFn: () => fetchSettings(shop),
    enabled: !!shop,
    staleTime: 60000, // Cache for 60s to avoid re-fetching on every page
  });

  const showAdvanced = settings?.features?.advanced_features_enabled ?? false;

  return (
    <I18nProvider>
      {/* App Bridge NavMenu - configures Shopify Admin sidebar navigation */}
      {/* Default: Dashboard, Members, Trade-Ins, Settings */}
      {/* Advanced: + Promotions, Points & Rewards, Membership Tiers, Integrations */}
      <NavMenu>
        <Link to="/app/dashboard" rel="home">Dashboard</Link>
        <Link to="/app/members">Members</Link>
        <Link to="/app/trade-ins">Trade-Ins</Link>
        <Link to="/app/bonus-events">Bonus Events</Link>
        {showAdvanced && <Link to="/app/promotions">Promotions</Link>}
        {showAdvanced && <Link to="/app/cashback">Cashback</Link>}
        {showAdvanced && <Link to="/app/points">Points & Rewards</Link>}
        {showAdvanced && <Link to="/app/tiers">Membership Tiers</Link>}
        {showAdvanced && <Link to="/app/integrations">Integrations</Link>}
        {showAdvanced && <Link to="/app/gamification">Gamification</Link>}
        {showAdvanced && <Link to="/app/page-builder">Page Builder</Link>}
        {showAdvanced && <Link to="/app/widgets">Widgets</Link>}
        {showAdvanced && <Link to="/app/analytics">Analytics</Link>}
        <Link to="/app/settings">Settings</Link>
      </NavMenu>

      {/* App Routes - wrapped in Suspense for lazy loading */}
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<Navigate to="/app/dashboard" replace />} />
          <Route path="/dashboard" element={<EmbeddedDashboard shop={shop} />} />
          <Route path="/tiers" element={<EmbeddedTiers shop={shop} />} />
          <Route path="/members" element={<EmbeddedMembers shop={shop} />} />
          <Route path="/trade-ins" element={<EmbeddedTradeLedger shop={shop} />} />
          {/* Legacy routes redirect to new ledger */}
          <Route path="/trade-ins/new" element={<Navigate to="/app/trade-ins" replace />} />
          <Route path="/trade-ins/categories" element={<Navigate to="/app/trade-ins" replace />} />
          <Route path="/bonus-events" element={<EmbeddedStoreCreditEvents shop={shop} />} />
          <Route path="/promotions" element={<EmbeddedPromotions shop={shop} />} />
          <Route path="/cashback" element={<EmbeddedCashback shop={shop} />} />
          <Route path="/points" element={<EmbeddedPoints shop={shop} />} />
          <Route path="/bulk-credit" element={<EmbeddedBulkCredit shop={shop} />} />
          <Route path="/settings" element={<EmbeddedSettings shop={shop} />} />
          <Route path="/billing" element={<EmbeddedBilling shop={shop} />} />
          <Route path="/referrals" element={<EmbeddedReferrals shop={shop} />} />
          <Route path="/analytics" element={<EmbeddedAnalytics shop={shop} />} />
          <Route path="/benchmarks" element={<EmbeddedBenchmarks shop={shop} />} />
          <Route path="/integrations" element={<EmbeddedIntegrations shop={shop} />} />
          <Route path="/gamification" element={<EmbeddedGamification shop={shop} />} />
          <Route path="/page-builder" element={<EmbeddedPageBuilder shop={shop} />} />
          <Route path="/widget-builder" element={<EmbeddedWidgetBuilder shop={shop} />} />
          <Route path="/widgets" element={<EmbeddedWidgets shop={shop} />} />
          <Route path="/onboarding" element={<EmbeddedOnboarding shop={shop} />} />
          <Route path="/products/wizard" element={<EmbeddedProductWizard shop={shop} />} />
          <Route path="/theme-blocks" element={<EmbeddedThemeBlocks shop={shop} />} />
          <Route path="/pending-distributions" element={<EmbeddedPendingDistributions shop={shop} />} />
          <Route path="/review-dashboard" element={<EmbeddedReviewDashboard shop={shop} />} />
        </Routes>
      </Suspense>

      {/* Support Chat Widget */}
      <SupportButton shopDomain={shop || undefined} />
    </I18nProvider>
  );
}
