/**
 * TradeUp Billing - Shopify Embedded Version
 *
 * Manage subscription via Shopify Billing API.
 */
import { useState, useCallback } from 'react';
import {
  Page,
  Layout,
  Card,
  Text,
  InlineStack,
  BlockStack,
  Badge,
  Button,
  Banner,
  Spinner,
  Box,
  ProgressBar,
  Icon,
  Modal,
} from '@shopify/polaris';
import { CheckIcon } from '@shopify/polaris-icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface BillingProps {
  shop: string | null;
}

interface Plan {
  key: string;
  name: string;
  price: number;
  max_members: number | null;
  max_tiers: number | null;
  features: string[];
}

interface BillingStatus {
  plan: string;
  status: string;
  active: boolean;
  trial_ends_at: string | null;
  current_period_end: string | null;
  usage: {
    members: { current: number; limit: number | null; percentage: number };
    tiers: { current: number; limit: number | null; percentage: number };
  };
}

async function fetchPlans(): Promise<{ plans: Plan[] }> {
  // Plans don't require auth - they're public
  const response = await fetch(`${getApiUrl()}/billing/plans`);
  if (!response.ok) throw new Error('Failed to fetch plans');
  return response.json();
}

async function fetchBillingStatus(shop: string | null): Promise<BillingStatus> {
  const response = await authFetch(
    `${getApiUrl()}/billing/status`,
    shop
  );
  if (!response.ok) throw new Error('Failed to fetch billing status');
  return response.json();
}

async function subscribeToPlan(
  shop: string | null,
  planKey: string
): Promise<{ confirmation_url: string }> {
  const response = await authFetch(
    `${getApiUrl()}/billing/subscribe`,
    shop,
    {
      method: 'POST',
      body: JSON.stringify({ plan: planKey }),
    }
  );
  if (!response.ok) throw new Error('Failed to subscribe');
  return response.json();
}

async function cancelSubscription(shop: string | null): Promise<void> {
  const response = await authFetch(
    `${getApiUrl()}/billing/cancel`,
    shop,
    { method: 'POST' }
  );
  if (!response.ok) throw new Error('Failed to cancel');
}

