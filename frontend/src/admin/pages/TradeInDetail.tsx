/**
 * Trade-In Detail Page
 * Shows batch details, items, bonus preview, and complete action.
 */
import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  getTradeInBatch,
  previewBatchBonus,
  completeBatch,
  type TradeInBatch,
  type BonusPreview,
} from '../api/adminApi';

// Icons
const Icons = {
  ArrowLeft: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m12 19-7-7 7-7" />
      <path d="M19 12H5" />
    </svg>
  ),
  Check: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  ),
  Gift: () => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="8" width="18" height="4" rx="1" />
      <path d="M12 8v13" />
      <path d="M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7" />
      <path d="M7.5 8a2.5 2.5 0 0 1 0-5A4.8 8 0 0 1 12 8a4.8 8 0 0 1 4.5-5 2.5 2.5 0 0 1 0 5" />
    </svg>
  ),
  User: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
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
  Loader: () => (
    <svg className="animate-spin" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  ),
  AlertCircle: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 8v4" />
      <path d="M12 16h.01" />
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
    <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium ${colors.bg} ${colors.text}`}>
      <span
        className="w-2 h-2 rounded-full"
        style={{ background: colors.dot }}
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

// Format date
function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function TradeInDetail() {
  const { id } = useParams<{ id: string }>();
  const [batch, setBatch] = useState<TradeInBatch | null>(null);
  const [bonusPreview, setBonusPreview] = useState<BonusPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [completing, setCompleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  // Fetch batch details
  useEffect(() => {
    async function fetchData() {
      if (!id) return;

      setLoading(true);
      setError(null);

      try {
        const batchData = await getTradeInBatch(parseInt(id, 10));
        setBatch(batchData);

        // Get bonus preview if batch is not completed
        if (batchData.status !== 'completed' && batchData.status !== 'cancelled') {
          try {
            const preview = await previewBatchBonus(parseInt(id, 10));
            setBonusPreview(preview);
          } catch (e) {
            console.error('Failed to get bonus preview:', e);
          }
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load batch');
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [id]);

  // Handle complete batch
  const handleComplete = async () => {
    if (!id || !batch) return;

    setCompleting(true);
    setError(null);

    try {
      const result = await completeBatch(parseInt(id, 10));

      // Update local state
      setBatch({
        ...batch,
        status: 'completed',
        completed_at: new Date().toISOString(),
        bonus_amount: result.bonus.bonus_amount,
      });

      setShowConfirm(false);
      setBonusPreview(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to complete batch');
    } finally {
      setCompleting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Icons.Loader />
          <p className="text-white/50 mt-4">Loading trade-in...</p>
        </div>
      </div>
    );
  }

  if (error && !batch) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link
            to="/admin/tradeins"
            className="p-2 hover:bg-white/5 rounded-lg transition-colors"
          >
            <Icons.ArrowLeft />
          </Link>
          <h1 className="text-2xl font-bold text-white">Trade-In Details</h1>
        </div>

        <div className="admin-glass admin-glass-glow p-8 text-center">
          <Icons.AlertCircle />
          <p className="text-red-400 mt-4">{error}</p>
          <Link
            to="/admin/tradeins"
            className="inline-block mt-4 text-orange-400 hover:text-orange-300"
          >
            Back to Trade-Ins
          </Link>
        </div>
      </div>
    );
  }

  if (!batch) return null;

  const canComplete = batch.status === 'pending' || batch.status === 'listed';

  return (
    <div className="space-y-6 admin-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/admin/tradeins"
            className="p-2 hover:bg-white/5 rounded-lg transition-colors text-white/60 hover:text-white"
          >
            <Icons.ArrowLeft />
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-white">
                {batch.batch_reference}
              </h1>
              <StatusBadge status={batch.status} />
            </div>
            <p className="text-white/50 mt-1">
              Created {formatDate(batch.created_at)}
              {batch.created_by && ` by ${batch.created_by}`}
            </p>
          </div>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="admin-glass bg-red-500/10 border border-red-500/20 p-4 rounded-xl">
          <p className="text-red-400">{error}</p>
        </div>
      )}

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column - Batch info */}
        <div className="lg:col-span-2 space-y-6">
          {/* Member & Category */}
          <div className="admin-glass admin-glass-glow p-6">
            <div className="grid grid-cols-2 gap-6">
              {/* Member */}
              <div>
                <div className="flex items-center gap-2 text-white/50 text-sm mb-2">
                  <Icons.User />
                  Member
                </div>
                <Link
                  to={`/admin/members/${batch.member_id}`}
                  className="block group"
                >
                  <p className="text-lg font-medium text-white group-hover:text-orange-400 transition-colors">
                    {batch.member_name || batch.member_number}
                  </p>
                  <p className="text-white/50 text-sm">{batch.member_number}</p>
                  {batch.member_tier && (
                    <span className="inline-block mt-1 text-xs px-2 py-0.5 rounded bg-white/10 text-white/70">
                      {batch.member_tier} tier
                    </span>
                  )}
                </Link>
              </div>

              {/* Category */}
              <div>
                <div className="flex items-center gap-2 text-white/50 text-sm mb-2">
                  <Icons.Package />
                  Category
                </div>
                <p className="text-lg">
                  <span className="text-2xl mr-2">
                    {CATEGORY_ICONS[batch.category] || CATEGORY_ICONS.other}
                  </span>
                  <span className="text-white capitalize">{batch.category}</span>
                </p>
              </div>
            </div>

            {batch.notes && (
              <div className="mt-6 pt-6 border-t border-white/10">
                <p className="text-white/50 text-sm mb-2">Notes</p>
                <p className="text-white/80">{batch.notes}</p>
              </div>
            )}
          </div>

          {/* Items */}
          <div className="admin-glass admin-glass-glow overflow-hidden">
            <div className="p-4 border-b border-white/10">
              <h2 className="text-lg font-semibold text-white">
                Items ({batch.total_items})
              </h2>
            </div>

            {batch.items && batch.items.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>Trade Value</th>
                      <th>Market Value</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {batch.items.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <div>
                            <p className="text-white/90">
                              {item.product_title || '(Untitled)'}
                            </p>
                            {item.product_sku && (
                              <p className="text-xs text-white/40">
                                SKU: {item.product_sku}
                              </p>
                            )}
                          </div>
                        </td>
                        <td className="font-medium text-white/90">
                          {formatCurrency(item.trade_value)}
                        </td>
                        <td className="text-white/60">
                          {item.market_value
                            ? formatCurrency(item.market_value)
                            : '—'}
                        </td>
                        <td>
                          {item.sold_date ? (
                            <span className="text-green-400 text-sm">Sold</span>
                          ) : item.listed_date ? (
                            <span className="text-blue-400 text-sm">Listed</span>
                          ) : (
                            <span className="text-white/40 text-sm">Pending</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 text-center text-white/40">
                No items in this batch yet
              </div>
            )}
          </div>

          {/* Completion info (if completed) */}
          {batch.status === 'completed' && batch.completed_at && (
            <div className="admin-glass bg-green-500/5 border border-green-500/20 p-6 rounded-xl">
              <div className="flex items-start gap-4">
                <div className="p-2 rounded-lg bg-green-500/20">
                  <Icons.Check />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-green-400">
                    Batch Completed
                  </h3>
                  <p className="text-white/60 text-sm mt-1">
                    Completed {formatDate(batch.completed_at)}
                    {batch.completed_by && ` by ${batch.completed_by}`}
                  </p>
                  {batch.bonus_amount > 0 && (
                    <p className="text-green-400 font-medium mt-2">
                      {formatCurrency(batch.bonus_amount)} bonus credit issued
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right column - Summary & Actions */}
        <div className="space-y-6">
          {/* Summary card */}
          <div className="admin-glass admin-glass-glow p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Summary</h3>

            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-white/50">Total Items</span>
                <span className="text-white font-medium">{batch.total_items}</span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-white/50">Trade Value</span>
                <span className="text-white font-medium text-lg">
                  {formatCurrency(batch.total_trade_value)}
                </span>
              </div>

              {batch.status === 'completed' && batch.bonus_amount > 0 && (
                <div className="flex justify-between items-center pt-4 border-t border-white/10">
                  <span className="text-white/50">Bonus Issued</span>
                  <span className="text-green-400 font-medium text-lg">
                    +{formatCurrency(batch.bonus_amount)}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Bonus Preview Card (if not completed) */}
          {canComplete && bonusPreview && (
            <div className="admin-glass admin-glass-glow p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 rounded-lg bg-orange-500/20 text-orange-400">
                  <Icons.Gift />
                </div>
                <h3 className="text-lg font-semibold text-white">Tier Bonus</h3>
              </div>

              {bonusPreview.bonus.eligible ? (
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-white/50">Tier</span>
                    <span className="text-white font-medium">
                      {bonusPreview.bonus.tier_name}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-white/50">Bonus Rate</span>
                    <span className="text-white font-medium">
                      {bonusPreview.bonus.bonus_percent}%
                    </span>
                  </div>
                  <div className="flex justify-between items-center pt-3 border-t border-white/10">
                    <span className="text-white/50">Bonus Credit</span>
                    <span className="text-green-400 font-bold text-xl">
                      +{formatCurrency(bonusPreview.bonus.bonus_amount)}
                    </span>
                  </div>
                  <p className="text-xs text-white/40 mt-2">
                    {bonusPreview.bonus.bonus_percent}% of{' '}
                    {formatCurrency(bonusPreview.bonus.trade_value)} trade value
                  </p>
                </div>
              ) : (
                <div className="text-center py-4">
                  <p className="text-white/50">{bonusPreview.bonus.reason}</p>
                </div>
              )}
            </div>
          )}

          {/* Complete Action */}
          {canComplete && (
            <div className="admin-glass admin-glass-glow p-6">
              <h3 className="text-lg font-semibold text-white mb-4">Actions</h3>

              {!showConfirm ? (
                <button
                  onClick={() => setShowConfirm(true)}
                  className="admin-btn admin-btn-primary w-full"
                >
                  <Icons.Check />
                  Complete Trade-In
                </button>
              ) : (
                <div className="space-y-4">
                  <div className="p-4 rounded-lg bg-orange-500/10 border border-orange-500/20">
                    <p className="text-orange-400 text-sm font-medium mb-2">
                      Confirm Completion
                    </p>
                    <p className="text-white/70 text-sm">
                      This will mark the batch as completed
                      {bonusPreview?.bonus.bonus_amount
                        ? ` and issue ${formatCurrency(bonusPreview.bonus.bonus_amount)} bonus credit to the member.`
                        : '.'}
                    </p>
                  </div>

                  <div className="flex gap-3">
                    <button
                      onClick={() => setShowConfirm(false)}
                      className="admin-btn admin-btn-ghost flex-1"
                      disabled={completing}
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleComplete}
                      disabled={completing}
                      className="admin-btn admin-btn-primary flex-1"
                    >
                      {completing ? (
                        <>
                          <Icons.Loader />
                          Completing...
                        </>
                      ) : (
                        <>
                          <Icons.Check />
                          Confirm
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}

              <p className="text-xs text-white/40 mt-4">
                Once completed, the member will receive their tier bonus as store credit.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
