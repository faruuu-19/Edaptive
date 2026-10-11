# Design: the Storybook theme

Every screen in Edaptive (Track A, B and C) uses this one theme, chosen by the team in
Oct 2026. New UI must follow it; don't introduce a second look.

The feel is a picture book: warm paper, navy ink outlines, tomato and mustard accents,
chunky offset shadows. Calm enough to learn on, friendly enough for Grades 1–5.

## Where it lives

- **Tokens and shared classes:** `frontend/src/app/globals.css`. This is the single source:
  use `var(--…)` and the shared classes, never hard-coded hex values in feature code.
- **Fonts:** imported once in `frontend/src/app/layout.tsx` from `@fontsource` (bundled,
  OFL licence). Never load fonts or icons from a CDN or Google Fonts: the app must work offline.
- **Reference screens:** the profile picker, child home and parent area in
  `frontend/src/features/home-profile/` show every pattern below in use.

## Colour tokens

| Token | Value | Use |
|---|---|---|
| `--paper` | `#fbf5e9` | Page background |
| `--paper-2` | `#fdfaf3` | Hover on light surfaces |
| `--surface` | `#fffdf8` | Cards, tiles, buttons |
| `--ground` | `#e8dcc2` | The "ground" strip on the picker scene |
| `--ink` | `#22304b` | Text, every outline, offset shadows |
| `--muted` | `#57607a` | Secondary text (grade, hints) |
| `--rule` | `#d9cfbc` | Dashed dividers inside cards |
| `--tomato` | `#b8452c` | Primary buttons, the current subject, selected state |
| `--tomato-soft` | `#f6d9cf` | Maths art panel |
| `--mustard` | `#e3a92b` | Focus ring, the sun, highlights |
| `--mustard-soft` | `#f7e7c2` | English art panel |
| `--teal-soft` | `#d3ece9` | Science art panel |
| `--danger` | `#a33a23` | Destructive actions, errors |
| `--notice` / `--notice-ink` | `#fbf1d6` / `#4a3b12` | Notice boxes |

Subject colours: **Maths = tomato, English = mustard, Science = teal.** Keep these
consistent everywhere a subject appears (widgets, lesson player, dashboards).

Child avatar colours (picked per child, stored as `avatar_key`): mustard `#e3a92b`,
teal `#7cc2be`, tomato `#f09a84`, plum `#b9a3d6`, leaf `#a8cf8e`.

One **light theme only**: no OS dark mode, so the app looks the same on every family's machine.

## Type

| Role | Font | Weight |
|---|---|---|
| Headings, names, subject titles, wordmark (`--display`) | Fraunces | 800 (600 for sub-headings) |
| Everything else (`--body`) | Andika (designed for beginning readers) | 400, 700 |

Base size 16px. `h1` scales `clamp(2rem, 5vw, 3rem)`. Child-facing text stays short and large.

## Shape and depth

- Outlines: **2px solid `--ink`** on cards, tiles, inputs and buttons.
- Radius: 16px cards and tiles, 12px buttons, 10px inputs, 50% avatars.
- Depth comes from **flat offset shadows**, never blur: tiles `5px 5px 0 var(--ink)`,
  primary buttons `4px 4px 0 var(--ink)`, the current subject card `6px 6px 0 var(--tomato)`.
  On press, translate toward the shadow and shrink it.
- Dividers inside cards: `2px dashed var(--rule)`.

## Components (shared classes in `globals.css`)

- `.btn`, plus `.btn-primary` (tomato, the one main action per screen), `.btn-dark` (Lock),
  `.btn-quiet` (text-only) and `.btn-danger` (red text for Remove).
- `.card`, `.input`, `.field` (label above input), `.notice`, `.error`, `.eyebrow`,
  `.wordmark`, and layout helpers `.page`, `.page-narrow`, `.stack`, `.row`, `.spread`.
- Avatar: a coloured circle with an ink outline and the child's first initial in Fraunces
  (`features/home-profile/Avatar.tsx`).

## Icons and imagery

- **Inline SVG stroke icons only**: 24×24 viewBox, `stroke="currentColor"`, stroke width
  2.2, round caps and joins (`features/home-profile/icons.tsx`).
- **No emoji** in UI: they render differently on each OS.
- Any picture where a count matters is drawn by code (SVG/widget), never generated. This
  follows the curriculum's `visual_generation_rules`.

## Child area vs parent area

- **Child screens** (picker, home, lessons): big tiles, Fraunces names, offset shadows,
  the paper-and-ground scene.
- **Parent screens** (anything behind the PIN): the same tokens but quieter. An `.eyebrow`
  "Parent area" label, a list plus form layout, and no scene decoration.

## Accessibility (non-negotiable)

- Touch targets at least 44px. Focus ring: `3px solid var(--mustard)`.
- Text contrast at least 4.5:1. Don't put body text in `--muted` on tinted panels.
- Real `<button>`, `<a>`, `<label>` and `<input>` elements, and `aria-label` on icon-only
  controls. Decorative SVG gets `aria-hidden`.
- Layouts must work at phone width (375px) with no horizontal scroll. Rows wrap and grids
  collapse.
