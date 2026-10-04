# Lotto Lab

## Jonathan Weighted range analysis

Jonathan Weighted now has a range-enabled reference in the **same strategy family**,
normally **Jonathan Weighted v2**. If v2 already exists, startup uses the next free
version number. **Jonathan Weighted v1 remains unchanged** for comparison, and no
saved strategy configuration or draw is overwritten.

Range Analysis uses `1-9`, `10-19`, `20-29`, `30-39`, `40-49`, and `50+`, clipped
to the game maximum. The existing bucket factor retains its original `1-10` and
`11-19` boundaries. The two factors are deliberately distinct.

To try the feature:

1. Open **Analytics**, choose a game and historical draw-count window, then
   **Refresh analysis → Range Analysis**. Inspect observed presence, uniform
   expected presence, percentage-point deviation, and mean selections per range.
   **Patterns** offers most/least frequent observed patterns and all valid patterns,
   including unseen ones. **40+ / 50+** shows count distributions, at-least-one/two
   frequencies and averages. **Range chart** compares observed and expected means.
2. Open **Strategy Lab** and select Jonathan Weighted v2 (or the newer reference
   with **Enable Range Weighting** checked). **Clone to new version** to edit.
   Defaults are **20% Range Weight Strength**, range weighting enabled, and High
   Number Balance enabled for 6/55 and 6/58 only. Save parameters. Strength applies
   to both structural factors; switch both off for the original weighting behavior.
3. Open **Generator**, select the saved version, game, and historical window, then
   generate tickets. **Show weight explanation** includes each selection's range
   and high-number structural factors. Using a version locks it; clone to edit again.
4. In **Backtesting**, check **Pure Random v1**, **Jonathan Weighted v1**, and the
   range-enabled Jonathan version. Choose dates, tickets, seed and window, then run.
   Compare 0–6 match counts, mean and variance. **Generated patterns** shows counts
   and shares for each strategy; the status shows distinct-pattern counts. Saved
   runs reload these distributions, including explicitly marked partial runs.

The new factors describe combination structure, not individual high-number
likelihood. Exact uniform expectations account for range sizes. A bounded,
smoothed observed-versus-expected preference is evaluated over possible random
completions after each candidate; its after/before ratio multiplies the existing
Jonathan factors. At the default strength each terminal structural preference
lies within 0.9–1.1 (closer to neutral with limited history). All valid patterns,
including unseen patterns, remain possible even at 100% strength. No target
pattern is mandatory, and sampling remains random without replacement.

All range training uses `AnalyticsService.snapshot()` with the target's strict
date cutoff and configured per-game draw-count window. Neither the target draw
nor future draws enter the structural model. Range factors are neutral without
history. Historical deviations do not increase the mathematical chance of winning.

Startup adds `backtest_range_pattern` without altering existing tables. Older
runs remain readable but cannot retroactively show patterns that were not recorded.
Implementation and validation details: [range analysis notes](docs/range-analysis.md).



Lotto Lab is a local desktop application for studying PCSO lotto draw history and

experimenting with transparent weighted-random ticket generation. It is **not a

lottery predictor**. Draws are treated as independent random events, and historical

patterns do not guarantee or increase the mathematical probability of winning.



## Current status: Phases 1-7



This repository currently provides:



- the complete package structure for the planned domain modules;

- application settings and local data-path handling;

- a normalized SQLAlchemy/SQLite schema;

- database bootstrap and transaction helpers;

- a professional PySide6 shell with all primary navigation destinations;

- validated CSV import and duplicate-safe historical storage;

- automatic background synchronization of 50 recent results per supported game;

- point-in-time frequency, cross-game, sequence, group, and parity analytics;

- six built-in, versioned strategies;

- pure and dynamically weighted random generation without replacement;

- locally persisted ticket weights and explanations; and

- unit, integration, and UI smoke tests.



Strategy Lab, background backtesting, and Matplotlib analytics charts are active.

Phase 8 (optimization and Windows packaging) remains pending.



## Strategy Lab



Select a strategy version and choose **Clone to new version**. Adjust the enabled

factors and numeric parameters, then **Save parameters**. Built-ins are read-only

references, including Pure Random v1. Drafts become permanently locked before

generation or backtesting; clone again to change a used configuration.



## Backtesting



Select the game, inclusive target-date interval, historical draw-count window,

tickets per target and strategy, seed, and strategy versions. Pure Random v1 is

selected by default as the control. Choose **Run backtest**. Work runs in the

background; **Cancel run** retains explicitly marked partial aggregates. Partial

runs can have unequal strategy workloads and must not be treated as full comparisons.



Each target uses only earlier draws, including cross-game history. Strategies use

separate equal-seeded random streams; repeatability requires the same stored history,

parameters, settings, and software version. Additional imports can change reruns.

Saved runs retain date bounds, seed, window, exact locked strategy versions, timestamps,

status, match counts (0?6), mean matches, and population variance. The saved-run

selector reloads results. The comparison chart shows observed percentages, not

