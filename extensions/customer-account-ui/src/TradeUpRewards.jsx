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
 * - Achievement unlocked celebrations
 * - Milestone celebrations
 * - In-app nudge notifications (NR-010)
 *
 * @version 2.4.0
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
  const [newlyEarnedBadges, setNewlyEarnedBadges] = useState([]);
  const [showAchievementModal, setShowAchievementModal] = useState(false);
  const [currentCelebrationBadge, setCurrentCelebrationBadge] = useState(null);
  const [newlyAchievedMilestones, setNewlyAchievedMilestones] = useState([]);
  const [showMilestoneModal, setShowMilestoneModal] = useState(false);
  const [currentCelebrationMilestone, setCurrentCelebrationMilestone] = useState(null);

  // Nudge notification state
  const [nudges, setNudges] = useState([]);
  const [nudgesLoading, setNudgesLoading] = useState(false);

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

  // Check for newly earned badges when page loads
  useEffect(() => {
    if (data?.is_member && customer?.id) {
      checkNewlyEarnedBadges();
    }
  }, [data?.is_member, customer?.id]);

  // Check for newly achieved milestones when page loads
  useEffect(() => {
    if (data?.is_member && customer?.id) {
      checkNewlyAchievedMilestones();
    }
  }, [data?.is_member, customer?.id]);

  // Fetch nudge notifications when member data is loaded
  useEffect(() => {
    if (data?.is_member && customer?.id) {
      fetchNudges();
    }
  }, [data?.is_member, customer?.id]);

  const fetchNudges = async () => {
    if (!customer?.id) return;
    setNudgesLoading(true);

    try {
      const token = await sessionToken.get();
      const customerId = customer.id.replace('gid://shopify/Customer/', '');

      const response = await fetch(`${API_BASE}/customer/extension/nudges`, {
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
        setNudges(result.nudges || []);
      }
    } catch (err) {
      console.error('Error fetching nudges:', err);
    } finally {
      setNudgesLoading(false);
    }
  };

  const dismissNudge = async (nudge) => {
    if (!customer?.id) return;

    try {
      const token = await sessionToken.get();
      const customerId = customer.id.replace('gid://shopify/Customer/', '');

      await fetch(`${API_BASE}/customer/extension/nudges/dismiss`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'X-Shop-Domain': shop.domain,
        },
        body: JSON.stringify({
          customer_id: customerId,
          nudge_id: nudge.id,
          nudge_type: nudge.nudge_type,
        }),
      });

      // Remove the dismissed nudge from state
      setNudges((prev) => prev.filter((n) => n.id !== nudge.id));
    } catch (err) {
      console.error('Error dismissing nudge:', err);
    }
  };

  const handleNudgeAction = (nudge) => {
    // Handle action based on nudge type
    if (nudge.action_tab) {
      setActiveTab(nudge.action_tab);
    } else if (nudge.action_url) {
      // Open external URL
      window.open(nudge.action_url, '_blank');
    }
    // Dismiss after action
    dismissNudge(nudge);
  };

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

  const checkNewlyEarnedBadges = async () => {
    if (!customer?.id) return;

    try {
      const token = await sessionToken.get();
      const customerId = customer.id.replace('gid://shopify/Customer/', '');

      const response = await fetch(`${API_BASE}/customer/extension/badges/newly-earned`, {
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
        if (result.newly_earned_badges && result.newly_earned_badges.length > 0) {
          setNewlyEarnedBadges(result.newly_earned_badges);
          // Show the first badge celebration
          setCurrentCelebrationBadge(result.newly_earned_badges[0]);
          setShowAchievementModal(true);
        }
      }
    } catch (err) {
      console.error('Error checking newly earned badges:', err);
    }
  };

  const checkNewlyAchievedMilestones = async () => {
    if (!customer?.id) return;

    try {
      const token = await sessionToken.get();
      const customerId = customer.id.replace('gid://shopify/Customer/', '');

      const response = await fetch(`${API_BASE}/customer/extension/milestones/newly-achieved`, {
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
        if (result.newly_achieved_milestones && result.newly_achieved_milestones.length > 0) {
          setNewlyAchievedMilestones(result.newly_achieved_milestones);
          // Show the first milestone celebration (after badges are done)
          if (!showAchievementModal) {
            setCurrentCelebrationMilestone(result.newly_achieved_milestones[0]);
            setShowMilestoneModal(true);
          }
        }
      }
    } catch (err) {
      console.error('Error checking newly achieved milestones:', err);
    }
  };

  const markBadgeAsNotified = async (badgeId) => {
    if (!customer?.id) return;

    try {
      const token = await sessionToken.get();
      const customerId = customer.id.replace('gid://shopify/Customer/', '');

      await fetch(`${API_BASE}/customer/extension/badges/mark-notified`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'X-Shop-Domain': shop.domain,
        },
        body: JSON.stringify({
          customer_id: customerId,
          badge_ids: [badgeId],
        }),
      });
    } catch (err) {
      console.error('Error marking badge as notified:', err);
    }
  };

  const markMilestoneAsNotified = async (milestoneId) => {
    if (!customer?.id) return;

    try {
      const token = await sessionToken.get();
      const customerId = customer.id.replace('gid://shopify/Customer/', '');

      await fetch(`${API_BASE}/customer/extension/milestones/mark-notified`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'X-Shop-Domain': shop.domain,
        },
        body: JSON.stringify({
          customer_id: customerId,
          milestone_ids: [milestoneId],
        }),
      });
    } catch (err) {
      console.error('Error marking milestone as notified:', err);
    }
  };

  const handleCloseCelebration = useCallback(() => {
    if (currentCelebrationBadge) {
      // Mark the current badge as notified
      markBadgeAsNotified(currentCelebrationBadge.id);

      // Find next badge to show
      const currentIndex = newlyEarnedBadges.findIndex(b => b.id === currentCelebrationBadge.id);
      const nextBadge = newlyEarnedBadges[currentIndex + 1];

      if (nextBadge) {
        setCurrentCelebrationBadge(nextBadge);
      } else {
        // No more badges, close the modal
        setShowAchievementModal(false);
        setCurrentCelebrationBadge(null);
        setNewlyEarnedBadges([]);

        // Check if there are milestones to celebrate next
        if (newlyAchievedMilestones.length > 0) {
          setCurrentCelebrationMilestone(newlyAchievedMilestones[0]);
          setShowMilestoneModal(true);
        }
      }
    }
  }, [currentCelebrationBadge, newlyEarnedBadges, newlyAchievedMilestones]);

  const handleCloseMilestoneCelebration = useCallback(() => {
    if (currentCelebrationMilestone) {
      // Mark the current milestone as notified
      markMilestoneAsNotified(currentCelebrationMilestone.id);

      // Find next milestone to show
      const currentIndex = newlyAchievedMilestones.findIndex(m => m.id === currentCelebrationMilestone.id);
      const nextMilestone = newlyAchievedMilestones[currentIndex + 1];

      if (nextMilestone) {
        setCurrentCelebrationMilestone(nextMilestone);
      } else {
        // No more milestones, close the modal
        setShowMilestoneModal(false);
        setCurrentCelebrationMilestone(null);
        setNewlyAchievedMilestones([]);
      }
    }
  }, [currentCelebrationMilestone, newlyAchievedMilestones]);

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

        {/* Nudge Notifications Banner */}
        {nudges.length > 0 && (
          <NudgeBanner
            nudges={nudges}
            onDismiss={dismissNudge}
            onAction={handleNudgeAction}
          />
        )}

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

        {/* Achievement Unlocked Celebration Modal */}
        {showAchievementModal && currentCelebrationBadge && (
          <AchievementUnlockedModal
            badge={currentCelebrationBadge}
            onClose={handleCloseCelebration}
            remainingCount={newlyEarnedBadges.length - 1 - newlyEarnedBadges.findIndex(b => b.id === currentCelebrationBadge.id)}
          />
        )}

        {/* Milestone Celebration Modal */}
        {showMilestoneModal && currentCelebrationMilestone && (
          <MilestoneCelebrationModal
            milestone={currentCelebrationMilestone}
            onClose={handleCloseMilestoneCelebration}
            remainingCount={newlyAchievedMilestones.length - 1 - newlyAchievedMilestones.findIndex(m => m.id === currentCelebrationMilestone.id)}
          />
        )}
      </BlockStack>
    </Card>
  );
}

