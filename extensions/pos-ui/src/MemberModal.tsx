import React, { useState, useCallback } from 'react';
import {
  Screen,
  ScrollView,
  Navigator,
  Text,
  TextField,
  Button,
  Banner,
  List,
  ListRow,
  Section,
  Selectable,
  FormattedTextField,
  useExtensionApi,
} from '@shopify/ui-extensions-react/point-of-sale';

interface Member {
  id: number;
  member_number: string;
  name: string;
  email: string;
  phone?: string;
  tier_name: string;
  store_credit_balance: number;
  points_balance: number;
}

/**
 * TradeUp Member Lookup Modal for POS.
 *
 * Allows staff to:
 * - Search members by email, phone, or member number
 * - View member details, tier, and balances
 * - Issue store credit
 */
export default function MemberModal() {
  const { session, toast } = useExtensionApi<'pos.home.modal.render'>();

  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [selectedMember, setSelectedMember] = useState<Member | null>(null);
  const [showCreditForm, setShowCreditForm] = useState(false);
  const [creditAmount, setCreditAmount] = useState('');

  // Get the shop domain from session
  const shopDomain = session.shop?.myshopifyDomain || '';

  // API base URL - this would be configured per installation
  const API_BASE = `https://app.cardflowlabs.com/api`;

  const searchMembers = useCallback(async () => {
    if (!searchQuery.trim()) {
      setError('Please enter a search term');
      return;
    }

    setLoading(true);
    setError(null);
    setMembers([]);

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

      if (!response.ok) {
        throw new Error('Search failed');
      }

      const data = await response.json();
      setMembers(data.members || []);

      if (data.members?.length === 0) {
        setError('No members found');
      }
    } catch (err) {
      setError('Failed to search members. Please try again.');
      console.error('Search error:', err);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, shopDomain]);

  const issueCredit = useCallback(async () => {
    if (!selectedMember || !creditAmount) {
      setError('Please enter an amount');
      return;
    }

    const amount = parseFloat(creditAmount);
    if (isNaN(amount) || amount <= 0) {
      setError('Please enter a valid amount');
      return;
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
          amount: amount,
          description: 'POS Credit',
          event_type: 'pos_credit',
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to issue credit');
      }

      const data = await response.json();

      toast.show('Credit issued successfully');
      setShowCreditForm(false);
      setCreditAmount('');

      // Update member balance locally
      setSelectedMember({
        ...selectedMember,
        store_credit_balance: data.new_balance,
      });
    } catch (err) {
      setError('Failed to issue credit. Please try again.');
      console.error('Credit error:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedMember, creditAmount, shopDomain, toast]);

  // Member details screen
  if (selectedMember) {
    return (
      <Navigator>
        <Screen title={selectedMember.name || 'Member Details'} name="details">
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

            <Section title="Member Info">
              <List>
                <ListRow
                  title="Member #"
                  subtitle={selectedMember.member_number}
                />
                <ListRow
                  title="Email"
                  subtitle={selectedMember.email}
                />
                {selectedMember.phone && (
                  <ListRow
                    title="Phone"
                    subtitle={selectedMember.phone}
                  />
                )}
                <ListRow
                  title="Tier"
                  subtitle={selectedMember.tier_name || 'Standard'}
                />
              </List>
            </Section>

            <Section title="Balances">
              <List>
                <ListRow
                  title="Store Credit"
                  subtitle={`$${selectedMember.store_credit_balance.toFixed(2)}`}
                  leftSide={{
                    badge: {
                      text: 'Credit',
                      variant: 'highlight',
                    },
                  }}
                />
                <ListRow
                  title="Points"
                  subtitle={`${selectedMember.points_balance.toLocaleString()} pts`}
                />
              </List>
            </Section>

            {showCreditForm ? (
              <Section title="Issue Credit">
                <FormattedTextField
                  title="Amount"
                  type="currency"
                  value={creditAmount}
                  onChange={setCreditAmount}
                  placeholder="0.00"
                />
                <Button
                  title="Issue Credit"
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
          </ScrollView>
        </Screen>
      </Navigator>
    );
  }

  // Search screen
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

          <Section title="Search Members">
            <TextField
              title="Search"
              placeholder="Email, phone, or member #"
              value={searchQuery}
              onChange={setSearchQuery}
              onSubmit={searchMembers}
            />
            <Button
              title="Search"
              type="primary"
              isLoading={loading}
              onPress={searchMembers}
            />
          </Section>

          {members.length > 0 && (
            <Section title="Results">
              <List>
                {members.map((member) => (
                  <Selectable
                    key={member.id}
                    onPress={() => setSelectedMember(member)}
                  >
                    <ListRow
                      title={member.name || member.email}
                      subtitle={`${member.tier_name || 'Standard'} · $${member.store_credit_balance.toFixed(2)}`}
                      leftSide={{
                        badge: {
                          text: member.member_number,
                          variant: 'info',
                        },
                      }}
                    />
                  </Selectable>
                ))}
              </List>
            </Section>
          )}
        </ScrollView>
      </Screen>
    </Navigator>
  );
}
