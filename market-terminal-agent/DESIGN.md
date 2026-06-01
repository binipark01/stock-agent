# Design

## Source of truth
- Status: Active draft
- Last refreshed: 2026-05-30
- Primary product surfaces:
  - Browser-based professional financial terminal.
  - Keyboard-first command shell.
  - Multi-panel workspace for market data, security analysis, news, charts, portfolio, alerts, and research.
- Evidence reviewed:
  - `README.md`: repo is a US-stock-first local research and alert agent with market briefings, sector/theme strength, filings, news, technical snapshots, Telegram/TradingView flows.
  - `scripts/stock_theme_dashboard.py`: current browser UI is a large single-file prototype with command palette, theme boards, ticker drilldowns, portfolio/risk/screening-like pages, and many synthetic terminal-style views.
  - `src/us/**`: existing backend capabilities include market data, news, options, earnings, SEC filings, sector/theme intelligence, technical snapshots, and agent pipeline/state.
  - User direction on 2026-05-30: the product target is not an alert-result viewer; the target is a Bloomberg-terminal-like financial workstation.

## Brand
- Personality:
  - Dense, professional, fast, command-first, data-rich.
  - Looks like a trader/research workstation, not a marketing dashboard.
- Trust signals:
  - Every screen must show data timestamp, source, freshness, and failure state.
  - Every command should produce a useful decision surface, not a decorative placeholder.
  - Screens should expose calculations and assumptions where possible.
- Avoid:
  - Treating Telegram/cron output as the center of the product.
  - Adding dozens of fake or thin “Bloomberg-ish” pages that do not answer a real workflow.
  - Pure cosmetic imitation without data depth, keyboard flow, persistence, or auditability.
  - Direct trademark/brand cloning. The goal is a professional terminal with comparable workflow density, not copying protected Bloomberg branding/assets.

## Product goals
- Goals:
  - Build a real financial terminal/workstation, not an alert viewer.
  - Make the command line the primary navigation model.
  - Support real workflows: market overview, ticker analysis, charting, news/filings, screening, portfolio/risk, watchlists, alerts, and research notes.
  - Make every panel actionable: sortable, drillable, filterable, exportable, and connected to command history.
  - Convert existing agent/data modules into terminal functions.
- Non-goals:
  - Do not make cron/Telegram alert output the default product model.
  - Do not keep adding low-value command names just to inflate feature count.
  - Do not implement trading execution with real money without a separate safety design.
  - Do not depend on one proprietary data provider as a hard requirement.
- Success signals:
  - A user can type commands such as `DES AAPL`, `FA NVDA`, `GP NVDA`, `CN TSLA`, `EQS`, `WEI`, `PORT`, `PMON`, `PMGR`, `RISK360`, `NEWS`, `ALERTS` and get a useful terminal page.
  - The home screen answers “what should I look at now?” without relying on Telegram text.
  - Each page has real data, source/freshness indicators, and a clear next action.
  - The system can save workspace layout, command history, watchlists, notes, and portfolio state.

## Personas and jobs
- Primary personas:
  - Individual trader/researcher watching US equities.
  - Power user who prefers keyboard commands over clicking menus.
  - Research agent operator using local data, public APIs, and generated analysis.
- User jobs:
  - Find what is moving now.
  - Understand a security quickly.
  - Compare stocks, sectors, factors, and themes.
  - Track news, filings, earnings, options, and catalysts.
  - Build and monitor watchlists/portfolios.
  - Turn data into a decision checklist.
- Key contexts of use:
  - Pre-market, intraday, post-market review.
  - Fast ticker lookup during a market move.
  - Deep dive on a company or theme.
  - Monitoring alerts and follow-up tasks.

## Information architecture
- Primary navigation:
  - Command input is primary.
  - Clicks are shortcuts, not the main route.
  - Persistent multi-panel workspace remains visible while command pages change.
- Core routes/screens:
  - `WSP MARKET|SECURITY <ticker>|TRADER|RISK|RESEARCH|DATA`: Bloomberg-style multi-panel workspace deck for the main operating modes.
  - `HOME` / `WEI`: world/equity overview, indices, rates, FX/crypto, commodities, breadth, top movers.
  - `DES <ticker>`: security description / company snapshot.
  - `GP <ticker>`: price chart, volume, technicals, events.
  - `CN <ticker|query>`: company/market news.
  - `FA <ticker>`: fundamentals and financial summary.
  - `EE <ticker>`: earnings calendar/preview/revision summary.
  - `EQS`: equity screener.
  - `RV <ticker|basket>`: relative value / peer comparison.
  - `PORT`: local portfolio monitor.
  - `RISK`: exposure, drawdown, scenario, correlation, concentration.
  - `ALERTS`: alert manager and live tape.
  - `NOTE` / `RESEARCH`: notes, thesis, saved views.
- Content hierarchy:
  1. Command bar and global status.
  2. Market strip / freshness / session status.
  3. Workspace panels.
  4. Main function page.
  5. Context/right rail: related news, events, alerts, watchlist, next actions.

