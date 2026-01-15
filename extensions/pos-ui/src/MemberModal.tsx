import React, { useState, useCallback } from 'react';
import {
  Screen,
  ScrollView,
  Navigator,
  Text,
  TextField,
  Button,
  Banner,
  Section,
  Selectable,
  NumberField,
  useExtensionApi,
  Stack,
  Badge,
  Box,
  SearchBar,
  RadioButtonList,
} from '@shopify/ui-extensions-react/point-of-sale';

interface TierInfo {
  name: string;
  trade_bonus_percent: number;
  color?: string;
  icon?: string;
}

interface TradeIn {
  id: number;
  reference_number: string;
  date: string;
  total_value: number;
  credit_amount: number;
  category?: string;
}

interface Member {
  id: number;
  member_number: string;
  name: string;
  email: string;
  phone?: string;
  tier: TierInfo;
  store_credit_balance: number;
  points_balance: number;
  lifetime_trade_value: number;
  lifetime_credit_earned: number;
  trade_count: number;
  member_since: string;
  recent_trades: TradeIn[];
  is_vip: boolean;
}

interface SearchResult {
  id: number;
  member_number: string;
  name: string;
  email: string;
  phone?: string;
  tier_name: string;
  store_credit_balance: number;
  is_vip: boolean;
}

/**
 * TradeUp Member Lookup - Best in Class POS Experience
 *
 * Features:
 * - Instant member search
 * - VIP badges that stand out
 * - Trade-in bonus rates displayed prominently
 * - Recent trade-in history
 * - Lifetime value stats
 * - Quick credit issuance
 */
