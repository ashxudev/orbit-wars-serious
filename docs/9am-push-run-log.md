# 9am Push Run Log

## Current Baseline

- Active workspace: `/Users/user/dev/hackathons/orbit-wars-serious`.
- Current serious live submissions remain far below the historical fallback:
  - `53925932` / `orbit_wars_v2_submission.py`: public score `423.2`.
  - `53894832` / `orbit_wars_v1_submission.py`: public score `415.1`.
  - Historical fallback `53555669` / `claude-v3-wide-search-forecast`:
    public score `912.2`.
- Known fallback file:
  `/tmp/orbit_wars_claude_v3_wide_search_forecast_submission.py`.
  SHA256: `cd547e3f8f9d93be8c8e2441cb3cc9f52050222114279cbe1192dbcc99a33875`.

## Top-Player Benchmark

Existing read-only top-player analysis under `/tmp/ow-top-player-analysis`
reported current rank 1 as `Isaiah @ Tufa Labs`, public score `1834.0`.
The sampled wins reached production/rank advantage around turn `20` and
preserved production into the endgame with a broad target mix.

Working interpretation: the serious V2 agent is not merely missing isolated
actions. It is failing to create and retain the early production curve that top
agents reach by about turn `20`.

## Daytona Evidence

Previous-commit fragile-base guard probe:

- Commit: `3f8514b`.
- Root: `/tmp/ow-9am-v2-fragile-guard-probe/`.
- Plan: `/tmp/ow-9am-v2-fragile-guard-probe/daytona-shard-jobs-004-005.json`.
- Report: `/tmp/ow-9am-v2-fragile-guard-probe/daytona-real-report-004-005.json`.
- Result: completed, `10` full-500 historical matches, `0` execution errors.

Aggregate:

| Mode | Matches | Mean survived | Mean final rank | Mean final production | Collapse rate |
|---|---:|---:|---:|---:|---:|
| 2P | `6` | `103.67` | `2.0` | `0.0` | `1.0` |
| 4P | `4` | `173.0` | `2.0` | `1.25` | `0.75` |

Decision: not promotable, no live submission.

Current-commit trajectory-continuation probe:

- Commit: `e4b30a3`.
- Root: `/tmp/ow-9am-v2-continuation-probe/`.
- Plan: `/tmp/ow-9am-v2-continuation-probe/daytona-shard-jobs-004-005.json`.
- Shard results:
  - `/tmp/ow-9am-v2-continuation-probe/package/historical-gauntlet-shard-004/historical-gauntlet-shard-004.shard-result.json`.
  - `/tmp/ow-9am-v2-continuation-probe/package/historical-gauntlet-shard-005/historical-gauntlet-shard-005.shard-result.json`.
- Result: completed shard artifacts, `10` full-500 historical matches, `0`
  match execution errors.

Aggregate:

| Mode | Matches | Mean survived | Mean final rank | Mean final production | Collapse rate | Mean no-action with owned production |
|---|---:|---:|---:|---:|---:|---:|
| 2P | `6` | `106.5` | `2.0` | `0.0` | `1.0` | `57.5` |
| 4P | `4` | `245.25` | `2.0` | `1.25` | `0.75` | `236.75` |

Decision: not promotable, no live submission. The continuation bridge did not
close the trajectory gap; it still loses every 2P historical match and mostly
collapses in 4P.

## Current Source Change

Added a V2-only, 4P-scoped trajectory continuation bridge:

- trajectory facts for preservation targets and denial unlock;
- 4P preservation reinforce candidate surface;
- mission objective/target metadata;
- preservation-target scenario-loss accounting;
- scoring components for preserve-before-deny behavior;
- compact fixture updates and focused tests.

This is planner infrastructure, not a promotion-ready agent. The hardest 4P
fixtures still often report no useful action after preservation accounting,
which means the bridge exposes the gap more clearly but does not solve top-10
strength by itself.

## Validation So Far

