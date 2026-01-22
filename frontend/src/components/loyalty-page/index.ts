/**
 * Loyalty Page Section Components
 *
 * Pre-built section components for the loyalty landing page builder.
 * Each component is configurable via props and supports theming.
 */

// Components
export { HeroSection } from './HeroSection';
export { HowItWorksSection } from './HowItWorksSection';
export { TierComparisonSection } from './TierComparisonSection';
export { RewardsCatalogSection } from './RewardsCatalogSection';
export { FAQSection } from './FAQSection';
export { CTASection } from './CTASection';

// Types
export type {
  SectionTheme,
  BaseProps,
  HeroSectionProps,
  Step,
  HowItWorksSectionProps,
  TierBenefit,
  Tier,
  TierComparisonSectionProps,
  Reward,
  RewardsCatalogSectionProps,
  FAQItem,
  FAQSectionProps,
  CTASectionProps,
} from './types';
