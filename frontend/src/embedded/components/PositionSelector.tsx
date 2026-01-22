/**
 * PositionSelector - Visual component to select widget position on page
 *
 * Features:
 * - Visual page mockup showing position options
 * - Positions: top-left, top-right, bottom-left, bottom-right, center
 * - Click to select position
 * - Preview shows widget in selected position
 * - Works for floating widgets
 */

import { useCallback } from 'react';
import {
  Box,
  Text,
  BlockStack,
  InlineStack,
} from '@shopify/polaris';

export type WidgetPosition =
  | 'top-left'
  | 'top-right'
  | 'bottom-left'
  | 'bottom-right'
  | 'center'
  | 'left-tab'
  | 'right-tab';

interface PositionSelectorProps {
  /** Currently selected position */
  value: WidgetPosition;
  /** Callback when position changes */
  onChange: (position: WidgetPosition) => void;
  /** Widget appearance for preview */
  widgetPreview?: {
    icon?: string;
    primaryColor?: string;
    size?: number;
    borderRadius?: number;
  };
  /** Show tab positions (left/right side tabs) */
  showTabPositions?: boolean;
  /** Label displayed above the selector */
  label?: string;
  /** Help text displayed below */
  helpText?: string;
}

// Position configuration with visual coordinates
const POSITIONS: Record<WidgetPosition, { label: string; gridArea: string; justify: string; align: string }> = {
  'top-left': {
    label: 'Top Left',
    gridArea: '1 / 1',
    justify: 'flex-start',
    align: 'flex-start',
  },
  'top-right': {
    label: 'Top Right',
    gridArea: '1 / 3',
    justify: 'flex-end',
    align: 'flex-start',
  },
  'center': {
    label: 'Center',
    gridArea: '2 / 2',
    justify: 'center',
    align: 'center',
  },
  'bottom-left': {
    label: 'Bottom Left',
    gridArea: '3 / 1',
    justify: 'flex-start',
    align: 'flex-end',
  },
  'bottom-right': {
    label: 'Bottom Right',
    gridArea: '3 / 3',
    justify: 'flex-end',
    align: 'flex-end',
  },
  'left-tab': {
    label: 'Left Tab',
    gridArea: '2 / 1',
    justify: 'flex-start',
    align: 'center',
  },
  'right-tab': {
    label: 'Right Tab',
    gridArea: '2 / 3',
    justify: 'flex-end',
    align: 'center',
  },
};

// Default widget preview settings
const DEFAULT_PREVIEW = {
  icon: '🎁',
  primaryColor: '#e85d27',
  size: 48,
  borderRadius: 24,
};

/**
 * Position button that shows in the page mockup
 */
