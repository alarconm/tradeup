import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

/**
 * Signup page for TradeUp membership.
 *
 * Note: Membership tiers are now assigned by staff or earned through activity.
 * There is no payment step during signup - customers just create an account.
 */
export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Account form fields
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [name, setName] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setLoading(true);
    try {
      await signup({ email, password, name: name || undefined });
      // Navigate to dashboard after successful signup
      navigate('/dashboard?welcome=1');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Signup failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-md mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <Link to="/" className="text-2xl font-bold text-orange-500">
            TradeUp
          </Link>
          <h1 className="text-3xl font-bold mt-4">Create Your Account</h1>
          <p className="text-gray-600">Join TradeUp and start earning more from your trade-ins</p>
        </div>

        {error && (
          <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        {/* Account Creation Form */}
        <div className="card p-8">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="name" className="block text-sm font-medium mb-1">
                Full Name
              </label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="input"
                placeholder="John Doe"
              />
            </div>

            <div>
              <label htmlFor="email" className="block text-sm font-medium mb-1">
                Email <span className="text-red-500">*</span>
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input"
                placeholder="you@example.com"
                required
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium mb-1">
                Password <span className="text-red-500">*</span>
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
                placeholder="At least 8 characters"
                required
              />
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium mb-1">
                Confirm Password <span className="text-red-500">*</span>
              </label>
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="input"
                placeholder="Confirm your password"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary w-full mt-6"
            >
              {loading ? 'Creating Account...' : 'Create Account'}
            </button>
          </form>

          <p className="text-center mt-6 text-gray-600">
            Already have an account?{' '}
            <Link to="/login" className="text-orange-500 hover:underline">
              Sign in
            </Link>
          </p>
        </div>

        {/* Info about tiers */}
        <div className="mt-6 text-center text-sm text-gray-500">
          <p>Membership tiers and benefits are assigned by our team.</p>
          <p>Contact us to learn about tier eligibility.</p>
        </div>
      </div>
    </div>
  );
}
