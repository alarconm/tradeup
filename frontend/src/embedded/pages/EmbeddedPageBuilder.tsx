/**
 * Loyalty Page Builder
 *
 * Visual editor for customizing the loyalty program landing page.
 */

import React, { useState } from 'react';
import {
  Page,
  Layout,
  Card,
  Text,
  Button,
  BlockStack,
  InlineStack,
  Select,
  TextField,
  Checkbox,
  Banner,
  Spinner,
  Badge,
  Tabs,
  Box,
  Divider,
  Icon,
  Modal,
  FormLayout,
  ColorPicker,
  hsbToRgb,
  rgbToHsb,
} from '@shopify/polaris';
import {
  ViewIcon,
  EditIcon,
  DragHandleIcon,
  CheckIcon,
} from '@shopify/polaris-icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface EmbeddedPageBuilderProps {
  shop: string | null;
}

interface Section {
  id: string;
  type: string;
  enabled: boolean;
  order: number;
  settings: Record<string, any>;
}

interface Template {
  id: string;
  name: string;
  description: string;
  colors: Record<string, string>;
}

interface PageConfig {
  enabled: boolean;
  template: string;
  sections: Section[];
  colors: Record<string, string>;
  custom_css: string;
  meta: {
    title?: string;
    description?: string;
  };
  last_updated: string | null;
}

async function fetchPageConfig(shop: string | null): Promise<{ config: PageConfig }> {
  const response = await authFetch(`${getApiUrl()}/page-builder/config`, shop);
  if (!response.ok) throw new Error('Failed to fetch page config');
  return response.json();
}

async function fetchTemplates(shop: string | null): Promise<{ templates: Template[] }> {
  const response = await authFetch(`${getApiUrl()}/page-builder/templates`, shop);
  if (!response.ok) throw new Error('Failed to fetch templates');
  return response.json();
}

const SECTION_LABELS: Record<string, string> = {
  hero: 'Hero Banner',
  how_it_works: 'How It Works',
  tier_comparison: 'Membership Tiers',
  rewards_catalog: 'Rewards Catalog',
  earning_rules: 'Ways to Earn',
  faq: 'FAQ Section',
  referral_banner: 'Referral Program',
};

