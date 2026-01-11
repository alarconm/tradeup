/**
 * ProductPreviewCard - WYSIWYG preview of a membership product
 *
 * Shows exactly what the product will look like in Shopify,
 * with live updates as the user edits.
 */

import { Box, Text, InlineStack, BlockStack, Thumbnail, Badge } from '@shopify/polaris';

interface ProductPreviewCardProps {
  title: string;
  description: string;
  imageUrl: string;
  monthlyPrice: number;
  yearlyPrice?: number | null;
  tierName: string;
  isDraft?: boolean;
  compact?: boolean;
}

export function ProductPreviewCard({
  title,
  description,
  imageUrl,
  monthlyPrice,
  yearlyPrice,
  tierName,
  isDraft = true,
  compact = false,
}: ProductPreviewCardProps) {
  // Strip HTML for plain text preview
  const plainDescription = description
    .replace(/<[^>]*>/g, '')
    .replace(/&nbsp;/g, ' ')
    .trim();

  // Truncate description for compact view
  const displayDescription = compact && plainDescription.length > 100
    ? plainDescription.substring(0, 100) + '...'
    : plainDescription;

  // Format price
  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(price);
  };

  // Calculate yearly savings percentage
  const yearlySavings = yearlyPrice
    ? Math.round((1 - yearlyPrice / (monthlyPrice * 12)) * 100)
    : 0;

  if (compact) {
    return (
      <Box
        padding="400"
        borderRadius="200"
        borderWidth="025"
        borderColor="border"
        background="bg-surface"
      >
        <InlineStack gap="400" align="start" blockAlign="start">
          <div style={{ flexShrink: 0 }}>
            <Thumbnail
              source={imageUrl || 'https://cdn.shopify.com/s/files/1/0533/2089/files/placeholder-images-image_large.png'}
              alt={title}
              size="medium"
            />
          </div>
          <BlockStack gap="200">
            <InlineStack gap="200" align="start">
              <Text as="h3" variant="headingSm" fontWeight="semibold">
                {title || `${tierName} Membership`}
              </Text>
              {isDraft && (
                <Badge tone="warning">Draft</Badge>
              )}
            </InlineStack>
            <Text as="p" variant="bodySm" tone="subdued">
              {displayDescription || 'No description'}
            </Text>
            <InlineStack gap="200">
              <Text as="span" variant="bodyMd" fontWeight="semibold">
                {formatPrice(monthlyPrice)}/mo
              </Text>
              {yearlyPrice && (
                <Text as="span" variant="bodySm" tone="subdued">
                  or {formatPrice(yearlyPrice)}/yr
                  {yearlySavings > 0 && ` (Save ${yearlySavings}%)`}
                </Text>
              )}
            </InlineStack>
          </BlockStack>
        </InlineStack>
      </Box>
    );
  }

  // Full card view
  return (
    <Box
      borderRadius="300"
      borderWidth="025"
      borderColor="border"
      background="bg-surface"
      shadow="100"
    >
      {/* Product Image */}
      <div
        style={{
          width: '100%',
          aspectRatio: '1 / 1',
          backgroundColor: '#f6f6f7',
          borderTopLeftRadius: '12px',
          borderTopRightRadius: '12px',
          overflow: 'hidden',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={title}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
            }}
          />
        ) : (
          <div
            style={{
              width: '100%',
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: '#e4e5e7',
            }}
          >
            <Text as="span" tone="subdued">No image</Text>
          </div>
        )}
      </div>

      {/* Product Info */}
      <Box padding="400">
        <BlockStack gap="300">
          {/* Title and Draft Badge */}
          <InlineStack gap="200" align="start" wrap={false}>
            <div style={{ flex: 1 }}>
              <Text as="h3" variant="headingMd" fontWeight="semibold">
                {title || `${tierName} Membership`}
              </Text>
            </div>
            {isDraft && (
              <Badge tone="warning">Draft</Badge>
            )}
          </InlineStack>

          {/* Description */}
          <Text as="p" variant="bodyMd" tone="subdued">
            {displayDescription || 'No description provided.'}
          </Text>

          {/* Pricing */}
          <Box paddingBlockStart="200">
            <BlockStack gap="100">
              <InlineStack gap="200" align="start">
                <Text as="span" variant="headingLg" fontWeight="bold">
                  {formatPrice(monthlyPrice)}
                </Text>
                <Text as="span" variant="bodyMd" tone="subdued">
                  /month
                </Text>
              </InlineStack>

              {yearlyPrice && (
                <InlineStack gap="200" align="start">
                  <Text as="span" variant="bodyMd">
                    {formatPrice(yearlyPrice)}/year
                  </Text>
                  {yearlySavings > 0 && (
                    <Badge tone="success">{`Save ${yearlySavings}%`}</Badge>
                  )}
                </InlineStack>
              )}
            </BlockStack>
          </Box>

          {/* Tier indicator */}
          <Box paddingBlockStart="200">
            <InlineStack gap="200">
              <div
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: '#008060',
                }}
              />
              <Text as="span" variant="bodySm" tone="subdued">
                {tierName} tier
              </Text>
            </InlineStack>
          </Box>
        </BlockStack>
      </Box>
    </Box>
  );
}

// Grid wrapper for displaying multiple product cards
interface ProductPreviewGridProps {
  children: React.ReactNode;
  columns?: 2 | 3 | 4;
}

export function ProductPreviewGrid({ children, columns = 3 }: ProductPreviewGridProps) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${columns}, 1fr)`,
        gap: '20px',
      }}
    >
      {children}
    </div>
  );
}
