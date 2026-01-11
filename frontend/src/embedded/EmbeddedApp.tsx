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

// Embedded app pages
import { EmbeddedDashboard } from './pages/EmbeddedDashboard';
import { EmbeddedTiers } from './pages/EmbeddedTiers';
import { EmbeddedMembers } from './pages/EmbeddedMembers';
import { EmbeddedTradeIns } from './pages/EmbeddedTradeIns';
import { EmbeddedNewTradeIn } from './pages/EmbeddedNewTradeIn';
import { EmbeddedCategories } from './pages/EmbeddedCategories';
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

interface EmbeddedAppProps {
  shop: string | null;
}

export function EmbeddedApp({ shop }: EmbeddedAppProps) {
  return (
    <>
      {/* App Bridge NavMenu - configures Shopify Admin sidebar navigation */}
      <NavMenu>
        <Link to="/app/dashboard" rel="home">Dashboard</Link>
        <Link to="/app/members">Members</Link>
        <Link to="/app/trade-ins">Trade-Ins</Link>
        <Link to="/app/promotions">Promotions</Link>
        <Link to="/app/points">Points & Rewards</Link>
        <Link to="/app/tiers">Membership Tiers</Link>
        <Link to="/app/settings">Settings</Link>
      </NavMenu>

      {/* App Routes */}
      <Routes>
        <Route path="/" element={<Navigate to="/app/dashboard" replace />} />
        <Route path="/dashboard" element={<EmbeddedDashboard shop={shop} />} />
        <Route path="/tiers" element={<EmbeddedTiers shop={shop} />} />
        <Route path="/members" element={<EmbeddedMembers shop={shop} />} />
        <Route path="/trade-ins" element={<EmbeddedTradeIns shop={shop} />} />
        <Route path="/trade-ins/new" element={<EmbeddedNewTradeIn shop={shop} />} />
        <Route path="/trade-ins/categories" element={<EmbeddedCategories shop={shop} />} />
        <Route path="/promotions" element={<EmbeddedPromotions shop={shop} />} />
        <Route path="/points" element={<EmbeddedPoints shop={shop} />} />
        <Route path="/bulk-credit" element={<EmbeddedBulkCredit shop={shop} />} />
        <Route path="/settings" element={<EmbeddedSettings shop={shop} />} />
        <Route path="/billing" element={<EmbeddedBilling shop={shop} />} />
        <Route path="/referrals" element={<EmbeddedReferrals shop={shop} />} />
        <Route path="/analytics" element={<EmbeddedAnalytics shop={shop} />} />
        <Route path="/onboarding" element={<EmbeddedOnboarding shop={shop} />} />
        <Route path="/products/wizard" element={<EmbeddedProductWizard shop={shop} />} />
        <Route path="/theme-blocks" element={<EmbeddedThemeBlocks shop={shop} />} />
      </Routes>
    </>
  );
}
