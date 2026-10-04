# Lotto Lab Agent Guide

This file is the working contract for every human or AI contributor. Read it before
changing the repository and keep it synchronized with architectural decisions.

## Product truth

Lotto Lab is a local PCSO lotto historical-analysis and weighted-random experiment
application for Lotto 6/42, Mega Lotto 6/45, Super Lotto 6/49, Grand Lotto 6/55,
and Ultra Lotto 6/58.

It is not a lottery predictor. Lotto draws are modeled as independent random events.
Historical resemblance, statistical rarity, and strategy weights must never be
described as winning probability or as a guarantee of improved winning odds.

## Architecture

The application is a modular monolith with four practical layers:

1. `domain.py` holds stable shared vocabulary and value definitions.
2. Feature packages contain calculations and use cases: `draw_history`,
   `analytics`, `strategy`, `generator`, and `backtesting`.
3. `persistence` implements local SQLAlchemy storage without owning business rules.
4. `ui` presents use cases through PySide6. `app.py` is the composition root.

Dependencies point inward: UI and persistence may depend on domain vocabulary;
domain code must not import Qt, SQLAlchemy, Pandas, Matplotlib, or infrastructure.
Feature services should accept narrow protocols or explicit input data rather than
reaching into widgets or global database sessions.

Use SOLID as a decision aid, not a reason to create one-interface-per-class. Prefer
small functions, immutable data objects, explicit dependencies, and cohesive modules.

## Project structure

```text
src/lotto_lab/
  app.py                 # application assembly and process entry point
  config.py              # immutable environment-derived runtime settings
  domain.py              # game definitions and number-group vocabulary
  draw_history/          # importing, validation, historical draw queries
  analytics/             # point-in-time feature and distribution calculations
  strategy/              # immutable versioned configuration and factor policies
  generator/             # dynamic weighted selection without replacement
  backtesting/           # chronological, look-ahead-safe simulations
  persistence/           # SQLAlchemy mappings, database lifecycle, repositories
  ui/                    # PySide6 windows, pages, models, workers, theme
tests/                   # mirrors production concerns
design-system/           # recorded visual design tokens and guidance
```

Keep public modules focused. Avoid generic `utils.py`, circular feature imports,
business logic in Qt slots, and database queries embedded in widgets.

Implemented service flow through Phase 7:

```text
DrawCsvImporter -> DrawRepository -> AnalyticsService/AnalyticsEngine
                                      -> GeneratorService/WeightedGenerator
                                      -> TicketRepository
```

The importer returns valid records and row-specific issues before persistence. The
repository skips existing game/date identities rather than overwriting source history.
`AnalyticsService.snapshot()` is the only production path used to assemble generator
history and applies a strict cutoff plus a per-game draw-count window.

`OfficialResultsClient` accesses only the public PCSO LottoMatik HTTPS history
endpoint, requests at most 100 rows per game, caps response bodies at 2 MB, validates
JSON fields through `HistoricalDraw`, and rejects future dates. The normal sync asks
for 50 recent records per supported game. `ResultsSyncService` tolerates individual
game-feed failures and never deletes or overwrites local history. `ResultsSyncController`
runs this work on a `QThread`; it starts automatically through a zero-delay Qt timer
after the main window appears and is also triggered by the Draw History refresh button.

## Domain terminology

- **Game**: one supported 6-of-N PCSO lotto product.
- **Draw**: an official result for one game on a calendar date.
- **Ticket / combination**: six distinct numbers within a game's valid range.
- **Historical window**: draws strictly before an evaluation cutoff, further limited
  by a configured count or period.
- **Number group / bucket**: exactly `1-10`, `11-19`, `20-29`, `30-39`, `40-49`,
  or `50-58`; ignore groups outside the selected game's range.
- **Range composition**: separate from legacy buckets, uses `1-9`, `10-19`,
  `20-29`, `30-39`, `40-49`, `50+`. Clip each range to the game maximum;
  omit `50+` for 6/42, 6/45 and 6/49. Preserve the legacy bucket factor so
  Jonathan Weighted v1 and disabled-range comparisons keep their behavior.
- **Factor**: an explainable positive multiplier applied to a candidate's weight.
- **Strategy**: a named family of weighting behavior.
- **Strategy version**: an immutable, numbered snapshot of strategy parameters.
- **Historical pattern score**: a 0-100 resemblance score for common historical
  characteristics. Never label it “Winning Probability.”
- **Backtest cutoff**: the target draw date; only earlier draws are observable.

## Weighting algorithm contract

Every currently eligible number begins each selection step at `base_weight = 1.0`.
For a candidate `n`, a strategy conceptually calculates:

```text
final_weight(n) = base_weight
                * cross_game_factor(n)
                * sequence_factor(n, partial_ticket)
                * bucket_factor(n, partial_ticket)
                * odd_even_factor(n, partial_ticket)
                * other_strategy_factors(n, context)
```

