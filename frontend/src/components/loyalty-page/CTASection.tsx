/**
 * CTA Section Component
 *
 * A call-to-action section with optional email signup form.
 */

import React, { useState } from 'react';
import type { CTASectionProps } from './types';

const defaultStyles = {
  section: {
    padding: '100px 24px',
    textAlign: 'center' as const,
  },
  container: {
    maxWidth: '700px',
    margin: '0 auto',
  },
  title: {
    fontSize: '40px',
    fontWeight: 800,
    marginBottom: '16px',
    margin: '0 0 16px 0',
  },
  subtitle: {
    fontSize: '20px',
    opacity: 0.9,
    marginBottom: '32px',
    margin: '0 0 32px 0',
  },
  button: {
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
  form: {
    display: 'flex',
    gap: '12px',
    justifyContent: 'center',
    flexWrap: 'wrap' as const,
    maxWidth: '500px',
    margin: '0 auto',
  },
  input: {
    flex: '1 1 250px',
    padding: '16px 20px',
    borderRadius: '8px',
    border: 'none',
    fontSize: '16px',
    minWidth: '200px',
  },
  submitButton: {
    padding: '16px 32px',
    borderRadius: '8px',
    fontWeight: 600,
    fontSize: '16px',
    border: 'none',
    cursor: 'pointer',
    transition: 'all 0.3s',
    whiteSpace: 'nowrap' as const,
  },
  successMessage: {
    padding: '16px 24px',
    borderRadius: '8px',
    fontSize: '16px',
    fontWeight: 500,
    marginTop: '16px',
    display: 'inline-block',
  },
  errorMessage: {
    padding: '16px 24px',
    borderRadius: '8px',
    fontSize: '16px',
    fontWeight: 500,
    marginTop: '16px',
    display: 'inline-block',
  },
};

export function CTASection({
  title,
  subtitle,
  buttonText,
  buttonUrl = '#',
  showEmailForm = false,
  emailPlaceholder = 'Enter your email',
  onEmailSubmit,
  theme = {},
  className = '',
}: CTASectionProps) {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  const {
    primaryColor = '#e85d27',
    backgroundColor,
    textColor = '#ffffff',
  } = theme;

  // CTA section typically has a gradient background
  const sectionStyle: React.CSSProperties = {
    ...defaultStyles.section,
    background: backgroundColor || `linear-gradient(135deg, ${primaryColor} 0%, ${lightenColor(primaryColor, 20)} 100%)`,
    color: textColor,
  };

  const buttonStyle: React.CSSProperties = {
    ...defaultStyles.button,
    background: textColor,
    color: primaryColor,
  };

  const inputStyle: React.CSSProperties = {
    ...defaultStyles.input,
    background: 'rgba(255, 255, 255, 0.9)',
    color: '#1a1a2e',
  };

  const submitButtonStyle: React.CSSProperties = {
    ...defaultStyles.submitButton,
    background: textColor,
    color: primaryColor,
  };

  const successMessageStyle: React.CSSProperties = {
    ...defaultStyles.successMessage,
    background: 'rgba(16, 185, 129, 0.2)',
    color: '#10b981',
  };

  const errorMessageStyle: React.CSSProperties = {
    ...defaultStyles.errorMessage,
    background: 'rgba(239, 68, 68, 0.2)',
    color: '#ef4444',
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email || !email.includes('@')) {
      setError('Please enter a valid email address');
      return;
    }

    if (onEmailSubmit) {
      onEmailSubmit(email);
    }

    setSubmitted(true);
    setEmail('');
  };

  return (
    <section style={sectionStyle} className={className}>
      <div style={defaultStyles.container}>
        <h2 style={defaultStyles.title}>{title}</h2>
        {subtitle && <p style={defaultStyles.subtitle}>{subtitle}</p>}

        {showEmailForm ? (
          <>
            {!submitted ? (
              <form style={defaultStyles.form} onSubmit={handleSubmit}>
                <input
                  type="email"
                  placeholder={emailPlaceholder}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  style={inputStyle}
                  aria-label="Email address"
                />
                <button type="submit" style={submitButtonStyle}>
                  {buttonText}
                </button>
              </form>
            ) : (
              <div style={successMessageStyle}>
                Thanks for signing up! We will be in touch soon.
              </div>
            )}
            {error && <div style={errorMessageStyle}>{error}</div>}
          </>
        ) : (
          <a href={buttonUrl} style={buttonStyle}>
            {buttonText}
          </a>
        )}
      </div>
    </section>
  );
}

/**
 * Helper function to lighten a hex color
 */
function lightenColor(hex: string, percent: number): string {
  // Remove # if present
  const cleanHex = hex.replace('#', '');

  // Parse RGB
  const r = parseInt(cleanHex.substring(0, 2), 16);
  const g = parseInt(cleanHex.substring(2, 4), 16);
  const b = parseInt(cleanHex.substring(4, 6), 16);

  // Lighten
  const lighten = (value: number) =>
    Math.min(255, Math.round(value + (255 - value) * (percent / 100)));

  const newR = lighten(r).toString(16).padStart(2, '0');
  const newG = lighten(g).toString(16).padStart(2, '0');
  const newB = lighten(b).toString(16).padStart(2, '0');

  return `#${newR}${newG}${newB}`;
}

export default CTASection;
