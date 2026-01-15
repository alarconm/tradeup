/**
 * Integrations Hub Page
 *
 * Central management for all third-party integrations:
 * - Klaviyo (email marketing)
 * - Postscript/Attentive (SMS)
 * - Gorgias (customer service)
 * - Judge.me (reviews)
 * - Recharge (subscriptions)
 * - Shopify Flow (automation)
 */

import React, { useState } from 'react';
import {
  Page,
  Layout,
  Card,
  Text,
  Badge,
  Button,
  Banner,
  Modal,
  TextField,
  FormLayout,
  BlockStack,
  InlineStack,
  Icon,
  Spinner,
  Tabs,
} from '@shopify/polaris';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface EmbeddedIntegrationsProps {
  shop: string | null;
}

interface IntegrationStatus {
  enabled: boolean;
  type: string;
}

interface IntegrationsResponse {
  success: boolean;
  integrations: {
    klaviyo: IntegrationStatus;
    postscript: IntegrationStatus;
    attentive: IntegrationStatus;
    gorgias: IntegrationStatus;
    judgeme: IntegrationStatus;
    recharge: IntegrationStatus;
  };
}

async function fetchIntegrationStatus(shop: string | null): Promise<IntegrationsResponse> {
  const response = await authFetch(`${getApiUrl()}/integrations/status`, shop);
  if (!response.ok) throw new Error('Failed to fetch integrations');
  return response.json();
}

