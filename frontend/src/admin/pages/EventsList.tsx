import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getStoreCreditEvents, type StoreCreditEvent } from '../api/adminApi';

// Icons
const Icons = {
  Search: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  ),
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
  Calendar: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect width="18" height="18" x="3" y="4" rx="2" ry="2" />
      <line x1="16" x2="16" y1="2" y2="6" />
      <line x1="8" x2="8" y1="2" y2="6" />
      <line x1="3" x2="21" y1="10" y2="10" />
    </svg>
  ),
  Users: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  DollarSign: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="12" x2="12" y1="2" y2="22" />
      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </svg>
  ),
  Check: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  ),
  Clock: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  ),
  AlertCircle: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" x2="12" y1="8" y2="12" />
      <line x1="12" x2="12.01" y1="16" y2="16" />
    </svg>
  ),
  Eye: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  ),
};

// Status badge component
function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { icon: React.FC; color: string; bg: string }> = {
    completed: { icon: Icons.Check, color: '#10b981', bg: 'rgba(16, 185, 129, 0.15)' },
    running: { icon: Icons.Clock, color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.15)' },
    failed: { icon: Icons.AlertCircle, color: '#ef4444', bg: 'rgba(239, 68, 68, 0.15)' },
    pending: { icon: Icons.Clock, color: '#6366f1', bg: 'rgba(99, 102, 241, 0.15)' },
  };

  const { icon: Icon, color, bg } = config[status] || config.pending;

  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
      style={{ color, background: bg }}
    >
      <Icon />
      {status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Unknown'}
    </span>
  );
}

// Format currency
function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

