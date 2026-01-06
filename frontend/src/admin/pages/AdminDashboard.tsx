import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getMembers, getTiers, type Member, type Tier } from '../api/adminApi';

// Icons
const Icons = {
  Users: () => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  TrendingUp: () => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="22,7 13.5,15.5 8.5,10.5 2,17" />
      <polyline points="16,7 22,7 22,13" />
    </svg>
  ),
  DollarSign: () => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="12" x2="12" y1="2" y2="22" />
      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </svg>
  ),
  Zap: () => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="13,2 3,14 12,14 11,22 21,10 12,10 13,2" />
    </svg>
  ),
  Plus: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M5 12h14" />
      <path d="M12 5v14" />
    </svg>
  ),
  ArrowRight: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M5 12h14" />
      <path d="m12 5 7 7-7 7" />
    </svg>
  ),
  UserPlus: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <line x1="19" x2="19" y1="8" y2="14" />
      <line x1="22" x2="16" y1="11" y2="11" />
    </svg>
  ),
  Star: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26 12,2" />
    </svg>
  ),
  Gift: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="20,12 20,22 4,22 4,12" />
      <rect x="2" y="7" width="20" height="5" />
      <line x1="12" x2="12" y1="22" y2="7" />
      <path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z" />
      <path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z" />
    </svg>
  ),
};

// Animated counter component
function AnimatedCounter({ value, prefix = '', suffix = '' }: { value: number; prefix?: string; suffix?: string }) {
  const [displayed, setDisplayed] = useState(0);

  useEffect(() => {
    const duration = 1000;
    const steps = 30;
    const increment = value / steps;
    let current = 0;
    let step = 0;

    const timer = setInterval(() => {
      step++;
      current = Math.min(increment * step, value);
      setDisplayed(current);
      if (step >= steps) clearInterval(timer);
    }, duration / steps);

    return () => clearInterval(timer);
  }, [value]);

  return (
    <span className="admin-counter">
      {prefix}
      {displayed.toLocaleString('en-US', {
        minimumFractionDigits: prefix === '$' ? 2 : 0,
        maximumFractionDigits: prefix === '$' ? 2 : 0,
      })}
      {suffix}
    </span>
  );
}

// Tier badge component
function TierBadge({ tier }: { tier: string }) {
  const tierClass = tier.toLowerCase();
  return (
    <span className={`admin-tier-badge ${tierClass}`}>
      {tier}
    </span>
  );
}

