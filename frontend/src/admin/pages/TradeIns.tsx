/**
 * TradeIns - Premium Light Mode
 * World-class Shopify App Store design
 */
import { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import {
  Plus,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  X,
  ArrowRightLeft,
  Eye,
} from 'lucide-react';
import {
  getTradeInBatches,
  getTradeInCategories,
  type TradeInBatch,
  type TradeInCategory,
} from '../api/adminApi';

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
  interactiveLight: '#e8f4fd',
};

const shadows = {
  card: '0 1px 2px rgba(0, 0, 0, 0.05), 0 1px 3px rgba(0, 0, 0, 0.1)',
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

// Category icons map
const CATEGORY_ICONS: Record<string, string> = {
  sports: '🏈',
  pokemon: '⚡',
  magic: '🔮',
  riftbound: '🌀',
  tcg_other: '🎴',
  other: '📦',
};

// Status badge component
function StatusBadge({ status }: { status: string }) {
  const statusStyles: Record<string, { bg: string; color: string; dot: string }> = {
    pending: { bg: colors.warningLight, color: colors.warning, dot: colors.warning },
    listed: { bg: colors.interactiveLight, color: colors.interactive, dot: colors.interactive },
    completed: { bg: colors.successLight, color: colors.success, dot: colors.success },
    cancelled: { bg: colors.criticalLight, color: colors.critical, dot: colors.critical },
  };
  const style = statusStyles[status] || statusStyles.pending;

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

// Format currency
function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
}

export default function TradeIns() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [batches, setBatches] = useState<TradeInBatch[]>([]);
  const [categories, setCategories] = useState<TradeInCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const breakpoint = useResponsive();

  // Filter state
  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') || '');
  const [categoryFilter, setCategoryFilter] = useState(searchParams.get('category') || '');
  const page = parseInt(searchParams.get('page') || '1', 10);
  const limit = 20;

  // Fetch batches
  const fetchBatches = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getTradeInBatches({
        page,
        per_page: limit,
        status: statusFilter || undefined,
      });
      setBatches(result.batches);
      setTotal(result.total);
      setPages(Math.ceil(result.total / limit));
    } catch (error) {
      console.error('Failed to fetch trade-in batches:', error);
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter]);

  // Fetch categories once
  useEffect(() => {
    getTradeInCategories()
      .then((res) => setCategories(res.categories))
      .catch(console.error);
  }, []);

  // Handle filter changes
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
    if (key === 'category') setCategoryFilter(value);
  };

  // Handle pagination
  const handlePageChange = (newPage: number) => {
    const params = new URLSearchParams(searchParams);
    params.set('page', String(newPage));
    setSearchParams(params);
  };

  // Clear all filters
  const clearFilters = () => {
    setStatusFilter('');
    setCategoryFilter('');
    setSearchParams({});
  };

  // Fetch on param changes
  useEffect(() => {
    fetchBatches();
  }, [fetchBatches]);

  const hasFilters = statusFilter || categoryFilter;

  // Card style
  const cardStyle: React.CSSProperties = {
    backgroundColor: colors.bgSurface,
    borderRadius: 12,
    border: `1px solid ${colors.border}`,
    boxShadow: shadows.card,
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
            Trade-Ins
          </h1>
          <p style={{ fontSize: 14, color: colors.textSecondary, margin: '4px 0 0 0' }}>
            {total} total batch{total !== 1 ? 'es' : ''}
          </p>
        </div>
        <Link
          to="/admin/tradeins/new"
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
          <Plus size={18} />
          New Trade-In
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
          {/* Status Filter */}
          <div style={{ position: 'relative', minWidth: breakpoint === 'mobile' ? '100%' : 150 }}>
            <select
              value={statusFilter}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              style={selectStyle}
            >
              <option value="">All Status</option>
              <option value="pending">Pending</option>
              <option value="listed">Listed</option>
              <option value="completed">Completed</option>
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

          {/* Category Filter */}
          <div style={{ position: 'relative', minWidth: breakpoint === 'mobile' ? '100%' : 170 }}>
            <select
              value={categoryFilter}
              onChange={(e) => handleFilterChange('category', e.target.value)}
              style={selectStyle}
            >
              <option value="">All Categories</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.icon} {cat.name}
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
                  <div style={{ width: 40, height: 40, borderRadius: 8, backgroundColor: colors.bgSubdued }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ height: 16, width: '60%', backgroundColor: colors.bgSubdued, borderRadius: 4, marginBottom: 8 }} />
                    <div style={{ height: 12, width: '40%', backgroundColor: colors.bgSubdued, borderRadius: 4 }} />
                  </div>
                </div>
              </div>
            ))
          ) : batches.length === 0 ? (
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
                <ArrowRightLeft size={28} color={colors.primary} />
              </div>
              <div style={{ fontSize: 16, fontWeight: 600, color: colors.text, marginBottom: 4 }}>
                {hasFilters ? 'No batches match your filters' : 'No trade-ins yet'}
              </div>
              <div style={{ fontSize: 14, color: colors.textSecondary, marginBottom: 16 }}>
                {hasFilters ? 'Try adjusting your filters' : 'Get started by creating your first trade-in'}
              </div>
            </div>
          ) : (
            batches.map((batch) => (
              <Link
                key={batch.id}
                to={`/admin/tradeins/${batch.id}`}
                style={{
                  ...cardStyle,
                  padding: 16,
                  textDecoration: 'none',
                  display: 'block',
                }}
              >
                {/* Header row */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div
                      style={{
                        width: 40,
                        height: 40,
                        borderRadius: 8,
                        backgroundColor: colors.primaryLight,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: 20,
                      }}
                    >
                      {CATEGORY_ICONS[batch.category] || CATEGORY_ICONS.other}
                    </div>
                    <div>
                      <code
                        style={{
                          fontSize: 13,
                          backgroundColor: colors.primaryLight,
                          padding: '3px 6px',
                          borderRadius: 4,
                          color: colors.primary,
                          fontWeight: 500,
                        }}
                      >
                        {batch.batch_reference}
                      </code>
                    </div>
                  </div>
                  <StatusBadge status={batch.status} />
                </div>

                {/* Member info */}
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 15, fontWeight: 600, color: colors.text, marginBottom: 2 }}>
                    {batch.member_name || batch.member_number}
                  </div>
                  {batch.member_tier && (
                    <div style={{ fontSize: 12, color: colors.textSubdued }}>
                      {batch.member_tier} tier
                    </div>
                  )}
                </div>

                {/* Stats row */}
                <div style={{ display: 'flex', gap: 16, marginBottom: 12 }}>
                  <div>
                    <div style={{ fontSize: 11, color: colors.textSubdued, textTransform: 'uppercase', marginBottom: 2 }}>Items</div>
                    <div style={{ fontSize: 14, fontWeight: 500, color: colors.text }}>{batch.total_items}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: colors.textSubdued, textTransform: 'uppercase', marginBottom: 2 }}>Value</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: colors.text }}>{formatCurrency(batch.total_trade_value)}</div>
                  </div>
                  {batch.bonus_amount > 0 && (
                    <div>
                      <div style={{ fontSize: 11, color: colors.textSubdued, textTransform: 'uppercase', marginBottom: 2 }}>Bonus</div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: colors.success }}>+{formatCurrency(batch.bonus_amount)}</div>
                    </div>
                  )}
                </div>

                {/* Footer */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 12, borderTop: `1px solid ${colors.borderSubdued}` }}>
                  <span style={{ fontSize: 12, color: colors.textSubdued }}>
                    {new Date(batch.trade_in_date).toLocaleDateString()}
                  </span>
                  <ChevronRight size={18} color={colors.textSubdued} />
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
                  {['Batch', 'Member', 'Category', 'Items', 'Trade Value', 'Bonus', 'Status', 'Date', ''].map((header, i) => (
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
                      <td style={{ padding: 16 }}><div style={{ height: 14, width: 100, backgroundColor: colors.bgSubdued, borderRadius: 4 }} /></td>
                      <td style={{ padding: 16 }}><div style={{ height: 14, width: 90, backgroundColor: colors.bgSubdued, borderRadius: 4 }} /></td>
                      <td style={{ padding: 16 }}><div style={{ height: 24, width: 30, backgroundColor: colors.bgSubdued, borderRadius: 4 }} /></td>
                      <td style={{ padding: 16 }}><div style={{ height: 14, width: 30, backgroundColor: colors.bgSubdued, borderRadius: 4 }} /></td>
                      <td style={{ padding: 16 }}><div style={{ height: 14, width: 70, backgroundColor: colors.bgSubdued, borderRadius: 4 }} /></td>
                      <td style={{ padding: 16 }}><div style={{ height: 14, width: 50, backgroundColor: colors.bgSubdued, borderRadius: 4 }} /></td>
                      <td style={{ padding: 16 }}><div style={{ height: 24, width: 80, backgroundColor: colors.bgSubdued, borderRadius: 6 }} /></td>
                      <td style={{ padding: 16 }}><div style={{ height: 14, width: 80, backgroundColor: colors.bgSubdued, borderRadius: 4 }} /></td>
                      <td style={{ padding: 16 }} />
                    </tr>
                  ))
                ) : batches.length === 0 ? (
                  <tr>
                    <td colSpan={9} style={{ padding: 48, textAlign: 'center' }}>
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
                        <ArrowRightLeft size={28} color={colors.primary} />
                      </div>
                      <div style={{ fontSize: 16, fontWeight: 600, color: colors.text, marginBottom: 4 }}>
                        {hasFilters ? 'No batches match your filters' : 'No trade-ins yet'}
                      </div>
                      <div style={{ fontSize: 14, color: colors.textSecondary, marginBottom: 16 }}>
                        {hasFilters ? 'Try adjusting your filters' : 'Get started by creating your first trade-in'}
                      </div>
                      {!hasFilters && (
                        <Link
                          to="/admin/tradeins/new"
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
                          <Plus size={16} />
                          New Trade-In
                        </Link>
                      )}
                    </td>
                  </tr>
                ) : (
                  batches.map((batch) => (
                    <tr
                      key={batch.id}
                      style={{
                        borderBottom: `1px solid ${colors.borderSubdued}`,
                        transition: 'background 150ms ease',
                        cursor: 'pointer',
                      }}
                      onClick={() => navigate(`/admin/tradeins/${batch.id}`)}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = colors.bgSurfaceHover;
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = 'transparent';
                      }}
                    >
                      <td style={{ padding: 16 }}>
                        <code
                          style={{
                            fontSize: 13,
                            backgroundColor: colors.primaryLight,
                            padding: '4px 8px',
                            borderRadius: 4,
                            color: colors.primary,
                            fontWeight: 500,
                          }}
                        >
                          {batch.batch_reference}
                        </code>
                      </td>
                      <td style={{ padding: 16 }}>
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 500, color: colors.text }}>
                            {batch.member_name || batch.member_number}
                          </div>
                          {batch.member_tier && (
                            <div style={{ fontSize: 12, color: colors.textSubdued }}>
                              {batch.member_tier} tier
                            </div>
                          )}
                        </div>
                      </td>
                      <td style={{ padding: 16 }}>
                        <span style={{ fontSize: 18 }} title={batch.category}>
                          {CATEGORY_ICONS[batch.category] || CATEGORY_ICONS.other}
                        </span>
                      </td>
                      <td style={{ padding: 16, fontSize: 14, color: colors.textSecondary }}>
                        {batch.total_items}
                      </td>
                      <td style={{ padding: 16, fontSize: 14, fontWeight: 600, color: colors.text }}>
                        {formatCurrency(batch.total_trade_value)}
                      </td>
                      <td style={{ padding: 16 }}>
                        {batch.bonus_amount > 0 ? (
                          <span style={{ color: colors.success, fontWeight: 600, fontSize: 14 }}>
                            +{formatCurrency(batch.bonus_amount)}
                          </span>
                        ) : (
                          <span style={{ color: colors.textSubdued, fontSize: 14 }}>—</span>
                        )}
                      </td>
                      <td style={{ padding: 16 }}>
                        <StatusBadge status={batch.status} />
                      </td>
                      <td style={{ padding: 16, fontSize: 14, color: colors.textSecondary }}>
                        {new Date(batch.trade_in_date).toLocaleDateString()}
                      </td>
                      <td style={{ padding: 16 }}>
                        <Link
                          to={`/admin/tradeins/${batch.id}`}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: 32,
                            height: 32,
                            borderRadius: 6,
                            color: colors.textSubdued,
                            transition: 'all 150ms ease',
                          }}
                          onClick={(e) => e.stopPropagation()}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = colors.bgSubdued;
                            e.currentTarget.style.color = colors.text;
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'transparent';
                            e.currentTarget.style.color = colors.textSubdued;
                          }}
                        >
                          <Eye size={18} />
                        </Link>
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
