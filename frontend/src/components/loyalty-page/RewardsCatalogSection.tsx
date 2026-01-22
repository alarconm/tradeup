/**
 * Rewards Catalog Section Component
 *
 * Displays available rewards that members can redeem with their points.
 */

import React from 'react';
import type { RewardsCatalogSectionProps } from './types';

const defaultStyles = {
  section: {
    padding: '80px 24px',
  },
  container: {
    maxWidth: '1200px',
    margin: '0 auto',
  },
  header: {
    textAlign: 'center' as const,
    marginBottom: '60px',
  },
  title: {
    fontSize: '40px',
    fontWeight: 800,
    marginBottom: '16px',
    margin: '0 0 16px 0',
  },
  subtitle: {
    fontSize: '18px',
    opacity: 0.6,
    margin: 0,
  },
  rewardsGrid: {
    display: 'grid',
    gap: '24px',
  },
  rewardCard: {
    borderRadius: '16px',
    overflow: 'hidden',
    transition: 'all 0.3s',
    position: 'relative' as const,
  },
  imageContainer: {
    width: '100%',
    height: '160px',
    overflow: 'hidden',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  image: {
    width: '100%',
    height: '100%',
    objectFit: 'cover' as const,
  },
  imagePlaceholder: {
    width: '100%',
    height: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '48px',
  },
  cardContent: {
    padding: '20px',
  },
  category: {
    fontSize: '12px',
    textTransform: 'uppercase' as const,
    letterSpacing: '1px',
    marginBottom: '8px',
    opacity: 0.7,
    margin: '0 0 8px 0',
  },
  rewardName: {
    fontSize: '18px',
    fontWeight: 600,
    marginBottom: '8px',
    margin: '0 0 8px 0',
  },
  rewardDescription: {
    fontSize: '14px',
    opacity: 0.7,
    marginBottom: '16px',
    margin: '0 0 16px 0',
    lineHeight: 1.5,
  },
  pointsCost: {
    fontSize: '16px',
    fontWeight: 700,
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
  },
  unavailableBadge: {
    position: 'absolute' as const,
    top: '12px',
    right: '12px',
    padding: '4px 12px',
    borderRadius: '12px',
    fontSize: '12px',
    fontWeight: 600,
    background: 'rgba(0, 0, 0, 0.6)',
    color: '#ffffff',
  },
  noRewards: {
    textAlign: 'center' as const,
    padding: '60px 20px',
    opacity: 0.7,
  },
};

export function RewardsCatalogSection({
  title = 'Rewards Catalog',
  subtitle = 'Redeem your points for exclusive rewards',
  rewards,
  showPointsCost = true,
  theme = {},
  className = '',
}: RewardsCatalogSectionProps) {
  const {
    primaryColor = '#e85d27',
    accentColor = '#ffd700',
    backgroundColor = '#0f0f1a',
    textColor = '#ffffff',
    darkMode = true,
  } = theme;

  const sectionStyle: React.CSSProperties = {
    ...defaultStyles.section,
    backgroundColor,
    color: textColor,
  };

  const rewardCardStyle: React.CSSProperties = {
    ...defaultStyles.rewardCard,
    background: darkMode ? '#1a1a2e' : '#ffffff',
    border: `1px solid ${darkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'}`,
  };

  const imagePlaceholderStyle: React.CSSProperties = {
    ...defaultStyles.imagePlaceholder,
    background: darkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.03)',
  };

  const pointsCostStyle: React.CSSProperties = {
    ...defaultStyles.pointsCost,
    color: accentColor,
  };

  // Responsive grid columns based on number of rewards
  const getGridColumns = () => {
    if (rewards.length === 1) return 1;
    if (rewards.length === 2) return 2;
    if (rewards.length <= 4) return rewards.length;
    return 4;
  };

  const gridStyle: React.CSSProperties = {
    ...defaultStyles.rewardsGrid,
    gridTemplateColumns: `repeat(${getGridColumns()}, 1fr)`,
  };

  if (!rewards || rewards.length === 0) {
    return (
      <section style={sectionStyle} className={className}>
        <div style={defaultStyles.container}>
          <div style={defaultStyles.header}>
            <h2 style={defaultStyles.title}>{title}</h2>
            {subtitle && <p style={defaultStyles.subtitle}>{subtitle}</p>}
          </div>
          <div style={defaultStyles.noRewards}>
            <p>No rewards available at this time. Check back soon!</p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section style={sectionStyle} className={className}>
      <div style={defaultStyles.container}>
        <div style={defaultStyles.header}>
          <h2 style={defaultStyles.title}>{title}</h2>
          {subtitle && <p style={defaultStyles.subtitle}>{subtitle}</p>}
        </div>
        <div style={gridStyle}>
          {rewards.map((reward) => (
            <div
              key={reward.id}
              style={{
                ...rewardCardStyle,
                opacity: reward.available === false ? 0.6 : 1,
              }}
            >
              {reward.available === false && (
                <div style={defaultStyles.unavailableBadge}>Coming Soon</div>
              )}
              <div style={defaultStyles.imageContainer}>
                {reward.image ? (
                  <img src={reward.image} alt={reward.name} style={defaultStyles.image} />
                ) : (
                  <div style={imagePlaceholderStyle}>
                    <span role="img" aria-label="gift">
                      Gift
                    </span>
                  </div>
                )}
              </div>
              <div style={defaultStyles.cardContent}>
                {reward.category && (
                  <p style={{ ...defaultStyles.category, color: primaryColor }}>
                    {reward.category}
                  </p>
                )}
                <h4 style={defaultStyles.rewardName}>{reward.name}</h4>
                {reward.description && (
                  <p style={defaultStyles.rewardDescription}>{reward.description}</p>
                )}
                {showPointsCost && (
                  <div style={pointsCostStyle}>
                    <span>{reward.pointsCost.toLocaleString()}</span>
                    <span style={{ fontWeight: 400, opacity: 0.8 }}>points</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default RewardsCatalogSection;
