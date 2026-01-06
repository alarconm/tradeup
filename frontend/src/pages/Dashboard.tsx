import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  getMembershipStatus,
  getStoreCredit,
  getBonusHistory,
  linkShopifyAccount
} from '../api/membership';
import type { MembershipStatus, BonusTransaction, StoreCreditBalance } from '../api/membership';

export default function Dashboard() {
  const { member, logout, refreshMember } = useAuth();
  const [searchParams] = useSearchParams();
  const [membershipStatus, setMembershipStatus] = useState<MembershipStatus | null>(null);
  const [storeCredit, setStoreCredit] = useState<StoreCreditBalance | null>(null);
  const [bonusHistory, setBonusHistory] = useState<BonusTransaction[]>([]);
  const [linkingShopify, setLinkingShopify] = useState(false);

  const isWelcome = searchParams.get('welcome') === '1';

  useEffect(() => {
    // Refresh member data on mount
    refreshMember();

    // Get membership status
    getMembershipStatus()
      .then(setMembershipStatus)
      .catch(console.error);

    // Get store credit balance
    getStoreCredit()
      .then(setStoreCredit)
      .catch(console.error);

    // Get bonus history
    getBonusHistory(5, 0)
      .then(res => setBonusHistory(res.transactions))
      .catch(console.error);
  }, []);

  if (!member) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-orange-500">TradeUp</h1>
          <div className="flex items-center gap-4">
            <span className="text-gray-600">{member.name || member.email}</span>
            <button onClick={logout} className="btn btn-secondary">
              Logout
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        {/* Welcome Message */}
        {isWelcome && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6">
            <h2 className="text-green-800 font-semibold">🎉 Welcome to TradeUp!</h2>
            <p className="text-green-700">Your membership is now active. Start trading in your cards to earn bonuses!</p>
          </div>
        )}

        {/* Pending Payment Warning */}
        {member.status === 'pending' && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
            <h2 className="text-yellow-800 font-semibold">⚠️ Complete Your Signup</h2>
            <p className="text-yellow-700">Please complete payment to activate your membership benefits.</p>
            <Link to="/signup" className="btn btn-primary mt-2">
              Complete Signup
            </Link>
          </div>
        )}

        <div className="grid md:grid-cols-3 gap-6 mb-8">
          {/* Member Card */}
          <div className="card p-6">
            <h3 className="text-sm text-gray-500 mb-1">Member Number</h3>
            <p className="text-2xl font-bold">{member.member_number}</p>
          </div>

          {/* Tier Card */}
          <div className="card p-6">
            <h3 className="text-sm text-gray-500 mb-1">Membership Tier</h3>
            <p className="text-2xl font-bold text-orange-500">
              {member.tier?.name || 'No Plan'}
            </p>
            {member.tier && (
              <p className="text-sm text-gray-600">
                {Math.round(member.tier.bonus_rate * 100)}% Cashback
              </p>
            )}
          </div>

          {/* Store Credit */}
          <div className="card p-6">
            <h3 className="text-sm text-gray-500 mb-1">Store Credit Balance</h3>
            {storeCredit ? (
              <>
                <p className="text-2xl font-bold text-green-600">
                  ${storeCredit.balance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
                <p className="text-sm text-gray-500">
                  {storeCredit.message || 'Use at checkout'}
                </p>
              </>
            ) : member?.shopify_customer_id ? (
              <p className="text-gray-500">Loading...</p>
            ) : (
              <>
                <p className="text-xl text-gray-400">Not linked</p>
                <button
                  onClick={async () => {
                    setLinkingShopify(true);
                    try {
                      const result = await linkShopifyAccount();
                      setStoreCredit({ balance: result.store_credit_balance, currency: 'USD' });
                      refreshMember();
                    } catch (err) {
                      console.error('Failed to link Shopify:', err);
                      alert('Could not link your Shopify account. Make sure you have made a purchase with this email.');
                    } finally {
                      setLinkingShopify(false);
                    }
                  }}
                  disabled={linkingShopify}
                  className="text-sm text-orange-500 hover:underline mt-1"
                >
                  {linkingShopify ? 'Linking...' : 'Link Shopify Account'}
                </button>
              </>
            )}
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          {/* Bonus Stats */}
          <div className="card p-6">
            <h3 className="text-lg font-semibold mb-4">Trade-In Stats</h3>
            <div className="space-y-4">
              <div className="flex justify-between">
                <span className="text-gray-600">Total Credit Earned</span>
                <span className="font-semibold text-green-600">
                  ${member.stats?.total_credit_earned?.toFixed(2) || '0.00'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Total Trade-Ins</span>
                <span className="font-semibold">{member.stats?.total_trade_ins || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Total Trade Value</span>
                <span className="font-semibold">
                  ${member.stats?.total_trade_value?.toFixed(2) || '0.00'}
                </span>
              </div>
            </div>
          </div>

          {/* Membership Status */}
          <div className="card p-6">
            <h3 className="text-lg font-semibold mb-4">Membership</h3>
            {membershipStatus ? (
              <div className="space-y-4">
                <div className="flex justify-between">
                  <span className="text-gray-600">Status</span>
                  <span className={`font-semibold ${membershipStatus.status === 'active' ? 'text-green-600' : 'text-yellow-600'}`}>
                    {membershipStatus.status.charAt(0).toUpperCase() + membershipStatus.status.slice(1)}
                  </span>
                </div>
                {membershipStatus.tier && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">Tier</span>
                    <span className="font-semibold text-orange-500">
                      {membershipStatus.tier.name}
                    </span>
                  </div>
                )}
                {membershipStatus.tier_expires_at && (
                  <div className="bg-yellow-50 p-3 rounded-lg text-yellow-800 text-sm">
                    Tier expires on{' '}
                    {new Date(membershipStatus.tier_expires_at).toLocaleDateString()}
                  </div>
                )}
                {membershipStatus.tier_assigned_by && (
                  <div className="text-xs text-gray-400">
                    Assigned: {membershipStatus.tier_assigned_by.replace('staff:', '')}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-gray-600">No tier assigned</p>
            )}
          </div>
        </div>

        {/* Recent Activity */}
        <div className="card p-6 mt-6">
          <h3 className="text-lg font-semibold mb-4">Recent Bonus Activity</h3>
          {bonusHistory.length > 0 ? (
            <div className="space-y-3">
              {bonusHistory.map((tx) => (
                <div
                  key={tx.id}
                  className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0"
                >
                  <div>
                    <p className="font-medium">
                      {tx.transaction_type === 'credit' ? 'Store Credit' : tx.transaction_type}
                    </p>
                    <p className="text-sm text-gray-500">
                      {tx.reason || tx.notes || 'Bonus credit'}
                    </p>
                    <p className="text-xs text-gray-400">
                      {new Date(tx.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className={`text-lg font-semibold ${tx.bonus_amount >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {tx.bonus_amount >= 0 ? '+' : ''}${Math.abs(tx.bonus_amount).toFixed(2)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <p>No bonus activity yet.</p>
              <p className="text-sm">Trade in some cards to earn store credit!</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
