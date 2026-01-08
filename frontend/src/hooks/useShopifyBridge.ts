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
      // Check if embedded in Shopify admin
      const isEmbedded = window.top !== window.self;

      // Try to get shop from various sources (in priority order)
      let shop: string | null = null;

      // 1. First check Flask-injected config (most reliable in production)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const tradeupConfig = (window as any).__TRADEUP_CONFIG__;
      if (tradeupConfig?.shop) {
        shop = tradeupConfig.shop;
        console.log('[TradeUp] Got shop from server config:', shop);
      }

      // 2. Then check URL params (works for direct navigation)
      if (!shop) {
        const urlParams = new URLSearchParams(window.location.search);
        shop = urlParams.get('shop');
        if (shop) {
          console.log('[TradeUp] Got shop from URL params:', shop);
        }
      }

      // 2b. Try decoding shop from host param (Shopify always passes this)
      if (!shop) {
        // Check URL first, then server config
        const urlParams = new URLSearchParams(window.location.search);
        const host = urlParams.get('host') || tradeupConfig?.host;
        if (host) {
          try {
            // host is base64 encoded and contains shop info
            const decoded = atob(host);
            console.log('[TradeUp] Decoded host:', decoded);
            // Format is typically "admin.shopify.com/store/shop-name" or similar
            const match = decoded.match(/([a-zA-Z0-9-]+)\.myshopify\.com/) ||
                          decoded.match(/store\/([a-zA-Z0-9-]+)/);
            if (match) {
              shop = match[0].includes('.myshopify.com') ? match[0] : `${match[1]}.myshopify.com`;
              console.log('[TradeUp] Got shop from host param:', shop);
            }
          } catch (e) {
            console.warn('[TradeUp] Failed to decode host param:', e);
          }
        }
      }

      // 3. In embedded mode, get shop from session token (App Bridge 4.x)
      if (!shop && isEmbedded) {
        // Wait for App Bridge to initialize and get session token
        for (let i = 0; i < 30; i++) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const shopify = (window as any).shopify;
          if (shopify?.idToken) {
            try {
              const token = await shopify.idToken();
              if (token) {
                // Decode JWT payload to get shop (tokens are base64url encoded)
                const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
                if (payload.dest) {
                  // dest is the shop URL like "https://myshop.myshopify.com"
                  const shopUrl = new URL(payload.dest);
                  shop = shopUrl.hostname;
                  console.log('[TradeUp] Got shop from session token:', shop);
                  break;
                }
              }
            } catch (e) {
              console.warn('[TradeUp] Failed to decode session token:', e);
            }
          }
          await new Promise(resolve => setTimeout(resolve, 100));
        }
      }

      // 4. Try local storage for returning users
      if (!shop) {
        shop = localStorage.getItem('tradeup_shop');
        if (shop) {
          console.log('[TradeUp] Got shop from localStorage:', shop);
        }
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
      if (isEmbedded && shop) {
        sessionToken = await fetchSessionToken();
      }

      console.log('[TradeUp] Bridge initialized:', { shop, isEmbedded, hasToken: !!sessionToken });

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
