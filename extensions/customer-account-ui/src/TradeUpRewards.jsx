/**
 * TradeUp Rewards - Customer Account Extension
 *
 * A world-class loyalty experience showing:
 * - Points balance with animated counter
 * - Points history timeline
 * - Rewards catalog with redemption
 * - Tier status and progress
 * - Referral program integration
 * - Badge showcase with progress
 *
 * @version 2.1.0
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
  View,
  Grid,
  Image,
  Pressable,
  Modal,
  TextBlock,
} from '@shopify/ui-extensions-react/customer-account';
import { useState, useEffect, useCallback, useMemo } from 'react';

// ============================================================================
// Extension Entry Points
// ============================================================================

export default reactExtension(
  'customer-account.order-index.block.render',
  () => <TradeUpRewards />
);

reactExtension(
  'customer-account.profile.block.render',
  () => <TradeUpRewards />
);

// ============================================================================
// API Configuration
// ============================================================================

const API_BASE = 'https://app.cardflowlabs.com/api';

// ============================================================================
// Main Component
// ============================================================================

function TradeUpRewards() {
  const { shop, sessionToken } = useApi();
  const customer = useCustomer();
  const settings = useSettings();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [rewardsData, setRewardsData] = useState(null);
  const [rewardsLoading, setRewardsLoading] = useState(false);
  const [historyData, setHistoryData] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedReward, setSelectedReward] = useState(null);
  const [redeeming, setRedeeming] = useState(false);
  const [redeemResult, setRedeemResult] = useState(null);
  const [copied, setCopied] = useState(false);
  const [badgesData, setBadgesData] = useState(null);
  const [badgesLoading, setBadgesLoading] = useState(false);

  // Fetch initial data
  useEffect(() => {
    async function fetchData() {
      if (!customer?.id) {
        setLoading(false);
        return;
      }

      try {
        const token = await sessionToken.get();
        const customerId = customer.id.replace('gid://shopify/Customer/', '');

        const response = await fetch(`${API_BASE}/customer/extension/data`, {
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
        });

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

  // Fetch rewards when tab is selected
  useEffect(() => {
    if (activeTab === 'rewards' && !rewardsData && data?.is_member) {
      fetchRewards();
    }
  }, [activeTab, data]);

  // Fetch history when tab is selected
  useEffect(() => {
    if (activeTab === 'history' && !historyData && data?.is_member) {
      fetchHistory();
    }
  }, [activeTab, data]);

  // Fetch badges when tab is selected
  useEffect(() => {
    if (activeTab === 'badges' && !badgesData && data?.is_member) {
      fetchBadges();
    }
  }, [activeTab, data]);

  const fetchRewards = async () => {
    if (!customer?.id) return;
    setRewardsLoading(true);

    try {
      const token = await sessionToken.get();
      const customerId = customer.id.replace('gid://shopify/Customer/', '');

      const response = await fetch(`${API_BASE}/customer/extension/rewards`, {
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
      });

      if (response.ok) {
        const result = await response.json();
        setRewardsData(result);
      }
    } catch (err) {
      console.error('Error fetching rewards:', err);
    } finally {
      setRewardsLoading(false);
    }
  };

  const fetchHistory = async () => {
    // History is already loaded in the main data call
    // Just mark as loaded with data from initial fetch
    if (data?.recent_activity) {
      setHistoryData({
        points_balance: data.points?.balance,
        tier: data.member?.tier,
        recent_activity: data.recent_activity,
      });
    }
    setHistoryLoading(false);
  };

  const fetchBadges = async () => {
    if (!customer?.id) return;
    setBadgesLoading(true);

    try {
      const token = await sessionToken.get();
      const customerId = customer.id.replace('gid://shopify/Customer/', '');

      const response = await fetch(`${API_BASE}/customer/extension/badges`, {
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
      });

      if (response.ok) {
        const result = await response.json();
        setBadgesData(result);
      }
    } catch (err) {
      console.error('Error fetching badges:', err);
    } finally {
      setBadgesLoading(false);
    }
  };

  const handleRedeemReward = async (reward) => {
    if (!customer?.id || !data?.member?.member_number) return;
    setRedeeming(true);
    setRedeemResult(null);

    try {
      const token = await sessionToken.get();
      const customerId = customer.id.replace('gid://shopify/Customer/', '');

      const response = await fetch(`${API_BASE}/customer/extension/rewards/${reward.id}/redeem`, {
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
      });

      const result = await response.json();

      if (response.ok) {
        setRedeemResult({
          success: true,
          message: result.message,
          redemption: result.redemption,
          newBalance: result.new_balance,
        });

        // Update local data
        if (data.points) {
          setData({
            ...data,
            points: { ...data.points, balance: result.new_balance },
          });
        }

        // Refresh rewards list
        fetchRewards();
      } else {
        setRedeemResult({
          success: false,
          message: result.error || 'Failed to redeem reward',
        });
      }
    } catch (err) {
      console.error('Error redeeming reward:', err);
      setRedeemResult({
        success: false,
        message: 'Something went wrong. Please try again.',
      });
    } finally {
      setRedeeming(false);
      setSelectedReward(null);
    }
  };

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
      email: `mailto:?subject=${encodeURIComponent('Join me and get store credit!')}&body=${text}%20${shareUrl}`,
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
          <SkeletonText lines={4} />
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
    return <NotMemberView />;
  }

  // Settings-based visibility (defaults to true if not set)
  const showPointsBalance = settings.show_points_balance !== false;
  const showRewardsCatalog = settings.show_rewards_catalog !== false;
  const showReferralProgram = settings.show_referral_program !== false;
  const showTierProgress = settings.show_tier_progress !== false;
  const defaultTab = settings.default_tab || 'overview';

  // Set initial tab from settings on first load
  useEffect(() => {
    if (defaultTab && ['overview', 'history', 'rewards', 'referrals'].includes(defaultTab)) {
      setActiveTab(defaultTab);
    }
  }, []);

  // Prepare tab content based on settings
  const tabs = [
    { id: 'overview', label: 'Overview' },
    showPointsBalance && { id: 'history', label: 'History' },
    showRewardsCatalog && { id: 'rewards', label: 'Rewards' },
    { id: 'badges', label: 'Badges' },
    showReferralProgram && data.referral?.program_active && { id: 'referrals', label: 'Refer Friends' },
  ].filter(Boolean);

  return (
    <Card>
      <BlockStack spacing="loose">
        {/* Header */}
        <InlineStack spacing="loose" blockAlignment="center">
          <Heading level={2}>TradeUp Rewards</Heading>
          {data.member?.tier && (
            <Badge tone="success">{data.member.tier.name}</Badge>
          )}
        </InlineStack>

        {/* Tab Navigation */}
        <TabNavigation
          tabs={tabs}
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />

        <Divider />

        {/* Tab Content */}
        {activeTab === 'overview' && (
          <OverviewTab
            data={data}
            onViewHistory={() => setActiveTab('history')}
            onViewRewards={() => setActiveTab('rewards')}
          />
        )}

        {activeTab === 'history' && (
          <HistoryTab
            data={data}
            historyData={historyData}
            loading={historyLoading}
          />
        )}

        {activeTab === 'rewards' && (
          <RewardsTab
            data={data}
            rewardsData={rewardsData}
            loading={rewardsLoading}
            onRedeem={(reward) => setSelectedReward(reward)}
            redeemResult={redeemResult}
          />
        )}

        {activeTab === 'badges' && (
          <BadgesTab
            badgesData={badgesData}
            loading={badgesLoading}
          />
        )}

        {activeTab === 'referrals' && (
          <ReferralsTab
            data={data}
            copied={copied}
            onCopyCode={handleCopyCode}
            onShare={handleShare}
          />
        )}

        {/* Redemption Confirmation Modal */}
        {selectedReward && (
          <RedemptionModal
            reward={selectedReward}
            pointsBalance={data.points?.balance || 0}
            redeeming={redeeming}
            onConfirm={() => handleRedeemReward(selectedReward)}
            onCancel={() => setSelectedReward(null)}
          />
        )}
      </BlockStack>
    </Card>
  );
}

