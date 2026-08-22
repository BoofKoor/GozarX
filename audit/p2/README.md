# Phase 2 evidence

Raw measurements behind `audit/02-ui.md`. Every number in the report comes from one of these files;
nothing was computed by reading CSS.

## Reproducing

```bash
# 1. build the site
cd frontend/site && npm ci && BACKEND_ORIGIN=http://127.0.0.1:8000 npm run build

# 2. the mock backend, scaled to production so the layout matches the audited screenshots:
#      LOCATIONS  -> 29 entries, first five: 🇦🇪 Emirates, 🇹🇷 Turkey, 🇺🇸 United States,
#                    🇳🇱 Netherlands, 🇩🇪 Germany
#      LANDINGS   -> the 18 rows of backend/gozar/seed_landings.py (13 without a
#                    location_remark => 13 article links)
#      /stats     -> {"configs_delivered": 4154, "uptime_pct": 99.4}
#    Edit those three fixtures in audit/.harness/mockapi.py, then:
cd audit/.harness && python3 mockapi.py &

# 3. serve and probe
cd frontend/site && BACKEND_ORIGIN=http://127.0.0.1:8000 npm run start &
cd audit/.harness && npm install && npm install pngjs --no-save
node p2-geometry.mjs && node p2-spacing.mjs && node p2-bcf.mjs && node p2-final.mjs
node p2-contrast2.mjs && node p2-verify.mjs && node p2-grad.mjs
node p2-crops.mjs && node p2-hd.mjs && node p2-status.mjs && node p2-savings.mjs
```

The default fixtures ship 12 locations and 3 landings; with those the section-boundary,
touch-target and contrast numbers are unchanged, but the document height, the flag-strip orphan
(B3) and the article-chip count (C1/D5/H1) are not comparable to the audited screenshots.

## Files

| file | what it answers |
|---|---|
| `geometry.json` | sections, radii (A3), text-align (A6), scroll containers (B2), header (E1/E2), hero gradient geometry (4.4), locations card (H8), statband (G5/H7), footer columns (I3), keyword lists (H1/H2), hover rules (I1), language controls (I4) — at 360/390/412/591 |
| `spacing.json` | A1: per-boundary ink→head and ink→body, and the `.sec-head` stack broken into its parts |
| `bcf.json` | B5 global row-flex sweep, C touch targets, F1 per-line text of every centred subtitle, F3 truncated location names |
| `contrast.json` | first contrast sweep, 33 text groups × 2 themes (superseded by `contrast2.json` for `.cta` and `.grad` — see the report's §6) |
| `contrast2.json` | G2/G3 contrast without mutating the element (dominant colour of its own rect) |
| `verify-contrast.json` | 4.4 and the CTA read from named pixel points instead of a dominant colour |
| `gradient-pixels.json` | 4.4 decisive: real glyph pixels across the gradient span, paired with the ground behind them |
| `crops.json` | G4 app-tile luminance, H7 stat dot geometry and location-dot colours, B1 per-badge visibility |
| `final.json` | 4.2 font fallback + Cyrillic checks, D5 pill family, A4 nested framed boxes, D1 link inventory |
| `status-fresh.json` | 4.3: what `/status` and `/` render for a visitor with no prior state |
| `savings.json` | §5: measured Δ document height for each proposed fix, at 360/390/412 |
| `shots/` | the crops the report cites |

Font coverage (§4.2) was read from the font files' own cmap with `fontTools`, not inferred from
the filename:

```bash
pip install fonttools brotli
python3 -c "
from fontTools.ttLib import TTFont
for f in ['frontend/site/public/fonts/Inter-Variable-latin.woff2',
          'frontend/site/public/fonts/YekanBakh-VF.woff2']:
    t=TTFont(f); c=set()
    for tbl in t['cmap'].tables: c |= set(tbl.cmap)
    print(f, 'cyrillic:', len([x for x in c if 0x400<=x<=0x4FF]))"
```
