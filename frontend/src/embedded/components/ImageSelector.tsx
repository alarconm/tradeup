/**
 * ImageSelector - 3-tab interface for selecting product images
 *
 * Options:
 * 1. Template images (pre-made placeholders)
 * 2. URL input (paste image URL)
 * 3. Upload (drag & drop or file picker)
 */

import { useState, useCallback } from 'react';
import {
  Box,
  Text,
  TextField,
  Button,
  InlineStack,
  BlockStack,
  Thumbnail,
  DropZone,
  Banner,
} from '@shopify/polaris';

type ImageSource = 'template' | 'url' | 'upload';

interface TemplateImage {
  id: string;
  url: string;
  name: string;
}

interface ImageSelectorProps {
  value: string;
  source: ImageSource;
  onChange: (url: string, source: ImageSource) => void;
  templateImages?: TemplateImage[];
  tierSlug?: string;
}

// Tab button component
function TabButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: '8px 16px',
        border: 'none',
        borderBottom: active ? '2px solid #008060' : '2px solid transparent',
        backgroundColor: 'transparent',
        color: active ? '#202223' : '#6d7175',
        fontWeight: active ? 600 : 400,
        cursor: 'pointer',
        transition: 'all 0.2s ease',
      }}
    >
      {label}
    </button>
  );
}

