// Intensity Color Mapping with WCAG Contrast Calculation

const INTENSITY_COLORS = {
  1: { name: 'Recovery',  hex: '#16A34A' },
  2: { name: 'Easy',      hex: '#22C55E' },
  3: { name: 'Moderate',  hex: '#F59E0B' },
  4: { name: 'Hard',      hex: '#F97316' },
  5: { name: 'Max',       hex: '#EF4444' }
};

/**
 * Calculate relative luminance for WCAG contrast
 * https://www.w3.org/WAI/GL/wiki/Relative_luminance
 */
function getLuminance(hex) {
  const rgb = hexToRgb(hex);
  const [r, g, b] = [rgb.r, rgb.g, rgb.b].map(val => {
    const sRGB = val / 255;
    return sRGB <= 0.03928
      ? sRGB / 12.92
      : Math.pow((sRGB + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/**
 * Calculate contrast ratio between two colors
 * https://www.w3.org/WAI/GL/wiki/Contrast_ratio
 */
function getContrastRatio(hex1, hex2) {
  const lum1 = getLuminance(hex1);
  const lum2 = getLuminance(hex2);
  const lighter = Math.max(lum1, lum2);
  const darker = Math.min(lum1, lum2);
  return (lighter + 0.05) / (darker + 0.05);
}

/**
 * Assert WCAG AA contrast compliance (4.5:1 for normal text)
 */
function assertContrast(fgHex, bgHex, minRatio = 4.5) {
  const ratio = getContrastRatio(fgHex, bgHex);
  if (ratio < minRatio) {
    throw new Error(
      `Contrast ratio ${ratio.toFixed(2)}:1 fails WCAG AA (needs ${minRatio}:1). ` +
      `Foreground: ${fgHex}, Background: ${bgHex}`
    );
  }
  return ratio;
}

/**
 * Convert hex to RGB
 */
function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? {
    r: parseInt(result[1], 16),
    g: parseInt(result[2], 16),
    b: parseInt(result[3], 16)
  } : null;
}

/**
 * Determine if we should use black or white text on a background
 */
function getReadableForeground(bgHex) {
  const whiteRatio = getContrastRatio('#FFFFFF', bgHex);
  const blackRatio = getContrastRatio('#000000', bgHex);
  
  // Prefer white text if both meet requirements
  if (whiteRatio >= 4.5) return '#FFFFFF';
  if (blackRatio >= 4.5) return '#000000';
  
  // Return whichever is better (even if below threshold)
  return whiteRatio > blackRatio ? '#FFFFFF' : '#000000';
}

/**
 * Get intensity color scheme with accessible foreground
 */
function getIntensityColors(level) {
  if (!INTENSITY_COLORS[level]) {
    console.warn(`Invalid intensity level: ${level}, defaulting to 3`);
    level = 3;
  }
  
  const base = INTENSITY_COLORS[level];
  const bg = base.hex;
  const fg = getReadableForeground(bg);
  
  // Generate subtle variant (30% opacity overlay)
  const rgb = hexToRgb(bg);
  const subtle = `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.3)`;
  
  // Generate accent variant (lighter/darker by 15%)
  const lum = getLuminance(bg);
  const accentMultiplier = lum > 0.5 ? 0.85 : 1.15; // Darken light colors, lighten dark colors
  const accent = rgbToHex(
    Math.min(255, Math.round(rgb.r * accentMultiplier)),
    Math.min(255, Math.round(rgb.g * accentMultiplier)),
    Math.min(255, Math.round(rgb.b * accentMultiplier))
  );
  
  return {
    name: base.name,
    level,
    bg,
    fg,
    accent,
    subtle,
    contrast: getContrastRatio(fg, bg)
  };
}

/**
 * Convert RGB to hex
 */
function rgbToHex(r, g, b) {
  return "#" + [r, g, b].map(x => {
    const hex = x.toString(16);
    return hex.length === 1 ? "0" + hex : hex;
  }).join('');
}

/**
 * Map speed to intensity level (1-5)
 */
function speedToIntensity(speedMph) {
  if (speedMph < 4.5) return 1; // Recovery
  if (speedMph < 5.5) return 2; // Easy
  if (speedMph < 6.5) return 3; // Moderate
  if (speedMph < 7.5) return 4; // Hard
  return 5; // Max
}

export {
  INTENSITY_COLORS,
  getIntensityColors,
  getContrastRatio,
  assertContrast,
  getLuminance,
  getReadableForeground,
  speedToIntensity,
  hexToRgb,
  rgbToHex
};