// ============================================================================
// Tab Navigation Component
// ============================================================================

function TabNavigation({ tabs, activeTab, onTabChange }) {
  return (
    <InlineStack spacing="tight">
      {tabs.map((tab) => (
        <Button
          key={tab.id}
          kind={activeTab === tab.id ? 'primary' : 'secondary'}
          onPress={() => onTabChange(tab.id)}
        >
          {tab.label}
        </Button>
      ))}
    </InlineStack>
  );
}

// ============================================================================
// Not Member View
// ============================================================================

function NotMemberView() {
  return (
    <Card>
      <BlockStack spacing="loose">
        <Heading level={2}>TradeUp Rewards</Heading>

        <View
          padding="loose"
          background="subdued"
          borderRadius="base"
        >
          <BlockStack spacing="base">
            <Text emphasis="bold" size="large">
              Join Our Rewards Program
            </Text>
            <Text appearance="subdued">
              Earn points on every purchase and trade-in. Redeem for store credit,
              discounts, and exclusive rewards.
            </Text>

            <InlineStack spacing="loose">
              <BlockStack spacing="extraTight">
                <Text emphasis="bold" size="large">1 point</Text>
                <Text appearance="subdued" size="small">per $1 spent</Text>
              </BlockStack>
              <BlockStack spacing="extraTight">
                <Text emphasis="bold" size="large">2x points</Text>
                <Text appearance="subdued" size="small">on trade-ins</Text>
              </BlockStack>
              <BlockStack spacing="extraTight">
                <Text emphasis="bold" size="large">$5+</Text>
                <Text appearance="subdued" size="small">in rewards</Text>
              </BlockStack>
            </InlineStack>

            <Text appearance="subdued" size="small">
              Make a purchase to automatically enroll.
            </Text>
          </BlockStack>
        </View>
      </BlockStack>
    </Card>
  );
}

