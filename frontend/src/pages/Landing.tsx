import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { getTiers } from '../api/membership';
import type { Tier } from '../api/auth';

export default function Landing() {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [tiers, setTiers] = useState<Tier[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard');
    }
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    getTiers()
      .then((response) => {
        setTiers(response.tiers);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-orange-500">TradeUp</h1>
          <div className="space-x-4">
            <Link to="/login" className="btn btn-secondary">
              Login
            </Link>
            <Link to="/signup" className="btn btn-primary">
              Join Now
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="py-20 px-4 text-center bg-gradient-to-b from-orange-50 to-white">
        <h2 className="text-5xl font-bold mb-6">
          Earn <span className="text-orange-500">More</span> From Your Trade-Ins
        </h2>
        <p className="text-xl text-gray-600 max-w-2xl mx-auto mb-8">
          TradeUp members earn bonus store credit on trade-ins and purchases.
          Join our loyalty program and start earning more!
        </p>
        <Link to="/signup" className="btn btn-primary text-lg px-8 py-3">
          Start Your Membership
        </Link>
      </section>

      {/* How It Works */}
      <section className="py-16 px-4">
        <div className="max-w-4xl mx-auto">
          <h3 className="text-3xl font-bold text-center mb-12">How TradeUp Works</h3>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">1</span>
              </div>
              <h4 className="font-semibold mb-2">Trade In Your Cards</h4>
              <p className="text-gray-600">Bring your cards to the shop. We value them and credit your account.</p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">2</span>
              </div>
              <h4 className="font-semibold mb-2">We List & Sell</h4>
              <p className="text-gray-600">Your cards go on our store. When they sell, you earn a bonus!</p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">3</span>
              </div>
              <h4 className="font-semibold mb-2">Earn Bonus Credit</h4>
              <p className="text-gray-600">The faster it sells, the more you earn. Up to 30% of the profit!</p>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="py-16 px-4 bg-gray-50">
        <div className="max-w-5xl mx-auto">
          <h3 className="text-3xl font-bold text-center mb-4">Choose Your Tier</h3>
          <p className="text-center text-gray-600 mb-12">Higher tiers get bigger bonuses and more perks</p>

          {loading ? (
            <div className="text-center">Loading tiers...</div>
          ) : (
            <div className="grid md:grid-cols-3 gap-6">
              {tiers.map((tier, index) => (
                <div
                  key={tier.id}
                  className={`tier-card ${index === 1 ? 'ring-2 ring-orange-500 relative' : ''}`}
                >
                  {index === 1 && (
                    <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-orange-500 text-white text-sm px-3 py-1 rounded-full">
                      Most Popular
                    </span>
                  )}
                  <h4 className="text-xl font-bold mb-2">{tier.name}</h4>
                  <p className="text-3xl font-bold text-orange-500 mb-4">
                    ${tier.monthly_price}
                    <span className="text-sm text-gray-500 font-normal">/mo</span>
                  </p>
                  <ul className="space-y-3 mb-6">
                    <li className="flex items-center gap-2">
                      <span className="text-green-500">✓</span>
                      <span>{Math.round(tier.bonus_rate * 100)}% Cashback on Purchases</span>
                    </li>
                    {tier.benefits?.discount_percent != null && (
                      <li className="flex items-center gap-2">
                        <span className="text-green-500">✓</span>
                        <span>{Number(tier.benefits.discount_percent)}% store discount</span>
                      </li>
                    )}
                    {tier.benefits?.early_access != null && (
                      <li className="flex items-center gap-2">
                        <span className="text-green-500">✓</span>
                        <span>Early access to new products</span>
                      </li>
                    )}
                  </ul>
                  <Link
                    to={`/signup?tier=${tier.id}`}
                    className="btn btn-primary w-full text-center block"
                  >
                    Get Started
                  </Link>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-4 bg-gray-900 text-gray-400">
        <div className="max-w-6xl mx-auto text-center">
          <p>&copy; 2026 ORB Sports Cards. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
