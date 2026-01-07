/**
 * TradeUp Shopify Embedded App
 *
 * This component renders inside the Shopify Admin when merchants
 * access the TradeUp app. Uses Shopify Polaris for consistent UX.
 */
import { Routes, Route, Navigate } from 'react-router-dom';
import { Frame, Navigation, TopBar } from '@shopify/polaris';
import {
  HomeIcon,
  PersonIcon,
  ReceiptIcon,
  SettingsIcon,
  CreditCardIcon,
  ListBulletedIcon,
  DiscountIcon,
} from '@shopify/polaris-icons';
import { useState, useCallback } from 'react';

// Embedded app pages
import { EmbeddedDashboard } from './pages/EmbeddedDashboard';
import { EmbeddedTiers } from './pages/EmbeddedTiers';
import { EmbeddedMembers } from './pages/EmbeddedMembers';
import { EmbeddedTradeIns } from './pages/EmbeddedTradeIns';
import { EmbeddedPromotions } from './pages/EmbeddedPromotions';
import { EmbeddedSettings } from './pages/EmbeddedSettings';
import { EmbeddedBilling } from './pages/EmbeddedBilling';

interface EmbeddedAppProps {
  shop: string | null;
}

export function EmbeddedApp({ shop }: EmbeddedAppProps) {
  const [mobileNavActive, setMobileNavActive] = useState(false);

  const toggleMobileNav = useCallback(() => {
    setMobileNavActive((active) => !active);
  }, []);

  const logo = {
    width: 36,
    topBarSource: '/tradeup-logo.svg',
    contextualSaveBarSource: '/tradeup-logo.svg',
    accessibilityLabel: 'TradeUp',
  };

  const topBarMarkup = (
    <TopBar
      showNavigationToggle
      onNavigationToggle={toggleMobileNav}
    />
  );

  const navigationMarkup = (
    <Navigation location={window.location.pathname}>
      <Navigation.Section
        items={[
          {
            url: '/app/dashboard',
            label: 'Dashboard',
            icon: HomeIcon,
            selected: window.location.pathname === '/app/dashboard',
          },
          {
            url: '/app/tiers',
            label: 'Membership Tiers',
            icon: ListBulletedIcon,
            selected: window.location.pathname === '/app/tiers',
          },
          {
            url: '/app/members',
            label: 'Members',
            icon: PersonIcon,
            selected: window.location.pathname.startsWith('/app/members'),
          },
          {
            url: '/app/trade-ins',
            label: 'Trade-Ins',
            icon: ReceiptIcon,
            selected: window.location.pathname.startsWith('/app/trade-ins'),
          },
          {
            url: '/app/promotions',
            label: 'Promotions',
            icon: DiscountIcon,
            selected: window.location.pathname.startsWith('/app/promotions'),
          },
        ]}
      />
      <Navigation.Section
        title="Settings"
        items={[
          {
            url: '/app/billing',
            label: 'Plan & Billing',
            icon: CreditCardIcon,
            selected: window.location.pathname === '/app/billing',
          },
          {
            url: '/app/settings',
            label: 'Settings',
            icon: SettingsIcon,
            selected: window.location.pathname === '/app/settings',
          },
        ]}
      />
    </Navigation>
  );

  return (
    <Frame
      logo={logo}
      topBar={topBarMarkup}
      navigation={navigationMarkup}
      showMobileNavigation={mobileNavActive}
      onNavigationDismiss={toggleMobileNav}
    >
      <Routes>
        <Route path="/" element={<Navigate to="/app/dashboard" replace />} />
        <Route path="/dashboard" element={<EmbeddedDashboard shop={shop} />} />
        <Route path="/tiers" element={<EmbeddedTiers shop={shop} />} />
        <Route path="/members" element={<EmbeddedMembers shop={shop} />} />
        <Route path="/trade-ins" element={<EmbeddedTradeIns shop={shop} />} />
        <Route path="/promotions" element={<EmbeddedPromotions shop={shop} />} />
        <Route path="/settings" element={<EmbeddedSettings shop={shop} />} />
        <Route path="/billing" element={<EmbeddedBilling shop={shop} />} />
      </Routes>
    </Frame>
  );
}
