# The admin panel's design source of truth

## `panel-redesign.html` — the approved artifact

A single self-contained file: the panel's approved visual design, as a **live** mock. Open it in a
browser and it works — the language toggle, the theme toggle, the screen switcher on the icon rail,
the chart hover. Nothing in it is a picture; every surface, radius, shadow and curve is real CSS
and real SVG, which is why it can be diffed against the shipped panel line by line.

It carries no build step and no dependencies. `file://` is enough.

**It is the reference, not the implementation.** The panel lives in `frontend/admin` and is a React
app; this file is what that app is measured against. When the two disagree about a colour, a
spacing, a curve or a state, the artifact is right unless someone decides otherwise on purpose —
and when they do, the decision belongs in `CLAUDE.md`, not in a silent divergence.

Its own source is worth reading before changing a chart. The drawing code — `smooth`, `drawSpark`,
`drawPlot`, `rosePoints`, `rosePath`, `drawRadar`, `drawGauges` — carries comments explaining why
each constant is what it is: why the rose needs eight points and not four, why the handle length
comes from the segment rather than the radius, why the sparkline's fade is anchored to the line
instead of the viewBox. Those comments are the reasoning behind `frontend/admin/src/components/
charts/geometry.ts`, and every one of them was written after a version that got it wrong.

## `mockapi.py` — rendering the real panel without a database

```bash
cd frontend/admin && npm run build
python3 docs/panel/mockapi.py          # → http://127.0.0.1:4174/admin/
```

A dependency-free stand-in for the admin API. It serves the built SPA and answers every endpoint
the panel calls, with response shapes copied from the pydantic models — so the pages run their real
queries, real formatting and real error states, against plausible data.

The shell accepts three query parameters:

| parameter | effect |
|---|---|
| `?theme=light\|dark` | seeded into `localStorage` **before** the app module runs — the only way to set it headless |
| `?locale=fa\|en` | same, for the language |
| `?fill=<name>` | runs one of the `FILLS` snippets ~900ms after load |

`FILLS` exists for states you cannot reach with a URL: a chart mid-hover, a form with text in it, an
open dialog, a long message against the character counter. Add one rather than screenshotting an
empty page and calling it verified.

## Why render instead of only testing

Every serious defect in this panel's history was invisible to `tsc` and to vitest, and obvious in a
screenshot:

- «۴٬۰۹۶ / ۱۳۸» — a character counter reading backwards, because two numbers around a slash are
  separate bidi runs and an `isolate` does not reorder them.
- `bg-brand/12` compiling to **nothing**, because Tailwind's opacity modifiers are multiples of 5 —
  a tinted badge that silently rendered with no background at all.
- A chart's top gridline and its label drawn above the canvas, because the plot scaled to the data
  while the ticks were rounded up.

So: render it, read the PNG back, and compare against the artifact rendered the same way. Chromium
is enough —

```bash
chromium --headless --disable-gpu --no-sandbox --hide-scrollbars \
  --force-device-scale-factor=2 --window-size=1440,1000 --virtual-time-budget=10000 \
  --screenshot=out.png "http://127.0.0.1:4174/admin/?theme=dark&locale=fa"
```

Absolute pixel sizes are **not** comparable between the two: the artifact renders inside a scaled
device frame, so its 14px is not the panel's 14px. What compares is treatment — the depth order of
the surfaces, whether an edge is a border or a shadow, the shape of a curve, the tone of a fill,
which element sits on top at a crossing.
