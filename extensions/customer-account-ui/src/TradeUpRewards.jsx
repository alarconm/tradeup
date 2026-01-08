/**
 * TradeUp Rewards - Customer Account Extension
 *
 * Displays member tier status, store credit balance, trade-in history,
 * and referral program info in the Shopify customer account page.
 */
import {
  reactExtension,
  useApi,
  useCustomer,
  Card,
  BlockStack,
  InlineStack,
  Text,
  Badge,
  Divider,
  Icon,
  Heading,
  SkeletonText,
  Banner,
  List,
  ListItem,
  Link,
  useSettings,
  Button,
  TextField,
} from '@shopify/ui-extensions-react/customer-account';
import { useState, useEffect, useCallback } from 'react';

// Extension entry point
export default reactExtension(
  'customer-account.order-index.block.render',
  () => <TradeUpRewards />
);

// Also render in profile
reactExtension(
  'customer-account.profile.block.render',
  () => <TradeUpRewards />
);

function TradeUpRewards() {
  const { shop, sessionToken } = useApi();
  const customer = useCustomer();
  const settings = useSettings();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    async function fetchData() {
      if (!customer?.id) {
        setLoading(false);
        return;
      }

      try {
        // Get session token for authenticated request
        const token = await sessionToken.get();

        // Extract numeric customer ID from GID
        const customerId = customer.id.replace('gid://shopify/Customer/', '');

        // Fetch member data from TradeUp API
        const response = await fetch(
          `https://app.cardflowlabs.com/api/customer/extension/data`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`,
              'X-Shop-Domain': shop.domain,
            },
            body: JSON.stringify({
              customer_id: customerId,
              shop: shop.domain,
            }),
          }
        );

        if (!response.ok) {
          throw new Error('Failed to fetch rewards data');
        }

        const result = await response.json();
        setData(result);
      } catch (err) {
        console.error('TradeUp Extension Error:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [customer?.id, sessionToken, shop.domain]);

  const handleCopyCode = useCallback(async () => {
    if (!data?.referral?.referral_code) return;

    try {
      await navigator.clipboard.writeText(data.referral.share_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Copy failed:', err);
    }
  }, [data?.referral]);

  const handleShare = useCallback((platform) => {
    if (!data?.referral?.share_url) return;

    const shareUrl = encodeURIComponent(data.referral.share_url);
    const text = encodeURIComponent(
      `Join me and we'll both get store credit! Use my referral code: ${data.referral.referral_code}`
    );

    const urls = {
      facebook: `https://www.facebook.com/sharer/sharer.php?u=${shareUrl}`,
      twitter: `https://twitter.com/intent/tweet?text=${text}&url=${shareUrl}`,
      whatsapp: `https://wa.me/?text=${text}%20${shareUrl}`,
      email: `mailto:?subject=${encodeURIComponent('Join me and get store credit!')}&body=${text}%20${shareUrl}`
    };

    if (urls[platform]) {
      window.open(urls[platform], '_blank');
    }
  }, [data?.referral]);

  // Loading state
  if (loading) {
    return (
      <Card>
        <BlockStack spacing="loose">
          <Heading level={2}>TradeUp Rewards</Heading>
          <SkeletonText lines={3} />
        </BlockStack>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card>
        <Banner status="warning" title="Could not load rewards">
          <Text>Unable to load your rewards information. Please try again later.</Text>
        </Banner>
      </Card>
    );
  }

  // Not a member
  if (!data?.is_member) {
    return (
      <Card>
        <BlockStack spacing="loose">
          <Heading level={2}>TradeUp Rewards</Heading>
          <Text>
            Join our rewards program to earn bonus store credit on trade-ins!
          </Text>
          <Text appearance="subdued">
            Make a purchase to automatically enroll.
          </Text>
        </BlockStack>
      </Card>
    );
  }

  // Member view
  const { member, stats, recent_trade_ins, referral } = data;

  return (
    <Card>
      <BlockStack spacing="loose">
        {/* Header */}
        <InlineStack spacing="loose" blockAlignment="center">
          <Heading level={2}>TradeUp Rewards</Heading>
          {member.tier && (
            <Badge tone="success">{member.tier.name}</Badge>
          )}
        </InlineStack>

        <Divider />

        {/* Member Info */}
        <BlockStack spacing="tight">
          <InlineStack spacing="base" blockAlignment="center">
            <Text appearance="subdued">Member #:</Text>
            <Text emphasis="bold">{member.member_number}</Text>
          </InlineStack>

          {member.tier && (
            <>
              {member.tier.trade_in_bonus_pct > 0 && (
                <InlineStack spacing="base" blockAlignment="center">
                  <Text appearance="subdued">Trade-in Bonus:</Text>
                  <Text emphasis="bold" tone="success">
                    +{member.tier.trade_in_bonus_pct}%
                  </Text>
                </InlineStack>
              )}
              {member.tier.purchase_cashback_pct > 0 && (
                <InlineStack spacing="base" blockAlignment="center">
                  <Text appearance="subdued">Purchase Cashback:</Text>
                  <Text emphasis="bold" tone="success">
                    {member.tier.purchase_cashback_pct}%
                  </Text>
                </InlineStack>
              )}
              {member.tier.monthly_credit_amount > 0 && (
                <InlineStack spacing="base" blockAlignment="center">
                  <Text appearance="subdued">Monthly Credit:</Text>
                  <Text emphasis="bold" tone="success">
                    ${member.tier.monthly_credit_amount.toFixed(2)}
                  </Text>
                </InlineStack>
              )}
            </>
          )}
        </BlockStack>

        <Divider />

        {/* Stats */}
        <BlockStack spacing="tight">
          <Text emphasis="bold">Your Stats</Text>

          <InlineStack spacing="loose">
            <BlockStack spacing="extraTight">
              <Text appearance="subdued" size="small">Store Credit</Text>
              <Text emphasis="bold" size="large">
                ${stats.store_credit_balance.toFixed(2)}
              </Text>
            </BlockStack>

            <BlockStack spacing="extraTight">
              <Text appearance="subdued" size="small">Trade-ins</Text>
              <Text emphasis="bold" size="large">
                {stats.total_trade_ins}
              </Text>
            </BlockStack>

            <BlockStack spacing="extraTight">
              <Text appearance="subdued" size="small">Bonus Earned</Text>
              <Text emphasis="bold" size="large" tone="success">
                ${stats.total_bonus_earned.toFixed(2)}
              </Text>
            </BlockStack>
          </InlineStack>
        </BlockStack>

        {/* Referral Program */}
        {referral?.program_active && (
          <>
            <Divider />

            <BlockStack spacing="tight">
              <InlineStack spacing="loose" blockAlignment="center">
                <Text emphasis="bold">Refer Friends</Text>
                <Badge tone="info">
                  Give ${referral.rewards?.referred_amount}, Get ${referral.rewards?.referrer_amount}
                </Badge>
              </InlineStack>

              <Text appearance="subdued" size="small">
                Share your code and you both earn store credit!
              </Text>

              <BlockStack spacing="tight">
                <InlineStack spacing="base" blockAlignment="center">
                  <Text appearance="subdued">Your Code:</Text>
                  <Text emphasis="bold" size="large">
                    {referral.referral_code}
                  </Text>
                  <Button
                    kind={copied ? 'secondary' : 'primary'}
                    onPress={handleCopyCode}
                  >
                    {copied ? 'Copied!' : 'Copy Link'}
                  </Button>
                </InlineStack>

                <InlineStack spacing="tight">
                  <Button kind="secondary" onPress={() => handleShare('email')}>
                    Email
                  </Button>
                  <Button kind="secondary" onPress={() => handleShare('whatsapp')}>
                    WhatsApp
                  </Button>
                  <Button kind="secondary" onPress={() => handleShare('twitter')}>
                    Tweet
                  </Button>
                </InlineStack>
              </BlockStack>

              {(referral.referral_count > 0 || referral.referral_earnings > 0) && (
                <InlineStack spacing="loose">
                  <BlockStack spacing="extraTight">
                    <Text appearance="subdued" size="small">Friends Referred</Text>
                    <Text emphasis="bold" size="large">
                      {referral.referral_count}
                    </Text>
                  </BlockStack>
                  <BlockStack spacing="extraTight">
                    <Text appearance="subdued" size="small">Rewards Earned</Text>
                    <Text emphasis="bold" size="large" tone="success">
                      ${referral.referral_earnings.toFixed(2)}
                    </Text>
                  </BlockStack>
                </InlineStack>
              )}
            </BlockStack>
          </>
        )}

        {/* Trade-in History */}
        {settings.show_trade_history !== false && recent_trade_ins?.length > 0 && (
          <>
            <Divider />

            <BlockStack spacing="tight">
              <Text emphasis="bold">Recent Trade-ins</Text>

              <List>
                {recent_trade_ins.map((tradeIn) => (
                  <ListItem key={tradeIn.batch_reference}>
                    <InlineStack spacing="loose" blockAlignment="center">
                      <Text>{tradeIn.batch_reference}</Text>
                      <Badge
                        tone={tradeIn.status === 'completed' ? 'success' : 'info'}
                      >
                        {tradeIn.status}
                      </Badge>
                      <Text>${tradeIn.trade_value.toFixed(2)}</Text>
                      {tradeIn.bonus_amount > 0 && (
                        <Text tone="success">
                          +${tradeIn.bonus_amount.toFixed(2)} bonus
                        </Text>
                      )}
                    </InlineStack>
                  </ListItem>
                ))}
              </List>
            </BlockStack>
          </>
        )}

        {/* Tier Benefits */}
        {member.tier?.benefits && Object.keys(member.tier.benefits).length > 0 && (
          <>
            <Divider />

            <BlockStack spacing="tight">
              <Text emphasis="bold">Your {member.tier.name} Benefits</Text>

              <List>
                {member.tier.benefits.discount_percent && (
                  <ListItem>
                    <InlineStack spacing="tight" blockAlignment="center">
                      <Icon source="discount" />
                      <Text>{member.tier.benefits.discount_percent}% discount on purchases</Text>
                    </InlineStack>
                  </ListItem>
                )}
                {member.tier.benefits.free_shipping && (
                  <ListItem>
                    <InlineStack spacing="tight" blockAlignment="center">
                      <Icon source="delivery" />
                      <Text>Free shipping on all orders</Text>
                    </InlineStack>
                  </ListItem>
                )}
                {member.tier.benefits.free_shipping_threshold && (
                  <ListItem>
                    <InlineStack spacing="tight" blockAlignment="center">
                      <Icon source="delivery" />
                      <Text>
                        Free shipping on orders over ${member.tier.benefits.free_shipping_threshold}
                      </Text>
                    </InlineStack>
                  </ListItem>
                )}
                {member.tier.benefits.priority_support && (
                  <ListItem>
                    <InlineStack spacing="tight" blockAlignment="center">
                      <Icon source="chat" />
                      <Text>Priority customer support</Text>
                    </InlineStack>
                  </ListItem>
                )}
                {member.tier.benefits.early_access && (
                  <ListItem>
                    <InlineStack spacing="tight" blockAlignment="center">
                      <Icon source="star" />
                      <Text>Early access to new products</Text>
                    </InlineStack>
                  </ListItem>
                )}
              </List>
            </BlockStack>
          </>
        )}
      </BlockStack>
    </Card>
  );
}
