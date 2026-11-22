# FundPulse | Morocco FundGuard AI

FundPulse is a Streamlit dashboard for the 2026 Moroccan OPCVM consolidated workbook. It reads the four structured metric sheets with openpyxl and Pandas. The original Excel file stays in `data/` and is opened for reading only.

## Run on Windows PowerShell

From the project root, with Python 3.11 or newer installed:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

Open http://127.0.0.1:8501. The sidebar sets the inclusive report-date range and fund categories. Market cards show the latest published TOTAL in that range. The portfolio composition tab has its own security-category filter. Each CSV reflects its view's filters and includes original provenance columns. The flow export also includes the derived `Net subscriptions` column. Blanks export as empty fields.

## Workbook audit

Source workbook `data/OPCVM_2026_Consolide (1).xlsx`. The six dated sheets cover **2 January to 9 November 2026**, with **44 distinct report dates**. Gaps between consecutive reports are 3, 4, 7, 10, 11 or 14 days. Charts use the recorded dates.

| Sheet | Data rows | Missing cells | Exact duplicate rows |
| --- | ---: | --- | ---: |
| Actif_Net_OPCVM | 308 | None | 0 |
| Indices_Performance | 220 | None | 0 |
| Actif_Categorie_Valeurs | 528 | Montant × 4 | 0 |
| Souscriptions_Rachats | 308 | None | 0 |
| Détail intégral | 2,601 | See raw detail table | 0 |
| Contrôle des sources | 44 | Titre visible × 35, Valeurs manquantes × 40 | 0 |
| Power Query | 5 | None | 0 |

The four metric sheets have zero duplicate `Date` + `Catégorie` keys. Raw detail has zero duplicate `date_semaine` + `Fichier xlsx` + `Ligne export` keys. Source control has one row per report date. Power Query contains instructions and has no date column.

### Columns and observed Excel types

All four metric sheets start with `Date` (datetime), `Fichier xlsx` (text), `Fichier d’origine` (text), `Ligne export` (integer), `Catégorie` (text). The rest of the columns follow in workbook order below. “Number” denotes integer and decimal numeric cells, or decimal cells alone.

| Sheet | Remaining columns in source order |
| --- | --- |
| Actif_Net_OPCVM | `Nombre OPCVM` (integer), `Montant` (number), `Structure (%)` (number), `Variation hebdomadaire (%)` (number), `Variation mensuelle (%)` (number), `Variation annuelle (%)` (number) |
| Indices_Performance | `Indice` (number), `Variation hebdomadaire (%)` (number), `Variation mensuelle (%)` (number), `Variation annuelle (%)` (number), `Catégorie source` (text) |
| Actif_Categorie_Valeurs | `Montant` (number), `Structure (%)` (number), `Variation hebdomadaire (%)` (number), `Variation mensuelle (%)` (number), `Variation annuelle (%)` (number) |
| Souscriptions_Rachats | `Volume de souscriptions` (number), `Volume de rachats` (number), `Ligne rachats` (integer) |

#### Détail intégral

| Column | Observed type | Missing |
| --- | --- | ---: |
| date_semaine | datetime | 0 |
| Fichier xlsx | text | 0 |
| Fichier d’origine | text | 0 |
| Ligne export | integer | 0 |
| Feuille source | text | 0 |
| Section | text | 408 |
| Type de ligne | text | 0 |
| Column1 | blank | 2,601 |
| Column2 | text | 1,017 |
| Column3 | text, integer, decimal | 1,281 |
| Column4 | text, integer, decimal | 1,228 |
| Column5 | text, integer, decimal | 1,237 |
| Column6 | text, integer, decimal | 1,237 |
| Column7 | text, integer, decimal | 1,545 |
| Column8 | text, integer, decimal | 2,117 |
| Column9 | text | 2,588 |
| Column10 | text, integer, decimal | 2,434 |
| Column11 | text | 2,592 |
| Column12 | blank | 2,601 |

This sheet preserves original export lines including headings, blank lines and mixed values. Units depend on the original field.

#### Contrôle des sources and Power Query

Source control columns in order are `date_semaine` (datetime), `Fichier xlsx` (text), `Fichier d’origine` (text), `Lignes exportées` (integer), `Sections` (integer), `Montants actif net` (integer count), `Montants actif total` (integer count), `Volumes` (integer count), `Titre visible` (text), `Valeurs manquantes` (text). Power Query has two text columns, `Table` and `Instructions`.

## Available metrics and units

