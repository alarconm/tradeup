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
        }

        // 2. Then check URL params (works for direct navigation)
        if (!shop) {
          const urlParams = new URLSearchParams(window.location.search);
          const shopParam = urlParams.get('shop');
          if (shopParam) {
            shop = normalizeShop(shopParam);
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
              // Format is typically "admin.shopify.com/store/shop-name" or similar
              const match = decoded.match(/([a-zA-Z0-9-]+)\.myshopify\.com/) ||
                            decoded.match(/store\/([a-zA-Z0-9-]+)/);
              if (match) {
                shop = match[0].includes('.myshopify.com') ? match[0] : `${match[1]}.myshopify.com`;
              }
            } catch {
              // Host param decode failed - continue to other methods
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
                    break;
                  }
                }
              } catch {
                // Session token decode failed - continue trying
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
            }
          } catch {
            // localStorage blocked in iframe - continue without cached shop
          }
        }

        // Development fallback - use a test shop for local dev
        if (!shop && import.meta.env.DEV) {
          shop = import.meta.env.VITE_SHOPIFY_SHOP || 'dev-shop.myshopify.com';
        }

        // Save to localStorage (wrapped in try-catch for iframe restrictions)
        if (shop) {
          try {
            localStorage.setItem('tradeup_shop', shop);
          } catch {
            // localStorage blocked in iframe - skip caching
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
          } catch {
            // Session token fetch failed - continue without token
          }
        }

        setState({
          shop,
          isEmbedded,
          isLoading: false,
          sessionToken,
          getSessionToken,
        });
      } catch {
        // Bridge init failed - set loading to false so the app doesn't hang
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
 * XMLHttpRequest-based fetch to bypass Shopify App Bridge fetch interception.
 * App Bridge 4.x intercepts the global fetch() and can cause hangs when calling
 * custom backend APIs. XMLHttpRequest is not intercepted.
 */
function xhrFetch(url: string, options: RequestInit = {}): Promise<Response> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const method = options.method || 'GET';

    xhr.open(method, url, true);

    // Set headers
    const headers = options.headers as Record<string, string> || {};
    Object.keys(headers).forEach((key) => {
      xhr.setRequestHeader(key, headers[key]);
    });

    // Set timeout (10 seconds)
    xhr.timeout = 10000;

    xhr.onload = () => {
      const response = new Response(xhr.responseText, {
        status: xhr.status,
        statusText: xhr.statusText,
        headers: new Headers(
          xhr.getAllResponseHeaders()
            .split('\r\n')
            .filter(Boolean)
            .reduce((acc, line) => {
              const [key, ...vals] = line.split(': ');
              acc[key] = vals.join(': ');
              return acc;
            }, {} as Record<string, string>)
        ),
      });
      resolve(response);
    };

    xhr.onerror = () => {
      reject(new Error('Network error'));
    };

    xhr.ontimeout = () => {
      reject(new Error('Request timeout'));
    };

    // Send request
    if (options.body) {
      xhr.send(options.body as string);
    } else {
      xhr.send();
    }
  });
}

/**
 * Authenticated fetch wrapper for API requests.
 * Uses XMLHttpRequest to bypass Shopify App Bridge fetch interception.
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

  // Use absolute URL to avoid any relative URL resolution issues
  const baseUrl = window.location.origin;
  const absoluteUrl = urlWithShop.startsWith('/') ? `${baseUrl}${urlWithShop}` : urlWithShop;

  return xhrFetch(absoluteUrl, {
    ...options,
    headers: {
      ...headers,
      ...options.headers as Record<string, string>,
    },
  });
}