// ============================================================================
// Nudge Banner Component
// ============================================================================

function NudgeBanner({ nudges, onDismiss, onAction }) {
  if (!nudges || nudges.length === 0) return null;

  // Get urgency-based styling
  const getUrgencyTone = (urgency) => {
    switch (urgency) {
      case 'critical':
        return 'critical';
      case 'warning':
        return 'warning';
      case 'success':
        return 'success';
      default:
        return 'info';
    }
  };

  return (
    <BlockStack spacing="tight">
      {nudges.map((nudge) => (
        <Banner
          key={nudge.id}
          status={getUrgencyTone(nudge.urgency)}
          title={nudge.title}
          onDismiss={nudge.dismissable ? () => onDismiss(nudge) : undefined}
        >
          <BlockStack spacing="tight">
            <Text>{nudge.message}</Text>
            {nudge.action_text && (
              <Button
                kind="secondary"
                onPress={() => onAction(nudge)}
              >
                {nudge.action_text}
              </Button>
            )}
          </BlockStack>
        </Banner>
      ))}
    </BlockStack>
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
        <TierProgressBar
          currentTierName={tier.name}
          nextTierName={nextTierName}
          pointsToNextTier={pointsToNextTier}
          progress={progress}
        />
      )}

      {!nextTierName && (
        <View padding="base" background="subdued" borderRadius="base">
          <BlockStack spacing="tight" inlineAlignment="center">
            <Text size="large" tone="success">
              MAX TIER ACHIEVED
            </Text>
            <Text size="small" appearance="subdued">
              You're at the highest tier - enjoy all benefits!
            </Text>
          </BlockStack>
        </View>
      )}
    </BlockStack>
  );
}