| Source | Metrics | Units and treatment |
| --- | --- | --- |
| Actif_Net_OPCVM | Net assets, fund count, market share, reported weekly, monthly and annual changes | Amounts on source scale with unspecified currency, counts in funds, shares and changes in percent. Published TOTAL is used for the market. |
| Indices_Performance | Reported index levels and weekly, monthly and annual variations | Index levels with unspecified base, variations in percent. Five categories have indices. Contractuel has no published series. |
| Actif_Categorie_Valeurs | Assets and reported composition by security category, plus reported changes | Amounts on source scale with unspecified currency, shares and changes in percent. Parent categories and subcategories overlap. |
| Souscriptions_Rachats | Subscriptions, redemptions and net subscriptions per category or published TOTAL | Volumes on source scale with unspecified unit and reporting period. Net subscriptions equals subscriptions minus redemptions for the same row. |

The workbook's Power Query instructions confirm that `10.28` means `10.28%`. The dashboard uses source percentages directly. Fund-level performance and individual investor flows are unavailable. Flow amounts are displayed by report date and are not summed over time.

## Data-quality findings

- Four missing `Montant` cells concern `VC Obligations émises ou garanties par l'état` on 2026-01-09, 2026-03-06, 2026-05-08 and 2026-07-10. The underlying export uses dashes. The app preserves blanks and distinguishes them from numeric zeros.
- Across the 44 reports, the sum of net asset categories differs from the published market amount by at most about 0.02 on the source scale. The dashboard uses the published figure.
- The dashboard consumes the structured metric tables. The raw detail, control and instruction sheets support provenance and are covered by this audit.

## Project layout

- `app.py` provides the dashboard, filters, charts and CSV downloads.
- `src/data_loader.py` loads the four metric sheets and verifies their headers.
- `src/validation.py` parses and validates dates, numeric values and unique report keys.
- `src/metrics.py` filters records, selects snapshots and calculates net subscriptions.
- `tests/test_fundpulse.py` checks the real workbook and validation edge cases.
- `requirements.txt` declares runtime and test dependencies.


## Phase 2 · SmartFlow

SmartFlow has independent date, category, metric and status filters. It reads only
`Actif_Net_OPCVM` and monitors each of the six fund categories separately. The
published market `TOTAL` is an optional seventh series. Each alert gives its
report date, baseline evidence and workbook provenance. Filtered records and
supporting values are available as CSV.

- **Calculated seven-day net asset change** uses `100 × (current Montant / prior Montant − 1)`
  when consecutive category reports are exactly seven days apart and the prior
  amount is positive. Of 44 reports, 33 have an eligible pair per series. The first
  report and intervals of 3, 4, 10, 11 or 14 days have a blank calculated change.
- **Published weekly net asset change** uses `Variation hebdomadaire (%)` on its
  original percent scale. Both series are displayed separately. The published
  series may follow a different comparison period or conventions.
- Scoring uses the rolling median and median absolute deviation (MAD) of the
  preceding 26 valid observations by default, with at least eight required.
  The current observation is excluded. Missing values do not enter the
  baseline. The date filter limits what is displayed after scoring, so history
  before the selected start date remains available.
- The modified z-score is `0.67448975 × (observation − median) / MAD`.
  The threshold defaults to `|score| > 3.5`. Insufficient history, zero MAD and
  missing observations have distinct statuses and leave the score blank.
  The score is a statistical heuristic, separate from investment risk scoring.
  It makes no probability or causal estimate. The anomaly count uses the date,
  category and metric filters. The status filter narrows the chart and records.
- With the supplied workbook and default settings, the six fund categories
  show seven calculated-series alerts and ten published-series alerts. The
  optional market aggregate has zero for both metrics. Alerts are counted
  separately per metric and can describe the same report and category.

The engine lives in `src/anomalies.py`, the Streamlit tab in
`src/smartflow.py`, and the regression tests in `tests/test_smartflow.py`.


## Phase 3 · Explainable AI

The Explainable AI tab lists SmartFlow alerts for the active date, category,
metric and scoring settings. A missing or insufficient observation cannot
generate an alert. The explanation engine also describes these unscored
statuses when called directly. Ranked alert options use descending absolute
robust z-score, with report date and category as tie-breakers. This ordering
measures deviation within the active selection.

The historical comparison shows the exact earlier, valid same-category points
used to score the selected alert. The evidence table and UTF-8 text download
give the report date, metric, source sheet and original file, baseline median
and MAD, observed change, absolute-score threshold, and signed difference in
percentage points. English and French templates share numeric formatting and
ISO dates. The explanation describes the statistical decision and its limits.


## V2 installation and configuration

Use the Windows PowerShell install and launch commands at the top of this
README. The application needs Python 3.11+, the dependencies in
`requirements.txt`, and the original workbook at the documented path.
Workbook mode runs with no credentials. Run the same pytest command before
a demo or deployment.

