/**
 * Hero Section Component
 *
 * A configurable hero banner for loyalty program landing pages.
 * Supports title, subtitle, CTA buttons, background image, and badge.
 */

import React from 'react';
import type { HeroSectionProps } from './types';

const defaultStyles = {
  section: {
    padding: '100px 24px 80px',
    textAlign: 'center' as const,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    position: 'relative' as const,
  },
  overlay: {
    position: 'absolute' as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: 'rgba(0, 0, 0, 0.5)',
  },
  content: {
    position: 'relative' as const,
    zIndex: 1,
    maxWidth: '900px',
    margin: '0 auto',
  },
  badge: {
    display: 'inline-block',
    padding: '8px 16px',
    borderRadius: '20px',
    fontSize: '14px',
    fontWeight: 600,
    marginBottom: '24px',
  },
  title: {
    fontSize: 'clamp(36px, 5vw, 64px)',
    fontWeight: 800,
    lineHeight: 1.1,
    marginBottom: '24px',
    margin: '0 0 24px 0',
  },
  subtitle: {
    fontSize: '20px',
    maxWidth: '600px',
    margin: '0 auto 40px',
    opacity: 0.8,
  },
  ctaContainer: {
    display: 'flex',
    gap: '16px',
    flexWrap: 'wrap' as const,
    justifyContent: 'center',
  },
  primaryButton: {
    padding: '16px 32px',
    borderRadius: '8px',
    textDecoration: 'none',
    fontWeight: 600,
    fontSize: '18px',
    border: 'none',
    cursor: 'pointer',
    transition: 'all 0.3s',
    display: 'inline-block',
  },
  secondaryButton: {
    padding: '16px 32px',
    borderRadius: '8px',
    textDecoration: 'none',
    fontWeight: 600,
    fontSize: '18px',
    border: '2px solid',
    background: 'transparent',
    cursor: 'pointer',
    transition: 'all 0.3s',
    display: 'inline-block',
  },
};

export function HeroSection({
  title,
  subtitle,
  ctaText,
  ctaUrl = '#',
  backgroundImage,
  badge,
  secondaryCtaText,
  secondaryCtaUrl = '#',
  theme = {},
  className = '',
}: HeroSectionProps) {
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
    ...(backgroundImage && { backgroundImage: `url(${backgroundImage})` }),
  };

  const badgeStyle: React.CSSProperties = {
    ...defaultStyles.badge,
    background: darkMode ? 'rgba(232, 93, 39, 0.15)' : 'rgba(232, 93, 39, 0.1)',
    color: primaryColor,
    border: `1px solid ${primaryColor}40`,
  };

  const primaryButtonStyle: React.CSSProperties = {
    ...defaultStyles.primaryButton,
    background: primaryColor,
    color: '#ffffff',
  };

  const secondaryButtonStyle: React.CSSProperties = {
    ...defaultStyles.secondaryButton,
    borderColor: darkMode ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)',
    color: textColor,
  };

  return (
    <section style={sectionStyle} className={className}>
      {backgroundImage && <div style={defaultStyles.overlay} />}
      <div style={defaultStyles.content}>
        {badge && <div style={badgeStyle}>{badge}</div>}
        <h1 style={defaultStyles.title}>{title}</h1>
        {subtitle && <p style={defaultStyles.subtitle}>{subtitle}</p>}
        {(ctaText || secondaryCtaText) && (
          <div style={defaultStyles.ctaContainer}>
            {ctaText && (
              <a href={ctaUrl} style={primaryButtonStyle}>
                {ctaText}
              </a>
            )}
            {secondaryCtaText && (
              <a href={secondaryCtaUrl} style={secondaryButtonStyle}>
                {secondaryCtaText}
              </a>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

export default HeroSection;
