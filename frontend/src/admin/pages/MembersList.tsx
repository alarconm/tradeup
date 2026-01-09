/**
 * MembersList - Premium Light Mode
 * World-class Shopify App Store design
 */
import { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  Search,
  UserPlus,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  MoreVertical,
  X,
  Users,
} from 'lucide-react';
import { getMembers, getTiers, type Member, type Tier } from '../api/adminApi';
import { debounce } from '../utils/debounce';

// Design tokens
const colors = {
  bgPage: '#f6f6f7',
  bgSurface: '#ffffff',
  bgSurfaceHover: '#f9fafb',
  bgSubdued: '#fafbfb',
  text: '#202223',
  textSecondary: '#6d7175',
  textSubdued: '#8c9196',
  border: '#e1e3e5',
  borderSubdued: '#ebebeb',
  primary: '#5c6ac4',
  primaryLight: '#f4f5fa',
  success: '#008060',
  successLight: '#e3f1ed',
  warning: '#b98900',
  warningLight: '#fcf1cd',
  critical: '#d72c0d',
  criticalLight: '#fbeae5',
  interactive: '#2c6ecb',
};

const shadows = {
  card: '0 1px 2px rgba(0, 0, 0, 0.05), 0 1px 3px rgba(0, 0, 0, 0.1)',
  cardHover: '0 2px 4px rgba(0, 0, 0, 0.08), 0 4px 12px rgba(0, 0, 0, 0.12)',
};

// Responsive hook
function useResponsive() {
  const [breakpoint, setBreakpoint] = useState<'mobile' | 'tablet' | 'desktop'>('desktop');
  useEffect(() => {
    const check = () => {
      if (window.innerWidth < 640) setBreakpoint('mobile');
      else if (window.innerWidth < 1024) setBreakpoint('tablet');
      else setBreakpoint('desktop');
    };
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);
  return breakpoint;
}

// Tier badge component
function TierBadge({ tier }: { tier: string }) {
  const tierColors: Record<string, { bg: string; color: string }> = {
    bronze: { bg: '#fdf4e8', color: '#8b5a2b' },
    silver: { bg: '#f3f4f6', color: '#6b7280' },
    gold: { bg: '#fef9e7', color: '#b8860b' },
    platinum: { bg: '#f1f5f9', color: '#64748b' },
    none: { bg: colors.bgSubdued, color: colors.textSubdued },
  };
  const tierKey = tier?.toLowerCase() || 'none';
  const style = tierColors[tierKey] || tierColors.silver;

  if (!tier || tier === 'None') {
    return <span style={{ fontSize: 13, color: colors.textSubdued }}>—</span>;
  }

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '4px 10px',
        borderRadius: 20,
        backgroundColor: style.bg,
        color: style.color,
        fontSize: 12,
        fontWeight: 600,
        textTransform: 'capitalize',
      }}
    >
      {tier}
    </span>
  );
}

// Status badge component
function StatusBadge({ status }: { status: string }) {
  const statusStyles: Record<string, { bg: string; color: string; dot: string }> = {
    active: { bg: colors.successLight, color: colors.success, dot: colors.success },
    pending: { bg: colors.warningLight, color: colors.warning, dot: colors.warning },
    paused: { bg: colors.bgSubdued, color: colors.textSecondary, dot: colors.textSubdued },
    cancelled: { bg: colors.criticalLight, color: colors.critical, dot: colors.critical },
  };
  const style = statusStyles[status] || statusStyles.paused;

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '4px 10px',
        borderRadius: 6,
        backgroundColor: style.bg,
        color: style.color,
        fontSize: 12,
        fontWeight: 500,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          backgroundColor: style.dot,
        }}
      />
      {status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Unknown'}
    </span>
  );
}

