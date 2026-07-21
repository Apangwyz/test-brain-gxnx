<!--
 * @Author: apang ar478913459@qq.com
 * @Date: 2026-07-19 11:46:27
 * @LastEditors: apang ar478913459@qq.com
 * @LastEditTime: 2026-07-19 15:13:09
 * @FilePath: /TestBrain-main/DESIGN.md
 * @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
-->
## Style Prompt

Premium business-tech HUD dashboard built on the Starbucks Design System token contract. Four-tier green system, Starbucks Gold for status/premium moments, SoDoSans typography with universal -0.01em tracking. Adapted for a dark-glass context: the warm cream canvas is replaced by deep House Green (#0a1814) as the void backdrop; content cards render as frosted glass panels (backdrop-filter + semi-transparent green-tinted surface) floating above the canvas. Gold outlines trace premium card edges; Green Accent (#00754A) serves as the data-highlight color replacing the original blue; Text White / Text White Soft provide the light-on-dark reading scale. Every surface has subtle glass reflections, inner shadows, outer rim glow, and backdrop blur — never opaque, never flat. Motion is restrained: a slow micro-float (2–4px over 4.5–6s) driven by the Starbucks Expander easing curve. The overall feel is a light-luxury cockpit dashboard rooted in the Starbucks brand palette and typographic voice.

## Design System Source

Starbucks Design System (four-tier green, warm cream canvas, full-pill buttons, SoDoSans typeface, whisper-soft layered shadows). All colors map to `tokens.css` custom properties. The dark HUD adaptation extends (never redefines) the token set with `--hud-*` variables for dark-surface text and glass-specific values.

## Colors

### Starbucks Token Colors (source of truth)

| Role               | Token                    | Value                               |
| ------------------ | ------------------------ | ----------------------------------- |
| Green Accent (CTA) | `--accent`               | `#00754A`                           |
| Success            | `--success`              | `#16a34a`                           |
| Warning            | `--warn`                 | `#fbbc05`                           |
| Danger             | `--danger`               | `#c82014`                           |

### HUD Extension Colors (dark adaptation)

| Role                  | Variable                 | Value                               |
| --------------------- | ------------------------ | ----------------------------------- |
| Canvas background     | `--hud-canvas`           | `#0a1814` (dark House Green)        |
| Card surface (glass)  | `--hud-surface-glass`    | `rgba(30,57,50,0.48)` + `blur(24px)` |
| Card surface (hover)  | `--hud-surface-glass-hover` | `rgba(35,65,57,0.58)`           |
| Gold accent           | `--hud-gold`             | `#cba258` (Starbucks Gold)          |
| Gold light            | `--hud-gold-light`       | `#dfc49d` (Gold Light)              |
| Gold muted            | `--hud-gold-muted`       | `#a68a3e`                           |
| Gold glow             | `--hud-gold-glow`        | `rgba(203,162,88,0.18)`             |
| Gold border           | `--hud-gold-border`      | `rgba(203,162,88,0.22)`             |
| Gold border active    | `--hud-gold-border-active` | `rgba(203,162,88,0.45)`           |
| Text primary          | `--hud-text`             | `rgba(255,255,255,1)` (Text White)  |
| Text secondary        | `--hud-text-secondary`   | `rgba(255,255,255,0.70)` (Text White Soft) |
| Text tertiary         | `--hud-text-tertiary`    | `rgba(255,255,255,0.40)`            |
| Data glow             | `--hud-accent-glow`      | `color-mix(in oklab, var(--accent), transparent 75%)` |
| Danger glow           | `--hud-danger-glow`      | `color-mix(in oklab, var(--danger), transparent 80%)` |
| Success glow          | `--hud-success-glow`     | `color-mix(in oklab, var(--success), transparent 80%)` |

### Color Mapping Summary

| Original (pre-migration) | Starbucks-adapted             | Token Source    |
| ------------------------ | ----------------------------- | --------------- |
| `#08080D` canvas         | `#0a1814`                     | `--hud-canvas`  |
| `rgba(20,22,30,0.55)` glass | `rgba(30,57,50,0.48)`      | `--hud-surface-glass` |
| `#C8A45C` gold           | `#cba258`                     | `--hud-gold`    |
| `#8B7344` gold muted     | `#a68a3e`                     | `--hud-gold-muted` |
| `#5B9BD5` blue data      | `#00754A`                     | `--accent`      |
| `#D95A5A` red            | `#c82014`                     | `--danger`      |
| `#5ABF8A` green          | `#16a34a`                     | `--success`     |
| `#E8E6F0` text primary   | `rgba(255,255,255,1)`         | `--hud-text`    |
| `#8A8896` text secondary | `rgba(255,255,255,0.70)`      | `--hud-text-secondary` |

## Typography

| Role         | Font                                                    | Weight | Size           | Token       |
| ------------ | ------------------------------------------------------- | ------ | -------------- | ----------- |
| Headlines    | SoDoSans, "Helvetica Neue", Helvetica, Arial, sans-serif | 600    | 24px           | `--text-xl` |
| Card titles  | SoDoSans, "Helvetica Neue", Helvetica, Arial, sans-serif | 500    | 14–16px        | `--text-sm` / `--text-base` |
| Body text    | SoDoSans, "Helvetica Neue", Helvetica, Arial, sans-serif | 400    | 13–16px        | `--text-xs` / `--text-base` |
| Data numbers | ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace | 500 | 13–24px | `--text-xs` / `--text-xl` |
| Labels       | SoDoSans, "Helvetica Neue", Helvetica, Arial, sans-serif | 400    | 11–13px        | `--text-xs` |

- `letter-spacing: var(--tracking-display)` = `-0.01em` — universal SoDoSans tracking
- `font-variant-numeric: tabular-nums` on all numeric columns
- `line-height: var(--leading-body)` = `1.5` for body; `var(--leading-tight)` = `1.2` for display

## Shape & Radius

| Element         | Radius                  | Token            |
| --------------- | ----------------------- | ---------------- |
| Content cards   | 12px                    | `--radius-md`    |
| Pill badges     | 9999px                  | `--radius-pill`  |
| Input chips     | 4px                     | `--radius-sm`    |
| Metric bars     | 2px (hairline)          | —                |

## Motion & Easing

- Entrance / transition easing: `cubic-bezier(0.25, 0.46, 0.45, 0.94)` — the Starbucks Expander curve
- Micro-float animation: 2–4px translateY, 4.5–6s cycle, no bounce/spring physics
- Hover glow fade: opacity transition 0.6–0.8s ease
- Scale(0.95) active press on interactive pills per the Starbucks button contract

## What NOT to Do

1. **Never use fully opaque cards** — every panel MUST have `backdrop-filter: blur()` and semi-transparent background
2. **Never use `#FFD700` or bright gold** — gold is always muted, aged, restrained (`#cba258` family)
3. **Never use large solid-color blocks** — all surfaces are edges + transparency, not filled shapes
4. **Never animate with spring/bounce physics** — motion is the Starbucks Expander cubic-bezier, a slow float (2–4px over 4.5–6s)
5. **Never use drop shadows without blur** — all shadows are soft and diffuse, never hard
6. **Never use white backgrounds or light mode** — this is a dark-only HUD built on House Green
7. **Never use more than 2 Green-Accent-highlighted data elements per card** — Green Accent (`--accent`) is attention currency
8. **Never underline text** — use gold bottom-border dividers or gold/green text color for keyboard-navigation-level emphasis
