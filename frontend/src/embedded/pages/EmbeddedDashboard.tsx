/**
 * TradeUp Dashboard - Shopify Embedded Version
 *
 * Overview of membership program performance with key metrics,
 * recent activity, and quick actions.
 */
import {
  Page,
  Layout,
  Card,
  Text,
  InlineStack,
  BlockStack,
  Box,
  Badge,
  ProgressBar,
  DataTable,
  EmptyState,
  Spinner,
  Banner,
  InlineGrid,
} from '@shopify/polaris';
import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';
import { SetupChecklist } from '../components/SetupChecklist';

interface DashboardProps {
  shop: string | null;
}

interface DashboardStats {
  total_members: number;
  active_members: number;
  pending_trade_ins: number;
  completed_trade_ins: number;
  total_trade_in_value: number;
  total_credits_issued: number;
  subscription: {
    plan: string;
    status: string;
    active: boolean;
    usage: {
      members: { current: number; limit: number; percentage: number };
      tiers: { current: number; limit: number; percentage: number };
    };
  };
  // Product wizard status
  membership_products_count?: number;
  membership_products_draft?: boolean;
  product_wizard_in_progress?: boolean;
}

interface RecentActivity {
  id: number;
  type: string;
  member_name: string;
  description: string;
  amount: number;
  created_at: string;
}

async function fetchDashboard(shop: string | null): Promise<DashboardStats> {
  const response = await authFetch(
    `${getApiUrl()}/dashboard/stats`,
    shop
  );
  if (!response.ok) throw new Error('Failed to fetch dashboard');
  return response.json();
}

async function fetchRecentActivity(shop: string | null): Promise<RecentActivity[]> {
  const response = await authFetch(
    `${getApiUrl()}/dashboard/activity`,
    shop
  );
  if (!response.ok) throw new Error('Failed to fetch activity');
  return response.json();
}

// Hook to detect mobile viewport with multiple breakpoints
function useResponsive() {
  const [screenSize, setScreenSize] = useState(() => {
    if (typeof window === 'undefined') return { isSmallMobile: false, isMobile: false, isTablet: false };
    const width = window.innerWidth;
    return {
      isSmallMobile: width < 480,  // iPhone SE, small phones
      isMobile: width < 768,        // Most phones
      isTablet: width < 1024,       // Tablets
    };
  });

  useEffect(() => {
    const checkSize = () => {
      const width = window.innerWidth;
      setScreenSize({
        isSmallMobile: width < 480,
        isMobile: width < 768,
        isTablet: width < 1024,
      });
    };
    window.addEventListener('resize', checkSize);
    return () => window.removeEventListener('resize', checkSize);
  }, []);

  return screenSize;
}

