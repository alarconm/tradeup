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
      // Add timeout to prevent hanging if App Bridge isn't ready
      const tokenPromise = shopify.idToken();
      const timeoutPromise = new Promise<null>((resolve) => setTimeout(() => resolve(null), 3000));
      const token = await Promise.race([tokenPromise, timeoutPromise]);
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
      try {
        // Check if embedded in Shopify admin
        const isEmbedded = window.top !== window.self;
        console.log('[TradeUp] Starting init, isEmbedded:', isEmbedded);

        // Try to get shop from various sources (in priority order)
        let shop: string | null = null;

        // Helper to ensure shop has .myshopify.com suffix
        const normalizeShop = (s: string): string => {
          if (!s) return s;
          return s.includes('.myshopify.com') ? s : `${s}.myshopify.com`;
        };

        // 1. First check Flask-injected config (most reliable in production)
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const tradeupConfig = (window as any).__TRADEUP_CONFIG__;
        if (tradeupConfig?.shop) {
          shop = normalizeShop(tradeupConfig.shop);
          console.log('[TradeUp] Got shop from server config:', shop);
        }

        // 2. Then check URL params (works for direct navigation)
        if (!shop) {
          const urlParams = new URLSearchParams(window.location.search);
          const shopParam = urlParams.get('shop');
          if (shopParam) {
            shop = normalizeShop(shopParam);
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
          console.log('[TradeUp] Trying session token...');
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

        // 4. Try local storage for returning users (wrapped in try-catch for iframe restrictions)
        if (!shop) {
          try {
            const storedShop = localStorage.getItem('tradeup_shop');
            if (storedShop) {
              shop = normalizeShop(storedShop);
              console.log('[TradeUp] Got shop from localStorage:', shop);
            }
          } catch (e) {
            console.warn('[TradeUp] localStorage read blocked:', e);
          }
        }

        // Development fallback - use a test shop for local dev
        if (!shop && import.meta.env.DEV) {
          shop = import.meta.env.VITE_SHOPIFY_SHOP || 'dev-shop.myshopify.com';
          console.log('[TradeUp] Dev mode: Using fallback shop:', shop);
        }

        // Save to localStorage (wrapped in try-catch for iframe restrictions)
        if (shop) {
          try {
            localStorage.setItem('tradeup_shop', shop);
          } catch (e) {
            console.warn('[TradeUp] localStorage write blocked:', e);
          }
        }

        // Get initial session token if embedded (with timeout to prevent hanging)
        let sessionToken: string | null = null;
        if (isEmbedded && shop) {
          try {
            // Add 3 second timeout to prevent hanging if App Bridge isn't ready
            const tokenPromise = fetchSessionToken();
            const timeoutPromise = new Promise<null>((resolve) => setTimeout(() => resolve(null), 3000));
            sessionToken = await Promise.race([tokenPromise, timeoutPromise]);
          } catch (e) {
            console.warn('[TradeUp] Session token fetch failed:', e);
          }
        }

        console.log('[TradeUp] Bridge initialized:', { shop, isEmbedded, hasToken: !!sessionToken });

        setState({
          shop,
          isEmbedded,
          isLoading: false,
          sessionToken,
          getSessionToken,
        });
      } catch (error) {
        console.error('[TradeUp] Bridge init failed:', error);
        // Still set loading to false so the app doesn't hang
        setState(prev => ({
          ...prev,
          isLoading: false,
        }));
      }
    };

    init();
  }, [getSessionToken]);

  return state;
}

/**
 * Get API base URL based on environment.
 *
 * For Shopify embedded apps:
 * - Production: Use relative /api path (same origin as frontend)
 * - Development: Use VITE_API_URL for tunnels, or localhost
 *
 * This ensures production builds always use the correct API endpoint
 * regardless of dev .env files being accidentally included.
 */
export function getApiUrl(): string {
  // Production builds should ALWAYS use relative path (same origin)
  // This prevents stale dev tunnel URLs from breaking production
  if (import.meta.env.PROD) {
    return '/api';
  }

  // Development: Use tunnel URL if set, otherwise localhost
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }

  return 'http://localhost:5000/api';
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
  console.log('[TradeUp] createAuthHeaders called for shop:', shop);
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };

  // Try to get session token for embedded auth
  console.log('[TradeUp] Attempting to get session token...');
  const token = await fetchSessionToken();
  console.log('[TradeUp] Session token result:', token ? 'obtained' : 'null');
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Also include shop as header for backwards compatibility
  if (shop) {
    headers['X-Shop-Domain'] = shop;
  }

  console.log('[TradeUp] Headers ready (has auth:', !!token, ')');
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
  console.log('[TradeUp] authFetch called:', { url, shop });
  const headers = await createAuthHeaders(shop);
  console.log('[TradeUp] authFetch headers created');

  // Add shop to URL if not already present
  const urlWithShop = url.includes('?')
    ? url.includes('shop=') ? url : `${url}&shop=${shop}`
    : `${url}?shop=${shop}`;

  console.log('[TradeUp] authFetch fetching:', urlWithShop);
  const response = await fetch(urlWithShop, {
    ...options,
    headers: {
      ...headers,
      ...options.headers,
    },
  });
  console.log('[TradeUp] authFetch response received:', response.status);
  return response;
}