export function ImageSelector({
  value,
  source,
  onChange,
  templateImages = [],
  tierSlug,
}: ImageSelectorProps) {
  const [activeTab, setActiveTab] = useState<ImageSource>(source || 'template');
  const [urlInput, setUrlInput] = useState(source === 'url' ? value : '');
  const [urlError, setUrlError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Handle template image selection
  const handleTemplateSelect = useCallback((url: string) => {
    onChange(url, 'template');
  }, [onChange]);

  // Handle URL input
  const handleUrlChange = useCallback((newValue: string) => {
    setUrlInput(newValue);
    setUrlError(null);
  }, []);

  // Validate and apply URL
  const handleUrlApply = useCallback(() => {
    if (!urlInput.trim()) {
      setUrlError('Please enter a URL');
      return;
    }

    // Basic URL validation
    try {
      new URL(urlInput);
      onChange(urlInput.trim(), 'url');
      setUrlError(null);
    } catch {
      setUrlError('Please enter a valid URL');
    }
  }, [urlInput, onChange]);

  // Handle file drop/upload
  const handleDrop = useCallback(
    (_dropFiles: File[], acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) {
        setUploadError('Please upload an image file (PNG, JPG, GIF, WebP)');
        return;
      }

      const file = acceptedFiles[0];

      // Check file size (max 5MB)
      if (file.size > 5 * 1024 * 1024) {
        setUploadError('Image must be less than 5MB');
        return;
      }

      // Create preview URL
      const reader = new FileReader();
      reader.onload = (e) => {
        const dataUrl = e.target?.result as string;
        onChange(dataUrl, 'upload');
        setUploadError(null);
      };
      reader.onerror = () => {
        setUploadError('Failed to read file');
      };
      reader.readAsDataURL(file);
    },
    [onChange]
  );

  // Render template grid
  const renderTemplateTab = () => (
    <BlockStack gap="400">
      {templateImages.length === 0 ? (
        <Box padding="400" background="bg-surface-secondary" borderRadius="200">
          <Text as="p" tone="subdued" alignment="center">
            No template images available for this template.
          </Text>
        </Box>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: '12px',
          }}
        >
          {templateImages.map((img) => (
            <button
              key={img.id}
              type="button"
              onClick={() => handleTemplateSelect(img.url)}
              style={{
                padding: '8px',
                border: value === img.url ? '2px solid #008060' : '2px solid #e1e3e5',
                borderRadius: '8px',
                backgroundColor: value === img.url ? '#f0fdf4' : 'white',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
              }}
            >
              <BlockStack gap="200">
                <div
                  style={{
                    width: '100%',
                    aspectRatio: '1 / 1',
                    borderRadius: '4px',
                    overflow: 'hidden',
                    backgroundColor: '#f6f6f7',
                  }}
                >
                  <img
                    src={img.url}
                    alt={img.name}
                    style={{
                      width: '100%',
                      height: '100%',
                      objectFit: 'cover',
                    }}
                    onError={(e) => {
                      // Fallback for broken images
                      (e.target as HTMLImageElement).style.display = 'none';
                    }}
                  />
                </div>
                <Text as="span" variant="bodySm" alignment="center">
                  {img.name}
                </Text>
              </BlockStack>
            </button>
          ))}
        </div>
      )}

      {/* Tier-specific suggestion */}
      {tierSlug && (
        <Text as="p" variant="bodySm" tone="subdued">
          Tip: Choose an image that matches your "{tierSlug}" tier theme.
        </Text>
      )}
    </BlockStack>
  );

  // Render URL input tab
  const renderUrlTab = () => (
    <BlockStack gap="400">
      <TextField
        label="Image URL"
        value={urlInput}
        onChange={handleUrlChange}
        placeholder="https://example.com/image.png"
        error={urlError || undefined}
        autoComplete="off"
        connectedRight={
          <Button onClick={handleUrlApply}>Apply</Button>
        }
      />

      {/* Preview */}
      {source === 'url' && value && (
        <Box padding="400" background="bg-surface-secondary" borderRadius="200">
          <InlineStack gap="400" align="start">
            <Thumbnail source={value} alt="Preview" size="large" />
            <BlockStack gap="100">
              <Text as="span" variant="bodyMd" fontWeight="semibold">
                Image loaded
              </Text>
              <Text as="span" variant="bodySm" tone="subdued">
                {value.length > 50 ? value.substring(0, 50) + '...' : value}
              </Text>
            </BlockStack>
          </InlineStack>
        </Box>
      )}

      <Text as="p" variant="bodySm" tone="subdued">
        Enter a direct link to an image. Make sure the URL ends in .png, .jpg, .gif, or .webp.
      </Text>
    </BlockStack>
  );

  // Render upload tab
  const renderUploadTab = () => (
    <BlockStack gap="400">
      {uploadError && (
        <Banner tone="critical" onDismiss={() => setUploadError(null)}>
          {uploadError}
        </Banner>
      )}

      <DropZone
        accept="image/*"
        type="image"
        onDrop={handleDrop}
        allowMultiple={false}
      >
        <DropZone.FileUpload
          actionTitle="Add image"
          actionHint="or drop file to upload"
        />
      </DropZone>

      {/* Preview */}
      {source === 'upload' && value && (
        <Box padding="400" background="bg-surface-secondary" borderRadius="200">
          <InlineStack gap="400" align="center">
            <Thumbnail source={value} alt="Uploaded" size="large" />
            <BlockStack gap="100">
              <Text as="span" variant="bodyMd" fontWeight="semibold">
                Image uploaded
              </Text>
              <Button
                variant="plain"
                tone="critical"
                onClick={() => onChange('', 'upload')}
              >
                Remove
              </Button>
            </BlockStack>
          </InlineStack>
        </Box>
      )}

      <Text as="p" variant="bodySm" tone="subdued">
        Recommended size: 1200 x 1200 pixels. Max file size: 5MB.
      </Text>
    </BlockStack>
  );

  return (
    <BlockStack gap="400">
      {/* Tab bar */}
      <Box borderBlockEndWidth="025" borderColor="border">
        <InlineStack gap="0">
          <TabButton
            label="Templates"
            active={activeTab === 'template'}
            onClick={() => setActiveTab('template')}
          />
          <TabButton
            label="URL"
            active={activeTab === 'url'}
            onClick={() => setActiveTab('url')}
          />
          <TabButton
            label="Upload"
            active={activeTab === 'upload'}
            onClick={() => setActiveTab('upload')}
          />
        </InlineStack>
      </Box>

      {/* Tab content */}
      <Box paddingBlockStart="200">
        {activeTab === 'template' && renderTemplateTab()}
        {activeTab === 'url' && renderUrlTab()}
        {activeTab === 'upload' && renderUploadTab()}
      </Box>
    </BlockStack>
  );
}