| Module | What it shows |
| --- | --- |
| FundPulse | Market KPIs, category trends, indices, flows, portfolio composition and source CSVs |
| SmartFlow | Category-level anomaly scores and filtered alert evidence |
| Explainable AI | English/French statistical explanations and TXT export |
| FundCopilot | Sourced chat answers through validated workbook queries and optional Gemini interpretation |
| Predictive Analytics | The earlier exact-seven-day net asset experiment |
| Risk Radar | Absolute robust z-score heatmap, original row provenance and prior baseline |
| AI Investigation Center | An English/French investigation brief tied to the current Risk Radar selection, with TXT export |
| Forecast Lab | Persistence, moving average and lagged ridge comparisons on common walk-forward weeks |
| Scenario Studio | A single-category shock on the latest reconciled actual report |

For optional Gemini access, put `GEMINI_API_KEY` in an environment variable
or a locally readable `.streamlit/secrets.toml`. Keep the key out of Git.
Set `GEMINI_FREE_TIER_CONFIRMED=true` only after checking that your project
and selected model qualify. The app defaults to `gemini-2.5-flash`.
Set `GEMINI_MODEL` to `gemini-3.1-flash-lite` if that is the supported
free-tier model for your project. Live access depends on the project's
credentials and quota. The app uses workbook fallback for missing
credentials or Gemini failure. If Streamlit itself fails during startup
with a secrets file access error, restore local read access to that file or
launch with an explicitly configured, readable secrets path.

Forecast Lab uses actual seven-day pairs. The current workbook provides 20
baseline folds, of which 12 are comparable with ridge at the default settings.
No series qualifies for a next-week estimate under the default comparison.
Scenario Studio uses the source scale with unspecified currency. Its outputs
are conditional on the entered shock and the fixed values of other categories.

### Five-minute hackathon demo

| Time | Step | What to show |
| --- | --- | --- |
| 0:00–0:55 | Discover | Open Overview and show the market KPI and the reported category share chart. Point to the source, report date and workbook-unit badges. |
| 0:55–1:50 | Detect | Open Risk Radar, choose Obligations CT and the calculated seven-day metric, then select 24 April 2026. Show the +18.923% change, 7.372 robust z-score and 3.500 threshold. Gray cells indicate unavailable scores. |
| 1:50–2:55 | Investigate | Generate a brief for the selected Risk Radar observation. Show the original report filename, export line 922, and earlier baseline observations. Download the TXT brief. Workbook mode supports the same evidence flow when Gemini is unavailable. |
| 2:55–3:55 | Forecast | Open Forecast Lab for TOTAL. Compare persistence, the moving average, and ridge on 12 common weeks. Show why the lab withholds a next-week estimate. |
| 3:55–5:00 | Simulate | Apply +10% to Actions in Scenario Studio. Show the before/after amounts and the hypothetical market total of 839,966,205,270.95 on the workbook scale. State the fixed-other-categories assumption and close on source transparency. |


## Streamlit Community Cloud deployment checklist

- Use a dedicated GitHub repository containing this project's files only.
  This local checkout has a parent Git root, so pushing that root could
  include unrelated files. With the project at the GitHub repository root,
  enter `app.py` as **Main file path**. If the intended GitHub repository
  deliberately preserves the current project subdirectory, enter
  `Desktop/Morocco-FundGuard-AI/app.py`.
- Include `app.py`, `requirements.txt`, all runtime Python files under
  `src/`, and `data/OPCVM_2026_Consolide (1).xlsx` with that exact spelling
  and filename. Keep `requirements.txt` alongside the entrypoint. Include
  `requirements-dev.txt` and `tests/` for local regression testing.
- Select Python **3.11** in Advanced settings. The runtime file pins the
  directly used packages from the verified local stack.
- Keep the Cloud app in workbook mode for the first smoke test. For optional
  Gemini access, enter the secret in the Cloud **Secrets** panel, along with
  `GEMINI_FREE_TIER_CONFIRMED = true` only after verifying the model and
  free-tier project. `GEMINI_MODEL` is optional. Keep local secrets files,
  credentials, caches, and virtual environments outside Git.
- Before authorizing any push, confirm the selected branch includes the
  current V2 modules and that the workbook is present. Several V2 files
  were untracked at preparation time. Check the exact branch contents.
- After an authorized deployment, open Overview and verify the workbook loads.
  Check Explainable AI, a FundCopilot answer in workbook mode, and the V2 tabs.
  Review build logs and exercise the installed app before sharing its URL.
  Local checks do not establish Cloud memory use, startup time, or Gemini
  entitlement.

See the official [Community Cloud deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
and [dependency layout](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies).
#   M o r o c c o - F u n d G u a r d - A I  
 