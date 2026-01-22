/**
 * EmbeddedWidgets - Widget Builder Admin Page
 *
 * Admin page to configure all widget types with toggle, position, and color settings.
 * Supports Points Balance, Tier Badge, Rewards Launcher, and Referral Prompt widgets.
 */

import React, { useState, useCallback } from 'react';
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
  Box,
  Divider,
  Select,
  FormLayout,
  Modal,
  Collapsible,
  Icon,
  Tooltip,
} from '@shopify/polaris';
import {
  ChevronDownIcon,
  ChevronUpIcon,
  RefreshIcon,
  ViewIcon,
  SettingsIcon,
  GiftCardIcon,
  StarIcon,
  PersonIcon,
  ShareIcon,
} from '@shopify/polaris-icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, authFetch } from '../../hooks/useShopifyBridge';
import { PositionSelector, type WidgetPosition } from '../components/PositionSelector';
import { ColorPicker } from '../components/ColorPicker';

interface EmbeddedWidgetsProps {
  shop: string | null;
}

/** Widget type enum matching backend */
type WidgetType = 'points_balance' | 'tier_badge' | 'rewards_launcher' | 'referral_prompt';

/** Widget configuration structure */
interface WidgetConfig {
  position?: {
    type?: string;
    location?: string;
    offset_x?: number;
    offset_y?: number;
    selector?: string;
    placement?: string;
  };
  styling?: {
    background_color?: string;
    text_color?: string;
    accent_color?: string;
    icon_color?: string;
    border_radius?: number;
    font_size?: number;
    shadow?: boolean;
    size?: number;
    badge_style?: string;
  };
  content?: {
    show_icon?: boolean;
    show_label?: boolean;
    label_text?: string;
    show_tier_indicator?: boolean;
    show_tier_name?: boolean;
    show_tier_icon?: boolean;
    show_progress_bar?: boolean;
    icon?: string;
    tooltip_text?: string;
    show_notification_badge?: boolean;
    title?: string;
    description?: string;
    cta_text?: string;
    show_reward_amount?: boolean;
  };
  behavior?: {
    click_action?: string;
    animate_on_update?: boolean;
    show_on_mobile?: boolean;
    panel_position?: string;
    trigger?: string;
    trigger_value?: number;
    show_once_per_session?: boolean;
    dismissible?: boolean;
  };
}