## Design principles
- Principle 1: Command-first, not dashboard-first.
  - A useful terminal starts from fast typed functions and stateful workspaces.
- Principle 2: Real data beats visual density.
  - A sparse screen with real timestamped data is better than a dense fake terminal.
- Principle 3: Every panel needs a job.
  - If a panel cannot answer a trading/research question, remove or demote it.
- Principle 4: Drilldown is mandatory.
  - Market → sector/theme → ticker → chart/news/fundamentals/risk must be one or two actions.
- Principle 5: Persistence matters.
  - Layout, font size, watchlists, portfolio, notes, and recent commands should survive refresh.
- Tradeoffs:
  - Dense UI is acceptable only if readability and keyboard flow remain strong.
  - Public/free data limits will exist; make source and freshness visible instead of hiding gaps.

## Visual language
- Color:
  - Dark terminal background.
  - Amber for command/navigation.
  - Green/red for positive/negative market movement.
  - Cyan/blue for secondary links and data-source hints.
  - Muted gray/green for metadata.
- Typography:
  - Monospace terminal font.
  - Default text must be readable at normal browser zoom; do not default to tiny text.
  - User-adjustable text scale is required.
- Spacing/layout rhythm:
  - Dense but not cramped.
  - Resizable gutters for major panels.
  - Tables should preserve alignment and avoid hiding critical numbers.
- Shape/radius/elevation:
  - Minimal radius.
  - Thin grid borders.
  - Avoid glossy dashboard cards unless they carry real data.
- Motion:
  - Minimal. Prefer instant command response and subtle refresh indicators.
- Imagery/iconography:
  - No decorative icons unless they improve scanning.

## Components
- Existing components to reuse:
  - Command bar.
  - Ticker/market tape.
  - Terminal rows.
  - Sortable tables.
  - Quick command buttons.
  - Resizable panel gutters.
  - Local storage persistence for layout/font/workspace state.
  - WSP workspace density/column persistence: `WSP 2COL`, `WSP 3COL`, `WSP 4COL`, `WSP DENSE`, `WSP FOCUS`, `WSP RESET`.
  - WSP per-panel size/focus persistence: `WSP WIDE <panel>`, `WSP FULL <panel>`, `WSP NORMAL <panel>`, `WSP SOLO <panel>`, `WSP HIDE <panel>`, `WSP SHOW <panel|ALL>`, `WSP PANELS RESET` let the user resize, enlarge, collapse, and restore workspace panels without leaving the command shell.
  - UI language selector: `한국어` / `English` dropdown plus `LANG KO` / `LANG EN` / `한글판` / `영문판` commands; selected language persists in localStorage, and `?lang=ko|en` can set the initial shell language.
  - RUNX session checklist persistence: `RUNX NEXT`, `RUNX DONE <stage>`, `RUNX TODO <stage>`, `RUNX RESET`, and Korean aliases like `RUNX 완료 시장` turn the session runbook into a localStorage-backed workflow tracker instead of a static command list.
  - NEXT action stack persistence: `NEXT GO`, `NEXT DONE <row>`, `NEXT TODO <row>`, `NEXT RESET`, and Korean aliases like `NEXT 완료 1` turn surveillance/idea/watch/query candidates into a localStorage-backed execution stack with a top-action KPI.
  - ACTX action blotter persistence: `ACTX GO`, `ACTX DONE <row>`, `ACTX TODO <row>`, `ACTX RESET`, and Korean aliases like `ACTX 완료 1` turn ORDER/HEDGE/PMGR/ALERT/RUNBOOK candidates into a single persisted execution blotter.
  - TPLAYX tactical playbook persistence: `TPLAYX GO`, `TPLAYX PIN <row>`, `TPLAYX DONE <row>`, `TPLAYX TODO <row>`, `TPLAYX UNPIN <row>`, `TPLAYX RESET`, and Korean aliases like `TPLAYX 고정 1` turn ACTX/NEXT/IDEA candidates into a saved tactical playbook.
  - TPLAYX trade bridge: `TPLAYX TICKET <row>` opens a paper ticket from a tactical candidate, `TPLAYX OMS <row>` stages the extracted ticker into the local paper OMS, and `TPLAYX FILL <row>` performs a local-only paper fill that updates `PORT`/`PMON` and feeds `RISK360`.
  - Live workflow control tower: saved `COMPQ` comparisons, saved `PAIR BOOK` pairs, open `ACTX` items, and `TPLAYX` tactical candidates now surface together in `NEXT`, `ACTX`, `TPLAYX`, `TRADAR`, `CMDX`, and `WORKFLOWCONTROLX`, so the terminal exposes a single prioritized route from saved idea to paper execution and risk review.
  - LIVEQ global execution queue: `LIVEQ` / `GQ` / `전역큐` / `실행큐` merges saved `COMPQ` comparisons, `PAIR BOOK` / `PBOOK` pairs, active paper `OMS` orders, and pinned `TPLAYX` candidates into one actionable blotter with `LIVEQ GO`, `LIVEQ TICKET`, `LIVEQ STAGE`, `LIVEQ PORT`, `LIVEQ FILL`, `LIVEQ DONE`, `LIVEQ TODO`, and `LIVEQ CLEAR`.
  - WSP Trader execution bridge: `WSP TRADER` now starts from `LIVEQ` instead of a scattered alert/result view. It shows `EXECUTION BRIDGE`, `GLOBAL EXECUTION QUEUE`, `TACTICAL PLAYBOOK`, `PAPER OMS`, and `PORT / RISK HANDOFF` panels so a user can move from candidate discovery to paper ticket, paper OMS, paper fill, PMON, and RISK360 without hunting for separate pages.
  - WSP flow rails: `WSP MARKET`, `WSP SECURITY <ticker>`, and `WSP RISK` now each include a full-width operating/decision/control rail that explains what to open next and why, linking market regime → security research → trader workflow → paper OMS → portfolio/risk review.