// ============================================================================
// Overview Tab
// ============================================================================

function OverviewTab({ data, onViewHistory, onViewRewards }) {
  const { member, stats, points, recent_trade_ins, tier_progress } = data;

  // Get tier progress from API data
  const pointsToNextTier = tier_progress?.points_to_next_tier || 0;
  const tierProgressValue = tier_progress?.progress || 0;
  const nextTierName = tier_progress?.next_tier_name || null;

  return (
    <BlockStack spacing="loose">
      {/* Points Balance Hero */}
      <View
        padding="loose"
        background="subdued"
        borderRadius="base"
      >
        <BlockStack spacing="base" inlineAlignment="center">
          <Text appearance="subdued" size="small">YOUR POINTS BALANCE</Text>
          <AnimatedPointsDisplay points={points?.balance || 0} />

          {points?.earned_this_month > 0 && (
            <Text appearance="subdued" size="small">
              +{points.earned_this_month} earned this month
            </Text>
          )}

          {points?.available_rewards > 0 && (
            <Badge tone="success">
              {points.available_rewards} reward{points.available_rewards > 1 ? 's' : ''} available
            </Badge>
          )}
        </BlockStack>
      </View>

      {/* Quick Stats Grid */}
      <Grid columns={['fill', 'fill', 'fill']} spacing="tight">
        <StatCard
          label="Store Credit"
          value={`$${(stats?.store_credit_balance || 0).toFixed(2)}`}
          tone="success"
        />
        <StatCard
          label="Trade-ins"
          value={stats?.total_trade_ins || 0}
        />
        <StatCard
          label="Bonus Earned"
          value={`$${(stats?.total_bonus_earned || 0).toFixed(2)}`}
          tone="success"
        />
      </Grid>

      {/* Tier Progress */}
      {member?.tier && (
        <>
          <Divider />
          <TierProgressCard
            tier={member.tier}
            pointsToNextTier={pointsToNextTier}
            progress={tierProgressValue}
            nextTierName={nextTierName}
          />
        </>
      )}

      {/* Quick Actions */}
      <InlineStack spacing="tight">
        <Button kind="secondary" onPress={onViewHistory}>
          View History
        </Button>
        <Button kind="primary" onPress={onViewRewards}>
          Browse Rewards
        </Button>
      </InlineStack>

      {/* Recent Activity Preview */}
      {data.recent_activity?.length > 0 && (
        <>
          <Divider />
          <BlockStack spacing="tight">
            <Text emphasis="bold">Recent Activity</Text>
            <List>
              {data.recent_activity.slice(0, 3).map((activity, index) => (
                <ListItem key={index}>
                  <ActivityItem activity={activity} />
                </ListItem>
              ))}
            </List>
            <Button kind="plain" onPress={onViewHistory}>
              View all activity
            </Button>
          </BlockStack>
        </>
      )}

      {/* Member Benefits */}
      {member?.tier && (
        <>
          <Divider />
          <MemberBenefits tier={member.tier} />
        </>
      )}
    </BlockStack>
  );
}

// ============================================================================
// History Tab
// ============================================================================

