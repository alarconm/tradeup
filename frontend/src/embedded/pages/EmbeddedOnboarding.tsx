/**
 * TradeUp Onboarding - Shopify Embedded Version
 *
 * Simplified setup wizard using Shopify Polaris:
 * - Check store credit status
 * - Choose a tier template
 * - Go live
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
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
  InlineGrid,
} from '@shopify/polaris';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface OnboardingProps {
  shop: string | null;
}

interface OnboardingStatus {
  setup_complete: boolean;
  current_step: number;
  steps: {
    id: number;
    name: string;
    description: string;
    status: string;
    action: string | null;
  }[];
}

interface StoreCreditCheck {
  enabled: boolean;
  status: string;
  message: string;
  instructions?: string[];
  settings_url?: string;
}

interface TierTemplate {
  key: string;
  name: string;
  description: string;
  tier_count: number;
  tiers: {
    name: string;
    icon: string;
    color: string;
    trade_in_rate: number;
  }[];
}

async function fetchOnboardingStatus(shop: string | null): Promise<OnboardingStatus> {
  const response = await authFetch(`${getApiUrl()}/onboarding/status`, shop);
  if (!response.ok) throw new Error('Failed to fetch onboarding status');
  return response.json();
}

async function fetchTemplates(shop: string | null): Promise<{ templates: TierTemplate[] }> {
  const response = await authFetch(`${getApiUrl()}/onboarding/templates`, shop);
  if (!response.ok) throw new Error('Failed to fetch templates');
  return response.json();
}

async function checkStoreCredit(shop: string | null): Promise<StoreCreditCheck> {
  const response = await authFetch(`${getApiUrl()}/onboarding/store-credit-check`, shop);
  if (!response.ok) throw new Error('Failed to check store credit');
  return response.json();
}

async function applyTemplate(shop: string | null, templateKey: string): Promise<void> {
  const response = await authFetch(
    `${getApiUrl()}/onboarding/templates/${templateKey}/apply`,
    shop,
    { method: 'POST' }
  );
  if (!response.ok) throw new Error('Failed to apply template');
}

async function completeOnboarding(shop: string | null): Promise<void> {
  const response = await authFetch(
    `${getApiUrl()}/onboarding/complete`,
    shop,
    { method: 'POST' }
  );
  if (!response.ok) throw new Error('Failed to complete onboarding');
}

async function skipOnboarding(shop: string | null): Promise<void> {
  const response = await authFetch(
    `${getApiUrl()}/onboarding/skip`,
    shop,
    { method: 'POST' }
  );
  if (!response.ok) throw new Error('Failed to skip onboarding');
}

export function EmbeddedOnboarding({ shop }: OnboardingProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [storeCreditResult, setStoreCreditResult] = useState<StoreCreditCheck | null>(null);

  const { data: status, isLoading: statusLoading, error: statusError } = useQuery({
    queryKey: ['onboarding-status', shop],
    queryFn: () => fetchOnboardingStatus(shop),
    enabled: !!shop,
  });

  const { data: templatesData, isLoading: templatesLoading } = useQuery({
    queryKey: ['onboarding-templates', shop],
    queryFn: () => fetchTemplates(shop),
    enabled: !!shop,
  });

  const checkCreditMutation = useMutation({
    mutationFn: () => checkStoreCredit(shop),
    onSuccess: (result) => {
      setStoreCreditResult(result);
      if (result.enabled) {
        queryClient.invalidateQueries({ queryKey: ['onboarding-status'] });
      }
    },
  });

  const applyMutation = useMutation({
    mutationFn: (templateKey: string) => applyTemplate(shop, templateKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['onboarding-status'] });
    },
  });

  const completeMutation = useMutation({
    mutationFn: () => completeOnboarding(shop),
    onSuccess: () => {
      navigate('/app/dashboard');
    },
  });

  const skipMutation = useMutation({
    mutationFn: () => skipOnboarding(shop),
    onSuccess: () => {
      navigate('/app/dashboard');
    },
  });

  if (!shop) {
    return (
      <Page title="Setup Wizard">
        <Banner tone="warning">
          <p>No shop connected. Please install the app from the Shopify App Store.</p>
        </Banner>
      </Page>
    );
  }

  if (statusLoading) {
    return (
      <Page title="Setup Wizard">
        <Box padding="1600">
          <InlineStack align="center">
            <Spinner size="large" />
          </InlineStack>
        </Box>
      </Page>
    );
  }

  if (statusError) {
    return (
      <Page title="Setup Wizard">
        <Banner tone="critical">
          <p>Failed to load setup status. Please try refreshing the page.</p>
        </Banner>
      </Page>
    );
  }

  // If onboarding is complete, redirect to dashboard with a loading message
  if (status?.setup_complete) {
    navigate('/app/dashboard', { replace: true });
    return (
      <Page title="Setup Complete">
        <Box padding="1600">
          <BlockStack gap="400" inlineAlign="center">
            <Spinner size="large" />
            <Text as="p" tone="subdued">Redirecting to dashboard...</Text>
          </BlockStack>
        </Box>
      </Page>
    );
  }

  const currentStep = status?.current_step || 1;
  const progress = ((currentStep - 1) / 3) * 100;

  return (
    <Page
      title="Welcome to TradeUp!"
      subtitle="Let's get your loyalty program set up in just a few steps"
      backAction={{ content: 'Dashboard', onAction: () => navigate('/app/dashboard') }}
    >
      <Layout>
        {/* Progress indicator */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between">
                <Text as="span" variant="bodySm" tone="subdued">Setup Progress</Text>
                <Text as="span" variant="bodySm" tone="subdued">{currentStep} of 4 steps</Text>
              </InlineStack>
              <ProgressBar progress={progress} size="small" tone="primary" />
              <InlineStack gap="200" wrap>
                {status?.steps.map((step) => (
                  <Badge
                    key={step.id}
                    tone={step.status === 'complete' ? 'success' : step.id === currentStep ? 'info' : undefined}
                  >
                    {`${step.status === 'complete' ? '✓' : step.id} ${step.name}`}
                  </Badge>
                ))}
              </InlineStack>
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Step 1: Welcome - App Installed */}
        {currentStep === 1 && (
          <Layout.Section>
            <Card>
              <BlockStack gap="400" inlineAlign="center">
                <div style={{ fontSize: '48px' }}>🎉</div>
                <Text as="h2" variant="headingLg">TradeUp is Installed!</Text>
                <Text as="p" tone="subdued" alignment="center">
                  Great! TradeUp is connected to your store. Let's get your loyalty
                  program set up in just a few quick steps.
                </Text>
                <Button
                  variant="primary"
                  onClick={() => {
                    // Force refetch to get updated step (Step 1 should auto-complete)
                    queryClient.invalidateQueries({ queryKey: ['onboarding-status'] });
                  }}
                >
                  Let's Get Started
                </Button>
              </BlockStack>
            </Card>
          </Layout.Section>
        )}

        {/* Step 2: Store Credit Check */}
        {currentStep === 2 && (
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingLg">Enable Shopify Store Credit</Text>
                <Text as="p" tone="subdued">
                  TradeUp uses Shopify's native store credit feature to reward your customers.
                  This needs to be enabled in your Shopify settings.
                </Text>

                {!storeCreditResult ? (
                  <Button
                    variant="primary"
                    loading={checkCreditMutation.isPending}
                    onClick={() => checkCreditMutation.mutate()}
                  >
                    Check Store Credit Status
                  </Button>
                ) : storeCreditResult.enabled ? (
                  <Banner tone="success">
                    <p><strong>Store credit is enabled!</strong> {storeCreditResult.message}</p>
                  </Banner>
                ) : (
                  <BlockStack gap="400">
                    <Banner tone="warning">
                      <p><strong>Store credit needs to be enabled</strong></p>
                      <p>{storeCreditResult.message}</p>
                      {storeCreditResult.instructions && (
                        <ol style={{ margin: '8px 0', paddingLeft: '20px' }}>
                          {storeCreditResult.instructions.map((instruction, idx) => (
                            <li key={idx}>{instruction}</li>
                          ))}
                        </ol>
                      )}
                    </Banner>
                    <InlineStack gap="200">
                      {storeCreditResult.settings_url && (
                        <Button
                          variant="secondary"
                          url={storeCreditResult.settings_url}
                          external
                        >
                          Open Shopify Settings
                        </Button>
                      )}
                      <Button
                        loading={checkCreditMutation.isPending}
                        onClick={() => checkCreditMutation.mutate()}
                      >
                        Check Again
                      </Button>
                    </InlineStack>
                  </BlockStack>
                )}
              </BlockStack>
            </Card>
          </Layout.Section>
        )}

        {/* Step 3: Choose Template */}
        {currentStep === 3 && (
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingLg">Choose Your Tier Structure</Text>
                <Text as="p" tone="subdued">
                  Select a pre-built template that matches your business type.
                  You can customize these later in Settings.
                </Text>

                {templatesLoading ? (
                  <Box padding="400">
                    <InlineStack align="center">
                      <Spinner size="small" />
                    </InlineStack>
                  </Box>
                ) : (
                  <InlineStack gap="400" wrap>
                    {templatesData?.templates.map((template) => (
                      <Card
                        key={template.key}
                        background={selectedTemplate === template.key ? 'bg-surface-secondary' : undefined}
                      >
                        <BlockStack gap="300">
                          <InlineStack align="space-between" blockAlign="center">
                            <Text as="h3" variant="headingMd">{template.name}</Text>
                            <Badge>{`${template.tier_count} tiers`}</Badge>
                          </InlineStack>
                          <Text as="p" variant="bodySm" tone="subdued">
                            {template.description}
                          </Text>
                          <BlockStack gap="100">
                            {template.tiers.map((tier, idx) => (
                              <InlineStack key={idx} gap="200" blockAlign="center">
                                <Text as="span">{tier.icon}</Text>
                                <Text as="span" variant="bodySm">{tier.name}</Text>
                                <Badge tone="info">{`${tier.trade_in_rate}%`}</Badge>
                              </InlineStack>
                            ))}
                          </BlockStack>
                          <Button
                            variant={selectedTemplate === template.key ? 'primary' : 'secondary'}
                            onClick={() => setSelectedTemplate(template.key)}
                            fullWidth
                          >
                            {selectedTemplate === template.key ? 'Selected' : 'Select'}
                          </Button>
                        </BlockStack>
                      </Card>
                    ))}
                  </InlineStack>
                )}

                <InlineStack gap="200">
                  <Button
                    variant="primary"
                    loading={applyMutation.isPending}
                    disabled={!selectedTemplate}
                    onClick={() => selectedTemplate && applyMutation.mutate(selectedTemplate)}
                  >
                    Apply Template
                  </Button>
                  <Button
                    variant="plain"
                    onClick={() => navigate('/app/tiers')}
                  >
                    Or create custom tiers
                  </Button>
                </InlineStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        )}

        {/* Step 4: Ready to Go */}
        {currentStep === 4 && (
          <Layout.Section>
            <Card>
              <BlockStack gap="400" inlineAlign="center">
                <div style={{ fontSize: '48px' }}>🚀</div>
                <Text as="h2" variant="headingLg">You're All Set!</Text>
                <Text as="p" tone="subdued" alignment="center">
                  Your loyalty program is ready to start accepting members.
                  Customers will automatically be enrolled when they make a purchase.
                </Text>

                <InlineGrid columns={{ xs: 1, sm: 3 }} gap="400">
                  <Card>
                    <BlockStack gap="100" inlineAlign="center">
                      <Text as="span" variant="bodySm" tone="subdued">Tiers Created</Text>
                      <Text as="span" variant="headingLg">3</Text>
                    </BlockStack>
                  </Card>
                  <Card>
                    <BlockStack gap="100" inlineAlign="center">
                      <Text as="span" variant="bodySm" tone="subdued">Store Credit</Text>
                      <Text as="span" variant="headingLg">Enabled</Text>
                    </BlockStack>
                  </Card>
                  <Card>
                    <BlockStack gap="100" inlineAlign="center">
                      <Text as="span" variant="bodySm" tone="subdued">Auto-Enrollment</Text>
                      <Text as="span" variant="headingLg">On</Text>
                    </BlockStack>
                  </Card>
                </InlineGrid>

                <Button
                  variant="primary"
                  size="large"
                  loading={completeMutation.isPending}
                  onClick={() => completeMutation.mutate()}
                >
                  Go to Dashboard
                </Button>
              </BlockStack>
            </Card>
          </Layout.Section>
        )}

        {/* Skip link */}
        <Layout.Section>
          <InlineStack align="center">
            <Button
              variant="plain"
              loading={skipMutation.isPending}
              onClick={() => skipMutation.mutate()}
            >
              Skip setup and configure manually
            </Button>
          </InlineStack>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