winning probabilities; no inferential confidence interval is asserted.



## Analytics charts



Choose **Refresh analysis**, then select number frequency, cross-game presence,

consecutive runs, maximum group concentration, or odd/even distribution. Computation

runs in the background. **Data table** exposes equivalent values. The Matplotlib

toolbar supports zoom, pan, and saving charts locally. Empty histories are labeled.

The desktop layout supports the minimum 900 ? 600 window with scrolling forms.



Database upgrades are additive: startup creates the new `backtest_settings` table

without dropping or rewriting existing tables. Older runs without settings can still

be inspected. If the process is forcibly stopped, a run may remain marked `running`;

it is not a completed comparison.



## Setup (Windows PowerShell)



Python 3.12 or newer is required.



```powershell

py -3 -m venv .venv

.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip

python -m pip install -e ".[dev]"

```



Run the application:



```powershell

python -m lotto_lab

```



Run tests:



```powershell

pytest

```



By default, the database is stored under the operating system's per-user local

application-data directory. Set `LOTTO_LAB_DATA_DIR` to use another directory.



## Generate tickets



1. Open Lotto Lab and select **Generator**.

2. Select a game and strategy. Use **Pure Random v1** for the statistical control.

3. Choose the historical window and number of tickets.

4. Select **Generate tickets**.

5. Expand a ticket's weight explanation to inspect every selected number.



Weighted strategies work without imported history, but historical factors remain

neutral until data exists. A score of 50 is used as the neutral no-history pattern

score. Generated tickets and their factor trails are saved in the local database.



## Import historical draws



### Automatic official-results update



Each time Lotto Lab opens, it checks the public PCSO LottoMatik results service in a

background thread and requests the 50 most recent draws for each supported game.

Validated new draws are inserted; existing game/date records are preserved. Open

**Draw History** to see synchronization status or select **Check official results**

to refresh manually.



The source is `https://lottomatik.pcso.gov.ph/api/backend/get-game-history`. If the

computer is offline or a feed is unavailable, startup continues normally and all

existing local history is retained. The upstream service can change independently,

so the app treats every response as untrusted input and validates it before storage.



### CSV import



Open **Draw History**, choose **Import CSV**, and select a UTF-8 CSV with this header:



```csv

game,date,n1,n2,n3,n4,n5,n6

6/42,2026-01-01,1,7,12,19,31,42

Mega Lotto 6/45,2026-01-02,2,8,14,23,34,45

```



`game` accepts a game code (`6/42`, `6/45`, `6/49`, `6/55`, `6/58`) or its full

display name. ISO dates (`YYYY-MM-DD`) are recommended; `MM/DD/YYYY` and

`DD/MM/YYYY` are also accepted in that parsing order. Invalid rows are reported and

skipped. Existing game/date records are not overwritten.



Verify the source and accuracy of manually imported data before drawing conclusions

from it.



## Roadmap



1. Foundation and desktop shell (complete)

2. Historical draw storage and import (complete)

3. Analytics engine (complete)

4. Weighted-random generator (complete)

5. Strategy Lab (complete)

6. Look-ahead-safe backtesting (complete)

7. Charts and UI polish (complete)

8. Optimization, testing, and PyInstaller packaging



## Table paging

Draw History, Analytics data, and Backtesting results display 25 rows per page by
default. Use **Previous**, **Next**, or the **Page** field to navigate; **Rows** offers
10, 25, 50, or 100 rows per page. The row range shows your position in the full result.
Changing the page size, history game filter, or displayed results returns to page 1.
Draw History fetches bounded pages from SQLite and includes records beyond the former
500-row display limit. Paging data tables does not change chart calculations.

## Today's Lotto

The opening page lists scheduled 6-of-N draws for the current date in `Asia/Manila`, with the next upcoming draw and a **Pick Numbers** shortcut into the existing Generator. Draw time passing changes the schedule status; it does not confirm that official results are available. **View Results** opens locally stored Draw History.

The regular schedule follows [PCSO's published draw schedule](https://www.pcso.gov.ph/pcsofiles/transparency/02/Annual%20Report%202021%282%29.pdf): 6/42 Tuesday/Thursday/Saturday; 6/45 Monday/Wednesday/Friday; 6/49 Tuesday/Thursday/Sunday; 6/55 Monday/Wednesday/Saturday; 6/58 Tuesday/Friday/Sunday, all at 9 PM. Special non-draw days and temporary changes may override this regular schedule; verify the current PCSO announcement.

For local schedule changes, create `lotto_schedule.json` in the app data directory (`LOTTO_LAB_DATA_DIR` if set). It contains a `games` array; each entry has `id` (for example `6/42`), `drawDays` (Monday=0 through Sunday=6), `drawTime` (`HH:MM`), and optional `active`, `description`, and `sourceUrl`. The file replaces the default schedule on startup. Example: `{"games":[{"id":"6/42","drawDays":[1,3,5],"drawTime":"21:00","active":true}]}`. This local desktop app has no HTTP backend or admin account system.
