/**
 * Review Tracking Dashboard - Shopify Embedded Version
 *
 * Internal dashboard to track review collection progress.
 *
 * Story: RC-010 - Build review tracking dashboard
 *
 * Displays:
 * - Total reviews collected
 * - Average rating (placeholder - Shopify API doesn't provide this)
 * - Prompt-to-review conversion rate
 * - Top reviewers list
 * - Review velocity chart (reviews per week)
 */
import { useState, useEffect } from 'react';
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
  InlineGrid,
  Icon,
} from '@shopify/polaris';
import {
  StarFilledIcon,
  ChartVerticalFilledIcon,
  PersonFilledIcon,
  EmailIcon,
  ChatIcon,
} from '@shopify/polaris-icons';

// Hook to detect mobile viewport
function useResponsive() {
  const [screenSize, setScreenSize] = useState(() => {
    if (typeof window === 'undefined') return { isSmallMobile: false, isMobile: false, isTablet: false };
    const width = window.innerWidth;
    return {
      isSmallMobile: width < 480,
      isMobile: width < 768,
      isTablet: width < 1024,
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

import { useQuery } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface ReviewDashboardProps {
  shop: string | null;
}

interface TopReviewer {
  id: number;
  name: string;
  member_number: string;
  joined_at: string | null;
  total_trade_ins: number;
}

interface WeeklyVelocity {
  week: string;
  reviews: number;
}

interface InAppMetrics {
  total_impressions: number;
  clicked_count: number;
  dismissed_count: number;
  reminded_later_count: number;
  no_response_count: number;
  click_rate: number;
  response_rate: number;
}

interface SupportMetrics {
  total_sent: number;
  total_opened: number;
  total_clicked: number;
  open_rate: number;
  click_rate: number;
  click_to_open_rate: number;
}

interface DashboardMetrics {
  total_reviews_collected: number;
  average_rating: number;
  prompt_to_review_conversion_rate: number;
  top_reviewers: TopReviewer[];
  weekly_velocity: WeeklyVelocity[];
  overview: {
    total_prompts_sent: number;
    total_review_clicks: number;
    conversion_rate: number;
    period_days: number | string;
  };
  in_app_prompts: InAppMetrics;
  support_review_emails: SupportMetrics;
}

interface DashboardResponse {
  success: boolean;
  metrics: DashboardMetrics;
}

async function fetchDashboardMetrics(shop: string | null, days: string): Promise<DashboardMetrics> {
  const response = await authFetch(
    `${getApiUrl()}/review-dashboard/metrics?days=${days}`,
    shop
  );
  if (!response.ok) throw new Error('Failed to fetch review metrics');
  const data: DashboardResponse = await response.json();
  return data.metrics;
}

export function EmbeddedReviewDashboard({ shop }: ReviewDashboardProps) {
  const { isSmallMobile, isMobile } = useResponsive();
  const [period, setPeriod] = useState('30');

  const { data: metrics, isLoading, error } = useQuery({
    queryKey: ['review-dashboard', shop, period],
    queryFn: () => fetchDashboardMetrics(shop, period),
    enabled: !!shop,
  });

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat('en-US').format(num);
  };

  const formatPercent = (num: number) => {
    return `${num.toFixed(1)}%`;
  };

  if (!shop) {
    return (
      <Page title="Review Tracking">
        <Banner tone="warning">
          <p>No shop connected. Please install the app from the Shopify App Store.</p>
        </Banner>
      </Page>
    );
  }

  if (isLoading) {
    return (
      <Page title="Review Tracking">
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
      <Page title="Review Tracking">
        <Banner tone="critical">
          <p>Failed to load review metrics. Please try refreshing the page.</p>
        </Banner>
      </Page>
    );
  }

  // Default values if metrics not loaded
  const overview = metrics?.overview || {
    total_prompts_sent: 0,
    total_review_clicks: 0,
    conversion_rate: 0,
    period_days: 30,
  };

  const inAppPrompts = metrics?.in_app_prompts || {
    total_impressions: 0,
    clicked_count: 0,
    dismissed_count: 0,
    reminded_later_count: 0,
    no_response_count: 0,
    click_rate: 0,
    response_rate: 0,
  };

  const supportEmails = metrics?.support_review_emails || {
    total_sent: 0,
    total_opened: 0,
    total_clicked: 0,
    open_rate: 0,
    click_rate: 0,
    click_to_open_rate: 0,
  };

  const topReviewers = metrics?.top_reviewers || [];
  const weeklyVelocity = metrics?.weekly_velocity || [];

  // Calculate max for velocity chart scaling
  const maxVelocity = Math.max(...weeklyVelocity.map(w => w.reviews), 1);

  return (
    <Page
      title="Review Tracking"
      subtitle="Monitor your app review collection progress"
      backAction={{ content: 'Settings', url: '/app/settings' }}
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
                  { label: 'All time', value: '0' },
                ]}
                value={period}
                onChange={setPeriod}
              />
            </InlineStack>
          </Card>
        </Layout.Section>

        {/* Key Metrics Grid - Acceptance Criteria */}
        <Layout.Section>
          <InlineGrid columns={isSmallMobile ? 1 : isMobile ? 2 : 4} gap={isMobile ? "300" : "400"}>
            {/* Total Reviews Collected */}
            <Card>
              <BlockStack gap="300">
                <InlineStack align="space-between" blockAlign="center">
                  <Text as="h3" variant="headingMd">Reviews Collected</Text>
                  <Icon source={StarFilledIcon} tone="warning" />
                </InlineStack>
                <Text as="p" variant="heading2xl">
                  {formatNumber(metrics?.total_reviews_collected || 0)}
                </Text>
                <Divider />
                <Text as="span" variant="bodySm" tone="subdued">
                  Total clicks to review page
                </Text>
              </BlockStack>
            </Card>

            {/* Average Rating */}
            <Card>
              <BlockStack gap="300">
                <InlineStack align="space-between" blockAlign="center">
                  <Text as="h3" variant="headingMd">Average Rating</Text>
                  <Badge tone="success">Estimated</Badge>
                </InlineStack>
                <Text as="p" variant="heading2xl">
                  {(metrics?.average_rating || 4.8).toFixed(1)}
                </Text>
                <Divider />
                <Text as="span" variant="bodySm" tone="subdued">
                  Based on industry average for engaged users
                </Text>
              </BlockStack>
            </Card>

            {/* Conversion Rate */}
            <Card>
              <BlockStack gap="300">
                <InlineStack align="space-between" blockAlign="center">
                  <Text as="h3" variant="headingMd">Conversion Rate</Text>
                  <Icon source={ChartVerticalFilledIcon} tone="info" />
                </InlineStack>
                <Text as="p" variant="heading2xl">
                  {formatPercent(metrics?.prompt_to_review_conversion_rate || 0)}
                </Text>
                <Divider />
                <Text as="span" variant="bodySm" tone="subdued">
                  Prompts to review clicks
                </Text>
              </BlockStack>
            </Card>

            {/* Total Prompts */}
            <Card>
              <BlockStack gap="300">
                <InlineStack align="space-between" blockAlign="center">
                  <Text as="h3" variant="headingMd">Total Prompts</Text>
                  <Badge>Combined</Badge>
                </InlineStack>
                <Text as="p" variant="heading2xl">
                  {formatNumber(overview.total_prompts_sent)}
                </Text>
                <Divider />
                <Text as="span" variant="bodySm" tone="subdued">
                  In-app + email prompts sent
                </Text>
              </BlockStack>
            </Card>
          </InlineGrid>
        </Layout.Section>

        {/* Review Velocity Chart */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between" blockAlign="center">
                <Text as="h3" variant="headingMd">Review Velocity (Reviews per Week)</Text>
                <Badge tone="info">Trend</Badge>
              </InlineStack>
              {weeklyVelocity.length > 0 ? (
                <BlockStack gap="200">
                  {weeklyVelocity.slice(-8).map((week) => (
                    <BlockStack key={week.week} gap="100">
                      <InlineStack align="space-between">
                        <Text as="span" variant="bodySm">{week.week}</Text>
                        <Text as="span" variant="bodySm" fontWeight="semibold">
                          {formatNumber(week.reviews)} reviews
                        </Text>
                      </InlineStack>
                      <ProgressBar
                        progress={(week.reviews / maxVelocity) * 100}
                        size="small"
                        tone="primary"
                      />
                    </BlockStack>
                  ))}
                </BlockStack>
              ) : (
                <Text as="p" tone="subdued">No review data available for this period</Text>
              )}
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Channel Breakdown */}
        <Layout.Section variant="oneHalf">
          <Card>
            <BlockStack gap="400">
              <InlineStack gap="200" blockAlign="center">
                <Icon source={ChatIcon} tone="base" />
                <Text as="h3" variant="headingMd">In-App Prompts</Text>
              </InlineStack>
              <Divider />
              <BlockStack gap="200">
                <InlineStack align="space-between">
                  <Text as="span" variant="bodyMd">Total Impressions</Text>
                  <Text as="span" variant="bodyMd" fontWeight="semibold">
                    {formatNumber(inAppPrompts.total_impressions)}
                  </Text>
                </InlineStack>
                <InlineStack align="space-between">
                  <Text as="span" variant="bodyMd">Clicked (Rate Now)</Text>
                  <Text as="span" variant="bodyMd" fontWeight="semibold">
                    {formatNumber(inAppPrompts.clicked_count)} ({formatPercent(inAppPrompts.click_rate)})
                  </Text>
                </InlineStack>
                <InlineStack align="space-between">
                  <Text as="span" variant="bodyMd">Dismissed</Text>
                  <Text as="span" variant="bodyMd" fontWeight="semibold">
                    {formatNumber(inAppPrompts.dismissed_count)}
                  </Text>
                </InlineStack>
                <InlineStack align="space-between">
                  <Text as="span" variant="bodyMd">Remind Later</Text>
                  <Text as="span" variant="bodyMd" fontWeight="semibold">
                    {formatNumber(inAppPrompts.reminded_later_count)}
                  </Text>
                </InlineStack>
                <InlineStack align="space-between">
                  <Text as="span" variant="bodyMd">Response Rate</Text>
                  <Text as="span" variant="bodyMd" fontWeight="semibold">
                    {formatPercent(inAppPrompts.response_rate)}
                  </Text>
                </InlineStack>
              </BlockStack>
            </BlockStack>
          </Card>
        </Layout.Section>

        <Layout.Section variant="oneHalf">
          <Card>
            <BlockStack gap="400">
              <InlineStack gap="200" blockAlign="center">
                <Icon source={EmailIcon} tone="base" />
                <Text as="h3" variant="headingMd">Post-Support Emails</Text>
              </InlineStack>
              <Divider />
              <BlockStack gap="200">
                <InlineStack align="space-between">
                  <Text as="span" variant="bodyMd">Total Sent</Text>
                  <Text as="span" variant="bodyMd" fontWeight="semibold">
                    {formatNumber(supportEmails.total_sent)}
                  </Text>
                </InlineStack>
                <InlineStack align="space-between">
                  <Text as="span" variant="bodyMd">Opened</Text>
                  <Text as="span" variant="bodyMd" fontWeight="semibold">
                    {formatNumber(supportEmails.total_opened)} ({formatPercent(supportEmails.open_rate)})
                  </Text>
                </InlineStack>
                <InlineStack align="space-between">
                  <Text as="span" variant="bodyMd">Clicked</Text>
                  <Text as="span" variant="bodyMd" fontWeight="semibold">
                    {formatNumber(supportEmails.total_clicked)} ({formatPercent(supportEmails.click_rate)})
                  </Text>
                </InlineStack>
                <InlineStack align="space-between">
                  <Text as="span" variant="bodyMd">Click-to-Open Rate</Text>
                  <Text as="span" variant="bodyMd" fontWeight="semibold">
                    {formatPercent(supportEmails.click_to_open_rate)}
                  </Text>
                </InlineStack>
              </BlockStack>
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Top Reviewers */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between" blockAlign="center">
                <InlineStack gap="200" blockAlign="center">
                  <Icon source={PersonFilledIcon} tone="base" />
                  <Text as="h3" variant="headingMd">Top Engaged Members</Text>
                </InlineStack>
                <Badge tone="success">Most Active</Badge>
              </InlineStack>
              {topReviewers.length > 0 ? (
                <DataTable
                  columnContentTypes={['text', 'text', 'numeric']}
                  headings={['Member', 'Member #', 'Trade-Ins']}
                  rows={topReviewers.slice(0, 10).map((reviewer) => [
                    reviewer.name,
                    reviewer.member_number || '-',
                    formatNumber(reviewer.total_trade_ins),
                  ])}
                />
              ) : (
                <Text as="p" tone="subdued">No member data available for this period</Text>
              )}
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Note about limitations */}
        <Layout.Section>
          <Banner tone="info">
            <p>
              <strong>Note:</strong> The Shopify App Store API does not provide access to actual review counts or ratings.
              "Reviews Collected" represents clicks to the review page. "Average Rating" is an estimate based on
              industry benchmarks for engaged users (typically 4.5-5.0 stars).
            </p>
          </Banner>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