- New/changed components:
  - Multi-panel workspace deck: `WSP MARKET`, `WSP SECURITY <ticker>`, `WSP TRADER`, `WSP RISK`, `WSP RESEARCH`, `WSP DATA` render real compact panels for regime/indexes, security master, chart/news/SEC, trader queue, paper OMS, risk/KRI/shock ladder, research/catalyst flow, and data-control surfaces. The deck supports persisted column/density commands so the user can make it dense like a terminal or readable like an analysis workspace.
  - Function registry with metadata: command, aliases, required arguments, data sources, status, last refresh.
  - Security master card.
  - Provider-backed security data pack: `/api/security?symbol=...` feeds `DES`, `FA`, `EE`, `GP`, ticker-scoped `CN`, quote surfaces `QMON`/`QMON <ticker>`, market microstructure surface `DEPTHX <ticker>`/`LEVEL2 <ticker>`, paper execution surfaces `TICKET <ticker>`/`ORDER ...`/`OMS`/`ORDX`, event/options surfaces `EARN <ticker>`/`OPTX <ticker>`, local-book surfaces `PORT`/`PMON`/`PMGR`/`RISK360`, watchlist surfaces `WATCH`/`WATCHX`/`WATCHRISK`, screener surfaces `EQS`/`SCNR`, and relative-value surface `RV <ticker>` from Toss WTS insights, SEC company submissions, and optional yfinance when installed.
  - Chart panel.
  - News/filing event tape.
  - Provider-backed screener builder: `EQS`/`SCNR` combine terminal signals with provider price, market cap, target gap, SEC events, and direct routes into `DES`, `GP`, `CN`, `WATCH`, and `PORT`.
- Provider-backed peer relative-value monitor: `RV <ticker>` combines theme-overlap peers with provider price, market cap, target gap, SEC filings, and routes into pair/watch/portfolio workflows.
- Provider-backed pair desk: `PAIR <base>|<peer>` opens a two-security relative-value desk with normalized pair chart, peer-minus-base spread, target-gap spread, market-cap ratio, SEC/event context, pair execution rail, and local paper routes. `PAIR SAVE <base>|<peer>` persists the pair in a local `PAIR BOOK`/`PBOOK` monitor with recomputed spread/risk and one-click execution routes; `PAIR QUEUE <base>|<peer>` saves it to `COMPQ`, `PAIR STAGE <base>|<peer>` stages both long/short legs into the local paper OMS, `PAIR TICKET <base>|<peer>` opens the recommended long-leg ticket, and `PAIR PORT <base>|<peer>` writes a local long/short paper portfolio pair.
  - Provider-backed quote monitor: `QMON` shows provider price, market cap, target gap, SEC coverage, theme hits, and direct action routes; `QMON <ticker>` opens a security quote ticket with field board, hit tape, SEC/event overlay, and next actions.
- Quote Monitor Book and worksheet: `QMON BOOK`, `QMON SAVE <name> = <tickers>`, `QMON LOAD <name>`, `QMON DEL <name>`, `QMON CLEAR`, `QMON TECH SORT RISK`, `QMON TECH SORT TARGET`, `COMP TECH`, `COMPARE QMON TECH`, and Korean aliases such as `호가북`, `호가 저장 TECH = DELL NVDA AAPL`, `호가 TECH 정렬 리스크` persist named multi-security quote boards in localStorage, rank them by worksheet score, opportunity, risk, activity, move, target gap, RSI, volume, hits, or market cap, and route saved/preset monitors directly into the security comparison matrix.
  - Provider-backed market-depth proxy: `DEPTHX <ticker>` / `LEVEL2 <ticker>` exposes spread estimate, depth ladder proxy, imbalance, liquidity score, route plan, OMS/TICKET handoff, and explicit no-live-Level-2 disclosure.
  - Provider-backed paper execution workflow: `TICKET <ticker>` / `ORDER BUY <ticker> ...` creates a pre-trade ticket with price, notional, target gap, SEC/event overlay, risk checks, route/TCA plan, and `OMS ADD`; `OMS` persists local paper orders and `ORDX` includes those staged tickets. It never sends real broker orders.
  - Provider-backed event/options monitor: `EARN <ticker>` combines price/volume shock, target gap, range position, SEC filings, and explicit EPS/revenue estimate gaps; `OPTX <ticker>` exposes gamma/skew proxy while clearly marking live option-chain data as unavailable.
  - Provider-backed portfolio/risk blotter: local holdings, provider price, market cap, target gap, SEC filing coverage, P&L, risk action, and drilldown route.
  - Provider-backed watchlist manager: saved securities/themes, price, market cap, target gap, SEC coverage, theme signal, risk route, and add/delete/clear commands.
  - Source/freshness badge.
  - Error/partial-data banner.
