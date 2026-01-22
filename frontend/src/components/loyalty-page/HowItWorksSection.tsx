/**
 * How It Works Section Component
 *
 * Displays 3-4 step icons with descriptions explaining how the loyalty program works.
 */

import React from 'react';
import type { HowItWorksSectionProps } from './types';

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
  stepsGrid: {
    display: 'grid',
    gap: '24px',
  },
  step: {
    padding: '32px',
    borderRadius: '16px',
    textAlign: 'center' as const,
    position: 'relative' as const,
  },
  stepNumber: {
    width: '48px',
    height: '48px',
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontWeight: 700,
    fontSize: '20px',
    margin: '0 auto 20px',
  },
  stepIcon: {
    fontSize: '32px',
    marginBottom: '20px',
  },
  stepTitle: {
    fontSize: '18px',
    fontWeight: 600,
    marginBottom: '8px',
    margin: '0 0 8px 0',
  },
  stepDescription: {
    fontSize: '14px',
    opacity: 0.6,
    margin: 0,
    lineHeight: 1.5,
  },
};

export function HowItWorksSection({
  title = 'How It Works',
  subtitle = 'Join our rewards program in just a few simple steps',
  steps,
  theme = {},
  className = '',
}: HowItWorksSectionProps) {
  const {
    primaryColor = '#e85d27',
    backgroundColor = '#1a1a2e',
    textColor = '#ffffff',
    darkMode = true,
  } = theme;

  const sectionStyle: React.CSSProperties = {
    ...defaultStyles.section,
    backgroundColor,
    color: textColor,
  };

  const stepStyle: React.CSSProperties = {
    ...defaultStyles.step,
    background: darkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.03)',
  };

  const stepNumberStyle: React.CSSProperties = {
    ...defaultStyles.stepNumber,
    background: primaryColor,
    color: '#ffffff',
  };

  // Responsive grid columns based on number of steps
  const gridColumns = steps.length <= 2 ? steps.length : steps.length <= 4 ? steps.length : 4;
  const gridStyle: React.CSSProperties = {
    ...defaultStyles.stepsGrid,
    gridTemplateColumns: `repeat(${gridColumns}, 1fr)`,
  };

  return (
    <section style={sectionStyle} className={className}>
      <div style={defaultStyles.container}>
        <div style={defaultStyles.header}>
          <h2 style={defaultStyles.title}>{title}</h2>
          {subtitle && <p style={defaultStyles.subtitle}>{subtitle}</p>}
        </div>
        <div style={gridStyle}>
          {steps.map((step, index) => (
            <div key={index} style={stepStyle}>
              {step.icon ? (
                <div style={defaultStyles.stepIcon}>{step.icon}</div>
              ) : (
                <div style={stepNumberStyle}>{index + 1}</div>
              )}
              <h4 style={defaultStyles.stepTitle}>{step.title}</h4>
              <p style={defaultStyles.stepDescription}>{step.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default HowItWorksSection;
