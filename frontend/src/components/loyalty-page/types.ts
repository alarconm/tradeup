/**
 * Shared types for loyalty page section components
 */

export interface SectionTheme {
  primaryColor?: string;
  accentColor?: string;
  backgroundColor?: string;
  textColor?: string;
  darkMode?: boolean;
}

export interface BaseProps {
  theme?: SectionTheme;
  className?: string;
}

export interface HeroSectionProps extends BaseProps {
  title: string;
  subtitle?: string;
  ctaText?: string;
  ctaUrl?: string;
  backgroundImage?: string;
  badge?: string;
  secondaryCtaText?: string;
  secondaryCtaUrl?: string;
}

export interface Step {
  icon?: string;
  title: string;
  description: string;
}

export interface HowItWorksSectionProps extends BaseProps {
  title?: string;
  subtitle?: string;
  steps: Step[];
}

export interface TierBenefit {
  name: string;
  included: boolean;
  value?: string;
}

export interface Tier {
  id: string;
  name: string;
  pointsRequired?: number;
  description?: string;
  benefits: TierBenefit[];
  featured?: boolean;
}

export interface TierComparisonSectionProps extends BaseProps {
  title?: string;
  subtitle?: string;
  tiers: Tier[];
  benefitLabels?: string[];
}

export interface Reward {
  id: string;
  name: string;
  description?: string;
  pointsCost: number;
  image?: string;
  category?: string;
  available?: boolean;
}

export interface RewardsCatalogSectionProps extends BaseProps {
  title?: string;
  subtitle?: string;
  rewards: Reward[];
  showPointsCost?: boolean;
}

export interface FAQItem {
  question: string;
  answer: string;
}

export interface FAQSectionProps extends BaseProps {
  title?: string;
  subtitle?: string;
  items: FAQItem[];
}

export interface CTASectionProps extends BaseProps {
  title: string;
  subtitle?: string;
  buttonText: string;
  buttonUrl?: string;
  showEmailForm?: boolean;
  emailPlaceholder?: string;
  onEmailSubmit?: (email: string) => void;
}
