/**
 * ColorPicker - Color selection component for widget styling
 *
 * Features:
 * - Preset brand colors for quick selection
 * - Custom hex/RGB input for precise colors
 * - Live color preview
 * - Support for primary, secondary, text, and background colors
 * - Color validation
 */

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import {
  Box,
  Text,
  BlockStack,
  InlineStack,
  TextField,
  Popover,
  Button,
  Tooltip,
} from '@shopify/polaris';

/** Color type for categorization */
export type ColorType = 'primary' | 'secondary' | 'text' | 'background';

/** Preset color definition */
export interface PresetColor {
  name: string;
  value: string;
  category?: 'brand' | 'neutral' | 'accent';
}

interface ColorPickerProps {
  /** Current color value (hex format) */
  value: string;
  /** Callback when color changes */
  onChange: (color: string) => void;
  /** Label for the color picker */
  label?: string;
  /** Help text displayed below */
  helpText?: string;
  /** Type of color being selected (affects preset suggestions) */
  colorType?: ColorType;
  /** Custom preset colors to add */
  customPresets?: PresetColor[];
  /** Show RGB input option */
  showRgbInput?: boolean;
  /** Disable the picker */
  disabled?: boolean;
  /** Error message */
  error?: string;
}

// Default preset colors organized by category
const BRAND_PRESETS: PresetColor[] = [
  { name: 'TradeUp Orange', value: '#e85d27', category: 'brand' },
  { name: 'Shopify Green', value: '#008060', category: 'brand' },
  { name: 'Coral', value: '#ff7f50', category: 'brand' },
  { name: 'Royal Blue', value: '#4169e1', category: 'brand' },
  { name: 'Deep Purple', value: '#663399', category: 'brand' },
  { name: 'Teal', value: '#008080', category: 'brand' },
];

const NEUTRAL_PRESETS: PresetColor[] = [
  { name: 'White', value: '#ffffff', category: 'neutral' },
  { name: 'Light Gray', value: '#f6f6f7', category: 'neutral' },
  { name: 'Gray', value: '#8c9196', category: 'neutral' },
  { name: 'Dark Gray', value: '#303030', category: 'neutral' },
  { name: 'Charcoal', value: '#1a1a1a', category: 'neutral' },
  { name: 'Black', value: '#000000', category: 'neutral' },
];

const ACCENT_PRESETS: PresetColor[] = [
  { name: 'Success Green', value: '#2e844a', category: 'accent' },
  { name: 'Warning Yellow', value: '#ffc107', category: 'accent' },
  { name: 'Error Red', value: '#d72c0d', category: 'accent' },
  { name: 'Info Blue', value: '#2c6ecb', category: 'accent' },
  { name: 'Gold', value: '#d4af37', category: 'accent' },
  { name: 'Rose', value: '#e91e63', category: 'accent' },
];

// Color type specific recommendations
const COLOR_TYPE_PRESETS: Record<ColorType, PresetColor[]> = {
  primary: BRAND_PRESETS,
  secondary: [...NEUTRAL_PRESETS.slice(0, 3), ...ACCENT_PRESETS.slice(0, 3)],
  text: [
    { name: 'Dark Text', value: '#303030', category: 'neutral' },
    { name: 'Medium Text', value: '#6d7175', category: 'neutral' },
    { name: 'Light Text', value: '#ffffff', category: 'neutral' },
    { name: 'Muted Text', value: '#8c9196', category: 'neutral' },
    { name: 'Inverse Text', value: '#ffffff', category: 'neutral' },
    { name: 'Black', value: '#000000', category: 'neutral' },
  ],
  background: [
    { name: 'White', value: '#ffffff', category: 'neutral' },
    { name: 'Light Gray', value: '#f6f6f7', category: 'neutral' },
    { name: 'Cream', value: '#faf9f6', category: 'neutral' },
    { name: 'Light Blue', value: '#f0f8ff', category: 'neutral' },
    { name: 'Light Green', value: '#f0fff0', category: 'neutral' },
    { name: 'Dark', value: '#1a1a1a', category: 'neutral' },
  ],
};

/**
 * Validates hex color format
 */
function isValidHex(color: string): boolean {
  return /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/.test(color);
}

/**
 * Converts RGB to hex
 */