function HistoryTab({ data, historyData, loading }) {
  if (loading) {
    return (
      <BlockStack spacing="loose">
        <SkeletonText lines={6} />
      </BlockStack>
    );
  }

  const activities = historyData?.recent_activity || data.recent_activity || [];

  if (activities.length === 0) {
    return (
      <BlockStack spacing="loose" inlineAlignment="center">
        <Text appearance="subdued">No activity yet</Text>
        <Text size="small" appearance="subdued">
          Start earning points by making purchases or trade-ins.
        </Text>
      </BlockStack>
    );
  }

  return (
    <BlockStack spacing="loose">
      <Text emphasis="bold">Points History</Text>

      {/* Points Summary */}
      {historyData && (
        <View padding="base" background="subdued" borderRadius="base">
          <InlineStack spacing="loose">
            <BlockStack spacing="extraTight">
              <Text appearance="subdued" size="small">Balance</Text>
              <Text emphasis="bold" size="large">
                {historyData.points_balance?.toLocaleString() || 0}
              </Text>
            </BlockStack>
            {historyData.tier && (
              <BlockStack spacing="extraTight">
                <Text appearance="subdued" size="small">Tier Bonus</Text>
                <Text emphasis="bold" size="large" tone="success">
                  {historyData.tier.earning_multiplier}x
                </Text>
              </BlockStack>
            )}
          </InlineStack>
        </View>
      )}

      {/* Activity Timeline */}
      <BlockStack spacing="tight">
        {activities.map((activity, index) => (
          <View key={index} padding="tight" background={index % 2 === 0 ? 'subdued' : undefined} borderRadius="base">
            <ActivityItem activity={activity} detailed />
          </View>
        ))}
      </BlockStack>

      {/* Trade-in History */}
      {data.recent_trade_ins?.length > 0 && (
        <>
          <Divider />
          <Text emphasis="bold">Recent Trade-ins</Text>
          <List>
            {data.recent_trade_ins.map((tradeIn) => (
              <ListItem key={tradeIn.batch_reference}>
                <InlineStack spacing="loose" blockAlignment="center">
                  <BlockStack spacing="extraTight">
                    <Text>{tradeIn.batch_reference}</Text>
                    <Text size="small" appearance="subdued">
                      {formatDate(tradeIn.created_at)}
                    </Text>
                  </BlockStack>
                  <Badge tone={tradeIn.status === 'completed' ? 'success' : 'info'}>
                    {tradeIn.status}
                  </Badge>
                  <BlockStack spacing="extraTight" inlineAlignment="end">
                    <Text emphasis="bold">${tradeIn.trade_value.toFixed(2)}</Text>
                    {tradeIn.bonus_amount > 0 && (
                      <Text size="small" tone="success">
                        +${tradeIn.bonus_amount.toFixed(2)} bonus
                      </Text>
                    )}
                  </BlockStack>
                </InlineStack>
              </ListItem>
            ))}
          </List>
        </>
      )}
    </BlockStack>
  );
}

// ============================================================================
// Rewards Tab
// ============================================================================

function RewardsTab({ data, rewardsData, loading, onRedeem, redeemResult }) {
  const pointsBalance = data.points?.balance || rewardsData?.points_balance || 0;

  if (loading) {
    return (
      <BlockStack spacing="loose">
        <SkeletonText lines={8} />
      </BlockStack>
    );
  }

  // Show redemption result if exists
  if (redeemResult) {
    return (
      <BlockStack spacing="loose">
        <Banner
          status={redeemResult.success ? 'success' : 'warning'}
          title={redeemResult.success ? 'Reward Redeemed!' : 'Redemption Failed'}
        >
          <Text>{redeemResult.message}</Text>
          {redeemResult.success && redeemResult.redemption?.discount_code && (
            <BlockStack spacing="tight">
              <Text emphasis="bold">Your code:</Text>
              <View padding="base" background="subdued" borderRadius="base">
                <Text emphasis="bold" size="large">
                  {redeemResult.redemption.discount_code}
                </Text>
              </View>
              <Text size="small" appearance="subdued">
                Use this code at checkout
              </Text>
            </BlockStack>
          )}
        </Banner>
        <Button kind="secondary" onPress={() => window.location.reload()}>
          Continue Browsing
        </Button>
      </BlockStack>
    );
  }

  const rewards = rewardsData?.rewards || [];

  if (rewards.length === 0) {
    return (
      <BlockStack spacing="loose" inlineAlignment="center">
        <Text appearance="subdued">No rewards available right now</Text>
        <Text size="small" appearance="subdued">
          Check back soon for new rewards!
        </Text>
      </BlockStack>
    );
  }

  // Separate available and locked rewards
  const availableRewards = rewards.filter((r) => r.can_redeem);
  const lockedRewards = rewards.filter((r) => !r.can_redeem);

  return (
    <BlockStack spacing="loose">
      {/* Points Balance */}
      <View padding="base" background="subdued" borderRadius="base">
        <InlineStack spacing="loose" blockAlignment="center">
          <BlockStack spacing="extraTight">
            <Text appearance="subdued" size="small">Available Points</Text>
            <Text emphasis="bold" size="large">
              {pointsBalance.toLocaleString()}
            </Text>
          </BlockStack>
        </InlineStack>
      </View>

      {/* Available Rewards */}
      {availableRewards.length > 0 && (
        <BlockStack spacing="tight">
          <Text emphasis="bold" tone="success">
            Available to Redeem ({availableRewards.length})
          </Text>
          <Grid columns={['fill', 'fill']} spacing="tight">
            {availableRewards.map((reward) => (
              <RewardCard
                key={reward.id}
                reward={reward}
                pointsBalance={pointsBalance}
                onRedeem={() => onRedeem(reward)}
              />
            ))}
          </Grid>
        </BlockStack>
      )}

      {/* Locked Rewards */}
      {lockedRewards.length > 0 && (
        <BlockStack spacing="tight">
          <Text emphasis="bold" appearance="subdued">
            Keep Earning ({lockedRewards.length})
          </Text>
          <Grid columns={['fill', 'fill']} spacing="tight">
            {lockedRewards.map((reward) => (
              <RewardCard
                key={reward.id}
                reward={reward}
                pointsBalance={pointsBalance}
                locked
              />
            ))}
          </Grid>
        </BlockStack>
      )}
    </BlockStack>
  );
}

