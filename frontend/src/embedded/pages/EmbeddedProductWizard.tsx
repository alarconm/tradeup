/**
 * EmbeddedProductWizard - Guided membership product setup
 *
 * 4-step wizard:
 * 1. Welcome & Preview - Show what products will be created
 * 2. Choose Template - Select a design template
 * 3. Customize - Edit titles, descriptions, images, prices
 * 4. Review & Publish - Final review, create as draft or active
 */
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Page,
  Layout,
  Card,
  Text,
  BlockStack,
  InlineStack,
  Button,
  Banner,
  Spinner,
  Box,
  TextField,
  Checkbox,
  Modal,
  Divider,
  EmptyState,
  Badge,
} from '@shopify/polaris';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';
import { WizardProgress, PRODUCT_WIZARD_STEPS } from '../components/WizardProgress';
import { ProductPreviewCard, ProductPreviewGrid } from '../components/ProductPreviewCard';
import { ImageSelector } from '../components/ImageSelector';

interface EmbeddedProductWizardProps {
  shop: string | null;
}

interface WizardStatus {
  success: boolean;
  has_tiers: boolean;
  tier_count: number;
  has_draft: boolean;
  draft_step: number;
  draft_template: string | null;
  has_products: boolean;
  products_count: number;
  products_are_draft: boolean;
}

interface ProductTemplate {
  id: string;
  name: string;
  description: string;
  preview_image: string;
}

interface ProductDraft {
  tier_id: number;
  tier_name: string;
  tier_slug: string;
  title: string;
  description: string;
  image_url: string;
  image_source: 'template' | 'url' | 'upload';
  monthly_price: number;
  yearly_price: number | null;
  customized: boolean;
}

interface TemplateImage {
  id: string;
  url: string;
  name: string;
}

// API functions
async function fetchWizardStatus(shop: string | null): Promise<WizardStatus> {
  const response = await authFetch(`${getApiUrl()}/products/wizard/status`, shop);
  if (!response.ok) throw new Error('Failed to fetch wizard status');
  return response.json();
}

async function fetchTemplates(shop: string | null): Promise<{ success: boolean; templates: ProductTemplate[] }> {
  const response = await authFetch(`${getApiUrl()}/products/wizard/templates`, shop);
  if (!response.ok) throw new Error('Failed to fetch templates');
  return response.json();
}

async function previewTemplate(shop: string | null, templateId: string): Promise<{
  success: boolean;
  template: ProductTemplate;
  products: ProductDraft[];
}> {
  const response = await authFetch(`${getApiUrl()}/products/wizard/templates/${templateId}/preview`, shop);
  if (!response.ok) throw new Error('Failed to preview template');
  return response.json();
}

async function fetchDraft(shop: string | null): Promise<{
  success: boolean;
  has_draft: boolean;
  step?: number;
  template?: string;
  products?: ProductDraft[];
  publish_as_active?: boolean;
}> {
  const response = await authFetch(`${getApiUrl()}/products/wizard/draft`, shop);
  if (!response.ok) throw new Error('Failed to fetch draft');
  return response.json();
}

