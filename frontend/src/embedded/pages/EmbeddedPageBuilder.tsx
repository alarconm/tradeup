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
  Select,
  ChoiceList,
  RangeSlider,
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
  DesktopIcon,
  MobileIcon,
} from '@shopify/polaris-icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';
import { PageBuilderImageUpload } from '../components/PageBuilderImageUpload';

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
  styles: {
    fontFamily?: string;
    headingFontFamily?: string;
    buttonStyle?: 'rounded' | 'pill' | 'square';
    buttonSize?: 'small' | 'medium' | 'large';
    sectionSpacing?: 'compact' | 'normal' | 'relaxed';
    borderRadius?: 'none' | 'small' | 'medium' | 'large';
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

// Preview mode type for LP-007
type PreviewMode = 'desktop' | 'mobile';

// Mobile device dimensions for preview
const MOBILE_PREVIEW = {
  width: 375,
  height: 667,
  label: 'iPhone SE',
};

export function EmbeddedPageBuilder({ shop }: EmbeddedPageBuilderProps) {
  const [selectedTab, setSelectedTab] = useState(0);
  const [showPreview, setShowPreview] = useState(false);
  const [previewMode, setPreviewMode] = useState<PreviewMode>('desktop'); // LP-007
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
            {/* Undo/Redo toolbar with preview mode toggle (LP-007) */}
            <Box paddingBlockEnd="400">
              <InlineStack gap="200" blockAlign="center">
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

                {/* Preview mode toggle - LP-007 */}
                <div style={{ marginLeft: '16px', borderLeft: '1px solid #e0e0e0', paddingLeft: '16px' }}>
                  <InlineStack gap="100" blockAlign="center">
                    <Text as="span" variant="bodySm" tone="subdued">Preview:</Text>
                    <div style={{
                      display: 'flex',
                      background: '#f6f6f7',
                      borderRadius: '8px',
                      padding: '2px',
                    }}>
                      <Tooltip content="Desktop preview">
                        <button
                          onClick={() => setPreviewMode('desktop')}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: '36px',
                            height: '32px',
                            border: 'none',
                            borderRadius: '6px',
                            cursor: 'pointer',
                            background: previewMode === 'desktop' ? '#ffffff' : 'transparent',
                            boxShadow: previewMode === 'desktop' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                            transition: 'all 0.15s ease',
                          }}
                          aria-label="Desktop preview"
                          aria-pressed={previewMode === 'desktop'}
                        >
                          <Icon source={DesktopIcon} tone={previewMode === 'desktop' ? 'base' : 'subdued'} />
                        </button>
                      </Tooltip>
                      <Tooltip content="Mobile preview">
                        <button
                          onClick={() => setPreviewMode('mobile')}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: '36px',
                            height: '32px',
                            border: 'none',
                            borderRadius: '6px',
                            cursor: 'pointer',
                            background: previewMode === 'mobile' ? '#ffffff' : 'transparent',
                            boxShadow: previewMode === 'mobile' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                            transition: 'all 0.15s ease',
                          }}
                          aria-label="Mobile preview"
                          aria-pressed={previewMode === 'mobile'}
                        >
                          <Icon source={MobileIcon} tone={previewMode === 'mobile' ? 'base' : 'subdued'} />
                        </button>
                      </Tooltip>
                    </div>
                  </InlineStack>
                </div>

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

              {/* Design Tab - LP-006 Style Customization */}
              {selectedTab === 2 && config && (
                <Box paddingBlockStart="400">
                  <BlockStack gap="600">
                    {/* Colors Section */}
                    <BlockStack gap="400">
                      <Text as="h3" variant="headingMd">Colors</Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Click the color swatch to change colors. Changes apply to all sections in real-time.
                      </Text>
                      <FormLayout>
                        <FormLayout.Group>
                          <div>
                            <Text as="p" variant="bodyMd">Primary Color</Text>
                            <Text as="p" variant="bodySm" tone="subdued">Used for hero backgrounds, buttons, and highlights</Text>
                            <InlineStack gap="200" blockAlign="center">
                              <input
                                type="color"
                                value={config.colors?.primary || '#e85d27'}
                                onChange={(e) => updateConfig({
                                  ...config,
                                  colors: { ...config.colors, primary: e.target.value },
                                })}
                                style={{
                                  width: 48,
                                  height: 48,
                                  border: '2px solid #ddd',
                                  borderRadius: 8,
                                  cursor: 'pointer',
                                  padding: 0,
                                }}
                              />
                              <TextField
                                label=""
                                labelHidden
                                value={config.colors?.primary || '#e85d27'}
                                onChange={(v) => updateConfig({
                                  ...config,
                                  colors: { ...config.colors, primary: v },
                                })}
                                autoComplete="off"
                                monospaced
                              />
                            </InlineStack>
                          </div>
                          <div>
                            <Text as="p" variant="bodyMd">Secondary Color</Text>
                            <Text as="p" variant="bodySm" tone="subdued">Used for text and secondary elements</Text>
                            <InlineStack gap="200" blockAlign="center">
                              <input
                                type="color"
                                value={config.colors?.secondary || '#666666'}
                                onChange={(e) => updateConfig({
                                  ...config,
                                  colors: { ...config.colors, secondary: e.target.value },
                                })}
                                style={{
                                  width: 48,
                                  height: 48,
                                  border: '2px solid #ddd',
                                  borderRadius: 8,
                                  cursor: 'pointer',
                                  padding: 0,
                                }}
                              />
                              <TextField
                                label=""
                                labelHidden
                                value={config.colors?.secondary || '#666666'}
                                onChange={(v) => updateConfig({
                                  ...config,
                                  colors: { ...config.colors, secondary: v },
                                })}
                                autoComplete="off"
                                monospaced
                              />
                            </InlineStack>
                          </div>
                        </FormLayout.Group>
                        <FormLayout.Group>
                          <div>
                            <Text as="p" variant="bodyMd">Accent Color</Text>
                            <Text as="p" variant="bodySm" tone="subdued">Used for icons, badges, and emphasis</Text>
                            <InlineStack gap="200" blockAlign="center">
                              <input
                                type="color"
                                value={config.colors?.accent || '#ffd700'}
                                onChange={(e) => updateConfig({
                                  ...config,
                                  colors: { ...config.colors, accent: e.target.value },
                                })}
                                style={{
                                  width: 48,
                                  height: 48,
                                  border: '2px solid #ddd',
                                  borderRadius: 8,
                                  cursor: 'pointer',
                                  padding: 0,
                                }}
                              />
                              <TextField
                                label=""
                                labelHidden
                                value={config.colors?.accent || '#ffd700'}
                                onChange={(v) => updateConfig({
                                  ...config,
                                  colors: { ...config.colors, accent: v },
                                })}
                                autoComplete="off"
                                monospaced
                              />
                            </InlineStack>
                          </div>
                          <div>
                            <Text as="p" variant="bodyMd">Background Color</Text>
                            <Text as="p" variant="bodySm" tone="subdued">Page background color</Text>
                            <InlineStack gap="200" blockAlign="center">
                              <input
                                type="color"
                                value={config.colors?.background || '#ffffff'}
                                onChange={(e) => updateConfig({
                                  ...config,
                                  colors: { ...config.colors, background: e.target.value },
                                })}
                                style={{
                                  width: 48,
                                  height: 48,
                                  border: '2px solid #ddd',
                                  borderRadius: 8,
                                  cursor: 'pointer',
                                  padding: 0,
                                }}
                              />
                              <TextField
                                label=""
                                labelHidden
                                value={config.colors?.background || '#ffffff'}
                                onChange={(v) => updateConfig({
                                  ...config,
                                  colors: { ...config.colors, background: v },
                                })}
                                autoComplete="off"
                                monospaced
                              />
                            </InlineStack>
                          </div>
                        </FormLayout.Group>
                      </FormLayout>
                    </BlockStack>

                    <Divider />

                    {/* Typography Section */}
                    <BlockStack gap="400">
                      <Text as="h3" variant="headingMd">Typography</Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Choose fonts that match your brand. Changes apply to all text on the page.
                      </Text>
                      <FormLayout>
                        <FormLayout.Group>
                          <Select
                            label="Body Font"
                            helpText="Used for paragraphs and descriptions"
                            options={[
                              { label: 'System Default', value: 'system-ui' },
                              { label: 'Inter', value: 'Inter' },
                              { label: 'Roboto', value: 'Roboto' },
                              { label: 'Open Sans', value: 'Open Sans' },
                              { label: 'Lato', value: 'Lato' },
                              { label: 'Poppins', value: 'Poppins' },
                              { label: 'Montserrat', value: 'Montserrat' },
                              { label: 'Source Sans Pro', value: 'Source Sans Pro' },
                              { label: 'Nunito', value: 'Nunito' },
                            ]}
                            value={config.styles?.fontFamily || 'system-ui'}
                            onChange={(v) => updateConfig({
                              ...config,
                              styles: { ...config.styles, fontFamily: v },
                            })}
                          />
                          <Select
                            label="Heading Font"
                            helpText="Used for titles and headings"
                            options={[
                              { label: 'Same as Body', value: '' },
                              { label: 'System Default', value: 'system-ui' },
                              { label: 'Inter', value: 'Inter' },
                              { label: 'Roboto', value: 'Roboto' },
                              { label: 'Open Sans', value: 'Open Sans' },
                              { label: 'Lato', value: 'Lato' },
                              { label: 'Poppins', value: 'Poppins' },
                              { label: 'Montserrat', value: 'Montserrat' },
                              { label: 'Playfair Display', value: 'Playfair Display' },
                              { label: 'Oswald', value: 'Oswald' },
                            ]}
                            value={config.styles?.headingFontFamily || ''}
                            onChange={(v) => updateConfig({
                              ...config,
                              styles: { ...config.styles, headingFontFamily: v },
                            })}
                          />
                        </FormLayout.Group>
                      </FormLayout>
                      {/* Font Preview */}
                      <Card>
                        <BlockStack gap="200">
                          <Text as="p" variant="bodySm" tone="subdued">Preview</Text>
                          <div style={{
                            fontFamily: config.styles?.headingFontFamily || config.styles?.fontFamily || 'system-ui, sans-serif',
                            fontSize: '1.5rem',
                            fontWeight: 600,
                          }}>
                            Welcome to Our Rewards
                          </div>
                          <div style={{
                            fontFamily: config.styles?.fontFamily || 'system-ui, sans-serif',
                            fontSize: '1rem',
                          }}>
                            Earn points on every purchase and unlock exclusive member benefits.
                          </div>
                        </BlockStack>
                      </Card>
                    </BlockStack>

                    <Divider />

                    {/* Button Styles Section */}
                    <BlockStack gap="400">
                      <Text as="h3" variant="headingMd">Button Styles</Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Customize how buttons appear across your loyalty page.
                      </Text>
                      <FormLayout>
                        <FormLayout.Group>
                          <div>
                            <Text as="p" variant="bodyMd">Button Shape</Text>
                            <div style={{ marginTop: 8 }}>
                              <ChoiceList
                                title=""
                                titleHidden
                                choices={[
                                  { label: 'Square', value: 'square' },
                                  { label: 'Rounded', value: 'rounded' },
                                  { label: 'Pill', value: 'pill' },
                                ]}
                                selected={[config.styles?.buttonStyle || 'rounded']}
                                onChange={(v) => updateConfig({
                                  ...config,
                                  styles: { ...config.styles, buttonStyle: v[0] as 'rounded' | 'pill' | 'square' },
                                })}
                              />
                            </div>
                          </div>
                          <div>
                            <Text as="p" variant="bodyMd">Button Size</Text>
                            <div style={{ marginTop: 8 }}>
                              <ChoiceList
                                title=""
                                titleHidden
                                choices={[
                                  { label: 'Small', value: 'small' },
                                  { label: 'Medium', value: 'medium' },
                                  { label: 'Large', value: 'large' },
                                ]}
                                selected={[config.styles?.buttonSize || 'medium']}
                                onChange={(v) => updateConfig({
                                  ...config,
                                  styles: { ...config.styles, buttonSize: v[0] as 'small' | 'medium' | 'large' },
                                })}
                              />
                            </div>
                          </div>
                        </FormLayout.Group>
                      </FormLayout>
                      {/* Button Preview */}
                      <Card>
                        <BlockStack gap="200">
                          <Text as="p" variant="bodySm" tone="subdued">Preview</Text>
                          <InlineStack gap="200">
                            <button
                              style={{
                                background: config.colors?.primary || '#e85d27',
                                color: '#ffffff',
                                border: 'none',
                                padding: config.styles?.buttonSize === 'small' ? '8px 16px' :
                                         config.styles?.buttonSize === 'large' ? '16px 32px' : '12px 24px',
                                borderRadius: config.styles?.buttonStyle === 'square' ? '0px' :
                                              config.styles?.buttonStyle === 'pill' ? '999px' : '8px',
                                fontSize: config.styles?.buttonSize === 'small' ? '0.875rem' :
                                          config.styles?.buttonSize === 'large' ? '1.125rem' : '1rem',
                                fontWeight: 600,
                                cursor: 'pointer',
                                fontFamily: config.styles?.fontFamily || 'system-ui, sans-serif',
                              }}
                            >
                              Primary Button
                            </button>
                            <button
                              style={{
                                background: 'transparent',
                                color: config.colors?.primary || '#e85d27',
                                border: `2px solid ${config.colors?.primary || '#e85d27'}`,
                                padding: config.styles?.buttonSize === 'small' ? '6px 14px' :
                                         config.styles?.buttonSize === 'large' ? '14px 30px' : '10px 22px',
                                borderRadius: config.styles?.buttonStyle === 'square' ? '0px' :
                                              config.styles?.buttonStyle === 'pill' ? '999px' : '8px',
                                fontSize: config.styles?.buttonSize === 'small' ? '0.875rem' :
                                          config.styles?.buttonSize === 'large' ? '1.125rem' : '1rem',
                                fontWeight: 600,
                                cursor: 'pointer',
                                fontFamily: config.styles?.fontFamily || 'system-ui, sans-serif',
                              }}
                            >
                              Secondary Button
                            </button>
                          </InlineStack>
                        </BlockStack>
                      </Card>
                    </BlockStack>

                    <Divider />

                    {/* Section Spacing */}
                    <BlockStack gap="400">
                      <Text as="h3" variant="headingMd">Spacing & Layout</Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Control the spacing between sections and the overall page feel.
                      </Text>
                      <FormLayout>
                        <FormLayout.Group>
                          <div>
                            <Text as="p" variant="bodyMd">Section Spacing</Text>
                            <div style={{ marginTop: 8 }}>
                              <ChoiceList
                                title=""
                                titleHidden
                                choices={[
                                  { label: 'Compact - Minimal spacing between sections', value: 'compact' },
                                  { label: 'Normal - Balanced spacing (recommended)', value: 'normal' },
                                  { label: 'Relaxed - More breathing room between sections', value: 'relaxed' },
                                ]}
                                selected={[config.styles?.sectionSpacing || 'normal']}
                                onChange={(v) => updateConfig({
                                  ...config,
                                  styles: { ...config.styles, sectionSpacing: v[0] as 'compact' | 'normal' | 'relaxed' },
                                })}
                              />
                            </div>
                          </div>
                          <div>
                            <Text as="p" variant="bodyMd">Corner Radius</Text>
                            <div style={{ marginTop: 8 }}>
                              <ChoiceList
                                title=""
                                titleHidden
                                choices={[
                                  { label: 'None - Sharp corners', value: 'none' },
                                  { label: 'Small - Subtle rounding', value: 'small' },
                                  { label: 'Medium - Moderate rounding', value: 'medium' },
                                  { label: 'Large - Pronounced rounding', value: 'large' },
                                ]}
                                selected={[config.styles?.borderRadius || 'medium']}
                                onChange={(v) => updateConfig({
                                  ...config,
                                  styles: { ...config.styles, borderRadius: v[0] as 'none' | 'small' | 'medium' | 'large' },
                                })}
                              />
                            </div>
                          </div>
                        </FormLayout.Group>
                      </FormLayout>
                      {/* Spacing Preview */}
                      <Card>
                        <BlockStack gap="200">
                          <Text as="p" variant="bodySm" tone="subdued">Preview</Text>
                          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                            {[1, 2, 3].map((i) => (
                              <div
                                key={i}
                                style={{
                                  width: 80,
                                  height: 50,
                                  background: config.colors?.primary || '#e85d27',
                                  borderRadius: config.styles?.borderRadius === 'none' ? '0px' :
                                                config.styles?.borderRadius === 'small' ? '4px' :
                                                config.styles?.borderRadius === 'large' ? '16px' : '8px',
                                  marginBottom: config.styles?.sectionSpacing === 'compact' ? '8px' :
                                                config.styles?.sectionSpacing === 'relaxed' ? '24px' : '16px',
                                }}
                              />
                            ))}
                          </div>
                        </BlockStack>
                      </Card>
                    </BlockStack>
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

        {/* Preview sidebar - LP-007 responsive preview */}
        <Layout.Section variant="oneThird">
          <BlockStack gap="400">
            <Card>
              <BlockStack gap="300">
                <InlineStack align="space-between" blockAlign="center">
                  <Text as="h3" variant="headingMd">Live Preview</Text>
                  <Badge tone={previewMode === 'mobile' ? 'info' : 'success'}>
                    {previewMode === 'mobile' ? MOBILE_PREVIEW.label : 'Desktop'}
                  </Badge>
                </InlineStack>

                {/* Preview frame with device simulation - LP-007 */}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'flex-start',
                    background: '#f5f5f5',
                    borderRadius: 8,
                    padding: previewMode === 'mobile' ? '16px' : '0',
                    minHeight: 400,
                    overflow: 'hidden',
                  }}
                >
                  {previewMode === 'mobile' ? (
                    /* Mobile device frame */
                    <div
                      style={{
                        background: '#1a1a1a',
                        borderRadius: '32px',
                        padding: '12px',
                        boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
                        position: 'relative',
                      }}
                    >
                      {/* Notch */}
                      <div
                        style={{
                          position: 'absolute',
                          top: '12px',
                          left: '50%',
                          transform: 'translateX(-50%)',
                          width: '80px',
                          height: '24px',
                          background: '#1a1a1a',
                          borderRadius: '0 0 16px 16px',
                          zIndex: 10,
                        }}
                      />
                      {/* Screen */}
                      <div
                        style={{
                          width: `${MOBILE_PREVIEW.width * 0.45}px`,
                          height: `${MOBILE_PREVIEW.height * 0.5}px`,
                          borderRadius: '20px',
                          overflow: 'hidden',
                          background: '#ffffff',
                        }}
                      >
                        <iframe
                          src={`${getApiUrl()}/loyalty-page/preview?viewport=mobile`}
                          style={{
                            width: `${MOBILE_PREVIEW.width}px`,
                            height: `${MOBILE_PREVIEW.height}px`,
                            border: 'none',
                            transform: 'scale(0.45)',
                            transformOrigin: 'top left',
                          }}
                          title="Mobile Preview"
                        />
                      </div>
                    </div>
                  ) : (
                    /* Desktop preview */
                    <div
                      style={{
                        border: '1px solid #e0e0e0',
                        borderRadius: 8,
                        overflow: 'hidden',
                        width: '100%',
                        height: 400,
                        background: '#ffffff',
                      }}
                    >
                      <iframe
                        src={`${getApiUrl()}/loyalty-page/preview`}
                        style={{
                          width: '200%',
                          height: '200%',
                          border: 'none',
                          transform: 'scale(0.5)',
                          transformOrigin: 'top left',
                        }}
                        title="Desktop Preview"
                      />
                    </div>
                  )}
                </div>

                {/* Quick toggle in sidebar */}
                <InlineStack gap="200">
                  <Button
                    fullWidth
                    onClick={() => setPreviewMode('desktop')}
                    icon={DesktopIcon}
                    variant={previewMode === 'desktop' ? 'primary' : 'secondary'}
                    size="slim"
                  >
                    Desktop
                  </Button>
                  <Button
                    fullWidth
                    onClick={() => setPreviewMode('mobile')}
                    icon={MobileIcon}
                    variant={previewMode === 'mobile' ? 'primary' : 'secondary'}
                    size="slim"
                  >
                    Mobile
                  </Button>
                </InlineStack>

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

      {/* Full Preview Modal with mobile/desktop toggle - LP-007 */}
      <Modal
        open={showPreview}
        onClose={() => setShowPreview(false)}
        title="Page Preview"
        size="large"
      >
        <Modal.Section>
          <BlockStack gap="400">
            {/* Preview mode toggle in modal */}
            <InlineStack align="center" gap="400">
              <Text as="span" variant="bodyMd">View as:</Text>
              <div style={{
                display: 'flex',
                background: '#f6f6f7',
                borderRadius: '8px',
                padding: '4px',
              }}>
                <button
                  onClick={() => setPreviewMode('desktop')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 16px',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    background: previewMode === 'desktop' ? '#ffffff' : 'transparent',
                    boxShadow: previewMode === 'desktop' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                    transition: 'all 0.15s ease',
                    fontWeight: previewMode === 'desktop' ? 600 : 400,
                    color: previewMode === 'desktop' ? '#202223' : '#6d7175',
                  }}
                  aria-pressed={previewMode === 'desktop'}
                >
                  <Icon source={DesktopIcon} tone={previewMode === 'desktop' ? 'base' : 'subdued'} />
                  Desktop
                </button>
                <button
                  onClick={() => setPreviewMode('mobile')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 16px',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    background: previewMode === 'mobile' ? '#ffffff' : 'transparent',
                    boxShadow: previewMode === 'mobile' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                    transition: 'all 0.15s ease',
                    fontWeight: previewMode === 'mobile' ? 600 : 400,
                    color: previewMode === 'mobile' ? '#202223' : '#6d7175',
                  }}
                  aria-pressed={previewMode === 'mobile'}
                >
                  <Icon source={MobileIcon} tone={previewMode === 'mobile' ? 'base' : 'subdued'} />
                  Mobile ({MOBILE_PREVIEW.label})
                </button>
              </div>
            </InlineStack>

            {/* Preview container */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'flex-start',
                background: '#f5f5f5',
                borderRadius: 8,
                padding: previewMode === 'mobile' ? '24px' : '0',
                minHeight: 600,
              }}
            >
              {previewMode === 'mobile' ? (
                /* Mobile device frame in modal */
                <div
                  style={{
                    background: '#1a1a1a',
                    borderRadius: '44px',
                    padding: '14px',
                    boxShadow: '0 12px 48px rgba(0,0,0,0.25)',
                    position: 'relative',
                  }}
                >
                  {/* Notch */}
                  <div
                    style={{
                      position: 'absolute',
                      top: '14px',
                      left: '50%',
                      transform: 'translateX(-50%)',
                      width: '120px',
                      height: '28px',
                      background: '#1a1a1a',
                      borderRadius: '0 0 20px 20px',
                      zIndex: 10,
                    }}
                  />
                  {/* Screen */}
                  <div
                    style={{
                      width: `${MOBILE_PREVIEW.width}px`,
                      height: `${MOBILE_PREVIEW.height}px`,
                      borderRadius: '30px',
                      overflow: 'hidden',
                      background: '#ffffff',
                    }}
                  >
                    <iframe
                      src={`${getApiUrl()}/loyalty-page/preview?viewport=mobile`}
                      style={{
                        width: '100%',
                        height: '100%',
                        border: 'none',
                      }}
                      title="Mobile Preview"
                    />
                  </div>
                  {/* Home indicator */}
                  <div
                    style={{
                      position: 'absolute',
                      bottom: '8px',
                      left: '50%',
                      transform: 'translateX(-50%)',
                      width: '100px',
                      height: '4px',
                      background: '#4a4a4a',
                      borderRadius: '2px',
                    }}
                  />
                </div>
              ) : (
                /* Desktop preview in modal */
                <iframe
                  src={`${getApiUrl()}/loyalty-page/preview`}
                  style={{
                    width: '100%',
                    height: '600px',
                    border: '1px solid #e0e0e0',
                    borderRadius: 8,
                    background: '#ffffff',
                  }}
                  title="Desktop Preview"
                />
              )}
            </div>
          </BlockStack>
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
          shop={shop}
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
  shop: string | null;
  onClose: () => void;
  onSave: (settings: Record<string, any>) => void;
}

