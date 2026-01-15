/**
 * TradeUp Internationalization (i18n) Module
 *
 * Provides multi-language support for the frontend.
 * Supports 12+ languages commonly used by Shopify merchants.
 */

import en from './en.json';
import es from './es.json';
import fr from './fr.json';

// Type definitions
export type LocaleCode =
  | 'en' | 'es' | 'fr' | 'de' | 'it' | 'pt' | 'pt-BR'
  | 'nl' | 'ja' | 'ko' | 'zh-CN' | 'zh-TW';

export interface LocaleInfo {
  code: LocaleCode;
  name: string;
  nativeName: string;
  flag: string;
}

// Available locales with metadata
export const AVAILABLE_LOCALES: LocaleInfo[] = [
  { code: 'en', name: 'English', nativeName: 'English', flag: '🇺🇸' },
  { code: 'es', name: 'Spanish', nativeName: 'Espanol', flag: '🇪🇸' },
  { code: 'fr', name: 'French', nativeName: 'Francais', flag: '🇫🇷' },
  { code: 'de', name: 'German', nativeName: 'Deutsch', flag: '🇩🇪' },
  { code: 'it', name: 'Italian', nativeName: 'Italiano', flag: '🇮🇹' },
  { code: 'pt', name: 'Portuguese', nativeName: 'Portugues', flag: '🇵🇹' },
  { code: 'pt-BR', name: 'Portuguese (Brazil)', nativeName: 'Portugues (Brasil)', flag: '🇧🇷' },
  { code: 'nl', name: 'Dutch', nativeName: 'Nederlands', flag: '🇳🇱' },
  { code: 'ja', name: 'Japanese', nativeName: '日本語', flag: '🇯🇵' },
  { code: 'ko', name: 'Korean', nativeName: '한국어', flag: '🇰🇷' },
  { code: 'zh-CN', name: 'Chinese (Simplified)', nativeName: '简体中文', flag: '🇨🇳' },
  { code: 'zh-TW', name: 'Chinese (Traditional)', nativeName: '繁體中文', flag: '🇹🇼' },
];

// Loaded translations (lazy loading for non-default locales)
const translations: Record<string, typeof en> = {
  en,
  es,
  fr,
};

// Default locale
export const DEFAULT_LOCALE: LocaleCode = 'en';

/**
 * Get translations for a locale
 * Falls back to English if locale not found
 */
export function getTranslations(locale: LocaleCode): typeof en {
  return translations[locale] || translations[DEFAULT_LOCALE];
}

/**
 * Translate a key path (e.g., "common.save")
 */
export function t(key: string, locale: LocaleCode = DEFAULT_LOCALE): string {
  const trans = getTranslations(locale);
  const keys = key.split('.');

  let value: unknown = trans;
  for (const k of keys) {
    if (value && typeof value === 'object' && k in value) {
      value = (value as Record<string, unknown>)[k];
    } else {
      // Key not found, return the key itself
      return key;
    }
  }

  return typeof value === 'string' ? value : key;
}

/**
 * Translate with interpolation
 * e.g., t('greeting', 'en', { name: 'John' }) => "Hello, John!"
 */
export function tInterpolate(
  key: string,
  locale: LocaleCode = DEFAULT_LOCALE,
  params: Record<string, string | number> = {}
): string {
  let text = t(key, locale);

  for (const [param, value] of Object.entries(params)) {
    text = text.replace(new RegExp(`{${param}}`, 'g'), String(value));
  }

  return text;
}

/**
 * Detect locale from browser or Shopify shop settings
 */
export function detectLocale(): LocaleCode {
  // Check Shopify config first
  const shopifyConfig = (window as unknown as { __TRADEUP_CONFIG__?: { locale?: string } }).__TRADEUP_CONFIG__;
  if (shopifyConfig?.locale) {
    const code = shopifyConfig.locale.toLowerCase();
    if (AVAILABLE_LOCALES.find(l => l.code === code)) {
      return code as LocaleCode;
    }
  }

  // Fall back to browser language
  const browserLang = navigator.language || (navigator as unknown as { userLanguage?: string }).userLanguage;
  if (browserLang) {
    // Try exact match first
    const exact = browserLang.toLowerCase();
    if (AVAILABLE_LOCALES.find(l => l.code === exact)) {
      return exact as LocaleCode;
    }

    // Try base language (e.g., "en" from "en-US")
    const base = exact.split('-')[0];
    if (AVAILABLE_LOCALES.find(l => l.code === base)) {
      return base as LocaleCode;
    }
  }

  return DEFAULT_LOCALE;
}

/**
 * Format currency for a locale
 */
export function formatCurrency(
  amount: number,
  currency = 'USD',
  locale: LocaleCode = DEFAULT_LOCALE
): string {
  const localeMap: Record<LocaleCode, string> = {
    'en': 'en-US',
    'es': 'es-ES',
    'fr': 'fr-FR',
    'de': 'de-DE',
    'it': 'it-IT',
    'pt': 'pt-PT',
    'pt-BR': 'pt-BR',
    'nl': 'nl-NL',
    'ja': 'ja-JP',
    'ko': 'ko-KR',
    'zh-CN': 'zh-CN',
    'zh-TW': 'zh-TW',
  };

  return new Intl.NumberFormat(localeMap[locale] || 'en-US', {
    style: 'currency',
    currency,
  }).format(amount);
}

/**
 * Format date for a locale
 */
export function formatDate(
  date: Date | string,
  locale: LocaleCode = DEFAULT_LOCALE,
  options?: Intl.DateTimeFormatOptions
): string {
  const d = typeof date === 'string' ? new Date(date) : date;

  const localeMap: Record<LocaleCode, string> = {
    'en': 'en-US',
    'es': 'es-ES',
    'fr': 'fr-FR',
    'de': 'de-DE',
    'it': 'it-IT',
    'pt': 'pt-PT',
    'pt-BR': 'pt-BR',
    'nl': 'nl-NL',
    'ja': 'ja-JP',
    'ko': 'ko-KR',
    'zh-CN': 'zh-CN',
    'zh-TW': 'zh-TW',
  };

  const defaultOptions: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  };

  return new Intl.DateTimeFormat(
    localeMap[locale] || 'en-US',
    options || defaultOptions
  ).format(d);
}

/**
 * Format number for a locale
 */
export function formatNumber(
  num: number,
  locale: LocaleCode = DEFAULT_LOCALE
): string {
  const localeMap: Record<LocaleCode, string> = {
    'en': 'en-US',
    'es': 'es-ES',
    'fr': 'fr-FR',
    'de': 'de-DE',
    'it': 'it-IT',
    'pt': 'pt-PT',
    'pt-BR': 'pt-BR',
    'nl': 'nl-NL',
    'ja': 'ja-JP',
    'ko': 'ko-KR',
    'zh-CN': 'zh-CN',
    'zh-TW': 'zh-TW',
  };

  return new Intl.NumberFormat(localeMap[locale] || 'en-US').format(num);
}

export default {
  t,
  tInterpolate,
  getTranslations,
  detectLocale,
  formatCurrency,
  formatDate,
  formatNumber,
  AVAILABLE_LOCALES,
  DEFAULT_LOCALE,
};