Normalize candidate weights, select one candidate, remove it from the candidate set,
then recompute every remaining weight against the new partial ticket. Selection is
weighted random without replacement. Prefer `secrets.SystemRandom` for ordinary
generation. A backtest may use an explicitly seeded pseudorandom source for exact
reproducibility; store that seed with the run.

Factors and thresholds belong in `StrategyParameter`, typed configuration objects,
or configuration files—not buried as numeric literals inside evaluation logic. Each
selected number must retain its final weight, factor breakdown, and explanations.

Soft weighting is the default. A candidate may receive a lower or higher positive
weight but must not be eliminated. Zero-weight/hard filtering is allowed only behind
an explicit experimental strategy setting and must be clearly disclosed.

Phase 4 built-ins are Pure Random v1, Jonathan Weighted v1, Cross-Game Only v1,
Bucket + Sequence v1, Historical Frequency v1, and Hybrid v1. Their complete typed
configuration is serialized into a single documented `config` strategy parameter.
Built-in values are defaults, not claims of optimality.

Range enhancement extends the Jonathan Weighted family with the next available
integer version (normally v2). Startup seeds this locked reference once using the
`jonathan_range_reference` parameter marker, without overwriting v1 or user clones.
Legacy JSON configurations default both new factors off. The enhanced reference
enables range weighting at 20% and high-number balance (active only for 6/55 and
6/58). Strategy Lab edits these settings through the existing clone/save flow.

`analytics.range_analyzer` computes range patterns, presence frequencies, mean
counts, and 40+/50+ count distributions from the selected game's snapshot window.
Uniform expectations use exact combinations without replacement, including range
sizes and game maxima. Empty history has no observed frequency, rather than a
fabricated zero. `strategy.range_weighting.StructuralWeights` compares terminal
pattern frequencies (and joint 40+/50+ counts) with those uniform expectations.
It integrates bounded positive preferences over uniform completions of the partial
ticket, and contributes the after/before potential ratio at each selection step.
This multiplies the existing factors; it never mandates a target pattern or boosts
every high number by a fixed amount. Strength applies to both structural factors;
the maximum terminal deviation is capped at 0.5 and the default smoothing prior
is 20 draws. Both are typed, serialized parameters. All unseen patterns retain
positive weight. Only the current snapshot/configuration is cached per generator,
so changing the target cutoff replaces the model. No new hard-filter mode exists.

## Strategy invariants

- Strategy versions that have generated a ticket or participated in a backtest are
  immutable. Lock the version before use and reject parameter edits after locking.
- To change parameters, clone the version and increment its integer version number.
- Names exposed to users include the version, for example “Jonathan Weighted v1.”
- Pure Random remains available as the control strategy.
- All factors are transparent, deterministic given context and configuration, and
  independently testable.

Generation locks a version before reading its configuration; ticket persistence also
locks transactionally. Built-ins are read-only references. Edits and cloning serialize
through SQLite BEGIN IMMEDIATE; clones increment the family's maximum version.

BacktestService orchestrates explicit draw, analytics, and run repository dependencies.
BacktestRepository locks selected versions and creates aggregate rows transactionally.
Each chronological target uses AnalyticsService with a strict date cutoff, including
cross-game data. Each strategy gets a separate equal-seeded random stream. Cancellation
and failures retain partial aggregates with explicit status. Statistics are descriptive
mean matches and population variance; no confidence intervals are claimed.

BacktestSettings is an additive table storing the historical draw-count window.
`BacktestRangePattern` is an additive normalized table keyed by run, strategy
version, and generated range-pattern string. It stores counts only, including
partial cancelled/failed runs. It is saved transactionally with match aggregates;
older runs without these rows remain readable and are labeled as lacking pattern
observations. Generated patterns use the new range boundaries for every strategy.
Startup creates missing tables without destructive schema changes. Repeatability
requires unchanged history, software, and settings. A forcibly interrupted process may
leave a running record; it must not be interpreted as completed.

JobController runs analytics, generation, and backtests on QThread workers with queued
result, error, and progress delivery. Backtests poll cancellation between tickets.
Matplotlib renders on the GUI thread and has equivalent data tables. Closing during
background work requests cancellation and defers close until work finishes.

All three data tables use ui.paged_table.PagedTable with 25 rows per page by default.
Range Analysis and generated backtest pattern tables also use this component.
Range Analysis is an Analytics tab sharing its game/window and background snapshot;
its observed/expected chart renders on the GUI thread with an equivalent data table.
Computed result tables page their existing rows; Draw History loads bounded repository
pages using limit/offset and a date/ID ordering for stable ties. Filters, page-size
changes, and refreshed results reset to page 1. Chart data remains independent of paging.

## Database structure

SQLite is local and is initialized through `persistence.Database`. Foreign keys are
enabled on every connection. SQLAlchemy 2.x declarative mappings are used.

