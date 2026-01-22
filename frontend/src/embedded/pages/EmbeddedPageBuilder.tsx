/**
 * Loyalty Page Builder - LP-004, LP-005
 *
 * Visual drag-and-drop editor for customizing the loyalty program landing page.
 * Features:
 * - Section list with add/remove/reorder (drag-and-drop)
 * - Click to edit section content
 * - Real-time preview panel
 * - Save and publish buttons
 * - Undo/redo functionality
 * - Pre-built templates (Classic, Modern, Gamified) with one-click apply (LP-005)
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  Page,
  Layout,
  Card,
  Text,
  Button,
  BlockStack,
  InlineStack,
  TextField,
  Checkbox,
  Banner,
  Spinner,
  Badge,
  Tabs,
  Divider,
  Icon,
  Modal,
  FormLayout,
  Box,
  Tooltip,
} from '@shopify/polaris';
import {
  ViewIcon,
  EditIcon,
  DragHandleIcon,
  PlusIcon,
  DeleteIcon,
  UndoIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  CheckCircleIcon,
  AlertCircleIcon,
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

interface PageConfig {
  enabled: boolean;
  sections: Section[];
  colors: {
    primary?: string;
    secondary?: string;
    accent?: string;
    background?: string;
  };
  custom_css: string;
  meta: {
    title?: string;
    description?: string;
  };
}

interface PageData {
  id: number;
  tenant_id: number;
  is_published: boolean;
  published_at: string | null;
  draft_updated_at: string | null;
}

interface ApiResponse {
  success: boolean;
  page: PageData;
  draft_config: PageConfig | null;
  published_config: PageConfig | null;
  has_unsaved_changes: boolean;
}

// History state for undo/redo
interface HistoryState {
  past: PageConfig[];
  present: PageConfig | null;
  future: PageConfig[];
}

// Available section types
const SECTION_TYPES = [
  { type: 'hero', label: 'Hero Banner', description: 'Large banner with title, subtitle, and CTA' },
  { type: 'how_it_works', label: 'How It Works', description: 'Step-by-step explanation' },
  { type: 'tier_comparison', label: 'Membership Tiers', description: 'Compare tier benefits' },
  { type: 'rewards_catalog', label: 'Rewards Catalog', description: 'Display available rewards' },
  { type: 'earning_rules', label: 'Ways to Earn', description: 'Show how to earn points' },
  { type: 'faq', label: 'FAQ Section', description: 'Frequently asked questions' },
  { type: 'referral_banner', label: 'Referral Program', description: 'Promote referral program' },
  { type: 'cta', label: 'Call to Action', description: 'Final CTA with email signup' },
];

const SECTION_LABELS: Record<string, string> = {
  hero: 'Hero Banner',
  how_it_works: 'How It Works',
  tier_comparison: 'Membership Tiers',
  rewards_catalog: 'Rewards Catalog',
  earning_rules: 'Ways to Earn',
  faq: 'FAQ Section',
  referral_banner: 'Referral Program',
  cta: 'Call to Action',
};

// Default settings for new sections
const DEFAULT_SECTION_SETTINGS: Record<string, Record<string, any>> = {
  hero: {
    title: 'Join Our Rewards Program',
    subtitle: 'Earn points on every purchase and unlock exclusive rewards',
    cta_text: 'Join Now',
    cta_link: '/account',
    background_color: '#e85d27',
    text_color: '#ffffff',
  },
  how_it_works: {
    title: 'How It Works',
    steps: [
      { title: 'Sign Up', description: 'Create your free account' },
      { title: 'Earn Points', description: 'Get points on every purchase' },
      { title: 'Redeem Rewards', description: 'Use points for discounts and perks' },
    ],
  },
  tier_comparison: {
    title: 'Membership Tiers',
    show_benefits: true,
  },
  rewards_catalog: {
    title: 'Available Rewards',
    show_points_cost: true,
  },
  earning_rules: {
    title: 'Ways to Earn',
    show_multipliers: true,
  },
  faq: {
    title: 'Frequently Asked Questions',
    items: [
      { question: 'How do I earn points?', answer: 'You earn points on every purchase based on your membership tier.' },
      { question: 'When do my points expire?', answer: 'Points expire 12 months after they are earned.' },
    ],
  },
  referral_banner: {
    title: 'Refer Friends & Earn',
    description: 'Share your referral link and earn bonus points when friends join',
  },
  cta: {
    title: 'Ready to Start Earning?',
    subtitle: 'Join thousands of members earning rewards today',
    button_text: 'Create Account',
    button_url: '/account/register',
  },
};

// Template interface for LP-005
interface Template {
  id: string;
  name: string;
  description: string;
  colors: {
    primary: string;
    secondary: string;
    accent: string;
    background: string;
  };
  preview_image?: string;
  sections: string[];
}

interface TemplatesResponse {
  success: boolean;
  templates: Template[];
}

// API functions using LP-002 endpoints
async function fetchPageData(shop: string | null): Promise<ApiResponse> {
  const response = await authFetch(`${getApiUrl()}/loyalty-page`, shop);
  if (!response.ok) throw new Error('Failed to fetch page data');
  return response.json();
}

// Template API functions for LP-005
async function fetchTemplates(shop: string | null): Promise<TemplatesResponse> {
  const response = await authFetch(`${getApiUrl()}/page-builder/templates`, shop);
  if (!response.ok) throw new Error('Failed to fetch templates');
  return response.json();
}

async function applyTemplate(shop: string | null, templateId: string): Promise<{ success: boolean; config: PageConfig }> {
  const response = await authFetch(`${getApiUrl()}/page-builder/templates/${templateId}/apply`, shop, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to apply template');
  return response.json();
}

async function saveDraft(shop: string | null, config: PageConfig): Promise<ApiResponse> {
  const response = await authFetch(`${getApiUrl()}/loyalty-page`, shop, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!response.ok) throw new Error('Failed to save draft');
  return response.json();
}

async function publishPage(shop: string | null): Promise<ApiResponse> {
  const response = await authFetch(`${getApiUrl()}/loyalty-page/publish`, shop, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to publish page');
  return response.json();
}

async function unpublishPage(shop: string | null): Promise<ApiResponse> {
  const response = await authFetch(`${getApiUrl()}/loyalty-page/unpublish`, shop, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to unpublish page');
  return response.json();
}

async function discardDraft(shop: string | null): Promise<ApiResponse> {
  const response = await authFetch(`${getApiUrl()}/loyalty-page/discard-draft`, shop, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to discard draft');
  return response.json();
}

export function EmbeddedPageBuilder({ shop }: EmbeddedPageBuilderProps) {
  const [selectedTab, setSelectedTab] = useState(0);
  const [showPreview, setShowPreview] = useState(false);
  const [editingSection, setEditingSection] = useState<Section | null>(null);
  const [showAddSection, setShowAddSection] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  // History for undo/redo
  const [history, setHistory] = useState<HistoryState>({
    past: [],
    present: null,
    future: [],
  });

  // Local config state (for editing before save)
  const [localConfig, setLocalConfig] = useState<PageConfig | null>(null);
  const [hasLocalChanges, setHasLocalChanges] = useState(false);

  const queryClient = useQueryClient();

  const { data: pageData, isLoading, error } = useQuery({
    queryKey: ['loyalty-page', shop],
    queryFn: () => fetchPageData(shop),
    enabled: !!shop,
  });

  // Initialize local config from API data
  useEffect(() => {
    if (pageData?.draft_config && !localConfig) {
      setLocalConfig(pageData.draft_config);
      setHistory({
        past: [],
        present: pageData.draft_config,
        future: [],
      });
    }
  }, [pageData?.draft_config, localConfig]);

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: (config: PageConfig) => saveDraft(shop, config),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['loyalty-page', shop] });
      setHasLocalChanges(false);
      setSaveMessage('Draft saved successfully');
      setTimeout(() => setSaveMessage(null), 3000);
    },
    onError: () => {
      setSaveMessage('Failed to save draft');
      setTimeout(() => setSaveMessage(null), 3000);
    },
  });

  // Publish mutation
  const publishMutation = useMutation({
    mutationFn: () => publishPage(shop),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['loyalty-page', shop] });
      setSaveMessage('Page published successfully!');
      setTimeout(() => setSaveMessage(null), 3000);
    },
  });

  // Unpublish mutation
  const unpublishMutation = useMutation({
    mutationFn: () => unpublishPage(shop),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['loyalty-page', shop] });
      setSaveMessage('Page unpublished');
      setTimeout(() => setSaveMessage(null), 3000);
    },
  });

  // Discard mutation
  const discardMutation = useMutation({
    mutationFn: () => discardDraft(shop),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['loyalty-page', shop] });
      if (data.draft_config) {
        setLocalConfig(data.draft_config);
      }
      setHasLocalChanges(false);
      setSaveMessage('Draft discarded');
      setTimeout(() => setSaveMessage(null), 3000);
    },
  });

  // Templates query for LP-005
  const { data: templatesData } = useQuery({
    queryKey: ['page-builder-templates', shop],
    queryFn: () => fetchTemplates(shop),
    enabled: !!shop,
  });

  // Apply template mutation for LP-005
  const applyTemplateMutation = useMutation({
    mutationFn: (templateId: string) => applyTemplate(shop, templateId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['loyalty-page', shop] });
      if (data.config) {
        setLocalConfig(data.config as PageConfig);
        setHistory({
          past: [],
          present: data.config as PageConfig,
          future: [],
        });
      }
      setHasLocalChanges(true);
      setShowTemplates(false);
      setSaveMessage('Template applied successfully! Remember to save your changes.');
      setTimeout(() => setSaveMessage(null), 5000);
    },
    onError: () => {
      setSaveMessage('Failed to apply template');
      setTimeout(() => setSaveMessage(null), 3000);
    },
  });

  // Update config with history tracking
  const updateConfig = useCallback((newConfig: PageConfig) => {
    setHistory((prev) => ({
      past: prev.present ? [...prev.past, prev.present] : prev.past,
      present: newConfig,
      future: [],
    }));
    setLocalConfig(newConfig);
    setHasLocalChanges(true);
  }, []);

  // Undo
  const handleUndo = useCallback(() => {
    setHistory((prev) => {
      if (prev.past.length === 0) return prev;
      const previous = prev.past[prev.past.length - 1];
      const newPast = prev.past.slice(0, prev.past.length - 1);
      setLocalConfig(previous);
      setHasLocalChanges(true);
      return {
        past: newPast,
        present: previous,
        future: prev.present ? [prev.present, ...prev.future] : prev.future,
      };
    });
  }, []);

  // Redo
  const handleRedo = useCallback(() => {
    setHistory((prev) => {
      if (prev.future.length === 0) return prev;
      const next = prev.future[0];
      const newFuture = prev.future.slice(1);
      setLocalConfig(next);
      setHasLocalChanges(true);
      return {
        past: prev.present ? [...prev.past, prev.present] : prev.past,
        present: next,
        future: newFuture,
      };
    });
  }, []);

  // Section management
  const addSection = useCallback((type: string) => {
    if (!localConfig) return;

    const newSection: Section = {
      id: `${type}_${Date.now()}`,
      type,
      enabled: true,
      order: localConfig.sections.length,
      settings: DEFAULT_SECTION_SETTINGS[type] || {},
    };

    updateConfig({
      ...localConfig,
      sections: [...localConfig.sections, newSection],
    });
    setShowAddSection(false);
  }, [localConfig, updateConfig]);

  const removeSection = useCallback((sectionId: string) => {
    if (!localConfig) return;

    const newSections = localConfig.sections
      .filter((s) => s.id !== sectionId)
      .map((s, i) => ({ ...s, order: i }));

    updateConfig({
      ...localConfig,
      sections: newSections,
    });
  }, [localConfig, updateConfig]);

  const toggleSection = useCallback((sectionId: string, enabled: boolean) => {
    if (!localConfig) return;

    const newSections = localConfig.sections.map((s) =>
      s.id === sectionId ? { ...s, enabled } : s
    );

    updateConfig({
      ...localConfig,
      sections: newSections,
    });
  }, [localConfig, updateConfig]);

  const moveSection = useCallback((fromIndex: number, toIndex: number) => {
    if (!localConfig || fromIndex === toIndex) return;

    const sections = [...localConfig.sections];
    const [moved] = sections.splice(fromIndex, 1);
    sections.splice(toIndex, 0, moved);

    const reordered = sections.map((s, i) => ({ ...s, order: i }));

    updateConfig({
      ...localConfig,
      sections: reordered,
    });
  }, [localConfig, updateConfig]);

  const updateSectionSettings = useCallback((sectionId: string, settings: Record<string, any>) => {
    if (!localConfig) return;

    const newSections = localConfig.sections.map((s) =>
      s.id === sectionId ? { ...s, settings: { ...s.settings, ...settings } } : s
    );

    updateConfig({
      ...localConfig,
      sections: newSections,
    });
  }, [localConfig, updateConfig]);

  // Drag and drop handlers
  const handleDragStart = (index: number) => {
    setDraggedIndex(index);
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (draggedIndex !== null && draggedIndex !== index) {
      moveSection(draggedIndex, index);
      setDraggedIndex(index);
    }
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
  };

  // Save handler
  const handleSave = useCallback(() => {
    if (localConfig) {
      saveMutation.mutate(localConfig);
    }
  }, [localConfig, saveMutation]);

  // Loading state
  if (isLoading) {
    return (
      <Page title="Loyalty Page Builder">
        <Card>
          <BlockStack gap="400" inlineAlign="center">
            <Spinner size="large" />
            <Text as="p">Loading page builder...</Text>
          </BlockStack>
        </Card>
      </Page>
    );
  }

  // Error state
  if (error) {
    return (
      <Page title="Loyalty Page Builder">
        <Banner tone="critical">
          <p>Failed to load page builder. Please try again.</p>
        </Banner>
      </Page>
    );
  }

  const config = localConfig;
  const isPublished = pageData?.page?.is_published || false;
  const hasUnsavedChanges = hasLocalChanges || pageData?.has_unsaved_changes || false;

  const enabledSections = config?.sections
    ?.filter((s) => s.enabled)
    ?.sort((a, b) => a.order - b.order) || [];

  const disabledSections = config?.sections?.filter((s) => !s.enabled) || [];

  const tabs = [
    { id: 'templates', content: 'Templates', panelID: 'templates-panel' },
    { id: 'sections', content: 'Sections', panelID: 'sections-panel' },
    { id: 'design', content: 'Design', panelID: 'design-panel' },
    { id: 'settings', content: 'Settings', panelID: 'settings-panel' },
  ];

  return (
    <Page
      title="Loyalty Page Builder"
      subtitle="Customize your rewards program landing page"
      titleMetadata={
        isPublished ? (
          <Badge tone="success">Published</Badge>
        ) : (
          <Badge tone="attention">Draft</Badge>
        )
      }
      primaryAction={{
        content: 'Publish',
        icon: CheckCircleIcon,
        onAction: () => {
          if (hasLocalChanges) {
            saveMutation.mutate(localConfig!);
          }
          publishMutation.mutate();
        },
        loading: publishMutation.isPending,
        disabled: !config,
      }}
      secondaryActions={[
        {
          content: 'Save Draft',
          onAction: handleSave,
          loading: saveMutation.isPending,
          disabled: !hasUnsavedChanges || !config,
        },
        {
          content: 'Preview',
          icon: ViewIcon,
          onAction: () => setShowPreview(true),
        },
        ...(isPublished
          ? [{
              content: 'Unpublish',
              onAction: () => unpublishMutation.mutate(),
              loading: unpublishMutation.isPending,
              destructive: true,
            }]
          : []),
      ]}
    >
      {/* Status banners */}
      {saveMessage && (
        <div style={{ marginBottom: '16px' }}>
          <Banner
            tone={saveMessage.includes('Failed') ? 'critical' : 'success'}
            onDismiss={() => setSaveMessage(null)}
          >
            <p>{saveMessage}</p>
          </Banner>
        </div>
      )}

      {hasUnsavedChanges && (
        <div style={{ marginBottom: '16px' }}>
          <Banner tone="warning">
            <p>You have unsaved changes.</p>
          </Banner>
        </div>
      )}

      <Layout>
        {/* Main content area */}
        <Layout.Section>
          <Card>
            {/* Undo/Redo toolbar */}
            <Box paddingBlockEnd="400">
              <InlineStack gap="200">
                <Tooltip content="Undo (Ctrl+Z)">
                  <Button
                    icon={UndoIcon}
                    onClick={handleUndo}
                    disabled={history.past.length === 0}
                    accessibilityLabel="Undo"
                  />
                </Tooltip>
                <Tooltip content="Redo (Ctrl+Y)">
                  <Button
                    icon={UndoIcon}
                    onClick={handleRedo}
                    disabled={history.future.length === 0}
                    accessibilityLabel="Redo"
                  />
                </Tooltip>
                <div style={{ flex: 1 }} />
                {hasUnsavedChanges && (
                  <Button
                    onClick={() => discardMutation.mutate()}
                    tone="critical"
                    variant="plain"
                    loading={discardMutation.isPending}
                  >
                    Discard Changes
                  </Button>
                )}
              </InlineStack>
            </Box>

            <Divider />

            <Tabs tabs={tabs} selected={selectedTab} onSelect={setSelectedTab}>
              {/* Templates Tab - LP-005 */}
              {selectedTab === 0 && (
                <Box paddingBlockStart="400">
                  <BlockStack gap="400">
                    <Text as="h3" variant="headingMd">Choose a Template</Text>
                    <Text as="p" variant="bodyMd" tone="subdued">
                      Start with a pre-built template and customize it to match your brand.
                      Applying a template will replace your current page configuration.
                    </Text>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
                      {templatesData?.templates?.map((template) => (
                        <Card key={template.id}>
                          <BlockStack gap="300">
                            {/* Template Preview */}
                            <div
                              style={{
                                height: 140,
                                borderRadius: 8,
                                background: `linear-gradient(135deg, ${template.colors.primary} 0%, ${template.colors.secondary} 100%)`,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                position: 'relative',
                                overflow: 'hidden',
                              }}
                            >
                              <div
                                style={{
                                  position: 'absolute',
                                  bottom: 0,
                                  left: 0,
                                  right: 0,
                                  height: '60%',
                                  background: template.colors.background,
                                  borderTopLeftRadius: 12,
                                  borderTopRightRadius: 12,
                                }}
                              />
                              <div
                                style={{
                                  position: 'absolute',
                                  bottom: 20,
                                  left: 20,
                                  right: 20,
                                  display: 'flex',
                                  gap: 8,
                                }}
                              >
                                <div style={{ width: 40, height: 8, borderRadius: 4, background: template.colors.accent }} />
                                <div style={{ width: 60, height: 8, borderRadius: 4, background: template.colors.secondary, opacity: 0.5 }} />
                              </div>
                            </div>

                            {/* Template Info */}
                            <BlockStack gap="200">
                              <InlineStack align="space-between" blockAlign="center">
                                <Text as="h4" variant="headingSm">{template.name}</Text>
                                {(localConfig as any)?.template === template.id && (
                                  <Badge tone="success">Current</Badge>
                                )}
                              </InlineStack>
                              <Text as="p" variant="bodySm" tone="subdued">
                                {template.description}
                              </Text>
                            </BlockStack>

                            {/* Color Preview */}
                            <InlineStack gap="200">
                              {Object.entries(template.colors).map(([name, color]) => (
                                <Tooltip key={name} content={name.charAt(0).toUpperCase() + name.slice(1)}>
                                  <div
                                    style={{
                                      width: 24,
                                      height: 24,
                                      borderRadius: 4,
                                      background: color,
                                      border: color === '#ffffff' || color === '#fafafa' || color === '#faf5ff' ? '1px solid #ddd' : 'none',
                                    }}
                                  />
                                </Tooltip>
                              ))}
                            </InlineStack>

                            {/* Sections included */}
                            <Text as="p" variant="bodySm" tone="subdued">
                              {template.sections.length} sections included
                            </Text>

                            {/* Apply Button */}
                            <Button
                              fullWidth
                              variant={(localConfig as any)?.template === template.id ? 'secondary' : 'primary'}
                              onClick={() => applyTemplateMutation.mutate(template.id)}
                              loading={applyTemplateMutation.isPending}
                              disabled={(localConfig as any)?.template === template.id}
                            >
                              {(localConfig as any)?.template === template.id ? 'Currently Applied' : 'Apply Template'}
                            </Button>
                          </BlockStack>
                        </Card>
                      ))}
                    </div>

                    {!templatesData?.templates?.length && (
                      <Card>
                        <BlockStack gap="200" inlineAlign="center">
                          <Spinner size="small" />
                          <Text as="p" tone="subdued">Loading templates...</Text>
                        </BlockStack>
                      </Card>
                    )}
                  </BlockStack>
                </Box>
              )}

              {/* Sections Tab */}
              {selectedTab === 1 && (
                <Box paddingBlockStart="400">
                  <BlockStack gap="400">
                    <InlineStack align="space-between">
                      <Text as="h3" variant="headingMd">Active Sections</Text>
                      <Button
                        icon={PlusIcon}
                        onClick={() => setShowAddSection(true)}
                      >
                        Add Section
                      </Button>
                    </InlineStack>

                    <Text as="p" variant="bodyMd" tone="subdued">
                      Drag sections to reorder. Click Edit to customize content.
                    </Text>

                    <BlockStack gap="200">
                      {enabledSections.map((section, index) => (
                        <div
                          key={section.id}
                          draggable
                          onDragStart={() => handleDragStart(index)}
                          onDragOver={(e) => handleDragOver(e, index)}
                          onDragEnd={handleDragEnd}
                          style={{
                            opacity: draggedIndex === index ? 0.5 : 1,
                            cursor: 'grab',
                          }}
                        >
                          <Card>
                            <InlineStack align="space-between" blockAlign="center">
                              <InlineStack gap="300" blockAlign="center">
                                <div style={{ cursor: 'grab' }}>
                                  <Icon source={DragHandleIcon} tone="subdued" />
                                </div>
                                <BlockStack gap="100">
                                  <Text as="span" variant="bodyMd" fontWeight="semibold">
                                    {SECTION_LABELS[section.type] || section.type}
                                  </Text>
                                  <Text as="span" variant="bodySm" tone="subdued">
                                    {section.settings.title || 'No title set'}
                                  </Text>
                                </BlockStack>
                              </InlineStack>
                              <InlineStack gap="200">
                                <Tooltip content="Move up">
                                  <Button
                                    icon={ArrowUpIcon}
                                    size="slim"
                                    onClick={() => moveSection(index, Math.max(0, index - 1))}
                                    disabled={index === 0}
                                    accessibilityLabel="Move up"
                                  />
                                </Tooltip>
                                <Tooltip content="Move down">
                                  <Button
                                    icon={ArrowDownIcon}
                                    size="slim"
                                    onClick={() => moveSection(index, Math.min(enabledSections.length - 1, index + 1))}
                                    disabled={index === enabledSections.length - 1}
                                    accessibilityLabel="Move down"
                                  />
                                </Tooltip>
                                <Button
                                  icon={EditIcon}
                                  size="slim"
                                  onClick={() => setEditingSection(section)}
                                >
                                  Edit
                                </Button>
                                <Button
                                  size="slim"
                                  tone="critical"
                                  onClick={() => toggleSection(section.id, false)}
                                >
                                  Disable
                                </Button>
                              </InlineStack>
                            </InlineStack>
                          </Card>
                        </div>
                      ))}

                      {enabledSections.length === 0 && (
                        <Card>
                          <BlockStack gap="200" inlineAlign="center">
                            <Text as="p" tone="subdued">No active sections</Text>
                            <Button onClick={() => setShowAddSection(true)}>Add Your First Section</Button>
                          </BlockStack>
                        </Card>
                      )}
                    </BlockStack>

                    {disabledSections.length > 0 && (
                      <>
                        <Divider />
                        <Text as="h3" variant="headingMd">Disabled Sections</Text>
                        <BlockStack gap="200">
                          {disabledSections.map((section) => (
                            <Card key={section.id}>
                              <InlineStack align="space-between" blockAlign="center">
                                <BlockStack gap="100">
                                  <Text as="span" variant="bodyMd" fontWeight="semibold">
                                    {SECTION_LABELS[section.type] || section.type}
                                  </Text>
                                </BlockStack>
                                <InlineStack gap="200">
                                  <Button
                                    size="slim"
                                    onClick={() => toggleSection(section.id, true)}
                                  >
                                    Enable
                                  </Button>
                                  <Button
                                    size="slim"
                                    icon={DeleteIcon}
                                    tone="critical"
                                    onClick={() => removeSection(section.id)}
                                    accessibilityLabel="Remove section"
                                  />
                                </InlineStack>
                              </InlineStack>
                            </Card>
                          ))}
                        </BlockStack>
                      </>
                    )}
                  </BlockStack>
                </Box>
              )}

              {/* Design Tab */}
              {selectedTab === 2 && config && (
                <Box paddingBlockStart="400">
                  <BlockStack gap="400">
                    <Text as="h3" variant="headingMd">Colors</Text>
                    <FormLayout>
                      <FormLayout.Group>
                        <TextField
                          label="Primary Color"
                          value={config.colors?.primary || '#e85d27'}
                          onChange={(v) => updateConfig({
                            ...config,
                            colors: { ...config.colors, primary: v },
                          })}
                          autoComplete="off"
                          prefix={
                            <div
                              style={{
                                width: 20,
                                height: 20,
                                borderRadius: 4,
                                background: config.colors?.primary || '#e85d27',
                              }}
                            />
                          }
                        />
                        <TextField
                          label="Accent Color"
                          value={config.colors?.accent || '#ffd700'}
                          onChange={(v) => updateConfig({
                            ...config,
                            colors: { ...config.colors, accent: v },
                          })}
                          autoComplete="off"
                          prefix={
                            <div
                              style={{
                                width: 20,
                                height: 20,
                                borderRadius: 4,
                                background: config.colors?.accent || '#ffd700',
                              }}
                            />
                          }
                        />
                      </FormLayout.Group>
                      <FormLayout.Group>
                        <TextField
                          label="Secondary Color"
                          value={config.colors?.secondary || '#666666'}
                          onChange={(v) => updateConfig({
                            ...config,
                            colors: { ...config.colors, secondary: v },
                          })}
                          autoComplete="off"
                          prefix={
                            <div
                              style={{
                                width: 20,
                                height: 20,
                                borderRadius: 4,
                                background: config.colors?.secondary || '#666666',
                              }}
                            />
                          }
                        />
                        <TextField
                          label="Background Color"
                          value={config.colors?.background || '#ffffff'}
                          onChange={(v) => updateConfig({
                            ...config,
                            colors: { ...config.colors, background: v },
                          })}
                          autoComplete="off"
                          prefix={
                            <div
                              style={{
                                width: 20,
                                height: 20,
                                borderRadius: 4,
                                background: config.colors?.background || '#ffffff',
                                border: '1px solid #ddd',
                              }}
                            />
                          }
                        />
                      </FormLayout.Group>
                    </FormLayout>
                  </BlockStack>
                </Box>
              )}

              {/* Settings Tab */}
              {selectedTab === 3 && config && (
                <Box paddingBlockStart="400">
                  <BlockStack gap="400">
                    <Text as="h3" variant="headingMd">Page Settings</Text>
                    <FormLayout>
                      <Checkbox
                        label="Enable loyalty page"
                        helpText="When enabled, the page is accessible at /apps/rewards"
                        checked={config.enabled !== false}
                        onChange={(v) => updateConfig({ ...config, enabled: v })}
                      />

                      <TextField
                        label="Page Title"
                        value={config.meta?.title || 'Rewards Program'}
                        onChange={(v) => updateConfig({
                          ...config,
                          meta: { ...config.meta, title: v },
                        })}
                        autoComplete="off"
                        helpText="Shown in browser tab and search results"
                      />

                      <TextField
                        label="Meta Description"
                        value={config.meta?.description || ''}
                        onChange={(v) => updateConfig({
                          ...config,
                          meta: { ...config.meta, description: v },
                        })}
                        multiline={2}
                        autoComplete="off"
                        helpText="Description for search engines (max 160 characters)"
                        maxLength={160}
                        showCharacterCount
                      />

                      <TextField
                        label="Custom CSS"
                        value={config.custom_css || ''}
                        onChange={(v) => updateConfig({ ...config, custom_css: v })}
                        multiline={6}
                        monospaced
                        autoComplete="off"
                        helpText="Add custom CSS to further customize your page styling"
                      />
                    </FormLayout>
                  </BlockStack>
                </Box>
              )}
            </Tabs>
          </Card>
        </Layout.Section>

        {/* Preview sidebar */}
        <Layout.Section variant="oneThird">
          <BlockStack gap="400">
            <Card>
              <BlockStack gap="300">
                <Text as="h3" variant="headingMd">Live Preview</Text>
                <div
                  style={{
                    border: '1px solid #e0e0e0',
                    borderRadius: 8,
                    overflow: 'hidden',
                    height: 400,
                    background: '#f5f5f5',
                  }}
                >
                  <iframe
                    src={`${getApiUrl()}/loyalty-page/preview`}
                    style={{
                      width: '100%',
                      height: '100%',
                      border: 'none',
                      transform: 'scale(0.5)',
                      transformOrigin: 'top left',
                      width: '200%',
                      height: '200%',
                    }}
                    title="Page Preview"
                  />
                </div>
                <Button
                  fullWidth
                  onClick={() => setShowPreview(true)}
                  icon={ViewIcon}
                >
                  Full Preview
                </Button>
              </BlockStack>
            </Card>

            <Card>
              <BlockStack gap="300">
                <Text as="h3" variant="headingMd">Quick Actions</Text>
                <Button
                  fullWidth
                  url="/apps/rewards"
                  external
                  disabled={!isPublished}
                >
                  View Live Page
                </Button>
                <Button
                  fullWidth
                  onClick={handleSave}
                  disabled={!hasUnsavedChanges}
                  loading={saveMutation.isPending}
                >
                  Save Draft
                </Button>
              </BlockStack>
            </Card>

            <Card>
              <BlockStack gap="300">
                <Text as="h3" variant="headingMd">Tips</Text>
                <BlockStack gap="200">
                  <Text as="p" variant="bodySm">Keep your hero section compelling and action-oriented.</Text>
                  <Text as="p" variant="bodySm">Show 3-4 steps in "How It Works" for clarity.</Text>
                  <Text as="p" variant="bodySm">Highlight your best rewards prominently.</Text>
                  <Text as="p" variant="bodySm">Include an FAQ to reduce support questions.</Text>
                </BlockStack>
              </BlockStack>
            </Card>
          </BlockStack>
        </Layout.Section>
      </Layout>

      {/* Full Preview Modal */}
      <Modal
        open={showPreview}
        onClose={() => setShowPreview(false)}
        title="Page Preview"
        size="large"
      >
        <Modal.Section>
          <iframe
            src={`${getApiUrl()}/loyalty-page/preview`}
            style={{ width: '100%', height: '600px', border: 'none' }}
            title="Page Preview"
          />
        </Modal.Section>
      </Modal>

      {/* Add Section Modal */}
      <Modal
        open={showAddSection}
        onClose={() => setShowAddSection(false)}
        title="Add Section"
      >
        <Modal.Section>
          <BlockStack gap="300">
            {SECTION_TYPES.map((sectionType) => {
              const alreadyAdded = config?.sections?.some((s) => s.type === sectionType.type);
              return (
                <Card key={sectionType.type}>
                  <InlineStack align="space-between" blockAlign="center">
                    <BlockStack gap="100">
                      <Text as="span" variant="bodyMd" fontWeight="semibold">
                        {sectionType.label}
                      </Text>
                      <Text as="span" variant="bodySm" tone="subdued">
                        {sectionType.description}
                      </Text>
                    </BlockStack>
                    <Button
                      size="slim"
                      onClick={() => addSection(sectionType.type)}
                      disabled={alreadyAdded}
                    >
                      {alreadyAdded ? 'Added' : 'Add'}
                    </Button>
                  </InlineStack>
                </Card>
              );
            })}
          </BlockStack>
        </Modal.Section>
      </Modal>

      {/* Edit Section Modal */}
      {editingSection && (
        <SectionEditor
          section={editingSection}
          onClose={() => setEditingSection(null)}
          onSave={(settings) => {
            updateSectionSettings(editingSection.id, settings);
            setEditingSection(null);
          }}
        />
      )}
    </Page>
  );
}

