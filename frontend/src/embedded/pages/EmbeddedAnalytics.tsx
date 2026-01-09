/**
 * TradeUp Analytics Dashboard - Shopify Embedded Version
 *
 * Comprehensive analytics and reporting:
 * - Member growth trends
 * - Trade-in volume and value
 * - Store credit metrics
 * - Tier distribution
 * - Revenue insights
 */
import { useState } from 'react';
import {
  Page,
  Layout,
  Card,
  Text,
  InlineStack,
  BlockStack,
  Badge,
  Select,
  Spinner,
  Banner,
  Box,
  ProgressBar,
  Divider,
  DataTable,
} from '@shopify/polaris';
import { useQuery } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface AnalyticsProps {
  shop: string | null;
}

interface AnalyticsData {
  overview: {
    total_members: number;
    active_members: number;
    new_members_this_month: number;
    member_growth_pct: number;
    total_trade_ins: number;
    trade_ins_this_month: number;
    trade_in_value_this_month: number;
    total_store_credit_issued: number;
    store_credit_this_month: number;
    total_referrals: number;
    referrals_this_month: number;
  };
  tier_distribution: Array<{
    tier_name: string;
    member_count: number;
    percentage: number;
    color: string;
  }>;
  monthly_trends: Array<{
    month: string;
    new_members: number;
    trade_ins: number;
    credit_issued: number;
    referrals: number;
  }>;
  top_members: Array<{
    id: number;
    member_number: string;
    name: string;
    total_trade_ins: number;
    total_credit_earned: number;
    referral_count: number;
  }>;
  category_performance: Array<{
    category_name: string;
    trade_in_count: number;
    total_value: number;
    avg_value: number;
  }>;
}

async function fetchAnalytics(shop: string | null, period: string): Promise<AnalyticsData> {
  const response = await authFetch(
    `${getApiUrl()}/analytics/dashboard?period=${period}`,
    shop
  );
  if (!response.ok) throw new Error('Failed to fetch analytics');
  return response.json();
}

