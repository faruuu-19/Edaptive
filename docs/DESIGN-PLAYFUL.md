# Design: the Playful look (opt-in)

An alternative look for the child screens, added on 16 Oct 2026 because the Storybook theme
([DESIGN.md](DESIGN.md)) left large empty areas that felt flat for a children's app. **The
Storybook look is untouched and is still one switch away.** Nothing in the Playful look
changes behaviour, data or copy that a screen reader would announce.

## Switching between the two looks

- Parent area → **App look** card → *Playful* or *Storybook* (remembered on this device).
- Or add `?look=storybook` / `?look=playful` to any address.
- Code: Playful is `src/app/theme-playful.css` (every rule is under `html[data-theme="playful"]`),
  `src/features/theme/` (Scenery, Pip the mascot, subject badges, look switch) and a few
  `ui-*` class hooks in the components. Delete the `import "./theme-playful.css"` line in
  `layout.tsx` and the original look is all that is left.
- A full copy of the Storybook-era front end is saved outside the repo:
  `~/Downloads/edaptive-voice-work/frontend-storybook-theme-backup-20261016.tgz`
  (plus `class-exit-uncommitted-20261016.diff`, the uncommitted work at that moment).

## What it does

The direction follows the "be kind with kids" reference the team supplied: calm sage green,
rolling hills, hairline drawings, a light serif for headings, and soft pastel shapes.

| Idea | How |
|---|---|
| Fill the empty space without noise | Scenery behind every child screen: pale mint cloud fields, a line-drawn sun, drifting clouds and three layers of sage hills. The profile picker also gets a line-drawn house with a heart window, trees, two children and a pond with a duck. Parent, setup and lesson screens get a quiet version (faint dots, no hills). Content always sits on solid cards, never straight on the scenery. |
| Subtle, not loud | Hairline outlines in deep sage (never heavy), almost no shadow, large radii (32–48px), one deep sage panel for the day. Pastel fields only: mint, lemon, peach, sky. |
| Cute | Pip, a rounded sprout-headed helper drawn with the same hairline, waves on the picker, home and class screens. |
| Type | A light serif (Fraunces 300) for headings with one *italic* accent word: "Who's *learning* today?", "Hi, *Fatima!*", "Your *subjects*". Andika, designed for beginning readers, for all other text. |
| Buttons | Soft pills with a visible bottom edge that lifts on hover and squishes on press (a small springy bounce), a leading icon in a little circle, and a tiny twinkle on the main action when hovered or focused. Main action = sage with a darker edge; others = white with a sage outline; Lock = deep sage. Targets are at least 50px high. |
| Tags | Little stickers instead of boxes: grade tags are lemon with a tiny leaf and a slight tilt; status tags ("Coming soon", "Lesson prepares at…") have a dashed die-cut outline and a coloured dot; time tags carry a tiny clock face. |
| Child home | A greeting banner, three subject cards (soft blob with a line icon, name, an italic line, a status pill) like the reference's "Services" row, then the day as a wide grid of outlined rows with subject badges and time pills on a deep sage band like the reference's "Reviews". |

Motion (clouds, Pip) is slow and stops for `prefers-reduced-motion`.

## Colour reasoning

Research on children's colour use is mixed, so the choices lean on what agrees across sources:
children like clear, friendly hues; cool greens and blues are the most common recommendation for
calm and focus while warm hues read as energising; strong text contrast and a quiet base matter
more than any single hue. The reference's sage palette is a calm, natural choice that fits a
learning app used for a whole school day.

- **Page and cards:** warm off-white and white, so reading text stays easy.
- **Sage greens** (hills, the day panel, the main action `#447f5e`, 4.9:1 with white text):
  calm and "going well". The day panel `#4f8567` carries white and pale-lemon text (4.6:1 or better for body text).
- **Peach** = Maths, **lemon** = English, **sky / mint** = Science. The team's subject colours
  from DESIGN.md are kept in meaning and softened in tone.
- **Deep sage charcoal `#34453a`** for all text on every pastel.

## Sources used for the direction

- Children's colour preference studies: a study of 7–8-year-olds (most preferred: red, yellow,
  green, blue, purple) at <https://ir.kdu.ac.lk/handle/345/7637>, and a 132-child study that found a
  preference for cool hues at <https://dspace.lu.lv/handle/7/64294>.
- Colour, concentration and stress in children's learning spaces (2025):
  <https://ijaup.iust.ac.ir/article-1-910-en.html>. The wider evidence is small and inconsistent.
- Nielsen Norman Group's work with 125 children aged 3–12 on usability (motor skills, large
  targets, simple gestures): <https://www.nngroup.com/articles/childrens-websites-usability-issues/>.
- Playful button systems (soft fully rounded buttons, a visible bottom edge that lifts and compresses, a springy press, separate decorative and accessible fills): <https://superdesign.dev/library/button-studio-a-playful-button-system>. Kids' interface guidance: rounded shapes feel friendly, a raised look signals tappable, and large targets suit young hands: <https://www.aufaitux.com/blog/kids-app-design/>.
- Case studies on mascots, large touch targets and clear feedback: Tubik Studio's *Roebuck* and
  *Nature Encyclopedia*, and the *Word Jumble* and *Izzi Playground* kids' app designs on Contra.
- Duolingo's published illustration approach (rounded shapes, no pointy shapes): rounded
  rectangles, circles and rounded triangles only. Pip and the shapes follow that rule.
- Visual references supplied by the team: Creative Kids Academy (pastel colour blocks, italic
  serif accents, pill tags), be kind with kids (layered sage waves, soft blobs, thin line
  drawings), Rainbow Friends (a friendly character on cream) and Mambtos (colour bands, a
  mascot and playful type).
