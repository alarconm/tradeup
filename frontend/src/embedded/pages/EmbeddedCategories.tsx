/**
 * TradeUp Categories - Shopify Embedded Version
 *
 * Manage trade-in categories with full CRUD operations.
 * Uses Shopify Polaris for consistent UX.
 */
import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Page,
  Layout,
  Card,
  Text,
  InlineStack,
  BlockStack,
  Box,
  Button,
  TextField,
  Banner,
  Spinner,
  EmptyState,
  Modal,
  ResourceList,
  ResourceItem,
  InlineGrid,
} from '@shopify/polaris';
import { PlusIcon } from '@shopify/polaris-icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface CategoriesProps {
  shop: string | null;
}

interface TradeInCategory {
  id: string;
  name: string;
  icon: string;
}

// Common emoji icons for trade-in categories
const EMOJI_OPTIONS = [
  { emoji: '🏈', label: 'Sports' },
  { emoji: '⚡', label: 'Pokemon' },
  { emoji: '🔮', label: 'Magic' },
  { emoji: '🌀', label: 'Riftbound' },
  { emoji: '🎴', label: 'TCG' },
  { emoji: '📦', label: 'Other' },
  { emoji: '⭐', label: 'Premium' },
  { emoji: '💎', label: 'Graded' },
  { emoji: '🃏', label: 'Cards' },
  { emoji: '🎮', label: 'Gaming' },
  { emoji: '🎯', label: 'Target' },
  { emoji: '🏆', label: 'Trophy' },
  { emoji: '🎁', label: 'Special' },
  { emoji: '🔥', label: 'Hot' },
  { emoji: '❄️', label: 'Cold' },
  { emoji: '🌟', label: 'Star' },
];

async function fetchCategories(shop: string | null): Promise<{ categories: TradeInCategory[] }> {
  const response = await authFetch(`${getApiUrl()}/trade-ins/categories`, shop);
  if (!response.ok) throw new Error('Failed to fetch categories');
  return response.json();
}