function rgbToHex(r: number, g: number, b: number): string {
  const toHex = (c: number) => {
    const hex = Math.max(0, Math.min(255, c)).toString(16);
    return hex.length === 1 ? '0' + hex : hex;
  };
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

/**
 * Converts hex to RGB
 */
function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result
    ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16),
      }
    : null;
}

/**
 * Determines if text should be light or dark based on background color
 */
function getContrastColor(hexColor: string): string {
  const rgb = hexToRgb(hexColor);
  if (!rgb) return '#000000';

  // Calculate relative luminance
  const luminance = (0.299 * rgb.r + 0.587 * rgb.g + 0.114 * rgb.b) / 255;
  return luminance > 0.5 ? '#000000' : '#ffffff';
}

/**
 * Color swatch button component
 */
function ColorSwatch({
  color,
  isSelected,
  onClick,
  name,
  size = 'medium',
}: {
  color: string;
  isSelected: boolean;
  onClick: () => void;
  name: string;
  size?: 'small' | 'medium' | 'large';
}) {
  const sizeMap = { small: 24, medium: 32, large: 40 };
  const dimension = sizeMap[size];

  return (
    <Tooltip content={name}>
      <button
        type="button"
        onClick={onClick}
        aria-label={`Select ${name}`}
        aria-pressed={isSelected}
        style={{
          width: `${dimension}px`,
          height: `${dimension}px`,
          borderRadius: '6px',
          backgroundColor: color,
          border: isSelected ? '3px solid #2c6ecb' : '1px solid #e1e3e5',
          cursor: 'pointer',
          padding: 0,
          transition: 'transform 0.15s ease, border-color 0.15s ease',
          transform: isSelected ? 'scale(1.1)' : 'scale(1)',
          boxShadow: isSelected ? '0 2px 8px rgba(0,0,0,0.15)' : '0 1px 2px rgba(0,0,0,0.05)',
          position: 'relative',
        }}
      >
        {isSelected && (
          <span
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: getContrastColor(color),
              fontSize: size === 'small' ? '12px' : '14px',
            }}
          >
            ✓
          </span>
        )}
      </button>
    </Tooltip>
  );
}

/**
 * Color preview with name and value
 */
function ColorPreview({
  color,
  label,
}: {
  color: string;
  label?: string;
}) {
  const contrastColor = getContrastColor(color);

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        padding: '12px',
        backgroundColor: '#f6f6f7',
        borderRadius: '8px',
      }}
    >
      <div
        style={{
          width: '48px',
          height: '48px',
          borderRadius: '8px',
          backgroundColor: color,
          border: '1px solid #e1e3e5',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: contrastColor,
          fontSize: '16px',
          fontWeight: 600,
        }}
      >
        Aa
      </div>
      <div style={{ flex: 1 }}>
        {label && (
          <Text as="p" variant="bodyMd" fontWeight="semibold">
            {label}
          </Text>
        )}
        <Text as="p" variant="bodySm" tone="subdued">
          {color.toUpperCase()}
        </Text>
      </div>
    </div>
  );
}

/**
 * RGB input fields component
 */
function RgbInputs({
  rgb,
  onChange,
}: {
  rgb: { r: number; g: number; b: number };
  onChange: (rgb: { r: number; g: number; b: number }) => void;
}) {
  const handleChange = (channel: 'r' | 'g' | 'b', value: string) => {
    const numValue = parseInt(value, 10);
    if (!isNaN(numValue)) {
      onChange({ ...rgb, [channel]: Math.max(0, Math.min(255, numValue)) });
    }
  };

  return (
    <InlineStack gap="200">
      <div style={{ width: '60px' }}>
        <TextField
          label="R"
          labelHidden
          value={String(rgb.r)}
          onChange={(v) => handleChange('r', v)}
          type="number"
          min={0}
          max={255}
          autoComplete="off"
          prefix={<span style={{ color: '#d72c0d', fontWeight: 600 }}>R</span>}
        />
      </div>
      <div style={{ width: '60px' }}>
        <TextField
          label="G"
          labelHidden
          value={String(rgb.g)}
          onChange={(v) => handleChange('g', v)}
          type="number"
          min={0}
          max={255}
          autoComplete="off"
          prefix={<span style={{ color: '#2e844a', fontWeight: 600 }}>G</span>}
        />
      </div>
      <div style={{ width: '60px' }}>
        <TextField
          label="B"
          labelHidden
          value={String(rgb.b)}
          onChange={(v) => handleChange('b', v)}
          type="number"
          min={0}
          max={255}
          autoComplete="off"
          prefix={<span style={{ color: '#2c6ecb', fontWeight: 600 }}>B</span>}
        />
      </div>
    </InlineStack>
  );
}