// Section Editor Component
interface SectionEditorProps {
  section: Section;
  onClose: () => void;
  onSave: (settings: Record<string, any>) => void;
}

function SectionEditor({ section, onClose, onSave }: SectionEditorProps) {
  const [settings, setSettings] = useState(section.settings);

  const updateSetting = (key: string, value: any) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  const renderFields = () => {
    switch (section.type) {
      case 'hero':
        return (
          <>
            <TextField
              label="Title"
              value={settings.title || ''}
              onChange={(v) => updateSetting('title', v)}
              autoComplete="off"
            />
            <TextField
              label="Subtitle"
              value={settings.subtitle || ''}
              onChange={(v) => updateSetting('subtitle', v)}
              multiline={2}
              autoComplete="off"
            />
            <TextField
              label="CTA Button Text"
              value={settings.cta_text || ''}
              onChange={(v) => updateSetting('cta_text', v)}
              autoComplete="off"
            />
            <TextField
              label="CTA Button Link"
              value={settings.cta_link || ''}
              onChange={(v) => updateSetting('cta_link', v)}
              autoComplete="off"
              helpText="e.g., /account or /account/register"
            />
            <TextField
              label="Background Color"
              value={settings.background_color || '#e85d27'}
              onChange={(v) => updateSetting('background_color', v)}
              autoComplete="off"
            />
            <TextField
              label="Text Color"
              value={settings.text_color || '#ffffff'}
              onChange={(v) => updateSetting('text_color', v)}
              autoComplete="off"
            />
          </>
        );

      case 'how_it_works':
        return (
          <>
            <TextField
              label="Section Title"
              value={settings.title || ''}
              onChange={(v) => updateSetting('title', v)}
              autoComplete="off"
            />
            <Divider />
            <Text as="h4" variant="headingSm">Steps</Text>
            {(settings.steps || []).map((step: any, index: number) => (
              <Card key={index}>
                <BlockStack gap="200">
                  <InlineStack align="space-between">
                    <Text as="span" variant="bodyMd" fontWeight="semibold">Step {index + 1}</Text>
                    <Button
                      size="slim"
                      tone="critical"
                      onClick={() => {
                        const newSteps = settings.steps.filter((_: any, i: number) => i !== index);
                        updateSetting('steps', newSteps);
                      }}
                    >
                      Remove
                    </Button>
                  </InlineStack>
                  <TextField
                    label="Title"
                    value={step.title || ''}
                    onChange={(v) => {
                      const newSteps = [...settings.steps];
                      newSteps[index] = { ...newSteps[index], title: v };
                      updateSetting('steps', newSteps);
                    }}
                    autoComplete="off"
                  />
                  <TextField
                    label="Description"
                    value={step.description || ''}
                    onChange={(v) => {
                      const newSteps = [...settings.steps];
                      newSteps[index] = { ...newSteps[index], description: v };
                      updateSetting('steps', newSteps);
                    }}
                    autoComplete="off"
                  />
                </BlockStack>
              </Card>
            ))}
            <Button
              onClick={() => {
                const newSteps = [...(settings.steps || []), { title: '', description: '' }];
                updateSetting('steps', newSteps);
              }}
            >
              Add Step
            </Button>
          </>
        );

      case 'faq':
        return (
          <>
            <TextField
              label="Section Title"
              value={settings.title || ''}
              onChange={(v) => updateSetting('title', v)}
              autoComplete="off"
            />
            <Divider />
            <Text as="h4" variant="headingSm">FAQ Items</Text>
            {(settings.items || []).map((item: any, index: number) => (
              <Card key={index}>
                <BlockStack gap="200">
                  <InlineStack align="space-between">
                    <Text as="span" variant="bodyMd" fontWeight="semibold">Question {index + 1}</Text>
                    <Button
                      size="slim"
                      tone="critical"
                      onClick={() => {
                        const newItems = settings.items.filter((_: any, i: number) => i !== index);
                        updateSetting('items', newItems);
                      }}
                    >
                      Remove
                    </Button>
                  </InlineStack>
                  <TextField
                    label="Question"
                    value={item.question || ''}
                    onChange={(v) => {
                      const newItems = [...settings.items];
                      newItems[index] = { ...newItems[index], question: v };
                      updateSetting('items', newItems);
                    }}
                    autoComplete="off"
                  />
                  <TextField
                    label="Answer"
                    value={item.answer || ''}
                    onChange={(v) => {
                      const newItems = [...settings.items];
                      newItems[index] = { ...newItems[index], answer: v };
                      updateSetting('items', newItems);
                    }}
                    multiline={3}
                    autoComplete="off"
                  />
                </BlockStack>
              </Card>
            ))}
            <Button
              onClick={() => {
                const newItems = [...(settings.items || []), { question: '', answer: '' }];
                updateSetting('items', newItems);
              }}
            >
              Add FAQ Item
            </Button>
          </>
        );

      case 'tier_comparison':
        return (
          <>
            <TextField
              label="Section Title"
              value={settings.title || ''}
              onChange={(v) => updateSetting('title', v)}
              autoComplete="off"
            />
            <Checkbox
              label="Show tier benefits"
              checked={settings.show_benefits !== false}
              onChange={(v) => updateSetting('show_benefits', v)}
            />
            <Text as="p" variant="bodySm" tone="subdued">
              Tiers are automatically loaded from your tier configuration.
            </Text>
          </>
        );

      case 'rewards_catalog':
        return (
          <>
            <TextField
              label="Section Title"
              value={settings.title || ''}
              onChange={(v) => updateSetting('title', v)}
              autoComplete="off"
            />
            <Checkbox
              label="Show points cost"
              checked={settings.show_points_cost !== false}
              onChange={(v) => updateSetting('show_points_cost', v)}
            />
            <Text as="p" variant="bodySm" tone="subdued">
              Rewards are automatically loaded from your rewards configuration.
            </Text>
          </>
        );

      case 'earning_rules':
        return (
          <>
            <TextField
              label="Section Title"
              value={settings.title || ''}
              onChange={(v) => updateSetting('title', v)}
              autoComplete="off"
            />
            <Checkbox
              label="Show multipliers"
              checked={settings.show_multipliers !== false}
              onChange={(v) => updateSetting('show_multipliers', v)}
            />
            <Text as="p" variant="bodySm" tone="subdued">
              Earning rules are automatically loaded from your points configuration.
            </Text>
          </>
        );

      case 'referral_banner':
        return (
          <>
            <TextField
              label="Title"
              value={settings.title || ''}
              onChange={(v) => updateSetting('title', v)}
              autoComplete="off"
            />
            <TextField
              label="Description"
              value={settings.description || ''}
              onChange={(v) => updateSetting('description', v)}
              multiline={2}
              autoComplete="off"
            />
          </>
        );

      case 'cta':
        return (
          <>
            <TextField
              label="Title"
              value={settings.title || ''}
              onChange={(v) => updateSetting('title', v)}
              autoComplete="off"
            />
            <TextField
              label="Subtitle"
              value={settings.subtitle || ''}
              onChange={(v) => updateSetting('subtitle', v)}
              multiline={2}
              autoComplete="off"
            />
            <TextField
              label="Button Text"
              value={settings.button_text || ''}
              onChange={(v) => updateSetting('button_text', v)}
              autoComplete="off"
            />
            <TextField
              label="Button URL"
              value={settings.button_url || ''}
              onChange={(v) => updateSetting('button_url', v)}
              autoComplete="off"
            />
            <Checkbox
              label="Show email signup form"
              checked={settings.show_email_form === true}
              onChange={(v) => updateSetting('show_email_form', v)}
            />
          </>
        );

      default:
        return (
          <TextField
            label="Section Title"
            value={settings.title || ''}
            onChange={(v) => updateSetting('title', v)}
            autoComplete="off"
          />
        );
    }
  };

  return (
    <Modal
      open={true}
      onClose={onClose}
      title={`Edit ${SECTION_LABELS[section.type] || section.type}`}
      primaryAction={{
        content: 'Save',
        onAction: () => onSave(settings),
      }}
      secondaryActions={[
        {
          content: 'Cancel',
          onAction: onClose,
        },
      ]}
    >
      <Modal.Section>
        <FormLayout>{renderFields()}</FormLayout>
      </Modal.Section>
    </Modal>
  );
}

export default EmbeddedPageBuilder;
