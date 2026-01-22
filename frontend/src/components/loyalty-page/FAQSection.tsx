/**
 * FAQ Section Component
 *
 * Displays expandable FAQ items for common questions about the loyalty program.
 */

import React, { useState } from 'react';
import type { FAQSectionProps } from './types';

const defaultStyles = {
  section: {
    padding: '80px 24px',
  },
  container: {
    maxWidth: '800px',
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
  faqList: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '16px',
  },
  faqItem: {
    borderRadius: '12px',
    overflow: 'hidden',
    transition: 'all 0.3s',
  },
  faqButton: {
    width: '100%',
    padding: '20px 24px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '16px',
    border: 'none',
    cursor: 'pointer',
    textAlign: 'left' as const,
    fontSize: '16px',
    fontWeight: 600,
    transition: 'all 0.2s',
  },
  questionText: {
    flex: 1,
  },
  expandIcon: {
    width: '24px',
    height: '24px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '20px',
    transition: 'transform 0.3s',
    flexShrink: 0,
  },
  answer: {
    padding: '0 24px 20px',
    fontSize: '15px',
    lineHeight: 1.7,
    opacity: 0.8,
  },
  noFaqs: {
    textAlign: 'center' as const,
    padding: '40px 20px',
    opacity: 0.7,
  },
};

interface FAQItemProps {
  question: string;
  answer: string;
  isOpen: boolean;
  onToggle: () => void;
  theme: {
    primaryColor: string;
    backgroundColor: string;
    textColor: string;
    darkMode: boolean;
  };
}

function FAQItem({ question, answer, isOpen, onToggle, theme }: FAQItemProps) {
  const { primaryColor, backgroundColor, textColor, darkMode } = theme;

  const itemStyle: React.CSSProperties = {
    ...defaultStyles.faqItem,
    background: darkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.03)',
    border: `1px solid ${darkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'}`,
  };

  const buttonStyle: React.CSSProperties = {
    ...defaultStyles.faqButton,
    background: 'transparent',
    color: textColor,
  };

  const iconStyle: React.CSSProperties = {
    ...defaultStyles.expandIcon,
    transform: isOpen ? 'rotate(45deg)' : 'rotate(0deg)',
    color: primaryColor,
  };

  return (
    <div style={itemStyle}>
      <button style={buttonStyle} onClick={onToggle} aria-expanded={isOpen}>
        <span style={defaultStyles.questionText}>{question}</span>
        <span style={iconStyle}>+</span>
      </button>
      {isOpen && (
        <div style={defaultStyles.answer}>
          {answer}
        </div>
      )}
    </div>
  );
}

export function FAQSection({
  title = 'Frequently Asked Questions',
  subtitle = 'Everything you need to know about our rewards program',
  items,
  theme = {},
  className = '',
}: FAQSectionProps) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

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

  const handleToggle = (index: number) => {
    setOpenIndex(openIndex === index ? null : index);
  };

  if (!items || items.length === 0) {
    return (
      <section style={sectionStyle} className={className}>
        <div style={defaultStyles.container}>
          <div style={defaultStyles.header}>
            <h2 style={defaultStyles.title}>{title}</h2>
            {subtitle && <p style={defaultStyles.subtitle}>{subtitle}</p>}
          </div>
          <div style={defaultStyles.noFaqs}>
            <p>No FAQs available at this time.</p>
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
        <div style={defaultStyles.faqList}>
          {items.map((item, index) => (
            <FAQItem
              key={index}
              question={item.question}
              answer={item.answer}
              isOpen={openIndex === index}
              onToggle={() => handleToggle(index)}
              theme={{ primaryColor, backgroundColor, textColor, darkMode }}
            />
          ))}
        </div>
      </div>
    </section>
  );
}

export default FAQSection;
