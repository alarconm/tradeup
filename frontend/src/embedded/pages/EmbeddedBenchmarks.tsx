/**
 * Benchmarks Page
 *
 * Compare store performance against industry benchmarks.
 * Shows where the store ranks and provides recommendations.
 */

import React, { useState } from 'react';
import {
  Page,
  Layout,
  Card,
  Text,
  Badge,
  Button,
  Select,
  DataTable,
  Banner,
  BlockStack,
  InlineStack,
  ProgressBar,
  Spinner,
} from '@shopify/polaris';
import { useQuery } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface EmbeddedBenchmarksProps {
  shop: string | null;
}

interface MetricData {
  name: string;
  description: string;
  unit: string;
  good_direction: string;
  benchmarks: {
    p25: number;
    p50: number;
    p75: number;
    p90: number;
  };
  your_value: number | null;
  your_percentile: number | null;
}

interface BenchmarkReport {
  success: boolean;
  overall_score: number | null;
  overall_grade: string;
  metrics: Record<string, {
    name: string;
    your_value: number | null;
    percentile: number | null;
    p50: number;
  }>;
  strengths: Array<{
    metric: string;
    percentile: number;
    message: string;
  }>;
  opportunities: Array<{
    metric: string;
    percentile: number;
    recommendation: string;
  }>;
  recommendations: string[];
}

async function fetchBenchmarkReport(shop: string | null): Promise<BenchmarkReport> {
  const response = await authFetch(`${getApiUrl()}/benchmarks/report`, shop);
  if (!response.ok) throw new Error('Failed to fetch benchmarks');
  return response.json();
}