- Variants and states:
  - Loading, stale, partial, empty, error, permission/API-limited.
  - Compact/default/large font states.
  - Korean/English product-shell language states; terminal command mnemonics remain English.
  - Side workspace/full workspace states.
- Token/component ownership:
  - CSS variables own colors, font size, panel dimensions, and control heights.
  - Terminal functions should eventually move out of the single-file prototype.

## Accessibility
- Target standard:
  - Practical keyboard-first accessibility.
- Keyboard/focus behavior:
  - `/` or `Ctrl+K` focuses command input.
  - Enter runs command.
  - Arrow navigation moves within selected table/function where possible.
  - Escape returns to home/clears transient state.
- Contrast/readability:
  - Default font size must be readable.
  - All critical color-coded values need text signs/labels, not color alone.
- Screen-reader semantics:
  - Tables should use table markup.
  - Buttons should be real buttons.
- Reduced motion and sensory considerations:
  - Avoid flashing or rapidly animated indicators.

## Responsive behavior
- Supported breakpoints/devices:
  - Primary target: desktop browser, 1440px+.
  - Secondary: laptop 1150px+.
  - Mobile is not a primary target for Bloomberg-like workflows.
- Layout adaptations:
  - Desktop uses multi-panel resizable workspace.
  - Smaller screens stack panels and disable drag gutters.
- Touch/hover differences:
  - Touch support is secondary; all core features must work by keyboard.

## Interaction states
- Loading:
  - Show command, source, and loading state.
- Empty:
  - Explain what command or data source is needed.
- Error:
  - Show the failed source/API and recovery action.
- Success:
  - Update command history and show timestamp.
- Disabled:
  - Explain missing provider/config.
- Partial data:
  - Show loaded provider names and missing providers separately; never fill EPS/revenue/fundamental fields with fabricated values.
- Offline/slow network:
  - Show cached data age and degraded mode.

## Content voice
- Tone:
  - Direct trader/research language.
  - Korean explanations are allowed, but command labels can stay Bloomberg-style English mnemonics.
  - Default browser shell language is Korean for this user; `LANG EN` switches the shell back to English and `LANG KO` restores Korean.
- Terminology:
  - Use consistent terms: Security, Market, News, Chart, Screener, Portfolio, Risk, Alert, Workspace.
  - Do not call the product an alert viewer.
- Microcopy rules:
  - Tell the user what to do next: “type DES NVDA”, “open GP”, “add to WATCH”.
  - Avoid vague “summary” cards without action.

## Implementation constraints
- Framework/styling system:
  - Current UI is implemented in `scripts/stock_theme_dashboard.py` as a generated HTML/JS/CSS page.
  - This is acceptable for prototype speed but not a durable terminal architecture.
- Design-token constraints:
  - Use CSS variables for font, color, panel size, and density.
- Performance constraints:
  - Command switching must feel instant.
  - Large tables should be bounded, virtualized, or paged if needed.
- Compatibility constraints:
  - Must run locally on Windows/PowerShell and browser.
  - Must not require paid data credentials for basic mode.
- Test/screenshot expectations:
  - Browser smoke tests must verify load, command execution, no console errors, font/layout persistence, and core command pages.
  - Server/API smoke tests cover local HTML/API load, stable browser selectors, Hermes envelope stripping, sensitive runtime redaction, output filename validation, security symbol normalization, and local security cache behavior.


