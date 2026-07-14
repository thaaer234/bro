---
name: Institutional Fintech Excellence
colors:
  surface: '#f7f9fd'
  surface-dim: '#d8dadd'
  surface-bright: '#f7f9fd'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f7'
  surface-container: '#eceef1'
  surface-container-high: '#e6e8eb'
  surface-container-highest: '#e0e3e6'
  on-surface: '#191c1e'
  on-surface-variant: '#40484e'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f4'
  outline: '#70787e'
  outline-variant: '#bfc8ce'
  surface-tint: '#016689'
  primary: '#00516e'
  on-primary: '#ffffff'
  primary-container: '#0e6a8e'
  on-primary-container: '#bce5ff'
  inverse-primary: '#87cff8'
  secondary: '#6e4f9c'
  on-secondary: '#ffffff'
  secondary-container: '#cca9fe'
  on-secondary-container: '#583985'
  tertiary: '#6b4200'
  on-tertiary: '#ffffff'
  tertiary-container: '#8a580d'
  on-tertiary-container: '#ffd9b1'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#c3e8ff'
  primary-fixed-dim: '#87cff8'
  on-primary-fixed: '#001e2c'
  on-primary-fixed-variant: '#004c68'
  secondary-fixed: '#eddcff'
  secondary-fixed-dim: '#d7baff'
  on-secondary-fixed: '#280155'
  on-secondary-fixed-variant: '#553683'
  tertiary-fixed: '#ffddb8'
  tertiary-fixed-dim: '#fcba69'
  on-tertiary-fixed: '#2b1700'
  on-tertiary-fixed-variant: '#663e00'
  background: '#f7f9fd'
  on-background: '#191c1e'
  surface-variant: '#e0e3e6'
typography:
  display-lg:
    fontFamily: Hanken Grotesk
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Hanken Grotesk
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Hanken Grotesk
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  container-max: 1280px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 40px
---

## Brand & Style

This design system establishes a bridge between the high-trust world of premium fintech and the academic heritage of the Institute. The visual identity is built on the concept of "Enlightened Prosperity," combining professional financial rigor with a sophisticated, institutional aesthetic. 

The design style follows a **Modern Corporate** direction with **Glassmorphic** accents. It utilizes the fluid, calligraphic lines from the logo to inform motion and decorative elements. The user experience should feel authoritative yet accessible, evoking a sense of wisdom, stability, and growth. Large amounts of whitespace are balanced by deep, rich color blocks and subtle metallic accents to reinforce the premium nature of the service.

## Colors

The palette is derived directly from the Institute's visual identity, optimized for digital financial interfaces. 

*   **Primary (Deep Teal/Blue):** Used for core navigation, primary actions, and brand headers. It represents stability and professional depth.
*   **Secondary (Deep Purple):** Used for secondary actions, interactive states, and as a highlight color for "Institutional" features.
*   **Accents:** Gold is reserved for "Wealth" indicators, premium tiers, and success states. Silver/Grey is used for borders, inactive states, and secondary metadata.
*   **Background Strategy:** Interfaces should primarily use the neutral off-white for clarity. Brand presence is maintained through "Watermark" layers—low-opacity (2-5%) abstract renderings of the logo's curved elements—placed in the background of cards and header sections.

## Typography

The typography system pairs **Hanken Grotesk** for headlines with **Inter** for UI and body text. 

Hanken Grotesk provides a sharp, contemporary edge that feels modern and precise, ideal for a fintech context. Inter is utilized for its exceptional legibility in data-heavy environments, such as transaction lists and financial dashboards. 

For the localized Arabic context, the system should pair these with a clean, professional Naskh-based typeface that shares the same x-height and optical weight as Inter to ensure a seamless bi-lingual experience.

## Layout & Spacing

The layout follows a **Fluid Grid** model based on a 12-column system for desktop and a 4-column system for mobile. 

*   **Rhythm:** A strict 8px base unit (0.5rem) governs all padding and margins to maintain mathematical harmony.
*   **Density:** The spacing is intentionally generous ("Airy") to reflect the "Premium" brand positioning. Avoid cramped data tables; instead, use expanded row heights and clear grouping.
*   **Adaptation:** On mobile, margins reduce to 16px to maximize screen real estate, while the vertical rhythm remains consistent to preserve the institutional structure.

## Elevation & Depth

Visual hierarchy in this design system is achieved through **Tonal Layering** supplemented by subtle **Ambient Shadows**.

1.  **Base Layer:** The neutral background (#F8F9FA).
2.  **Surface Layer:** White cards and containers, elevated by a very soft, diffused shadow (0px 4px 20px rgba(14, 106, 142, 0.05))—note the slight teal tint in the shadow to maintain color harmony.
3.  **Feature Layer:** Elements that require high focus (like active modals or primary CTA buttons) utilize a more defined shadow or a subtle Glassmorphic backdrop blur (12px) when appearing over brand-colored backgrounds.

Avoid heavy black shadows; depth should feel like light passing through high-quality paper or frosted glass.

## Shapes

The shape language is **Rounded (Level 2)**, reflecting the organic, circular forms found in the logo's "globe" and "brush strokes."

*   **Standard Elements:** Buttons and input fields use a 0.5rem (8px) radius.
*   **Large Containers:** Cards and modals use a 1rem (16px) radius to create a softer, more welcoming frame for complex financial data.
*   **Accent Shapes:** Decorative elements or "chips" may occasionally use pill-shapes (Level 3) to mimic the droplet-like shapes in the logo's upper-right quadrant.

## Components

### Buttons
Primary buttons use a solid Deep Teal fill with white text. Secondary buttons use a Deep Purple outline or text link style. For high-conversion "Premium" actions, a subtle gradient from Deep Teal to a slightly lighter variant can be applied.

### Cards
Cards are the primary container for the UI. They should be white, with a 1px Silver/Grey border (#CBD1D6). For featured content, include a faint, low-opacity watermark of the logo's abstract curves in the bottom-right corner.

### Input Fields
Inputs should have a clean Silver border that transitions to Deep Teal on focus. Labels should use the `label-md` style in a muted grey to keep the focus on the user's data.

### Chips & Badges
Used for status indicators. Success states should use the Accent Gold (subtle background with dark gold text), while neutral tags should use the Accent Silver.

### Data Visualization
Charts should primarily use the Teal and Purple colors for data series, with Gold used exclusively to highlight a "Goal" or "Target" achieved. Use Silver for all grid lines and axes to keep the interface light.