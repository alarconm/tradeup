import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  previewEvent,
  runEvent,
  getCollections,
  getProductTags,
  getCustomerTags,
  getTiers,
  type EventPreview,
  type Tier,
} from '../api/adminApi';
import { debounce } from '../utils/debounce';

// Icons
const Icons = {
  ArrowLeft: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m12 19-7-7 7-7" />
      <path d="M19 12H5" />
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
  DollarSign: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="12" x2="12" y1="2" y2="22" />
      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
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
  Filter: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
    </svg>
  ),
  Tag: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z" />
      <circle cx="7.5" cy="7.5" r=".5" fill="currentColor" />
    </svg>
  ),
  Store: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 9h18v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9Z" />
      <path d="m3 9 2.45-4.9A2 2 0 0 1 7.24 3h9.52a2 2 0 0 1 1.8 1.1L21 9" />
      <path d="M12 3v6" />
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
  Sparkles: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
      <path d="M5 3v4" />
      <path d="M19 17v4" />
      <path d="M3 5h4" />
      <path d="M17 19h4" />
    </svg>
  ),
  Play: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="6 3 20 12 6 21 6 3" />
    </svg>
  ),
  Eye: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  ),
  Loader: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="animate-spin">
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  ),
  Check: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  ),
  X: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  ),
  AlertTriangle: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
      <line x1="12" x2="12" y1="9" y2="13" />
      <line x1="12" x2="12.01" y1="17" y2="17" />
    </svg>
  ),
  ChevronDown: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m6 9 6 6 6-6" />
    </svg>
  ),
};

// Multi-select dropdown component
function MultiSelect({
  label,
  options,
  selected,
  onChange,
  placeholder,
  loading,
  icon: Icon,
}: {
  label: string;
  options: { value: string; label: string }[];
  selected: string[];
  onChange: (values: string[]) => void;
  placeholder: string;
  loading?: boolean;
  icon?: React.FC;
}) {
  const [open, setOpen] = useState(false);

  const toggle = (value: string) => {
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value));
    } else {
      onChange([...selected, value]);
    }
  };

  return (
    <div className="relative">
      <label className="block text-sm font-medium text-white/60 mb-2">{label}</label>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="admin-input w-full text-left flex items-center justify-between"
      >
        <div className="flex items-center gap-2 flex-1 min-w-0">
          {Icon && (
            <span className="text-white/40">
              <Icon />
            </span>
          )}
          {selected.length === 0 ? (
            <span className="text-white/40">{placeholder}</span>
          ) : (
            <span className="truncate">
              {selected.length} selected
            </span>
          )}
        </div>
        <Icons.ChevronDown />
      </button>

      {/* Selected Tags */}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {selected.map((value) => {
            const option = options.find((o) => o.value === value);
            return (
              <span
                key={value}
                className="inline-flex items-center gap-1 px-2 py-1 rounded bg-orange-500/20 text-orange-400 text-xs"
              >
                {option?.label || value}
                <button
                  type="button"
                  onClick={() => toggle(value)}
                  className="hover:text-orange-300"
                >
                  <Icons.X />
                </button>
              </span>
            );
          })}
        </div>
      )}

      {/* Dropdown */}
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute top-full left-0 right-0 mt-1 z-50 admin-glass border border-white/10 rounded-xl max-h-60 overflow-y-auto">
            {loading ? (
              <div className="p-4 text-center text-white/40">
                <Icons.Loader />
              </div>
            ) : options.length === 0 ? (
              <div className="p-4 text-center text-white/40 text-sm">No options available</div>
            ) : (
              options.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => toggle(option.value)}
                  className="w-full px-4 py-3 text-left hover:bg-white/5 flex items-center justify-between transition-colors"
                >
                  <span className={selected.includes(option.value) ? 'text-orange-400' : 'text-white/80'}>
                    {option.label}
                  </span>
                  {selected.includes(option.value) && (
                    <span className="text-orange-400">
                      <Icons.Check />
                    </span>
                  )}
                </button>
              ))
            )}
          </div>
        </>
      )}
    </div>
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

