# SOP-DEP-021: PWA Icon Requirements

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SOP-DEP-021| 1.1 | 2026-03-08 | 1.0 |Normative|

## I. Purpose

This document provides instructions for generating and managing Progressive Web App (PWA) icons and mobile navigation configurations.

## II. Scope

The PWA implementation, including icon generation, maskable icon guidelines, and mobile navigation components within the Classroom Token Hub.

## III. Authority Level

Normative (SOP Tier). Subordinate to INV-CORE-000.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`

## V. Overview

The Progressive Web App (PWA) implementation provides a native app-like experience on mobile devices with full offline support, mobile navigation, and installation capability.

**Version:** 1.7.0+ includes enhanced mobile navigation with hamburger menu.

## VI. Required Icons

The following icon files must be created and placed in `static/images/`:

1. **icon-192.png** - 192x192 pixels (maskable)
2. **icon-512.png** - 512x512 pixels (maskable)

## VII. How to Generate Icons

### 1. Option 1: Online Tool

1. Visit a PWA icon generator (e.g., https://www.pwabuilder.com/imageGenerator)
2. Upload `static/images/brand-logo.svg`
3. Generate the required sizes
4. Download and place in `static/images/`

### 2. Option 2: Using ImageMagick (Command Line)

```bash
# Install ImageMagick if not already installed
# On Ubuntu/Debian: apt-get install imagemagick librsvg2-bin
# On macOS: brew install imagemagick librsvg

# Convert SVG to PNG at required sizes
rsvg-convert -w 192 -h 192 static/images/brand-logo.svg -o static/images/icon-192.png
rsvg-convert -w 512 -h 512 static/images/brand-logo.svg -o static/images/icon-512.png
```

### 3. Option 3: Using Inkscape

```bash
# Install Inkscape
# On Ubuntu/Debian: apt-get install inkscape
# On macOS: brew install inkscape

# Export to PNG
inkscape static/images/brand-logo.svg --export-filename=static/images/icon-192.png --export-width=192 --export-height=192
inkscape static/images/brand-logo.svg --export-filename=static/images/icon-512.png --export-width=512 --export-height=512
```

### 4. Option 4: Using Python (Pillow + CairoSVG)

```python
# Install dependencies: pip install Pillow cairosvg

from cairosvg import svg2png

# Generate 192x192
svg2png(url='static/images/brand-logo.svg',
        write_to='static/images/icon-192.png',
        output_width=192,
        output_height=192)

# Generate 512x512
svg2png(url='static/images/brand-logo.svg',
        write_to='static/images/icon-512.png',
        output_width=512,
        output_height=512)
```

## VIII. Icon Design Guidelines

### 1. Maskable Icons

The icons use `"purpose": "any maskable"` which means:

- The icon should have important content in the "safe zone" (center 80% of the image)
- The outer 20% may be cropped on some devices
- Background should be solid color (#1a4d47 - brand primary color)

### 2. Testing

After generating icons:

1. Test PWA installation on Android (Chrome > Menu > Install app)
2. Test PWA installation on iOS (Safari > Share > Add to Home Screen)
3. Verify icons appear correctly on home screen
4. Verify icons appear correctly in app switcher

## IX. Current Status

-  **icon-192.png**: Generated and available in `static/images/`
-  **icon-512.png**: Generated and available in `static/images/`
-  **brand-logo.svg**: Available and ready for conversion

## X. References

- [PWA Icon Requirements](https://web.dev/add-manifest/#icons)
- [Maskable Icons](https://web.dev/maskable-icon/)
- [PWA Builder Icon Generator](https://www.pwabuilder.com/imageGenerator)

## XI. Mobile Navigation (v1.7.0+)

### 1. Overview

Version 1.7.0 introduces a floating hamburger menu for seamless navigation on mobile devices and PWA installations.

### 2. Features

**Hamburger Menu:**
- Floating button appears on screens <768px width
- Slides in from left with smooth animation
- Backdrop overlay for clear focus
- Auto-closes on navigation or backdrop click

**Responsive Help Buttons:**
- Icon-only display on mobile to save space
- Full navigation menu accessible
- No separate mobile templates needed

**PWA Compatibility:**
- Resolves previous limitation where navigation was inaccessible in PWA mode
- Consistent experience across desktop, mobile browser, and installed PWA
- Full feature parity across all platforms

### 3. User Experience

**On Desktop:**
- Standard sidebar navigation (always visible)
- Help buttons with text labels
- Traditional layout

**On Mobile Browser:**
- Hamburger menu button (top-left or floating)
- Tap to reveal full navigation
- Swipe or click backdrop to dismiss
- Icon-only help buttons

**In Installed PWA:**
- Same hamburger menu as mobile browser
- Native app-like feel
- Smooth animations
- Full navigation access

### 4. Technical Implementation

**CSS Media Queries:**
```css
@media (max-width: 768px) {
    .hamburger-menu {
        display: block;
    }
    .sidebar {
        transform: translateX(-100%);
    }
    .sidebar.active {
        transform: translateX(0);
    }
}
```

**JavaScript:**
- Toggle sidebar visibility
- Handle backdrop clicks
- Auto-close on navigation
- Touch-friendly interactions

**No Additional Templates:**
- Same templates work for all platforms
- Responsive design handles layout
- Progressive enhancement approach

### 5. Testing Mobile Navigation

**On Mobile Device:**
1. Visit site on phone/tablet
2. Look for hamburger menu button
3. Tap to open navigation
4. Verify all menu items accessible
5. Test backdrop dismissal

**In PWA:**
1. Install app from mobile browser
2. Open installed app
3. Verify hamburger menu present
4. Test navigation functionality
5. Confirm smooth animations

### 6. Troubleshooting

**Menu Not Appearing:**
- Check screen width (should be <768px)
- Verify JavaScript loaded
- Check browser console for errors

**Menu Won't Close:**
- Ensure backdrop click handler working
- Check for JavaScript conflicts
- Try clicking backdrop multiple times

**Icons Not Showing:**
- Verify Material Symbols font loaded
- Check icon font preload in HTML
- Review Content Security Policy settings

## XII. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.