export function EmbeddedDashboard({ shop }: DashboardProps) {
  const { isSmallMobile, isMobile, isTablet } = useResponsive();
  const navigate = useNavigate();

  // Both queries run in parallel with caching for faster subsequent loads
  const { data: stats, isLoading: statsLoading, error: statsError } = useQuery({
    queryKey: ['dashboard', shop],
    queryFn: () => fetchDashboard(shop),
    enabled: !!shop,
    staleTime: 30000, // Cache for 30s
    gcTime: 60000, // Keep in cache for 60s
  });

  const { data: activity, isLoading: activityLoading } = useQuery({
    queryKey: ['activity', shop],
    queryFn: () => fetchRecentActivity(shop),
    enabled: !!shop,
    staleTime: 30000,
    gcTime: 60000,
  });

  if (!shop) {
    return (
      <Page title="Dashboard">
        <Banner tone="warning">
          <p>No shop connected. Please install the app from the Shopify App Store.</p>
        </Banner>
      </Page>
    );
  }

  if (statsLoading) {
    return (
      <Page
        title="Dashboard"
        subtitle="Loading your membership program data..."
      >
        <Layout>
          <Layout.Section>
            <InlineGrid columns={isSmallMobile ? 1 : (isMobile || isTablet) ? 2 : 4} gap={isMobile ? "300" : "400"}>
              {[1, 2, 3, 4].map((i) => (
                <Card key={i}>
                  <BlockStack gap="200">
                    <Box background="bg-surface-secondary" borderRadius="100" minHeight="20px" />
                    <Box background="bg-surface-secondary" borderRadius="100" minHeight="40px" />
                    <Box background="bg-surface-secondary" borderRadius="100" minHeight="20px" maxWidth="60px" />
                  </BlockStack>
                </Card>
              ))}
            </InlineGrid>
          </Layout.Section>
          <Layout.Section variant="oneThird">
            <Card>
              <BlockStack gap="400">
                <Box background="bg-surface-secondary" borderRadius="100" minHeight="24px" />
                <Box background="bg-surface-secondary" borderRadius="100" minHeight="40px" />
                <Box background="bg-surface-secondary" borderRadius="100" minHeight="40px" />
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  if (statsError) {
    return (
      <Page title="Dashboard">
        <Banner tone="critical">
          <p>Failed to load dashboard data. Please try refreshing the page.</p>
        </Banner>
      </Page>
    );
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  return (
    <Page
      title="Dashboard"
      subtitle={`Welcome back! Here's how your membership program is performing.`}
    >
      <Layout>
        {/* Subscription Status Banner */}
        {stats?.subscription && !stats.subscription.active && (
          <Layout.Section>
            <Banner
              title="Subscription Required"
              action={{ content: 'Choose a Plan', url: '/app/billing' }}
              tone="warning"
            >
              <p>
                Start your free trial to unlock all TradeUp features.
              </p>
            </Banner>
          </Layout.Section>
        )}

        {/* Draft Products Warning Banner */}
        {stats?.membership_products_draft && (
          <Layout.Section>
            <Banner
              title="Membership Products in Draft Mode"
              action={{
                content: 'Complete Setup',
                onAction: () => navigate('/app/products/wizard'),
              }}
              tone="warning"
            >
              <p>
                Your {stats.membership_products_count || 0} membership product{(stats.membership_products_count || 0) !== 1 ? 's are' : ' is'} not visible to customers yet.
                Publish them when you're ready to start selling memberships.
              </p>
            </Banner>
          </Layout.Section>
        )}

        {/* Product Wizard In Progress Banner */}
        {stats?.product_wizard_in_progress && !stats?.membership_products_draft && (
          <Layout.Section>
            <Banner
              title="Product Setup Incomplete"
              action={{
                content: 'Resume Setup',
                onAction: () => navigate('/app/products/wizard'),
              }}
              tone="info"
            >
              <p>
                You have an unfinished product setup. Continue where you left off.
              </p>
            </Banner>
          </Layout.Section>
        )}

        {/* Setup Checklist - Shows until all setup is complete */}
        <Layout.Section>
          <SetupChecklist shop={shop} compact />
        </Layout.Section>

        {/* Key Metrics - Clickable Cards */}
        <Layout.Section>
          <InlineGrid columns={isSmallMobile ? 1 : (isMobile || isTablet) ? 2 : 4} gap={isMobile ? "300" : "400"}>
            <div
              onClick={() => navigate('/app/members')}
              style={{ cursor: 'pointer' }}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && navigate('/app/members')}
            >
              <Card>
                <BlockStack gap="200">
                  <Text as="h3" variant={isMobile ? "headingSm" : "headingMd"}>Total Members</Text>
                  <Text as="p" variant={isMobile ? "headingLg" : "heading2xl"}>{stats?.total_members || 0}</Text>
                  <Badge tone="success">{String(`${stats?.active_members ?? 0} active`)}</Badge>
                </BlockStack>
              </Card>
            </div>

            <div
              onClick={() => navigate('/app/trade-ins')}
              style={{ cursor: 'pointer' }}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && navigate('/app/trade-ins')}
            >
              <Card>
                <BlockStack gap="200">
                  <Text as="h3" variant={isMobile ? "headingSm" : "headingMd"}>Trade-Ins</Text>
                  <Text as="p" variant={isMobile ? "headingLg" : "heading2xl"}>{stats?.completed_trade_ins || 0}</Text>
                  <Badge tone="attention">{String(`${stats?.pending_trade_ins ?? 0} pending`)}</Badge>
                </BlockStack>
              </Card>
            </div>

            <div
              onClick={() => navigate('/app/trade-ins')}
              style={{ cursor: 'pointer' }}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && navigate('/app/trade-ins')}
            >
              <Card>
                <BlockStack gap="200">
                  <Text as="h3" variant={isMobile ? "headingSm" : "headingMd"}>Total Value</Text>
                  <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    <Text as="p" variant={(isMobile || isTablet) ? "headingLg" : "heading2xl"}>
                      {formatCurrency(stats?.total_trade_in_value || 0)}
                    </Text>
                  </div>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Trade-in value processed
                  </Text>
                </BlockStack>
              </Card>
            </div>

            <div
              onClick={() => navigate('/app/members')}
              style={{ cursor: 'pointer' }}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && navigate('/app/members')}
            >
              <Card>
                <BlockStack gap="200">
                  <Text as="h3" variant={isMobile ? "headingSm" : "headingMd"}>Credits Issued</Text>
                  <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    <Text as="p" variant={(isMobile || isTablet) ? "headingLg" : "heading2xl"}>
                      {formatCurrency(stats?.total_credits_issued || 0)}
                    </Text>
                  </div>
                  <Text as="p" variant="bodySm" tone="subdued">
                    Store credit distributed
                  </Text>
                </BlockStack>
              </Card>
            </div>
          </InlineGrid>
        </Layout.Section>

        {/* Usage & Plan */}
        <Layout.Section variant="oneThird">
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between">
                <Text as="h3" variant="headingMd">Current Plan</Text>
                <Badge tone="info">{String(stats?.subscription?.plan || 'Free')}</Badge>
              </InlineStack>

              <div
                onClick={() => navigate('/app/members')}
                style={{ cursor: 'pointer' }}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && navigate('/app/members')}
              >
                <BlockStack gap="200">
                  <InlineStack align="space-between">
                    <Text as="span" variant="bodySm">Members</Text>
                    <Text as="span" variant="bodySm">
                      {stats?.subscription?.usage?.members?.current || 0} /{' '}
                      {stats?.subscription?.usage?.members?.limit === null
                        ? '∞'
                        : stats?.subscription?.usage?.members?.limit}
                    </Text>
                  </InlineStack>
                  <ProgressBar
                    progress={stats?.subscription?.usage?.members?.percentage || 0}
                    size="small"
                    tone={
                      (stats?.subscription?.usage?.members?.percentage || 0) > 90
                        ? 'critical'
                        : (stats?.subscription?.usage?.members?.percentage || 0) > 75
                        ? 'highlight'
                        : 'success'
                    }
                  />
                </BlockStack>
              </div>

              <div
                onClick={() => navigate('/app/tiers')}
                style={{ cursor: 'pointer' }}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && navigate('/app/tiers')}
              >
                <BlockStack gap="200">
                  <InlineStack align="space-between">
                    <Text as="span" variant="bodySm">Tiers</Text>
                    <Text as="span" variant="bodySm">
                      {stats?.subscription?.usage?.tiers?.current || 0} /{' '}
                      {stats?.subscription?.usage?.tiers?.limit === null
                        ? '∞'
                        : stats?.subscription?.usage?.tiers?.limit}
                    </Text>
                  </InlineStack>
                  <ProgressBar
                    progress={stats?.subscription?.usage?.tiers?.percentage || 0}
                    size="small"
                  />
                </BlockStack>
              </div>
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Recent Activity */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text as="h3" variant="headingMd">Recent Activity</Text>

              {activityLoading ? (
                <Spinner size="small" />
              ) : activity && activity.length > 0 ? (
                <DataTable
                  columnContentTypes={['text', 'text', 'text', 'numeric']}
                  headings={['Type', 'Member', 'Description', 'Amount']}
                  rows={activity.slice(0, 5).filter(item => item && item.id != null).map((item) => [
                    <Badge
                      key={item.id}
                      tone={item.type === 'trade_in' ? 'success' : 'info'}
                    >
                      {String(item.type === 'trade_in' ? 'Trade-In' : (item.type || 'Activity'))}
                    </Badge>,
                    item.member_name || 'Unknown',
                    item.description || '-',
                    formatCurrency(item.amount || 0),
                  ])}
                />
              ) : (
                <EmptyState
                  heading="No activity yet"
                  image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                >
                  <p>
                    Activity will appear here once members start using the
                    trade-in program.
                  </p>
                </EmptyState>
              )}
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Build version for debugging cache issues */}
        <Layout.Section>
          <Box paddingBlockStart="400">
            <Text as="p" variant="bodySm" tone="subdued" alignment="center">
              Build: 2026-01-10-v1
            </Text>
          </Box>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