// Format date
function formatDate(date: string): string {
  return new Date(date).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

// Format date with time
function formatDateTime(date: string): string {
  return new Date(date).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

export default function EventsList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [events, setEvents] = useState<StoreCreditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);

  // Filter state
  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') || '');
  const page = parseInt(searchParams.get('page') || '1', 10);
  const limit = 15;

  // Fetch events
  useEffect(() => {
    async function fetchEvents() {
      setLoading(true);
      try {
        const result = await getStoreCreditEvents({
          page,
          limit,
          status: statusFilter || undefined,
        });
        setEvents(result.events);
        setTotal(result.total);
        setPages(result.pages);
      } catch (error) {
        console.error('Failed to fetch events:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchEvents();
  }, [page, statusFilter]);

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
    setSearchParams({});
  };

  const hasFilters = statusFilter;

  // Calculate totals
  const totalCredited = events.reduce((sum, e) => sum + (e.total_credited || 0), 0);
  const totalCustomers = events.reduce((sum, e) => sum + (e.customers_affected || 0), 0);

  return (
    <div className="space-y-6 admin-fade-in">
      {/* Header */}
      <div className="admin-header">
        <div>
          <h1 className="admin-page-title">Store Credit Events</h1>
          <p className="text-white/50 mt-1">
            {total} event{total !== 1 ? 's' : ''} total
          </p>
        </div>
        <Link to="/admin/events/new" className="admin-btn admin-btn-primary">
          <Icons.Plus />
          New Event
        </Link>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="admin-glass p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-green-500/20 to-green-600/20 flex items-center justify-center">
              <Icons.DollarSign />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{formatCurrency(totalCredited)}</p>
              <p className="text-xs text-white/40">Total Credited</p>
            </div>
          </div>
        </div>
        <div className="admin-glass p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500/20 to-blue-600/20 flex items-center justify-center">
              <Icons.Users />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{totalCustomers.toLocaleString()}</p>
              <p className="text-xs text-white/40">Customers Reached</p>
            </div>
          </div>
        </div>
        <div className="admin-glass p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500/20 to-purple-600/20 flex items-center justify-center">
              <Icons.Calendar />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{events.length}</p>
              <p className="text-xs text-white/40">Events This View</p>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="admin-glass admin-glass-glow p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          {/* Status Filter */}
          <div className="relative min-w-[180px]">
            <select
              value={statusFilter}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              className="admin-input appearance-none pr-10 cursor-pointer"
            >
              <option value="">All Statuses</option>
              <option value="completed">Completed</option>
              <option value="running">Running</option>
              <option value="pending">Pending</option>
              <option value="failed">Failed</option>
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

      {/* Events Grid */}
      <div className="grid gap-4">
        {loading ? (
          // Loading skeleton
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="admin-glass p-6">
              <div className="flex flex-col lg:flex-row lg:items-center gap-4">
                <div className="flex-1 space-y-3">
                  <div className="admin-skeleton h-6 w-48" />
                  <div className="admin-skeleton h-4 w-64" />
                </div>
                <div className="flex flex-wrap gap-6">
                  <div className="admin-skeleton h-10 w-24" />
                  <div className="admin-skeleton h-10 w-24" />
                  <div className="admin-skeleton h-10 w-24" />
                </div>
              </div>
            </div>
          ))
        ) : events.length === 0 ? (
          <div className="admin-glass p-12 text-center">
            <div className="text-white/30 mb-4">
              <Icons.Calendar />
            </div>
            <p className="text-white/50 mb-4">
              {hasFilters ? 'No events match your filters' : 'No store credit events yet'}
            </p>
            {!hasFilters && (
              <Link to="/admin/events/new" className="admin-btn admin-btn-primary inline-flex">
                <Icons.Plus />
                Create Your First Event
              </Link>
            )}
          </div>
        ) : (
          events.map((event, idx) => (
            <div
              key={event.id}
              className="admin-glass admin-glass-glow p-6 hover:bg-white/[0.08] transition-colors admin-slide-in"
              style={{ animationDelay: `${idx * 50}ms` }}
            >
              <div className="flex flex-col lg:flex-row lg:items-center gap-4">
                {/* Event Info */}
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="text-lg font-semibold text-white">{event.name}</h3>
                    <StatusBadge status={event.status} />
                  </div>
                  <p className="text-sm text-white/50 mb-2">{event.description}</p>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-white/40">
                    <span>Created {formatDateTime(event.created_at)}</span>
                    {event.executed_at && (
                      <span>Executed {formatDateTime(event.executed_at)}</span>
                    )}
                  </div>
                </div>

                {/* Event Stats */}
                <div className="flex flex-wrap gap-6 lg:gap-8">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-green-400">
                      {formatCurrency(event.credit_amount)}
                    </p>
                    <p className="text-xs text-white/40">Per Customer</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-blue-400">
                      {event.customers_affected?.toLocaleString() || '—'}
                    </p>
                    <p className="text-xs text-white/40">Customers</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-orange-400">
                      {event.total_credited ? formatCurrency(event.total_credited) : '—'}
                    </p>
                    <p className="text-xs text-white/40">Total</p>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex gap-2 lg:ml-4">
                  <Link
                    to={`/admin/events/${event.id}`}
                    className="admin-btn admin-btn-ghost admin-btn-icon"
                    title="View Details"
                  >
                    <Icons.Eye />
                  </Link>
                </div>
              </div>

              {/* Filters Applied */}
              {event.filters && Object.keys(event.filters).length > 0 && (
                <div className="mt-4 pt-4 border-t border-white/5">
                  <div className="flex flex-wrap gap-2">
                    {event.filters.date_range && (
                      <span className="px-2 py-1 rounded bg-white/5 text-xs text-white/60">
                        {formatDate(event.filters.date_range.start)} -{' '}
                        {formatDate(event.filters.date_range.end)}
                      </span>
                    )}
                    {event.filters.sources?.map((source: string) => (
                      <span
                        key={source}
                        className="px-2 py-1 rounded bg-blue-500/10 text-xs text-blue-400"
                      >
                        {source}
                      </span>
                    ))}
                    {event.filters.collections?.map((col: string) => (
                      <span
                        key={col}
                        className="px-2 py-1 rounded bg-purple-500/10 text-xs text-purple-400"
                      >
                        {col}
                      </span>
                    ))}
                    {event.filters.product_tags?.map((tag: string) => (
                      <span
                        key={tag}
                        className="px-2 py-1 rounded bg-green-500/10 text-xs text-green-400"
                      >
                        #{tag}
                      </span>
                    ))}
                    {event.filters.customer_tags?.map((tag: string) => (
                      <span
                        key={tag}
                        className="px-2 py-1 rounded bg-orange-500/10 text-xs text-orange-400"
                      >
                        @{tag}
                      </span>
                    ))}
                    {event.filters.min_spend && (
                      <span className="px-2 py-1 rounded bg-yellow-500/10 text-xs text-yellow-400">
                        Min ${event.filters.min_spend}
                      </span>
                    )}
                    {event.filters.tiers?.map((tier: string) => (
                      <span
                        key={tier}
                        className={`px-2 py-1 rounded text-xs admin-tier-badge ${tier?.toLowerCase() || ''}`}
                      >
                        {tier}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="admin-glass p-4 flex items-center justify-between">
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
  );
}
