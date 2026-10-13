# frontend/

Static HTML/CSS/vanilla JS, served by FastAPI (`StaticFiles` mount +
Jinja2 templates). No build step, no Node -  a non-technical user (or
Colile) should be able to run this with just `uvicorn`.

## Visual language (plain Material / Google style)

Deliberately unstyled-looking: the interface should disappear and leave
the numbers. One accent colour, flat surfaces, text labels only.

- Top app bar: white, one hairline bottom border, product name +
  breadcrumb. No colour block.
- Left nav: text labels only, no icons or glyphs. The active item gets a
  tinted band (#e8f0fe) running the width of the rail.
- Content: white background, cards with a 1px #dadce0 border, **square
  corners and no shadow**. Roboto / system sans stack.
- One accent colour throughout: #1a73e8 (buttons, links, focus rings,
  the baseline chip, bar fills).
- Every corner is square. `--radius` is the single token that sets this,
  so the whole interface changes from one line.
- Status colours: success green (#188038), running blue, failed red
  (#c5221f). Colour is never the only channel - every status also prints
  its word, and the sortable table spells out "(asc)" / "(desc)" rather
  than drawing an arrow glyph.
- **No emoji, no icon fonts, no decorative glyphs anywhere.** The source
  is ASCII-only, so nothing depends on an emoji font being installed and
  nothing renders as a replacement box.
- Light theme only for v1 (no dark-mode toggle needed for a single local
  user).

Two layout helpers exist for forms:

- `.field-row` - one label beside one control, label in a fixed 160px
  column. Right for stacked single-field forms.
- `.shared-settings` + `.field-group` - several controls side by side,
  each labelled above its own input. Right where a short label ("k")
  would otherwise inherit the wide label column and strand the row.

| Path | Role |
|---|---|
| `templates/base.html` | Shared shell: app bar, nav rail, content slot (Jinja2 `content`/`page_js`/`title`/`breadcrumb` blocks -  every page `{% extends %}` this) |
| `templates/datasets.html` | List an engine's registered datasets, upload a new CSV |
| `templates/experiment.html` | Build+launch (or save-only) a wizard form; techniques/models/mechanisms always come from `GET /api/experiments/choices`, never hardcoded |
| `templates/runs.html` | List launched runs (`GET /api/runs`), track one's validation summary + live log tail |
| `templates/results.html` | A succeeded run's real result tables (`GET /api/results/{run_id}`), rendered as sortable tables + simple bar charts |
| `static/css/theme.css` | Palette, layout, card/nav/form/table/log/chart component styles. Plain Material-style surface: white, one blue accent (#1a73e8), flat borders, no icon glyphs |
| `static/js/common.js` | Shared `apiCall()` fetch wrapper (surfaces the API's own `detail` message on error), `buildTable()` (sortable, columns inferred from the rows themselves), banner/nav helpers |
| `templates/dashboard.html` | **Analysis**: headline counts, every recorded sweep, a cost chart. Reads the engine's lab.db directly, so CLI-launched sweeps appear with no import step |
| `templates/findings.html` | **Analysis**: states what each sweep found, in plain English first, with Friedman/Wilcoxon/Holm behind expandable sections |
| `templates/explorer.html` | **Analysis**: plot any recorded field against any other, with presets and a CSV export |
| `templates/guide.html` | **Help**: what the project is and how to read a result. Server-rendered prose, loads no page script, so it works even if everything else fails |
| `static/js/analysis-common.js` | Shared by the three analysis pages: auto-refresh watcher, hand-drawn SVG charts with keys and captions, expandable explainers, CSV download |
| `templates/compose.html` | **Pipeline Lab**: the card grid -  columns are configurations, rows are the five components, cards drag between cells |
| `templates/network.html` | **Pipeline Lab**: the layered pipeline graph, nodes shaded by mean score, edges weighted by run count |
| `templates/trends.html` | **Pipeline Lab**: x/y/group pickers over the 86 recorded columns, plus preset views |
| `static/js/datasets.js`, `experiment.js`, `runs.js`, `results.js` | One script per page -  no framework |
| `static/js/compose.js`, `network.js`, `trends.js` | The three Pipeline Lab tabs. `compose.js` re-costs every column via `POST /api/lab/estimate` on each change; `network.js` draws positioned divs plus inline SVG edges; `trends.js` renders server-aggregated series as CSS bars -  no charting library, per the no-build-step rule |

## Integration

Talks to the backend only via the `/api/*` routes in `backend/app/api/`.
Never embeds a result number directly in HTML -  always fetched from the
API at render time. `app/main.py` serves one route per page
(`/datasets`, `/experiment`, `/runs`, `/results`), each passing
`active_page` to `base.html` for the nav rail's highlighted entry.

**The two engines name some of the same things differently** -  prepfx's
logistic-regression key is `logistic`, b2's is `logreg` -  and
`experiment.js` never hardcodes either; both the technique/model/mechanism
lists and whether a control is a checkbox or a radio (prepfx takes exactly
one missingness rate+mechanism and sweeps a factor's whole technique list;
b2 allows a subset and several rates/mechanisms) come from
`GET /api/experiments/choices` and are rendered conditionally per engine - 
confirmed live in a real browser session for both engines and both
factors (see `docs/build-order.md` step 12's own verification).

A note on Jinja2 comments in `templates/*.html`: Jinja parses `{% %}`
tags even inside an HTML `<!-- -->` comment (it compiles the raw text
before any HTML parser sees it), so a prose comment must never literally
write `{% block ... %}` -  it will be parsed as a real, duplicate block tag
and break the whole template with an unhelpful "unexpected end of
template" error. `base.html`'s header comment hit exactly this; describe
blocks by name in prose instead of writing their literal syntax.

## Pipeline Lab tabs

The composer's live cost estimate is the load-bearing part. A run count
badly understates the work -  nested CV turns 18 runs into 2,880 model
fits -  so every grid change re-costs the column and shows runs, model
fits **and** an estimated duration before anything launches. A column
that varies more than one component is flagged (red header, Run
disabled) because an effect could no longer be attributed to one
component, which is the whole basis of the OFAT design.

Verified in a real browser (2026-10-10): the grid builds itself from
`GET /api/lab/choices`, dragging `robust` into the scaling row took the
estimate from 9 runs/90 fits to 12 runs/120 fits live, launching from
the grid produced a real sweep, and the Network tab then identified
`scaling=standard` as the best node (0.9744 vs none 0.9524) while
Trends showed the cost side: unscaled 1.805 s vs standardised 0.121 s.
Zero console errors on every tab.

## Done when

Each page in the build-order walkthrough (step 12) renders correctly and
drives a real backend call, in a plain browser, with no console errors.
Verified via the `browser-automation` skill: a real smoke run launched
through the New Experiment form for each engine, tracked to `succeeded`
on the Runs page (live log tail via polling, output isolation confirmed
by the log's own "Outputs written under" line pointing at
`data/runs/<run_id>/outputs`), and its real result tables (prepfx's own
CSVs; b2's MLflow-extracted `results.csv`) rendered correctly on the
Results page -  zero console errors and zero failed requests throughout.