// ============================================================================
// Referrals Tab
// ============================================================================

function ReferralsTab({ data, copied, onCopyCode, onShare }) {
  const { referral } = data;

  if (!referral?.program_active) {
    return (
      <BlockStack spacing="loose" inlineAlignment="center">
        <Text appearance="subdued">Referral program is not currently active</Text>
      </BlockStack>
    );
  }

  return (
    <BlockStack spacing="loose">
      {/* Hero Section */}
      <View padding="loose" background="subdued" borderRadius="base">
        <BlockStack spacing="base" inlineAlignment="center">
          <Text emphasis="bold" size="large">Share & Earn</Text>
          <Text appearance="subdued">
            Share your code and you both get store credit!
          </Text>

          <InlineStack spacing="loose">
            <BlockStack spacing="extraTight" inlineAlignment="center">
              <Text emphasis="bold" size="large" tone="success">
                ${referral.rewards?.referrer_amount}
              </Text>
              <Text size="small" appearance="subdued">for you</Text>
            </BlockStack>
            <Text size="large">+</Text>
            <BlockStack spacing="extraTight" inlineAlignment="center">
              <Text emphasis="bold" size="large" tone="success">
                ${referral.rewards?.referred_amount}
              </Text>
              <Text size="small" appearance="subdued">for your friend</Text>
            </BlockStack>
          </InlineStack>
        </BlockStack>
      </View>

      {/* Referral Code */}
      <BlockStack spacing="tight">
        <Text emphasis="bold">Your Referral Code</Text>
        <View padding="base" background="subdued" borderRadius="base">
          <InlineStack spacing="loose" blockAlignment="center">
            <Text emphasis="bold" size="extraLarge">
              {referral.referral_code}
            </Text>
            <Button
              kind={copied ? 'secondary' : 'primary'}
              onPress={onCopyCode}
            >
              {copied ? 'Copied!' : 'Copy Link'}
            </Button>
          </InlineStack>
        </View>
      </BlockStack>

      {/* Share Buttons */}
      <BlockStack spacing="tight">
        <Text emphasis="bold">Share via</Text>
        <InlineStack spacing="tight">
          <Button kind="secondary" onPress={() => onShare('email')}>
            Email
          </Button>
          <Button kind="secondary" onPress={() => onShare('whatsapp')}>
            WhatsApp
          </Button>
          <Button kind="secondary" onPress={() => onShare('twitter')}>
            Tweet
          </Button>
          <Button kind="secondary" onPress={() => onShare('facebook')}>
            Facebook
          </Button>
        </InlineStack>
      </BlockStack>

      {/* Stats */}
      {(referral.referral_count > 0 || referral.referral_earnings > 0) && (
        <>
          <Divider />
          <BlockStack spacing="tight">
            <Text emphasis="bold">Your Referral Stats</Text>
            <InlineStack spacing="loose">
              <BlockStack spacing="extraTight">
                <Text emphasis="bold" size="large">
                  {referral.referral_count}
                </Text>
                <Text appearance="subdued" size="small">Friends Referred</Text>
              </BlockStack>
              <BlockStack spacing="extraTight">
                <Text emphasis="bold" size="large" tone="success">
                  ${referral.referral_earnings.toFixed(2)}
                </Text>
                <Text appearance="subdued" size="small">Credit Earned</Text>
              </BlockStack>
            </InlineStack>
          </BlockStack>
        </>
      )}

      {/* How it Works */}
      <Divider />
      <BlockStack spacing="tight">
        <Text emphasis="bold">How It Works</Text>
        <List>
          <ListItem>
            <InlineStack spacing="tight" blockAlignment="center">
              <Badge tone="info">1</Badge>
              <Text>Share your unique referral code with friends</Text>
            </InlineStack>
          </ListItem>
          <ListItem>
            <InlineStack spacing="tight" blockAlignment="center">
              <Badge tone="info">2</Badge>
              <Text>They make their first purchase using your code</Text>
            </InlineStack>
          </ListItem>
          <ListItem>
            <InlineStack spacing="tight" blockAlignment="center">
              <Badge tone="info">3</Badge>
              <Text>You both receive store credit automatically</Text>
            </InlineStack>
          </ListItem>
        </List>
      </BlockStack>
    </BlockStack>
  );
}

