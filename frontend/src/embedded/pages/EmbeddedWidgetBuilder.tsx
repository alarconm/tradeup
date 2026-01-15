/**
 * Widget Visual Builder
 *
 * Customize the customer-facing loyalty widget appearance and behavior.
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
  RangeSlider,
  FormLayout,
  Modal,
  Collapsible,
  Icon,
} from '@shopify/polaris';
import {
  ViewIcon,
  CodeIcon,
  PaintBrushFlatIcon,
  SettingsIcon,
} from '@shopify/polaris-icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';

interface EmbeddedWidgetBuilderProps {
  shop: string | null;
}

interface WidgetTheme {
  id: string;
  name: string;
  description: string;
  appearance: {
    primary_color: string;
    text_color: string;
    background_color: string;
    border_radius: number;
  };
}

interface WidgetConfig {
  enabled: boolean;
  position: string;
  theme: string;
  appearance: {
    primary_color?: string;
    text_color?: string;
    background_color?: string;
    border_radius?: number;
    shadow?: boolean;
    animation?: string;
  };
  launcher: {
    icon?: string;
    text?: string;
    show_points_badge?: boolean;
    size?: string;
  };
  panel: {
    show_points_balance?: boolean;
    show_tier_progress?: boolean;
    show_available_rewards?: boolean;
    show_earning_rules?: boolean;
    show_referral_link?: boolean;
    max_rewards_shown?: number;
    welcome_message?: string;
    guest_message?: string;
  };
  branding: {
    show_logo?: boolean;
    program_name?: string;
    powered_by?: boolean;
  };
  behavior: {
    auto_open_for_new_members?: boolean;
    close_on_outside_click?: boolean;
    show_notifications?: boolean;
  };
  display_rules: {
    hide_on_mobile?: boolean;
    show_only_for_members?: boolean;
    hide_during_checkout?: boolean;
  };
}

async function fetchWidgetConfig(shop: string | null): Promise<{ config: WidgetConfig }> {
  const response = await authFetch(`${getApiUrl()}/widget-builder/config`, shop);
  if (!response.ok) throw new Error('Failed to fetch widget config');
  return response.json();
}

async function fetchThemes(shop: string | null): Promise<{ themes: WidgetTheme[] }> {
  const response = await authFetch(`${getApiUrl()}/widget-builder/themes`, shop);
  if (!response.ok) throw new Error('Failed to fetch themes');
  return response.json();
}

async function fetchEmbedCode(shop: string | null): Promise<{ embed_code: string }> {
  const response = await authFetch(`${getApiUrl()}/widget-builder/embed-code`, shop);
  if (!response.ok) throw new Error('Failed to fetch embed code');
  return response.json();
}

const POSITION_OPTIONS = [
  { label: 'Bottom Right', value: 'bottom-right' },
  { label: 'Bottom Left', value: 'bottom-left' },
  { label: 'Right Tab', value: 'right-tab' },
  { label: 'Left Tab', value: 'left-tab' },
];

const ICON_OPTIONS = [
  { label: 'Gift', value: 'gift' },
  { label: 'Star', value: 'star' },
  { label: 'Heart', value: 'heart' },
  { label: 'Trophy', value: 'trophy' },
  { label: 'Custom', value: 'custom' },
];

const SIZE_OPTIONS = [
  { label: 'Small', value: 'small' },
  { label: 'Medium', value: 'medium' },
  { label: 'Large', value: 'large' },
];

const ANIMATION_OPTIONS = [
  { label: 'Slide', value: 'slide' },
  { label: 'Fade', value: 'fade' },
  { label: 'None', value: 'none' },
];

export function EmbeddedWidgetBuilder({ shop }: EmbeddedWidgetBuilderProps) {
  const [selectedTab, setSelectedTab] = useState(0);
  const [showEmbedCode, setShowEmbedCode] = useState(false);

  const queryClient = useQueryClient();

  const { data: configData, isLoading: loadingConfig } = useQuery({
    queryKey: ['widget-builder-config', shop],
    queryFn: () => fetchWidgetConfig(shop),
    enabled: !!shop,
  });

  const { data: themesData } = useQuery({
    queryKey: ['widget-builder-themes', shop],
    queryFn: () => fetchThemes(shop),
    enabled: !!shop,
  });

  const { data: embedCodeData } = useQuery({
    queryKey: ['widget-builder-embed-code', shop],
    queryFn: () => fetchEmbedCode(shop),
    enabled: showEmbedCode && !!shop,
  });

  const updateConfigMutation = useMutation({
    mutationFn: async (config: Partial<WidgetConfig>) => {
      const response = await authFetch(`${getApiUrl()}/widget-builder/config`, shop, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (!response.ok) throw new Error('Failed to update config');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['widget-builder-config', shop] });
    },
  });

  const applyThemeMutation = useMutation({
    mutationFn: async (themeId: string) => {
      const response = await authFetch(`${getApiUrl()}/widget-builder/themes/${themeId}/apply`, shop, {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Failed to apply theme');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['widget-builder-config', shop] });
    },
  });

  const config = configData?.config;
  const themes = themesData?.themes || [];

  const tabs = [
    { id: 'appearance', content: 'Appearance', panelID: 'appearance-panel' },
    { id: 'content', content: 'Content', panelID: 'content-panel' },
    { id: 'behavior', content: 'Behavior', panelID: 'behavior-panel' },
  ];

  if (loadingConfig) {
    return (
      <Page title="Widget Builder">
        <Card>
          <BlockStack gap="200" inlineAlign="center">
            <Spinner size="large" />
            <Text as="p">Loading widget builder...</Text>
          </BlockStack>
        </Card>
      </Page>
    );
  }

  return (
    <Page
      title="Widget Builder"
      subtitle="Customize your customer-facing loyalty widget"
      primaryAction={{
        content: 'Get Embed Code',
        icon: CodeIcon,
        onAction: () => setShowEmbedCode(true),
      }}
    >
      <Layout>
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <InlineStack align="space-between">
                <Text as="h3" variant="headingMd">Widget Preview</Text>
                <Checkbox
                  label="Enable Widget"
                  checked={config?.enabled !== false}
                  onChange={(v) => updateConfigMutation.mutate({ enabled: v })}
                />
              </InlineStack>

              {/* Widget Preview */}
              <Box
                padding="400"
                background="bg-surface-secondary"
                borderRadius="200"
              >
                <div style={{ position: 'relative', height: 300, display: 'flex', alignItems: 'flex-end', justifyContent: config?.position?.includes('left') ? 'flex-start' : 'flex-end' }}>
                  {/* Mock widget button */}
                  <div
                    style={{
                      width: config?.launcher?.size === 'large' ? 70 : config?.launcher?.size === 'small' ? 50 : 60,
                      height: config?.launcher?.size === 'large' ? 70 : config?.launcher?.size === 'small' ? 50 : 60,
                      borderRadius: config?.appearance?.border_radius || 16,
                      background: config?.appearance?.primary_color || '#e85d27',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: config?.appearance?.text_color || '#fff',
                      fontSize: 24,
                      boxShadow: config?.appearance?.shadow ? '0 4px 12px rgba(0,0,0,0.15)' : 'none',
                      cursor: 'pointer',
                    }}
                  >
                    {config?.launcher?.icon === 'gift' ? '🎁' :
                     config?.launcher?.icon === 'star' ? '⭐' :
                     config?.launcher?.icon === 'heart' ? '❤️' :
                     config?.launcher?.icon === 'trophy' ? '🏆' : '🎁'}
                  </div>
                </div>
              </Box>
            </BlockStack>
          </Card>

          <Card>
            <Tabs tabs={tabs} selected={selectedTab} onSelect={setSelectedTab}>
              {/* Appearance Tab */}
              {selectedTab === 0 && (
                <BlockStack gap="400">
                  <Text as="h3" variant="headingMd">Theme</Text>
                  <InlineStack gap="300" wrap>
                    {themes.map((theme) => (
                      <Card key={theme.id}>
                        <BlockStack gap="200">
                          <Text as="span" variant="headingSm">{theme.name}</Text>
                          <Text as="p" variant="bodySm" tone="subdued">{theme.description}</Text>
                          <InlineStack gap="100">
                            {Object.values(theme.appearance).filter(v => typeof v === 'string').slice(0, 3).map((color, i) => (
                              <div
                                key={i}
                                style={{
                                  width: 20,
                                  height: 20,
                                  borderRadius: 4,
                                  background: color as string,
                                  border: '1px solid #ddd',
                                }}
                              />
                            ))}
                          </InlineStack>
                          <Button
                            size="slim"
                            variant={config?.theme === theme.id ? 'primary' : undefined}
                            onClick={() => applyThemeMutation.mutate(theme.id)}
                          >
                            {config?.theme === theme.id ? 'Applied' : 'Apply'}
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
                        value={config?.appearance?.primary_color || '#e85d27'}
                        onChange={(v) => updateConfigMutation.mutate({
                          appearance: { ...config?.appearance, primary_color: v }
                        })}
                        autoComplete="off"
                      />
                      <TextField
                        label="Text Color"
                        value={config?.appearance?.text_color || '#ffffff'}
                        onChange={(v) => updateConfigMutation.mutate({
                          appearance: { ...config?.appearance, text_color: v }
                        })}
                        autoComplete="off"
                      />
                    </FormLayout.Group>
                    <FormLayout.Group>
                      <TextField
                        label="Background Color"
                        value={config?.appearance?.background_color || '#ffffff'}
                        onChange={(v) => updateConfigMutation.mutate({
                          appearance: { ...config?.appearance, background_color: v }
                        })}
                        autoComplete="off"
                      />
                      <TextField
                        label="Border Radius"
                        type="number"
                        value={String(config?.appearance?.border_radius || 16)}
                        onChange={(v) => updateConfigMutation.mutate({
                          appearance: { ...config?.appearance, border_radius: parseInt(v) }
                        })}
                        suffix="px"
                        autoComplete="off"
                      />
                    </FormLayout.Group>
                  </FormLayout>

                  <Divider />

                  <Text as="h3" variant="headingMd">Position & Size</Text>
                  <FormLayout>
                    <FormLayout.Group>
                      <Select
                        label="Position"
                        options={POSITION_OPTIONS}
                        value={config?.position || 'bottom-right'}
                        onChange={(v) => updateConfigMutation.mutate({ position: v })}
                      />
                      <Select
                        label="Launcher Size"
                        options={SIZE_OPTIONS}
                        value={config?.launcher?.size || 'medium'}
                        onChange={(v) => updateConfigMutation.mutate({
                          launcher: { ...config?.launcher, size: v }
                        })}
                      />
                    </FormLayout.Group>
                    <FormLayout.Group>
                      <Select
                        label="Launcher Icon"
                        options={ICON_OPTIONS}
                        value={config?.launcher?.icon || 'gift'}
                        onChange={(v) => updateConfigMutation.mutate({
                          launcher: { ...config?.launcher, icon: v }
                        })}
                      />
                      <Select
                        label="Animation"
                        options={ANIMATION_OPTIONS}
                        value={config?.appearance?.animation || 'slide'}
                        onChange={(v) => updateConfigMutation.mutate({
                          appearance: { ...config?.appearance, animation: v }
                        })}
                      />
                    </FormLayout.Group>
                  </FormLayout>
                </BlockStack>
              )}

              {/* Content Tab */}
              {selectedTab === 1 && (
                <BlockStack gap="400">
                  <Text as="h3" variant="headingMd">Panel Content</Text>
                  <FormLayout>
                    <Checkbox
                      label="Show points balance"
                      checked={config?.panel?.show_points_balance !== false}
                      onChange={(v) => updateConfigMutation.mutate({
                        panel: { ...config?.panel, show_points_balance: v }
                      })}
                    />
                    <Checkbox
                      label="Show tier progress"
                      checked={config?.panel?.show_tier_progress !== false}
                      onChange={(v) => updateConfigMutation.mutate({
                        panel: { ...config?.panel, show_tier_progress: v }
                      })}
                    />
                    <Checkbox
                      label="Show available rewards"
                      checked={config?.panel?.show_available_rewards !== false}
                      onChange={(v) => updateConfigMutation.mutate({
                        panel: { ...config?.panel, show_available_rewards: v }
                      })}
                    />
                    <Checkbox
                      label="Show earning rules"
                      checked={config?.panel?.show_earning_rules !== false}
                      onChange={(v) => updateConfigMutation.mutate({
                        panel: { ...config?.panel, show_earning_rules: v }
                      })}
                    />
                    <Checkbox
                      label="Show referral link"
                      checked={config?.panel?.show_referral_link !== false}
                      onChange={(v) => updateConfigMutation.mutate({
                        panel: { ...config?.panel, show_referral_link: v }
                      })}
                    />
                  </FormLayout>

                  <Divider />

                  <Text as="h3" variant="headingMd">Messages</Text>
                  <FormLayout>
                    <TextField
                      label="Welcome Message (Members)"
                      value={config?.panel?.welcome_message || ''}
                      onChange={(v) => updateConfigMutation.mutate({
                        panel: { ...config?.panel, welcome_message: v }
                      })}
                      autoComplete="off"
                    />
                    <TextField
                      label="Guest Message"
                      value={config?.panel?.guest_message || ''}
                      onChange={(v) => updateConfigMutation.mutate({
                        panel: { ...config?.panel, guest_message: v }
                      })}
                      autoComplete="off"
                    />
                  </FormLayout>

                  <Divider />

                  <Text as="h3" variant="headingMd">Branding</Text>
                  <FormLayout>
                    <TextField
                      label="Program Name"
                      value={config?.branding?.program_name || 'Rewards'}
                      onChange={(v) => updateConfigMutation.mutate({
                        branding: { ...config?.branding, program_name: v }
                      })}
                      autoComplete="off"
                    />
                    <Checkbox
                      label="Show 'Powered by TradeUp'"
                      checked={config?.branding?.powered_by !== false}
                      onChange={(v) => updateConfigMutation.mutate({
                        branding: { ...config?.branding, powered_by: v }
                      })}
                    />
                  </FormLayout>
                </BlockStack>
              )}

              {/* Behavior Tab */}
              {selectedTab === 2 && (
                <BlockStack gap="400">
                  <Text as="h3" variant="headingMd">Behavior</Text>
                  <FormLayout>
                    <Checkbox
                      label="Auto-open for new members"
                      checked={config?.behavior?.auto_open_for_new_members !== false}
                      onChange={(v) => updateConfigMutation.mutate({
                        behavior: { ...config?.behavior, auto_open_for_new_members: v }
                      })}
                    />
                    <Checkbox
                      label="Close when clicking outside"
                      checked={config?.behavior?.close_on_outside_click !== false}
                      onChange={(v) => updateConfigMutation.mutate({
                        behavior: { ...config?.behavior, close_on_outside_click: v }
                      })}
                    />
                    <Checkbox
                      label="Show notifications"
                      checked={config?.behavior?.show_notifications !== false}
                      onChange={(v) => updateConfigMutation.mutate({
                        behavior: { ...config?.behavior, show_notifications: v }
                      })}
                    />
                  </FormLayout>

                  <Divider />

                  <Text as="h3" variant="headingMd">Display Rules</Text>
                  <FormLayout>
                    <Checkbox
                      label="Hide on mobile devices"
                      checked={config?.display_rules?.hide_on_mobile === true}
                      onChange={(v) => updateConfigMutation.mutate({
                        display_rules: { ...config?.display_rules, hide_on_mobile: v }
                      })}
                    />
                    <Checkbox
                      label="Show only for members"
                      checked={config?.display_rules?.show_only_for_members === true}
                      onChange={(v) => updateConfigMutation.mutate({
                        display_rules: { ...config?.display_rules, show_only_for_members: v }
                      })}
                    />
                    <Checkbox
                      label="Hide during checkout"
                      checked={config?.display_rules?.hide_during_checkout !== false}
                      onChange={(v) => updateConfigMutation.mutate({
                        display_rules: { ...config?.display_rules, hide_during_checkout: v }
                      })}
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
              <Button fullWidth onClick={() => setShowEmbedCode(true)} icon={CodeIcon}>
                Get Embed Code
              </Button>
            </BlockStack>
          </Card>

          <Card>
            <BlockStack gap="300">
              <Text as="h3" variant="headingMd">Tips</Text>
              <BlockStack gap="100">
                <Text as="p" variant="bodyMd">Use colors that match your store theme.</Text>
                <Text as="p" variant="bodyMd">Keep the widget visible but not intrusive.</Text>
                <Text as="p" variant="bodyMd">Show points balance to encourage purchases.</Text>
                <Text as="p" variant="bodyMd">Hide during checkout to avoid distractions.</Text>
              </BlockStack>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>

      {/* Embed Code Modal */}
      <Modal
        open={showEmbedCode}
        onClose={() => setShowEmbedCode(false)}
        title="Widget Embed Code"
      >
        <Modal.Section>
          <BlockStack gap="300">
            <Text as="p" variant="bodyMd">
              Add this code to your theme to display the loyalty widget. The widget will automatically
              load using your theme app extension.
            </Text>
            <Box
              padding="300"
              background="bg-surface-secondary"
              borderRadius="200"
            >
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 12 }}>
                {embedCodeData?.embed_code || 'Loading...'}
              </pre>
            </Box>
            <Banner tone="info">
              If you're using a Shopify theme, the widget is automatically included via the theme app extension.
            </Banner>
          </BlockStack>
        </Modal.Section>
      </Modal>
    </Page>
  );
}

export default EmbeddedWidgetBuilder;