```text
.venv/bin/python -m unittest tests.test_planner_v2_trajectory_continuation tests.test_planner_v2_scoring tests.test_planner_v2_scenario_eval tests.test_planner_v2_mission_generation
Ran 26 tests in 0.054s
OK

.venv/bin/python -m unittest tests.test_planner_v2_trajectory_continuation tests.test_planner_v2_trajectory_loss_fixtures tests.test_planner_v2_trajectory_divergence_fixtures tests.test_planner_v2_scenario_selection_fixtures tests.test_planner_v2_scenario_backed_loss_fixtures tests.test_v2_replay_leak_fixtures tests.test_runtime_planner_pipeline tests.test_planner_v2_scoring tests.test_planner_v2_scenario_eval tests.test_planner_v2_mission_generation tests.test_planner_v2_mission_surface_completeness
Ran 71 tests in 162.416s
OK
```

The current-commit Daytona probe completed after these checks and rejected V2
promotion; see the Daytona evidence section above.

Completed validation:

```text
.venv/bin/python -m unittest discover -s tests
Ran 1530 tests in 394.662s
OK

.venv/bin/python scripts/evaluation_gate.py
gate=PASS matches=2 win_rate=1 mean_rank=1 error_rate=0 parity=pass failures=0

.venv/bin/python scripts/submission_preflight.py --quiet-progress
submission_preflight=PASS total=3 passed=3 failed=0 failed_checks=none exit_code=0
preflight_check=submission_build status=PASS exit_code=0
preflight_check=submission_parity status=PASS mismatches=0 exit_code=0
preflight_check=regression_gate status=PASS failures=0 exit_code=0

git diff --check
PASS
```

## Submission Status

- Exploratory live submissions used in this push: `0`.
- Final submissions used in this push before fallback submit: `0`.
- Current serious V2 path is not promotable on evidence.
- Current serious bundle candidate:
  `/tmp/orbit_wars_serious_e4b30a3_submission.py`,
  SHA256 `76fc642e337797a7415c565bf23878e081a02f22a9a0d57a4dfc071199a3f474`.
- Next-best fallback candidate remains
  `/tmp/orbit_wars_claude_v3_wide_search_forecast_submission.py`.

Final submission decision:

- Submitted fallback file:
  `/tmp/orbit_wars_claude_v3_wide_search_forecast_submission.py`.
- SHA256:
  `cd547e3f8f9d93be8c8e2441cb3cc9f52050222114279cbe1192dbcc99a33875`.
- Verification:
  - byte-identical to
    `historical_opponents/agents/claude_v3_wide_search_forecast.py`;
  - `py_compile` passed.
- Kaggle ref: `53988022`.
- Submitted at: `2026-06-24 03:57 AEST`.
- Submission message:
  `final fallback claude-v3-wide-search-forecast; serious-v2 423.2 and 0/10 Daytona, fallback historical public 912.2, leaving one reserve`.
- Status immediately after submit: `SubmissionStatus.PENDING`.
- Exploratory live submissions used in this push: `0`.
- Final submissions used in this push: `1`.
- Final submissions held in reserve: `1`.

First live-result check:

- Checked at: `2026-06-24 04:16 AEST`.
- Kaggle status: `SubmissionStatus.COMPLETE`.
- Public score shown: `594.3`.
- Public episodes available/analyzed: `3`.
- Analysis root, kept out of git:
  `/tmp/orbit-wars-final-53988022-live-analysis/`.
- Live sample record: `1-2`.
- Mean final rank: `1.67`.
- Mean final production: `25.3`.

Episode summary:

| Episode | Mode | Result | Final rank | Final production | Peak production | First zero production after peak |
|---:|---:|---:|---:|---:|---:|---:|
| `81519637` | 4P | loss | `2` | `0.0` | `17.0` | `60` |
| `81519221` | 2P | loss | `2` | `0.0` | `32.0` | `92` |
| `81518964` | 4P | win | `1` | `76.0` | `76.0` | n/a |