export function EmbeddedPageBuilder({ shop }: EmbeddedPageBuilderProps) {
  const [selectedTab, setSelectedTab] = useState(0);
  const [showPreview, setShowPreview] = useState(false);
  const [editingSection, setEditingSection] = useState<Section | null>(null);

  const queryClient = useQueryClient();

  const { data: configData, isLoading: loadingConfig } = useQuery({
    queryKey: ['page-builder-config', shop],
    queryFn: () => fetchPageConfig(shop),
    enabled: !!shop,
  });

  const { data: templatesData } = useQuery({
    queryKey: ['page-builder-templates', shop],
    queryFn: () => fetchTemplates(shop),
    enabled: !!shop,
  });

  const updateConfigMutation = useMutation({
    mutationFn: async (config: Partial<PageConfig>) => {
      const response = await authFetch(`${getApiUrl()}/page-builder/config`, shop, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (!response.ok) throw new Error('Failed to update config');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['page-builder-config', shop] });
    },
  });

  const applyTemplateMutation = useMutation({
    mutationFn: async (templateId: string) => {
      const response = await authFetch(`${getApiUrl()}/page-builder/templates/${templateId}/apply`, shop, {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Failed to apply template');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['page-builder-config', shop] });
    },
  });

  const toggleSectionMutation = useMutation({
    mutationFn: async ({ sectionId, enabled }: { sectionId: string; enabled: boolean }) => {
      const response = await authFetch(`${getApiUrl()}/page-builder/sections/${sectionId}/toggle`, shop, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      });
      if (!response.ok) throw new Error('Failed to toggle section');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['page-builder-config', shop] });
    },
  });

  const config = configData?.config;
  const templates = templatesData?.templates || [];

  const tabs = [
    { id: 'sections', content: 'Sections', panelID: 'sections-panel' },
    { id: 'design', content: 'Design', panelID: 'design-panel' },
    { id: 'settings', content: 'Settings', panelID: 'settings-panel' },
  ];

  if (loadingConfig) {
    return (
      <Page title="Loyalty Page Builder">
        <Card>
          <BlockStack gap="200" inlineAlign="center">
            <Spinner size="large" />
            <Text as="p">Loading page builder...</Text>
          </BlockStack>
        </Card>
      </Page>
    );
  }

  const sections = config?.sections || [];
  const enabledSections = sections.filter((s) => s.enabled).sort((a, b) => a.order - b.order);
  const disabledSections = sections.filter((s) => !s.enabled);

  return (
    <Page
      title="Loyalty Page Builder"
      subtitle="Customize your rewards program landing page"
      primaryAction={{
        content: 'Preview Page',
        icon: ViewIcon,
        onAction: () => setShowPreview(true),
      }}
      secondaryActions={[
        {
          content: 'View Live Page',
          url: `/apps/rewards`,
          external: true,
        },
      ]}
    >
      <Layout>
        <Layout.Section>
          <Card>
            <Tabs tabs={tabs} selected={selectedTab} onSelect={setSelectedTab}>
              {/* Sections Tab */}
              {selectedTab === 0 && (
                <BlockStack gap="400">
                  <Text as="h3" variant="headingMd">Active Sections</Text>
                  <Text as="p" variant="bodyMd" tone="subdued">
                    Drag to reorder. Toggle to enable/disable sections.
                  </Text>

                  <BlockStack gap="200">
                    {enabledSections.map((section) => (
                      <Card key={section.id}>
                        <InlineStack align="space-between" blockAlign="center">
                          <InlineStack gap="300" blockAlign="center">
                            <Icon source={DragHandleIcon} />
                            <BlockStack gap="100">
                              <Text as="span" variant="bodyMd" fontWeight="semibold">
                                {SECTION_LABELS[section.type] || section.type}
                              </Text>
                              <Text as="span" variant="bodySm" tone="subdued">
                                {section.type}
                              </Text>
                            </BlockStack>
                          </InlineStack>
                          <InlineStack gap="200">
                            <Button
                              size="slim"
                              onClick={() => setEditingSection(section)}
                            >
                              Edit
                            </Button>
                            <Button
                              size="slim"
                              tone="critical"
                              onClick={() => toggleSectionMutation.mutate({ sectionId: section.id, enabled: false })}
                            >
                              Disable
                            </Button>
                          </InlineStack>
                        </InlineStack>
                      </Card>
                    ))}
                  </BlockStack>

                  {disabledSections.length > 0 && (
                    <>
                      <Divider />
                      <Text as="h3" variant="headingMd">Available Sections</Text>
                      <BlockStack gap="200">
                        {disabledSections.map((section) => (
                          <Card key={section.id}>
                            <InlineStack align="space-between" blockAlign="center">
                              <BlockStack gap="100">
                                <Text as="span" variant="bodyMd" fontWeight="semibold">
                                  {SECTION_LABELS[section.type] || section.type}
                                </Text>
                              </BlockStack>
                              <Button
                                size="slim"
                                onClick={() => toggleSectionMutation.mutate({ sectionId: section.id, enabled: true })}
                              >
                                Enable
                              </Button>
                            </InlineStack>
                          </Card>
                        ))}
                      </BlockStack>
                    </>
                  )}
                </BlockStack>
              )}

              {/* Design Tab */}
              {selectedTab === 1 && (
                <BlockStack gap="400">
                  <Text as="h3" variant="headingMd">Choose a Template</Text>
                  <InlineStack gap="300" wrap>
                    {templates.map((template) => (
                      <Card key={template.id}>
                        <BlockStack gap="200">
                          <Text as="span" variant="headingSm">{template.name}</Text>
                          <Text as="p" variant="bodySm" tone="subdued">{template.description}</Text>
                          <InlineStack gap="100">
                            {Object.entries(template.colors).slice(0, 3).map(([key, color]) => (
                              <div
                                key={key}
                                style={{
                                  width: 24,
                                  height: 24,
                                  borderRadius: 4,
                                  background: color,
                                  border: '1px solid #ddd',
                                }}
                              />
                            ))}
                          </InlineStack>
                          <Button
                            size="slim"
                            variant={config?.template === template.id ? 'primary' : undefined}
                            onClick={() => applyTemplateMutation.mutate(template.id)}
                            loading={applyTemplateMutation.isPending}
                          >
                            {config?.template === template.id ? 'Applied' : 'Apply'}
                          </Button>
                        </BlockStack>
                      </Card>
                    ))}
                  </InlineStack>

                  <Divider />

                  <Text as="h3" variant="headingMd">Colors</Text>
                  <FormLayout>
                    <FormLayout.Group>
                      <TextField
                        label="Primary Color"
                        value={config?.colors?.primary || '#e85d27'}
                        onChange={(v) => updateConfigMutation.mutate({
                          colors: { ...config?.colors, primary: v }
                        })}
                        autoComplete="off"
                      />
                      <TextField
                        label="Accent Color"
                        value={config?.colors?.accent || '#ffd700'}
                        onChange={(v) => updateConfigMutation.mutate({
                          colors: { ...config?.colors, accent: v }
                        })}
                        autoComplete="off"
                      />
                    </FormLayout.Group>
                  </FormLayout>
                </BlockStack>
              )}

              {/* Settings Tab */}
              {selectedTab === 2 && (
                <BlockStack gap="400">
                  <Text as="h3" variant="headingMd">Page Settings</Text>
                  <FormLayout>
                    <Checkbox
                      label="Enable loyalty page"
                      checked={config?.enabled !== false}
                      onChange={(v) => updateConfigMutation.mutate({ enabled: v })}
                    />

                    <TextField
                      label="Page Title"
                      value={config?.meta?.title || 'Rewards Program'}
                      onChange={(v) => updateConfigMutation.mutate({
                        meta: { ...config?.meta, title: v }
                      })}
                      autoComplete="off"
                    />

                    <TextField
                      label="Meta Description"
                      value={config?.meta?.description || ''}
                      onChange={(v) => updateConfigMutation.mutate({
                        meta: { ...config?.meta, description: v }
                      })}
                      multiline={2}
                      autoComplete="off"
                    />

                    <TextField
                      label="Custom CSS"
                      value={config?.custom_css || ''}
                      onChange={(v) => updateConfigMutation.mutate({ custom_css: v })}
                      multiline={4}
                      monospaced
                      autoComplete="off"
                      helpText="Add custom CSS to further customize your page"
                    />
                  </FormLayout>
                </BlockStack>
              )}
            </Tabs>
          </Card>
        </Layout.Section>

        <Layout.Section variant="oneThird">
          <Card>
            <BlockStack gap="300">
              <Text as="h3" variant="headingMd">Quick Actions</Text>
              <Button
                fullWidth
                onClick={() => setShowPreview(true)}
                icon={ViewIcon}
              >
                Preview Page
              </Button>
              <Button
                fullWidth
                url="/apps/rewards"
                external
              >
                View Live Page
              </Button>
            </BlockStack>
          </Card>

          <Card>
            <BlockStack gap="300">
              <Text as="h3" variant="headingMd">Tips</Text>
              <BlockStack gap="100">
                <Text as="p" variant="bodyMd">Keep your hero section compelling and action-oriented.</Text>
                <Text as="p" variant="bodyMd">Show 3-4 steps in "How It Works" for clarity.</Text>
                <Text as="p" variant="bodyMd">Highlight your best rewards prominently.</Text>
                <Text as="p" variant="bodyMd">Include an FAQ to reduce support questions.</Text>
              </BlockStack>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>

      {/* Preview Modal */}
      <Modal
        open={showPreview}
        onClose={() => setShowPreview(false)}
        title="Page Preview"
        size="large"
      >
        <Modal.Section>
          <iframe
            src={`${getApiUrl()}/page-builder/preview`}
            style={{ width: '100%', height: '600px', border: 'none' }}
            title="Page Preview"
          />
        </Modal.Section>
      </Modal>

      {/* Edit Section Modal */}
      {editingSection && (
        <Modal
          open={!!editingSection}
          onClose={() => setEditingSection(null)}
          title={`Edit ${SECTION_LABELS[editingSection.type] || editingSection.type}`}
        >
          <Modal.Section>
            <FormLayout>
              {editingSection.type === 'hero' && (
                <>
                  <TextField
                    label="Title"
                    value={editingSection.settings.title || ''}
                    onChange={() => {}}
                    autoComplete="off"
                  />
                  <TextField
                    label="Subtitle"
                    value={editingSection.settings.subtitle || ''}
                    onChange={() => {}}
                    autoComplete="off"
                  />
                  <TextField
                    label="Button Text"
                    value={editingSection.settings.cta_text || ''}
                    onChange={() => {}}
                    autoComplete="off"
                  />
                </>
              )}
              <Text as="p" variant="bodySm" tone="subdued">
                Section editing is in preview mode. Full editing coming soon.
              </Text>
            </FormLayout>
          </Modal.Section>
        </Modal>
      )}
    </Page>
  );
}

export default EmbeddedPageBuilder;