export default function AdminDashboard() {
  const [members, setMembers] = useState<Member[]>([]);
  const [tiers, setTiers] = useState<Tier[]>([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalMembers: 0,
    activeMembers: 0,
    newThisMonth: 0,
    totalCredited: 0,
  });

  useEffect(() => {
    Promise.all([
      getMembers({ limit: 5 }),
      getTiers(),
    ])
      .then(([membersRes, tiersRes]) => {
        setMembers(membersRes.members);
        setTiers(tiersRes.tiers);
        setStats({
          totalMembers: membersRes.total,
          activeMembers: membersRes.members.filter((m) => m.status === 'active').length,
          newThisMonth: Math.floor(membersRes.total * 0.15), // Placeholder
          totalCredited: 2929.05, // From our test
        });
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  // Mock activity data
  const recentActivity = [
    { id: '1', type: 'member', icon: Icons.UserPlus, description: 'Michael joined as Silver member', time: '2 min ago', color: 'orange' },
    { id: '2', type: 'event', icon: Icons.Gift, description: 'Trade Night credited $487.20 to 32 customers', time: '1 hour ago', color: 'green' },
    { id: '3', type: 'upgrade', icon: Icons.Star, description: 'Sarah upgraded to Gold', time: '3 hours ago', color: 'gold' },
    { id: '4', type: 'member', icon: Icons.UserPlus, description: 'John joined as Silver member', time: '5 hours ago', color: 'orange' },
  ];

  return (
    <div className="space-y-8 admin-fade-in">
      {/* Header */}
      <div className="admin-header">
        <div>
          <h1 className="admin-page-title">
            Dashboard
          </h1>
          <p className="text-white/50 mt-1">Welcome back! Here's what's happening.</p>
        </div>
        <div className="flex gap-3">
          <Link to="/admin/events/new" className="admin-btn admin-btn-secondary">
            <Icons.Zap />
            New Event
          </Link>
          <Link to="/admin/members/new" className="admin-btn admin-btn-primary">
            <Icons.Plus />
            New Member
          </Link>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Members */}
        <div className="admin-glass admin-glass-glow admin-stat-card stat-orange p-6">
          <div className="flex items-start justify-between mb-4">
            <div className="p-3 rounded-xl bg-orange-500/20">
              <Icons.Users />
            </div>
            <span className="text-xs text-green-400 font-medium flex items-center gap-1">
              +12%
              <Icons.TrendingUp />
            </span>
          </div>
          <div className="text-3xl font-bold mb-1">
            {loading ? (
              <div className="admin-skeleton h-9 w-20" />
            ) : (
              <AnimatedCounter value={stats.totalMembers} />
            )}
          </div>
          <p className="text-sm text-white/50">Total Members</p>
        </div>

        {/* Active Members */}
        <div className="admin-glass admin-glass-glow admin-stat-card p-6">
          <div className="flex items-start justify-between mb-4">
            <div className="p-3 rounded-xl bg-green-500/20">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </div>
          </div>
          <div className="text-3xl font-bold mb-1">
            {loading ? (
              <div className="admin-skeleton h-9 w-20" />
            ) : (
              <AnimatedCounter value={stats.activeMembers} />
            )}
          </div>
          <p className="text-sm text-white/50">Active This Month</p>
        </div>

        {/* New This Month */}
        <div className="admin-glass admin-glass-glow admin-stat-card p-6">
          <div className="flex items-start justify-between mb-4">
            <div className="p-3 rounded-xl bg-blue-500/20">
              <Icons.UserPlus />
            </div>
          </div>
          <div className="text-3xl font-bold mb-1">
            {loading ? (
              <div className="admin-skeleton h-9 w-16" />
            ) : (
              <AnimatedCounter value={stats.newThisMonth} />
            )}
          </div>
          <p className="text-sm text-white/50">New This Month</p>
        </div>

        {/* Total Credited */}
        <div className="admin-glass admin-glass-glow admin-stat-card stat-green p-6">
          <div className="flex items-start justify-between mb-4">
            <div className="p-3 rounded-xl bg-emerald-500/20">
              <Icons.DollarSign />
            </div>
          </div>
          <div className="text-3xl font-bold mb-1 text-emerald-400">
            {loading ? (
              <div className="admin-skeleton h-9 w-28" />
            ) : (
              <AnimatedCounter value={stats.totalCredited} prefix="$" />
            )}
          </div>
          <p className="text-sm text-white/50">Credited This Month</p>
        </div>
      </div>

      {/* Content Grid */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Recent Members */}
        <div className="lg:col-span-2 admin-glass admin-glass-glow p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold">Recent Members</h2>
            <Link to="/admin/members" className="text-sm text-orange-400 hover:text-orange-300 flex items-center gap-1">
              View All <Icons.ArrowRight />
            </Link>
          </div>

          {loading ? (
            <div className="space-y-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="flex items-center gap-4">
                  <div className="admin-skeleton w-10 h-10 rounded-full" />
                  <div className="flex-1">
                    <div className="admin-skeleton h-4 w-32 mb-2" />
                    <div className="admin-skeleton h-3 w-48" />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              {members.map((member, idx) => (
                <Link
                  key={member.id}
                  to={`/admin/members/${member.id}`}
                  className="flex items-center gap-4 p-3 rounded-xl hover:bg-white/5 transition-colors admin-slide-in"
                  style={{ animationDelay: `${idx * 50}ms` }}
                >
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-orange-500/30 to-orange-600/30 flex items-center justify-center flex-shrink-0">
                    <span className="text-orange-400 font-semibold text-sm">
                      {(member.name || member.email)[0].toUpperCase()}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">
                      {member.name || member.email}
                    </p>
                    <p className="text-sm text-white/40 truncate">
                      {member.member_number} · {member.email}
                    </p>
                  </div>
                  <TierBadge tier={member.tier?.name || 'None'} />
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Activity Feed */}
        <div className="admin-glass admin-glass-glow p-6">
          <h2 className="text-lg font-semibold mb-6">Recent Activity</h2>
          <div className="space-y-1">
            {recentActivity.map((activity, idx) => (
              <div
                key={activity.id}
                className="admin-activity-item admin-slide-in"
                style={{ animationDelay: `${idx * 75}ms` }}
              >
                <div
                  className={`admin-activity-icon ${activity.type}`}
                  style={{
                    background:
                      activity.color === 'orange'
                        ? 'rgba(232, 93, 39, 0.2)'
                        : activity.color === 'green'
                        ? 'rgba(16, 185, 129, 0.2)'
                        : 'rgba(255, 215, 0, 0.2)',
                    color:
                      activity.color === 'orange'
                        ? '#e85d27'
                        : activity.color === 'green'
                        ? '#10b981'
                        : '#ffd700',
                  }}
                >
                  <activity.icon />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm">{activity.description}</p>
                  <p className="text-xs text-white/30 mt-1">{activity.time}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="admin-glass admin-glass-glow p-6">
        <h2 className="text-lg font-semibold mb-6">Quick Actions</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Link
            to="/admin/members/new"
            className="group p-6 rounded-xl bg-white/5 hover:bg-orange-500/10 border border-white/5 hover:border-orange-500/30 transition-all"
          >
            <div className="w-12 h-12 rounded-xl bg-orange-500/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <Icons.UserPlus />
            </div>
            <h3 className="font-semibold mb-1">Register Member</h3>
            <p className="text-sm text-white/40">Sign up a new TradeUp member</p>
          </Link>

          <Link
            to="/admin/events/new"
            className="group p-6 rounded-xl bg-white/5 hover:bg-green-500/10 border border-white/5 hover:border-green-500/30 transition-all"
          >
            <div className="w-12 h-12 rounded-xl bg-green-500/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <Icons.Gift />
            </div>
            <h3 className="font-semibold mb-1">Credit Event</h3>
            <p className="text-sm text-white/40">Run a store credit promotion</p>
          </Link>

          <Link
            to="/admin/members"
            className="group p-6 rounded-xl bg-white/5 hover:bg-blue-500/10 border border-white/5 hover:border-blue-500/30 transition-all"
          >
            <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <Icons.Users />
            </div>
            <h3 className="font-semibold mb-1">Manage Members</h3>
            <p className="text-sm text-white/40">View and edit member accounts</p>
          </Link>

          <Link
            to="/admin/events"
            className="group p-6 rounded-xl bg-white/5 hover:bg-purple-500/10 border border-white/5 hover:border-purple-500/30 transition-all"
          >
            <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <Icons.Zap />
            </div>
            <h3 className="font-semibold mb-1">Event History</h3>
            <p className="text-sm text-white/40">View past credit events</p>
          </Link>
        </div>
      </div>

      {/* Tier Breakdown */}
      <div className="admin-glass admin-glass-glow p-6">
        <h2 className="text-lg font-semibold mb-6">Membership Tiers</h2>
        <div className="grid md:grid-cols-3 gap-4">
          {tiers.map((tier, idx) => {
            const tierClass = tier.name.toLowerCase();
            const memberCount = Math.floor(Math.random() * 100) + 20; // Placeholder
            return (
              <div
                key={tier.id}
                className={`admin-tier-card ${tierClass} admin-slide-in`}
                style={{ animationDelay: `${idx * 100}ms` }}
              >
                <div className="tier-shine" />
                <div className="relative z-10">
                  <div className="flex items-center justify-between mb-4">
                    <TierBadge tier={tier.name} />
                    <span className="text-2xl font-bold">${tier.monthly_price}</span>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between text-white/60">
                      <span>Cashback Rate</span>
                      <span className="font-semibold text-white">{Math.round(tier.bonus_rate * 100)}%</span>
                    </div>
                    <div className="flex justify-between text-white/60">
                      <span>Members</span>
                      <span className="font-semibold text-white">{memberCount}</span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
