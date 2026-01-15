/**
 * TradeUp Shopify Embedded App
 *
 * This component renders inside the Shopify Admin when merchants
 * access the TradeUp app. Uses Shopify Polaris for consistent UX.
 *
 * Navigation is handled by App Bridge NavMenu component.
 * App Bridge CDN is loaded in index.html with the API key.
 */
import { Routes, Route, Navigate, Link } from 'react-router-dom';
import { NavMenu } from '@shopify/app-bridge-react';
import { useQuery } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../hooks/useShopifyBridge';
import { I18nProvider } from '../hooks/useI18n';

// Embedded app pages
import { EmbeddedDashboard } from './pages/EmbeddedDashboard';
import { EmbeddedTiers } from './pages/EmbeddedTiers';
import { EmbeddedMembers } from './pages/EmbeddedMembers';
import { EmbeddedTradeLedger } from './pages/EmbeddedTradeLedger';
import { EmbeddedBulkCredit } from './pages/EmbeddedBulkCredit';
import { EmbeddedPromotions } from './pages/EmbeddedPromotions';
import { EmbeddedSettings } from './pages/EmbeddedSettings';
import { EmbeddedBilling } from './pages/EmbeddedBilling';
import { EmbeddedReferrals } from './pages/EmbeddedReferrals';
import { EmbeddedAnalytics } from './pages/EmbeddedAnalytics';
import { EmbeddedOnboarding } from './pages/EmbeddedOnboarding';
import { EmbeddedProductWizard } from './pages/EmbeddedProductWizard';
import { EmbeddedThemeBlocks } from './pages/EmbeddedThemeBlocks';
import { EmbeddedPoints } from './pages/EmbeddedPoints';

// New feature pages
import { EmbeddedIntegrations } from './pages/EmbeddedIntegrations';
import { EmbeddedCashback } from './pages/EmbeddedCashback';
import { EmbeddedBenchmarks } from './pages/EmbeddedBenchmarks';
import { EmbeddedGamification } from './pages/EmbeddedGamification';
import { EmbeddedPageBuilder } from './pages/EmbeddedPageBuilder';
import { EmbeddedWidgetBuilder } from './pages/EmbeddedWidgetBuilder';
import { EmbeddedStoreCreditEvents } from './pages/EmbeddedStoreCreditEvents';

// Components
import { SupportButton } from './components/SupportChatWidget';

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
        {showAdvanced && <Link to="/app/analytics">Analytics</Link>}
        <Link to="/app/settings">Settings</Link>
      </NavMenu>

      {/* App Routes */}
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
        <Route path="/onboarding" element={<EmbeddedOnboarding shop={shop} />} />
        <Route path="/products/wizard" element={<EmbeddedProductWizard shop={shop} />} />
        <Route path="/theme-blocks" element={<EmbeddedThemeBlocks shop={shop} />} />
      </Routes>

      {/* Support Chat Widget */}
      <SupportButton shopDomain={shop || undefined} />
    </I18nProvider>
  );
}