// ============================================================================
// Badges Tab
// ============================================================================

function BadgesTab({ badgesData, loading }) {
  if (loading) {
    return (
      <BlockStack spacing="loose">
        <SkeletonText lines={6} />
      </BlockStack>
    );
  }

  if (!badgesData) {
    return (
      <BlockStack spacing="loose" inlineAlignment="center">
        <Text appearance="subdued">Unable to load badges</Text>
      </BlockStack>
    );
  }

  const { earned_badges = [], locked_badges = [], earned_count = 0, total_badges = 0 } = badgesData;

  return (
    <BlockStack spacing="loose">
      {/* Badge Stats Summary */}
      <View padding="base" background="subdued" borderRadius="base">
        <InlineStack spacing="loose" blockAlignment="center">
          <BlockStack spacing="extraTight" inlineAlignment="center">
            <Text appearance="subdued" size="small">Badges Earned</Text>
            <Text emphasis="bold" size="large" tone="success">
              {earned_count} / {total_badges}
            </Text>
          </BlockStack>
        </InlineStack>
      </View>

      {/* Earned Badges */}
      {earned_badges.length > 0 && (
        <BlockStack spacing="tight">
          <Text emphasis="bold" tone="success">
            Earned ({earned_badges.length})
          </Text>
          <BadgeShowcase badges={earned_badges} earned />
        </BlockStack>
      )}

      {/* Locked Badges */}
      {locked_badges.length > 0 && (
        <BlockStack spacing="tight">
          <Text emphasis="bold" appearance="subdued">
            Keep Going ({locked_badges.length})
          </Text>
          <BadgeShowcase badges={locked_badges} earned={false} />
        </BlockStack>
      )}

      {/* Empty State */}
      {earned_badges.length === 0 && locked_badges.length === 0 && (
        <BlockStack spacing="loose" inlineAlignment="center">
          <Text appearance="subdued">No badges available yet</Text>
          <Text size="small" appearance="subdued">
            Keep shopping and trading to earn your first badge!
          </Text>
        </BlockStack>
      )}
    </BlockStack>
  );
}

// ============================================================================
// Badge Showcase Component
// ============================================================================

function BadgeShowcase({ badges, earned }) {
  return (
    <Grid columns={['fill', 'fill']} spacing="tight">
      {badges.map((badge) => (
        <BadgeCard key={badge.id} badge={badge} earned={earned} />
      ))}
    </Grid>
  );
}

function BadgeCard({ badge, earned }) {
  // Map icon names to display emojis (since Shopify extensions have limited icon support)
  const iconMap = {
    'trophy': '\uD83C\uDFC6',
    'star': '\u2B50',
    'medal': '\uD83C\uDFC5',
    'cart': '\uD83D\uDED2',
    'exchange': '\uD83D\uDD04',
    'users': '\uD83D\uDC65',
    'coins': '\uD83E\uDE99',
    'gem': '\uD83D\uDC8E',
    'calendar': '\uD83D\uDCC5',
    'flame': '\uD83D\uDD25',
    'fire': '\uD83D\uDD25',
    'wallet': '\uD83D\uDCB0',
    'crown': '\uD83D\uDC51',
    'gift': '\uD83C\uDF81',
  };

  const iconEmoji = iconMap[badge.icon] || '\uD83C\uDFC6';

  return (
    <View
      padding="base"
      background={earned ? undefined : 'subdued'}
      borderRadius="base"
      border="base"
    >
      <BlockStack spacing="tight">
        {/* Badge Icon and Name */}
        <InlineStack spacing="tight" blockAlignment="center">
          <Text size="extraLarge">{iconEmoji}</Text>
          <BlockStack spacing="extraTight">
            <Text emphasis="bold">{badge.name}</Text>
            {earned && badge.earned_at && (
              <Text size="small" appearance="subdued">
                Earned {formatDate(badge.earned_at)}
              </Text>
            )}
          </BlockStack>
        </InlineStack>

        {/* Description */}
        {badge.description && (
          <Text size="small" appearance="subdued">
            {badge.description}
          </Text>
        )}

        {/* Progress Bar for Locked Badges */}
        {!earned && badge.progress_percentage < 100 && (
          <BlockStack spacing="tight">
            <View border="base" cornerRadius="base" padding="none">
              <View
                background="interactive"
                padding="tight"
                blockSize={8}
                inlineSize={`${badge.progress_percentage}%`}
              />
            </View>
            <Text size="small" appearance="subdued">
              {badge.progress} / {badge.progress_max} ({badge.progress_percentage}%)
            </Text>
          </BlockStack>
        )}

        {/* Reward Info */}
        {badge.points_reward > 0 && (
          <InlineStack spacing="tight" blockAlignment="center">
            <Badge tone={earned ? 'success' : 'info'}>
              +{badge.points_reward} pts
            </Badge>
          </InlineStack>
        )}
      </BlockStack>
    </View>
  );
}

