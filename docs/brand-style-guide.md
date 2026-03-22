# TiOLi AGENTIS — Brand Style Guide

## Gradient Text Treatment

The signature gradient text effect used on "AGENTIS" and hero headings. Apply this whenever a word or phrase needs brand emphasis.

### CSS Class
```css
.gradient-text {
    background: linear-gradient(135deg, #77d4e5, #edc05f);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
```

### Usage Instruction
To apply the TiOLi AGENTIS gradient text treatment to any text element:

**HTML with class:**
```html
<span class="gradient-text">AGENTIS</span>
```

**Inline style (when class not available):**
```html
<span style="background: linear-gradient(135deg, #77d4e5, #edc05f); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">AGENTIS</span>
```

**Tailwind (if using arbitrary values):**
```html
<span class="bg-gradient-to-br from-[#77d4e5] to-[#edc05f] bg-clip-text text-transparent">AGENTIS</span>
```

### When to Use
- The word "AGENTIS" in the logo/nav — always
- Hero headings that need brand emphasis
- Key feature names in marketing materials
- Section headers on the brochureware site
- NOT on body text, labels, or small UI elements

### Gradient Specification
| Property | Value |
|----------|-------|
| Type | Linear gradient |
| Angle | 135 degrees (top-left to bottom-right) |
| Start colour | `#77d4e5` (TiOLi Cyan/Turquoise) |
| End colour | `#edc05f` (TiOLi Gold/Amber) |
| Clip | Background-clip: text |
| Fill | Text-fill-color: transparent |

---

## Brand Colour Palette

| Name | Hex | Usage |
|------|-----|-------|
| Primary (Cyan) | `#77d4e5` | Links, active states, primary CTAs, borders |
| Accent (Gold) | `#edc05f` | Revenue, highlights, secondary CTAs, badges |
| Background | `#061423` | Page background, sidebar |
| Surface | `#0f1c2c` | Cards, panels, containers |
| Surface High | `#1e2b3b` | Hover states, elevated elements |
| Text Primary | `#d6e4f9` | Body text |
| Text Secondary | `#94a3b8` | Paragraphs, descriptions |
| Text Muted | `#64748b` | Labels, captions |
| Text Dark | `#44474c` | Borders, dividers |
| Success | `#6ecfb0` | Positive indicators |
| Error | `#ffb4ab` | Errors, warnings |
| Heading Pink | `#f0a0b0` | H1-H6 headings |

## Logo Construction

```
T[gold]i[/gold]OL[gold]i[/gold] [gradient]AGENTIS[/gradient]
```

- "TiOLi" in white, weight 300 (light)
- "i" letters in Gold (#edc05f)
- "AGENTIS" in gradient text (cyan→gold), weight 700 (bold)

## Typography

| Role | Font | Weight | Size |
|------|------|--------|------|
| Headlines | Inter | 800-900 (Black) | 2xl-7xl |
| Body | Inter | 400 | sm-base |
| Labels/Mono | JetBrains Mono | 400-500 | xs-sm |
| Navigation | Inter | 500 | sm |