Interpretation: the fallback remains the correct final choice versus serious V2
because it is already outperforming the current serious submissions, but the
first three live games are not enough to infer final leaderboard strength. Keep
the remaining final submission in reserve and continue passive monitoring.

Final live-result monitor check:

- Checked at: `2026-06-24 05:00 AEST`.
- Kaggle status: `SubmissionStatus.COMPLETE`.
- Public score shown: `720.0`.
- Public episodes available/analyzed: `12`.
- Analysis root, kept out of git:
  `/tmp/orbit-wars-final-53988022-live-analysis/`.
- Live sample record: `6-6`.
- 2P record: `5-4`.
- 4P record: `1-2`.
- Mean final rank: `1.50`.
- Mean final production: `40.8`.
- Mean final total ships: `2058.8`.

Episode summary:

| Episode | Mode | Result | Final rank | Final production | Peak production | First zero production after peak |
|---:|---:|---:|---:|---:|---:|---:|
| `81522954` | 2P | win | `1` | `64.0` | `64.0` | n/a |
| `81522559` | 2P | loss | `2` | `0.0` | `26.0` | `92` |
| `81522147` | 2P | win | `1` | `94.0` | `94.0` | n/a |
| `81521761` | 2P | loss | `2` | `0.0` | `38.0` | `131` |
| `81521396` | 2P | loss | `2` | `0.0` | `37.0` | `118` |
| `81520939` | 2P | win | `1` | `88.0` | `88.0` | n/a |
| `81520656` | 4P | loss | `2` | `0.0` | `27.0` | `210` |
| `81520269` | 2P | win | `1` | `104.0` | `104.0` | n/a |
| `81519902` | 2P | win | `1` | `64.0` | `64.0` | n/a |
| `81519637` | 4P | loss | `2` | `0.0` | `17.0` | `60` |
| `81519221` | 2P | loss | `2` | `0.0` | `32.0` | `92` |
| `81518964` | 4P | win | `1` | `76.0` | `76.0` | n/a |

Interpretation: the final fallback submission is materially better than the
current serious V1/V2 live submissions and remains the correct use of the final
slot, but it is not near the top-10 target. The reserve submission remains
unused. Further work should continue from the opening-trajectory rewrite
diagnosis rather than trying to patch V2 into the leaderboard with another
late-cycle heuristic.

## Post-Submit Reserve Candidate Follow-Up

Goal: continue improving toward a reserve candidate without making another live
submission. No Kaggle submission was made in this follow-up.

The final fallback live losses and top-player replay sample both point to the
same gap: the fallback is not materially behind by turn `10` or `20` in 2P, but
it fails to preserve or convert the turn `40` position. The loss pattern is
source-drain plus short-hold collapse:

- 2P losses often peak around `26`-`38` production, then lose all production
  between turns `92` and `131`.
- 4P collapse losses show the same pattern earlier or under third-party
  pressure, including short-held productive planets that flip back within a few
  turns.
- Direct replay diagnostics found many launches from sources that were lost
  within `20` turns after launch.

Throwaway local full-500 sweep root:
`/tmp/ow-fallback-reserve-sweep/`.

Matched pressure scenarios:

- `historical-gauntlet-2p-500-seat-1-vs-claude-v31-race-awareness`
- `historical-gauntlet-2p-500-seat-1-vs-claude-v9-hold-aware-capture`
- `historical-gauntlet-2p-500-seat-0-vs-ow2-current-main`
- `historical-gauntlet-4p-500-top-score-seat-3`
- `historical-gauntlet-4p-500-mixed-style-seat-2`
- `historical-gauntlet-4p-500-ow2-smoke-reference-seat-0`

Local sweep summary:

