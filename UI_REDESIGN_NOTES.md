# iSpotify — UI/UX refinement pass

A visual-only refresh toward a clean, minimal, desktop-native aesthetic
(Caelestia / Hyprland spirit): consistent radius & spacing, layered depth,
tactile controls, and a cohesive icon set. **No features were added, removed,
or rewired. All existing behavior is unchanged and cross-platform
(Windows + Linux). No new dependencies.**

## What changed (all visual / layout)

### Design-token foundation — `ui/theme.py`
- Added token constants: `SPACE` (4px scale), `RADIUS` (`sm/md/lg/pill`),
  `MOTION` (fast/base/slow ms), `EASING` (OutCubic/OutQuint/InOutCubic), and a
  `shadow` colour. These formalise values that were previously ad-hoc.
- Rationalised surface radii to the scale (cards 12, hero 16, download frames
  12) so corners stop drifting between 14/18/etc.
- Player surface raised (`surface_raised`) with a brighter top divider.
- Sidebar active item now carries a 2px accent selection rail.
- Larger, fully-round play button (44px) with refined hover/press/focus.

### Reusable motion/depth helpers — `ui/widgets.py`
- `soft_shadow()` — attaches a soft `QGraphicsDropShadowEffect` to a container
  for layered depth (used on the player bar).
- `HoverLift` — animates a shadow's blur/offset only (never geometry or event
  handling), keeping motion safe on Qt/Wayland as noted in `MotionButton`.

### Cohesive icons — `assets/icons/` (additive)
- `SP_DirIcon.svg` (folder-plus, "add to playlist")
- `SP_FileDialogDetailedView.svg` (pencil, "rename")
- `SP_ArrowUp.svg` (matches `SP_ArrowDown`, "move up")

  These replace the bright-blue **native OS fallback icons** that
  `standard_icon()` was rendering. Same monochrome language as the existing set
  (24×24, `fill=none`, stroke `#c9c9cc`, ~1.7 width, round caps).

### Layout polish
- `main_window.py` — header title/subtitle box given stretch so subtitles no
  longer clip (e.g. "Find something worth keeping.").
- `library_tab.py` — vertical rhythm between the controls row and content, plus
  breathing space between a song's status dot and its action cluster.
- `settings_tab.py` — card padding standardised to `20,18`.
- `toast.py` — hard-coded `#17171a` swapped for the `surface_raised` token.

## Safety notes
- Every widget carries at most one graphics effect: the page stack and each
  toast keep their opacity (fade) effect; the shadow lives on the player bar
  only — no collisions, fades intact.
- Object names used by QSS selectors are unchanged.

## Verification
- Full test suite: **38 passed, 8 subtests passed**.
- Additional behavioral smoke test (navigation/history, sidebar checked-state,
  search mode toggle, library filter/sort, download row states, token/icon
  resolution, effect-collision): **26/26 OK**.
- End-to-end boot via the real `main.py` theme path: OK.

---

# Motion & polish pass

A second, behaviour-preserving pass focused on smoothness. All motion
animates sizes, positions or values. No new per-button graphics effects, so
the Wayland click and repaint safety described above still holds.

- **Sliding navigation highlight.** The sidebar selection is a single
  `SlidingIndicator` that glides between items (`ui/widgets.py`). It re-snaps
  whenever the sidebar is shown or resized.
- **Page transitions.** Incoming pages fade in (0.35 → 1) and rise 14px into
  place over `MOTION["slow"]`. Rapid switching always settles at rest.
- **Tactile icon buttons.** Every `icon_button` glyph grows about 12% on hover,
  squishes on press and springs back (`OutBack`). Only `iconSize` is
  animated, and the frames are fixed-size in QSS, so layout never shifts.
- **Smooth wheel scrolling.** Mouse-wheel steps glide on every page's scroll
  area. Touchpad and high-resolution pixel scrolling pass through untouched.
- **Download progress** glides forward between reports and jumps
  straight back on a retry.
- **Fixes:**
  - Mojibake in the player: `Headphones Â· …` and `Detecting audio outputâ€¦`.
  - Hero and download SVGs used `rgba()` strokes, which Qt's SVG renderer
    ignores, so the record grooves were invisible. They now use
    `stroke-opacity`.
  - The hero headline was indented by QLabel's automatic indent.

Hidden extras are documented separately in `docs/EASTER_EGGS.md`.