async function saveDraft(
  shop: string | null,
  data: { step: number; template: string | null; products: ProductDraft[]; publish_as_active: boolean }
): Promise<{ success: boolean }> {
  const response = await authFetch(`${getApiUrl()}/products/wizard/save`, shop, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to save draft');
  return response.json();
}

async function createProducts(
  shop: string | null,
  data: { products: ProductDraft[]; publish_as_active: boolean }
): Promise<{
  success: boolean;
  products: Array<{ tier_id: number; product_id: string; status: string }>;
  errors: Array<{ tier: string; error: string }>;
  message: string;
}> {
  const response = await authFetch(`${getApiUrl()}/products/wizard/create`, shop, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to create products');
  return response.json();
}

async function resetWizard(shop: string | null): Promise<{ success: boolean }> {
  const response = await authFetch(`${getApiUrl()}/products/wizard/reset`, shop, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to reset wizard');
  return response.json();
}

export function EmbeddedProductWizard({ shop }: EmbeddedProductWizardProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Wizard state
  const [step, setStep] = useState(0); // 0 = welcome, 1 = template, 2 = customize, 3 = publish
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [products, setProducts] = useState<ProductDraft[]>([]);
  const [publishActive, setPublishActive] = useState(false);
  const [editingProduct, setEditingProduct] = useState<number | null>(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showResetModal, setShowResetModal] = useState(false);

  // Query wizard status
  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ['wizard-status', shop],
    queryFn: () => fetchWizardStatus(shop),
    enabled: !!shop,
  });

  // Query templates
  const { data: templatesData, isLoading: templatesLoading } = useQuery({
    queryKey: ['wizard-templates', shop],
    queryFn: () => fetchTemplates(shop),
    enabled: !!shop && step >= 1,
  });

  // Query saved draft
  const { data: draftData } = useQuery({
    queryKey: ['wizard-draft', shop],
    queryFn: () => fetchDraft(shop),
    enabled: !!shop,
  });

  // Preview template mutation
  const previewMutation = useMutation({
    mutationFn: (templateId: string) => previewTemplate(shop, templateId),
    onSuccess: (data) => {
      setProducts(data.products);
    },
  });

  // Save draft mutation
  const saveMutation = useMutation({
    mutationFn: (data: { step: number; template: string | null; products: ProductDraft[]; publish_as_active: boolean }) =>
      saveDraft(shop, data),
  });

  // Create products mutation
  const createMutation = useMutation({
    mutationFn: (data: { products: ProductDraft[]; publish_as_active: boolean }) =>
      createProducts(shop, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wizard-status'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
    },
  });

  // Reset wizard mutation
  const resetMutation = useMutation({
    mutationFn: () => resetWizard(shop),
    onSuccess: () => {
      setStep(0);
      setSelectedTemplate(null);
      setProducts([]);
      setPublishActive(false);
      queryClient.invalidateQueries({ queryKey: ['wizard-status'] });
      queryClient.invalidateQueries({ queryKey: ['wizard-draft'] });
    },
  });

  // Load saved draft on mount
  useEffect(() => {
    if (draftData?.has_draft) {
      setStep(draftData.step || 1);
      setSelectedTemplate(draftData.template || null);
      setProducts(draftData.products || []);
      setPublishActive(draftData.publish_as_active || false);
    }
  }, [draftData]);

  // Auto-save when step changes
  useEffect(() => {
    if (step > 0 && selectedTemplate) {
      saveMutation.mutate({
        step,
        template: selectedTemplate,
        products,
        publish_as_active: publishActive,
      });
    }
  }, [step]);

  // Handle template selection
  const handleTemplateSelect = useCallback((templateId: string) => {
    setSelectedTemplate(templateId);
    previewMutation.mutate(templateId);
  }, [previewMutation]);

  // Handle step navigation
  const handleStepClick = useCallback((stepIndex: number) => {
    if (stepIndex < step) {
      setStep(stepIndex);
    }
  }, [step]);

  // Handle next step
  const handleNext = useCallback(() => {
    if (step < 3) {
      setStep(step + 1);
    }
  }, [step]);

  // Handle previous step
  const handleBack = useCallback(() => {
    if (step > 0) {
      setStep(step - 1);
    }
  }, [step]);

  // Handle product edit
  const handleProductChange = useCallback((index: number, field: keyof ProductDraft, value: string | number | null) => {
    setProducts((prev) => {
      const updated = [...prev];
      updated[index] = {
        ...updated[index],
        [field]: value,
        customized: true,
      };
      return updated;
    });
  }, []);

  // Handle create products
  const handleCreate = useCallback(() => {
    setShowConfirmModal(false);
    createMutation.mutate({
      products,
      publish_as_active: publishActive,
    });
  }, [products, publishActive, createMutation]);

  // Loading state
  if (statusLoading) {
    return (
      <Page title="Membership Products">
        <Layout>
          <Layout.Section>
            <Card>
              <Box padding="800">
                <InlineStack align="center">
                  <Spinner size="large" />
                </InlineStack>
              </Box>
            </Card>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  // No tiers - redirect to tiers page
  if (!status?.has_tiers) {
    return (
      <Page
        title="Membership Products"
        backAction={{ content: 'Settings', onAction: () => navigate('/app/settings') }}
      >
        <Layout>
          <Layout.Section>
            <Card>
              <EmptyState
                heading="Create membership tiers first"
                image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                action={{
                  content: 'Set Up Tiers',
                  onAction: () => navigate('/app/tiers'),
                }}
              >
                <p>You need to create membership tiers before setting up products.</p>
              </EmptyState>
            </Card>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  // Products already exist
  if (status?.has_products && step === 0 && !draftData?.has_draft) {
    return (
      <Page
        title="Membership Products"
        backAction={{ content: 'Settings', onAction: () => navigate('/app/settings') }}
      >
        <Layout>
          <Layout.Section>
            {status.products_are_draft && (
              <Banner
                title="Your products are in draft mode"
                tone="warning"
                action={{
                  content: 'Publish Products',
                  onAction: () => navigate('/app/settings'),
                }}
              >
                <p>Customers can't see draft products. Publish them when you're ready.</p>
              </Banner>
            )}
          </Layout.Section>
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingMd">
                  Products Created
                </Text>
                <Text as="p" tone="subdued">
                  You have {status.products_count} membership product{status.products_count !== 1 ? 's' : ''} set up.
                  {status.products_are_draft ? ' They are currently in draft mode.' : ''}
                </Text>
                <InlineStack gap="300">
                  <Button
                    variant="primary"
                    onClick={() => {
                      setShowResetModal(true);
                    }}
                  >
                    Start Over
                  </Button>
                  <Button onClick={() => navigate('/app/settings')}>
                    Back to Settings
                  </Button>
                </InlineStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>

        {/* Reset confirmation modal */}
        <Modal
          open={showResetModal}
          onClose={() => setShowResetModal(false)}
          title="Start Over?"
          primaryAction={{
            content: 'Yes, Start Over',
            destructive: true,
            onAction: () => {
              resetMutation.mutate();
              setShowResetModal(false);
            },
          }}
          secondaryActions={[
            {
              content: 'Cancel',
              onAction: () => setShowResetModal(false),
            },
          ]}
        >
          <Modal.Section>
            <Text as="p">
              This will let you run through the wizard again. Your existing Shopify products will not be deleted.
            </Text>
          </Modal.Section>
        </Modal>
      </Page>
    );
  }

  // Render step content
  const renderStepContent = () => {
    switch (step) {
      case 0: // Welcome
        return (
          <Card>
            <BlockStack gap="500">
              <BlockStack gap="200">
                <Text as="h2" variant="headingLg">
                  Let's Set Up Your Membership Products
                </Text>
                <Text as="p" tone="subdued">
                  We'll create products for each of your {status?.tier_count} membership tiers.
                  Customers can purchase these to join your loyalty program.
                </Text>
              </BlockStack>

              <Box
                padding="400"
                background="bg-surface-secondary"
                borderRadius="200"
              >
                <BlockStack gap="300">
                  <Text as="h3" variant="headingMd">
                    What you'll do:
                  </Text>
                  <BlockStack gap="200">
                    <InlineStack gap="200" align="start">
                      <Badge tone="info">1</Badge>
                      <Text as="span">Choose a design template</Text>
                    </InlineStack>
                    <InlineStack gap="200" align="start">
                      <Badge tone="info">2</Badge>
                      <Text as="span">Customize titles, descriptions & images</Text>
                    </InlineStack>
                    <InlineStack gap="200" align="start">
                      <Badge tone="info">3</Badge>
                      <Text as="span">Review and create your products</Text>
                    </InlineStack>
                  </BlockStack>
                </BlockStack>
              </Box>

              <Banner tone="info">
                <p>
                  Products are created as <strong>drafts</strong> by default so you can review them
                  before making them visible to customers.
                </p>
              </Banner>

              <InlineStack gap="300" align="end">
                <Button onClick={() => navigate('/app/settings')}>
                  Cancel
                </Button>
                <Button variant="primary" onClick={handleNext}>
                  Get Started
                </Button>
              </InlineStack>
            </BlockStack>
          </Card>
        );

      case 1: // Choose Template
        return (
          <Card>
            <BlockStack gap="500">
              <BlockStack gap="200">
                <Text as="h2" variant="headingLg">
                  Choose a Template
                </Text>
                <Text as="p" tone="subdued">
                  Pick a design that matches your store's style. You can customize everything in the next step.
                </Text>
              </BlockStack>

              {templatesLoading ? (
                <Box padding="800">
                  <InlineStack align="center">
                    <Spinner size="large" />
                  </InlineStack>
                </Box>
              ) : (
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(2, 1fr)',
                    gap: '16px',
                  }}
                >
                  {templatesData?.templates.map((template) => (
                    <button
                      key={template.id}
                      type="button"
                      onClick={() => handleTemplateSelect(template.id)}
                      style={{
                        padding: '16px',
                        border: selectedTemplate === template.id
                          ? '2px solid #008060'
                          : '2px solid #e1e3e5',
                        borderRadius: '12px',
                        backgroundColor: selectedTemplate === template.id
                          ? '#f0fdf4'
                          : 'white',
                        cursor: 'pointer',
                        textAlign: 'left',
                        transition: 'all 0.2s ease',
                      }}
                    >
                      <BlockStack gap="300">
                        <div
                          style={{
                            width: '100%',
                            aspectRatio: '4 / 3',
                            borderRadius: '8px',
                            overflow: 'hidden',
                            backgroundColor: '#f6f6f7',
                          }}
                        >
                          <img
                            src={template.preview_image}
                            alt={template.name}
                            style={{
                              width: '100%',
                              height: '100%',
                              objectFit: 'cover',
                            }}
                            onError={(e) => {
                              (e.target as HTMLImageElement).src =
                                'https://cdn.shopify.com/s/files/1/0533/2089/files/placeholder-images-image_large.png';
                            }}
                          />
                        </div>
                        <BlockStack gap="100">
                          <InlineStack gap="200" align="start">
                            <Text as="h3" variant="headingMd">
                              {template.name}
                            </Text>
                            {selectedTemplate === template.id && (
                              <Badge tone="success">Selected</Badge>
                            )}
                          </InlineStack>
                          <Text as="p" variant="bodySm" tone="subdued">
                            {template.description}
                          </Text>
                        </BlockStack>
                      </BlockStack>
                    </button>
                  ))}
                </div>
              )}

              {previewMutation.isPending && (
                <Box padding="400">
                  <InlineStack gap="200" align="center">
                    <Spinner size="small" />
                    <Text as="span" tone="subdued">Generating preview...</Text>
                  </InlineStack>
                </Box>
              )}

              <Divider />

              <InlineStack gap="300" align="end">
                <Button onClick={handleBack}>
                  Back
                </Button>
                <Button
                  variant="primary"
                  onClick={handleNext}
                  disabled={!selectedTemplate || previewMutation.isPending}
                >
                  Continue
                </Button>
              </InlineStack>
            </BlockStack>
          </Card>
        );

      case 2: // Customize
        return (
          <BlockStack gap="400">
            <Card>
              <BlockStack gap="400">
                <BlockStack gap="200">
                  <Text as="h2" variant="headingLg">
                    Customize Your Products
                  </Text>
                  <Text as="p" tone="subdued">
                    Click on any product to edit its details. Changes are saved automatically.
                  </Text>
                </BlockStack>
              </BlockStack>
            </Card>

            {products.map((product, index) => (
              <Card key={product.tier_id}>
                <BlockStack gap="400">
                  <InlineStack gap="400" align="space-between" blockAlign="start">
                    <BlockStack gap="100">
                      <Text as="h3" variant="headingMd">
                        {product.tier_name} Tier
                      </Text>
                      {product.customized && (
                        <Badge tone="info">Customized</Badge>
                      )}
                    </BlockStack>
                    <Button
                      variant={editingProduct === index ? 'primary' : 'plain'}
                      onClick={() => setEditingProduct(editingProduct === index ? null : index)}
                    >
                      {editingProduct === index ? 'Done Editing' : 'Edit'}
                    </Button>
                  </InlineStack>

                  {editingProduct === index ? (
                    <BlockStack gap="400">
                      <TextField
                        label="Product Title"
                        value={product.title}
                        onChange={(value) => handleProductChange(index, 'title', value)}
                        autoComplete="off"
                      />
                      <TextField
                        label="Description"
                        value={product.description.replace(/<[^>]*>/g, '')}
                        onChange={(value) => handleProductChange(index, 'description', value)}
                        multiline={3}
                        autoComplete="off"
                      />
                      <InlineStack gap="400">
                        <div style={{ flex: 1 }}>
                          <TextField
                            label="Monthly Price"
                            type="number"
                            value={String(product.monthly_price)}
                            onChange={(value) => handleProductChange(index, 'monthly_price', parseFloat(value) || 0)}
                            prefix="$"
                            autoComplete="off"
                          />
                        </div>
                        <div style={{ flex: 1 }}>
                          <TextField
                            label="Yearly Price (optional)"
                            type="number"
                            value={product.yearly_price ? String(product.yearly_price) : ''}
                            onChange={(value) => handleProductChange(index, 'yearly_price', value ? parseFloat(value) : null)}
                            prefix="$"
                            placeholder="Leave empty for no yearly option"
                            autoComplete="off"
                          />
                        </div>
                      </InlineStack>
                      <Box>
                        <Text as="p" variant="bodyMd" fontWeight="semibold">
                          Product Image
                        </Text>
                        <Box paddingBlockStart="200">
                          <ImageSelector
                            value={product.image_url}
                            source={product.image_source}
                            onChange={(url, source) => {
                              handleProductChange(index, 'image_url', url);
                              handleProductChange(index, 'image_source', source);
                            }}
                            templateImages={[
                              { id: 'template', url: product.image_url, name: 'Template Default' },
                            ]}
                            tierSlug={product.tier_slug}
                          />
                        </Box>
                      </Box>
                    </BlockStack>
                  ) : (
                    <ProductPreviewCard
                      title={product.title}
                      description={product.description}
                      imageUrl={product.image_url}
                      monthlyPrice={product.monthly_price}
                      yearlyPrice={product.yearly_price}
                      tierName={product.tier_name}
                      isDraft
                      compact
                    />
                  )}
                </BlockStack>
              </Card>
            ))}

            <Card>
              <InlineStack gap="300" align="end">
                <Button onClick={handleBack}>
                  Back
                </Button>
                <Button variant="primary" onClick={handleNext}>
                  Review & Publish
                </Button>
              </InlineStack>
            </Card>
          </BlockStack>
        );

      case 3: // Review & Publish
        return (
          <BlockStack gap="400">
            <Card>
              <BlockStack gap="400">
                <BlockStack gap="200">
                  <Text as="h2" variant="headingLg">
                    Review Your Products
                  </Text>
                  <Text as="p" tone="subdued">
                    Here's what will be created in your Shopify store.
                  </Text>
                </BlockStack>
              </BlockStack>
            </Card>

            <ProductPreviewGrid columns={products.length <= 2 ? 2 : 3}>
              {products.map((product) => (
                <ProductPreviewCard
                  key={product.tier_id}
                  title={product.title}
                  description={product.description}
                  imageUrl={product.image_url}
                  monthlyPrice={product.monthly_price}
                  yearlyPrice={product.yearly_price}
                  tierName={product.tier_name}
                  isDraft={!publishActive}
                />
              ))}
            </ProductPreviewGrid>

            <Card>
              <BlockStack gap="400">
                <Checkbox
                  label="Publish products immediately"
                  helpText="If unchecked, products will be created as drafts so you can review them in Shopify first."
                  checked={publishActive}
                  onChange={setPublishActive}
                />

                {!publishActive && (
                  <Banner tone="info">
                    <p>
                      Products will be created as <strong>drafts</strong>. You'll see a reminder on your
                      dashboard to publish them when you're ready.
                    </p>
                  </Banner>
                )}

                {createMutation.isError && (
                  <Banner tone="critical">
                    <p>Failed to create products. Please try again.</p>
                  </Banner>
                )}

                {createMutation.isSuccess && (
                  <Banner tone="success">
                    <p>
                      {createMutation.data?.message || 'Products created successfully!'}
                    </p>
                  </Banner>
                )}

                <Divider />

                <InlineStack gap="300" align="end">
                  <Button onClick={handleBack} disabled={createMutation.isPending}>
                    Back
                  </Button>
                  <Button
                    variant="primary"
                    onClick={() => setShowConfirmModal(true)}
                    loading={createMutation.isPending}
                    disabled={createMutation.isSuccess}
                  >
                    {publishActive ? 'Create & Publish' : 'Create as Drafts'}
                  </Button>
                </InlineStack>
              </BlockStack>
            </Card>
          </BlockStack>
        );

      default:
        return null;
    }
  };

  return (
    <Page
      title="Product Setup Wizard"
      backAction={{
        content: 'Settings',
        onAction: () => navigate('/app/settings'),
      }}
      secondaryActions={
        step > 0
          ? [
              {
                content: 'Save & Exit',
                onAction: () => {
                  saveMutation.mutate({
                    step,
                    template: selectedTemplate,
                    products,
                    publish_as_active: publishActive,
                  });
                  navigate('/app/settings');
                },
              },
            ]
          : undefined
      }
    >
      <Layout>
        {step > 0 && (
          <Layout.Section>
            <WizardProgress
              steps={PRODUCT_WIZARD_STEPS}
              currentStep={step}
              onStepClick={handleStepClick}
            />
          </Layout.Section>
        )}

        <Layout.Section>
          {renderStepContent()}
        </Layout.Section>
      </Layout>

      {/* Confirm creation modal */}
      <Modal
        open={showConfirmModal}
        onClose={() => setShowConfirmModal(false)}
        title={publishActive ? 'Create & Publish Products?' : 'Create Draft Products?'}
        primaryAction={{
          content: publishActive ? 'Create & Publish' : 'Create as Drafts',
          onAction: handleCreate,
        }}
        secondaryActions={[
          {
            content: 'Cancel',
            onAction: () => setShowConfirmModal(false),
          },
        ]}
      >
        <Modal.Section>
          <BlockStack gap="300">
            <Text as="p">
              You're about to create {products.length} product{products.length !== 1 ? 's' : ''} in your Shopify store.
            </Text>
            {publishActive ? (
              <Banner tone="warning">
                <p>Products will be immediately visible to customers.</p>
              </Banner>
            ) : (
              <Banner tone="info">
                <p>Products will be created as drafts. You can publish them later from your Shopify admin.</p>
              </Banner>
            )}
          </BlockStack>
        </Modal.Section>
      </Modal>
    </Page>
  );
}
