# CFI State Outreach Dashboard

An internal outreach tool for **CrashFree India (CFI)** covering road-safety governance
and key contacts across a **13-state pilot** (Tamil Nadu, Delhi, Madhya Pradesh, Assam,
Haryana, Telangana, Maharashtra, Gujarat, Uttar Pradesh, Bihar, Karnataka, Jharkhand,
Rajasthan).
It is a single static page — no build step, no server — that reads its data from two
JSON files sitting next to it.

## Viewing it

Open `index.html` directly, or serve the folder with any static file server, e.g.:

```bash
npx http-server .
# or
python3 -m http.server
```

It also works as-is on **GitHub Pages** (Settings → Pages → deploy from the branch root).

## What's in it

- **State selector** — a real-boundary map (simplified for display) plus a searchable
  list, limited to the 13 pilot states/UTs.
- **Governance Structure** tab, two views built on the same data:
  - *By Problem Area* — policy, enforcement, engineering, emergency response, data &
    monitoring, education, funding.
  - *Governance Map* — an org-chart flowchart (department hierarchy + coordination
    bodies), with hover-to-trace-connections and zoom/pan for larger states.
  - Clicking any body in either view opens the same detail panel: mandate, roads
    owned, decision-making power, key positions (with per-post citations), subordinate
    bodies, and open flags.
- **Key People to Reach** tab — cards/table per individual with role, category,
  relevance, sourced track record, and flags.
- **Sourcing throughout** — every claim shown carries its citation (or an explicit
  "no citation on file for this line" note — nothing is invented). A "Sourcing & flags"
  button in the header explains what each confidence/flag badge means.
- **Cross-state search** — the header search matches states, departments, individual
  posts (e.g. "Transport Commissioner"), and people across all 12 states at once.
- **In-dashboard chatbot** and **"Check for updates"** — see the caveat below.

## Important: two features only work inside a Claude Artifact

The chat panel ("Ask about this data") and the "Check for updates" buttons are built
on [Claude Artifact runtime capabilities](https://claude.ai) (`window.claude.use(...)`),
not a raw API call — a static page cannot safely hold an API key, and a browser sandbox
blocks calling `api.anthropic.com` directly. Concretely:

- The **chat** asks Claude on the *viewer's own* Claude usage, grounded only in the
  dataset — no key is ever embedded in this code.
- **Check for updates** writes a timestamped request into a small live document store;
  the actual live-web recheck is intended to be run by whoever maintains this dashboard
  (via Claude, with web search) and the results are written back to the same store,
  which every open copy of the page reflects live.

Neither feature does anything (or appears) when this page is opened outside a Claude
Artifact viewer — e.g. on GitHub Pages, or locally. That's by design (the code checks
for `window.claude` and simply doesn't render the chat button / hides the update
buttons when it's absent) — the rest of the dashboard is fully static and functional
everywhere.

## Data pipeline

```
data/source/all-states-consolidated.json   (13-state research dataset, as supplied)
        │
        ├── scripts/prep.py  ──────────────►  data.json
        │     classifies each governance body into problem areas, derives
        │     confidence/flag badges, links flags to bodies/people, parses
        │     subordinate-body lists vs. prose — see comments in the script
        │     for exactly what's derived vs. sourced.
        │
data/source/india-gadm-admin1-raw.geojson  (not committed — see below)
        │
        └── scripts/build_map.py ─────────►  india-map.json
              simplifies real state-boundary geometry (Douglas-Peucker) and
              projects it for the sidebar map's SVG.
```

To regenerate `data.json` after editing the source dataset:

```bash
python3 scripts/prep.py
```

To regenerate `india-map.json`, first download an India admin-1 (state-level)
GeoJSON — this was built from
`https://raw.githubusercontent.com/geohacker/india/master/state/india_telengana.geojson`
(not committed here — it's ~23MB) — save it as
`data/source/india-gadm-admin1-raw.geojson`, then run:

```bash
python3 scripts/build_map.py
```

## Branding

The color palette and fonts in `index.html`'s `--cfi-*` custom properties are
pulled directly from crashfreeindia.org's shipped CSS (`--brand:#5d2df7`,
`--font-body:"Geist"`, `--font-heading:"Montserrat"`, fetched live on
2026-09-25) — not a visual estimate. `--cfi-primary` is the site's exact brand
color; `--cfi-primary-dark`/`--cfi-accent` and the dark-mode values are derived
from it at the same hue/saturation, since the live site doesn't itself expose
single tokens for those states. If the site's palette changes, re-fetch its
`/assets/*.css` and update the `:root` block at the top of `index.html`'s
`<style>` accordingly.