- `Game` has game code, display name, pick count, and maximum number.
- `Draw` belongs to a game and is unique by game/date.
- `DrawNumber` stores six unique positioned values per draw.
- `Strategy` names a strategy family.
- `StrategyVersion` is a numbered immutable configuration snapshot.
- `StrategyParameter` stores one JSON-encoded value per version/key plus its meaning.
- `GeneratedTicket` records game, exact strategy version, timestamp, historical
  cutoff, pattern score, and overall explanation.
- `GeneratedTicketNumber` stores position, number, weight, factor data, and explanation.
- `BacktestRun` records game, date interval, workload, seed, timing, and status.
- `BacktestSettings` stores each run's historical draw-count window.
- `BacktestResult` records a strategy's aggregate result for each match count (0-6),
  with occurrences, mean, variance, and optional confidence interval.

Historical draws are source records. Strategy calculations must never update them.
Schema evolution after released builds should use migrations rather than destructive
recreation. Do not place large arrays of draws or per-ticket simulation traces in a
single JSON column merely for convenience.

## Important invariants

1. A ticket and draw contain exactly six distinct in-range numbers.
2. Number grouping uses the specified uneven first two groups; do not silently change
   `11-19` into `11-20`.
3. No backtest query or computed feature may observe a draw on or after its target
   draw date. This includes precomputed aggregates and caches.
4. Backtests iterate chronologically and build context as-of each target draw.
5. Historical records never change because a strategy ran.
6. Weight factors and scoring components are explainable and saved with results.
7. Unusual sequences, group concentration, or odd/even splits affect soft weights;
   they do not default to exclusions.
8. “Historical pattern score” is the only approved user-facing score term.
9. Long analysis and simulation work never runs on the Qt GUI thread. Workers report
   progress/results through queued signals, and widgets are touched only on the GUI
   thread.
10. Local data stays local unless the user explicitly invokes an import or future
    network feature. Automatic PCSO LottoMatik synchronization is the sole currently
    approved network exception and is read-only toward the remote service.

## Testing approach

Run `pytest` after every coherent change and before handoff. Tests mirror modules and
cover behavior rather than implementation details.

- Domain tests cover ranges, ticket validation, group boundaries, and terminology.
- Persistence tests use a temporary SQLite file, exercise constraints and rollback,
  and verify foreign-key behavior.
- Analytics and strategy tests use small hand-calculable histories.
- Generator tests inject deterministic random sources and verify dynamic recalculation,
  no replacement, valid ranges, and retained nonzero soft weights.
- Backtesting tests use deliberately distinctive future draws to prove they cannot
  leak into earlier features. Include regression tests for every look-ahead defect.
- UI tests run with `QT_QPA_PLATFORM=offscreen`; worker tests verify cancellation,
  progress, and delivery back to the GUI thread.
- Statistical tests should assert invariants or broad tolerances, never a lucky exact
  random sequence unless a seeded source is explicitly under test.

## Instructions for future coding agents

1. Read this file, `README.md`, the relevant feature package, and existing tests first.
2. Inspect files before editing. Preserve unrelated user changes and avoid broad rewrites.
3. Work in the roadmap phase requested; do not fake later features with placeholder
   outputs. A descriptive inactive page is acceptable only while its phase is pending.
4. Keep additions small and typed. Place calculations outside UI and ORM entities.
5. Add or update tests with production code. Run the full suite and fix failures.
6. When changing schema or architecture, update this document in the same change.
7. State assumptions in code/docstrings when official source data is ambiguous.
8. Never add predictive or odds-improvement claims to copy, comments, or reports.
9. Treat future-date leakage and mutable used strategies as correctness defects.
10. Before completing UI work, verify keyboard navigation, visible focus, minimum text
    contrast, readable resizing, status feedback, and responsive background work.

## Phase roadmap

- Phase 1: structure, configuration, database schema/bootstrap, PySide6 shell, tests.
- Phase 2: validated historical draw import, storage services, history UI (complete).
- Phase 3: point-in-time analytics and characteristic distributions (complete).
- Phase 4: explainable dynamic weighted-random generation (complete).
- Phase 5: Strategy Lab, cloning, version locking, parameter validation (complete).
- Phase 6: responsive chronological backtesting and comparisons (complete).
- Phase 7: Matplotlib analytics charts and visual polish (complete).
- Phase 8: optimization, expanded tests, and Windows PyInstaller packaging.

## Today's Lotto schedule

`schedule.py` is the single source of draw-day and time rules. It derives game names and number ranges from `domain.py`, evaluates dates in `Asia/Manila`, and accepts an optional local `lotto_schedule.json` override from the app data directory. The opening `TodayPage` refreshes on navigation and each minute, and routes quick picks to the existing Generator. A passed draw time is a schedule status only, not proof of published results. Regular schedule defaults follow PCSO's published timetable; temporary cancellations require a local override or a future verified schedule feed.
