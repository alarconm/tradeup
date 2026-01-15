/**
 * React Hook and Context for Internationalization
 *
 * Provides easy access to translations throughout the app.
 *
 * Usage:
 *   const { t, locale, setLocale, formatCurrency } = useI18n();
 *   <p>{t('common.save')}</p>
 */

import React, { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from 'react';
import i18n, {
  type LocaleCode,
  detectLocale,
  t as translate,
  tInterpolate,
  formatCurrency as formatCurrencyFn,
  formatDate as formatDateFn,
  formatNumber as formatNumberFn,
  AVAILABLE_LOCALES,
  DEFAULT_LOCALE,
} from '../locales';

interface I18nContextType {
  locale: LocaleCode;
  setLocale: (locale: LocaleCode) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
  formatCurrency: (amount: number, currency?: string) => string;
  formatDate: (date: Date | string, options?: Intl.DateTimeFormatOptions) => string;
  formatNumber: (num: number) => string;
  availableLocales: typeof AVAILABLE_LOCALES;
}

const I18nContext = createContext<I18nContextType | undefined>(undefined);

interface I18nProviderProps {
  children: ReactNode;
  initialLocale?: LocaleCode;
}

/**
 * I18n Provider Component
 *
 * Wrap your app with this provider to enable translations.
 *
 * @example
 * <I18nProvider>
 *   <App />
 * </I18nProvider>
 */
export function I18nProvider({ children, initialLocale }: I18nProviderProps) {
  const [locale, setLocaleState] = useState<LocaleCode>(
    initialLocale || detectLocale()
  );

  const setLocale = useCallback((newLocale: LocaleCode) => {
    // Validate locale
    if (AVAILABLE_LOCALES.find(l => l.code === newLocale)) {
      setLocaleState(newLocale);

      // Persist to localStorage
      try {
        localStorage.setItem('tradeup_locale', newLocale);
      } catch {
        // Ignore storage errors
      }
    }
  }, []);

  const t = useCallback(
    (key: string, params?: Record<string, string | number>) => {
      if (params) {
        return tInterpolate(key, locale, params);
      }
      return translate(key, locale);
    },
    [locale]
  );

  const formatCurrency = useCallback(
    (amount: number, currency = 'USD') => {
      return formatCurrencyFn(amount, currency, locale);
    },
    [locale]
  );

  const formatDate = useCallback(
    (date: Date | string, options?: Intl.DateTimeFormatOptions) => {
      return formatDateFn(date, locale, options);
    },
    [locale]
  );

  const formatNumber = useCallback(
    (num: number) => {
      return formatNumberFn(num, locale);
    },
    [locale]
  );

  const value = useMemo(
    () => ({
      locale,
      setLocale,
      t,
      formatCurrency,
      formatDate,
      formatNumber,
      availableLocales: AVAILABLE_LOCALES,
    }),
    [locale, setLocale, t, formatCurrency, formatDate, formatNumber]
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

/**
 * Hook to access i18n functionality
 *
 * @example
 * function MyComponent() {
 *   const { t, locale, formatCurrency } = useI18n();
 *   return (
 *     <div>
 *       <h1>{t('dashboard.title')}</h1>
 *       <p>{formatCurrency(100)}</p>
 *     </div>
 *   );
 * }
 */
export function useI18n(): I18nContextType {
  const context = useContext(I18nContext);

  if (!context) {
    // Return default context if provider not found
    // This allows components to work without the provider
    return {
      locale: DEFAULT_LOCALE,
      setLocale: () => {},
      t: (key: string) => translate(key, DEFAULT_LOCALE),
      formatCurrency: (amount: number, currency = 'USD') =>
        formatCurrencyFn(amount, currency, DEFAULT_LOCALE),
      formatDate: (date: Date | string) => formatDateFn(date, DEFAULT_LOCALE),
      formatNumber: (num: number) => formatNumberFn(num, DEFAULT_LOCALE),
      availableLocales: AVAILABLE_LOCALES,
    };
  }

  return context;
}

/**
 * Higher-order component for class components
 *
 * @example
 * class MyComponent extends React.Component {
 *   render() {
 *     const { t } = this.props.i18n;
 *     return <h1>{t('dashboard.title')}</h1>;
 *   }
 * }
 * export default withI18n(MyComponent);
 */
export function withI18n<P extends { i18n?: I18nContextType }>(
  Component: React.ComponentType<P>
) {
  return function WithI18nComponent(props: Omit<P, 'i18n'>) {
    const i18n = useI18n();
    return <Component {...(props as P)} i18n={i18n} />;
  };
}

export default useI18n;
