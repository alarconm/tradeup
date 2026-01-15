/**
 * Demo Store Viewer Component
 *
 * Provides an interactive demo experience for merchants
 * to preview TradeUp features before installing.
 *
 * Uses mock data to simulate a real store environment.
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
  List,
  Tabs,
  DataTable,
  ProgressBar,
  BlockStack,
  InlineStack,
  Box,
} from '@shopify/polaris';

// Mock data for demo
const DEMO_MEMBERS = [
  {
    id: 1,
    memberNumber: 'TU1001',
    name: 'Sarah Johnson',
    email: 'sarah@example.com',
    tier: 'Gold',
    creditBalance: 150.00,
    pointsBalance: 2500,
    tradeIns: 8,
  },
  {
    id: 2,
    memberNumber: 'TU1002',
    name: 'Mike Chen',
    email: 'mike@example.com',
    tier: 'Silver',
    creditBalance: 75.50,
    pointsBalance: 1200,
    tradeIns: 4,
  },
  {
    id: 3,
    memberNumber: 'TU1003',
    name: 'Emma Williams',
    email: 'emma@example.com',
    tier: 'Bronze',
    creditBalance: 25.00,
    pointsBalance: 450,
    tradeIns: 2,
  },
];

const DEMO_TIERS = [
  { name: 'Bronze', bonus: 0, minSpend: 0, members: 150 },
  { name: 'Silver', bonus: 5, minSpend: 500, members: 75 },
  { name: 'Gold', bonus: 10, minSpend: 1500, members: 25 },
  { name: 'Platinum', bonus: 15, minSpend: 5000, members: 10 },
];

const DEMO_STATS = {
  totalMembers: 260,
  activeMembers: 180,
  totalCreditIssued: 12500,
  tradeInsThisMonth: 45,
  averageTradeValue: 85,
  redemptionRate: 68,
};

interface DemoStoreViewerProps {
  onStartTrial?: () => void;
}

export default function DemoStoreViewer({ onStartTrial }: DemoStoreViewerProps) {
  const [selectedTab, setSelectedTab] = useState(0);

  const tabs = [
    { id: 'dashboard', content: 'Dashboard', panelID: 'dashboard-panel' },
    { id: 'members', content: 'Members', panelID: 'members-panel' },
    { id: 'tiers', content: 'Tiers', panelID: 'tiers-panel' },
    { id: 'analytics', content: 'Analytics', panelID: 'analytics-panel' },
  ];

  const renderDashboard = () => (
    <BlockStack gap="400">
      <Layout>
        <Layout.Section variant="oneThird">
          <Card>
            <BlockStack gap="200">
              <Text as="h3" variant="headingMd">Total Members</Text>
              <Text as="p" variant="heading2xl">{DEMO_STATS.totalMembers}</Text>
              <Badge tone="success">+12% this month</Badge>
            </BlockStack>
          </Card>
        </Layout.Section>
        <Layout.Section variant="oneThird">
          <Card>
            <BlockStack gap="200">
              <Text as="h3" variant="headingMd">Credit Issued</Text>
              <Text as="p" variant="heading2xl">${DEMO_STATS.totalCreditIssued.toLocaleString()}</Text>
              <Badge tone="info">Lifetime</Badge>
            </BlockStack>
          </Card>
        </Layout.Section>
        <Layout.Section variant="oneThird">
          <Card>
            <BlockStack gap="200">
              <Text as="h3" variant="headingMd">Trade-Ins</Text>
              <Text as="p" variant="heading2xl">{DEMO_STATS.tradeInsThisMonth}</Text>
              <Badge>This month</Badge>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>

      <Card>
        <BlockStack gap="300">
          <Text as="h3" variant="headingMd">Recent Activity</Text>
          <List type="bullet">
            <List.Item>Sarah Johnson redeemed $50 store credit (2 min ago)</List.Item>
            <List.Item>New member Mike Chen enrolled (15 min ago)</List.Item>
            <List.Item>Trade-in #TI-2045 completed - $125 credit issued (1 hour ago)</List.Item>
            <List.Item>Emma Williams upgraded to Silver tier (2 hours ago)</List.Item>
          </List>
        </BlockStack>
      </Card>
    </BlockStack>
  );

  const renderMembers = () => (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between">
          <Text as="h3" variant="headingMd">Members</Text>
          <Button disabled>Add Member</Button>
        </InlineStack>
        <DataTable
          columnContentTypes={['text', 'text', 'text', 'numeric', 'numeric', 'numeric']}
          headings={['Member #', 'Name', 'Tier', 'Credit', 'Points', 'Trade-Ins']}
          rows={DEMO_MEMBERS.map(m => [
            m.memberNumber,
            m.name,
            <Badge key={m.id} tone={m.tier === 'Gold' ? 'success' : m.tier === 'Silver' ? 'info' : 'attention'}>
              {m.tier}
            </Badge>,
            `$${m.creditBalance.toFixed(2)}`,
            m.pointsBalance.toLocaleString(),
            m.tradeIns,
          ])}
        />
      </BlockStack>
    </Card>
  );

  const renderTiers = () => (
    <BlockStack gap="400">
      {DEMO_TIERS.map(tier => (
        <Card key={tier.name}>
          <BlockStack gap="200">
            <InlineStack align="space-between">
              <Text as="h3" variant="headingMd">{tier.name}</Text>
              <Badge>{`${tier.members} members`}</Badge>
            </InlineStack>
            <List type="bullet">
              <List.Item>Bonus: {tier.bonus}% extra on trade-ins</List.Item>
              <List.Item>Min Spend: ${tier.minSpend.toLocaleString()}</List.Item>
            </List>
          </BlockStack>
        </Card>
      ))}
    </BlockStack>
  );

  const renderAnalytics = () => (
    <BlockStack gap="400">
      <Card>
        <BlockStack gap="300">
          <Text as="h3" variant="headingMd">Program Performance</Text>
          <BlockStack gap="200">
            <InlineStack align="space-between">
              <Text as="span">Redemption Rate</Text>
              <Text as="span" variant="bodyMd">{DEMO_STATS.redemptionRate}%</Text>
            </InlineStack>
            <ProgressBar progress={DEMO_STATS.redemptionRate} tone="primary" />
          </BlockStack>
          <BlockStack gap="200">
            <InlineStack align="space-between">
              <Text as="span">Member Engagement</Text>
              <Text as="span" variant="bodyMd">72%</Text>
            </InlineStack>
            <ProgressBar progress={72} tone="success" />
          </BlockStack>
          <BlockStack gap="200">
            <InlineStack align="space-between">
              <Text as="span">Tier Advancement</Text>
              <Text as="span" variant="bodyMd">35%</Text>
            </InlineStack>
            <ProgressBar progress={35} tone="highlight" />
          </BlockStack>
        </BlockStack>
      </Card>

      <Card>
        <BlockStack gap="300">
          <Text as="h3" variant="headingMd">Key Metrics</Text>
          <DataTable
            columnContentTypes={['text', 'numeric']}
            headings={['Metric', 'Value']}
            rows={[
              ['Average Trade Value', `$${DEMO_STATS.averageTradeValue}`],
              ['Active Member Rate', '69%'],
              ['Avg Points per Member', '1,450'],
              ['Monthly Credit Issued', '$3,200'],
              ['Referral Conversion', '28%'],
            ]}
          />
        </BlockStack>
      </Card>
    </BlockStack>
  );

  return (
    <Page
      title="TradeUp Demo"
      subtitle="Preview the loyalty experience"
      primaryAction={
        onStartTrial
          ? { content: 'Start Free Trial', onAction: onStartTrial }
          : undefined
      }
    >
      <BlockStack gap="400">
        <Banner
          title="Demo Mode"
          tone="info"
        >
          <p>
            This is a preview with sample data. Install TradeUp to connect your actual store.
          </p>
        </Banner>

        <Tabs tabs={tabs} selected={selectedTab} onSelect={setSelectedTab}>
          <Box padding="400">
            {selectedTab === 0 && renderDashboard()}
            {selectedTab === 1 && renderMembers()}
            {selectedTab === 2 && renderTiers()}
            {selectedTab === 3 && renderAnalytics()}
          </Box>
        </Tabs>

        <Card>
          <BlockStack gap="300">
            <Text as="h3" variant="headingMd">Ready to get started?</Text>
            <Text as="p" variant="bodyMd">
              TradeUp helps you build customer loyalty through trade-ins, store credit,
              and tiered rewards. Start your free trial today!
            </Text>
            <InlineStack gap="200">
              {onStartTrial && (
                <Button variant="primary" onClick={onStartTrial}>
                  Start Free Trial
                </Button>
              )}
              <Button url="https://help.cardflowlabs.com" external>
                Learn More
              </Button>
            </InlineStack>
          </BlockStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