function SectionEditor({ section, shop, onClose, onSave }: SectionEditorProps) {
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
            <Divider />
            <Text as="h4" variant="headingSm">Background</Text>
            <PageBuilderImageUpload
              label="Background Image"
              value={settings.background_image || ''}
              onChange={(v) => updateSetting('background_image', v)}
              shop={shop}
              recommendedSize="1920 x 600 pixels"
              helpText="Optional. If set, will be used instead of background color."
              isBackground
            />
            <TextField
              label="Background Color"
              value={settings.background_color || '#e85d27'}
              onChange={(v) => updateSetting('background_color', v)}
              autoComplete="off"
              helpText="Used when no background image is set"
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
                  <PageBuilderImageUpload
                    label="Step Icon"
                    value={step.icon_image || ''}
                    onChange={(v) => {
                      const newSteps = [...settings.steps];
                      newSteps[index] = { ...newSteps[index], icon_image: v };
                      updateSetting('steps', newSteps);
                    }}
                    shop={shop}
                    recommendedSize="64 x 64 pixels"
                    helpText="Optional. Upload a custom icon for this step."
                  />
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
                const newSteps = [...(settings.steps || []), { title: '', description: '', icon_image: '' }];
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
            <Divider />
            <PageBuilderImageUpload
              label="Background Image"
              value={settings.background_image || ''}
              onChange={(v) => updateSetting('background_image', v)}
              shop={shop}
              recommendedSize="1200 x 400 pixels"
              helpText="Optional. Adds a background image to the referral banner."
              isBackground
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
            <Divider />
            <PageBuilderImageUpload
              label="Background Image"
              value={settings.background_image || ''}
              onChange={(v) => updateSetting('background_image', v)}
              shop={shop}
              recommendedSize="1200 x 400 pixels"
              helpText="Optional. Adds a background image to the CTA section."
              isBackground
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
