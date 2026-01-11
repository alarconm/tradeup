/**
 * CustomerJourneyPreview - Preview of customer experience
 *
 * Shows merchants what their customers will see and experience
 * when interacting with the loyalty program.
 */

import {
  Modal,
  BlockStack,
  Text,
  Card,
  InlineStack,
  Box,
  Badge,
  Divider,
  Button,
  Tabs,
  Banner,
} from '@shopify/polaris';
import { useState } from 'react';

interface CustomerJourneyPreviewProps {
  open: boolean;
  onClose: () => void;
  tierName?: string;
  tradeInBonus?: number;
  storeCreditBalance?: number;
}

export function CustomerJourneyPreview({
  open,
  onClose,
  tierName = 'Gold',
  tradeInBonus = 15,
  storeCreditBalance = 75.00,
}: CustomerJourneyPreviewProps) {
  const [selectedTab, setSelectedTab] = useState(0);

  const tabs = [
    { id: 'signup', content: 'Signup Flow' },
    { id: 'account', content: 'Account Page' },
    { id: 'trade-in', content: 'Trade-In' },
    { id: 'checkout', content: 'Checkout' },
  ];

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Customer Experience Preview"
      size="large"
      primaryAction={{
        content: 'Close Preview',
        onAction: onClose,
      }}
    >
      <Modal.Section>
        <BlockStack gap="400">
          <Banner tone="info">
            <p>This preview shows what your customers will see at each stage of their loyalty journey.</p>
          </Banner>

          <Tabs tabs={tabs} selected={selectedTab} onSelect={setSelectedTab}>
            <Box paddingBlockStart="400">
              {selectedTab === 0 && <SignupFlowPreview />}
              {selectedTab === 1 && (
                <AccountPagePreview
                  tierName={tierName}
                  tradeInBonus={tradeInBonus}
                  storeCreditBalance={storeCreditBalance}
                />
              )}
              {selectedTab === 2 && <TradeInFlowPreview tradeInBonus={tradeInBonus} />}
              {selectedTab === 3 && <CheckoutPreview storeCreditBalance={storeCreditBalance} />}
            </Box>
          </Tabs>
        </BlockStack>
      </Modal.Section>
    </Modal>
  );
}

// Signup flow preview
function SignupFlowPreview() {
  return (
    <BlockStack gap="400">
      <Text as="h3" variant="headingMd">What customers see when joining</Text>

      {/* Mock signup card */}
      <Card>
        <BlockStack gap="400">
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <Text as="h2" variant="headingLg">Join Our Loyalty Program</Text>
            <Box paddingBlockStart="200">
              <Text as="p" variant="bodyMd" tone="subdued">
                Earn rewards on every purchase and trade-in
              </Text>
            </Box>
          </div>

          <Divider />

          <BlockStack gap="300">
            <Text as="h4" variant="headingSm">Member Benefits:</Text>
            <InlineStack gap="200">
              <Badge tone="success">Trade-In Bonuses</Badge>
              <Badge tone="success">Exclusive Offers</Badge>
              <Badge tone="success">Early Access</Badge>
            </InlineStack>
          </BlockStack>

          <div style={{ textAlign: 'center' }}>
            <Button variant="primary" disabled>
              Join Now - It's Free!
            </Button>
          </div>
        </BlockStack>
      </Card>

      <Text as="p" variant="bodySm" tone="subdued">
        Customers can join through your storefront signup block or be added manually.
      </Text>
    </BlockStack>
  );
}

// Account page preview
function AccountPagePreview({
  tierName,
  tradeInBonus,
  storeCreditBalance,
}: {
  tierName: string;
  tradeInBonus: number;
  storeCreditBalance: number;
}) {
  return (
    <BlockStack gap="400">
      <Text as="h3" variant="headingMd">Customer Account Dashboard</Text>

      {/* Mock account section */}
      <Card>
        <BlockStack gap="400">
          <InlineStack align="space-between" blockAlign="center">
            <BlockStack gap="100">
              <Text as="h2" variant="headingLg">Your Rewards</Text>
              <InlineStack gap="200">
                <Badge tone="success">{`${tierName} Member`}</Badge>
                <Badge tone="info">{`${tradeInBonus}% Trade-In Bonus`}</Badge>
              </InlineStack>
            </BlockStack>
            <div style={{ textAlign: 'right' }}>
              <Text as="p" variant="bodySm" tone="subdued">Store Credit</Text>
              <Text as="p" variant="headingXl" fontWeight="bold">
                ${storeCreditBalance.toFixed(2)}
              </Text>
            </div>
          </InlineStack>

          <Divider />

          {/* Stats */}
          <InlineStack gap="400">
            <BlockStack gap="050">
              <Text as="p" variant="bodySm" tone="subdued">Total Earned</Text>
              <Text as="p" variant="headingMd">$245.00</Text>
            </BlockStack>
            <BlockStack gap="050">
              <Text as="p" variant="bodySm" tone="subdued">Trade-Ins</Text>
              <Text as="p" variant="headingMd">8</Text>
            </BlockStack>
            <BlockStack gap="050">
              <Text as="p" variant="bodySm" tone="subdued">Member Since</Text>
              <Text as="p" variant="headingMd">Jan 2025</Text>
            </BlockStack>
          </InlineStack>

          <Button disabled>Start a Trade-In</Button>
        </BlockStack>
      </Card>

      <Text as="p" variant="bodySm" tone="subdued">
        This appears in the customer's account page via the Customer Account UI extension.
      </Text>
    </BlockStack>
  );
}

