/**
 * Shopify Data Hooks
 *
 * React Query hooks for fetching Shopify store data (collections, vendors, etc.)
 * Used for populating promotion filters and product selectors.
 */
import { useQuery } from '@tanstack/react-query';
import { getApiUrl, authFetch } from './useShopifyBridge';

// Types for Shopify data
interface ShopifyCollection {
  id: string;
  title: string;
  handle: string;
}

interface CollectionsResponse {
  collections: ShopifyCollection[];
  count: number;
}

interface VendorsResponse {
  vendors: string[];
  count: number;
}

interface ProductTypesResponse {
  product_types: string[];
  count: number;
}

interface TagsResponse {
  tags: string[];
  count: number;
  note?: string;
}

/**
 * Fetch collections from Shopify store.
 */
async function fetchCollections(shop: string | null): Promise<CollectionsResponse> {
  if (!shop) throw new Error('Shop not connected');
  const response = await authFetch(`${getApiUrl()}/shopify-data/collections`, shop);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Failed to fetch collections' }));
    throw new Error(error.error || 'Failed to fetch collections');
  }
  return response.json();
}

/**
 * Fetch vendors/brands from Shopify store.
 */
async function fetchVendors(shop: string | null): Promise<VendorsResponse> {
  if (!shop) throw new Error('Shop not connected');
  const response = await authFetch(`${getApiUrl()}/shopify-data/vendors`, shop);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Failed to fetch vendors' }));
    throw new Error(error.error || 'Failed to fetch vendors');
  }
  return response.json();
}

/**
 * Fetch product types from Shopify store.
 */
async function fetchProductTypes(shop: string | null): Promise<ProductTypesResponse> {
  if (!shop) throw new Error('Shop not connected');
  const response = await authFetch(`${getApiUrl()}/shopify-data/product-types`, shop);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Failed to fetch product types' }));
    throw new Error(error.error || 'Failed to fetch product types');
  }
  return response.json();
}

/**
 * Fetch common product tags.
 */
async function fetchTags(shop: string | null): Promise<TagsResponse> {
  if (!shop) throw new Error('Shop not connected');
  const response = await authFetch(`${getApiUrl()}/shopify-data/tags`, shop);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Failed to fetch tags' }));
    throw new Error(error.error || 'Failed to fetch tags');
  }
  return response.json();
}

/**
 * Hook to fetch Shopify collections.
 * Returns collections as options for multi-select pickers.
 */
export function useCollections(shop: string | null) {
  return useQuery({
    queryKey: ['shopify-collections', shop],
    queryFn: () => fetchCollections(shop),
    enabled: !!shop,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes
  });
}

/**
 * Hook to fetch Shopify vendors.
 * Returns vendors as options for multi-select pickers.
 */
export function useVendors(shop: string | null) {
  return useQuery({
    queryKey: ['shopify-vendors', shop],
    queryFn: () => fetchVendors(shop),
    enabled: !!shop,
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });
}

/**
 * Hook to fetch Shopify product types.
 * Returns product types as options for multi-select pickers.
 */
export function useProductTypes(shop: string | null) {
  return useQuery({
    queryKey: ['shopify-product-types', shop],
    queryFn: () => fetchProductTypes(shop),
    enabled: !!shop,
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });
}

/**
 * Hook to fetch common product tags.
 * Returns tags as options for multi-select pickers.
 */
export function useTags(shop: string | null) {
  return useQuery({
    queryKey: ['shopify-tags', shop],
    queryFn: () => fetchTags(shop),
    enabled: !!shop,
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });
}

/**
 * Combined hook to fetch all Shopify data at once.
 * Useful for the promotions page where all filters are needed.
 */
export function useShopifyData(shop: string | null) {
  const collections = useCollections(shop);
  const vendors = useVendors(shop);
  const productTypes = useProductTypes(shop);
  const tags = useTags(shop);

  return {
    collections,
    vendors,
    productTypes,
    tags,
    isLoading: collections.isLoading || vendors.isLoading || productTypes.isLoading || tags.isLoading,
    isError: collections.isError || vendors.isError || productTypes.isError || tags.isError,
  };
}
