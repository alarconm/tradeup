/**
 * Cashback Campaigns Page
 *
 * Create and manage promotional cashback campaigns
 * that automatically reward customers with store credit.
 */

import React, { useState } from 'react';
import {
  Page,
  Layout,
  Card,
  Text,
  Badge,
  Button,
  Modal,
  TextField,
  Select,
  FormLayout,
  DataTable,
  Banner,
  BlockStack,
  InlineStack,
  ProgressBar,
  Spinner,
} from '@shopify/polaris';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface EmbeddedCashbackProps {
  shop: string | null;
}

interface Campaign {
  id: number;
  name: string;
  cashback_rate: number;
  min_purchase: number;
  max_cashback: number;
  start_date: string;
  end_date: string;
  applies_to: string;
  status: string;
  total_awarded: number;
  redemption_count: number;
  budget_used_percent: number;
}

interface CampaignForm {
  name: string;
  cashback_rate: string;
  min_purchase: string;
  max_cashback: string;
  start_date: string;
  end_date: string;
  applies_to: string;
  budget: string;
}

const initialForm: CampaignForm = {
  name: '',
  cashback_rate: '5',
  min_purchase: '0',
  max_cashback: '50',
  start_date: '',
  end_date: '',
  applies_to: 'all',
  budget: '1000',
};

async function fetchCampaigns(shop: string | null): Promise<{ campaigns: Campaign[] }> {
  const response = await authFetch(`${getApiUrl()}/cashback/campaigns`, shop);
  if (!response.ok) throw new Error('Failed to fetch campaigns');
  return response.json();
}

