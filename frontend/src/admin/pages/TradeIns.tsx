/**
 * Trade-Ins List Page
 * Shows all trade-in batches with filtering, status badges, and quick actions.
 */
import { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  getTradeInBatches,
  getTradeInCategories,
  type TradeInBatch,
  type TradeInCategory,
} from '../api/adminApi';

// Icons
const Icons = {
  Plus: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M5 12h14" />
      <path d="M12 5v14" />
    </svg>
  ),
  ChevronDown: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m6 9 6 6 6-6" />
    </svg>
  ),
  ChevronLeft: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m15 18-6-6 6-6" />
    </svg>
  ),
  ChevronRight: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m9 18 6-6-6-6" />
    </svg>
  ),
  X: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  ),
  ArrowRightLeft: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m16 3 4 4-4 4" />
      <path d="M20 7H4" />
      <path d="m8 21-4-4 4-4" />
      <path d="M4 17h16" />
    </svg>
  ),
  Package: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m7.5 4.27 9 5.15" />
      <path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" />
      <path d="m3.3 7 8.7 5 8.7-5" />
      <path d="M12 22V12" />
    </svg>
  ),
  Eye: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  ),
};

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
  const statusColors: Record<string, { bg: string; dot: string; text: string }> = {
    pending: { bg: 'bg-amber-500/10', dot: '#f59e0b', text: 'text-amber-400' },
    listed: { bg: 'bg-blue-500/10', dot: '#3b82f6', text: 'text-blue-400' },
    completed: { bg: 'bg-green-500/10', dot: '#10b981', text: 'text-green-400' },
    cancelled: { bg: 'bg-red-500/10', dot: '#ef4444', text: 'text-red-400' },
  };

  const colors = statusColors[status] || statusColors.pending;

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium ${colors.bg} ${colors.text}`}>
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{ background: colors.dot }}
      />
      {status.charAt(0).toUpperCase() + status.slice(1)}
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
  const [batches, setBatches] = useState<TradeInBatch[]>([]);
  const [categories, setCategories] = useState<TradeInCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);

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

  return (
    <div className="space-y-6 admin-fade-in">
      {/* Header */}
      <div className="admin-header">
        <div>
          <h1 className="admin-page-title">Trade-Ins</h1>
          <p className="text-white/50 mt-1">
            {total} total batch{total !== 1 ? 'es' : ''}
          </p>
        </div>
        <Link to="/admin/tradeins/new" className="admin-btn admin-btn-primary">
          <Icons.Plus />
          New Trade-In
        </Link>
      </div>

      {/* Filters */}
      <div className="admin-glass admin-glass-glow p-4">
        <div className="flex flex-col lg:flex-row gap-4">
          {/* Status Filter */}
          <div className="relative min-w-[160px]">
            <select
              value={statusFilter}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              className="admin-input appearance-none pr-10 cursor-pointer"
            >
              <option value="">All Status</option>
              <option value="pending">Pending</option>
              <option value="listed">Listed</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <span className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-white/40">
              <Icons.ChevronDown />
            </span>
          </div>

          {/* Category Filter */}
          <div className="relative min-w-[160px]">
            <select
              value={categoryFilter}
              onChange={(e) => handleFilterChange('category', e.target.value)}
              className="admin-input appearance-none pr-10 cursor-pointer"
            >
              <option value="">All Categories</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.icon} {cat.name}
                </option>
              ))}
            </select>
            <span className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-white/40">
              <Icons.ChevronDown />
            </span>
          </div>

          {/* Clear Filters */}
          {hasFilters && (
            <button onClick={clearFilters} className="admin-btn admin-btn-ghost">
              <Icons.X />
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="admin-glass admin-glass-glow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Batch</th>
                <th>Member</th>
                <th>Category</th>
                <th>Items</th>
                <th>Trade Value</th>
                <th>Bonus</th>
                <th>Status</th>
                <th>Date</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                // Loading skeleton
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    <td><div className="admin-skeleton h-4 w-28" /></td>
                    <td><div className="admin-skeleton h-4 w-24" /></td>
                    <td><div className="admin-skeleton h-4 w-16" /></td>
                    <td><div className="admin-skeleton h-4 w-8" /></td>
                    <td><div className="admin-skeleton h-4 w-20" /></td>
                    <td><div className="admin-skeleton h-4 w-16" /></td>
                    <td><div className="admin-skeleton h-6 w-20 rounded" /></td>
                    <td><div className="admin-skeleton h-4 w-24" /></td>
                    <td></td>
                  </tr>
                ))
              ) : batches.length === 0 ? (
                <tr>
                  <td colSpan={9} className="text-center py-12">
                    <Icons.ArrowRightLeft />
                    <div className="text-white/30 mt-4">
                      {hasFilters ? 'No batches match your filters' : 'No trade-ins yet'}
                    </div>
                    {!hasFilters && (
                      <Link
                        to="/admin/tradeins/new"
                        className="inline-flex items-center gap-2 text-orange-400 hover:text-orange-300 mt-2"
                      >
                        <Icons.Plus />
                        Create your first trade-in
                      </Link>
                    )}
                  </td>
                </tr>
              ) : (
                batches.map((batch, idx) => (
                  <tr
                    key={batch.id}
                    className="admin-slide-in cursor-pointer hover:bg-white/5"
                    style={{ animationDelay: `${idx * 30}ms` }}
                    onClick={() => window.location.href = `/admin/tradeins/${batch.id}`}
                  >
                    <td>
                      <code className="text-sm bg-white/5 px-2 py-1 rounded text-orange-400">
                        {batch.batch_reference}
                      </code>
                    </td>
                    <td>
                      <div>
                        <p className="font-medium text-white/90">
                          {batch.member_name || batch.member_number}
                        </p>
                        {batch.member_tier && (
                          <p className="text-xs text-white/40">{batch.member_tier} tier</p>
                        )}
                      </div>
                    </td>
                    <td>
                      <span className="text-lg" title={batch.category}>
                        {CATEGORY_ICONS[batch.category] || CATEGORY_ICONS.other}
                      </span>
                    </td>
                    <td className="text-white/60">
                      {batch.total_items}
                    </td>
                    <td className="font-medium text-white/90">
                      {formatCurrency(batch.total_trade_value)}
                    </td>
                    <td>
                      {batch.bonus_amount > 0 ? (
                        <span className="text-green-400 font-medium">
                          +{formatCurrency(batch.bonus_amount)}
                        </span>
                      ) : (
                        <span className="text-white/30">—</span>
                      )}
                    </td>
                    <td>
                      <StatusBadge status={batch.status} />
                    </td>
                    <td className="text-white/60 text-sm">
                      {new Date(batch.trade_in_date).toLocaleDateString()}
                    </td>
                    <td>
                      <Link
                        to={`/admin/tradeins/${batch.id}`}
                        className="p-2 rounded-lg hover:bg-white/10 text-white/40 hover:text-white transition-colors inline-flex"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Icons.Eye />
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
          <div className="flex items-center justify-between p-4 border-t border-white/5">
            <p className="text-sm text-white/40">
              Showing {(page - 1) * limit + 1} to {Math.min(page * limit, total)} of {total}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handlePageChange(page - 1)}
                disabled={page <= 1}
                className="admin-btn admin-btn-ghost admin-btn-icon disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <Icons.ChevronLeft />
              </button>
              <span className="text-sm text-white/60 min-w-[80px] text-center">
                Page {page} of {pages}
              </span>
              <button
                onClick={() => handlePageChange(page + 1)}
                disabled={page >= pages}
                className="admin-btn admin-btn-ghost admin-btn-icon disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <Icons.ChevronRight />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