| Variant | Wins | Mean rank | Mean survived | Read |
|---|---:|---:|---:|---|
| fallback base | `0/6` | `2.00` | `182.5` | baseline collapse |
| response discount `0.85` | `0/6` | `2.00` | `204.3` | survival up, no wins |
| strict hold | `0/6` | `2.00` | `196.5` | modest survival up, no wins |
| strict hold + response discount `0.85` | `0/6` | `2.00` | `204.0` | no clear gain over response discount |
| enemy margin `8` | `1/6` | `1.83` | `180.6` | one win, broad regression risk |
| source/short-hold guard | `1/6` | `1.83` | `203.0` | one win, mixed but conceptually aligned |
| source/short-hold guard + response discount `0.85` | `1/6` | `1.83` | `184.8` | no improvement over source guard |

Decision: source/short-hold guarding is the most defensible reserve-candidate
surface, but the local evidence is not submission-worthy. The tracked
`agents.fallback_source_guard` candidate is isolated from default runtime
behavior and exists only to support broader A/B evaluation. If evaluated next,
use `scripts/prepare_fallback_source_guard_ab_daytona_package.py` to run a
matched Daytona A/B against the unmodified fallback baseline. Keep the final
submission reserve unused unless Daytona and live-game evidence improve
materially.

Follow-up live submission:

- User explicitly requested another live Kaggle submission soon to get results
  over the next hour.
- Submitted reserve candidate:
  `/tmp/orbit_wars_fallback_source_guard_submission.py`.
- SHA256:
  `bf8e277a4386409011533ee22dcb34735a0d066c6e4b11b423e081d00e3ae319`.
- Kaggle ref: `53992217`.
- Submitted at: `2026-06-24 08:13 AEST`.
- Submission message:
  `reserve fallback-source-guard; targets source-drain and short-hold live-loss pattern; commit 6e1b3ba; prior fallback 53988022 score 720 sample 6-6`.
- Status immediately after submit: `SubmissionStatus.PENDING`.
- Exploratory/final reserve status: the previously held final reserve has now
  been used. No further Kaggle submission should be made unless explicitly
  instructed by the user.

Daytona A/B evidence for the submitted reserve candidate:

- Root: `/tmp/ow-fallback-source-guard-ab-daytona/`.
- Initial 4-job parallel Daytona plan exceeded the organization memory limit,
  so the same four jobs were run sequentially as one-job plans.
- Result: all `4` one-job Daytona runs completed, covering `12` full-500
  matched historical pressure matches.
- Summary JSON:
  `/tmp/ow-fallback-source-guard-ab-daytona/fallback-source-guard-ab-summary.json`.

| Cell | Matches | Wins | Mean rank | Mean survived | Mean final production | Collapses |
|---|---:|---:|---:|---:|---:|---:|
| fallback base | `6` | `0` | `2.0` | `188.0` | `0.0` | `6` |
| source-guard | `6` | `1` | `1.8333` | `193.1667` | `14.0` | `5` |

Interpretation: source-guard is only weakly better than fallback in the matched
Daytona A/B. It is not proven top-10 quality, but it is directionally aligned
with the observed live-loss source-drain/short-hold failure class and is now
live for empirical feedback.

First source-guard live check:

- Checked at: `2026-06-24 08:24 AEST`.
- Kaggle status: `SubmissionStatus.COMPLETE`.
- Public score shown: `600.0`.
- Public episodes available/analyzed: `1`.
- Analysis root, kept out of git:
  `/tmp/orbit-wars-source-guard-53992217-live-analysis-test/`.
- Episode `81538434`: 2P win against `Runlin zhang`, final production `48.0`,
  final total `2080.0`, peak production `48.0`.
- Source-loss-after-launch diagnostic: `within_5=0`, `within_10=0`,
  `within_20=0`.

Follow-up analyzer fix:

- `scripts/analyze_latest_submission_replays.py` now accepts submission-specific
  metadata for non-default submissions.
- `scripts/analyze_current_top_player_replays.py` can return compact action rows
  when requested, allowing latest-submission reports to compute
  source-loss-after-launch diagnostics directly from replay actions.

Already-doomed source-guard follow-up:

