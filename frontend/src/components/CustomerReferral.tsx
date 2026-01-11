/**
 * Customer-Facing Referral Component
 *
 * This component is designed to be embedded in a Shopify store's
 * customer account page or as a standalone referral widget.
 *
 * Features:
 * - Display referral code with copy button
 * - Social share buttons
 * - Referral stats (successful referrals, rewards earned)
 * - Recent referrals list
 */
import { useState, useEffect, useCallback } from 'react';

interface ReferralData {
  is_member: boolean;
  program_active: boolean;
  member_name?: string;
  referral_code?: string;
  share_url?: string;
  rewards?: {
    referrer_amount: number;
    referred_amount: number;
    reward_type: string;
  };
  stats?: {
    total_referrals: number;
    pending_referrals: number;
  };
  recent_referrals?: Array<{
    name: string;
    status: string;
    created_at: string;
  }>;
  program?: {
    name: string;
    description: string;
  };
  message?: string;
}

interface CustomerReferralProps {
  apiUrl: string;
  customerId: string;
  shop: string;
  theme?: 'light' | 'dark';
  primaryColor?: string;
}

export function CustomerReferral({
  apiUrl,
  customerId,
  shop,
  theme = 'light',
  primaryColor = '#2563eb',
}: CustomerReferralProps) {
  const [data, setData] = useState<ReferralData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    async function fetchReferralData() {
      try {
        const response = await fetch(`${apiUrl}/api/customer/extension/referral`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            customer_id: customerId,
            shop: shop,
          }),
        });

        if (!response.ok) {
          throw new Error('Failed to fetch referral data');
        }

        const result = await response.json();
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load referral data');
      } finally {
        setLoading(false);
      }
    }

    if (customerId && shop) {
      fetchReferralData();
    }
  }, [apiUrl, customerId, shop]);

  const handleCopyCode = useCallback(async () => {
    if (!data?.referral_code) return;

    try {
      await navigator.clipboard.writeText(data.referral_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const input = document.createElement('input');
      input.value = data.referral_code;
      document.body.appendChild(input);
      input.select();
      document.execCommand('copy');
      document.body.removeChild(input);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [data?.referral_code]);

  const handleShare = useCallback(async (platform: string) => {
    if (!data?.share_url) return;

    const shareText = `Join me at ${shop} and we'll both get store credit! Use my referral code: ${data.referral_code}`;

    let shareUrl = '';
    switch (platform) {
      case 'facebook':
        shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(data.share_url)}`;
        break;
      case 'twitter':
        shareUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(data.share_url)}`;
        break;
      case 'email':
        shareUrl = `mailto:?subject=${encodeURIComponent(`Join me at ${shop}!`)}&body=${encodeURIComponent(shareText + '\n\n' + data.share_url)}`;
        break;
      case 'whatsapp':
        shareUrl = `https://wa.me/?text=${encodeURIComponent(shareText + ' ' + data.share_url)}`;
        break;
    }

    if (shareUrl) {
      window.open(shareUrl, '_blank', 'noopener,noreferrer');
    }
  }, [data, shop]);

  // Styles based on theme
  const isDark = theme === 'dark';
  const styles = {
    container: {
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      background: isDark ? '#1f2937' : '#ffffff',
      color: isDark ? '#f9fafb' : '#111827',
      borderRadius: '12px',
      padding: '24px',
      maxWidth: '400px',
      boxShadow: isDark ? 'none' : '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
      border: isDark ? '1px solid #374151' : '1px solid #e5e7eb',
    },
    header: {
      fontSize: '20px',
      fontWeight: 600,
      marginBottom: '8px',
    },
    description: {
      fontSize: '14px',
      color: isDark ? '#9ca3af' : '#6b7280',
      marginBottom: '20px',
    },
    codeBox: {
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      background: isDark ? '#374151' : '#f3f4f6',
      borderRadius: '8px',
      padding: '12px 16px',
      marginBottom: '16px',
    },
    code: {
      flex: 1,
      fontSize: '24px',
      fontWeight: 700,
      letterSpacing: '2px',
      color: primaryColor,
      fontFamily: 'monospace',
    },
    copyButton: {
      background: copied ? '#10b981' : primaryColor,
      color: '#ffffff',
      border: 'none',
      borderRadius: '6px',
      padding: '8px 16px',
      fontSize: '14px',
      fontWeight: 500,
      cursor: 'pointer',
      transition: 'background 0.2s',
    },
    rewardBadge: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: '4px',
      background: isDark ? '#065f46' : '#d1fae5',
      color: isDark ? '#34d399' : '#065f46',
      borderRadius: '9999px',
      padding: '4px 12px',
      fontSize: '12px',
      fontWeight: 500,
      marginBottom: '16px',
    },
    shareButtons: {
      display: 'flex',
      gap: '8px',
      marginBottom: '20px',
    },
    shareButton: {
      flex: 1,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '6px',
      padding: '10px',
      borderRadius: '8px',
      border: isDark ? '1px solid #374151' : '1px solid #e5e7eb',
      background: isDark ? '#374151' : '#ffffff',
      color: isDark ? '#f9fafb' : '#374151',
      fontSize: '13px',
      fontWeight: 500,
      cursor: 'pointer',
      transition: 'background 0.2s',
    },
    stats: {
      display: 'flex',
      gap: '16px',
      background: isDark ? '#374151' : '#f9fafb',
      borderRadius: '8px',
      padding: '16px',
    },
    statItem: {
      flex: 1,
      textAlign: 'center' as const,
    },
    statValue: {
      fontSize: '24px',
      fontWeight: 700,
      color: primaryColor,
    },
    statLabel: {
      fontSize: '12px',
      color: isDark ? '#9ca3af' : '#6b7280',
      marginTop: '4px',
    },
    loading: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '40px',
    },
    notMember: {
      textAlign: 'center' as const,
      padding: '20px',
    },
  };

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.loading}>
          <span>Loading referral program...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.container}>
        <div style={styles.notMember}>
          <p style={{ color: '#ef4444' }}>{error}</p>
        </div>
      </div>
    );
  }

  if (!data?.is_member) {
    return (
      <div style={styles.container}>
        <div style={styles.notMember}>
          <h3 style={styles.header}>Join Our Rewards Program</h3>
          <p style={styles.description}>
            {data?.message || 'Become a member to unlock exclusive referral rewards!'}
          </p>
        </div>
      </div>
    );
  }

  if (!data.program_active) {
    return (
      <div style={styles.container}>
        <div style={styles.notMember}>
          <h3 style={styles.header}>Referral Program</h3>
          <p style={styles.description}>
            {data.message || 'The referral program is not currently active.'}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <h3 style={styles.header}>Refer Friends, Earn Rewards</h3>
      <p style={styles.description}>
        {data.program?.description}
      </p>

      <div style={styles.rewardBadge}>
        <span>🎁</span>
        <span>
          Give ${data.rewards?.referred_amount}, Get ${data.rewards?.referrer_amount}
        </span>
      </div>

      <div style={styles.codeBox}>
        <span style={styles.code}>{data.referral_code}</span>
        <button style={styles.copyButton} onClick={handleCopyCode}>
          {copied ? '✓ Copied!' : 'Copy'}
        </button>
      </div>

      <div style={styles.shareButtons}>
        <button style={styles.shareButton} onClick={() => handleShare('email')}>
          📧 Email
        </button>
        <button style={styles.shareButton} onClick={() => handleShare('whatsapp')}>
          💬 WhatsApp
        </button>
        <button style={styles.shareButton} onClick={() => handleShare('twitter')}>
          🐦 Twitter
        </button>
      </div>

      <div style={styles.stats}>
        <div style={styles.statItem}>
          <div style={styles.statValue}>{data.stats?.total_referrals || 0}</div>
          <div style={styles.statLabel}>Successful Referrals</div>
        </div>
        <div style={styles.statItem}>
          <div style={styles.statValue}>{data.stats?.pending_referrals || 0}</div>
          <div style={styles.statLabel}>Pending</div>
        </div>
      </div>
    </div>
  );
}

export default CustomerReferral;