export function EmbeddedCashback({ shop }: EmbeddedCashbackProps) {
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState<CampaignForm>(initialForm);
  const [error, setError] = useState<string | null>(null);

  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['cashback-campaigns', shop],
    queryFn: () => fetchCampaigns(shop),
    enabled: !!shop,
  });

  const createMutation = useMutation({
    mutationFn: async (campaign: CampaignForm) => {
      const response = await authFetch(`${getApiUrl()}/cashback/campaigns`, shop, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: campaign.name,
          cashback_rate: parseFloat(campaign.cashback_rate),
          min_purchase: parseFloat(campaign.min_purchase),
          max_cashback: parseFloat(campaign.max_cashback),
          start_date: campaign.start_date,
          end_date: campaign.end_date,
          applies_to: campaign.applies_to,
          budget: parseFloat(campaign.budget),
        }),
      });
      if (!response.ok) throw new Error('Failed to create campaign');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cashback-campaigns', shop] });
      setShowModal(false);
      setForm(initialForm);
    },
    onError: (err) => {
      setError(err.message);
    },
  });

  const activateMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await authFetch(`${getApiUrl()}/cashback/campaigns/${id}/activate`, shop, {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Failed to activate campaign');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cashback-campaigns', shop] });
    },
  });

  const handleSubmit = () => {
    if (!form.name || !form.cashback_rate || !form.start_date || !form.end_date) {
      setError('Please fill in all required fields');
      return;
    }
    createMutation.mutate(form);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge tone="success">Active</Badge>;
      case 'scheduled':
        return <Badge tone="info">Scheduled</Badge>;
      case 'ended':
        return <Badge>Ended</Badge>;
      case 'draft':
        return <Badge tone="attention">Draft</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  const campaigns = data?.campaigns || [];

  const tableRows = campaigns.map((campaign) => [
    campaign.name,
    `${campaign.cashback_rate}%`,
    `$${campaign.min_purchase}`,
    `$${campaign.max_cashback}`,
    getStatusBadge(campaign.status),
    `$${campaign.total_awarded.toFixed(2)}`,
    campaign.redemption_count,
    campaign.status === 'draft' ? (
      <Button
        size="slim"
        onClick={() => activateMutation.mutate(campaign.id)}
        loading={activateMutation.isPending}
      >
        Activate
      </Button>
    ) : null,
  ]);

  if (isLoading) {
    return (
      <Page title="Cashback Campaigns">
        <Card>
          <BlockStack gap="200" inlineAlign="center">
            <Spinner size="large" />
            <Text as="p">Loading campaigns...</Text>
          </BlockStack>
        </Card>
      </Page>
    );
  }

  return (
    <Page
      title="Cashback Campaigns"
      subtitle="Run promotional cashback periods to drive sales"
      primaryAction={{
        content: 'Create Campaign',
        onAction: () => setShowModal(true),
      }}
    >
      <Layout>
        <Layout.Section>
          {campaigns.length === 0 ? (
            <Card>
              <BlockStack gap="300" inlineAlign="center">
                <Text as="h3" variant="headingMd">No campaigns yet</Text>
                <Text as="p" variant="bodyMd" tone="subdued">
                  Create your first cashback campaign to automatically reward customers with store credit.
                </Text>
                <Button variant="primary" onClick={() => setShowModal(true)}>
                  Create Campaign
                </Button>
              </BlockStack>
            </Card>
          ) : (
            <Card>
              <DataTable
                columnContentTypes={[
                  'text',
                  'numeric',
                  'numeric',
                  'numeric',
                  'text',
                  'numeric',
                  'numeric',
                  'text',
                ]}
                headings={[
                  'Campaign',
                  'Rate',
                  'Min Purchase',
                  'Max Cashback',
                  'Status',
                  'Total Awarded',
                  'Redemptions',
                  'Actions',
                ]}
                rows={tableRows}
              />
            </Card>
          )}
        </Layout.Section>

        <Layout.Section variant="oneThird">
          <Card>
            <BlockStack gap="300">
              <Text as="h3" variant="headingMd">How It Works</Text>
              <Text as="p" variant="bodyMd" tone="subdued">
                Cashback campaigns automatically award store credit when customers complete qualifying purchases.
              </Text>
              <BlockStack gap="200">
                <Text as="p" variant="bodyMd">1. Set your cashback rate (e.g., 5%)</Text>
                <Text as="p" variant="bodyMd">2. Define minimum purchase requirements</Text>
                <Text as="p" variant="bodyMd">3. Set campaign dates</Text>
                <Text as="p" variant="bodyMd">4. Activate and watch credits flow!</Text>
              </BlockStack>
            </BlockStack>
          </Card>

          <Card>
            <BlockStack gap="300">
              <Text as="h3" variant="headingMd">Campaign Ideas</Text>
              <BlockStack gap="100">
                <Text as="p" variant="bodyMd">Double cashback weekend</Text>
                <Text as="p" variant="bodyMd">VIP member exclusive 10% back</Text>
                <Text as="p" variant="bodyMd">Holiday shopping bonus</Text>
                <Text as="p" variant="bodyMd">New product launch promo</Text>
              </BlockStack>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>

      {/* Create Campaign Modal */}
      <Modal
        open={showModal}
        onClose={() => {
          setShowModal(false);
          setForm(initialForm);
          setError(null);
        }}
        title="Create Cashback Campaign"
        primaryAction={{
          content: 'Create Campaign',
          onAction: handleSubmit,
          loading: createMutation.isPending,
        }}
        secondaryActions={[
          { content: 'Cancel', onAction: () => setShowModal(false) },
        ]}
      >
        <Modal.Section>
          {error && (
            <Banner tone="critical" onDismiss={() => setError(null)}>
              {error}
            </Banner>
          )}
          <FormLayout>
            <TextField
              label="Campaign Name"
              value={form.name}
              onChange={(v) => setForm({ ...form, name: v })}
              placeholder="Summer Cashback Special"
              autoComplete="off"
            />

            <FormLayout.Group>
              <TextField
                label="Cashback Rate (%)"
                type="number"
                value={form.cashback_rate}
                onChange={(v) => setForm({ ...form, cashback_rate: v })}
                suffix="%"
                autoComplete="off"
              />
              <TextField
                label="Budget"
                type="number"
                value={form.budget}
                onChange={(v) => setForm({ ...form, budget: v })}
                prefix="$"
                autoComplete="off"
              />
            </FormLayout.Group>

            <FormLayout.Group>
              <TextField
                label="Minimum Purchase"
                type="number"
                value={form.min_purchase}
                onChange={(v) => setForm({ ...form, min_purchase: v })}
                prefix="$"
                autoComplete="off"
              />
              <TextField
                label="Maximum Cashback"
                type="number"
                value={form.max_cashback}
                onChange={(v) => setForm({ ...form, max_cashback: v })}
                prefix="$"
                autoComplete="off"
              />
            </FormLayout.Group>

            <FormLayout.Group>
              <TextField
                label="Start Date"
                type="date"
                value={form.start_date}
                onChange={(v) => setForm({ ...form, start_date: v })}
                autoComplete="off"
              />
              <TextField
                label="End Date"
                type="date"
                value={form.end_date}
                onChange={(v) => setForm({ ...form, end_date: v })}
                autoComplete="off"
              />
            </FormLayout.Group>

            <Select
              label="Applies To"
              options={[
                { label: 'All Customers', value: 'all' },
                { label: 'Members Only', value: 'members' },
                { label: 'Gold Tier', value: 'tier:gold' },
                { label: 'Silver Tier', value: 'tier:silver' },
              ]}
              value={form.applies_to}
              onChange={(v) => setForm({ ...form, applies_to: v })}
            />
          </FormLayout>
        </Modal.Section>
      </Modal>
    </Page>
  );
}

export default EmbeddedCashback;