/**
 * Main ColorPicker component
 */
export function ColorPicker({
  value,
  onChange,
  label,
  helpText,
  colorType = 'primary',
  customPresets,
  showRgbInput = true,
  disabled = false,
  error,
}: ColorPickerProps) {
  const [popoverActive, setPopoverActive] = useState(false);
  const [hexInput, setHexInput] = useState(value);
  const [inputError, setInputError] = useState<string | undefined>(error);

  // Get presets based on color type
  const presets = useMemo(() => {
    const typePresets = COLOR_TYPE_PRESETS[colorType];
    const allPresets = customPresets ? [...typePresets, ...customPresets] : typePresets;
    return allPresets;
  }, [colorType, customPresets]);

  // Sync hex input with value prop
  useEffect(() => {
    setHexInput(value);
  }, [value]);

  // Convert current value to RGB
  const currentRgb = useMemo(() => {
    const rgb = hexToRgb(value);
    return rgb || { r: 0, g: 0, b: 0 };
  }, [value]);

  const handleHexChange = useCallback((newValue: string) => {
    // Allow typing with or without #
    let formattedValue = newValue.startsWith('#') ? newValue : `#${newValue}`;
    formattedValue = formattedValue.toLowerCase();
    setHexInput(formattedValue);

    // Validate and update
    if (isValidHex(formattedValue)) {
      setInputError(undefined);
      onChange(formattedValue);
    } else if (formattedValue.length > 1) {
      setInputError('Enter a valid hex color (e.g., #ff5500)');
    }
  }, [onChange]);

  const handleRgbChange = useCallback((rgb: { r: number; g: number; b: number }) => {
    const hex = rgbToHex(rgb.r, rgb.g, rgb.b);
    setHexInput(hex);
    setInputError(undefined);
    onChange(hex);
  }, [onChange]);

  const handlePresetClick = useCallback((color: string) => {
    setHexInput(color);
    setInputError(undefined);
    onChange(color);
  }, [onChange]);

  const togglePopover = useCallback(() => {
    if (!disabled) {
      setPopoverActive((active) => !active);
    }
  }, [disabled]);

  const activator = (
    <button
      type="button"
      onClick={togglePopover}
      disabled={disabled}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '8px 12px',
        background: '#ffffff',
        border: `1px solid ${inputError ? '#d72c0d' : '#e1e3e5'}`,
        borderRadius: '8px',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        width: '100%',
        textAlign: 'left',
      }}
    >
      <div
        style={{
          width: '24px',
          height: '24px',
          borderRadius: '4px',
          backgroundColor: value,
          border: '1px solid #e1e3e5',
          flexShrink: 0,
        }}
      />
      <span style={{ flex: 1, color: '#303030', fontSize: '14px' }}>
        {value.toUpperCase()}
      </span>
      <span style={{ color: '#8c9196', fontSize: '12px' }}>
        {popoverActive ? '▲' : '▼'}
      </span>
    </button>
  );

  return (
    <BlockStack gap="200">
      {label && (
        <Text as="span" variant="bodyMd" fontWeight="semibold">
          {label}
        </Text>
      )}

      <Popover
        active={popoverActive}
        activator={activator}
        onClose={() => setPopoverActive(false)}
        preferredAlignment="left"
        sectioned
      >
        <Box padding="400" minWidth="280px">
          <BlockStack gap="400">
            {/* Color preview */}
            <ColorPreview color={value} label={label} />

            {/* Hex input */}
            <TextField
              label="Hex Color"
              value={hexInput}
              onChange={handleHexChange}
              autoComplete="off"
              placeholder="#000000"
              error={inputError}
              prefix="#"
              maxLength={7}
            />

            {/* RGB inputs */}
            {showRgbInput && (
              <BlockStack gap="200">
                <Text as="span" variant="bodySm" tone="subdued">
                  RGB Values
                </Text>
                <RgbInputs rgb={currentRgb} onChange={handleRgbChange} />
              </BlockStack>
            )}

            {/* Preset colors */}
            <BlockStack gap="200">
              <Text as="span" variant="bodySm" tone="subdued">
                Presets
              </Text>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(6, 1fr)',
                  gap: '8px',
                }}
              >
                {presets.map((preset) => (
                  <ColorSwatch
                    key={preset.value}
                    color={preset.value}
                    name={preset.name}
                    isSelected={value.toLowerCase() === preset.value.toLowerCase()}
                    onClick={() => handlePresetClick(preset.value)}
                    size="medium"
                  />
                ))}
              </div>
            </BlockStack>

            {/* Quick access to all colors */}
            <BlockStack gap="200">
              <Text as="span" variant="bodySm" tone="subdued">
                More Colors
              </Text>
              <InlineStack gap="100" wrap>
                {[...BRAND_PRESETS, ...NEUTRAL_PRESETS, ...ACCENT_PRESETS]
                  .filter((p) => !presets.some((preset) => preset.value === p.value))
                  .slice(0, 12)
                  .map((preset) => (
                    <ColorSwatch
                      key={preset.value}
                      color={preset.value}
                      name={preset.name}
                      isSelected={value.toLowerCase() === preset.value.toLowerCase()}
                      onClick={() => handlePresetClick(preset.value)}
                      size="small"
                    />
                  ))}
              </InlineStack>
            </BlockStack>
          </BlockStack>
        </Box>
      </Popover>

      {helpText && (
        <Text as="p" variant="bodySm" tone="subdued">
          {helpText}
        </Text>
      )}

      {error && (
        <Text as="p" variant="bodySm" tone="critical">
          {error}
        </Text>
      )}
    </BlockStack>
  );
}

