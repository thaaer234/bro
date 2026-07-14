---
name: Premium Arabic Fintech
colors:
  surface: '#f8f9fa'
  surface-dim: '#d9dadb'
  surface-bright: '#f8f9fa'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f4f5'
  surface-container: '#edeeef'
  surface-container-high: '#e7e8e9'
  surface-container-highest: '#e1e3e4'
  on-surface: '#191c1d'
  on-surface-variant: '#404944'
  inverse-surface: '#2e3132'
  inverse-on-surface: '#f0f1f2'
  outline: '#707974'
  outline-variant: '#bfc9c3'
  surface-tint: '#2b6954'
  primary: '#003527'
  on-primary: '#ffffff'
  primary-container: '#064e3b'
  on-primary-container: '#80bea6'
  inverse-primary: '#95d3ba'
  secondary: '#735c00'
  on-secondary: '#ffffff'
  secondary-container: '#fed65b'
  on-secondary-container: '#745c00'
  tertiary: '#272e3e'
  on-tertiary: '#ffffff'
  tertiary-container: '#3d4455'
  on-tertiary-container: '#aab1c5'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#b0f0d6'
  primary-fixed-dim: '#95d3ba'
  on-primary-fixed: '#002117'
  on-primary-fixed-variant: '#0b513d'
  secondary-fixed: '#ffe088'
  secondary-fixed-dim: '#e9c349'
  on-secondary-fixed: '#241a00'
  on-secondary-fixed-variant: '#574500'
  tertiary-fixed: '#dce2f7'
  tertiary-fixed-dim: '#c0c6db'
  on-tertiary-fixed: '#141b2b'
  on-tertiary-fixed-variant: '#404758'
  background: '#f8f9fa'
  on-background: '#191c1d'
  surface-variant: '#e1e3e4'
typography:
  display-lg:
    fontFamily: IBM Plex Sans Arabic
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: IBM Plex Sans Arabic
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
  headline-md:
    fontFamily: IBM Plex Sans Arabic
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: IBM Plex Sans Arabic
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: IBM Plex Sans Arabic
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: IBM Plex Sans Arabic
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.01em
  stats-lg:
    fontFamily: IBM Plex Sans
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
  headline-lg-mobile:
    fontFamily: IBM Plex Sans Arabic
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  container-margin: 1.5rem
  gutter: 1rem
  section-gap: 2.5rem
  stack-sm: 0.5rem
  stack-md: 1rem
  stack-lg: 1.5rem
---

## Brand & Style
The design system is engineered to evoke a sense of institutional trust, enduring wealth, and educational empowerment. It targets a sophisticated audience seeking clarity in investment through a minimalist, high-end aesthetic.

The visual direction combines **Modern Minimalism** with **Corporate Professionalism**. By prioritizing negative space and a restrained color palette, the UI creates a "private banking" experience that feels exclusive yet accessible. The design narrative centers on transparency and growth, using precise geometric alignments and premium finishes to convey reliability and prestige.

## Colors
The palette is rooted in a deep **Forest Green**, symbolizing stability and ethical growth. This is paired with **Gold** accents used sparingly for high-value actions, achievement states, and critical brand moments, creating a "Gold Standard" visual metaphor.

- **Primary (Forest Green):** Used for main headers, primary buttons, and active states to anchor the interface in trust.
- **Secondary (Gold):** Reserved for highlights, badges, and premium progress indicators.
- **Neutral (Warm Gray & White):** The background layers use a soft Warm Gray to reduce eye strain and enhance the feeling of physical, high-quality paper or matte surfaces.
- **Status Colors:** Use muted versions of Emerald for success and Ochre for warnings to maintain the sophisticated tonal range.

## Typography
The typography system utilizes **IBM Plex Sans Arabic** to ensure a technical, modern, and highly legible experience across both Arabic and English scripts. 

For financial figures and data-heavy metrics, the system switches to the Latin-based **IBM Plex Sans** weights to ensure maximum clarity and a "ticker-tape" precision. Headlines are set with tight tracking and bold weights to establish a clear hierarchy, while body text maintains generous line heights to facilitate comfortable reading of educational investment content.

## Layout & Spacing
This design system employs a **Fluid Grid** model optimized for mobile-first ergonomics. The layout relies on a 4-column structure for mobile devices with a standard 24px (1.5rem) outer margin to provide content with breathing room.

The spacing rhythm is governed by an 8px base unit. Luxury is conveyed through "intentional emptiness"—using larger vertical gaps (section-gap) to separate distinct financial concepts or educational modules. Elements are grouped using a logical stack (sm/md/lg) to maintain a clear information architecture.

## Elevation & Depth
Elevation is handled through **Tonal Layers** and **Ambient Shadows** rather than aggressive highlights. Surfaces use a "stacked paper" metaphor where the base is the Warm Gray neutral color, and active cards sit slightly above on a White surface.

Shadows are extremely diffused (Blur: 20px-40px, Opacity: 4-6%) and tinted with a hint of the Primary Forest Green to avoid a "dirty" gray look. This creates a soft, natural depth that feels like a physical object resting on a premium surface. Borders are kept thin (1px) and use low-contrast shades to define boundaries without cluttering the visual field.

## Shapes
The shape language is **Soft (0.25rem base)**, balancing the precision of a financial institution with the approachability of an educational platform. 

Corners are slightly rounded to feel modern and "safe," but never fully circular or pill-shaped (except for tags and chips), as sharp, defined edges communicate professional rigor. Interactive elements like input fields and primary buttons utilize the `rounded-lg` (0.5rem) token to differentiate them from static container elements.

## Components
- **Buttons:** Primary buttons are solid Forest Green with White text. Secondary buttons use a transparent background with a thin Forest Green border.
- **Investment Cards:** Features a White background, a 1px `gray-100` border, and the primary ambient shadow. Key financial figures are displayed in the `stats-lg` typography style.
- **Inputs:** Minimalist bottom-border only or very light gray containers with a 1px border that thickens and turns Gold upon focus.
- **Chips & Tags:** Small, pill-shaped elements used for asset classes or risk levels. Use desaturated tints of the status colors (e.g., light sage green for 'Low Risk').
- **Progress Indicators:** Use a thin, elegant Gold line for completion bars to represent the "Path to Wealth."
- **Navigation:** A bottom navigation bar for mobile with haptic-ready icons and a subtle backdrop blur (Glassmorphism) to maintain context.