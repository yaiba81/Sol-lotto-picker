# Range enhancement implementation

## Files

- `analytics/range_analyzer.py`: pure range partitioning, composition frequencies,
  exact multivariate hypergeometric pattern probabilities, range presence and
  40+/50+ hypergeometric count distributions.
- `analytics/engine.py`: attaches these statistics to the existing snapshot.
- `strategy/config.py`: backward-compatible typed fields and enhanced Jonathan
  reference configuration; legacy JSON enables neither new factor.
- `strategy/repository.py`: idempotently seeds the next free Jonathan version,
  preserving existing versions and cloning/locking rules.
- `strategy/range_weighting.py`: bounded structural preferences and cached
  uniform-completion expectations for partial range compositions.
- `generator/engine.py`: multiplies the two structural factors into the original
  five factors and retains them in existing ticket explanations and factor storage.
- `backtesting/service.py`, `backtesting/repository.py`, `persistence/models.py`:
  count and persist generated patterns alongside match aggregates, including
  cancelled/failed workloads. The new aggregate table is additive.
- `ui/range_analysis.py`, `ui/feature_pages.py`, `ui/charts.py`: paged analysis
  tables, observed/expected chart, game/window context and minimum-window layout.
- `ui/strategy_page.py`, `ui/backtest_page.py`: persisted parameter controls and
  generated-pattern results. Existing generation/backtest window controls apply.
- `tests/analytics/test_ranges.py`, `tests/generator/test_range_weighting.py`,
  `tests/test_range_backtesting.py`, `tests/ui/test_range_analysis.py`: regression
  coverage of math, generation, versioning, cutoff safety, persistence and UI.
- `AGENTS.md`, `README.md`, this document: vocabulary, architecture and usage.

All source paths above are relative to `src/lotto_lab/` except tests and documentation.

## Calculation

For a range of K values in a game with N values, the expected selections per draw
are `6K/N`. The probability of k selections is
`C(K,k) C(N-K,6-k) / C(N,6)`. Range presence is one minus the probability of zero.
For a complete pattern p with range sizes s, its uniform probability is
`product(C(s_i,p_i)) / C(N,6)`. These expectations are mathematical reference
distributions, independent of the historical observations.

For each full pattern, let O be its historical count and E its uniform expected
count in the same sample. Define:

```
deviation = (O - E) / (O + E)
shrink = observed_draws / (observed_draws + structural_prior_draws)
preference = 1 + range_strength * structural_max_deviation * shrink * deviation
```

Defaults: strength 0.20, maximum deviation 0.50, prior 20 draws. Preferences are
strictly positive, including when O=0. No history produces a neutral preference.
The high-number factor applies the same calculation to the **joint** distribution
of `(count >=40, count >=50)`, respecting the nesting of these ranges. It is active
only for 6/55 and 6/58. Individual high numbers do not receive a fixed bonus.

For a partial ticket, the potential is the expected terminal preference over
uniform completions without replacement. A candidate contributes
`potential(after) / potential(before)`. Recompute after each selection and multiply
with the cross-game, sequence, legacy bucket, odd/even and optional frequency factors.
The random sampler still considers every unselected in-range number.

For a single structural factor with other factors neutral, these ratios telescope:
the resulting combination distribution is exactly the uniform distribution tilted
by its terminal preference and normalized. With both structural factors and the
original Jonathan factors, normalization happens at each selection step; no exact
match to the historical pattern distribution is claimed. The two structural factors
overlap, so their shared strength and deviation cap keep the combined effect modest.

The implementation does not sample a mandatory target pattern. It integrates over
possible completions and samples actual numbers using the existing weighted sampler.
Rare and unseen full patterns retain positive probability at every allowed strength.

## Cutoff and storage

The existing service queries only draws strictly before each target date, with the
latest configured number of draws per game. The range analyzer sees only the
selected game's returned draws. The generator retains one model keyed by snapshot
identity and immutable config; a different snapshot replaces it. The only shared
cache contains uniform mathematical pattern probabilities, never historical data.

Strategy settings are stored in the existing version's JSON config. Backtest window
settings remain in `backtest_settings`; generated pattern counts are normalized rows
in `backtest_range_pattern`. No historical source rows or existing used strategies
are rewritten. Version seeding uses a transaction and chooses the family's maximum
version plus one. The enhanced reference is locked and editable only through cloning.

## Verification

Run `python -m pytest -q` from the project root. Tests include all five game ranges,
the supplied pattern example, exact expectations, high-number joint behavior,
positive support for every full pattern, exact sequential pattern probabilities,
seeded disabled-mode compatibility, generated diversity and valid tickets, strict
backtest cutoff/window checks, version collision handling, persisted complete and
partial pattern counts, empty-history UI, keyboard controls and minimum-size layout.

UI rendering uses the existing chart theme, with filled observed bars and hatched
expected bars so comparison does not rely on color alone. Tables expose the same
values. Analysis/generation/backtesting remain on existing QThread workers, and
Matplotlib rendering remains on the GUI thread.