// ============================================================================
// Tier Progress Bar Component
// ============================================================================

/**
 * TierProgressBar - Visual progress indicator for tier advancement
 *
 * Shows:
 * - Current tier and next tier labels
 * - Visual progress bar with percentage
 * - Points needed to reach next tier
 * - Motivational messaging based on progress
 */
function TierProgressBar({ currentTierName, nextTierName, pointsToNextTier, progress }) {
  // Calculate percentage (progress is 0-1, convert to 0-100)
  const progressPercent = Math.min(100, Math.max(0, Math.round(progress * 100)));

  // Calculate current points (reverse engineer from progress and pointsToNextTier)
  // If progress = currentPoints / threshold, and pointsToNextTier = threshold - currentPoints
  // Then currentPoints = progress * threshold = progress * (currentPoints + pointsToNextTier)
  // currentPoints = (progress * pointsToNextTier) / (1 - progress)
  const currentPoints = progress < 1
    ? Math.round((progress * pointsToNextTier) / (1 - progress))
    : 0;

  // Calculate the total threshold for next tier
  const nextTierThreshold = currentPoints + pointsToNextTier;

  // Determine motivational message based on progress
  const getMotivationalMessage = () => {
    if (progressPercent >= 90) {
      return "Almost there! Just a few more points!";
    } else if (progressPercent >= 75) {
      return "Great progress! You're so close!";
    } else if (progressPercent >= 50) {
      return "Halfway there! Keep going!";
    } else if (progressPercent >= 25) {
      return "Nice start! Keep earning points!";
    } else {
      return "Start your journey to the next tier!";
    }
  };

  return (
    <View padding="base" background="subdued" borderRadius="base">
      <BlockStack spacing="base">
        {/* Header with tier names */}
        <InlineStack spacing="loose" blockAlignment="center">
          <BlockStack spacing="extraTight">
            <Text size="small" appearance="subdued">CURRENT</Text>
            <Text emphasis="bold">{currentTierName}</Text>
          </BlockStack>
          <View inlineSize="fill" />
          <BlockStack spacing="extraTight" inlineAlignment="end">
            <Text size="small" appearance="subdued">NEXT TIER</Text>
            <Text emphasis="bold" tone="success">{nextTierName}</Text>
          </BlockStack>
        </InlineStack>

        {/* Progress bar container */}
        <BlockStack spacing="tight">
          {/* Progress bar track */}
          <View
            border="base"
            borderRadius="base"
            padding="none"
            background="base"
            minBlockSize={16}
          >
            {/* Progress bar fill */}
            <View
              background="interactive"
              borderRadius="base"
              minBlockSize={16}
              inlineSize={`${progressPercent}%`}
            >
              {/* Percentage label inside bar (only show if enough space) */}
              {progressPercent >= 15 && (
                <View padding="extraTight" inlineAlignment="center">
                  <Text size="small" emphasis="bold">
                    {progressPercent}%
                  </Text>
                </View>
              )}
            </View>
          </View>

          {/* Percentage label outside bar (show if not enough space inside) */}
          {progressPercent < 15 && (
            <Text size="small" emphasis="bold" appearance="subdued">
              {progressPercent}% complete
            </Text>
          )}
        </BlockStack>

        {/* Points info */}
        <InlineStack spacing="loose" blockAlignment="center">
          <BlockStack spacing="extraTight">
            <Text size="small" appearance="subdued">Current Points</Text>
            <Text emphasis="bold">{currentPoints.toLocaleString()}</Text>
          </BlockStack>
          <View inlineSize="fill" />
          <BlockStack spacing="extraTight" inlineAlignment="end">
            <Text size="small" appearance="subdued">Need for {nextTierName}</Text>
            <Text emphasis="bold" tone="success">{nextTierThreshold.toLocaleString()}</Text>
          </BlockStack>
        </InlineStack>

        {/* Points remaining callout */}
        <View padding="tight" background="base" borderRadius="base">
          <InlineStack spacing="tight" blockAlignment="center" inlineAlignment="center">
            <Badge tone="info">{pointsToNextTier.toLocaleString()} pts to go</Badge>
            <Text size="small" appearance="subdued">
              {getMotivationalMessage()}
            </Text>
          </InlineStack>
        </View>
      </BlockStack>
    </View>
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

// ============================================================================
// Achievement Unlocked Celebration Modal
// ============================================================================

function AchievementUnlockedModal({ badge, onClose, remainingCount }) {
  // Map icon names to celebratory emojis
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

  // Confetti characters for simple animation
  const confettiChars = ['\uD83C\uDF89', '\uD83C\uDF8A', '\u2728', '\uD83C\uDF1F', '\uD83C\uDF8A'];

  return (
    <Modal
      id="achievement-unlocked"
      title="Achievement Unlocked!"
      open={true}
      onClose={onClose}
    >
      <BlockStack spacing="loose" padding="loose">
        {/* Celebration Header with Confetti */}
        <View padding="base" background="subdued" borderRadius="base">
          <BlockStack spacing="base" inlineAlignment="center">
            {/* Confetti Animation Row */}
            <InlineStack spacing="tight" inlineAlignment="center">
              <Text size="large">{confettiChars[0]}</Text>
              <Text size="large">{confettiChars[1]}</Text>
              <Text size="large">{confettiChars[2]}</Text>
            </InlineStack>

            {/* Badge Icon - Large and Centered */}
            <View padding="base">
              <Text size="extraLarge">{iconEmoji}</Text>
            </View>

            {/* More Confetti */}
            <InlineStack spacing="tight" inlineAlignment="center">
              <Text size="large">{confettiChars[3]}</Text>
              <Text size="large">{confettiChars[4]}</Text>
              <Text size="large">{confettiChars[0]}</Text>
            </InlineStack>
          </BlockStack>
        </View>

        {/* Badge Name */}
        <BlockStack spacing="extraTight" inlineAlignment="center">
          <Text emphasis="bold" size="large">
            {badge.name}
          </Text>
          {badge.description && (
            <Text appearance="subdued" size="medium">
              {badge.description}
            </Text>
          )}
        </BlockStack>

        {/* Rewards Earned */}
        {(badge.points_reward > 0 || badge.credit_reward > 0) && (
          <>
            <Divider />
            <BlockStack spacing="tight" inlineAlignment="center">
              <Text appearance="subdued" size="small">YOU EARNED</Text>
              <InlineStack spacing="loose" inlineAlignment="center">
                {badge.points_reward > 0 && (
                  <BlockStack spacing="extraTight" inlineAlignment="center">
                    <Text emphasis="bold" size="large" tone="success">
                      +{badge.points_reward.toLocaleString()}
                    </Text>
                    <Text appearance="subdued" size="small">points</Text>
                  </BlockStack>
                )}
                {badge.credit_reward > 0 && (
                  <BlockStack spacing="extraTight" inlineAlignment="center">
                    <Text emphasis="bold" size="large" tone="success">
                      +${badge.credit_reward.toFixed(2)}
                    </Text>
                    <Text appearance="subdued" size="small">store credit</Text>
                  </BlockStack>
                )}
              </InlineStack>
            </BlockStack>
          </>
        )}

        {/* Celebration Message */}
        <View padding="base" background="subdued" borderRadius="base">
          <BlockStack spacing="tight" inlineAlignment="center">
            <Text size="medium">
              Congratulations! Keep up the great work!
            </Text>
            {remainingCount > 0 && (
              <Text appearance="subdued" size="small">
                {remainingCount} more badge{remainingCount > 1 ? 's' : ''} to celebrate!
              </Text>
            )}
          </BlockStack>
        </View>

        {/* Close Button */}
        <Button kind="primary" onPress={onClose}>
          {remainingCount > 0 ? 'Next Badge' : 'Awesome!'}
        </Button>
      </BlockStack>
    </Modal>
  );
}

// ============================================================================
// Milestone Celebration Modal
// ============================================================================

function MilestoneCelebrationModal({ milestone, onClose, remainingCount }) {
  // Map milestone types to celebratory emojis
  const typeIconMap = {
    'points_earned': '\uD83C\uDFC6',
    'trade_ins_completed': '\uD83D\uDCE6',
    'referrals_made': '\uD83D\uDC65',
    'total_spent': '\uD83D\uDCB0',
    'member_days': '\uD83D\uDCC5',
  };

  const typeIcon = typeIconMap[milestone.milestone_type] || '\uD83C\uDF1F';

  // Celebration emojis
  const celebrationEmojis = ['\uD83C\uDF89', '\uD83C\uDF8A', '\uD83C\uDF1F', '\u2728', '\uD83C\uDF86'];

  // Get custom celebration message or generate default
  const celebrationMessage = milestone.celebration_message || `You reached ${milestone.threshold} ${milestone.milestone_type.replace(/_/g, ' ')}!`;

  return (
    <Modal
      id="milestone-celebration"
      title="Milestone Reached!"
      open={true}
      onClose={onClose}
    >
      <BlockStack spacing="loose" padding="loose">
        {/* Celebration Header */}
        <View padding="base" background="subdued" borderRadius="base">
          <BlockStack spacing="base" inlineAlignment="center">
            {/* Celebration Emojis Row */}
            <InlineStack spacing="tight" inlineAlignment="center">
              <Text size="large">{celebrationEmojis[0]}</Text>
              <Text size="large">{celebrationEmojis[1]}</Text>
              <Text size="large">{celebrationEmojis[2]}</Text>
            </InlineStack>

            {/* Milestone Icon - Large and Centered */}
            <View padding="base">
              <Text size="extraLarge">{typeIcon}</Text>
            </View>

            {/* More Celebration */}
            <InlineStack spacing="tight" inlineAlignment="center">
              <Text size="large">{celebrationEmojis[3]}</Text>
              <Text size="large">{celebrationEmojis[4]}</Text>
              <Text size="large">{celebrationEmojis[0]}</Text>
            </InlineStack>
          </BlockStack>
        </View>

        {/* Milestone Name */}
        <BlockStack spacing="extraTight" inlineAlignment="center">
          <Text emphasis="bold" size="large">
            {milestone.name}
          </Text>
          {milestone.description && (
            <Text appearance="subdued" size="medium">
              {milestone.description}
            </Text>
          )}
        </BlockStack>

        {/* Celebration Message */}
        <View padding="tight" background="subdued" borderRadius="base">
          <BlockStack spacing="tight" inlineAlignment="center">
            <Text size="medium">
              {celebrationMessage}
            </Text>
          </BlockStack>
        </View>

        {/* Rewards Earned */}
        {(milestone.points_reward > 0 || milestone.credit_reward > 0) && (
          <>
            <Divider />
            <BlockStack spacing="tight" inlineAlignment="center">
              <Text appearance="subdued" size="small">YOU EARNED</Text>
              <InlineStack spacing="loose" inlineAlignment="center">
                {milestone.points_reward > 0 && (
                  <BlockStack spacing="extraTight" inlineAlignment="center">
                    <Text emphasis="bold" size="large" tone="success">
                      +{milestone.points_reward.toLocaleString()}
                    </Text>
                    <Text appearance="subdued" size="small">bonus points</Text>
                  </BlockStack>
                )}
                {milestone.credit_reward > 0 && (
                  <BlockStack spacing="extraTight" inlineAlignment="center">
                    <Text emphasis="bold" size="large" tone="success">
                      +${milestone.credit_reward.toFixed(2)}
                    </Text>
                    <Text appearance="subdued" size="small">store credit</Text>
                  </BlockStack>
                )}
              </InlineStack>
            </BlockStack>
          </>
        )}

        {/* Motivational Message */}
        <View padding="base" background="subdued" borderRadius="base">
          <BlockStack spacing="tight" inlineAlignment="center">
            <Text size="medium">
              Amazing achievement! Keep going!
            </Text>
            {remainingCount > 0 && (
              <Text appearance="subdued" size="small">
                {remainingCount} more milestone{remainingCount > 1 ? 's' : ''} to celebrate!
              </Text>
            )}
          </BlockStack>
        </View>

        {/* Close Button */}
        <Button kind="primary" onPress={onClose}>
          {remainingCount > 0 ? 'Next Milestone' : 'Awesome!'}
        </Button>
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
