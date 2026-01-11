/**
 * i18n Configuration for TradeUp Frontend
 *
 * Provides internationalization support using i18next.
 * Supports: English, Spanish, French, German, Japanese
 *
 * Usage:
 *   import { useTranslation } from 'react-i18next';
 *   const { t } = useTranslation();
 *   t('dashboard.title')
 */
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

// Import locale files
import en from './locales/en.json';
import es from './locales/es.json';
import fr from './locales/fr.json';
import de from './locales/de.json';
import ja from './locales/ja.json';

// Supported locales
export const supportedLocales = ['en', 'es', 'fr', 'de', 'ja'] as const;
export type SupportedLocale = (typeof supportedLocales)[number];

// Locale display names
export const localeNames: Record<SupportedLocale, string> = {
  en: 'English',
  es: 'Español',
  fr: 'Français',
  de: 'Deutsch',
  ja: '日本語',
};

// Detect browser language or use Shopify shop locale
function detectLocale(): SupportedLocale {
  // Try to get locale from URL params (Shopify embeds can pass locale)
  const urlParams = new URLSearchParams(window.location.search);
  const urlLocale = urlParams.get('locale');
  if (urlLocale && supportedLocales.includes(urlLocale as SupportedLocale)) {
    return urlLocale as SupportedLocale;
  }

  // Try browser language
  const browserLang = navigator.language.split('-')[0];
  if (supportedLocales.includes(browserLang as SupportedLocale)) {
    return browserLang as SupportedLocale;
  }

  // Try localStorage (user preference)
  const storedLocale = localStorage.getItem('tradeup-locale');
  if (storedLocale && supportedLocales.includes(storedLocale as SupportedLocale)) {
    return storedLocale as SupportedLocale;
  }

  return 'en';
}

// Initialize i18n
i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    es: { translation: es },
    fr: { translation: fr },
    de: { translation: de },
    ja: { translation: ja },
  },
  lng: detectLocale(),
  fallbackLng: 'en',
  interpolation: {
    escapeValue: false, // React already escapes values
  },
  // Enable debug in development
  debug: import.meta.env.DEV,
});

// Helper to change locale and persist preference
export function setLocale(locale: SupportedLocale): void {
  i18n.changeLanguage(locale);
  localStorage.setItem('tradeup-locale', locale);
}

// Get current locale
export function getLocale(): SupportedLocale {
  return i18n.language as SupportedLocale;
}

export default i18n;
