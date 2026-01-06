import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  lookupShopifyCustomer,
  createMember,
  getTiers,
  type ShopifyCustomer,
  type Tier,
} from '../api/adminApi';
import { debounce } from '../utils/debounce';

// Icons
const Icons = {
  Search: () => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  ),
  Check: () => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  ),
  User: () => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  ),
  DollarSign: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="12" x2="12" y1="2" y2="22" />
      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </svg>
  ),
  CreditCard: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
      <line x1="1" x2="23" y1="10" y2="10" />
    </svg>
  ),
  Banknote: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="2" y="6" width="20" height="12" rx="2" />
      <circle cx="12" cy="12" r="2" />
      <path d="M6 12h.01M18 12h.01" />
    </svg>
  ),
  ArrowLeft: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m12 19-7-7 7-7" />
      <path d="M19 12H5" />
    </svg>
  ),
  Loader: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="animate-spin">
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  ),
  ShoppingBag: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z" />
      <line x1="3" x2="21" y1="6" y2="6" />
      <path d="M16 10a4 4 0 0 1-8 0" />
    </svg>
  ),
  AlertCircle: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" x2="12" y1="8" y2="12" />
      <line x1="12" x2="12.01" y1="16" y2="16" />
    </svg>
  ),
};

type PaymentMethod = 'store_credit' | 'card' | 'cash';