export function EmbeddedBenchmarks({ shop }: EmbeddedBenchmarksProps) {
  const [category, setCategory] = useState('');

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['benchmarks', shop, category],
    queryFn: () => fetchBenchmarkReport(shop),
    enabled: !!shop,
  });

  const getGradeBadge = (grade: string) => {
    const tones: Record<string, 'success' | 'info' | 'attention' | 'warning' | 'critical'> = {
      'A+': 'success',
      'A': 'success',
      'B+': 'info',
      'B': 'info',
      'C+': 'attention',
      'C': 'attention',
      'D': 'warning',
      'F': 'critical',
    };
    return <Badge tone={tones[grade] || undefined} size="large">{grade}</Badge>;
  };

  const getPercentileColor = (percentile: number | null) => {
    if (percentile === null) return 'subdued';
    if (percentile >= 75) return 'success';
    if (percentile >= 50) return 'highlight';
    if (percentile >= 25) return 'warning';
    return 'critical';
  };

  const formatValue = (value: number | null, unit: string) => {
    if (value === null) return 'N/A';
    if (unit === 'currency') return `$${value.toFixed(2)}`;
    if (unit === 'percent') return `${value}%`;
    return value.toLocaleString();
  };

  if (isLoading) {
    return (
      <Page title="Benchmarks">
        <Card>
          <BlockStack gap="200" inlineAlign="center">
            <Spinner size="large" />
            <Text as="p">Analyzing your performance...</Text>
          </BlockStack>
        </Card>
      </Page>
    );
  }

  if (error) {
    return (
      <Page title="Benchmarks">
        <Banner tone="critical">
          Failed to load benchmarks. Please try again.
        </Banner>
      </Page>
    );
  }

  const metrics = data?.metrics || {};
  const strengths = data?.strengths || [];
  const opportunities = data?.opportunities || [];
  const recommendations = data?.recommendations || [];

  return (
    <Page
      title="Benchmarks"
      subtitle="See how your loyalty program compares to similar stores"
      secondaryActions={[
        { content: 'Refresh', onAction: () => refetch() },
      ]}
    >
      <Layout>
        {/* Overall Score */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between">
                <BlockStack gap="200">
                  <Text as="h2" variant="headingLg">Overall Performance</Text>
                  <Text as="p" variant="bodyMd" tone="subdued">
                    Based on all available metrics
                  </Text>
                </BlockStack>
                <BlockStack gap="200" inlineAlign="end">
                  {data?.overall_grade && getGradeBadge(data.overall_grade)}
                  {data?.overall_score != null && (
                    <Text as="p" variant="bodySm" tone="subdued">
                      {data.overall_score.toFixed(0)}th percentile
                    </Text>
                  )}
                </BlockStack>
              </InlineStack>

              {data?.overall_score != null && (
                <ProgressBar
                  progress={data.overall_score}
                  tone={data.overall_score >= 50 ? 'primary' : 'critical'}
                  size="small"
                />
              )}
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Strengths & Opportunities */}
        <Layout.Section variant="oneHalf">
          <Card>
            <BlockStack gap="300">
              <Text as="h3" variant="headingMd">Your Strengths</Text>
              {strengths.length === 0 ? (
                <Text as="p" tone="subdued">Keep building your program to unlock strengths!</Text>
              ) : (
                <BlockStack gap="200">
                  {strengths.map((s, i) => (
                    <InlineStack key={i} gap="200" align="start">
                      <Badge tone="success">{`${s.percentile}%`}</Badge>
                      <Text as="p">{s.message}</Text>
                    </InlineStack>
                  ))}
                </BlockStack>
              )}
            </BlockStack>
          </Card>
        </Layout.Section>

        <Layout.Section variant="oneHalf">
          <Card>
            <BlockStack gap="300">
              <Text as="h3" variant="headingMd">Opportunities</Text>
              {opportunities.length === 0 ? (
                <Text as="p" tone="subdued">Great job! No major opportunities identified.</Text>
              ) : (
                <BlockStack gap="200">
                  {opportunities.map((o, i) => (
                    <BlockStack key={i} gap="100">
                      <InlineStack gap="200">
                        <Badge tone="attention">{`${o.percentile}%`}</Badge>
                        <Text as="p" fontWeight="semibold">{o.metric}</Text>
                      </InlineStack>
                      <Text as="p" tone="subdued" variant="bodySm">{o.recommendation}</Text>
                    </BlockStack>
                  ))}
                </BlockStack>
              )}
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Detailed Metrics */}
        <Layout.Section>
          <Card>
            <BlockStack gap="300">
              <Text as="h3" variant="headingMd">All Metrics</Text>
              <DataTable
                columnContentTypes={['text', 'numeric', 'numeric', 'text']}
                headings={['Metric', 'Your Value', 'Industry Median', 'Percentile']}
                rows={Object.entries(metrics).map(([key, m]) => [
                  m.name,
                  m.your_value !== null ? m.your_value.toLocaleString() : 'N/A',
                  m.p50?.toLocaleString() || 'N/A',
                  m.percentile !== null ? (
                    <Badge tone={m.percentile >= 50 ? 'success' : 'attention'}>
                      {`${m.percentile}%`}
                    </Badge>
                  ) : (
                    'N/A'
                  ),
                ])}
              />
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Recommendations */}
        {recommendations.length > 0 && (
          <Layout.Section>
            <Card>
              <BlockStack gap="300">
                <Text as="h3" variant="headingMd">Recommendations</Text>
                <BlockStack gap="200">
                  {recommendations.map((rec, i) => (
                    <Card key={i}>
                      <Text as="p">{rec}</Text>
                    </Card>
                  ))}
                </BlockStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        )}

        {/* Category Filter */}
        <Layout.Section variant="oneThird">
          <Card>
            <BlockStack gap="300">
              <Text as="h3" variant="headingMd">Industry Comparison</Text>
              <Select
                label="Compare against"
                options={[
                  { label: 'All Stores', value: '' },
                  { label: 'Sports Cards', value: 'sports_cards' },
                  { label: 'Pokemon TCG', value: 'pokemon' },
                  { label: 'Magic: The Gathering', value: 'mtg' },
                  { label: 'Collectibles', value: 'collectibles' },
                  { label: 'General Retail', value: 'general_retail' },
                ]}
                value={category}
                onChange={setCategory}
              />
              <Text as="p" variant="bodySm" tone="subdued">
                Narrow down benchmarks to stores in your industry for more relevant comparisons.
              </Text>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>
    </Page>
  );
}

export default EmbeddedBenchmarks;