export default function MembersList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [members, setMembers] = useState<Member[]>([]);
  const [tiers, setTiers] = useState<Tier[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const breakpoint = useResponsive();

  // Filter state
  const [search, setSearch] = useState(searchParams.get('search') || '');
  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') || '');
  const [tierFilter, setTierFilter] = useState(searchParams.get('tier') || '');
  const page = parseInt(searchParams.get('page') || '1', 10);
  const limit = 20;

  // Fetch members
  const fetchMembers = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getMembers({
        page,
        limit,
        search: search || undefined,
        status: statusFilter || undefined,
        tier_id: tierFilter ? parseInt(tierFilter, 10) : undefined,
      });
      setMembers(result.members);
      setTotal(result.total);
      setPages(result.pages);
    } catch (error) {
      console.error('Failed to fetch members:', error);
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter, tierFilter]);

  // Fetch tiers once
  useEffect(() => {
    getTiers()
      .then((res) => setTiers(res.tiers))
      .catch(console.error);
  }, []);

  // Debounced search
  const debouncedSearch = useCallback(
    debounce((value: string) => {
      const params = new URLSearchParams(searchParams);
      if (value) {
        params.set('search', value);
      } else {
        params.delete('search');
      }
      params.set('page', '1');
      setSearchParams(params);
    }, 300),
    [searchParams]
  );

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearch(value);
    debouncedSearch(value);
  };

  const handleFilterChange = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams);
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    params.set('page', '1');
    setSearchParams(params);
    if (key === 'status') setStatusFilter(value);
    if (key === 'tier') setTierFilter(value);
  };

  const handlePageChange = (newPage: number) => {
    const params = new URLSearchParams(searchParams);
    params.set('page', String(newPage));
    setSearchParams(params);
  };

  const clearFilters = () => {
    setSearch('');
    setStatusFilter('');
    setTierFilter('');
    setSearchParams({});
  };

  useEffect(() => {
    fetchMembers();
  }, [fetchMembers]);

  const hasFilters = search || statusFilter || tierFilter;

  // Card style
  const cardStyle: React.CSSProperties = {
    backgroundColor: colors.bgSurface,
    borderRadius: 12,
    border: `1px solid ${colors.border}`,
    boxShadow: shadows.card,
  };

  // Input style
  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '10px 12px 10px 40px',
    backgroundColor: colors.bgSurface,
    border: `1px solid ${colors.border}`,
    borderRadius: 8,
    fontSize: 14,
    color: colors.text,
    outline: 'none',
    transition: 'border-color 150ms ease, box-shadow 150ms ease',
  };

  // Select style
  const selectStyle: React.CSSProperties = {
    width: '100%',
    padding: '10px 32px 10px 12px',
    backgroundColor: colors.bgSurface,
    border: `1px solid ${colors.border}`,
    borderRadius: 8,
    fontSize: 14,
    color: colors.text,
    outline: 'none',
    appearance: 'none',
    cursor: 'pointer',
  };

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          flexDirection: breakpoint === 'mobile' ? 'column' : 'row',
          justifyContent: 'space-between',
          alignItems: breakpoint === 'mobile' ? 'flex-start' : 'center',
          gap: 16,
          marginBottom: 24,
        }}
      >
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: colors.text, margin: 0, letterSpacing: '-0.5px' }}>
            Members
          </h1>
          <p style={{ fontSize: 14, color: colors.textSecondary, margin: '4px 0 0 0' }}>
            {total} total member{total !== 1 ? 's' : ''}
          </p>
        </div>
        <Link
          to="/admin/members/new"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '10px 16px',
            backgroundColor: colors.primary,
            border: 'none',
            borderRadius: 8,
            color: '#fff',
            fontSize: 14,
            fontWeight: 500,
            textDecoration: 'none',
            transition: 'background 150ms ease',
            width: breakpoint === 'mobile' ? '100%' : 'auto',
            justifyContent: 'center',
          }}
        >
          <UserPlus size={18} />
          New Member
        </Link>
      </div>

      {/* Filters */}
      <div style={{ ...cardStyle, padding: 16, marginBottom: 24 }}>
        <div
          style={{
            display: 'flex',
            flexDirection: breakpoint === 'desktop' ? 'row' : 'column',
            gap: 12,
          }}
        >
          {/* Search */}
          <div style={{ position: 'relative', flex: 1 }}>
            <Search
              size={18}
              style={{
                position: 'absolute',
                left: 12,
                top: '50%',
                transform: 'translateY(-50%)',
                color: colors.textSubdued,
                pointerEvents: 'none',
              }}
            />
            <input
              type="text"
              placeholder="Search by name, email, or member number..."
              value={search}
              onChange={handleSearchChange}
              style={inputStyle}
              onFocus={(e) => {
                e.target.style.borderColor = colors.primary;
                e.target.style.boxShadow = `0 0 0 1px ${colors.primary}`;
              }}
              onBlur={(e) => {
                e.target.style.borderColor = colors.border;
                e.target.style.boxShadow = 'none';
              }}
            />
          </div>

          {/* Status Filter */}
          <div style={{ position: 'relative', minWidth: breakpoint === 'mobile' ? '100%' : 150 }}>
            <select
              value={statusFilter}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              style={selectStyle}
            >
              <option value="">All Status</option>
              <option value="active">Active</option>
              <option value="pending">Pending</option>
              <option value="paused">Paused</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <ChevronDown
              size={16}
              style={{
                position: 'absolute',
                right: 12,
                top: '50%',
                transform: 'translateY(-50%)',
                color: colors.textSubdued,
                pointerEvents: 'none',
              }}
            />
          </div>

          {/* Tier Filter */}
          <div style={{ position: 'relative', minWidth: breakpoint === 'mobile' ? '100%' : 150 }}>
            <select
              value={tierFilter}
              onChange={(e) => handleFilterChange('tier', e.target.value)}
              style={selectStyle}
            >
              <option value="">All Tiers</option>
              {tiers.map((tier) => (
                <option key={tier.id} value={tier.id}>
                  {tier.name}
                </option>
              ))}
            </select>
            <ChevronDown
              size={16}
              style={{
                position: 'absolute',
                right: 12,
                top: '50%',
                transform: 'translateY(-50%)',
                color: colors.textSubdued,
                pointerEvents: 'none',
              }}
            />
          </div>

          {/* Clear Filters */}
          {hasFilters && (
            <button
              onClick={clearFilters}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '10px 14px',
                backgroundColor: colors.bgSurface,
                border: `1px solid ${colors.border}`,
                borderRadius: 8,
                color: colors.text,
                fontSize: 14,
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'background 150ms ease',
                minWidth: breakpoint === 'mobile' ? '100%' : 'auto',
                justifyContent: 'center',
              }}
            >
              <X size={16} />
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Mobile Card View */}
      {breakpoint === 'mobile' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {loading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <div key={i} style={{ ...cardStyle, padding: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{ width: 48, height: 48, borderRadius: 24, backgroundColor: colors.bgSubdued }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ height: 16, width: '60%', backgroundColor: colors.bgSubdued, borderRadius: 4, marginBottom: 8 }} />
                    <div style={{ height: 12, width: '80%', backgroundColor: colors.bgSubdued, borderRadius: 4 }} />
                  </div>
                </div>
              </div>
            ))
          ) : members.length === 0 ? (
            <div style={{ ...cardStyle, padding: 48, textAlign: 'center' }}>
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 28,
                  backgroundColor: colors.primaryLight,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 16px',
                }}
              >
                <Users size={28} color={colors.primary} />
              </div>
              <div style={{ fontSize: 16, fontWeight: 600, color: colors.text, marginBottom: 4 }}>
                {hasFilters ? 'No members match your filters' : 'No members yet'}
              </div>
              <div style={{ fontSize: 14, color: colors.textSecondary, marginBottom: 16 }}>
                {hasFilters ? 'Try adjusting your search or filters' : 'Get started by adding your first member'}
              </div>
            </div>
          ) : (
            members.map((member) => (
              <Link
                key={member.id}
                to={`/admin/members/${member.id}`}
                style={{
                  ...cardStyle,
                  padding: 16,
                  textDecoration: 'none',
                  display: 'block',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                  <div
                    style={{
                      width: 48,
                      height: 48,
                      borderRadius: 24,
                      backgroundColor: colors.primaryLight,
                      color: colors.primary,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 600,
                      fontSize: 16,
                      flexShrink: 0,
                    }}
                  >
                    {(member.name || member.email || 'M')[0].toUpperCase()}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 15, fontWeight: 600, color: colors.text, marginBottom: 2 }}>
                      {member.name || '(No name)'}
                    </div>
                    <div style={{ fontSize: 13, color: colors.textSubdued, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {member.email}
                    </div>
                  </div>
                  <ChevronRight size={20} color={colors.textSubdued} />
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                  <code style={{ fontSize: 12, backgroundColor: colors.bgSubdued, padding: '4px 8px', borderRadius: 4, color: colors.textSecondary }}>
                    {member.member_number}
                  </code>
                  <TierBadge tier={member.tier?.name || 'None'} />
                  <StatusBadge status={member.status} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12, paddingTop: 12, borderTop: `1px solid ${colors.borderSubdued}` }}>
                  <span style={{ fontSize: 12, color: colors.textSubdued }}>
                    Joined {new Date(member.membership_start_date).toLocaleDateString()}
                  </span>
                  <span style={{ fontSize: 12, color: colors.textSecondary }}>
                    {member.total_trade_ins} trade-in{member.total_trade_ins !== 1 ? 's' : ''}
                  </span>
                </div>
              </Link>
            ))
          )}

          {/* Mobile Pagination */}
          {pages > 1 && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: 16,
                marginTop: 8,
                backgroundColor: colors.bgSurface,
                borderRadius: 12,
                border: `1px solid ${colors.border}`,
                boxShadow: shadows.card,
              }}
            >
              <p style={{ fontSize: 13, color: colors.textSecondary, margin: 0 }}>
                {(page - 1) * limit + 1}-{Math.min(page * limit, total)} of {total}
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <button
                  onClick={() => handlePageChange(page - 1)}
                  disabled={page <= 1}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 36,
                    height: 36,
                    borderRadius: 8,
                    backgroundColor: colors.bgSurface,
                    border: `1px solid ${colors.border}`,
                    color: page <= 1 ? colors.textSubdued : colors.text,
                    cursor: page <= 1 ? 'not-allowed' : 'pointer',
                    opacity: page <= 1 ? 0.5 : 1,
                  }}
                >
                  <ChevronLeft size={18} />
                </button>
                <span style={{ fontSize: 13, color: colors.textSecondary, minWidth: 60, textAlign: 'center' }}>
                  {page}/{pages}
                </span>
                <button
                  onClick={() => handlePageChange(page + 1)}
                  disabled={page >= pages}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 36,
                    height: 36,
                    borderRadius: 8,
                    backgroundColor: colors.bgSurface,
                    border: `1px solid ${colors.border}`,
                    color: page >= pages ? colors.textSubdued : colors.text,
                    cursor: page >= pages ? 'not-allowed' : 'pointer',
                    opacity: page >= pages ? 0.5 : 1,
                  }}
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Desktop/Tablet Table */}
      {breakpoint !== 'mobile' && (
        <div style={{ ...cardStyle, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${colors.border}` }}>
                  {['Member', 'Member #', 'Tier', 'Status', 'Joined', 'Trade-ins', ''].map((header, i) => (
                    <th
                      key={i}
                      style={{
                        textAlign: 'left',
                        padding: '12px 16px',
                        color: colors.textSubdued,
                        fontWeight: 500,
                        fontSize: 12,
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px',
                      }}
                    >
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} style={{ borderBottom: `1px solid ${colors.borderSubdued}` }}>
                      <td style={{ padding: 16 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <div style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: colors.bgSubdued }} />
                          <div>
                            <div style={{ height: 14, width: 120, backgroundColor: colors.bgSubdued, borderRadius: 4, marginBottom: 6 }} />
                            <div style={{ height: 12, width: 160, backgroundColor: colors.bgSubdued, borderRadius: 4 }} />
                          </div>
                        </div>
                      </td>
                      <td style={{ padding: 16 }}><div style={{ height: 14, width: 60, backgroundColor: colors.bgSubdued, borderRadius: 4 }} /></td>
                      <td style={{ padding: 16 }}><div style={{ height: 24, width: 60, backgroundColor: colors.bgSubdued, borderRadius: 20 }} /></td>
                      <td style={{ padding: 16 }}><div style={{ height: 24, width: 70, backgroundColor: colors.bgSubdued, borderRadius: 6 }} /></td>
                      <td style={{ padding: 16 }}><div style={{ height: 14, width: 80, backgroundColor: colors.bgSubdued, borderRadius: 4 }} /></td>
                      <td style={{ padding: 16 }}><div style={{ height: 14, width: 30, backgroundColor: colors.bgSubdued, borderRadius: 4 }} /></td>
                      <td style={{ padding: 16 }} />
                    </tr>
                  ))
                ) : members.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ padding: 48, textAlign: 'center' }}>
                      <div
                        style={{
                          width: 56,
                          height: 56,
                          borderRadius: 28,
                          backgroundColor: colors.primaryLight,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          margin: '0 auto 16px',
                        }}
                      >
                        <Users size={28} color={colors.primary} />
                      </div>
                      <div style={{ fontSize: 16, fontWeight: 600, color: colors.text, marginBottom: 4 }}>
                        {hasFilters ? 'No members match your filters' : 'No members yet'}
                      </div>
                      <div style={{ fontSize: 14, color: colors.textSecondary, marginBottom: 16 }}>
                        {hasFilters ? 'Try adjusting your search or filters' : 'Get started by adding your first member'}
                      </div>
                      {!hasFilters && (
                        <Link
                          to="/admin/members/new"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 6,
                            padding: '10px 16px',
                            backgroundColor: colors.primary,
                            borderRadius: 8,
                            color: '#fff',
                            fontSize: 14,
                            fontWeight: 500,
                            textDecoration: 'none',
                          }}
                        >
                          <UserPlus size={16} />
                          Add Member
                        </Link>
                      )}
                    </td>
                  </tr>
                ) : (
                  members.map((member) => (
                    <tr
                      key={member.id}
                      style={{
                        borderBottom: `1px solid ${colors.borderSubdued}`,
                        transition: 'background 150ms ease',
                        cursor: 'pointer',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = colors.bgSurfaceHover;
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = 'transparent';
                      }}
                    >
                      <td style={{ padding: 16 }}>
                        <Link
                          to={`/admin/members/${member.id}`}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 12,
                            textDecoration: 'none',
                            color: 'inherit',
                          }}
                        >
                          <div
                            style={{
                              width: 40,
                              height: 40,
                              borderRadius: 20,
                              backgroundColor: colors.primaryLight,
                              color: colors.primary,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontWeight: 600,
                              fontSize: 14,
                              flexShrink: 0,
                            }}
                          >
                            {(member.name || member.email || 'M')[0].toUpperCase()}
                          </div>
                          <div style={{ minWidth: 0 }}>
                            <div
                              style={{
                                fontSize: 14,
                                fontWeight: 500,
                                color: colors.text,
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                              }}
                            >
                              {member.name || '(No name)'}
                            </div>
                            <div
                              style={{
                                fontSize: 13,
                                color: colors.textSubdued,
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                              }}
                            >
                              {member.email}
                            </div>
                          </div>
                        </Link>
                      </td>
                      <td style={{ padding: 16 }}>
                        <code
                          style={{
                            fontSize: 13,
                            backgroundColor: colors.bgSubdued,
                            padding: '4px 8px',
                            borderRadius: 4,
                            color: colors.textSecondary,
                          }}
                        >
                          {member.member_number}
                        </code>
                      </td>
                      <td style={{ padding: 16 }}>
                        <TierBadge tier={member.tier?.name || 'None'} />
                      </td>
                      <td style={{ padding: 16 }}>
                        <StatusBadge status={member.status} />
                      </td>
                      <td style={{ padding: 16, fontSize: 14, color: colors.textSecondary }}>
                        {new Date(member.membership_start_date).toLocaleDateString()}
                      </td>
                      <td style={{ padding: 16, fontSize: 14, color: colors.textSecondary }}>
                        {member.total_trade_ins}
                      </td>
                      <td style={{ padding: 16 }}>
                        <button
                          style={{
                            padding: 8,
                            borderRadius: 6,
                            background: 'transparent',
                            border: 'none',
                            color: colors.textSubdued,
                            cursor: 'pointer',
                            transition: 'all 150ms ease',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = colors.bgSubdued;
                            e.currentTarget.style.color = colors.text;
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'transparent';
                            e.currentTarget.style.color = colors.textSubdued;
                          }}
                        >
                          <MoreVertical size={18} />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {pages > 1 && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: 16,
                borderTop: `1px solid ${colors.border}`,
              }}
            >
              <p style={{ fontSize: 14, color: colors.textSecondary, margin: 0 }}>
                Showing {(page - 1) * limit + 1} to {Math.min(page * limit, total)} of {total}
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <button
                  onClick={() => handlePageChange(page - 1)}
                  disabled={page <= 1}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 36,
                    height: 36,
                    borderRadius: 8,
                    backgroundColor: colors.bgSurface,
                    border: `1px solid ${colors.border}`,
                    color: page <= 1 ? colors.textSubdued : colors.text,
                    cursor: page <= 1 ? 'not-allowed' : 'pointer',
                    opacity: page <= 1 ? 0.5 : 1,
                  }}
                >
                  <ChevronLeft size={18} />
                </button>
                <span style={{ fontSize: 14, color: colors.textSecondary, minWidth: 80, textAlign: 'center' }}>
                  Page {page} of {pages}
                </span>
                <button
                  onClick={() => handlePageChange(page + 1)}
                  disabled={page >= pages}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 36,
                    height: 36,
                    borderRadius: 8,
                    backgroundColor: colors.bgSurface,
                    border: `1px solid ${colors.border}`,
                    color: page >= pages ? colors.textSubdued : colors.text,
                    cursor: page >= pages ? 'not-allowed' : 'pointer',
                    opacity: page >= pages ? 0.5 : 1,
                  }}
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