export default function NewMember() {
  const navigate = useNavigate();

  // State
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [selectedTier, setSelectedTier] = useState<Tier | null>(null);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('cash');
  const [tiers, setTiers] = useState<Tier[]>([]);
  const [shopifyCustomer, setShopifyCustomer] = useState<ShopifyCustomer | null>(null);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupDone, setLookupDone] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  // Fetch tiers on mount
  useEffect(() => {
    getTiers()
      .then((res) => {
        setTiers(res.tiers);
        // Default to Silver (first tier)
        if (res.tiers.length > 0) {
          setSelectedTier(res.tiers[0]);
        }
      })
      .catch(console.error);
  }, []);

  // Debounced Shopify lookup
  const lookupCustomer = useCallback(
    debounce(async (emailValue: string) => {
      if (!emailValue || !emailValue.includes('@')) {
        setShopifyCustomer(null);
        setLookupDone(false);
        return;
      }

      setLookupLoading(true);
      setError('');

      try {
        const customer = await lookupShopifyCustomer(emailValue);
        setShopifyCustomer(customer);
        setLookupDone(true);

        // Auto-fill name if found
        if (customer && !name) {
          const fullName = `${customer.firstName || ''} ${customer.lastName || ''}`.trim();
          if (fullName) setName(fullName);
          if (customer.phone) setPhone(customer.phone);
        }
      } catch (err) {
        console.error('Lookup failed:', err);
      } finally {
        setLookupLoading(false);
      }
    }, 500),
    [name]
  );

  // Handle email change
  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setEmail(value);
    setLookupDone(false);
    lookupCustomer(value);
  };

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email || !email.includes('@')) {
      setError('Please enter a valid email address');
      return;
    }

    if (!selectedTier) {
      setError('Please select a membership tier');
      return;
    }

    setCreating(true);

    try {
      const member = await createMember({
        email,
        name: name || undefined,
        phone: phone || undefined,
        tier_id: selectedTier.id,
        shopify_customer_id: shopifyCustomer?.id || undefined,
        notes: `Payment: ${paymentMethod}`,
      });

      // Navigate to the new member's page
      navigate(`/admin/members/${member.id}?created=1`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create member');
    } finally {
      setCreating(false);
    }
  };

  // Calculate if store credit can cover the tier price
  const canPayWithStoreCredit =
    shopifyCustomer && selectedTier && shopifyCustomer.storeCreditBalance >= selectedTier.monthly_price;

  return (
    <div className="max-w-2xl mx-auto admin-fade-in">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => navigate('/admin/members')}
          className="flex items-center gap-2 text-white/50 hover:text-white mb-4 transition-colors"
        >
          <Icons.ArrowLeft />
          Back to Members
        </button>
        <h1 className="admin-page-title text-3xl">New Member</h1>
        <p className="text-white/50 mt-2">Register a new TradeUp membership</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Step 1: Customer Lookup */}
        <div className="admin-glass admin-glass-glow p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <span className="w-8 h-8 rounded-full bg-orange-500/20 text-orange-400 flex items-center justify-center text-sm font-bold">
              1
            </span>
            Customer Email
          </h2>

          <div className="admin-search">
            <span className="admin-search-icon">
              {lookupLoading ? <Icons.Loader /> : <Icons.Search />}
            </span>
            <input
              type="email"
              placeholder="Enter customer email..."
              value={email}
              onChange={handleEmailChange}
              className="admin-input admin-input-lg pl-14"
              autoFocus
            />
          </div>

          {/* Shopify Customer Card */}
          {lookupDone && (
            <div
              className={`mt-4 p-4 rounded-xl border ${
                shopifyCustomer
                  ? 'bg-green-500/10 border-green-500/30'
                  : 'bg-yellow-500/10 border-yellow-500/30'
              } admin-slide-in`}
            >
              {shopifyCustomer ? (
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                    <Icons.Check />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-green-400">Found in Shopify!</p>
                    <p className="text-white/70 mt-1">
                      {shopifyCustomer.firstName} {shopifyCustomer.lastName}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-4 text-sm">
                      <div className="flex items-center gap-2 text-white/50">
                        <Icons.ShoppingBag />
                        <span>{shopifyCustomer.ordersCount} orders</span>
                      </div>
                      <div className="flex items-center gap-2 text-white/50">
                        <Icons.DollarSign />
                        <span>${shopifyCustomer.totalSpent.toFixed(2)} spent</span>
                      </div>
                      <div className="flex items-center gap-2 text-emerald-400 font-semibold">
                        <Icons.CreditCard />
                        <span>${shopifyCustomer.storeCreditBalance.toFixed(2)} credit</span>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-full bg-yellow-500/20 flex items-center justify-center flex-shrink-0">
                    <Icons.User />
                  </div>
                  <div>
                    <p className="font-semibold text-yellow-400">New Customer</p>
                    <p className="text-white/50 text-sm mt-1">
                      No Shopify account found. A new customer will be created when they make their first purchase.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Step 2: Customer Details */}
        <div className="admin-glass admin-glass-glow p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <span className="w-8 h-8 rounded-full bg-orange-500/20 text-orange-400 flex items-center justify-center text-sm font-bold">
              2
            </span>
            Customer Details
          </h2>

          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-white/50 mb-2">Name</label>
              <input
                type="text"
                placeholder="Full name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="admin-input"
              />
            </div>
            <div>
              <label className="block text-sm text-white/50 mb-2">Phone</label>
              <input
                type="tel"
                placeholder="Phone number"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="admin-input"
              />
            </div>
          </div>
        </div>

        {/* Step 3: Select Tier */}
        <div className="admin-glass admin-glass-glow p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <span className="w-8 h-8 rounded-full bg-orange-500/20 text-orange-400 flex items-center justify-center text-sm font-bold">
              3
            </span>
            Select Tier
          </h2>

          <div className="grid sm:grid-cols-3 gap-4">
            {tiers.map((tier, idx) => {
              const tierClass = tier.name.toLowerCase();
              const isSelected = selectedTier?.id === tier.id;

              return (
                <button
                  key={tier.id}
                  type="button"
                  onClick={() => setSelectedTier(tier)}
                  className={`admin-tier-card ${tierClass} ${isSelected ? 'selected' : ''} admin-slide-in`}
                  style={{ animationDelay: `${idx * 75}ms` }}
                >
                  <div className="tier-shine" />
                  <div className="relative z-10 text-left">
                    {/* Tier Name */}
                    <div className="flex items-center justify-between mb-3">
                      <span
                        className={`admin-tier-badge ${tierClass}`}
                        style={{ fontSize: '10px', padding: '4px 8px' }}
                      >
                        {tier.name}
                      </span>
                      {isSelected && (
                        <span className="text-orange-400">
                          <Icons.Check />
                        </span>
                      )}
                    </div>

                    {/* Price */}
                    <p className="text-2xl font-bold mb-3">
                      ${tier.monthly_price}
                      <span className="text-sm text-white/40 font-normal">/mo</span>
                    </p>

                    {/* Benefits */}
                    <div className="space-y-2 text-sm text-white/60">
                      <div className="flex items-center gap-2">
                        <span className="text-green-400">✓</span>
                        <span>{Math.round(tier.bonus_rate * 100)}% Cashback</span>
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Step 4: Payment */}
        <div className="admin-glass admin-glass-glow p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <span className="w-8 h-8 rounded-full bg-orange-500/20 text-orange-400 flex items-center justify-center text-sm font-bold">
              4
            </span>
            Payment Method
          </h2>

          <div className="grid sm:grid-cols-3 gap-4">
            {/* Store Credit */}
            <button
              type="button"
              onClick={() => canPayWithStoreCredit && setPaymentMethod('store_credit')}
              disabled={!canPayWithStoreCredit}
              className={`p-4 rounded-xl border-2 text-left transition-all ${
                paymentMethod === 'store_credit'
                  ? 'border-orange-500 bg-orange-500/10'
                  : canPayWithStoreCredit
                  ? 'border-white/10 hover:border-white/20'
                  : 'border-white/5 opacity-40 cursor-not-allowed'
              }`}
            >
              <div className="flex items-center gap-3 mb-2">
                <Icons.DollarSign />
                <span className="font-semibold">Store Credit</span>
              </div>
              <p className="text-sm text-white/50">
                {shopifyCustomer
                  ? `$${shopifyCustomer.storeCreditBalance.toFixed(2)} available`
                  : 'Not available'}
              </p>
            </button>

            {/* Card on File */}
            <button
              type="button"
              onClick={() => setPaymentMethod('card')}
              className={`p-4 rounded-xl border-2 text-left transition-all ${
                paymentMethod === 'card'
                  ? 'border-orange-500 bg-orange-500/10'
                  : 'border-white/10 hover:border-white/20'
              }`}
            >
              <div className="flex items-center gap-3 mb-2">
                <Icons.CreditCard />
                <span className="font-semibold">Card</span>
              </div>
              <p className="text-sm text-white/50">Process later</p>
            </button>

            {/* Cash */}
            <button
              type="button"
              onClick={() => setPaymentMethod('cash')}
              className={`p-4 rounded-xl border-2 text-left transition-all ${
                paymentMethod === 'cash'
                  ? 'border-orange-500 bg-orange-500/10'
                  : 'border-white/10 hover:border-white/20'
              }`}
            >
              <div className="flex items-center gap-3 mb-2">
                <Icons.Banknote />
                <span className="font-semibold">Cash</span>
              </div>
              <p className="text-sm text-white/50">Mark as paid</p>
            </button>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="flex items-center gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400">
            <Icons.AlertCircle />
            <span>{error}</span>
          </div>
        )}

        {/* Submit */}
        <div className="flex gap-4">
          <button
            type="button"
            onClick={() => navigate('/admin/members')}
            className="admin-btn admin-btn-secondary flex-1"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={creating || !email || !selectedTier}
            className="admin-btn admin-btn-primary flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {creating ? (
              <>
                <Icons.Loader />
                Creating...
              </>
            ) : (
              <>
                <Icons.Check />
                Create Membership
                {selectedTier && ` · $${selectedTier.monthly_price}`}
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