- No live Kaggle submission was made.
- Investigated whether `agents.fallback_source_guard` only catches launches
  that newly doom a source. The current guard compared post-launch source loss
  against baseline loss, so sources already forecast to fall inside the guard
  window were treated as if their ships were free unless they fell in the
  existing very-short evacuation window.
- Added a deterministic `already_doomed_source` branch in the isolated fallback
  source-guard candidate. Non-funnel launches from sources already forecast to
  fall inside `SOURCE_LOSS_GUARD_TICKS` now receive an additional penalty, with
  high-production sources rejected only inside the tighter 12-tick danger
  window.
- Added an inline synthetic regression fixture in
  `tests/test_fallback_source_guard_candidate.py`: one productive source is
  forecast to fall to an incoming fleet at tick `9`, and the previous candidate
  would attack with `50` ships. The patched candidate returns no launch.
- Matched local pressure check:
  `/tmp/ow-main-impact-sweep/tracked_source_guard_doomed_penalty-report.json`.
  The tracked patched source-guard candidate went `2/6` on the six historical
  pressure scenarios versus `1/6` for the prior source-guard candidate, with no
  errors. The added win was
  `historical-gauntlet-2p-500-seat-0-vs-ow2-current-main` (`rank=1`,
  final production `47`), while the existing `claude-v9-hold-aware-capture`
  2P win remained stable (`rank=1`, final production `84`).
- Live source-guard submission `53992217` later exposed three public wins and a
  public score above the fallback (`804.1` at the latest check here versus
  fallback `718.1`). No new live submission was made for this patch.
- Focused validation command:
  `python3 -m unittest tests.test_fallback_source_guard_candidate -v`.

Mode-split reserve candidate follow-up:

- No live Kaggle submission was made.
- Local variant search showed that a response-margin guard was strong in 4P but
  bad in 2P. The tracked `agents.fallback_mode_split` candidate therefore uses
  the already-doomed source-guard behavior in 2P and response-margin behavior
  only when the observation appears to be 4P.
- Tracked local pressure check:
  `/tmp/ow-mode-split-tracked/fallback_mode_split-report.json`.
  The mode-split candidate went `4/6`, mean rank `1.333`, mean score `0.333`,
  with no errors, versus `2/6` for the patched source-guard candidate and `1/6`
  for the prior source-guard baseline on the same pressure scenarios.
- Winning pressure scenarios:
  `2p seat-1 vs claude-v9` (`rank=1`, final production `84`),
  `2p seat-0 vs ow2-current-main` (`rank=1`, final production `47`),
  `4p top-score seat-3` (`rank=1`, final production `76`), and
  `4p ow2-smoke-reference seat-0` (`rank=1`, final production `68`).
- Remaining pressure losses:
  `2p seat-1 vs claude-v31` and `4p mixed-style seat-2`, both still collapsing
  to zero production.
- Daytona validation for the pushed mode-split candidate used commit
  `f0e622a` and artifacts under `/tmp/ow-mode-split-daytona`.
  The first generated plans had a mistyped full SHA and failed with a GitHub
  `404`; regenerated plans used the exact pushed SHA
  `f0e622a953f2815e8e045c5fe0e4f55587203862`.
- Completed Daytona mode-split shards:
  `job-0002-mode-split-ab-0002` (2P) and
  `job-0003-mode-split-ab-0003` (4P). Combined result:
  `4/6`, mean rank `1.333`, mean survived `190.667`, mean final production
  `45.833`, and `2` collapses.
- Daytona wins matched local evidence: `claude-v9` 2P, `ow2-current-main` 2P,
  `top-score` 4P, and `ow2-smoke-reference` 4P. Losses remained
  `claude-v31` 2P and `mixed-style` 4P.
- The older live source-guard submission `53992217` had fallen to public score
  `696.5` with `9` accessible public episodes by this check. Sample record was
  `4-5`; all `5/5` losses ended at zero production, reinforcing that source
  guard alone is not stable enough and that 4P retention/pressure behavior is
  the primary leak.