function PositionButton({
  position,
  isSelected,
  onClick,
  preview,
  isTabPosition,
}: {
  position: WidgetPosition;
  isSelected: boolean;
  onClick: () => void;
  preview: NonNullable<PositionSelectorProps['widgetPreview']>;
  isTabPosition: boolean;
}) {
  const config = POSITIONS[position];

  // Tab positions have different styling
  const tabStyles = isTabPosition ? {
    width: '20px',
    height: '60px',
    borderRadius: position === 'left-tab' ? '0 8px 8px 0' : '8px 0 0 8px',
    writingMode: 'vertical-rl' as const,
    textOrientation: 'mixed' as const,
    fontSize: '10px',
  } : {};

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Select ${config.label} position`}
      aria-pressed={isSelected}
      style={{
        gridArea: config.gridArea,
        display: 'flex',
        alignItems: config.align,
        justifyContent: config.justify,
        padding: '8px',
        background: 'transparent',
        border: 'none',
        cursor: 'pointer',
        transition: 'transform 0.15s ease',
      }}
    >
      <div
        style={{
          width: isTabPosition ? tabStyles.width : `${preview.size}px`,
          height: isTabPosition ? tabStyles.height : `${preview.size}px`,
          borderRadius: isTabPosition ? tabStyles.borderRadius : `${preview.borderRadius}px`,
          backgroundColor: isSelected ? preview.primaryColor : '#e1e3e5',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: isTabPosition ? '10px' : '18px',
          color: isSelected ? '#ffffff' : '#6d7175',
          boxShadow: isSelected ? '0 4px 12px rgba(0,0,0,0.15)' : '0 2px 4px rgba(0,0,0,0.1)',
          transform: isSelected ? 'scale(1.1)' : 'scale(1)',
          transition: 'all 0.2s ease',
          ...(isTabPosition ? {
            writingMode: tabStyles.writingMode,
            textOrientation: tabStyles.textOrientation,
          } : {}),
        }}
      >
        {isTabPosition ? (isSelected ? 'R' : '') : (isSelected ? preview.icon : '')}
      </div>
    </button>
  );
}

/**
 * Page mockup container that displays the store preview
 */
function PageMockup({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        maxWidth: '400px',
        aspectRatio: '4 / 3',
        backgroundColor: '#f6f6f7',
        borderRadius: '12px',
        border: '1px solid #e1e3e5',
        overflow: 'hidden',
      }}
    >
      {/* Browser chrome mockup */}
      <div
        style={{
          height: '28px',
          backgroundColor: '#ffffff',
          borderBottom: '1px solid #e1e3e5',
          display: 'flex',
          alignItems: 'center',
          padding: '0 12px',
          gap: '6px',
        }}
      >
        {/* Window controls */}
        <div style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#ed6a5e' }} />
        <div style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#f4bf4f' }} />
        <div style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#61c554' }} />
        {/* URL bar */}
        <div
          style={{
            flex: 1,
            marginLeft: '12px',
            height: '16px',
            backgroundColor: '#f6f6f7',
            borderRadius: '4px',
          }}
        />
      </div>

      {/* Page content mockup */}
      <div
        style={{
          padding: '16px',
          height: 'calc(100% - 28px)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header mockup */}
        <div
          style={{
            height: '12px',
            width: '40%',
            backgroundColor: '#d1d5db',
            borderRadius: '2px',
            marginBottom: '8px',
          }}
        />

        {/* Navigation mockup */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              style={{
                height: '8px',
                width: '32px',
                backgroundColor: '#e5e7eb',
                borderRadius: '2px',
              }}
            />
          ))}
        </div>

        {/* Content area with position grid */}
        <div
          style={{
            flex: 1,
            position: 'relative',
            backgroundColor: '#ffffff',
            borderRadius: '8px',
            border: '1px dashed #d1d5db',
          }}
        >
          {children}
        </div>
      </div>
    </div>
  );
}

/**
 * Legend showing position labels
 */
function PositionLegend({
  selectedPosition,
  positions,
}: {
  selectedPosition: WidgetPosition;
  positions: WidgetPosition[];
}) {
  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '8px',
        justifyContent: 'center',
      }}
    >
      {positions.map((pos) => (
        <div
          key={pos}
          style={{
            padding: '4px 12px',
            borderRadius: '16px',
            backgroundColor: selectedPosition === pos ? '#e85d27' : '#f6f6f7',
            color: selectedPosition === pos ? '#ffffff' : '#6d7175',
            fontSize: '12px',
            fontWeight: selectedPosition === pos ? 600 : 400,
            transition: 'all 0.2s ease',
          }}
        >
          {POSITIONS[pos].label}
        </div>
      ))}
    </div>
  );
}

export function PositionSelector({
  value,
  onChange,
  widgetPreview,
  showTabPositions = false,
  label = 'Widget Position',
  helpText = 'Select where the widget appears on your store',
}: PositionSelectorProps) {
  const preview = { ...DEFAULT_PREVIEW, ...widgetPreview };

  // Determine which positions to show
  const availablePositions: WidgetPosition[] = showTabPositions
    ? ['top-left', 'top-right', 'bottom-left', 'bottom-right', 'center', 'left-tab', 'right-tab']
    : ['top-left', 'top-right', 'bottom-left', 'bottom-right', 'center'];

  const handlePositionClick = useCallback((position: WidgetPosition) => {
    onChange(position);
  }, [onChange]);

  return (
    <BlockStack gap="400">
      {/* Label */}
      <Text as="span" variant="bodyMd" fontWeight="semibold">
        {label}
      </Text>

      {/* Page mockup with position selectors */}
      <Box paddingBlockStart="200" paddingBlockEnd="200">
        <InlineStack align="center">
          <PageMockup>
            <div
              style={{
                position: 'absolute',
                inset: 0,
                display: 'grid',
                gridTemplateColumns: '1fr 1fr 1fr',
                gridTemplateRows: '1fr 1fr 1fr',
              }}
            >
              {availablePositions.map((position) => (
                <PositionButton
                  key={position}
                  position={position}
                  isSelected={value === position}
                  onClick={() => handlePositionClick(position)}
                  preview={preview}
                  isTabPosition={position === 'left-tab' || position === 'right-tab'}
                />
              ))}
            </div>
          </PageMockup>
        </InlineStack>
      </Box>

      {/* Position legend */}
      <PositionLegend selectedPosition={value} positions={availablePositions} />

      {/* Help text */}
      {helpText && (
        <Text as="p" variant="bodySm" tone="subdued" alignment="center">
          {helpText}
        </Text>
      )}
    </BlockStack>
  );
}

export default PositionSelector;