export default function MemberModal() {
  const { session, toast } = useExtensionApi<'pos.home.modal.render'>();

  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [selectedMember, setSelectedMember] = useState<Member | null>(null);
  const [showCreditForm, setShowCreditForm] = useState(false);
  const [creditAmount, setCreditAmount] = useState('');
  const [creditReason, setCreditReason] = useState('trade_in');

  const shopDomain = session.shop?.myshopifyDomain || '';
  const API_BASE = 'https://app.cardflowlabs.com/api';

  // Search members
  const searchMembers = useCallback(async () => {
    if (!searchQuery.trim()) {
      setError('Enter email, phone, or member #');
      return;
    }

    setLoading(true);
    setError(null);
    setSearchResults([]);

    try {
      const response = await fetch(
        `${API_BASE}/members?search=${encodeURIComponent(searchQuery)}&limit=10`,
        {
          headers: {
            'X-Shopify-Shop-Domain': shopDomain,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) throw new Error('Search failed');

      const data = await response.json();
      const results = (data.members || []).map((m: any) => ({
        ...m,
        is_vip: ['gold', 'platinum', 'vip', 'elite'].some(
          (tier) => m.tier_name?.toLowerCase().includes(tier)
        ),
      }));

      setSearchResults(results);

      if (results.length === 0) {
        setError('No members found');
      }
    } catch (err) {
      setError('Search failed. Try again.');
    } finally {
      setLoading(false);
    }
  }, [searchQuery, shopDomain]);

  // Load full member details
  const loadMemberDetails = useCallback(async (memberId: number) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/members/${memberId}`, {
        headers: {
          'X-Shopify-Shop-Domain': shopDomain,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) throw new Error('Failed to load member');

      const data = await response.json();

      // Determine if VIP based on tier name
      const isVip = ['gold', 'platinum', 'vip', 'elite'].some(
        (tier) => data.tier?.name?.toLowerCase().includes(tier)
      );

      setSelectedMember({
        ...data,
        is_vip: isVip,
        tier: data.tier || { name: 'Standard', trade_bonus_percent: 0 },
        recent_trades: data.recent_trades || [],
        lifetime_trade_value: data.lifetime_trade_value || 0,
        lifetime_credit_earned: data.lifetime_credit_earned || 0,
        trade_count: data.trade_count || 0,
      });
    } catch (err) {
      setError('Failed to load member details');
    } finally {
      setLoading(false);
    }
  }, [shopDomain]);

  // Issue credit
  const issueCredit = useCallback(async () => {
    if (!selectedMember || !creditAmount) {
      setError('Enter an amount');
      return;
    }

    const amount = parseFloat(creditAmount);
    if (isNaN(amount) || amount <= 0) {
      setError('Enter a valid amount');
      return;
    }

    // Apply tier bonus if trade-in
    let finalAmount = amount;
    let bonusApplied = 0;
    if (creditReason === 'trade_in' && selectedMember.tier.trade_bonus_percent > 0) {
      bonusApplied = amount * (selectedMember.tier.trade_bonus_percent / 100);
      finalAmount = amount + bonusApplied;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/store-credit/add`, {
        method: 'POST',
        headers: {
          'X-Shopify-Shop-Domain': shopDomain,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          member_id: selectedMember.id,
          amount: finalAmount,
          description: creditReason === 'trade_in'
            ? `Trade-In (POS)${bonusApplied > 0 ? ` +$${bonusApplied.toFixed(2)} tier bonus` : ''}`
            : 'Store Credit (POS)',
          event_type: creditReason === 'trade_in' ? 'trade_in' : 'pos_credit',
        }),
      });

      if (!response.ok) throw new Error('Failed to issue credit');

      const data = await response.json();

      const message = bonusApplied > 0
        ? `$${finalAmount.toFixed(2)} issued (includes $${bonusApplied.toFixed(2)} bonus)`
        : `$${finalAmount.toFixed(2)} issued`;

      toast.show(message);
      setShowCreditForm(false);
      setCreditAmount('');

      // Update balance
      setSelectedMember({
        ...selectedMember,
        store_credit_balance: data.new_balance,
      });
    } catch (err) {
      setError('Failed to issue credit');
    } finally {
      setLoading(false);
    }
  }, [selectedMember, creditAmount, creditReason, shopDomain, toast]);

  // ========================
  // MEMBER DETAILS SCREEN
  // ========================
  if (selectedMember) {
    const tier = selectedMember.tier;
    const hasBonus = tier.trade_bonus_percent > 0;

    return (
      <Navigator>
        <Screen title={selectedMember.name || 'Member'} name="details">
          <ScrollView>
            {error && (
              <Banner
                title={error}
                variant="error"
                visible={true}
                action="Dismiss"
                onPress={() => setError(null)}
              />
            )}

            {/* VIP BANNER - Make it STAND OUT */}
            {selectedMember.is_vip && (
              <Banner
                title={`VIP MEMBER - ${tier.name.toUpperCase()}`}
                variant="confirmation"
                visible={true}
              />
            )}

            {/* TIER & BONUS - The most important info for trade-ins */}
            <Section title="Membership Tier">
              <Stack direction="horizontal" spacing="tight">
                <Badge
                  text={hasBonus ? `+${tier.trade_bonus_percent}%` : 'STD'}
                  variant={hasBonus ? 'success' : 'neutral'}
                />
                <Stack direction="vertical" spacing="extraTight">
                  <Text variant="headingSmall">{tier.name || 'Standard'}</Text>
                  <Text variant="body">
                    {hasBonus
                      ? `+${tier.trade_bonus_percent}% bonus on trade-ins`
                      : 'Standard rates'}
                  </Text>
                </Stack>
              </Stack>
            </Section>

            {/* BALANCES */}
            <Section title="Current Balance">
              <Stack direction="horizontal" spacing="tight">
                <Badge text="$" variant="highlight" />
                <Stack direction="vertical" spacing="extraTight">
                  <Text variant="headingSmall">Store Credit</Text>
                  <Text variant="headingLarge">
                    ${selectedMember.store_credit_balance.toFixed(2)}
                  </Text>
                </Stack>
              </Stack>
              {selectedMember.points_balance > 0 && (
                <Stack direction="vertical" spacing="extraTight">
                  <Text variant="body">Points</Text>
                  <Text variant="body">
                    {selectedMember.points_balance.toLocaleString()} pts
                  </Text>
                </Stack>
              )}
            </Section>

            {/* LIFETIME STATS */}
            <Section title="Lifetime Stats">
              <Stack direction="vertical" spacing="tight">
                <Stack direction="horizontal" spacing="base">
                  <Text variant="body">Total Trades:</Text>
                  <Text variant="body">{selectedMember.trade_count} trade-ins</Text>
                </Stack>
                <Stack direction="horizontal" spacing="base">
                  <Text variant="body">Total Value Traded:</Text>
                  <Text variant="body">${selectedMember.lifetime_trade_value.toFixed(2)}</Text>
                </Stack>
                <Stack direction="horizontal" spacing="base">
                  <Text variant="body">Total Credit Earned:</Text>
                  <Text variant="body">${selectedMember.lifetime_credit_earned.toFixed(2)}</Text>
                </Stack>
                <Stack direction="horizontal" spacing="base">
                  <Text variant="body">Member Since:</Text>
                  <Text variant="body">{selectedMember.member_since || 'N/A'}</Text>
                </Stack>
              </Stack>
            </Section>

            {/* RECENT TRADE-INS */}
            {selectedMember.recent_trades.length > 0 && (
              <Section title="Recent Trade-Ins">
                <Stack direction="vertical" spacing="tight">
                  {selectedMember.recent_trades.slice(0, 5).map((trade) => (
                    <Selectable key={trade.id} onPress={() => {}}>
                      <Stack direction="horizontal" spacing="tight">
                        <Badge text={trade.category || 'Trade'} variant="neutral" />
                        <Stack direction="vertical" spacing="extraTight">
                          <Text variant="body">{trade.reference_number}</Text>
                          <Text variant="captionRegular">
                            {trade.date} - ${trade.credit_amount.toFixed(2)} credit
                          </Text>
                        </Stack>
                      </Stack>
                    </Selectable>
                  ))}
                </Stack>
              </Section>
            )}

            {/* CREDIT FORM */}
            {showCreditForm ? (
              <Section title="Issue Credit">
                <RadioButtonList
                  items={[
                    {
                      label: `Trade-In${hasBonus ? ` (+${tier.trade_bonus_percent}% bonus)` : ''}`,
                      value: 'trade_in',
                    },
                    {
                      label: 'Adjustment/Other (no bonus)',
                      value: 'adjustment',
                    },
                  ]}
                  onItemSelected={(value) => setCreditReason(value)}
                  initialSelectedItem={creditReason}
                />

                <NumberField
                  title="Base Amount ($)"
                  value={creditAmount}
                  onChange={setCreditAmount}
                />

                {creditAmount && parseFloat(creditAmount) > 0 && creditReason === 'trade_in' && hasBonus && (
                  <Banner
                    title={`Total: $${(parseFloat(creditAmount) * (1 + tier.trade_bonus_percent / 100)).toFixed(2)} (includes $${(parseFloat(creditAmount) * tier.trade_bonus_percent / 100).toFixed(2)} bonus)`}
                    variant="confirmation"
                    visible={true}
                  />
                )}

                <Button
                  title={`Issue ${creditReason === 'trade_in' ? 'Trade-In ' : ''}Credit`}
                  type="primary"
                  isLoading={loading}
                  onPress={issueCredit}
                />
                <Button
                  title="Cancel"
                  type="plain"
                  onPress={() => {
                    setShowCreditForm(false);
                    setCreditAmount('');
                  }}
                />
              </Section>
            ) : (
              <Section title="Actions">
                <Button
                  title="Issue Store Credit"
                  type="primary"
                  onPress={() => setShowCreditForm(true)}
                />
                <Button
                  title="Back to Search"
                  type="plain"
                  onPress={() => setSelectedMember(null)}
                />
              </Section>
            )}

            {/* MEMBER INFO */}
            <Section title="Contact Info">
              <Stack direction="vertical" spacing="tight">
                <Stack direction="horizontal" spacing="base">
                  <Text variant="body">Member #:</Text>
                  <Text variant="body">{selectedMember.member_number}</Text>
                </Stack>
                <Stack direction="horizontal" spacing="base">
                  <Text variant="body">Email:</Text>
                  <Text variant="body">{selectedMember.email}</Text>
                </Stack>
                {selectedMember.phone && (
                  <Stack direction="horizontal" spacing="base">
                    <Text variant="body">Phone:</Text>
                    <Text variant="body">{selectedMember.phone}</Text>
                  </Stack>
                )}
              </Stack>
            </Section>
          </ScrollView>
        </Screen>
      </Navigator>
    );
  }

  // ========================
  // SEARCH SCREEN
  // ========================
  return (
    <Navigator>
      <Screen title="TradeUp Members" name="search">
        <ScrollView>
          {error && (
            <Banner
              title={error}
              variant="error"
              visible={true}
              action="Dismiss"
              onPress={() => setError(null)}
            />
          )}

          <Section title="Find Member">
            <SearchBar
              placeholder="Email, phone, or member #"
              value={searchQuery}
              onSearch={searchMembers}
              onChange={setSearchQuery}
              editable={!loading}
            />
            <Button
              title="Search"
              type="primary"
              isLoading={loading}
              onPress={searchMembers}
            />
          </Section>

          {searchResults.length > 0 && (
            <Section title={`${searchResults.length} Results`}>
              <Stack direction="vertical" spacing="tight">
                {searchResults.map((member) => (
                  <Selectable
                    key={member.id}
                    onPress={() => loadMemberDetails(member.id)}
                  >
                    <Stack direction="horizontal" spacing="tight">
                      <Badge
                        text={member.is_vip ? 'VIP' : member.member_number}
                        variant={member.is_vip ? 'success' : 'neutral'}
                      />
                      <Stack direction="vertical" spacing="extraTight">
                        <Text variant="headingSmall">{member.name || member.email}</Text>
                        <Text variant="captionRegular">
                          {member.tier_name || 'Standard'} - ${member.store_credit_balance.toFixed(2)} credit
                        </Text>
                      </Stack>
                    </Stack>
                  </Selectable>
                ))}
              </Stack>
            </Section>
          )}

          {/* Quick tip for staff */}
          <Section title="Tips">
            <Text variant="body">
              Search by email, phone number, or member # for fastest results.
            </Text>
          </Section>
        </ScrollView>
      </Screen>
    </Navigator>
  );
}