/**
 * Grouped color pickers for widget styling
 * Provides a cohesive interface for selecting primary, secondary, text, and background colors
 */
export interface WidgetColors {
  primary: string;
  secondary: string;
  text: string;
  background: string;
}

interface WidgetColorPickerGroupProps {
  /** Current color values */
  colors: WidgetColors;
  /** Callback when any color changes */
  onChange: (colors: WidgetColors) => void;
  /** Show preview of all colors together */
  showCombinedPreview?: boolean;
  /** Disable all pickers */
  disabled?: boolean;
}

export function WidgetColorPickerGroup({
  colors,
  onChange,
  showCombinedPreview = true,
  disabled = false,
}: WidgetColorPickerGroupProps) {
  const handleColorChange = useCallback(
    (colorType: keyof WidgetColors, value: string) => {
      onChange({ ...colors, [colorType]: value });
    },
    [colors, onChange]
  );

  return (
    <BlockStack gap="400">
      {showCombinedPreview && (
        <Box padding="400" borderRadius="200" background="bg-surface-secondary">
          <div
            style={{
              padding: '16px',
              borderRadius: '12px',
              backgroundColor: colors.background,
              border: `2px solid ${colors.primary}`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div
                style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '8px',
                  backgroundColor: colors.primary,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: getContrastColor(colors.primary),
                  fontSize: '18px',
                }}
              >
                🎁
              </div>
              <div>
                <div style={{ color: colors.text, fontWeight: 600, fontSize: '14px' }}>
                  Your Rewards
                </div>
                <div style={{ color: colors.secondary, fontSize: '12px' }}>
                  250 points available
                </div>
              </div>
            </div>
          </div>
        </Box>
      )}

      <InlineStack gap="400" wrap>
        <Box minWidth="200px">
          <ColorPicker
            label="Primary Color"
            value={colors.primary}
            onChange={(v) => handleColorChange('primary', v)}
            colorType="primary"
            helpText="Buttons and accents"
            disabled={disabled}
          />
        </Box>
        <Box minWidth="200px">
          <ColorPicker
            label="Secondary Color"
            value={colors.secondary}
            onChange={(v) => handleColorChange('secondary', v)}
            colorType="secondary"
            helpText="Secondary text and details"
            disabled={disabled}
          />
        </Box>
      </InlineStack>

      <InlineStack gap="400" wrap>
        <Box minWidth="200px">
          <ColorPicker
            label="Text Color"
            value={colors.text}
            onChange={(v) => handleColorChange('text', v)}
            colorType="text"
            helpText="Main text color"
            disabled={disabled}
          />
        </Box>
        <Box minWidth="200px">
          <ColorPicker
            label="Background Color"
            value={colors.background}
            onChange={(v) => handleColorChange('background', v)}
            colorType="background"
            helpText="Panel background"
            disabled={disabled}
          />
        </Box>
      </InlineStack>
    </BlockStack>
  );
}

export default ColorPicker;