async function createCategory(
  shop: string | null,
  data: { name: string; icon: string }
): Promise<TradeInCategory> {
  const response = await authFetch(`${getApiUrl()}/trade-ins/categories`, shop, {
    method: 'POST',
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to create category');
  return response.json();
}

async function updateCategory(
  shop: string | null,
  id: string,
  data: { name: string; icon: string }
): Promise<TradeInCategory> {
  const response = await authFetch(`${getApiUrl()}/trade-ins/categories/${id}`, shop, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to update category');
  return response.json();
}

async function deleteCategory(shop: string | null, id: string): Promise<void> {
  const response = await authFetch(`${getApiUrl()}/trade-ins/categories/${id}`, shop, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to delete category');
}

export function EmbeddedCategories({ shop }: CategoriesProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showModal, setShowModal] = useState(false);
  const [editingCategory, setEditingCategory] = useState<TradeInCategory | null>(null);
  const [formName, setFormName] = useState('');
  const [formIcon, setFormIcon] = useState('📦');
  const [error, setError] = useState('');
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const { data, isLoading, error: fetchError } = useQuery({
    queryKey: ['categories', shop],
    queryFn: () => fetchCategories(shop),
    enabled: !!shop,
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: { name: string; icon: string }) => createCategory(shop, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] });
      closeModal();
    },
    onError: (err: Error) => setError(err.message),
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name: string; icon: string } }) =>
      updateCategory(shop, id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] });
      closeModal();
    },
    onError: (err: Error) => setError(err.message),
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteCategory(shop, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] });
      setDeleteConfirmId(null);
    },
    onError: (err: Error) => setError(err.message),
  });

  const openNewModal = useCallback(() => {
    setFormName('');
    setFormIcon('📦');
    setEditingCategory(null);
    setError('');
    setShowModal(true);
  }, []);

  const openEditModal = useCallback((category: TradeInCategory) => {
    setFormName(category.name);
    setFormIcon(category.icon);
    setEditingCategory(category);
    setError('');
    setShowModal(true);
  }, []);

  const closeModal = useCallback(() => {
    setShowModal(false);
    setEditingCategory(null);
    setFormName('');
    setFormIcon('📦');
    setError('');
  }, []);

  const handleSubmit = useCallback(() => {
    if (!formName.trim()) {
      setError('Category name is required');
      return;
    }

    const data = { name: formName.trim(), icon: formIcon };

    if (editingCategory) {
      updateMutation.mutate({ id: editingCategory.id, data });
    } else {
      createMutation.mutate(data);
    }
  }, [formName, formIcon, editingCategory, createMutation, updateMutation]);

  const handleDelete = useCallback(
    (id: string) => {
      deleteMutation.mutate(id);
    },
    [deleteMutation]
  );

  if (!shop) {
    return (
      <Page title="Categories">
        <Banner tone="warning">
          <p>No shop connected. Please install the app from the Shopify App Store.</p>
        </Banner>
      </Page>
    );
  }

  const categories = data?.categories || [];
  const isSaving = createMutation.isPending || updateMutation.isPending;

  return (
    <Page
      title="Trade-In Categories"
      subtitle="Organize trade-ins by product type"
      backAction={{ content: 'Trade-Ins', onAction: () => navigate('/app/trade-ins') }}
      primaryAction={{
        content: 'Add Category',
        icon: PlusIcon,
        onAction: openNewModal,
      }}
    >
      <Layout>
        {fetchError && (
          <Layout.Section>
            <Banner tone="critical">
              <p>Failed to load categories. Please try refreshing the page.</p>
            </Banner>
          </Layout.Section>
        )}

        {error && (
          <Layout.Section>
            <Banner tone="critical" onDismiss={() => setError('')}>
              <p>{error}</p>
            </Banner>
          </Layout.Section>
        )}

        <Layout.Section>
          {isLoading ? (
            <Card>
              <Box padding="1600">
                <InlineStack align="center">
                  <Spinner size="large" />
                </InlineStack>
              </Box>
            </Card>
          ) : categories.length > 0 ? (
            <Card padding="0">
              <ResourceList
                resourceName={{ singular: 'category', plural: 'categories' }}
                items={categories.filter(c => c && c.id != null)}
                renderItem={(category) => (
                  <ResourceItem
                    id={category.id}
                    media={
                      <Box
                        padding="200"
                        background="bg-surface-secondary"
                        borderRadius="200"
                      >
                        <Text as="span" variant="headingLg">
                          {category.icon}
                        </Text>
                      </Box>
                    }
                    shortcutActions={[
                      {
                        content: 'Edit',
                        onAction: () => openEditModal(category),
                      },
                      {
                        content: 'Delete',
                        onAction: () => setDeleteConfirmId(category.id),
                      },
                    ]}
                    onClick={() => openEditModal(category)}
                  >
                    <Text as="h3" variant="bodyMd" fontWeight="bold">
                      {category.name}
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      ID: {category.id}
                    </Text>
                  </ResourceItem>
                )}
              />
            </Card>
          ) : (
            <Card>
              <EmptyState
                heading="No categories created yet"
                image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                action={{
                  content: 'Add Category',
                  icon: PlusIcon,
                  onAction: openNewModal,
                }}
              >
                <p>
                  Create categories to organize your trade-in submissions by product type.
                </p>
              </EmptyState>
            </Card>
          )}
        </Layout.Section>
      </Layout>

      {/* Create/Edit Modal */}
      <Modal
        open={showModal}
        onClose={closeModal}
        title={editingCategory ? 'Edit Category' : 'New Category'}
        primaryAction={{
          content: editingCategory ? 'Save Changes' : 'Create Category',
          onAction: handleSubmit,
          loading: isSaving,
          disabled: !formName.trim(),
        }}
        secondaryActions={[{ content: 'Cancel', onAction: closeModal }]}
      >
        <Modal.Section>
          <BlockStack gap="400">
            <TextField
              label="Category Name"
              value={formName}
              onChange={setFormName}
              placeholder="e.g., Pokemon, Sports Cards"
              autoComplete="off"
              requiredIndicator
              autoFocus
            />

            <BlockStack gap="200">
              <Text as="span" variant="bodyMd" fontWeight="semibold">
                Icon
              </Text>
              <InlineGrid columns={{ xs: 4, sm: 8 }} gap="200">
                {EMOJI_OPTIONS.map(({ emoji, label }) => (
                  <Button
                    key={emoji}
                    variant={formIcon === emoji ? 'primary' : 'secondary'}
                    onClick={() => setFormIcon(emoji)}
                    accessibilityLabel={label}
                  >
                    {emoji}
                  </Button>
                ))}
              </InlineGrid>
              <TextField
                label="Custom icon"
                labelHidden
                value={formIcon}
                onChange={setFormIcon}
                placeholder="Or type a custom emoji"
                autoComplete="off"
                maxLength={2}
              />
            </BlockStack>

            <Card background="bg-surface-secondary">
              <BlockStack gap="200">
                <Text as="span" variant="bodySm" tone="subdued">
                  Preview
                </Text>
                <InlineStack gap="300" blockAlign="center">
                  <Box padding="200" background="bg-surface" borderRadius="200">
                    <Text as="span" variant="headingLg">
                      {formIcon}
                    </Text>
                  </Box>
                  <Text as="span" variant="bodyMd" fontWeight="semibold">
                    {formName || 'Category Name'}
                  </Text>
                </InlineStack>
              </BlockStack>
            </Card>
          </BlockStack>
        </Modal.Section>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        open={deleteConfirmId !== null}
        onClose={() => setDeleteConfirmId(null)}
        title="Delete Category?"
        primaryAction={{
          content: 'Delete',
          destructive: true,
          onAction: () => deleteConfirmId && handleDelete(deleteConfirmId),
          loading: deleteMutation.isPending,
        }}
        secondaryActions={[
          { content: 'Cancel', onAction: () => setDeleteConfirmId(null) },
        ]}
      >
        <Modal.Section>
          <Text as="p">
            Are you sure you want to delete this category? Trade-ins using this category will be
            set to "Other".
          </Text>
        </Modal.Section>
      </Modal>
    </Page>
  );
}
