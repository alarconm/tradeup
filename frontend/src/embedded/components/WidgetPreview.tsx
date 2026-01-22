/**
 * WidgetPreview - Live preview component for widget builder
 *
 * Features:
 * - Real-time preview updates as settings change
 * - Mobile/desktop toggle for responsive preview
 * - Mock store page context
 * - Accurate representation of final widget output
 * - Multiple widget types support
 */

import React, { useState, useMemo } from 'react';
import {
  Box,
  Text,
  BlockStack,
  InlineStack,
  Button,
  ButtonGroup,
  Badge,
  Tooltip,
} from '@shopify/polaris';
import {
  MobileIcon,
  DesktopIcon,
  RefreshIcon,
} from '@shopify/polaris-icons';

export type PreviewDevice = 'desktop' | 'mobile';

export interface WidgetAppearance {
  primary_color?: string;
  text_color?: string;
  background_color?: string;
  border_radius?: number;
  shadow?: boolean;
  animation?: string;
}

export interface WidgetLauncher {
  icon?: string;
  text?: string;
  show_points_badge?: boolean;
  size?: string;
}

export interface WidgetPanel {
  show_points_balance?: boolean;
  show_tier_progress?: boolean;
  show_available_rewards?: boolean;
  show_earning_rules?: boolean;
  show_referral_link?: boolean;
  max_rewards_shown?: number;
  welcome_message?: string;
  guest_message?: string;
}

export interface WidgetBranding {
  show_logo?: boolean;
  program_name?: string;
  powered_by?: boolean;
}

export interface WidgetConfig {
  enabled?: boolean;
  position?: string;
  theme?: string;
  appearance?: WidgetAppearance;
  launcher?: WidgetLauncher;
  panel?: WidgetPanel;
  branding?: WidgetBranding;
  display_rules?: {
    hide_on_mobile?: boolean;
    show_only_for_members?: boolean;
    hide_during_checkout?: boolean;
  };
}

interface WidgetPreviewProps {
  /** Current widget configuration */
  config: WidgetConfig;
  /** Show device toggle buttons */
  showDeviceToggle?: boolean;
  /** Initial device mode */
  defaultDevice?: PreviewDevice;
  /** Callback when device changes */
  onDeviceChange?: (device: PreviewDevice) => void;
  /** Show expanded panel preview */
  showExpandedPanel?: boolean;
  /** Custom height for the preview container */
  height?: number;
  /** Show page context (mock store elements) */
  showPageContext?: boolean;
  /** Store name for branding */
  storeName?: string;
}

// Icon mapping for launcher icons
const ICON_MAP: Record<string, string> = {
  gift: '\u{1F381}',
  star: '\u{2B50}',
  heart: '\u{2764}\u{FE0F}',
  trophy: '\u{1F3C6}',
  custom: '\u{1F381}',
};

// Device dimensions
const DEVICE_DIMENSIONS = {
  desktop: { width: 480, height: 320 },
  mobile: { width: 220, height: 380 },
};

/**
 * Browser chrome component for realistic preview
 */
function BrowserChrome({
  device,
  storeName,
}: {
  device: PreviewDevice;
  storeName: string;
}) {
  return (
    <div
      style={{
        height: device === 'mobile' ? '24px' : '28px',
        backgroundColor: '#ffffff',
        borderBottom: '1px solid #e1e3e5',
        display: 'flex',
        alignItems: 'center',
        padding: device === 'mobile' ? '0 8px' : '0 12px',
        gap: '6px',
      }}
    >
      {device === 'desktop' && (
        <>
          {/* Window controls */}
          <div
            style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              backgroundColor: '#ed6a5e',
            }}
          />
          <div
            style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              backgroundColor: '#f4bf4f',
            }}
          />
          <div
            style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              backgroundColor: '#61c554',
            }}
          />
        </>
      )}
      {/* URL bar */}
      <div
        style={{
          flex: 1,
          marginLeft: device === 'desktop' ? '12px' : '0',
          height: device === 'mobile' ? '14px' : '16px',
          backgroundColor: '#f6f6f7',
          borderRadius: '4px',
          display: 'flex',
          alignItems: 'center',
          paddingLeft: '8px',
          fontSize: device === 'mobile' ? '8px' : '10px',
          color: '#8c9196',
          overflow: 'hidden',
        }}
      >
        {storeName}.myshopify.com
      </div>
    </div>
  );
}