// ============================================================================
// Sub-Components
// ============================================================================

function AnimatedPointsDisplay({ points }) {
  // In a real implementation, you could animate this with requestAnimationFrame
  // For now, we just display the formatted number
  return (
    <Text emphasis="bold" size="extraLarge">
      {points.toLocaleString()} points
    </Text>
  );
}

function StatCard({ label, value, tone }) {
  return (
    <View padding="tight" background="subdued" borderRadius="base">
      <BlockStack spacing="extraTight" inlineAlignment="center">
        <Text appearance="subdued" size="small">{label}</Text>
        <Text emphasis="bold" size="large" tone={tone}>
          {value}
        </Text>
      </BlockStack>
    </View>
  );
}

function TierProgressCard({ tier, pointsToNextTier, progress, nextTierName }) {
  return (
    <BlockStack spacing="tight">
      <InlineStack spacing="loose" blockAlignment="center">
        <Text emphasis="bold">Your Tier: {tier.name}</Text>
        {tier.trade_in_bonus_pct > 0 && (
          <Badge tone="success">+{tier.trade_in_bonus_pct}% trade-in bonus</Badge>
        )}
      </InlineStack>

      {pointsToNextTier > 0 && nextTierName && (
        <BlockStack spacing="tight">
          <View border="base" cornerRadius="base" padding="none">
            <View background="interactive" padding="tight" blockSize={8} inlineSize={`${Math.round(progress * 100)}%`} />
          </View>
          <Text size="small" appearance="subdued">
            {pointsToNextTier.toLocaleString()} points to reach {nextTierName}
          </Text>
        </BlockStack>
      )}

      {!nextTierName && (
        <Text size="small" tone="success">
          You're at the highest tier - enjoy all benefits!
        </Text>
      )}
    </BlockStack>
  );
}

function ActivityItem({ activity, detailed }) {
  const isPositive = activity.points > 0;

  return (
    <InlineStack spacing="loose" blockAlignment="center">
      <BlockStack spacing="extraTight">
        <Text size={detailed ? 'medium' : 'small'}>
          {activity.description || getActivityDescription(activity)}
        </Text>
        {detailed && activity.date && (
          <Text size="small" appearance="subdued">
            {formatDate(activity.date)}
          </Text>
        )}
      </BlockStack>
      <Text
        emphasis="bold"
        tone={isPositive ? 'success' : undefined}
      >
        {isPositive ? '+' : ''}{activity.points}
      </Text>
    </InlineStack>
  );
}

function RewardCard({ reward, pointsBalance, onRedeem, locked }) {
  const pointsNeeded = Math.max(0, reward.points_cost - pointsBalance);

  return (
    <View
      padding="base"
      background={locked ? 'subdued' : undefined}
      borderRadius="base"
      border="base"
    >
      <BlockStack spacing="tight">
        {reward.image_url && (
          <Image
            source={reward.image_url}
            fit="cover"
            aspectRatio={1.5}
            borderRadius="base"
          />
        )}

        <Text emphasis="bold">{reward.name}</Text>

        {reward.description && (
          <Text size="small" appearance="subdued">
            {reward.description}
          </Text>
        )}

        <InlineStack spacing="loose" blockAlignment="center">
          <Text emphasis="bold" tone={locked ? undefined : 'success'}>
            {reward.points_cost.toLocaleString()} pts
          </Text>

          {!reward.in_stock && (
            <Badge tone="warning">Out of stock</Badge>
          )}
        </InlineStack>

        {locked ? (
          <Text size="small" appearance="subdued">
            Need {pointsNeeded.toLocaleString()} more points
          </Text>
        ) : (
          <Button
            kind="primary"
            disabled={!reward.can_redeem || !reward.in_stock}
            onPress={onRedeem}
          >
            Redeem Now
          </Button>
        )}
      </BlockStack>
    </View>
  );
}

