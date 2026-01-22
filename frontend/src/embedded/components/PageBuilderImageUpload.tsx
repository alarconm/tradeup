/**
 * PageBuilderImageUpload - LP-009
 *
 * Image upload component for loyalty page builder sections.
 * Supports:
 * - Drag and drop upload
 * - File picker
 * - URL input
 * - Image preview
 * - Size/format validation
 * - Recently uploaded images gallery
 */

import { useState, useCallback, useEffect } from 'react';
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
  Spinner,
  Icon,
  Card,
  Modal,
} from '@shopify/polaris';
import { DeleteIcon, ImageIcon } from '@shopify/polaris-icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

type ImageSourceTab = 'upload' | 'url' | 'library';

interface UploadedImage {
  url: string;
  filename: string;
  size: number;
  uploaded_at: string;
}

interface PageBuilderImageUploadProps {
  /** Current image URL */
  value: string;
  /** Callback when image changes */
  onChange: (url: string) => void;
  /** Shop domain for API calls */
  shop: string | null;
  /** Label for the field */
  label?: string;
  /** Help text */
  helpText?: string;
  /** Recommended dimensions */
  recommendedSize?: string;
  /** Whether this is for a background image (shows overlay options) */
  isBackground?: boolean;
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

// Allowed extensions
const ALLOWED_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'];
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB

// API functions
async function uploadImage(shop: string | null, file: File): Promise<{ success: boolean; url: string; filename: string; size: number }> {
  const formData = new FormData();
  formData.append('file', file);

  const url = `${getApiUrl()}/page-builder/images/upload`;
  const urlWithShop = `${url}?shop=${shop}`;

  // Get auth headers (without Content-Type as FormData sets it)
  const token = await getSessionToken();
  const headers: HeadersInit = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  if (shop) {
    headers['X-Shop-Domain'] = shop;
  }

  const response = await fetch(urlWithShop, {
    method: 'POST',
    headers,
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Upload failed');
  }

  return response.json();
}

async function fetchUploadedImages(shop: string | null): Promise<{ success: boolean; images: UploadedImage[] }> {
  const response = await authFetch(`${getApiUrl()}/page-builder/images/list`, shop);
  if (!response.ok) {
    throw new Error('Failed to fetch images');
  }
  return response.json();
}

async function deleteImage(shop: string | null, filename: string): Promise<{ success: boolean }> {
  const response = await authFetch(`${getApiUrl()}/page-builder/images/delete/${filename}`, shop, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Delete failed');
  }
  return response.json();
}

// Helper to get session token
async function getSessionToken(): Promise<string | null> {
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const shopify = (window as any).shopify;
    if (shopify?.idToken) {
      return await shopify.idToken();
    }
  } catch {
    // Ignore errors
  }
  return null;
}

export function PageBuilderImageUpload({
  value,
  onChange,
  shop,
  label = 'Image',
  helpText,
  recommendedSize = '1200 x 600 pixels',
  isBackground = false,
}: PageBuilderImageUploadProps) {
  const [activeTab, setActiveTab] = useState<ImageSourceTab>('upload');
  const [urlInput, setUrlInput] = useState('');
  const [urlError, setUrlError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [showLibrary, setShowLibrary] = useState(false);

  const queryClient = useQueryClient();

  // Fetch uploaded images
  const { data: imagesData, isLoading: imagesLoading } = useQuery({
    queryKey: ['page-builder-images', shop],
    queryFn: () => fetchUploadedImages(shop),
    enabled: !!shop && (activeTab === 'library' || showLibrary),
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (filename: string) => deleteImage(shop, filename),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['page-builder-images', shop] });
    },
  });

  // Validate file
  const validateFile = useCallback((file: File): string | null => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!ext || !ALLOWED_EXTENSIONS.includes(ext)) {
      return `Invalid file type. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`;
    }
    if (file.size > MAX_FILE_SIZE) {
      return `File too large. Maximum size is ${MAX_FILE_SIZE / (1024 * 1024)}MB`;
    }
    return null;
  }, []);

  // Handle file drop/upload
  const handleDrop = useCallback(
    async (_dropFiles: File[], acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) {
        setUploadError('Please upload an image file (PNG, JPG, GIF, WebP, SVG)');
        return;
      }

      const file = acceptedFiles[0];

      // Validate
      const error = validateFile(file);
      if (error) {
        setUploadError(error);
        return;
      }

      // Upload
      setIsUploading(true);
      setUploadError(null);

      try {
        const result = await uploadImage(shop, file);
        onChange(result.url);
        queryClient.invalidateQueries({ queryKey: ['page-builder-images', shop] });
      } catch (err) {
        setUploadError(err instanceof Error ? err.message : 'Upload failed');
      } finally {
        setIsUploading(false);
      }
    },
    [shop, onChange, validateFile, queryClient]
  );

  // Handle URL input
  const handleUrlApply = useCallback(() => {
    if (!urlInput.trim()) {
      setUrlError('Please enter a URL');
      return;
    }

    // Basic URL validation
    try {
      new URL(urlInput);
      onChange(urlInput.trim());
      setUrlError(null);
      setUrlInput('');
    } catch {
      setUrlError('Please enter a valid URL');
    }
  }, [urlInput, onChange]);

  // Handle library selection
  const handleLibrarySelect = useCallback((url: string) => {
    onChange(url);
    setShowLibrary(false);
  }, [onChange]);

  // Handle image removal
  const handleRemove = useCallback(() => {
    onChange('');
  }, [onChange]);

  // Format file size
  const formatSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

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
        disabled={isUploading}
      >
        {isUploading ? (
          <Box padding="800">
            <BlockStack gap="200" inlineAlign="center">
              <Spinner size="small" />
              <Text as="p" tone="subdued">Uploading...</Text>
            </BlockStack>
          </Box>
        ) : (
          <DropZone.FileUpload
            actionTitle="Add image"
            actionHint="or drop file to upload"
          />
        )}
      </DropZone>

      <Text as="p" variant="bodySm" tone="subdued">
        Recommended size: {recommendedSize}. Max file size: 5MB.
        Supported formats: PNG, JPG, GIF, WebP, SVG.
      </Text>
    </BlockStack>
  );

  // Render URL tab
  const renderUrlTab = () => (
    <BlockStack gap="400">
      <TextField
        label="Image URL"
        value={urlInput}
        onChange={setUrlInput}
        placeholder="https://example.com/image.png"
        error={urlError || undefined}
        autoComplete="off"
        connectedRight={
          <Button onClick={handleUrlApply}>Apply</Button>
        }
      />

      <Text as="p" variant="bodySm" tone="subdued">
        Enter a direct link to an image. Make sure the URL is publicly accessible.
      </Text>
    </BlockStack>
  );

  // Render library tab
  const renderLibraryTab = () => (
    <BlockStack gap="400">
      {imagesLoading ? (
        <Box padding="400">
          <BlockStack gap="200" inlineAlign="center">
            <Spinner size="small" />
            <Text as="p" tone="subdued">Loading images...</Text>
          </BlockStack>
        </Box>
      ) : imagesData?.images?.length === 0 ? (
        <Box padding="400" background="bg-surface-secondary" borderRadius="200">
          <BlockStack gap="200" inlineAlign="center">
            <Icon source={ImageIcon} tone="subdued" />
            <Text as="p" tone="subdued" alignment="center">
              No images uploaded yet. Upload an image to see it here.
            </Text>
          </BlockStack>
        </Box>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: '12px',
          }}
        >
          {imagesData?.images?.map((img) => (
            <button
              key={img.filename}
              type="button"
              onClick={() => handleLibrarySelect(img.url)}
              style={{
                padding: '8px',
                border: value === img.url ? '2px solid #008060' : '2px solid #e1e3e5',
                borderRadius: '8px',
                backgroundColor: value === img.url ? '#f0fdf4' : 'white',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                position: 'relative',
              }}
            >
              <BlockStack gap="100">
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
                    alt={img.filename}
                    style={{
                      width: '100%',
                      height: '100%',
                      objectFit: 'cover',
                    }}
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none';
                    }}
                  />
                </div>
                <Text as="span" variant="bodySm" tone="subdued">
                  {formatSize(img.size)}
                </Text>
              </BlockStack>
            </button>
          ))}
        </div>
      )}
    </BlockStack>
  );

  return (
    <BlockStack gap="300">
      <Text as="p" variant="bodyMd" fontWeight="semibold">{label}</Text>

      {/* Current image preview */}
      {value && (
        <Card>
          <BlockStack gap="300">
            <div
              style={{
                width: '100%',
                maxHeight: '200px',
                borderRadius: '8px',
                overflow: 'hidden',
                backgroundColor: '#f6f6f7',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <img
                src={value}
                alt="Preview"
                style={{
                  maxWidth: '100%',
                  maxHeight: '200px',
                  objectFit: 'contain',
                }}
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = 'none';
                }}
              />
            </div>
            <InlineStack gap="200">
              <Button size="slim" onClick={handleRemove} tone="critical" icon={DeleteIcon}>
                Remove
              </Button>
              <Button size="slim" onClick={() => setShowLibrary(true)}>
                Change
              </Button>
            </InlineStack>
            {value.length > 60 && (
              <Text as="p" variant="bodySm" tone="subdued">
                {value.substring(0, 60)}...
              </Text>
            )}
          </BlockStack>
        </Card>
      )}

      {/* Upload interface (when no image selected) */}
      {!value && (
        <>
          {/* Tab bar */}
          <Box borderBlockEndWidth="025" borderColor="border">
            <InlineStack gap="0">
              <TabButton
                label="Upload"
                active={activeTab === 'upload'}
                onClick={() => setActiveTab('upload')}
              />
              <TabButton
                label="URL"
                active={activeTab === 'url'}
                onClick={() => setActiveTab('url')}
              />
              <TabButton
                label="Library"
                active={activeTab === 'library'}
                onClick={() => setActiveTab('library')}
              />
            </InlineStack>
          </Box>

          {/* Tab content */}
          <Box paddingBlockStart="200">
            {activeTab === 'upload' && renderUploadTab()}
            {activeTab === 'url' && renderUrlTab()}
            {activeTab === 'library' && renderLibraryTab()}
          </Box>
        </>
      )}

      {helpText && (
        <Text as="p" variant="bodySm" tone="subdued">{helpText}</Text>
      )}

      {/* Full library modal */}
      <Modal
        open={showLibrary}
        onClose={() => setShowLibrary(false)}
        title="Select Image"
        size="large"
      >
        <Modal.Section>
          <BlockStack gap="400">
            {/* Upload option in modal */}
            <DropZone
              accept="image/*"
              type="image"
              onDrop={handleDrop}
              allowMultiple={false}
              disabled={isUploading}
            >
              {isUploading ? (
                <Box padding="400">
                  <BlockStack gap="200" inlineAlign="center">
                    <Spinner size="small" />
                    <Text as="p" tone="subdued">Uploading...</Text>
                  </BlockStack>
                </Box>
              ) : (
                <DropZone.FileUpload
                  actionTitle="Upload new image"
                  actionHint="or drop file to upload"
                />
              )}
            </DropZone>

            {uploadError && (
              <Banner tone="critical" onDismiss={() => setUploadError(null)}>
                {uploadError}
              </Banner>
            )}

            {/* Library grid */}
            {imagesLoading ? (
              <Box padding="400">
                <BlockStack gap="200" inlineAlign="center">
                  <Spinner size="small" />
                  <Text as="p" tone="subdued">Loading images...</Text>
                </BlockStack>
              </Box>
            ) : imagesData?.images?.length === 0 ? (
              <Box padding="400" background="bg-surface-secondary" borderRadius="200">
                <Text as="p" tone="subdued" alignment="center">
                  No images uploaded yet.
                </Text>
              </Box>
            ) : (
              <>
                <Text as="h3" variant="headingSm">Your Images</Text>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(4, 1fr)',
                    gap: '16px',
                  }}
                >
                  {imagesData?.images?.map((img) => (
                    <div
                      key={img.filename}
                      style={{
                        position: 'relative',
                      }}
                    >
                      <button
                        type="button"
                        onClick={() => handleLibrarySelect(img.url)}
                        style={{
                          width: '100%',
                          padding: '8px',
                          border: value === img.url ? '2px solid #008060' : '2px solid #e1e3e5',
                          borderRadius: '8px',
                          backgroundColor: value === img.url ? '#f0fdf4' : 'white',
                          cursor: 'pointer',
                          transition: 'all 0.2s ease',
                        }}
                      >
                        <BlockStack gap="100">
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
                              alt={img.filename}
                              style={{
                                width: '100%',
                                height: '100%',
                                objectFit: 'cover',
                              }}
                            />
                          </div>
                          <Text as="span" variant="bodySm" tone="subdued">
                            {formatSize(img.size)}
                          </Text>
                        </BlockStack>
                      </button>
                      {/* Delete button */}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (confirm('Delete this image?')) {
                            deleteMutation.mutate(img.filename);
                          }
                        }}
                        style={{
                          position: 'absolute',
                          top: '4px',
                          right: '4px',
                          width: '24px',
                          height: '24px',
                          borderRadius: '50%',
                          border: 'none',
                          backgroundColor: 'rgba(0, 0, 0, 0.6)',
                          color: 'white',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '14px',
                        }}
                        title="Delete image"
                      >
                        x
                      </button>
                    </div>
                  ))}
                </div>
              </>
            )}
          </BlockStack>
        </Modal.Section>
      </Modal>
    </BlockStack>
  );
}

export default PageBuilderImageUpload;