export function EmbeddedAnalytics({ shop }: AnalyticsProps) {
  const [period, setPeriod] = useState('30');

  const { data: analytics, isLoading, error } = useQuery({
    queryKey: ['analytics', shop, period],
    queryFn: () => fetchAnalytics(shop, period),
    enabled: !!shop,
  });

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat('en-US').format(num);
  };

  const formatPercent = (num: number) => {
    const sign = num >= 0 ? '+' : '';
    return `${sign}${num.toFixed(1)}%`;
  };

  if (!shop) {
    return (
      <Page title="Analytics">
        <Banner tone="warning">
          <p>No shop connected. Please install the app from the Shopify App Store.</p>
        </Banner>
      </Page>
    );
  }

  if (isLoading) {
    return (
      <Page title="Analytics">
        <Box padding="1600">
          <InlineStack align="center">
            <Spinner size="large" />
          </InlineStack>
        </Box>
      </Page>
    );
  }

  if (error) {
    return (
      <Page title="Analytics">
        <Banner tone="critical">
          <p>Failed to load analytics data. Please try refreshing the page.</p>
        </Banner>
      </Page>
    );
  }

  // Calculate derived metrics
  const overview = analytics?.overview || {
    total_members: 0,
    active_members: 0,
    new_members_this_month: 0,
    member_growth_pct: 0,
    total_trade_ins: 0,
    trade_ins_this_month: 0,
    trade_in_value_this_month: 0,
    total_store_credit_issued: 0,
    store_credit_this_month: 0,
    total_referrals: 0,
    referrals_this_month: 0,
  };

  const tierDistribution = analytics?.tier_distribution || [];
  const topMembers = analytics?.top_members || [];
  const categoryPerformance = analytics?.category_performance || [];

  const handleExport = (exportType: string = 'summary') => {
    // Build export URL with auth params
    const params = new URLSearchParams();
    params.set('type', exportType);
    params.set('period', period);
    if (shop) params.set('shop', shop);

    // Open in new tab to trigger download
    window.open(`${getApiUrl()}/analytics/export?${params.toString()}`, '_blank');
  };

  return (
    <Page
      title="Analytics"
      subtitle="Track your loyalty program performance"
      primaryAction={{
        content: 'Export Report',
        onAction: () => handleExport('summary'),
      }}
      secondaryActions={[
        { content: 'Export Members', onAction: () => handleExport('members') },
        { content: 'Export Trade-Ins', onAction: () => handleExport('trade_ins') },
        { content: 'Export Credits', onAction: () => handleExport('credits') },
      ]}
    >
      <Layout>
        {/* Period Selector */}
        <Layout.Section>
          <Card>
            <InlineStack align="space-between" blockAlign="center">
              <Text as="h3" variant="headingMd">Reporting Period</Text>
              <Select
                label=""
                labelHidden
                options={[
                  { label: 'Last 7 days', value: '7' },
                  { label: 'Last 30 days', value: '30' },
                  { label: 'Last 90 days', value: '90' },
                  { label: 'Last 12 months', value: '365' },
                  { label: 'All time', value: 'all' },
                ]}
                value={period}
                onChange={setPeriod}
              />
            </InlineStack>
          </Card>
        </Layout.Section>

        {/* Key Metrics Grid */}
        <Layout.Section>
          <InlineStack gap="400" wrap={false}>
            {/* Members Card */}
            <Card>
              <BlockStack gap="300">
                <InlineStack align="space-between" blockAlign="center">
                  <Text as="h3" variant="headingMd">Members</Text>
                  <Badge tone={overview.member_growth_pct >= 0 ? 'success' : 'critical'}>
                    {formatPercent(overview.member_growth_pct)}
                  </Badge>
                </InlineStack>
                <Text as="p" variant="heading2xl">{formatNumber(overview.total_members)}</Text>
                <Divider />
                <InlineStack gap="400">
                  <BlockStack gap="050">
                    <Text as="span" variant="bodySm" tone="subdued">Active</Text>
                    <Text as="span" variant="bodyMd" fontWeight="semibold">
                      {formatNumber(overview.active_members)}
                    </Text>
                  </BlockStack>
                  <BlockStack gap="050">
                    <Text as="span" variant="bodySm" tone="subdued">New This Month</Text>
                    <Text as="span" variant="bodyMd" fontWeight="semibold">
                      {formatNumber(overview.new_members_this_month)}
                    </Text>
                  </BlockStack>
                </InlineStack>
              </BlockStack>
            </Card>

            {/* Trade-Ins Card */}
            <Card>
              <BlockStack gap="300">
                <InlineStack align="space-between" blockAlign="center">
                  <Text as="h3" variant="headingMd">Trade-Ins</Text>
                  <Badge tone="info">This Period</Badge>
                </InlineStack>
                <Text as="p" variant="heading2xl">{formatNumber(overview.trade_ins_this_month)}</Text>
                <Divider />
                <InlineStack gap="400">
                  <BlockStack gap="050">
                    <Text as="span" variant="bodySm" tone="subdued">Total Value</Text>
                    <Text as="span" variant="bodyMd" fontWeight="semibold">
                      {formatCurrency(overview.trade_in_value_this_month)}
                    </Text>
                  </BlockStack>
                  <BlockStack gap="050">
                    <Text as="span" variant="bodySm" tone="subdued">All Time</Text>
                    <Text as="span" variant="bodyMd" fontWeight="semibold">
                      {formatNumber(overview.total_trade_ins)}
                    </Text>
                  </BlockStack>
                </InlineStack>
              </BlockStack>
            </Card>

            {/* Store Credit Card */}
            <Card>
              <BlockStack gap="300">
                <InlineStack align="space-between" blockAlign="center">
                  <Text as="h3" variant="headingMd">Store Credit</Text>
                  <Badge tone="success">Issued</Badge>
                </InlineStack>
                <Text as="p" variant="heading2xl">
                  {formatCurrency(overview.store_credit_this_month)}
                </Text>
                <Divider />
                <InlineStack gap="400">
                  <BlockStack gap="050">
                    <Text as="span" variant="bodySm" tone="subdued">This Month</Text>
                    <Text as="span" variant="bodyMd" fontWeight="semibold">
                      {formatCurrency(overview.store_credit_this_month)}
                    </Text>
                  </BlockStack>
                  <BlockStack gap="050">
                    <Text as="span" variant="bodySm" tone="subdued">All Time</Text>
                    <Text as="span" variant="bodyMd" fontWeight="semibold">
                      {formatCurrency(overview.total_store_credit_issued)}
                    </Text>
                  </BlockStack>
                </InlineStack>
              </BlockStack>
            </Card>

            {/* Referrals Card */}
            <Card>
              <BlockStack gap="300">
                <InlineStack align="space-between" blockAlign="center">
                  <Text as="h3" variant="headingMd">Referrals</Text>
                  <Badge>Word of Mouth</Badge>
                </InlineStack>
                <Text as="p" variant="heading2xl">{formatNumber(overview.referrals_this_month)}</Text>
                <Divider />
                <InlineStack gap="400">
                  <BlockStack gap="050">
                    <Text as="span" variant="bodySm" tone="subdued">This Month</Text>
                    <Text as="span" variant="bodyMd" fontWeight="semibold">
                      {formatNumber(overview.referrals_this_month)}
                    </Text>
                  </BlockStack>
                  <BlockStack gap="050">
                    <Text as="span" variant="bodySm" tone="subdued">All Time</Text>
                    <Text as="span" variant="bodyMd" fontWeight="semibold">
                      {formatNumber(overview.total_referrals)}
                    </Text>
                  </BlockStack>
                </InlineStack>
              </BlockStack>
            </Card>
          </InlineStack>
        </Layout.Section>

        {/* Tier Distribution */}
        <Layout.Section variant="oneHalf">
          <Card>
            <BlockStack gap="400">
              <Text as="h3" variant="headingMd">Tier Distribution</Text>
              {tierDistribution.length > 0 ? (
                <BlockStack gap="300">
                  {tierDistribution.map((tier) => (
                    <BlockStack key={tier.tier_name} gap="100">
                      <InlineStack align="space-between">
                        <Text as="span" variant="bodyMd">{tier.tier_name}</Text>
                        <Text as="span" variant="bodyMd" fontWeight="semibold">
                          {formatNumber(tier.member_count)} ({(tier.percentage || 0).toFixed(1)}%)
                        </Text>
                      </InlineStack>
                      <ProgressBar
                        progress={tier.percentage}
                        size="small"
                        tone="primary"
                      />
                    </BlockStack>
                  ))}
                </BlockStack>
              ) : (
                <Text as="p" tone="subdued">No tier data available</Text>
              )}
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Category Performance */}
        <Layout.Section variant="oneHalf">
          <Card>
            <BlockStack gap="400">
              <Text as="h3" variant="headingMd">Category Performance</Text>
              {categoryPerformance.length > 0 ? (
                <DataTable
                  columnContentTypes={['text', 'numeric', 'numeric', 'numeric']}
                  headings={['Category', 'Trade-Ins', 'Total Value', 'Avg Value']}
                  rows={categoryPerformance.slice(0, 5).map((cat) => [
                    cat.category_name,
                    formatNumber(cat.trade_in_count),
                    formatCurrency(cat.total_value),
                    formatCurrency(cat.avg_value),
                  ])}
                />
              ) : (
                <Text as="p" tone="subdued">No category data available</Text>
              )}
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Top Members */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between" blockAlign="center">
                <Text as="h3" variant="headingMd">Top Performing Members</Text>
                <Badge tone="success">VIPs</Badge>
              </InlineStack>
              {topMembers.length > 0 ? (
                <DataTable
                  columnContentTypes={['text', 'numeric', 'numeric', 'numeric']}
                  headings={['Member', 'Trade-Ins', 'Credit Earned', 'Referrals']}
                  rows={topMembers.slice(0, 10).map((member) => [
                    <BlockStack key={member.id} gap="050">
                      <Text as="span" variant="bodyMd" fontWeight="semibold">
                        {member.name || member.member_number}
                      </Text>
                      <Text as="span" variant="bodySm" tone="subdued">
                        {member.member_number}
                      </Text>
                    </BlockStack>,
                    formatNumber(member.total_trade_ins),
                    formatCurrency(member.total_credit_earned),
                    formatNumber(member.referral_count),
                  ])}
                />
              ) : (
                <Text as="p" tone="subdued">No member data available</Text>
              )}
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Quick Insights */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text as="h3" variant="headingMd">Quick Insights</Text>
              <InlineStack gap="400" wrap>
                <Card>
                  <BlockStack gap="200">
                    <Text as="span" variant="bodySm" tone="subdued">Avg Trade-In Value</Text>
                    <Text as="span" variant="headingLg">
                      {overview.trade_ins_this_month > 0
                        ? formatCurrency(overview.trade_in_value_this_month / overview.trade_ins_this_month)
                        : '$0.00'}
                    </Text>
                  </BlockStack>
                </Card>
                <Card>
                  <BlockStack gap="200">
                    <Text as="span" variant="bodySm" tone="subdued">Member Retention</Text>
                    <Text as="span" variant="headingLg">
                      {overview.total_members > 0
                        ? `${((overview.active_members / overview.total_members) * 100).toFixed(1)}%`
                        : '0%'}
                    </Text>
                  </BlockStack>
                </Card>
                <Card>
                  <BlockStack gap="200">
                    <Text as="span" variant="bodySm" tone="subdued">Credit per Member</Text>
                    <Text as="span" variant="headingLg">
                      {overview.total_members > 0
                        ? formatCurrency(overview.total_store_credit_issued / overview.total_members)
                        : '$0.00'}
                    </Text>
                  </BlockStack>
                </Card>
                <Card>
                  <BlockStack gap="200">
                    <Text as="span" variant="bodySm" tone="subdued">Referral Rate</Text>
                    <Text as="span" variant="headingLg">
                      {overview.total_members > 0
                        ? `${((overview.total_referrals / overview.total_members) * 100).toFixed(1)}%`
                        : '0%'}
                    </Text>
                  </BlockStack>
                </Card>
              </InlineStack>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
