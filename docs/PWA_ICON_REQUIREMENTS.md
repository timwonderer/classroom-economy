# PWA Icon Requirements

## Overview

The Progressive Web App implementation requires PNG icon files for proper installation on mobile devices. While the manifest references these icons, they need to be generated from the existing brand logo.

## Required Icons

The following icon files must be created and placed in `static/images/`:

1. **icon-192.png** - 192x192 pixels (maskable)
2. **icon-512.png** - 512x512 pixels (maskable)

## How to Generate Icons

### Option 1: Online Tool

1. Visit a PWA icon generator (e.g., https://www.pwabuilder.com/imageGenerator)
2. Upload `static/images/brand-logo.svg`
3. Generate the required sizes
4. Download and place in `static/images/`

### Option 2: Using ImageMagick (Command Line)

```bash
# Install ImageMagick if not already installed
# On Ubuntu/Debian: apt-get install imagemagick librsvg2-bin
# On macOS: brew install imagemagick librsvg

# Convert SVG to PNG at required sizes
rsvg-convert -w 192 -h 192 static/images/brand-logo.svg -o static/images/icon-192.png
rsvg-convert -w 512 -h 512 static/images/brand-logo.svg -o static/images/icon-512.png
```

### Option 3: Using Inkscape

```bash
# Install Inkscape
# On Ubuntu/Debian: apt-get install inkscape
# On macOS: brew install inkscape

# Export to PNG
inkscape static/images/brand-logo.svg --export-filename=static/images/icon-192.png --export-width=192 --export-height=192
inkscape static/images/brand-logo.svg --export-filename=static/images/icon-512.png --export-width=512 --export-height=512
```

### Option 4: Using Python (Pillow + CairoSVG)

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

## Icon Design Guidelines

### Maskable Icons

The icons use `"purpose": "any maskable"` which means:
- The icon should have important content in the "safe zone" (center 80% of the image)
- The outer 20% may be cropped on some devices
- Background should be solid color (#1a4d47 - brand primary color)

### Testing

After generating icons:
1. Test PWA installation on Android (Chrome > Menu > Install app)
2. Test PWA installation on iOS (Safari > Share > Add to Home Screen)
3. Verify icons appear correctly on home screen
4. Verify icons appear correctly in app switcher

## Current Status

- ✅ **icon-192.png**: Generated and available in `static/images/`
- ✅ **icon-512.png**: Generated and available in `static/images/`
- ✅ **brand-logo.svg**: Available and ready for conversion

## References

- [PWA Icon Requirements](https://web.dev/add-manifest/#icons)
- [Maskable Icons](https://web.dev/maskable-icon/)
- [PWA Builder Icon Generator](https://www.pwabuilder.com/imageGenerator)
