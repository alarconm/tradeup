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
} from '@shopify/polaris';
import { useQuery } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

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

export function EmbeddedDashboard({ shop }: DashboardProps) {
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
            <InlineStack gap="400" wrap={false}>
              {[1, 2, 3, 4].map((i) => (
                <Card key={i}>
                  <BlockStack gap="200">
                    <Box background="bg-surface-secondary" borderRadius="100" minHeight="20px" />
                    <Box background="bg-surface-secondary" borderRadius="100" minHeight="40px" />
                    <Box background="bg-surface-secondary" borderRadius="100" minHeight="20px" maxWidth="60px" />
                  </BlockStack>
                </Card>
              ))}
            </InlineStack>
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

        {/* Key Metrics */}
        <Layout.Section>
          <InlineStack gap="400" wrap={false}>
            <Card>
              <BlockStack gap="200">
                <Text as="h3" variant="headingMd">Total Members</Text>
                <Text as="p" variant="heading2xl">{stats?.total_members || 0}</Text>
                <Badge tone="success">{`${stats?.active_members || 0} active`}</Badge>
              </BlockStack>
            </Card>

            <Card>
              <BlockStack gap="200">
                <Text as="h3" variant="headingMd">Trade-Ins</Text>
                <Text as="p" variant="heading2xl">{stats?.completed_trade_ins || 0}</Text>
                <Badge tone="attention">{`${stats?.pending_trade_ins || 0} pending`}</Badge>
              </BlockStack>
            </Card>

            <Card>
              <BlockStack gap="200">
                <Text as="h3" variant="headingMd">Total Value</Text>
                <Text as="p" variant="heading2xl">
                  {formatCurrency(stats?.total_trade_in_value || 0)}
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  Trade-in value processed
                </Text>
              </BlockStack>
            </Card>

            <Card>
              <BlockStack gap="200">
                <Text as="h3" variant="headingMd">Credits Issued</Text>
                <Text as="p" variant="heading2xl">
                  {formatCurrency(stats?.total_credits_issued || 0)}
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">
                  Store credit distributed
                </Text>
              </BlockStack>
            </Card>
          </InlineStack>
        </Layout.Section>

        {/* Usage & Plan */}
        <Layout.Section variant="oneThird">
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between">
                <Text as="h3" variant="headingMd">Current Plan</Text>
                <Badge tone="info">{stats?.subscription?.plan || 'Free'}</Badge>
              </InlineStack>

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
                      {item.type === 'trade_in' ? 'Trade-In' : (item.type || 'Activity')}
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
      </Layout>
    </Page>
  );
}
