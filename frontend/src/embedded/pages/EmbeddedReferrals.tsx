/**
 * TradeUp Referral Program Page - Shopify Embedded Version
 *
 * Comprehensive referral program management:
 * - View referral statistics
 * - Top referrers leaderboard
 * - Recent referral activity
 * - Configure referral rewards
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
  DataTable,
  EmptyState,
  Spinner,
  Banner,
  Box,
  Button,
  Modal,
  TextField,
  Select,
  InlineGrid,
} from '@shopify/polaris';

// Hook to detect mobile viewport
function useIsMobile(breakpoint: number = 768) {
  const [isMobile, setIsMobile] = useState(
    typeof window !== 'undefined' ? window.innerWidth < breakpoint : false
  );

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < breakpoint);
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, [breakpoint]);

  return isMobile;
}
import { useQuery } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface ReferralsProps {
  shop: string | null;
}

interface ReferralStats {
  total_referrals: number;
  monthly_referrals: number;
  total_credit_issued: number;
  top_referrers: TopReferrer[];
  recent_referrals: RecentReferral[];
}

interface TopReferrer {
  id: number;
  member_number: string;
  name: string;
  email: string;
  referral_code: string;
  referral_count: number;
  referral_earnings: number;
}

interface RecentReferral {
  id: number;
  member_number: string;
  name: string;
  referred_by: string;
  created_at: string;
}

interface ReferralConfig {
  config: {
    referrer_credit: number;
    referee_credit: number;
    grant_on_signup: boolean;
    require_first_purchase: boolean;
    max_referrals_per_month: number;
  };
}

async function fetchReferralStats(shop: string | null): Promise<ReferralStats> {
  const response = await authFetch(`${getApiUrl()}/referrals/admin/stats`, shop);
  if (!response.ok) throw new Error('Failed to fetch referral stats');
  const data = await response.json();
  // Map backend response to expected frontend format
  return {
    total_referrals: data.stats?.total_referrals || 0,
    monthly_referrals: data.stats?.total_referrals || 0, // Backend doesn't track monthly separately
    total_credit_issued: data.stats?.total_credit_issued || 0,
    top_referrers: data.top_referrers || [],
    recent_referrals: data.recent_referrals || [],
  };
}

async function fetchReferralConfig(shop: string | null): Promise<ReferralConfig> {
  const response = await authFetch(`${getApiUrl()}/referrals/admin/config`, shop);
  if (!response.ok) throw new Error('Failed to fetch referral config');
  return response.json();
}

export function EmbeddedReferrals({ shop }: ReferralsProps) {
  const isMobile = useIsMobile();
  const [configModalOpen, setConfigModalOpen] = useState(false);

  const { data: stats, isLoading: statsLoading, error: statsError } = useQuery({
    queryKey: ['referral-stats', shop],
    queryFn: () => fetchReferralStats(shop),
    enabled: !!shop,
  });

  const { data: config } = useQuery({
    queryKey: ['referral-config', shop],
    queryFn: () => fetchReferralConfig(shop),
    enabled: !!shop,
  });

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  if (!shop) {
    return (
      <Page title="Referral Program">
        <Banner tone="warning">
          <p>No shop connected. Please install the app from the Shopify App Store.</p>
        </Banner>
      </Page>
    );
  }

  if (statsLoading) {
    return (
      <Page title="Referral Program">
        <Box padding="1600">
          <InlineStack align="center">
            <Spinner size="large" />
          </InlineStack>
        </Box>
      </Page>
    );
  }

  if (statsError) {
    return (
      <Page title="Referral Program">
        <Banner tone="critical">
          <p>Failed to load referral data. Please try refreshing the page.</p>
        </Banner>
      </Page>
    );
  }

  return (
    <Page
      title="Referral Program"
      subtitle="Grow your membership through word-of-mouth"
      primaryAction={{
        content: 'Configure Rewards',
        onAction: () => setConfigModalOpen(true),
      }}
    >
      <Layout>
        {/* Key Metrics */}
        <Layout.Section>
          <InlineGrid columns={isMobile ? 1 : { xs: 1, sm: 2, md: 2, lg: 4 }} gap="400">
            <Card>
              <BlockStack gap="200">
                <Text as="h3" variant="headingMd">Total Referrals</Text>
                <Text as="p" variant="heading2xl">{stats?.total_referrals || 0}</Text>
                <Text as="p" variant="bodySm" tone="subdued">All-time successful referrals</Text>
              </BlockStack>
            </Card>

            <Card>
              <BlockStack gap="200">
                <Text as="h3" variant="headingMd">This Month</Text>
                <Text as="p" variant="heading2xl">{stats?.monthly_referrals || 0}</Text>
                <Badge tone="success">
                  {String(stats?.monthly_referrals && stats?.total_referrals
                    ? `${Math.round((stats.monthly_referrals / stats.total_referrals) * 100)}% of total`
                    : '0%'
                  )}
                </Badge>
              </BlockStack>
            </Card>

            <Card>
              <BlockStack gap="200">
                <Text as="h3" variant="headingMd">Credits Issued</Text>
                <Text as="p" variant="heading2xl">
                  {formatCurrency(stats?.total_credit_issued || 0)}
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">Total referral rewards</Text>
              </BlockStack>
            </Card>

            <Card>
              <BlockStack gap="200">
                <Text as="h3" variant="headingMd">Avg. per Referrer</Text>
                <Text as="p" variant="heading2xl">
                  {stats?.top_referrers && stats.top_referrers.length > 0
                    ? (stats.top_referrers.reduce((sum, r) => sum + r.referral_count, 0) / stats.top_referrers.length).toFixed(1)
                    : '0'
                  }
                </Text>
                <Text as="p" variant="bodySm" tone="subdued">Referrals per active referrer</Text>
              </BlockStack>
            </Card>
          </InlineGrid>
        </Layout.Section>

        {/* Program Info */}
        {config && (
          <Layout.Section>
            <Card>
              <BlockStack gap="300">
                <Text as="h3" variant="headingMd">Current Reward Structure</Text>
                <InlineStack gap="600">
                  <BlockStack gap="100">
                    <Text as="span" variant="bodySm" tone="subdued">Referrer Reward</Text>
                    <Text as="span" variant="headingMd">
                      {formatCurrency(config.config.referrer_credit)}
                    </Text>
                  </BlockStack>
                  <BlockStack gap="100">
                    <Text as="span" variant="bodySm" tone="subdued">New Member Reward</Text>
                    <Text as="span" variant="headingMd">
                      {formatCurrency(config.config.referee_credit)}
                    </Text>
                  </BlockStack>
                  <BlockStack gap="100">
                    <Text as="span" variant="bodySm" tone="subdued">Granted On</Text>
                    <Badge tone={config.config.grant_on_signup ? 'success' : 'info'}>
                      {config.config.grant_on_signup ? 'Signup' : 'First Purchase'}
                    </Badge>
                  </BlockStack>
                  <BlockStack gap="100">
                    <Text as="span" variant="bodySm" tone="subdued">Monthly Limit</Text>
                    <Text as="span" variant="headingMd">
                      {config.config.max_referrals_per_month} per member
                    </Text>
                  </BlockStack>
                </InlineStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        )}

        {/* Top Referrers */}
        <Layout.Section variant="oneHalf">
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between" blockAlign="center">
                <Text as="h3" variant="headingMd">Top Referrers</Text>
                <Badge tone="info">Leaderboard</Badge>
              </InlineStack>

              {stats?.top_referrers && stats.top_referrers.length > 0 ? (
                <DataTable
                  columnContentTypes={['text', 'text', 'numeric', 'numeric']}
                  headings={['Member', 'Code', 'Referrals', 'Earnings']}
                  rows={stats.top_referrers.slice(0, 5).filter(referrer => referrer && referrer.id != null).map((referrer, index) => [
                    <InlineStack gap="200" key={referrer.id} blockAlign="center">
                      <Badge tone={index === 0 ? 'success' : index === 1 ? 'info' : 'enabled'}>
                        {`#${index + 1}`}
                      </Badge>
                      <BlockStack gap="050">
                        <Text as="span" variant="bodyMd" fontWeight="semibold">
                          {referrer.name || referrer.member_number || 'Unknown'}
                        </Text>
                        <Text as="span" variant="bodySm" tone="subdued">
                          {referrer.email || '-'}
                        </Text>
                      </BlockStack>
                    </InlineStack>,
                    <Badge key={`code-${referrer.id}`}>{String(referrer.referral_code || '-')}</Badge>,
                    referrer.referral_count || 0,
                    formatCurrency(referrer.referral_earnings || 0),
                  ])}
                />
              ) : (
                <EmptyState
                  heading="No referrals yet"
                  image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                >
                  <p>Top referrers will appear here once members start sharing.</p>
                </EmptyState>
              )}
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Recent Referrals */}
        <Layout.Section variant="oneHalf">
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between" blockAlign="center">
                <Text as="h3" variant="headingMd">Recent Activity</Text>
                <Badge>Latest signups</Badge>
              </InlineStack>

              {stats?.recent_referrals && stats.recent_referrals.length > 0 ? (
                <DataTable
                  columnContentTypes={['text', 'text', 'text']}
                  headings={['New Member', 'Referred By', 'Joined']}
                  rows={stats.recent_referrals.slice(0, 5).filter(referral => referral && referral.id != null).map((referral) => [
                    <BlockStack gap="050" key={referral.id}>
                      <Text as="span" variant="bodyMd" fontWeight="semibold">
                        {referral.name || referral.member_number || 'Unknown'}
                      </Text>
                    </BlockStack>,
                    <Badge key={`by-${referral.id}`} tone="info">
                      {String(referral.referred_by || 'Unknown')}
                    </Badge>,
                    referral.created_at ? formatDate(referral.created_at) : '-',
                  ])}
                />
              ) : (
                <EmptyState
                  heading="No recent referrals"
                  image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                >
                  <p>Recent referral activity will appear here.</p>
                </EmptyState>
              )}
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Sharing Instructions */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text as="h3" variant="headingMd">Promote Your Referral Program</Text>
              <BlockStack gap="200">
                <InlineStack gap="200">
                  <Badge>1</Badge>
                  <Text as="p">Add the <strong>Refer a Friend</strong> theme block to your storefront</Text>
                </InlineStack>
                <InlineStack gap="200">
                  <Badge>2</Badge>
                  <Text as="p">Members can find their unique referral code in their account dashboard</Text>
                </InlineStack>
                <InlineStack gap="200">
                  <Badge>3</Badge>
                  <Text as="p">New customers use the code at signup to unlock rewards for both parties</Text>
                </InlineStack>
              </BlockStack>
              <InlineStack gap="300">
                <Button url="/app/settings">Customize Theme Blocks</Button>
                <Button variant="plain">View Documentation</Button>
              </InlineStack>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>

      {/* Configuration Modal */}
      <Modal
        open={configModalOpen}
        onClose={() => setConfigModalOpen(false)}
        title="Configure Referral Rewards"
        primaryAction={{
          content: 'Save Changes',
          onAction: () => setConfigModalOpen(false),
        }}
        secondaryActions={[
          { content: 'Cancel', onAction: () => setConfigModalOpen(false) },
        ]}
      >
        <Modal.Section>
          <BlockStack gap="400">
            <Banner tone="info">
              <p>Referral reward amounts are currently configured in the backend. Contact support to change these values.</p>
            </Banner>
            <TextField
              label="Referrer Reward"
              type="number"
              prefix="$"
              value={config?.config.referrer_credit?.toString() || '10'}
              helpText="Credit given to the existing member who referred someone"
              autoComplete="off"
              disabled
            />
            <TextField
              label="New Member Reward"
              type="number"
              prefix="$"
              value={config?.config.referee_credit?.toString() || '5'}
              helpText="Credit given to the new member who was referred"
              autoComplete="off"
              disabled
            />
            <Select
              label="Grant Rewards"
              options={[
                { label: 'On Signup', value: 'signup' },
                { label: 'On First Purchase', value: 'purchase' },
              ]}
              value={config?.config.grant_on_signup ? 'signup' : 'purchase'}
              helpText="When referral rewards are credited"
              disabled
            />
            <TextField
              label="Monthly Limit per Member"
              type="number"
              value={config?.config.max_referrals_per_month?.toString() || '50'}
              helpText="Maximum referrals a single member can make per month"
              autoComplete="off"
              disabled
            />
          </BlockStack>
        </Modal.Section>
      </Modal>
    </Page>
  );
}