function RedemptionModal({ reward, pointsBalance, redeeming, onConfirm, onCancel }) {
  return (
    <Modal
      id="redeem-confirmation"
      title="Confirm Redemption"
      open={true}
      onClose={onCancel}
    >
      <BlockStack spacing="loose" padding="loose">
        <Text emphasis="bold" size="large">{reward.name}</Text>

        {reward.description && (
          <Text appearance="subdued">{reward.description}</Text>
        )}

        <Divider />

        <InlineStack spacing="loose">
          <BlockStack spacing="extraTight">
            <Text appearance="subdued" size="small">Points Required</Text>
            <Text emphasis="bold">{reward.points_cost.toLocaleString()}</Text>
          </BlockStack>
          <BlockStack spacing="extraTight">
            <Text appearance="subdued" size="small">Your Balance</Text>
            <Text emphasis="bold">{pointsBalance.toLocaleString()}</Text>
          </BlockStack>
          <BlockStack spacing="extraTight">
            <Text appearance="subdued" size="small">After Redemption</Text>
            <Text emphasis="bold" tone="success">
              {(pointsBalance - reward.points_cost).toLocaleString()}
            </Text>
          </BlockStack>
        </InlineStack>

        <Divider />

        <InlineStack spacing="tight">
          <Button kind="secondary" onPress={onCancel} disabled={redeeming}>
            Cancel
          </Button>
          <Button kind="primary" onPress={onConfirm} loading={redeeming}>
            {redeeming ? 'Redeeming...' : 'Confirm Redemption'}
          </Button>
        </InlineStack>
      </BlockStack>
    </Modal>
  );
}

function MemberBenefits({ tier }) {
  const benefits = tier.benefits || {};

  return (
    <BlockStack spacing="tight">
      <Text emphasis="bold">Your {tier.name} Benefits</Text>
      <List>
        {tier.trade_in_bonus_pct > 0 && (
          <ListItem>
            <InlineStack spacing="tight" blockAlignment="center">
              <Icon source="discount" />
              <Text>+{tier.trade_in_bonus_pct}% bonus on all trade-ins</Text>
            </InlineStack>
          </ListItem>
        )}
        {tier.purchase_cashback_pct > 0 && (
          <ListItem>
            <InlineStack spacing="tight" blockAlignment="center">
              <Icon source="discount" />
              <Text>{tier.purchase_cashback_pct}% cashback on purchases</Text>
            </InlineStack>
          </ListItem>
        )}
        {tier.monthly_credit_amount > 0 && (
          <ListItem>
            <InlineStack spacing="tight" blockAlignment="center">
              <Icon source="gift" />
              <Text>${tier.monthly_credit_amount.toFixed(2)} monthly credit</Text>
            </InlineStack>
          </ListItem>
        )}
        {benefits.discount_percent && (
          <ListItem>
            <InlineStack spacing="tight" blockAlignment="center">
              <Icon source="discount" />
              <Text>{benefits.discount_percent}% discount on purchases</Text>
            </InlineStack>
          </ListItem>
        )}
        {benefits.free_shipping && (
          <ListItem>
            <InlineStack spacing="tight" blockAlignment="center">
              <Icon source="delivery" />
              <Text>Free shipping on all orders</Text>
            </InlineStack>
          </ListItem>
        )}
        {benefits.free_shipping_threshold && (
          <ListItem>
            <InlineStack spacing="tight" blockAlignment="center">
              <Icon source="delivery" />
              <Text>Free shipping on orders over ${benefits.free_shipping_threshold}</Text>
            </InlineStack>
          </ListItem>
        )}
        {benefits.priority_support && (
          <ListItem>
            <InlineStack spacing="tight" blockAlignment="center">
              <Icon source="chat" />
              <Text>Priority customer support</Text>
            </InlineStack>
          </ListItem>
        )}
        {benefits.early_access && (
          <ListItem>
            <InlineStack spacing="tight" blockAlignment="center">
              <Icon source="star" />
              <Text>Early access to new products</Text>
            </InlineStack>
          </ListItem>
        )}
      </List>
    </BlockStack>
  );
}

// ============================================================================
// Utility Functions
// ============================================================================

function formatDate(dateString) {
  if (!dateString) return '';
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function getActivityDescription(activity) {
  const descriptions = {
    earn: 'Points earned',
    redeem: 'Points redeemed',
    expire: 'Points expired',
    adjustment: 'Points adjustment',
    bonus: 'Bonus points',
  };

  return descriptions[activity.type] || 'Points activity';
}
