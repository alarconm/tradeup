/**
 * Tier Comparison Section Component
 *
 * Displays a comparison table of membership tiers and their benefits.
 */

import React from 'react';
import type { TierComparisonSectionProps } from './types';

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
  tiersGrid: {
    display: 'grid',
    gap: '24px',
  },
  tierCard: {
    padding: '32px',
    borderRadius: '16px',
    border: '1px solid',
    transition: 'all 0.3s',
    position: 'relative' as const,
  },
  featuredBadge: {
    position: 'absolute' as const,
    top: '-12px',
    left: '50%',
    transform: 'translateX(-50%)',
    padding: '4px 16px',
    borderRadius: '20px',
    fontSize: '12px',
    fontWeight: 600,
  },
  tierName: {
    fontSize: '24px',
    fontWeight: 700,
    marginBottom: '8px',
    margin: '0 0 8px 0',
  },
  tierPoints: {
    fontSize: '14px',
    opacity: 0.7,
    marginBottom: '16px',
    margin: '0 0 16px 0',
  },
  tierDescription: {
    fontSize: '14px',
    opacity: 0.7,
    marginBottom: '24px',
    margin: '0 0 24px 0',
  },
  benefitsList: {
    listStyle: 'none',
    padding: 0,
    margin: 0,
  },
  benefitItem: {
    padding: '12px 0',
    fontSize: '14px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    borderBottom: '1px solid',
  },
  benefitIcon: {
    width: '20px',
    height: '20px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '14px',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse' as const,
    marginTop: '20px',
  },
  tableHeader: {
    textAlign: 'left' as const,
    padding: '16px',
    fontWeight: 600,
    borderBottom: '2px solid',
  },
  tableCell: {
    padding: '16px',
    borderBottom: '1px solid',
  },
};

export function TierComparisonSection({
  title = 'Membership Tiers',
  subtitle = 'Choose the tier that fits your needs',
  tiers,
  benefitLabels,
  theme = {},
  className = '',
}: TierComparisonSectionProps) {
  const {
    primaryColor = '#e85d27',
    backgroundColor = '#0f0f1a',
    textColor = '#ffffff',
    darkMode = true,
  } = theme;

  const sectionStyle: React.CSSProperties = {
    ...defaultStyles.section,
    backgroundColor,
    color: textColor,
  };

  const borderColor = darkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';

  const tierCardStyle = (featured: boolean): React.CSSProperties => ({
    ...defaultStyles.tierCard,
    background: darkMode ? '#1a1a2e' : '#ffffff',
    borderColor: featured ? primaryColor : borderColor,
  });

  const featuredBadgeStyle: React.CSSProperties = {
    ...defaultStyles.featuredBadge,
    background: primaryColor,
    color: '#ffffff',
  };

  // Grid columns based on number of tiers
  const gridColumns = tiers.length <= 4 ? tiers.length : 4;
  const gridStyle: React.CSSProperties = {
    ...defaultStyles.tiersGrid,
    gridTemplateColumns: `repeat(${gridColumns}, 1fr)`,
  };

  // If we have benefit labels, show as a comparison table
  if (benefitLabels && benefitLabels.length > 0) {
    return (
      <section style={sectionStyle} className={className}>
        <div style={defaultStyles.container}>
          <div style={defaultStyles.header}>
            <h2 style={defaultStyles.title}>{title}</h2>
            {subtitle && <p style={defaultStyles.subtitle}>{subtitle}</p>}
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={defaultStyles.table}>
              <thead>
                <tr>
                  <th style={{ ...defaultStyles.tableHeader, borderColor }}></th>
                  {tiers.map((tier) => (
                    <th
                      key={tier.id}
                      style={{
                        ...defaultStyles.tableHeader,
                        borderColor,
                        color: tier.featured ? primaryColor : textColor,
                      }}
                    >
                      {tier.name}
                      {tier.pointsRequired !== undefined && (
                        <div style={{ fontSize: '12px', fontWeight: 'normal', opacity: 0.7 }}>
                          {tier.pointsRequired === 0 ? 'Starting tier' : `${tier.pointsRequired.toLocaleString()} points`}
                        </div>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {benefitLabels.map((label, index) => (
                  <tr key={index}>
                    <td style={{ ...defaultStyles.tableCell, borderColor, fontWeight: 500 }}>
                      {label}
                    </td>
                    {tiers.map((tier) => {
                      const benefit = tier.benefits.find((b) => b.name === label);
                      return (
                        <td
                          key={tier.id}
                          style={{
                            ...defaultStyles.tableCell,
                            borderColor,
                            textAlign: 'center',
                          }}
                        >
                          {benefit ? (
                            benefit.value ? (
                              <span style={{ color: primaryColor, fontWeight: 600 }}>{benefit.value}</span>
                            ) : benefit.included ? (
                              <span style={{ color: '#10b981' }}>Yes</span>
                            ) : (
                              <span style={{ opacity: 0.4 }}>-</span>
                            )
                          ) : (
                            <span style={{ opacity: 0.4 }}>-</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    );
  }

  // Card-based view
  return (
    <section style={sectionStyle} className={className}>
      <div style={defaultStyles.container}>
        <div style={defaultStyles.header}>
          <h2 style={defaultStyles.title}>{title}</h2>
          {subtitle && <p style={defaultStyles.subtitle}>{subtitle}</p>}
        </div>
        <div style={gridStyle}>
          {tiers.map((tier) => (
            <div key={tier.id} style={tierCardStyle(tier.featured || false)}>
              {tier.featured && <div style={featuredBadgeStyle}>Popular</div>}
              <h3 style={defaultStyles.tierName}>{tier.name}</h3>
              {tier.pointsRequired !== undefined && (
                <p style={defaultStyles.tierPoints}>
                  {tier.pointsRequired === 0
                    ? 'Starting tier'
                    : `${tier.pointsRequired.toLocaleString()} points to qualify`}
                </p>
              )}
              {tier.description && <p style={defaultStyles.tierDescription}>{tier.description}</p>}
              <ul style={defaultStyles.benefitsList}>
                {tier.benefits
                  .filter((b) => b.included)
                  .map((benefit, index) => (
                    <li
                      key={index}
                      style={{ ...defaultStyles.benefitItem, borderColor }}
                    >
                      <span style={{ ...defaultStyles.benefitIcon, color: '#10b981' }}>
                        Yes
                      </span>
                      <span>
                        {benefit.value ? `${benefit.value} ${benefit.name}` : benefit.name}
                      </span>
                    </li>
                  ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default TierComparisonSection;