## Current implementation notes
- 2026-05-30:
  - `WSP TRADER` and `WF EXEC` now expose the full execution chain: tactical candidate, paper ticket, paper OMS, paper fill, `PMON`, and `RISK360`.
  - `WSP MARKET`, `WSP SECURITY <ticker>`, and `WSP RISK` now expose first-screen flow rails (`MARKET OPERATING RAIL`, `SECURITY DECISION RAIL`, `RISK CONTROL RAIL`) so the user can understand how to use each workspace without reading a separate manual.
  - Terminal home now has a numbered operator rail (`GO` first operating order) and a Korean command dock so a user can start with `시장판`, `종목판 DELL`, `주문판`, `리스크판`, or `데이터판` instead of guessing Bloomberg-style mnemonics.
  - Terminal home now also includes `TODAY OPERATING BLOTTER` / `오늘 운영 블로터`: a live priority queue merged from `RISK360`, `NEXT`, `TPLAYX`, `TOPX`, and leader rows. `GO 1` / `GO 2` opens the ranked rows directly, while `오늘할일`, `운영블로터`, and `액션보드` return to the queue.
  - `TPLAYX TICKET 1`, `TPLAYX OMS 1`, and `TPLAYX FILL 1` connect tactical candidates to the existing paper ticket/OMS/PORT path; `OMS FILL 1` remains available as the explicit local-only fill step and `RISK360` now includes paper OMS rows before/after fill.
  - `TPLAYX` is now a persisted tactical playbook: `TPLAYX PIN 1` saves a candidate, `TPLAYX GO` opens the top pinned/incomplete play, `TPLAYX DONE 1` / `TPLAYX TODO 1` mark progress, and `TPLAYX RESET` clears local playbook state.
  - `ACTX` is now a persisted action blotter: `ACTX GO` opens the first unfinished ORDER/HEDGE/PMGR/ALERT/RUNBOOK row, `ACTX DONE 1` / `ACTX TODO 1` mark rows, and `ACTX RESET` clears local progress.
  - `NEXT` is now a persisted action stack: `NEXT GO` opens the first unfinished action, `NEXT DONE 1` / `NEXT TODO 1` mark rows, and `NEXT RESET` clears local progress.
  - `PORT` is now a local portfolio workstation, not an alert-result page.
  - `PMON` monitors local positions with provider price, SEC filings, target gap, factor/theme risk, and P&L.
  - `PMGR` overlays the local book on top of model theme allocation so the user can see actual positions before model suggestions.
  - `RISK360` now includes a `PORTFOLIO` bucket for local-position risk rows.
  - `WATCH` is now a provider-backed watchlist workstation; `WATCHX` is the command center and `WATCHRISK` is the risk queue.
  - `EQS` and `SCNR` are now provider-backed ticker screeners with market cap, target gap, SEC filing coverage, and direct watch/portfolio actions.
  - `RV <ticker>` is now a provider-backed peer relative-value workstation with base security, peer coverage, target-gap spread, market-cap ratio, SEC coverage, and pair/watch/portfolio routes.
  - `QMON` is now a provider-backed quote monitor blotter; `QMON <ticker>` is a provider-backed quote/security tape with quote fields, terminal hit tape, SEC/event overlay, and routes into `DES`/`GP`/`FA`/`CN`/`EARN`/`OPTX`.
  - `DEPTHX <ticker>` / `LEVEL2 <ticker>` is now a provider-backed market microstructure/depth proxy with estimated spread, synthetic depth ladder, imbalance, liquidity score, route plan, and OMS/TICKET handoff.
  - Language mode is now available from the visible `언어` header dropdown, the `LANG` settings page, and commands: default `한국어`, `LANG EN`/`영어`/`영문판`/`언어 영어` for English, `LANG KO`/`한국어`/`한글`/`한글판`/`언어 한국어` for Korean; the shell/header/home/footer/core command guidance updates immediately and persists locally.
  - Korean mode now also translates core chrome/table headers, empty states, panel metadata, and high-use workspace pages (`DES`, `FA`, `EE`, `GP`, `CN`, `EQS`, `RISK360`, `PORT`, `PMGR`, `DEPTHX`) through shared i18n/content-translation layers; command mnemonics and tickers intentionally remain English.
  - `TIDX`/`FINDCMD` now act as a real terminal function index: each function row shows command/key, group, status, data source, workflow purpose, sample command, next-command route, and exportability so users can discover how to operate the workstation without guessing.
  - The terminal home now includes a workflow launcher with first-class rails for market regime, security research, idea generation, portfolio/risk, paper execution, and data/control so the product opens as an operating console instead of a static alert dashboard.
  - `WF` / `WORKFLOW` now opens a workflow navigator that turns those rails into runnable command chains. `WF MARKET`, `WF SECURITY DELL`, `WF IDEA`, `WF PORT`, `WF EXEC`, `WF RISK`, and `WF DATA` show ordered next steps, live status, data source, and direct buttons so users do not have to guess how to operate the terminal.
  - `SEC360 <ticker>` is now the single-security workstation that binds `DES`, `FA`, `EE`, `GP`, `CN`, `DEPTHX`, `TICKET`, `WATCH`, local portfolio state, SEC filings, peer read-through, and action ladders into one ticker-centric operating page.
  - `NOTE <ticker> ...` and `NOTES <ticker>` now behave as local ticker-linked research notes; `SEC360 <ticker>` surfaces matching notes so the workflow includes thesis capture, not just data viewing.
  - `EARN <ticker>` is now a provider-backed event/earnings risk workstation with event score, price/volume shock, target gap, 52-week range, SEC event filings, catalyst flow, and honest EPS/revenue data-gap disclosure.
  - `OPTX <ticker>` is now a provider-backed option/gamma risk proxy with gamma risk, skew proxy, event/SEC overlay, workflow routing, and explicit option-chain data-gap disclosure.
  - `TICKET <ticker>` and `ORDER BUY <ticker> ...` are now provider-backed paper pre-trade tickets with price, notional, target gap, SEC/event overlay, pre-trade risk checks, route/TCA plan, and explicit no-real-execution warning.
  - `OMS` is now a provider-backed local paper order blotter, and `ORDX` includes staged local OMS tickets above model-generated execution ideas.
  - `WSP` is now the primary Bloomberg-style multi-panel entry point. `WSP MARKET` opens a real market command deck; `WSP SECURITY <ticker>` opens a ticker workstation; `WSP TRADER`, `WSP RISK`, `WSP RESEARCH`, and `WSP DATA` open task-specific multi-panel decks with direct command handoff buttons.
  - Each WSP deck now includes a `WSP ACTION QUEUE / 액션 큐` panel. It filters the shared operating blotter by workspace context (`MARKET`, `SECURITY <ticker>`, `TRADER`, `RISK`, `RESEARCH`, `DATA`) and `WSP GO 1` opens the current deck's top action instead of forcing the user back to the home blotter.
  - WSP decks now have terminal-style panel focus controls: panels are numbered on render, `WSP PANEL 1`, `WSP NEXT PANEL`, `WSP OPEN PANEL`, and `WSP FOCUS ACTION` manipulate the focused panel, while keyboard shortcuts inside WSP use `1-9` to focus panels, `[`/`]` to move, `Enter` to open the focused panel, and `G` to run `WSP GO 1`.
  - WSP workspaces now persist the full operating context: `WSP SAVE <name>` stores the active WSP deck, layout, panel sizes/visibility, focus, full-workspace flag, symbol, and language in localStorage; `WSP LOAD <name>` restores it; `WSP PRESETS` opens the workspace book with built-in `MARKET`, `SECURITY`, `TRADER`, `RISK`, `RESEARCH`, and `DATA` presets.
  - WSP layout is now command-adjustable and persisted in localStorage: `WSP 2COL`, `WSP 3COL`, `WSP 4COL`, `WSP DENSE`, `WSP FOCUS`, and `WSP RESET` change panel column count, row height, spacing, and minimum panel height.
  - `PAGE`/`PAGES` now behaves like workspace persistence instead of a static alert snapshot: `PAGE SAVE CURRENT` saves the current terminal view, `PAGE SAVE MYWSP = WSP SECURITY DELL` saves an explicit command workspace, and `PAGE LOAD <name>` restores the saved command or DASH layout directly.
  - The command bar now accepts Bloomberg-style security/function order for core ticker workflows: `DELL US Equity DES`, `DELL GP`, `NVDA CN`, `AAPL US Equity EE`, `MSFT SEC360`, and `DELL WSP` normalize into the existing terminal functions while stripping `<GO>` / trailing `GO`.
  - `GUIDE` / `사용법` / `시작` opens a short Korean-first operating guide that shows the actual workflow order: market deck, ticker workstation, research functions, watch/portfolio/risk, page save/load, and readability/layout commands.
  - Single ticker input now routes to the ticker workstation (`DELL` -> `SEC360 DELL`), and unknown/mistyped commands land on a `CMD?` resolver page with nearest function matches plus ticker/workflow quick actions instead of silently falling back to an empty/unclear screen.
  - Trader-style short commands now work without the longer `TICKET`/`OMS ADD` form: `BUY DELL 1 @100` and `SELL DELL 1 @110` open provider-backed paper pre-trade tickets, `STAGE BUY DELL 1 @100` saves a local paper OMS order, and `WATCH DELL` adds the ticker to the local watchlist. These remain paper/local only; no broker order is sent.
  - Paper OMS now has a local lifecycle instead of stopping at `STAGED`: `OMS FILL 1`, `OMS FILL DELL`, `OMS 체결 1`, or `FILL DELL` marks the matching paper order as `FILLED`, stores fill price/time, and applies the paper fill to local `PORT`; `OMS CANCEL 1`, `OMS CANCEL DELL`, or `CXL DELL` marks it `CANCELLED` without deleting audit history, while `OMS DEL 1` / `OMS DEL DELL` remains a hard local delete.
  - `GP <ticker/theme>` is now a more terminal-like Graph Profile workstation: range tokens (`30D`, `90D`, `ALL`), moving-average tokens (`MA5`, `MA20`), normalized view (`NORM`), price-action KPIs, drawdown, MA overlay, and a price-action ladder are shown with SEC/event context.