export function EmbeddedIntegrations({ shop }: EmbeddedIntegrationsProps) {
  const [selectedTab, setSelectedTab] = useState(0);
  const [connectModal, setConnectModal] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState('');
  const [domain, setDomain] = useState('');

  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ['integrations', shop],
    queryFn: () => fetchIntegrationStatus(shop),
    enabled: !!shop,
  });

  // Map integration keys to API paths
  const getIntegrationPath = (integration: string) => {
    const pathMap: Record<string, string> = {
      klaviyo: 'klaviyo',
      postscript: 'sms/postscript',
      attentive: 'sms/attentive',
      gorgias: 'gorgias',
      judgeme: 'judgeme',
      recharge: 'recharge',
    };
    return pathMap[integration] || integration;
  };

  const connectMutation = useMutation({
    mutationFn: async ({ integration, credentials }: { integration: string; credentials: Record<string, string> }) => {
      const path = getIntegrationPath(integration);
      const response = await authFetch(`${getApiUrl()}/integrations/${path}/connect`, shop, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials),
      });
      if (!response.ok) throw new Error('Connection failed');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations', shop] });
      setConnectModal(null);
      setApiKey('');
      setDomain('');
    },
  });

  const disconnectMutation = useMutation({
    mutationFn: async (integration: string) => {
      const path = getIntegrationPath(integration);
      const response = await authFetch(`${getApiUrl()}/integrations/${path}/disconnect`, shop, {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Disconnect failed');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations', shop] });
    },
  });

  const tabs = [
    { id: 'email', content: 'Email Marketing' },
    { id: 'sms', content: 'SMS Marketing' },
    { id: 'support', content: 'Customer Service' },
    { id: 'reviews', content: 'Reviews' },
    { id: 'subscriptions', content: 'Subscriptions' },
  ];

  const renderIntegrationCard = (
    name: string,
    key: string,
    description: string,
    status: IntegrationStatus | undefined
  ) => (
    <Card key={key}>
      <BlockStack gap="300">
        <InlineStack align="space-between">
          <Text as="h3" variant="headingMd">{name}</Text>
          <Badge tone={status?.enabled ? 'success' : undefined}>
            {status?.enabled ? 'Connected' : 'Not Connected'}
          </Badge>
        </InlineStack>
        <Text as="p" variant="bodyMd" tone="subdued">
          {description}
        </Text>
        <InlineStack gap="200">
          {status?.enabled ? (
            <>
              <Button onClick={() => setConnectModal(key)}>Configure</Button>
              <Button
                tone="critical"
                onClick={() => disconnectMutation.mutate(key)}
                loading={disconnectMutation.isPending}
              >
                Disconnect
              </Button>
            </>
          ) : (
            <Button variant="primary" onClick={() => setConnectModal(key)}>
              Connect
            </Button>
          )}
        </InlineStack>
      </BlockStack>
    </Card>
  );

  const renderEmailTab = () => (
    <BlockStack gap="400">
      {renderIntegrationCard(
        'Klaviyo',
        'klaviyo',
        'Sync member data and trigger email flows on loyalty events like tier upgrades and points earned.',
        data?.integrations.klaviyo
      )}
    </BlockStack>
  );

  const renderSmsTab = () => (
    <BlockStack gap="400">
      {renderIntegrationCard(
        'Postscript',
        'postscript',
        'Send SMS notifications for loyalty events and sync subscriber data.',
        data?.integrations.postscript
      )}
      {renderIntegrationCard(
        'Attentive',
        'attentive',
        'Trigger Attentive journeys on loyalty events and sync customer attributes.',
        data?.integrations.attentive
      )}
    </BlockStack>
  );

  const renderSupportTab = () => (
    <BlockStack gap="400">
      {renderIntegrationCard(
        'Gorgias',
        'gorgias',
        'Display loyalty data in support tickets and auto-enrich customer profiles.',
        data?.integrations.gorgias
      )}
    </BlockStack>
  );

  const renderReviewsTab = () => (
    <BlockStack gap="400">
      {renderIntegrationCard(
        'Judge.me',
        'judgeme',
        'Award points when customers leave product reviews. Bonus points for photo and video reviews.',
        data?.integrations.judgeme
      )}
    </BlockStack>
  );

  const renderSubscriptionsTab = () => (
    <BlockStack gap="400">
      {renderIntegrationCard(
        'Recharge',
        'recharge',
        'Track subscription revenue for tier eligibility and award points on recurring payments.',
        data?.integrations.recharge
      )}
    </BlockStack>
  );

  const handleConnect = () => {
    if (!connectModal) return;

    const credentials: Record<string, string> = { api_key: apiKey };
    if (domain) credentials.domain = domain;

    connectMutation.mutate({ integration: connectModal, credentials });
  };

  if (isLoading) {
    return (
      <Page title="Integrations">
        <Card>
          <BlockStack gap="200" inlineAlign="center">
            <Spinner size="large" />
            <Text as="p">Loading integrations...</Text>
          </BlockStack>
        </Card>
      </Page>
    );
  }

  return (
    <Page
      title="Integrations"
      subtitle="Connect your favorite apps to TradeUp"
    >
      <Layout>
        <Layout.Section>
          {error && (
            <Banner tone="critical">
              Failed to load integrations. Please try again.
            </Banner>
          )}

          <Tabs tabs={tabs} selected={selectedTab} onSelect={setSelectedTab}>
            <div style={{ padding: '16px 0' }}>
              {selectedTab === 0 && renderEmailTab()}
              {selectedTab === 1 && renderSmsTab()}
              {selectedTab === 2 && renderSupportTab()}
              {selectedTab === 3 && renderReviewsTab()}
              {selectedTab === 4 && renderSubscriptionsTab()}
            </div>
          </Tabs>
        </Layout.Section>

        <Layout.Section variant="oneThird">
          <Card>
            <BlockStack gap="300">
              <Text as="h3" variant="headingMd">Shopify Flow</Text>
              <Text as="p" variant="bodyMd" tone="subdued">
                TradeUp automatically works with Shopify Flow. Use our triggers and actions in your automation workflows.
              </Text>
              <Button url="https://admin.shopify.com/store/flow" external>
                Open Flow Editor
              </Button>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>

      {/* Connect Modal */}
      <Modal
        open={!!connectModal}
        onClose={() => {
          setConnectModal(null);
          setApiKey('');
          setDomain('');
        }}
        title={`Connect ${connectModal}`}
        primaryAction={{
          content: 'Connect',
          onAction: handleConnect,
          loading: connectMutation.isPending,
        }}
        secondaryActions={[
          { content: 'Cancel', onAction: () => setConnectModal(null) },
        ]}
      >
        <Modal.Section>
          <FormLayout>
            <TextField
              label="API Key"
              value={apiKey}
              onChange={setApiKey}
              autoComplete="off"
              type="password"
            />
            {(connectModal === 'gorgias') && (
              <TextField
                label="Domain"
                value={domain}
                onChange={setDomain}
                placeholder="yourstore.gorgias.com"
                autoComplete="off"
              />
            )}
          </FormLayout>
        </Modal.Section>
      </Modal>
    </Page>
  );
}

export default EmbeddedIntegrations;