export default function EventBuilder() {
  const navigate = useNavigate();

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [creditAmount, setCreditAmount] = useState<number>(5);
  const [dateStart, setDateStart] = useState('');
  const [dateEnd, setDateEnd] = useState('');
  const [sources, setSources] = useState<string[]>([]);
  const [collections, setCollections] = useState<string[]>([]);
  const [productTags, setProductTags] = useState<string[]>([]);
  const [customerTags, setCustomerTags] = useState<string[]>([]);
  const [tiers, setTiers] = useState<string[]>([]);
  const [minSpend, setMinSpend] = useState<number | ''>('');

  // Options from API
  const [collectionOptions, setCollectionOptions] = useState<{ value: string; label: string }[]>([]);
  const [productTagOptions, setProductTagOptions] = useState<{ value: string; label: string }[]>([]);
  const [customerTagOptions, setCustomerTagOptions] = useState<{ value: string; label: string }[]>([]);
  const [tierOptions, setTierOptions] = useState<{ value: string; label: string }[]>([]);
  const [loadingOptions, setLoadingOptions] = useState(true);

  // Preview state
  const [preview, setPreview] = useState<EventPreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Run state
  const [running, setRunning] = useState(false);
  const [runSuccess, setRunSuccess] = useState(false);

  // Source options
  const sourceOptions = [
    { value: 'pos', label: 'POS (In-Store)' },
    { value: 'web', label: 'Web (Online)' },
  ];

  // Fetch options on mount
  useEffect(() => {
    async function fetchOptions() {
      setLoadingOptions(true);
      try {
        const [collectionsRes, productTagsRes, customerTagsRes, tiersRes] = await Promise.all([
          getCollections(),
          getProductTags(),
          getCustomerTags(),
          getTiers(),
        ]);

        setCollectionOptions(
          collectionsRes.collections.map((c: { id: string; title: string }) => ({
            value: c.id,
            label: c.title,
          }))
        );
        setProductTagOptions(
          productTagsRes.tags.map((t: string) => ({ value: t, label: t }))
        );
        setCustomerTagOptions(
          customerTagsRes.tags.map((t: string) => ({ value: t, label: t }))
        );
        setTierOptions(
          tiersRes.tiers.map((t: Tier) => ({ value: t.name, label: t.name }))
        );
      } catch (error) {
        console.error('Failed to fetch options:', error);
      } finally {
        setLoadingOptions(false);
      }
    }
    fetchOptions();
  }, []);

  // Debounced preview
  const fetchPreview = useCallback(
    debounce(async (params: Parameters<typeof previewEvent>[0]) => {
      if (!params.credit_amount || params.credit_amount <= 0) {
        setPreview(null);
        return;
      }
      setLoadingPreview(true);
      setPreviewError(null);
      try {
        const result = await previewEvent(params);
        setPreview(result);
      } catch (error) {
        console.error('Preview error:', error);
        setPreviewError('Failed to generate preview');
        setPreview(null);
      } finally {
        setLoadingPreview(false);
      }
    }, 500),
    []
  );

  // Update preview when filters change
  useEffect(() => {
    fetchPreview({
      credit_amount: creditAmount,
      filters: {
        date_range:
          dateStart && dateEnd ? { start: dateStart, end: dateEnd } : undefined,
        sources: sources.length > 0 ? sources : undefined,
        collections: collections.length > 0 ? collections : undefined,
        product_tags: productTags.length > 0 ? productTags : undefined,
        customer_tags: customerTags.length > 0 ? customerTags : undefined,
        tiers: tiers.length > 0 ? tiers : undefined,
        min_spend: minSpend ? Number(minSpend) : undefined,
      },
    });
  }, [creditAmount, dateStart, dateEnd, sources, collections, productTags, customerTags, tiers, minSpend, fetchPreview]);

  // Run event
  const handleRun = async () => {
    if (!name.trim()) {
      alert('Please enter an event name');
      return;
    }
    if (!creditAmount || creditAmount <= 0) {
      alert('Please enter a valid credit amount');
      return;
    }
    if (!preview || preview.customer_count === 0) {
      alert('No customers match your filters');
      return;
    }

    setRunning(true);
    try {
      await runEvent({
        name: name.trim(),
        description: description.trim(),
        credit_amount: creditAmount,
        filters: {
          date_range:
            dateStart && dateEnd ? { start: dateStart, end: dateEnd } : undefined,
          sources: sources.length > 0 ? sources : undefined,
          collections: collections.length > 0 ? collections : undefined,
          product_tags: productTags.length > 0 ? productTags : undefined,
          customer_tags: customerTags.length > 0 ? customerTags : undefined,
          tiers: tiers.length > 0 ? tiers : undefined,
          min_spend: minSpend ? Number(minSpend) : undefined,
        },
      });
      setRunSuccess(true);
      setTimeout(() => {
        navigate('/admin/events');
      }, 2000);
    } catch (error) {
      console.error('Run error:', error);
      alert('Failed to run event. Please try again.');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6 admin-fade-in">
      {/* Header */}
      <div className="admin-header">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/admin/events')}
            className="admin-btn admin-btn-ghost admin-btn-icon"
          >
            <Icons.ArrowLeft />
          </button>
          <div>
            <h1 className="admin-page-title">Create Store Credit Event</h1>
            <p className="text-white/50 mt-1">
              Issue bonus store credit to customers based on purchase history
            </p>
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Left Column - Filters */}
        <div className="lg:col-span-2 space-y-6">
          {/* Event Details */}
          <div className="admin-glass admin-glass-glow p-6">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Icons.Sparkles />
              Event Details
            </h2>
            <div className="grid md:grid-cols-2 gap-4">
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-white/60 mb-2">
                  Event Name *
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Holiday Bonus 2026"
                  className="admin-input w-full"
                />
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-white/60 mb-2">
                  Description
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Optional description for internal reference..."
                  rows={2}
                  className="admin-input w-full resize-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-white/60 mb-2">
                  Credit Amount *
                </label>
                <div className="relative">
                  <span className="absolute left-4 top-1/2 -translate-y-1/2 text-white/40">
                    <Icons.DollarSign />
                  </span>
                  <input
                    type="number"
                    value={creditAmount}
                    onChange={(e) => setCreditAmount(Number(e.target.value))}
                    min={1}
                    step={1}
                    className="admin-input w-full pl-12"
                    placeholder="5"
                  />
                </div>
                <p className="text-xs text-white/40 mt-1">Per qualifying customer</p>
              </div>
            </div>
          </div>

          {/* Date Range Filter */}
          <div className="admin-glass admin-glass-glow p-6">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Icons.Calendar />
              Purchase Date Range
            </h2>
            <p className="text-sm text-white/40 mb-4">
              Filter customers who made purchases within this date range
            </p>
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-white/60 mb-2">
                  Start Date
                </label>
                <input
                  type="date"
                  value={dateStart}
                  onChange={(e) => setDateStart(e.target.value)}
                  className="admin-input w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-white/60 mb-2">
                  End Date
                </label>
                <input
                  type="date"
                  value={dateEnd}
                  onChange={(e) => setDateEnd(e.target.value)}
                  className="admin-input w-full"
                />
              </div>
            </div>
          </div>

          {/* Product Filters */}
          <div className="admin-glass admin-glass-glow p-6">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Icons.Package />
              Product Filters
            </h2>
            <p className="text-sm text-white/40 mb-4">
              Target customers who purchased from specific collections or product categories
            </p>
            <div className="grid md:grid-cols-2 gap-4">
              <MultiSelect
                label="Collections"
                options={collectionOptions}
                selected={collections}
                onChange={setCollections}
                placeholder="All collections"
                loading={loadingOptions}
                icon={Icons.Package}
              />
              <MultiSelect
                label="Product Tags"
                options={productTagOptions}
                selected={productTags}
                onChange={setProductTags}
                placeholder="Any product tag"
                loading={loadingOptions}
                icon={Icons.Tag}
              />
            </div>
          </div>

          {/* Customer Filters */}
          <div className="admin-glass admin-glass-glow p-6">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Icons.Users />
              Customer Filters
            </h2>
            <p className="text-sm text-white/40 mb-4">
              Target specific customer segments
            </p>
            <div className="grid md:grid-cols-2 gap-4">
              <MultiSelect
                label="Order Source"
                options={sourceOptions}
                selected={sources}
                onChange={setSources}
                placeholder="All sources"
                icon={Icons.Store}
              />
              <MultiSelect
                label="Member Tiers"
                options={tierOptions}
                selected={tiers}
                onChange={setTiers}
                placeholder="All tiers"
                loading={loadingOptions}
                icon={Icons.Sparkles}
              />
              <MultiSelect
                label="Customer Tags"
                options={customerTagOptions}
                selected={customerTags}
                onChange={setCustomerTags}
                placeholder="Any customer tag"
                loading={loadingOptions}
                icon={Icons.Tag}
              />
              <div>
                <label className="block text-sm font-medium text-white/60 mb-2">
                  Minimum Spend
                </label>
                <div className="relative">
                  <span className="absolute left-4 top-1/2 -translate-y-1/2 text-white/40">
                    <Icons.DollarSign />
                  </span>
                  <input
                    type="number"
                    value={minSpend}
                    onChange={(e) => setMinSpend(e.target.value ? Number(e.target.value) : '')}
                    min={0}
                    step={10}
                    className="admin-input w-full pl-12"
                    placeholder="No minimum"
                  />
                </div>
                <p className="text-xs text-white/40 mt-1">Total spent in date range</p>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column - Preview */}
        <div className="space-y-6">
          {/* Preview Card */}
          <div className="admin-glass admin-glass-glow p-6 sticky top-6">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Icons.Eye />
              Event Preview
            </h2>

            {loadingPreview ? (
              <div className="text-center py-8">
                <div className="inline-flex items-center gap-2 text-white/40">
                  <Icons.Loader />
                  Calculating...
                </div>
              </div>
            ) : previewError ? (
              <div className="text-center py-8 text-red-400">
                <Icons.AlertTriangle />
                <p className="mt-2 text-sm">{previewError}</p>
              </div>
            ) : preview ? (
              <div className="space-y-6">
                {/* Stats */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="admin-glass p-4 text-center">
                    <p className="text-3xl font-bold text-blue-400">
                      {preview.customer_count.toLocaleString()}
                    </p>
                    <p className="text-xs text-white/40 mt-1">Customers</p>
                  </div>
                  <div className="admin-glass p-4 text-center">
                    <p className="text-3xl font-bold text-green-400">
                      {formatCurrency(preview.total_credit)}
                    </p>
                    <p className="text-xs text-white/40 mt-1">Total Credit</p>
                  </div>
                </div>

                {/* Breakdown by Tier */}
                {preview.breakdown_by_tier && Object.keys(preview.breakdown_by_tier).length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-white/60 mb-2">By Tier</h3>
                    <div className="space-y-2">
                      {Object.entries(preview.breakdown_by_tier).map(([tier, count]) => (
                        <div key={tier} className="flex items-center justify-between">
                          <span className={`admin-tier-badge ${tier?.toLowerCase() || ''}`}>{tier}</span>
                          <span className="text-white/60">{(count as number).toLocaleString()}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Sample Customers */}
                {preview.sample_customers && preview.sample_customers.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-white/60 mb-2">Sample Customers</h3>
                    <div className="space-y-2">
                      {preview.sample_customers.slice(0, 5).map((customer, i) => (
                        <div
                          key={i}
                          className="flex items-center gap-2 text-sm text-white/60 truncate"
                        >
                          <div className="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center text-xs">
                            {(customer.name?.[0] || customer.email?.[0] || 'C').toUpperCase()}
                          </div>
                          <span className="truncate">{customer.name || customer.email}</span>
                        </div>
                      ))}
                      {preview.customer_count > 5 && (
                        <p className="text-xs text-white/40">
                          + {(preview.customer_count - 5).toLocaleString()} more
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {/* Warning if high amount */}
                {preview.total_credit > 1000 && (
                  <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
                    <div className="flex items-start gap-2 text-yellow-400">
                      <Icons.AlertTriangle />
                      <div>
                        <p className="text-sm font-medium">High Value Event</p>
                        <p className="text-xs text-yellow-400/70 mt-1">
                          This event will issue {formatCurrency(preview.total_credit)} in store credit.
                          Please verify the filters are correct before running.
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Run Button */}
                <button
                  onClick={handleRun}
                  disabled={running || runSuccess || !name.trim() || preview.customer_count === 0}
                  className={`w-full py-4 rounded-xl font-semibold text-lg flex items-center justify-center gap-2 transition-all ${
                    runSuccess
                      ? 'bg-green-500 text-white'
                      : running
                      ? 'bg-orange-500/50 text-white/50 cursor-wait'
                      : 'bg-gradient-to-r from-orange-500 to-orange-600 text-white hover:from-orange-400 hover:to-orange-500 shadow-lg shadow-orange-500/25'
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  {runSuccess ? (
                    <>
                      <Icons.Check />
                      Event Created!
                    </>
                  ) : running ? (
                    <>
                      <Icons.Loader />
                      Running Event...
                    </>
                  ) : (
                    <>
                      <Icons.Play />
                      Run Event
                    </>
                  )}
                </button>

                {preview.customer_count === 0 && (
                  <p className="text-center text-sm text-white/40">
                    No customers match your current filters
                  </p>
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-white/40">
                <Icons.Filter />
                <p className="mt-2 text-sm">Set filters to see preview</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