/** Widget data from API */
interface Widget {
  id: number;
  tenant_id: number;
  widget_type: WidgetType;
  config: WidgetConfig;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

/** Widget metadata for display */
interface WidgetMetadata {
  type: WidgetType;
  name: string;
  description: string;
  icon: typeof GiftCardIcon;
  preview: string;
}

/** Widget metadata definitions */
const WIDGET_METADATA: Record<WidgetType, WidgetMetadata> = {
  points_balance: {
    type: 'points_balance',
    name: 'Points Balance',
    description: 'Floating widget showing customer\'s current points balance',
    icon: StarIcon,
    preview: '500 pts',
  },
  tier_badge: {
    type: 'tier_badge',
    name: 'Tier Badge',
    description: 'Badge displaying customer\'s membership tier',
    icon: PersonIcon,
    preview: 'Gold',
  },
  rewards_launcher: {
    type: 'rewards_launcher',
    name: 'Rewards Launcher',
    description: 'Button to open the rewards panel',
    icon: GiftCardIcon,
    preview: 'icon',
  },
  referral_prompt: {
    type: 'referral_prompt',
    name: 'Referral Prompt',
    description: 'Promotional banner encouraging referrals',
    icon: ShareIcon,
    preview: 'Share & Earn!',
  },
};

/** Position options for fixed widgets */
const POSITION_OPTIONS = [
  { label: 'Bottom Right', value: 'bottom-right' },
  { label: 'Bottom Left', value: 'bottom-left' },
  { label: 'Top Right', value: 'top-right' },
  { label: 'Top Left', value: 'top-left' },
  { label: 'Top Center', value: 'top-center' },
  { label: 'Bottom Center', value: 'bottom-center' },
];

/** Icon options for widgets */
const ICON_OPTIONS = [
  { label: 'Gift', value: 'gift' },
  { label: 'Star', value: 'star' },
  { label: 'Heart', value: 'heart' },
  { label: 'Trophy', value: 'trophy' },
  { label: 'Coin', value: 'coin' },
];

/** Badge style options */
const BADGE_STYLE_OPTIONS = [
  { label: 'Pill', value: 'pill' },
  { label: 'Square', value: 'square' },
  { label: 'Rounded', value: 'rounded' },
];

/** Trigger options for referral prompt */
const TRIGGER_OPTIONS = [
  { label: 'On Scroll', value: 'scroll' },
  { label: 'After Delay', value: 'delay' },
  { label: 'Exit Intent', value: 'exit_intent' },
  { label: 'Immediately', value: 'immediate' },
];

/** API functions */
async function fetchWidgets(shop: string | null): Promise<{ widgets: Widget[] }> {
  const response = await authFetch(`${getApiUrl()}/widgets`, shop);
  if (!response.ok) throw new Error('Failed to fetch widgets');
  return response.json();
}

async function updateWidget(
  shop: string | null,
  widgetType: WidgetType,
  data: { config?: WidgetConfig; is_enabled?: boolean }
): Promise<{ widget: Widget }> {
  const response = await authFetch(`${getApiUrl()}/widgets/${widgetType}`, shop, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to update widget');
  return response.json();
}

async function toggleWidget(
  shop: string | null,
  widgetType: WidgetType,
  enabled: boolean
): Promise<{ widget: Widget }> {
  const endpoint = enabled ? 'enable' : 'disable';
  const response = await authFetch(`${getApiUrl()}/widgets/${widgetType}/${endpoint}`, shop, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to toggle widget');
  return response.json();
}

async function resetWidget(
  shop: string | null,
  widgetType: WidgetType
): Promise<{ widget: Widget }> {
  const response = await authFetch(`${getApiUrl()}/widgets/${widgetType}/reset`, shop, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to reset widget');
  return response.json();
}

/** Widget Card Component */
function WidgetCard({
  widget,
  metadata,
  onToggle,
  onConfigure,
  isToggling,
}: {
  widget: Widget;
  metadata: WidgetMetadata;
  onToggle: (enabled: boolean) => void;
  onConfigure: () => void;
  isToggling: boolean;
}) {
  const IconComponent = metadata.icon;

  return (
    <Card>
      <BlockStack gap="400">
        <InlineStack align="space-between" blockAlign="center">
          <InlineStack gap="300" blockAlign="center">
            <Box
              padding="300"
              borderRadius="200"
              background={widget.is_enabled ? 'bg-fill-success' : 'bg-surface-secondary'}
            >
              <Icon source={IconComponent} tone={widget.is_enabled ? 'base' : 'subdued'} />
            </Box>
            <BlockStack gap="050">
              <InlineStack gap="200" blockAlign="center">
                <Text as="h3" variant="headingMd">{metadata.name}</Text>
                <Badge tone={widget.is_enabled ? 'success' : undefined}>
                  {widget.is_enabled ? 'Enabled' : 'Disabled'}
                </Badge>
              </InlineStack>
              <Text as="p" variant="bodySm" tone="subdued">
                {metadata.description}
              </Text>
            </BlockStack>
          </InlineStack>
          <InlineStack gap="200">
            <Tooltip content={widget.is_enabled ? 'Disable widget' : 'Enable widget'}>
              <Button
                onClick={() => onToggle(!widget.is_enabled)}
                loading={isToggling}
                variant={widget.is_enabled ? undefined : 'primary'}
              >
                {widget.is_enabled ? 'Disable' : 'Enable'}
              </Button>
            </Tooltip>
            <Button onClick={onConfigure} icon={SettingsIcon}>
              Configure
            </Button>
          </InlineStack>
        </InlineStack>

        {/* Preview */}
        <Box padding="300" background="bg-surface-secondary" borderRadius="200">
          <InlineStack align="center">
            <WidgetPreview widget={widget} metadata={metadata} />
          </InlineStack>
        </Box>
      </BlockStack>
    </Card>
  );
}

/** Widget Preview Component */
function WidgetPreview({ widget, metadata }: { widget: Widget; metadata: WidgetMetadata }) {
  const { config, widget_type } = widget;
  const styling = config.styling || {};
  const content = config.content || {};

  const baseStyle: React.CSSProperties = {
    backgroundColor: styling.background_color || '#000000',
    color: styling.text_color || '#ffffff',
    borderRadius: styling.border_radius || 12,
    padding: '12px 16px',
    fontSize: styling.font_size || 14,
    boxShadow: styling.shadow !== false ? '0 4px 12px rgba(0,0,0,0.15)' : 'none',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  };

  switch (widget_type) {
    case 'points_balance':
      return (
        <div style={baseStyle}>
          {content.show_icon !== false && <span>&#11088;</span>}
          <span style={{ fontWeight: 600 }}>
            {content.label_text || 'Your Points'}: {metadata.preview}
          </span>
        </div>
      );

    case 'tier_badge':
      const badgeStyle: React.CSSProperties = {
        ...baseStyle,
        borderRadius:
          styling.badge_style === 'square'
            ? 4
            : styling.badge_style === 'rounded'
            ? 8
            : 20,
        padding: '6px 12px',
      };
      return (
        <div style={badgeStyle}>
          {content.show_tier_icon !== false && <span>&#128081;</span>}
          {content.show_tier_name !== false && (
            <span style={{ fontWeight: 600 }}>{metadata.preview}</span>
          )}
        </div>
      );

    case 'rewards_launcher':
      const launcherStyle: React.CSSProperties = {
        width: styling.size || 56,
        height: styling.size || 56,
        borderRadius: '50%',
        backgroundColor: styling.background_color || '#e85d27',
        color: styling.icon_color || '#ffffff',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 24,
        boxShadow: styling.shadow !== false ? '0 4px 12px rgba(0,0,0,0.15)' : 'none',
        cursor: 'pointer',
      };
      const iconMap: Record<string, string> = {
        gift: '\u{1F381}',
        star: '\u{2B50}',
        heart: '\u{2764}',
        trophy: '\u{1F3C6}',
        coin: '\u{1FA99}',
      };
      return (
        <div style={launcherStyle}>
          {iconMap[content.icon || 'gift'] || '\u{1F381}'}
        </div>
      );

    case 'referral_prompt':
      const promptStyle: React.CSSProperties = {
        ...baseStyle,
        flexDirection: 'column',
        alignItems: 'flex-start',
        gap: '8px',
        maxWidth: '300px',
      };
      return (
        <div style={promptStyle}>
          <span style={{ fontWeight: 600, fontSize: 16 }}>
            {content.title || 'Share & Earn!'}
          </span>
          <span style={{ fontSize: 12, opacity: 0.9 }}>
            {content.description || 'Refer a friend and you both get rewarded'}
          </span>
          <span
            style={{
              marginTop: 4,
              padding: '6px 12px',
              backgroundColor: styling.accent_color || '#e85d27',
              borderRadius: 4,
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            {content.cta_text || 'Get Your Link'}
          </span>
        </div>
      );

    default:
      return null;
  }
}

/** Widget Configuration Modal */
function WidgetConfigModal({
  widget,
  metadata,
  open,
  onClose,
  onSave,
  onReset,
  isSaving,
}: {
  widget: Widget;
  metadata: WidgetMetadata;
  open: boolean;
  onClose: () => void;
  onSave: (config: WidgetConfig) => void;
  onReset: () => void;
  isSaving: boolean;
}) {
  const [config, setConfig] = useState<WidgetConfig>(widget.config);
  const [showPositionSelector, setShowPositionSelector] = useState(false);

  // Update local config when widget changes
  React.useEffect(() => {
    setConfig(widget.config);
  }, [widget.config]);

  const updateConfig = useCallback(
    (section: keyof WidgetConfig, key: string, value: unknown) => {
      setConfig((prev) => ({
        ...prev,
        [section]: {
          ...prev[section],
          [key]: value,
        },
      }));
    },
    []
  );

  const handleSave = () => {
    onSave(config);
  };

  const renderPositionSettings = () => {
    const position = config.position || {};
    const isFixed = position.type === 'fixed' || widget.widget_type !== 'tier_badge';

    return (
      <BlockStack gap="400">
        <Text as="h3" variant="headingMd">Position</Text>

        {isFixed ? (
          <>
            <Select
              label="Position"
              options={POSITION_OPTIONS}
              value={position.location || 'bottom-right'}
              onChange={(v) => updateConfig('position', 'location', v)}
            />

            <Button
              onClick={() => setShowPositionSelector(!showPositionSelector)}
              icon={showPositionSelector ? ChevronUpIcon : ChevronDownIcon}
            >
              {showPositionSelector ? 'Hide Visual Selector' : 'Use Visual Selector'}
            </Button>

            <Collapsible open={showPositionSelector} id="position-selector">
              <Box paddingBlockStart="200">
                <PositionSelector
                  value={(position.location as WidgetPosition) || 'bottom-right'}
                  onChange={(pos) => updateConfig('position', 'location', pos)}
                  showTabPositions={false}
                  helpText="Click a position to place your widget"
                />
              </Box>
            </Collapsible>

            <FormLayout.Group>
              <TextField
                label="Horizontal Offset (px)"
                type="number"
                value={String(position.offset_x || 20)}
                onChange={(v) => updateConfig('position', 'offset_x', parseInt(v))}
                autoComplete="off"
              />
              <TextField
                label="Vertical Offset (px)"
                type="number"
                value={String(position.offset_y || 20)}
                onChange={(v) => updateConfig('position', 'offset_y', parseInt(v))}
                autoComplete="off"
              />
            </FormLayout.Group>
          </>
        ) : (
          <>
            <TextField
              label="CSS Selector"
              value={position.selector || '.customer-info'}
              onChange={(v) => updateConfig('position', 'selector', v)}
              autoComplete="off"
              helpText="Target element for inline placement"
            />
            <Select
              label="Placement"
              options={[
                { label: 'After Element', value: 'after' },
                { label: 'Before Element', value: 'before' },
                { label: 'Inside (Append)', value: 'append' },
                { label: 'Inside (Prepend)', value: 'prepend' },
              ]}
              value={position.placement || 'after'}
              onChange={(v) => updateConfig('position', 'placement', v)}
            />
          </>
        )}
      </BlockStack>
    );
  };

  const renderStylingSettings = () => {
    const styling = config.styling || {};

    return (
      <BlockStack gap="400">
        <Text as="h3" variant="headingMd">Styling</Text>

        <InlineStack gap="400" wrap>
          <Box minWidth="200px">
            <ColorPicker
              label="Background Color"
              value={styling.background_color || '#000000'}
              onChange={(v) => updateConfig('styling', 'background_color', v)}
              colorType="background"
            />
          </Box>
          <Box minWidth="200px">
            <ColorPicker
              label="Text Color"
              value={styling.text_color || '#ffffff'}
              onChange={(v) => updateConfig('styling', 'text_color', v)}
              colorType="text"
            />
          </Box>
        </InlineStack>

        {(widget.widget_type === 'rewards_launcher' ||
          widget.widget_type === 'referral_prompt') && (
          <Box minWidth="200px">
            <ColorPicker
              label={widget.widget_type === 'rewards_launcher' ? 'Icon Color' : 'Accent Color'}
              value={
                widget.widget_type === 'rewards_launcher'
                  ? styling.icon_color || '#ffffff'
                  : styling.accent_color || '#e85d27'
              }
              onChange={(v) =>
                updateConfig(
                  'styling',
                  widget.widget_type === 'rewards_launcher' ? 'icon_color' : 'accent_color',
                  v
                )
              }
              colorType="primary"
            />
          </Box>
        )}

        <FormLayout.Group>
          <TextField
            label="Border Radius (px)"
            type="number"
            value={String(styling.border_radius || 12)}
            onChange={(v) => updateConfig('styling', 'border_radius', parseInt(v))}
            autoComplete="off"
          />
          {widget.widget_type !== 'rewards_launcher' && (
            <TextField
              label="Font Size (px)"
              type="number"
              value={String(styling.font_size || 14)}
              onChange={(v) => updateConfig('styling', 'font_size', parseInt(v))}
              autoComplete="off"
            />
          )}
          {widget.widget_type === 'rewards_launcher' && (
            <TextField
              label="Button Size (px)"
              type="number"
              value={String(styling.size || 56)}
              onChange={(v) => updateConfig('styling', 'size', parseInt(v))}
              autoComplete="off"
            />
          )}
        </FormLayout.Group>

        {widget.widget_type === 'tier_badge' && (
          <Select
            label="Badge Style"
            options={BADGE_STYLE_OPTIONS}
            value={styling.badge_style || 'pill'}
            onChange={(v) => updateConfig('styling', 'badge_style', v)}
          />
        )}

        <Checkbox
          label="Show Shadow"
          checked={styling.shadow !== false}
          onChange={(v) => updateConfig('styling', 'shadow', v)}
        />
      </BlockStack>
    );
  };

  const renderContentSettings = () => {
    const content = config.content || {};

    switch (widget.widget_type) {
      case 'points_balance':
        return (
          <BlockStack gap="400">
            <Text as="h3" variant="headingMd">Content</Text>
            <Checkbox
              label="Show Icon"
              checked={content.show_icon !== false}
              onChange={(v) => updateConfig('content', 'show_icon', v)}
            />
            <Checkbox
              label="Show Label"
              checked={content.show_label !== false}
              onChange={(v) => updateConfig('content', 'show_label', v)}
            />
            <TextField
              label="Label Text"
              value={content.label_text || 'Your Points'}
              onChange={(v) => updateConfig('content', 'label_text', v)}
              autoComplete="off"
            />
            <Checkbox
              label="Show Tier Indicator"
              checked={content.show_tier_indicator !== false}
              onChange={(v) => updateConfig('content', 'show_tier_indicator', v)}
            />
          </BlockStack>
        );

      case 'tier_badge':
        return (
          <BlockStack gap="400">
            <Text as="h3" variant="headingMd">Content</Text>
            <Checkbox
              label="Show Tier Name"
              checked={content.show_tier_name !== false}
              onChange={(v) => updateConfig('content', 'show_tier_name', v)}
            />
            <Checkbox
              label="Show Tier Icon"
              checked={content.show_tier_icon !== false}
              onChange={(v) => updateConfig('content', 'show_tier_icon', v)}
            />
            <Checkbox
              label="Show Progress Bar"
              checked={content.show_progress_bar === true}
              onChange={(v) => updateConfig('content', 'show_progress_bar', v)}
            />
          </BlockStack>
        );

      case 'rewards_launcher':
        return (
          <BlockStack gap="400">
            <Text as="h3" variant="headingMd">Content</Text>
            <Select
              label="Icon"
              options={ICON_OPTIONS}
              value={content.icon || 'gift'}
              onChange={(v) => updateConfig('content', 'icon', v)}
            />
            <TextField
              label="Tooltip Text"
              value={content.tooltip_text || 'View Rewards'}
              onChange={(v) => updateConfig('content', 'tooltip_text', v)}
              autoComplete="off"
            />
            <Checkbox
              label="Show Notification Badge"
              checked={content.show_notification_badge !== false}
              onChange={(v) => updateConfig('content', 'show_notification_badge', v)}
              helpText="Shows a badge when there are available rewards"
            />
          </BlockStack>
        );

      case 'referral_prompt':
        return (
          <BlockStack gap="400">
            <Text as="h3" variant="headingMd">Content</Text>
            <TextField
              label="Title"
              value={content.title || 'Share & Earn!'}
              onChange={(v) => updateConfig('content', 'title', v)}
              autoComplete="off"
            />
            <TextField
              label="Description"
              value={content.description || 'Refer a friend and you both get rewarded'}
              onChange={(v) => updateConfig('content', 'description', v)}
              autoComplete="off"
              multiline={2}
            />
            <TextField
              label="CTA Button Text"
              value={content.cta_text || 'Get Your Link'}
              onChange={(v) => updateConfig('content', 'cta_text', v)}
              autoComplete="off"
            />
            <Checkbox
              label="Show Reward Amount"
              checked={content.show_reward_amount !== false}
              onChange={(v) => updateConfig('content', 'show_reward_amount', v)}
            />
          </BlockStack>
        );

      default:
        return null;
    }
  };

  const renderBehaviorSettings = () => {
    const behavior = config.behavior || {};

    return (
      <BlockStack gap="400">
        <Text as="h3" variant="headingMd">Behavior</Text>

        <Checkbox
          label="Show on Mobile"
          checked={behavior.show_on_mobile !== false}
          onChange={(v) => updateConfig('behavior', 'show_on_mobile', v)}
        />

        {widget.widget_type === 'points_balance' && (
          <Checkbox
            label="Animate on Update"
            checked={behavior.animate_on_update !== false}
            onChange={(v) => updateConfig('behavior', 'animate_on_update', v)}
          />
        )}

        {widget.widget_type === 'rewards_launcher' && (
          <Select
            label="Panel Position"
            options={[
              { label: 'Right', value: 'right' },
              { label: 'Left', value: 'left' },
              { label: 'Center', value: 'center' },
            ]}
            value={behavior.panel_position || 'right'}
            onChange={(v) => updateConfig('behavior', 'panel_position', v)}
          />
        )}

        {widget.widget_type === 'referral_prompt' && (
          <>
            <Select
              label="Trigger"
              options={TRIGGER_OPTIONS}
              value={behavior.trigger || 'scroll'}
              onChange={(v) => updateConfig('behavior', 'trigger', v)}
            />
            <TextField
              label={
                behavior.trigger === 'scroll'
                  ? 'Scroll Percentage'
                  : behavior.trigger === 'delay'
                  ? 'Delay (seconds)'
                  : 'Trigger Value'
              }
              type="number"
              value={String(behavior.trigger_value || 50)}
              onChange={(v) => updateConfig('behavior', 'trigger_value', parseInt(v))}
              autoComplete="off"
            />
            <Checkbox
              label="Show Once Per Session"
              checked={behavior.show_once_per_session !== false}
              onChange={(v) => updateConfig('behavior', 'show_once_per_session', v)}
            />
            <Checkbox
              label="Dismissible"
              checked={behavior.dismissible !== false}
              onChange={(v) => updateConfig('behavior', 'dismissible', v)}
            />
          </>
        )}
      </BlockStack>
    );
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Configure ${metadata.name}`}
      primaryAction={{
        content: 'Save',
        onAction: handleSave,
        loading: isSaving,
      }}
      secondaryActions={[
        {
          content: 'Reset to Defaults',
          onAction: onReset,
          icon: RefreshIcon,
        },
        {
          content: 'Cancel',
          onAction: onClose,
        },
      ]}
      size="large"
    >
      <Modal.Section>
        <BlockStack gap="600">
          {/* Live Preview */}
          <Card>
            <BlockStack gap="200">
              <Text as="h3" variant="headingMd">Preview</Text>
              <Box padding="400" background="bg-surface-secondary" borderRadius="200">
                <InlineStack align="center">
                  <WidgetPreview
                    widget={{ ...widget, config }}
                    metadata={metadata}
                  />
                </InlineStack>
              </Box>
            </BlockStack>
          </Card>

          {/* Position Settings */}
          {renderPositionSettings()}

          <Divider />

          {/* Styling Settings */}
          {renderStylingSettings()}

          <Divider />

          {/* Content Settings */}
          {renderContentSettings()}

          <Divider />

          {/* Behavior Settings */}
          {renderBehaviorSettings()}
        </BlockStack>
      </Modal.Section>
    </Modal>
  );
}

/** Main Component */
export function EmbeddedWidgets({ shop }: EmbeddedWidgetsProps) {
  const [selectedWidget, setSelectedWidget] = useState<WidgetType | null>(null);
  const [togglingWidget, setTogglingWidget] = useState<WidgetType | null>(null);

  const queryClient = useQueryClient();

  // Fetch all widgets
  const { data, isLoading, error } = useQuery({
    queryKey: ['widgets', shop],
    queryFn: () => fetchWidgets(shop),
    enabled: !!shop,
  });

  // Toggle widget mutation
  const toggleMutation = useMutation({
    mutationFn: ({ type, enabled }: { type: WidgetType; enabled: boolean }) =>
      toggleWidget(shop, type, enabled),
    onMutate: ({ type }) => setTogglingWidget(type),
    onSettled: () => setTogglingWidget(null),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['widgets', shop] });
    },
  });

  // Update widget mutation
  const updateMutation = useMutation({
    mutationFn: ({ type, config }: { type: WidgetType; config: WidgetConfig }) =>
      updateWidget(shop, type, { config }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['widgets', shop] });
      setSelectedWidget(null);
    },
  });

  // Reset widget mutation
  const resetMutation = useMutation({
    mutationFn: (type: WidgetType) => resetWidget(shop, type),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['widgets', shop] });
    },
  });

  const widgets = data?.widgets || [];
  const widgetMap = new Map(widgets.map((w) => [w.widget_type, w]));

  const handleToggle = (type: WidgetType, enabled: boolean) => {
    toggleMutation.mutate({ type, enabled });
  };

  const handleSave = (type: WidgetType, config: WidgetConfig) => {
    updateMutation.mutate({ type, config });
  };

  const handleReset = (type: WidgetType) => {
    resetMutation.mutate(type);
  };

  const selectedWidgetData = selectedWidget ? widgetMap.get(selectedWidget) : null;
  const selectedWidgetMetadata = selectedWidget ? WIDGET_METADATA[selectedWidget] : null;

  // Count enabled widgets
  const enabledCount = widgets.filter((w) => w.is_enabled).length;

  if (isLoading) {
    return (
      <Page title="Widgets">
        <Card>
          <BlockStack gap="400" inlineAlign="center">
            <Spinner accessibilityLabel="Loading widgets" size="large" />
            <Text as="p">Loading widgets...</Text>
          </BlockStack>
        </Card>
      </Page>
    );
  }

  if (error) {
    return (
      <Page title="Widgets">
        <Banner tone="critical">
          Failed to load widgets. Please try again.
        </Banner>
      </Page>
    );
  }

  return (
    <Page
      title="Widgets"
      subtitle="Configure customer-facing widgets for your store"
      primaryAction={{
        content: 'View Store',
        icon: ViewIcon,
        url: `https://${shop}`,
        external: true,
      }}
    >
      <Layout>
        <Layout.Section>
          <Banner tone="info">
            <Text as="p">
              Widgets appear on your storefront to engage customers. You have{' '}
              <Text as="span" fontWeight="bold">{enabledCount}</Text> of{' '}
              <Text as="span" fontWeight="bold">{Object.keys(WIDGET_METADATA).length}</Text>{' '}
              widgets enabled.
            </Text>
          </Banner>
        </Layout.Section>

        <Layout.Section>
          <BlockStack gap="400">
            {Object.values(WIDGET_METADATA).map((metadata) => {
              const widget = widgetMap.get(metadata.type);
              if (!widget) return null;

              return (
                <WidgetCard
                  key={metadata.type}
                  widget={widget}
                  metadata={metadata}
                  onToggle={(enabled) => handleToggle(metadata.type, enabled)}
                  onConfigure={() => setSelectedWidget(metadata.type)}
                  isToggling={togglingWidget === metadata.type}
                />
              );
            })}
          </BlockStack>
        </Layout.Section>

        <Layout.Section variant="oneThird">
          <Card>
            <BlockStack gap="300">
              <Text as="h3" variant="headingMd">Tips</Text>
              <BlockStack gap="200">
                <Text as="p" variant="bodySm">
                  Enable the Points Balance widget to show customers their loyalty status.
                </Text>
                <Text as="p" variant="bodySm">
                  The Rewards Launcher gives quick access to your rewards program.
                </Text>
                <Text as="p" variant="bodySm">
                  Use the Referral Prompt to encourage word-of-mouth marketing.
                </Text>
                <Text as="p" variant="bodySm">
                  Match widget colors to your store theme for a cohesive look.
                </Text>
              </BlockStack>
            </BlockStack>
          </Card>

          <Card>
            <BlockStack gap="300">
              <Text as="h3" variant="headingMd">Need Help?</Text>
              <Text as="p" variant="bodySm">
                Check our documentation for detailed widget setup guides.
              </Text>
              <Button url="/app/settings" fullWidth>
                Go to Settings
              </Button>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>

      {/* Configuration Modal */}
      {selectedWidgetData && selectedWidgetMetadata && (
        <WidgetConfigModal
          widget={selectedWidgetData}
          metadata={selectedWidgetMetadata}
          open={!!selectedWidget}
          onClose={() => setSelectedWidget(null)}
          onSave={(config) => handleSave(selectedWidget!, config)}
          onReset={() => handleReset(selectedWidget!)}
          isSaving={updateMutation.isPending}
        />
      )}
    </Page>
  );
}

export default EmbeddedWidgets;