// Trade-in flow preview
function TradeInFlowPreview({ tradeInBonus }: { tradeInBonus: number }) {
  const baseValue = 100;
  const bonusAmount = baseValue * (tradeInBonus / 100);
  const totalValue = baseValue + bonusAmount;

  return (
    <BlockStack gap="400">
      <Text as="h3" variant="headingMd">Trade-In Experience</Text>

      {/* Mock trade-in summary */}
      <Card>
        <BlockStack gap="400">
          <Text as="h2" variant="headingLg">Trade-In Summary</Text>

          {/* Items */}
          <Card>
            <InlineStack align="space-between">
              <BlockStack gap="050">
                <Text as="p" variant="bodyMd" fontWeight="semibold">2023 Topps Chrome Box</Text>
                <Text as="p" variant="bodySm" tone="subdued">Sports Cards - Sealed</Text>
              </BlockStack>
              <Text as="p" variant="bodyMd">${baseValue.toFixed(2)}</Text>
            </InlineStack>
          </Card>

          <Divider />

          {/* Calculation */}
          <BlockStack gap="200">
            <InlineStack align="space-between">
              <Text as="span" variant="bodyMd">Base Value</Text>
              <Text as="span" variant="bodyMd">${baseValue.toFixed(2)}</Text>
            </InlineStack>
            <InlineStack align="space-between">
              <InlineStack gap="200">
                <Text as="span" variant="bodyMd">Member Bonus</Text>
                <Badge tone="success">{`${tradeInBonus}%`}</Badge>
              </InlineStack>
              <Text as="span" variant="bodyMd" tone="success">+${bonusAmount.toFixed(2)}</Text>
            </InlineStack>
            <Divider />
            <InlineStack align="space-between">
              <Text as="span" variant="headingMd" fontWeight="bold">Total Store Credit</Text>
              <Text as="span" variant="headingMd" fontWeight="bold">${totalValue.toFixed(2)}</Text>
            </InlineStack>
          </BlockStack>

          <Banner tone="success">
            <p>Your member bonus saved you ${bonusAmount.toFixed(2)} on this trade-in!</p>
          </Banner>
        </BlockStack>
      </Card>

      <Text as="p" variant="bodySm" tone="subdued">
        Members see their tier bonus applied automatically during trade-in.
      </Text>
    </BlockStack>
  );
}

// Checkout preview
function CheckoutPreview({ storeCreditBalance }: { storeCreditBalance: number }) {
  const orderTotal = 125.00;
  const creditUsed = Math.min(storeCreditBalance, orderTotal);
  const remaining = orderTotal - creditUsed;

  return (
    <BlockStack gap="400">
      <Text as="h3" variant="headingMd">Checkout with Store Credit</Text>

      {/* Mock checkout */}
      <Card>
        <BlockStack gap="400">
          <Text as="h2" variant="headingLg">Order Summary</Text>

          <BlockStack gap="200">
            <InlineStack align="space-between">
              <Text as="span" variant="bodyMd">Subtotal</Text>
              <Text as="span" variant="bodyMd">${orderTotal.toFixed(2)}</Text>
            </InlineStack>
            <InlineStack align="space-between">
              <InlineStack gap="200">
                <Text as="span" variant="bodyMd">Store Credit Applied</Text>
                <Badge tone="success">{`Available: $${storeCreditBalance.toFixed(2)}`}</Badge>
              </InlineStack>
              <Text as="span" variant="bodyMd" tone="success">-${creditUsed.toFixed(2)}</Text>
            </InlineStack>
            <Divider />
            <InlineStack align="space-between">
              <Text as="span" variant="headingMd" fontWeight="bold">Amount Due</Text>
              <Text as="span" variant="headingMd" fontWeight="bold">${remaining.toFixed(2)}</Text>
            </InlineStack>
          </BlockStack>

          {remaining === 0 ? (
            <Banner tone="success">
              <p>This order is fully covered by store credit!</p>
            </Banner>
          ) : (
            <Text as="p" variant="bodySm" tone="subdued">
              Store credit is automatically applied at checkout in Shopify.
            </Text>
          )}
        </BlockStack>
      </Card>

      <Text as="p" variant="bodySm" tone="subdued">
        Store credit integrates with Shopify's native store credit system.
      </Text>
    </BlockStack>
  );
}

// Button to open the preview
export function PreviewJourneyButton({ onClick }: { onClick: () => void }) {
  return (
    <Button onClick={onClick} variant="plain">
      Preview Customer Experience
    </Button>
  );
}