- `COMP` / `COMPARE` now works for securities, saved/preset QMON monitor names, and themes. `COMP DELL NVDA ORCL`, `COMP TECH`, or `COMPARE QMON TECH` opens a multi-security comparison matrix with normalized performance chart, provider price/move, target-gap spread, market-cap ratio, SEC/event context, and a Compare Execution Workflow Rail that routes the comparison into `DES`/`FA`/`GP`/`CN`, `PAIR`/`RV`, local paper `TICKET`/`STAGE`, `WATCH`, and `PORT` actions, while `COMPARE AI|반도체` remains a theme comparison.
- Compare execution queue: `COMPQ`, `COMPQ SAVE TECH`, `COMPQ SAVE <name> = <tickers>`, `COMPQ GO 1`, `COMPQ TICKET 1`, `COMPQ STAGE 1`, and `COMPQ PORT 1` persist comparison candidates in localStorage, expose them as ACTX/TPLAYX action rows, and keep all order-related actions inside the local paper workflow.
- `PAIR <base>|<peer>` has been upgraded from a timestamp move correlation readout into a provider-backed pair trade workstation with normalized base/peer chart, spread chart, long/short setup read, local paper staging commands, and queue handoff through `COMPQ SAVE <base> <peer>`.
  - `LIVEQ` is now the cross-workflow execution queue: it ranks and routes `COMPQ`, saved `PBOOK` pairs, active `OMS` orders, and pinned tactical candidates without requiring the user to remember which page originally created the idea. `LIVEQ STAGE <row>` can stage pair legs into the paper OMS, `LIVEQ FILL <row>` can paper-fill active OMS rows into `PORT`, and `LIVEQ DONE/TODO` persists queue triage state locally.
  - `WSP TRADER` now embeds `LIVEQ` as its first operating surface and the terminal home/guide include `LIVEQ` / `전역큐` shortcuts, making the intended execution workflow visible without memorizing the originating page.
  - `BQL` is now dual-mode: theme queries still work (`BQL BREADTH>60 RSI>65`), while security queries open a provider-backed result table (`BQL GET(TICKERS) WHERE MOVE>3 RSI>60`, `BQL PX>100 MCAP>10B TARGETGAP>0`, `BQL SEC=1 EVENT<70`) with price, market cap, target-gap, SEC/event fields, and direct `DES`/`GP`/`CN`/`WATCH`/`PORT` routes.
  - The new `BQL` theme/security query pages are language-aware: Korean mode renders Korean titles, explanations, KPI labels, query-plan labels, table headers, empty states, and side labels while preserving Bloomberg-style command mnemonics.
  - `FLDS` / `FIELDS` is now a Bloomberg-style field browser. `FIELDS` shows separate theme-query and security-BQL field catalogs, while `FLDS DELL` shows current field values, aliases, field type, data source, runnable `BQL` examples, and provider status for one security.
  - `HELP <function>` / `? <function>` now opens a contextual function card, e.g. `HELP BQL`, `? FLDS`, `HELP WSP`, with Korean-first workflow text, source/status/depth metadata, runnable examples, related functions, and direct next-command buttons.
  - Command entry now has a Bloomberg-style autocomplete overlay: focus with `Ctrl+K` or `/`, search in Korean/English/function mnemonics, use `↑/↓` to select, `TAB` to fill, `ENTER` to run, and click any suggestion to execute. Suggestions merge recent commands, workflow starters, function index rows, tickers, themes, and Korean intent keywords.
  - A visible Bloomberg-style F1~F12 function-key strip now sits under the header and mirrors keyboard shortcuts: `F1 HELP`, `F2 WSP MARKET`, `F3 WSP SECURITY <ticker>`, `F4 WSP TRADER`, `F5 WSP RISK`, `F6 WSP RESEARCH <ticker>`, `F7 TICKET <ticker>`, `F8 PMGR`, `F9 WSP SAVE MORNING`, `F10 WSP PRESETS`, `F11 FONT BIG`, and `F12 BBG`.
  - Each full workspace now renders a context command rail above the page body. It derives the next 1~9 commands from the active screen (`WSP`, ticker pages, or home), supports click execution, `Shift+1..9` keyboard execution, and `CTX <n>` command execution, so the user can operate the terminal without memorizing command names.
  - The terminal now has a persistent page/tab stack under the function keys: every executed command is captured as a runnable tab, `TABS` opens the stack book, `BACK`/`FORWARD` and Korean `뒤로`/`앞으로` navigate it, and `Alt+←/→` gives Bloomberg-like page recall without losing the command-first workflow.
  - Terminal sessions can now be saved and restored with `SESSION SAVE MORNING`, `SESSION LOAD MORNING`, `SESSION BOOK`, `SESS`, and Korean `세션북` / `세션 저장 MORNING`: the snapshot includes the current command page, tab stack, WSP layout and panel state, language, font size, DASH cards, selected item, and recent command history.
  - `LANG` now opens a language settings card, `HELP LANG` documents aliases and persistence, and command autocomplete surfaces Korean/English language-switch commands.
  - Korean edition now supports Korean intent commands in the command bar: `시장` -> `WSP MARKET`, `종목 DELL` -> `SEC360 DELL`, `차트 DELL` -> `GP DELL`, `뉴스 DELL` -> `CN DELL`, `매수 DELL 1 @100` -> paper `BUY ...`, and `메모 DELL ...` -> ticker-linked `NOTE ...`.
  - `PRTU` / `PORT IMPORT` now loads multiple local portfolio holdings in one command (`PRTU DELL 2 300; NVDA 1 100`, `PORT IMPORT DELL,2,300;NVDA,1,100`, `PORT REPLACE ...`), giving the portfolio/risk stack a practical Bloomberg-like setup path without broker credentials.
  - Known gap: no broker import/execution yet; holdings and OMS orders are manual/localStorage only.
  - Known gap: no live market depth/order-book/fill provider yet; `DEPTHX` is a provider-backed proxy and execution screens are pre-trade/paper workflow only.
  - Known gap: no live option chain/open interest provider yet; `OPTX` is a risk proxy, not a full options terminal.

