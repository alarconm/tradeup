import { useState, useEffect, useCallback, useRef } from 'react';

interface ShopifyBridgeState {
  shop: string | null;
  isEmbedded: boolean;
  isLoading: boolean;
  sessionToken: string | null;
  getSessionToken: () => Promise<string | null>;
}

// Session token cache
let cachedToken: string | null = null;
let tokenExpiry: number = 0;

/**
 * Get session token from Shopify App Bridge.
 * Tokens are cached and refreshed before expiry.
 */
async function fetchSessionToken(): Promise<string | null> {
  // Check cache first (tokens valid for ~60s, refresh at 45s)
  const now = Date.now();
  if (cachedToken && tokenExpiry > now + 15000) {
    return cachedToken;
  }

  // In embedded mode, use App Bridge to get token
  const isEmbedded = window.top !== window.self;
  if (!isEmbedded) {
    return null;
  }

  try {
    // Shopify App Bridge 4.x uses the global shopify object
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const shopify = (window as any).shopify;
    if (shopify?.idToken) {
      const token = await shopify.idToken();
      if (token) {
        cachedToken = token;
        // Tokens typically expire in 60 seconds
        tokenExpiry = now + 55000;
        return token;
      }
    }
  } catch (error) {
    console.warn('[TradeUp] Failed to get session token:', error);
  }

  return null;
}

/**
 * Hook to handle Shopify App Bridge initialization and shop context.
 * Detects if running embedded in Shopify admin or standalone.
 */
export function useShopifyBridge(): ShopifyBridgeState {
  const [state, setState] = useState<ShopifyBridgeState>({
    shop: null,
    isEmbedded: false,
    isLoading: true,
    sessionToken: null,
    getSessionToken: async () => null,
  });

  const initRef = useRef(false);

  const getSessionToken = useCallback(async (): Promise<string | null> => {
    return fetchSessionToken();
  }, []);

  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;

    const init = async () => {
      // Get shop from URL params or local storage
      const urlParams = new URLSearchParams(window.location.search);
      const shopParam = urlParams.get('shop');

      // Check if embedded in Shopify admin
      const isEmbedded = window.top !== window.self;

      // Try to get shop from various sources
      let shop = shopParam;

      if (!shop) {
        // Try local storage for returning users
        shop = localStorage.getItem('tradeup_shop');
      }

      // Development fallback - use a test shop for local dev
      if (!shop && import.meta.env.DEV) {
        shop = import.meta.env.VITE_SHOPIFY_SHOP || 'dev-shop.myshopify.com';
        console.log('[TradeUp] Dev mode: Using fallback shop:', shop);
      }

      if (shop) {
        localStorage.setItem('tradeup_shop', shop);
      }

      // Get initial session token if embedded
      let sessionToken: string | null = null;
      if (isEmbedded) {
        // Wait a tick for App Bridge to initialize
        await new Promise(resolve => setTimeout(resolve, 100));
        sessionToken = await fetchSessionToken();
      }

      setState({
        shop,
        isEmbedded,
        isLoading: false,
        sessionToken,
        getSessionToken,
      });
    };

    init();
  }, [getSessionToken]);

  return state;
}

/**
 * Get API base URL based on environment.
 * Prefers VITE_API_URL if set (for tunnel/production), falls back to localhost in dev.
 */
export function getApiUrl(): string {
  // Always prefer explicit API URL if set (supports tunnels in dev)
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  // Fall back to localhost for local dev, or /api for production
  return import.meta.env.DEV ? 'http://localhost:5000/api' : '/api';
}

/**
 * Get tenant ID from shop domain.
 */
export function getTenantParam(shop: string | null): string {
  if (!shop) return '';
  return `?shop=${encodeURIComponent(shop)}`;
}

/**
 * Create fetch options with session token authentication.
 * Use this for all API requests in the embedded app.
 */
export async function createAuthHeaders(shop: string | null): Promise<HeadersInit> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };

  // Try to get session token for embedded auth
  const token = await fetchSessionToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Also include shop as header for backwards compatibility
  if (shop) {
    headers['X-Shop-Domain'] = shop;
  }

  return headers;
}

/**
 * Authenticated fetch wrapper for API requests.
 * Automatically includes session token and shop context.
 */
export async function authFetch(
  url: string,
  shop: string | null,
  options: RequestInit = {}
): Promise<Response> {
  const headers = await createAuthHeaders(shop);

  // Add shop to URL if not already present
  const urlWithShop = url.includes('?')
    ? url.includes('shop=') ? url : `${url}&shop=${shop}`
    : `${url}?shop=${shop}`;

  return fetch(urlWithShop, {
    ...options,
    headers: {
      ...headers,
      ...options.headers,
    },
  });
}