export function EmbeddedBilling({ shop }: BillingProps) {
  const queryClient = useQueryClient();
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const [cancelModalOpen, setCancelModalOpen] = useState(false);

  const { data: plansData, isLoading: plansLoading } = useQuery({
    queryKey: ['plans'],
    queryFn: fetchPlans,
  });

  const { data: status, isLoading: statusLoading, error } = useQuery({
    queryKey: ['billing-status', shop],
    queryFn: () => fetchBillingStatus(shop),
    enabled: !!shop,
  });

  const subscribeMutation = useMutation({
    mutationFn: (planKey: string) => subscribeToPlan(shop, planKey),
    onSuccess: (data) => {
      // Redirect to Shopify confirmation URL
      window.top?.location.assign(data.confirmation_url);
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelSubscription(shop),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billing-status'] });
      setCancelModalOpen(false);
    },
  });

  const handleSelectPlan = useCallback((planKey: string) => {
    setSelectedPlan(planKey);
    subscribeMutation.mutate(planKey);
  }, [subscribeMutation]);

  if (!shop) {
    return (
      <Page title="Plan & Billing">
        <Banner tone="warning">
          <p>No shop connected. Please install the app from the Shopify App Store.</p>
        </Banner>
      </Page>
    );
  }

  if (plansLoading || statusLoading) {
    return (
      <Page title="Plan & Billing">
        <Box padding="1600">
          <InlineStack align="center">
            <Spinner size="large" />
          </InlineStack>
        </Box>
      </Page>
    );
  }

  const formatLimit = (limit: number | null) => {
    return limit === null ? 'Unlimited' : limit.toLocaleString();
  };

  const isCurrentPlan = (planKey: string) => {
    return status?.plan === planKey && status?.active;
  };

  return (
    <Page
      title="Plan & Billing"
      subtitle="Manage your TradeUp subscription"
    >
      <Layout>
        {error && (
          <Layout.Section>
            <Banner tone="critical">
              <p>Failed to load billing information. Please try refreshing.</p>
            </Banner>
          </Layout.Section>
        )}

        {/* Current Plan Overview */}
        {status && (
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <InlineStack align="space-between" blockAlign="center">
                  <BlockStack gap="100">
                    <InlineStack gap="200" blockAlign="center">
                      <Text as="h2" variant="headingLg">
                        {status.plan ? String(status.plan).charAt(0).toUpperCase() + String(status.plan).slice(1) : 'Free'}
                      </Text>
                      <Badge tone={status.active ? 'success' : 'warning'}>
                        {status.status || 'inactive'}
                      </Badge>
                    </InlineStack>
                    {status.trial_ends_at && (
                      <Text as="p" variant="bodySm" tone="subdued">
                        Trial ends: {new Date(status.trial_ends_at).toLocaleDateString()}
                      </Text>
                    )}
                  </BlockStack>

                  {status.active && (
                    <Button
                      variant="plain"
                      tone="critical"
                      onClick={() => setCancelModalOpen(true)}
                    >
                      Cancel subscription
                    </Button>
                  )}
                </InlineStack>

                <InlineStack gap="800">
                  <BlockStack gap="200">
                    <Text as="span" variant="bodySm" tone="subdued">
                      Members
                    </Text>
                    <Text as="span" variant="headingMd">
                      {status.usage.members.current} / {formatLimit(status.usage.members.limit)}
                    </Text>
                    <ProgressBar
                      progress={status.usage.members.percentage}
                      size="small"
                      tone={
                        status.usage.members.percentage > 90
                          ? 'critical'
                          : status.usage.members.percentage > 75
                          ? 'highlight'
                          : 'success'
                      }
                    />
                  </BlockStack>

                  <BlockStack gap="200">
                    <Text as="span" variant="bodySm" tone="subdued">
                      Tiers
                    </Text>
                    <Text as="span" variant="headingMd">
                      {status.usage.tiers.current} / {formatLimit(status.usage.tiers.limit)}
                    </Text>
                    <ProgressBar
                      progress={status.usage.tiers.percentage}
                      size="small"
                    />
                  </BlockStack>
                </InlineStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        )}

        {/* Plans */}
        <Layout.Section>
          <Text as="h2" variant="headingLg">
            Available Plans
          </Text>
        </Layout.Section>

        <Layout.Section>
          <InlineStack gap="400" wrap={false}>
            {plansData?.plans.filter(plan => plan && plan.key).map((plan) => (
              <Card key={plan.key}>
                <BlockStack gap="400">
                  <BlockStack gap="200">
                    <InlineStack align="space-between" blockAlign="center">
                      <Text as="h3" variant="headingMd">
                        {plan.name}
                      </Text>
                      {isCurrentPlan(plan.key) && (
                        <Badge tone="success">Current</Badge>
                      )}
                    </InlineStack>
                    <InlineStack gap="100" blockAlign="baseline">
                      <Text as="span" variant="heading2xl">
                        ${plan.price}
                      </Text>
                      <Text as="span" variant="bodySm" tone="subdued">
                        /month
                      </Text>
                    </InlineStack>
                  </BlockStack>

                  <BlockStack gap="200">
                    <InlineStack gap="200">
                      <Icon source={CheckIcon} tone="success" />
                      <Text as="span" variant="bodySm">
                        {formatLimit(plan.max_members)} members
                      </Text>
                    </InlineStack>
                    <InlineStack gap="200">
                      <Icon source={CheckIcon} tone="success" />
                      <Text as="span" variant="bodySm">
                        {formatLimit(plan.max_tiers)} tiers
                      </Text>
                    </InlineStack>
                    {(plan.features || []).filter(f => f).map((feature, idx) => (
                      <InlineStack gap="200" key={idx}>
                        <Icon source={CheckIcon} tone="success" />
                        <Text as="span" variant="bodySm">
                          {feature}
                        </Text>
                      </InlineStack>
                    ))}
                  </BlockStack>

                  <Button
                    variant={isCurrentPlan(plan.key) ? 'secondary' : 'primary'}
                    disabled={isCurrentPlan(plan.key)}
                    loading={subscribeMutation.isPending && selectedPlan === plan.key}
                    onClick={() => handleSelectPlan(plan.key)}
                    fullWidth
                  >
                    {isCurrentPlan(plan.key) ? 'Current Plan' : 'Select Plan'}
                  </Button>
                </BlockStack>
              </Card>
            ))}
          </InlineStack>
        </Layout.Section>
      </Layout>

      {/* Cancel Confirmation Modal */}
      <Modal
        open={cancelModalOpen}
        onClose={() => setCancelModalOpen(false)}
        title="Cancel Subscription"
        primaryAction={{
          content: 'Cancel Subscription',
          destructive: true,
          onAction: () => cancelMutation.mutate(),
          loading: cancelMutation.isPending,
        }}
        secondaryActions={[
          { content: 'Keep Subscription', onAction: () => setCancelModalOpen(false) },
        ]}
      >
        <Modal.Section>
          <BlockStack gap="400">
            <Text as="p">
              Are you sure you want to cancel your subscription?
            </Text>
            <Text as="p" tone="subdued">
              You'll lose access to premium features at the end of your current
              billing period. Your data will be preserved if you decide to
              resubscribe.
            </Text>
          </BlockStack>
        </Modal.Section>
      </Modal>
    </Page>
  );
}