- 2026-06-01:
  - `SCMD <ticker>` / `CHAIN <ticker>` / `종목체인 <ticker>` now opens a ticker command-chain launcher. It orders the practical Bloomberg-style path around one security: `DES`, `SEC360`, `FA`, `EE`, `GP`, `CN`, `FLDS`, `BQL`, `RV`, `COMP`, `QMON`, `WATCH`, `DEPTHX`, paper `TICKET`/`OMS`, `LIVEQ`, `RISK360`, `PMON`, `NOTE`, and local `PORT`. This is intended as the first answer to “how do I use this screen?” before drilling into the denser workstations.
  - `WSP SECURITY <ticker>` now embeds that same command-chain as a first-screen `SECURITY COMMAND CHAIN` panel, adds `SCMD`/`CHAIN` to the workspace hero, and changes the old generic command strip into a ticker-specific function strip. The security workspace now starts with an explicit research → compare → paper execution → risk path instead of leaving the user to guess which dense panel to open first.
  - `MCMD` / `MCHAIN` / `시장체인` now opens a market-level command-chain launcher. It starts from `WSP MARKET`, `WEI`, `RISKON`, strong/weak themes, `LBD`, `TOPX`, `NEWSX`/`ATAPE`, then hands off to `SCMD <leader>`, `LIVEQ`, `WSP TRADER`, `RISK360`, `SENTRY`, and `TIDX`. `WSP MARKET` embeds the same `MARKET COMMAND CHAIN` as its first full-width panel so the screen starts with a usable operating path instead of disconnected dashboard widgets.

  - A persistent `COMMAND COACH` row now sits directly under the header. It shows the current screen, the next 1~9 runnable commands, `FONT BIG`/`FONT HUGE`, `PANELS RESET`, and a visible reminder that panel gutters are draggable, so users no longer need to guess how to operate the dense terminal.
  - Function keys now start from operating chains: `F2` opens `MCMD` and `F3` opens `SCMD <ticker>` before deeper `WSP` decks. The context command rail also prioritizes `MCMD`/`SCMD` on home, market, WSP market, WSP security, and chain pages.
  - Panel resizing is now more discoverable: existing draggable gutters show a `DRAG RESIZE` affordance on hover/drag, while the coach keeps `PANELS RESET` visible for recovery.

  - `REFRESH` now runs as a soft data refresh, not a user-context reset: it fetches `/api/dashboard`, keeps the active command, command input focus/selection, selected theme, focused WSP panel, and known scroll containers, shows a temporary `갱신중/REFRESHING` button state, and restores the screen after render. This reduces the previous full-rerender “broken screen” feeling.
  - `tests/test_stock_theme_dashboard_server.py` now adds server/API smoke coverage for the terminal prototype: index HTML includes stable `data-testid` browser-smoke selectors and the command-coach/chain entry points, `/api/dashboard` reads fixture Hermes output, cron envelopes are stripped, runtime secret-like values are redacted, invalid output filenames are rejected, and `/api/security` uses normalized ticker cache behavior without hitting live providers.
  - `docs/browser-smoke.md` now documents the real-browser smoke path and the verified commands: `MCMD`, `WSP MARKET`, `WSP SECURITY DELL`, `LIVEQ`, `LANG EN`, `LANG KO`, and `REFRESH`.

## Open questions
- [ ] Which data provider becomes the primary quote/history backend beyond current public/free helpers? / owner: user+agent / impact: determines real-time capability.
- [ ] Which terminal functions are first-class MVP versus later placeholders? / owner: agent / impact: prevents bloat.
- [ ] Should the browser UI remain single-file for now or be split into a small web app structure? / owner: agent / impact: maintainability.
- [ ] What is the minimum acceptable charting depth for `GP`? / owner: user+agent / impact: chart library/data needs.
- [ ] What portfolio state is required: manual holdings only, broker import, or simulated blotter? / owner: user / impact: risk/PORT scope.