/**
 * Mock store header component
 */
function MockStoreHeader({ device }: { device: PreviewDevice }) {
  const isMobile = device === 'mobile';

  return (
    <div style={{ marginBottom: isMobile ? '8px' : '12px' }}>
      {/* Logo placeholder */}
      <div
        style={{
          height: isMobile ? '10px' : '14px',
          width: isMobile ? '60px' : '100px',
          backgroundColor: '#374151',
          borderRadius: '2px',
          marginBottom: isMobile ? '6px' : '8px',
        }}
      />
      {/* Navigation */}
      <div
        style={{
          display: 'flex',
          gap: isMobile ? '4px' : '8px',
          flexWrap: 'wrap',
        }}
      >
        {(isMobile ? [1, 2, 3] : [1, 2, 3, 4, 5]).map((i) => (
          <div
            key={i}
            style={{
              height: isMobile ? '6px' : '8px',
              width: isMobile ? '24px' : '40px',
              backgroundColor: '#e5e7eb',
              borderRadius: '2px',
            }}
          />
        ))}
      </div>
    </div>
  );
}

/**
 * Mock store content (product grid)
 */
function MockStoreContent({ device }: { device: PreviewDevice }) {
  const isMobile = device === 'mobile';
  const gridCols = isMobile ? 2 : 3;

  return (
    <div style={{ flex: 1 }}>
      {/* Section title */}
      <div
        style={{
          height: isMobile ? '8px' : '12px',
          width: isMobile ? '80px' : '120px',
          backgroundColor: '#374151',
          borderRadius: '2px',
          marginBottom: isMobile ? '8px' : '12px',
        }}
      />
      {/* Product grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${gridCols}, 1fr)`,
          gap: isMobile ? '6px' : '10px',
        }}
      >
        {[1, 2, 3, 4, 5, 6].slice(0, isMobile ? 4 : 6).map((i) => (
          <div
            key={i}
            style={{
              backgroundColor: '#f3f4f6',
              borderRadius: '4px',
              aspectRatio: '1',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            {/* Product image placeholder */}
            <div
              style={{
                flex: 1,
                backgroundColor: '#e5e7eb',
              }}
            />
            {/* Product info */}
            <div style={{ padding: isMobile ? '3px' : '6px' }}>
              <div
                style={{
                  height: isMobile ? '4px' : '6px',
                  width: '70%',
                  backgroundColor: '#d1d5db',
                  borderRadius: '2px',
                  marginBottom: isMobile ? '2px' : '4px',
                }}
              />
              <div
                style={{
                  height: isMobile ? '4px' : '6px',
                  width: '40%',
                  backgroundColor: '#9ca3af',
                  borderRadius: '2px',
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Widget launcher button preview
 */
function WidgetLauncherPreview({
  config,
  device,
  onClick,
}: {
  config: WidgetConfig;
  device: PreviewDevice;
  onClick?: () => void;
}) {
  const isMobile = device === 'mobile';
  const position = config.position || 'bottom-right';
  const appearance = config.appearance || {};
  const launcher = config.launcher || {};

  // Check if widget should be hidden on mobile
  if (isMobile && config.display_rules?.hide_on_mobile) {
    return null;
  }

  // Determine position styles
  const getPositionStyles = (): React.CSSProperties => {
    const offset = isMobile ? 8 : 16;
    const baseStyles: React.CSSProperties = {
      position: 'absolute',
      zIndex: 10,
    };

    if (position.includes('tab')) {
      const isLeft = position === 'left-tab';
      return {
        ...baseStyles,
        [isLeft ? 'left' : 'right']: 0,
        top: '50%',
        transform: 'translateY(-50%)',
      };
    }

    const isTop = position.includes('top');
    const isLeft = position.includes('left');
    const isCenter = position === 'center';

    return {
      ...baseStyles,
      ...(isCenter
        ? { left: '50%', top: '50%', transform: 'translate(-50%, -50%)' }
        : {
            [isTop ? 'top' : 'bottom']: offset,
            [isLeft ? 'left' : 'right']: offset,
          }),
    };
  };

  // Determine launcher size
  const getSize = () => {
    const baseSize =
      launcher.size === 'large' ? 56 : launcher.size === 'small' ? 40 : 48;
    return isMobile ? Math.round(baseSize * 0.75) : baseSize;
  };

  // Tab position styling
  const isTabPosition = position.includes('tab');
  const size = getSize();

  const buttonStyles: React.CSSProperties = isTabPosition
    ? {
        width: isMobile ? 16 : 20,
        height: isMobile ? 60 : 80,
        borderRadius:
          position === 'left-tab' ? '0 8px 8px 0' : '8px 0 0 8px',
        writingMode: 'vertical-rl',
        textOrientation: 'mixed',
        fontSize: isMobile ? 8 : 10,
        fontWeight: 600,
      }
    : {
        width: size,
        height: size,
        borderRadius: appearance.border_radius || size / 2,
        fontSize: isMobile ? 16 : 20,
      };

  return (
    <div style={getPositionStyles()}>
      <div
        onClick={onClick}
        role="button"
        tabIndex={0}
        style={{
          ...buttonStyles,
          backgroundColor: appearance.primary_color || '#e85d27',
          color: appearance.text_color || '#ffffff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow:
            appearance.shadow !== false
              ? '0 4px 12px rgba(0,0,0,0.15)'
              : 'none',
          cursor: 'pointer',
          transition: 'all 0.2s ease',
        }}
      >
        {isTabPosition
          ? config.branding?.program_name || 'Rewards'
          : ICON_MAP[launcher.icon || 'gift'] || ICON_MAP.gift}
        {launcher.show_points_badge && !isTabPosition && (
          <div
            style={{
              position: 'absolute',
              top: -4,
              right: -4,
              backgroundColor: '#ef4444',
              color: '#ffffff',
              fontSize: isMobile ? 8 : 10,
              fontWeight: 600,
              padding: '2px 6px',
              borderRadius: '10px',
              minWidth: isMobile ? 16 : 20,
              textAlign: 'center',
            }}
          >
            500
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Expanded widget panel preview
 */
function WidgetPanelPreview({
  config,
  device,
  onClose,
}: {
  config: WidgetConfig;
  device: PreviewDevice;
  onClose?: () => void;
}) {
  const isMobile = device === 'mobile';
  const appearance = config.appearance || {};
  const panel = config.panel || {};
  const branding = config.branding || {};
  const position = config.position || 'bottom-right';

  // Panel positioning
  const getPanelPosition = (): React.CSSProperties => {
    const isRight = position.includes('right') || position === 'right-tab';
    return {
      position: 'absolute',
      [isRight ? 'right' : 'left']: isMobile ? 8 : 16,
      bottom: isMobile ? 60 : 80,
      width: isMobile ? 'calc(100% - 16px)' : 280,
      maxHeight: isMobile ? 240 : 320,
    };
  };

  return (
    <div
      style={{
        ...getPanelPosition(),
        backgroundColor: appearance.background_color || '#ffffff',
        borderRadius: appearance.border_radius || 12,
        boxShadow:
          appearance.shadow !== false
            ? '0 8px 32px rgba(0,0,0,0.15)'
            : 'none',
        overflow: 'hidden',
        zIndex: 20,
      }}
    >
      {/* Panel header */}
      <div
        style={{
          backgroundColor: appearance.primary_color || '#e85d27',
          color: appearance.text_color || '#ffffff',
          padding: isMobile ? '12px' : '16px',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span
            style={{
              fontWeight: 600,
              fontSize: isMobile ? 14 : 16,
            }}
          >
            {branding.program_name || 'Rewards'}
          </span>
          {onClose && (
            <button
              onClick={onClose}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'inherit',
                cursor: 'pointer',
                fontSize: isMobile ? 16 : 18,
                padding: 0,
              }}
            >
              x
            </button>
          )}
        </div>
        {panel.welcome_message && (
          <div
            style={{
              fontSize: isMobile ? 11 : 12,
              opacity: 0.9,
              marginTop: 4,
            }}
          >
            {panel.welcome_message}
          </div>
        )}
      </div>

      {/* Panel content */}
      <div style={{ padding: isMobile ? '12px' : '16px' }}>
        {/* Points balance */}
        {panel.show_points_balance !== false && (
          <div
            style={{
              textAlign: 'center',
              marginBottom: isMobile ? 12 : 16,
            }}
          >
            <div
              style={{
                fontSize: isMobile ? 24 : 32,
                fontWeight: 700,
                color: appearance.primary_color || '#e85d27',
              }}
            >
              500
            </div>
            <div
              style={{
                fontSize: isMobile ? 11 : 12,
                color: '#6b7280',
              }}
            >
              Available Points
            </div>
          </div>
        )}

        {/* Tier progress */}
        {panel.show_tier_progress !== false && (
          <div
            style={{
              marginBottom: isMobile ? 12 : 16,
              padding: isMobile ? 8 : 12,
              backgroundColor: '#f9fafb',
              borderRadius: 8,
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: isMobile ? 10 : 11,
                marginBottom: 6,
              }}
            >
              <span style={{ color: '#6b7280' }}>Silver</span>
              <span style={{ color: '#6b7280' }}>Gold</span>
            </div>
            <div
              style={{
                height: 6,
                backgroundColor: '#e5e7eb',
                borderRadius: 3,
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: '60%',
                  height: '100%',
                  backgroundColor: appearance.primary_color || '#e85d27',
                  borderRadius: 3,
                }}
              />
            </div>
            <div
              style={{
                fontSize: isMobile ? 9 : 10,
                color: '#9ca3af',
                marginTop: 4,
                textAlign: 'center',
              }}
            >
              300 more points to Gold
            </div>
          </div>
        )}

        {/* Available rewards */}
        {panel.show_available_rewards !== false && (
          <div>
            <div
              style={{
                fontSize: isMobile ? 11 : 12,
                fontWeight: 600,
                marginBottom: 8,
                color: '#374151',
              }}
            >
              Available Rewards
            </div>
            {[1, 2].map((i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: isMobile ? '6px 0' : '8px 0',
                  borderBottom: '1px solid #f3f4f6',
                }}
              >
                <span
                  style={{
                    fontSize: isMobile ? 11 : 12,
                    color: '#374151',
                  }}
                >
                  ${i * 5} Off
                </span>
                <span
                  style={{
                    fontSize: isMobile ? 10 : 11,
                    color: '#9ca3af',
                  }}
                >
                  {i * 250} pts
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Powered by footer */}
      {branding.powered_by !== false && (
        <div
          style={{
            padding: isMobile ? '8px 12px' : '10px 16px',
            borderTop: '1px solid #f3f4f6',
            textAlign: 'center',
            fontSize: isMobile ? 9 : 10,
            color: '#9ca3af',
          }}
        >
          Powered by TradeUp
        </div>
      )}
    </div>
  );
}

/**
 * Main WidgetPreview component
 */
export function WidgetPreview({
  config,
  showDeviceToggle = true,
  defaultDevice = 'desktop',
  onDeviceChange,
  showExpandedPanel = false,
  height,
  showPageContext = true,
  storeName = 'your-store',
}: WidgetPreviewProps) {
  const [device, setDevice] = useState<PreviewDevice>(defaultDevice);
  const [isPanelOpen, setIsPanelOpen] = useState(showExpandedPanel);

  const handleDeviceChange = (newDevice: PreviewDevice) => {
    setDevice(newDevice);
    onDeviceChange?.(newDevice);
  };

  const dimensions = DEVICE_DIMENSIONS[device];
  const isMobile = device === 'mobile';

  // Check if widget is enabled
  const isEnabled = config.enabled !== false;

  // Memoize the widget preview for performance
  const widgetPreview = useMemo(() => {
    if (!isEnabled) return null;

    return (
      <>
        <WidgetLauncherPreview
          config={config}
          device={device}
          onClick={() => setIsPanelOpen(!isPanelOpen)}
        />
        {isPanelOpen && (
          <WidgetPanelPreview
            config={config}
            device={device}
            onClose={() => setIsPanelOpen(false)}
          />
        )}
      </>
    );
  }, [config, device, isPanelOpen, isEnabled]);

  return (
    <BlockStack gap="400">
      {/* Device toggle and controls */}
      {showDeviceToggle && (
        <InlineStack align="space-between" blockAlign="center">
          <InlineStack gap="200" blockAlign="center">
            <Text as="span" variant="headingSm">
              Preview
            </Text>
            <Badge tone={isEnabled ? 'success' : undefined}>
              {isEnabled ? 'Enabled' : 'Disabled'}
            </Badge>
          </InlineStack>
          <InlineStack gap="200">
            <ButtonGroup variant="segmented">
              <Tooltip content="Desktop preview">
                <Button
                  icon={DesktopIcon}
                  pressed={device === 'desktop'}
                  onClick={() => handleDeviceChange('desktop')}
                  accessibilityLabel="Desktop preview"
                />
              </Tooltip>
              <Tooltip content="Mobile preview">
                <Button
                  icon={MobileIcon}
                  pressed={device === 'mobile'}
                  onClick={() => handleDeviceChange('mobile')}
                  accessibilityLabel="Mobile preview"
                />
              </Tooltip>
            </ButtonGroup>
            <Tooltip content="Toggle panel">
              <Button
                icon={RefreshIcon}
                onClick={() => setIsPanelOpen(!isPanelOpen)}
                accessibilityLabel="Toggle panel preview"
              />
            </Tooltip>
          </InlineStack>
        </InlineStack>
      )}

      {/* Preview container */}
      <Box paddingBlockStart="200" paddingBlockEnd="200">
        <InlineStack align="center">
          <div
            style={{
              width: dimensions.width,
              height: height || dimensions.height,
              backgroundColor: '#f6f6f7',
              borderRadius: isMobile ? '24px' : '12px',
              border: isMobile ? '8px solid #1f2937' : '1px solid #e1e3e5',
              overflow: 'hidden',
              position: 'relative',
              boxShadow: '0 4px 20px rgba(0,0,0,0.1)',
              transition: 'all 0.3s ease',
            }}
          >
            {/* Browser chrome */}
            <BrowserChrome device={device} storeName={storeName} />

            {/* Page content */}
            <div
              style={{
                padding: isMobile ? '8px' : '16px',
                height: `calc(100% - ${isMobile ? 24 : 28}px)`,
                display: 'flex',
                flexDirection: 'column',
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              {showPageContext && (
                <>
                  <MockStoreHeader device={device} />
                  <MockStoreContent device={device} />
                </>
              )}

              {/* Widget overlay */}
              {widgetPreview}

              {/* Disabled overlay */}
              {!isEnabled && (
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    backgroundColor: 'rgba(255, 255, 255, 0.8)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 30,
                  }}
                >
                  <div
                    style={{
                      textAlign: 'center',
                      color: '#6b7280',
                    }}
                  >
                    <div style={{ fontSize: 24, marginBottom: 8 }}>
                      Widget Disabled
                    </div>
                    <div style={{ fontSize: 12 }}>
                      Enable the widget to see preview
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </InlineStack>
      </Box>

      {/* Device info */}
      <Text as="p" variant="bodySm" tone="subdued" alignment="center">
        {device === 'desktop'
          ? 'Desktop view (480px wide)'
          : 'Mobile view (375px wide)'}
        {isMobile &&
          config.display_rules?.hide_on_mobile &&
          ' - Widget hidden on mobile'}
      </Text>
    </BlockStack>
  );
}

export default WidgetPreview;
