# Historical Champion Gauntlet

This runbook tracks the local historical-opponent registry for the Distributed
Historical Champion Gauntlet segment. Cycle 0 is inventory only: it does not
run local gauntlet matches, launch Daytona jobs, or copy historical agent code
into this repo.

## Registry

The source-controlled registry is:

```text
experiments/historical_champions/registry.json
```

Each entry records a stable opponent name, source repo, absolute source file
path, source kind, callable name, historical submission ref and public score
where known, intended modes, loadability status, and a skip reason when the
current harness cannot load the candidate.

Loadable entries are intended to become `python_file` opponents in later full
500-step gauntlet manifests. Skipped entries are retained as explicit inventory
so known historical candidates are not silently lost.

## Current Loadable Champion Pool

The strongest currently loadable historical opponents come from
`/Users/user/dev/hackathons/orbit-wars-claude`, including prior visible
800+ public-score submissions:

- `claude-v3-wide-search-forecast` (`53555669`, public score `912.2`).
- `claude-v28-mode-split-champion` (`53585590`, public score `872.4`).
- `claude-v37-race-fix-mode-split` (`53602635`, public score `870.4`).
- `claude-v14-hammer-discipline` (`53585594`, public score `859.1`).
- `claude-v8-leader-weighted-denial` (`53556108`, public score `851.1`).
- `claude-v9-hold-aware-capture` (`53556449`, public score `841.9`).
- `claude-v31-race-awareness` (`53602639`, public score `826.6`).
- `claude-v62-low-pickoff-bundled` (`53641340`, public score `824.4`).

The registry also includes loadable `orbit-wars-2` frozen agents that were used
by the earlier bounded legacy-opponent smoke benchmark.

## Skipped Historical Candidates

Some original `/Users/user/dev/hackathons/orbit-wars` exported submissions are
listed as skipped because they currently raise loader errors under the
`python_file` harness. They should not be forced into a gauntlet until loader
compatibility is addressed. Keeping them in the registry with skip reasons
makes the inventory explicit without weakening the harness.

## Validation

Cycle 0 validation is loadability only. It proves that every entry marked
`loadable` can be imported as a callable through the current evaluation harness;
it does not call the agent, run official matches, write reports, or create
Daytona plans.

```bash
.venv/bin/python -m unittest tests.test_historical_champion_registry
.venv/bin/python -m unittest tests.test_evaluation_agent_loading tests.test_evaluation_official_runner
git diff --check
```

## Cycle 4 Daytona Package Compatibility

Cycle 4 makes the recommended probe shard compatible with the existing
distributed evaluation shard/job package infrastructure. It remains
package-planning/materialization only: it does not run the shard, launch Daytona
jobs, upload files, download files, generate reports, create replays, or call
Kaggle.

The package adapter APIs are:

```python
from pathlib import Path
from ow_eval.historical_gauntlet_shards import (
    build_historical_champion_evaluation_shard_plan,
    write_historical_champion_probe_shard_package,
)

plan = build_historical_champion_evaluation_shard_plan(
    output_root=Path("/tmp/ow-historical-gauntlet-cycle4-package")
)
package = write_historical_champion_probe_shard_package(
    Path("/tmp/ow-historical-gauntlet-cycle4-package")
)
```

The adapter selects `historical-gauntlet-shard-000` by default. The converted
`EvaluationShardPlan` contains exactly the five scenarios assigned to that
historical shard, with original scenario labels, seeds, controlled seats,
opponent specs, and `episode_steps == "500"` preserved.

The package writer reuses existing shard job/package primitives and writes only
package specs:

- `manifest.json`: shard-local experiment manifest.
- `historical-gauntlet-shard-000.job.json`: local shard job spec.
- `shard-jobs.index.json`: deterministic package index.
- Planned future paths for `report.json` and `shard-result.json`.

Cycle 4 materialization smoke output should be under `/tmp`, for example:

```text
/tmp/ow-historical-gauntlet-cycle4-package/historical-gauntlet-shard-000/manifest.json
/tmp/ow-historical-gauntlet-cycle4-package/historical-gauntlet-shard-000/historical-gauntlet-shard-000.job.json
/tmp/ow-historical-gauntlet-cycle4-package/shard-jobs.index.json
```

Cycle 5 should use this package-ready `historical-gauntlet-shard-000` unit for
the first single-shard Daytona dry/probe path before any multi-shard pilot.

## Cycle 5 Single-Shard Daytona Probe Path

Cycle 5 proved that the package-ready recommended probe shard flows through the
local Daytona preparation, preflight, and dry-run executor paths. Real Daytona
execution was not run because readiness was blocked by explicit safety gates.

Generated files were written only under:

```text
/tmp/ow-historical-gauntlet-cycle5-shard-000/
```

Selected package:

- Shard id: `historical-gauntlet-shard-000`.
- Scenario count: `5`.
- Episode steps: `500`.
- Package manifest:
  `/tmp/ow-historical-gauntlet-cycle5-shard-000/historical-gauntlet-shard-000/manifest.json`.
- Job path:
  `/tmp/ow-historical-gauntlet-cycle5-shard-000/historical-gauntlet-shard-000/historical-gauntlet-shard-000.job.json`.
- Job index:
  `/tmp/ow-historical-gauntlet-cycle5-shard-000/shard-jobs.index.json`.

Selected scenario labels:

- `historical-gauntlet-2p-500-seat-0-vs-claude-v3-wide-search-forecast`.
- `historical-gauntlet-2p-500-seat-0-vs-claude-v14-hammer-discipline`.
- `historical-gauntlet-2p-500-seat-0-vs-claude-v31-race-awareness`.
- `historical-gauntlet-2p-500-seat-0-vs-ow2-current-main`.
- `historical-gauntlet-4p-500-top-score-seat-2`.

Daytona plan generation:

```bash
.venv/bin/python scripts/prepare_daytona_shard_jobs.py /tmp/ow-historical-gauntlet-cycle5-shard-000/shard-jobs.index.json --output-path /tmp/ow-historical-gauntlet-cycle5-shard-000/daytona-shard-jobs.json --working-dir /workspace/orbit-wars-serious --sandbox-name-prefix ow-historical-gauntlet-probe
```

Result:

```text
daytona_shard_job_plan=WRITTEN index_path=/tmp/ow-historical-gauntlet-cycle5-shard-000/shard-jobs.index.json output_path=/tmp/ow-historical-gauntlet-cycle5-shard-000/daytona-shard-jobs.json jobs=1 exit_code=0
```

Daytona preflight:

```bash
.venv/bin/python scripts/validate_daytona_shard_jobs.py /tmp/ow-historical-gauntlet-cycle5-shard-000/daytona-shard-jobs.json
```

Result:

```text
daytona_shard_job_plan_validation=PASS plan_path=/tmp/ow-historical-gauntlet-cycle5-shard-000/daytona-shard-jobs.json specs=1 missing_upload_paths=0 duplicate_sandbox_names=0 exit_code=0
```

Dry-run executor:

```bash
.venv/bin/python scripts/run_daytona_shard_jobs.py /tmp/ow-historical-gauntlet-cycle5-shard-000/daytona-shard-jobs.json --dry-run --json-output /tmp/ow-historical-gauntlet-cycle5-shard-000/daytona-dry-run-result.json
```

Result:

```text
daytona_shard_jobs_cli=COMPLETE plan_path=/tmp/ow-historical-gauntlet-cycle5-shard-000/daytona-shard-jobs.json dry_run=True jobs=1 exit_code=0
daytona_shard_execution=COMPLETE plan_path=/tmp/ow-historical-gauntlet-cycle5-shard-000/daytona-shard-jobs.json jobs=1 merged=False exit_code=0
```

Daytona plan inspection:

- Specs: `1`.
- Job id: `job-0000`.
- Shard id: `historical-gauntlet-shard-000`.
- Sandbox name:
  `ow-historical-gauntlet-probe-0000-historical-gauntlet-shard-000`.
- Manifest scenario count: `5`.
- Manifest episode steps: `500`.

Real Daytona readiness:

```text
daytona_real_execution_readiness=BLOCKED allow_real_daytona=False missing_env_vars=1 exit_code=2
passed False
missing_env_vars DAYTONA_API_KEY
error_text real Daytona execution is not explicitly allowed; missing env vars: DAYTONA_API_KEY
```

Because readiness was blocked, no
`scripts/run_daytona_real_shard_jobs.py --allow-real-daytona` command was run.
No real Daytona sandbox was created, uploaded to, executed, downloaded from, or
closed in this cycle.

Focused regression checks:

```bash
.venv/bin/python -m unittest tests.test_historical_champion_gauntlet_shards tests.test_historical_champion_gauntlet_packages
.venv/bin/python -m unittest tests.test_evaluation_daytona_plan_cli tests.test_evaluation_daytona_preflight tests.test_evaluation_daytona_executor_cli tests.test_evaluation_daytona_real_cli tests.test_evaluation_daytona_client_report
git diff --check
```

## Cycle 6 Guarded Real Daytona Single-Shard Probe

Cycle 6 rebuilt the recommended real-probe package for exactly one shard,
`historical-gauntlet-shard-000`, and revalidated the local Daytona preparation
path. Real Daytona execution was not run because the explicit readiness gate was
still blocked.

Generated files were written only under:

```text
/tmp/ow-historical-gauntlet-cycle6-real-shard-000/
```

Selected package:

- Shard id: `historical-gauntlet-shard-000`.
- Scenario count: `5`.
- Episode steps: `500`.
- Package manifest:
  `/tmp/ow-historical-gauntlet-cycle6-real-shard-000/historical-gauntlet-shard-000/manifest.json`.
- Job path:
  `/tmp/ow-historical-gauntlet-cycle6-real-shard-000/historical-gauntlet-shard-000/historical-gauntlet-shard-000.job.json`.
- Job index:
  `/tmp/ow-historical-gauntlet-cycle6-real-shard-000/shard-jobs.index.json`.

Selected scenario labels:

- `historical-gauntlet-2p-500-seat-0-vs-claude-v3-wide-search-forecast`.
- `historical-gauntlet-2p-500-seat-0-vs-claude-v14-hammer-discipline`.
- `historical-gauntlet-2p-500-seat-0-vs-claude-v31-race-awareness`.
- `historical-gauntlet-2p-500-seat-0-vs-ow2-current-main`.
- `historical-gauntlet-4p-500-top-score-seat-2`.

Daytona plan generation:

```bash
.venv/bin/python scripts/prepare_daytona_shard_jobs.py /tmp/ow-historical-gauntlet-cycle6-real-shard-000/shard-jobs.index.json --output-path /tmp/ow-historical-gauntlet-cycle6-real-shard-000/daytona-shard-jobs.json --working-dir /workspace/orbit-wars-serious --sandbox-name-prefix ow-historical-gauntlet-real-probe
```

Result:

```text
daytona_shard_job_plan=WRITTEN index_path=/tmp/ow-historical-gauntlet-cycle6-real-shard-000/shard-jobs.index.json output_path=/tmp/ow-historical-gauntlet-cycle6-real-shard-000/daytona-shard-jobs.json jobs=1 exit_code=0
```

Daytona preflight:

```bash
.venv/bin/python scripts/validate_daytona_shard_jobs.py /tmp/ow-historical-gauntlet-cycle6-real-shard-000/daytona-shard-jobs.json
```

Result:

```text
daytona_shard_job_plan_validation=PASS plan_path=/tmp/ow-historical-gauntlet-cycle6-real-shard-000/daytona-shard-jobs.json specs=1 missing_upload_paths=0 duplicate_sandbox_names=0 exit_code=0
```

Dry-run executor:

```bash
.venv/bin/python scripts/run_daytona_shard_jobs.py /tmp/ow-historical-gauntlet-cycle6-real-shard-000/daytona-shard-jobs.json --dry-run --json-output /tmp/ow-historical-gauntlet-cycle6-real-shard-000/daytona-dry-run-result.json
```

Result:

```text
daytona_shard_jobs_cli=COMPLETE plan_path=/tmp/ow-historical-gauntlet-cycle6-real-shard-000/daytona-shard-jobs.json dry_run=True jobs=1 exit_code=0
daytona_shard_execution=COMPLETE plan_path=/tmp/ow-historical-gauntlet-cycle6-real-shard-000/daytona-shard-jobs.json jobs=1 merged=False exit_code=0
```

Daytona plan inspection:

- Specs: `1`.
- Job id: `job-0000`.
- Shard id: `historical-gauntlet-shard-000`.
- Sandbox name:
  `ow-historical-gauntlet-real-probe-0000-historical-gauntlet-shard-000`.
- Manifest scenario count: `5`.
- Manifest episode steps: `500`.

Real Daytona readiness:

```text
daytona_real_execution_readiness=BLOCKED allow_real_daytona=False missing_env_vars=1 exit_code=2
passed False
missing_env_vars DAYTONA_API_KEY
error_text real Daytona execution is not explicitly allowed; missing env vars: DAYTONA_API_KEY
```

Because readiness was blocked, no
`scripts/run_daytona_real_shard_jobs.py --allow-real-daytona` command was run.
No real Daytona sandbox was created, uploaded to, executed, downloaded from, or
closed in this cycle. This is blocked by environment/configuration, not by the
package, Daytona plan, validation, or dry-run path.

Focused regression checks:

```bash
.venv/bin/python -m unittest tests.test_historical_champion_gauntlet_shards tests.test_historical_champion_gauntlet_packages
.venv/bin/python -m unittest tests.test_evaluation_daytona_plan_cli tests.test_evaluation_daytona_preflight tests.test_evaluation_daytona_executor_cli tests.test_evaluation_daytona_real_cli tests.test_evaluation_daytona_client_report
git diff --check
```

## Cycle 7 Daytona Setup Consolidation

Cycle 7 replaces the prior blocked real-Daytona state with a working guarded
single-shard execution path. It consolidates the setup/fix work needed before a
future full distributed historical champion gauntlet:

- `.env.example` documents the local Daytona guard and required non-committed
  config.
- `.gitignore` excludes local `.env` secrets.
- The Daytona readiness config can load `.env` values without overriding shell
  values.
- Runtime snapshot preparation is available through
  `scripts/prepare_daytona_runtime_snapshot.py`.
- Real setup smoke diagnostics are available through
  `scripts/run_daytona_real_smoke.py`.
- Historical `python_file` opponents are copied into the generated package and
  uploaded as package-local files instead of relying on host-local absolute
  paths inside Daytona.
- Long real Daytona worker commands use process sessions; the earlier long
  synchronous command path failed with a Daytona proxy disconnect.

Real setup evidence from `/tmp` artifacts:

- Daytona auth/readiness worked with the local guarded config.
- The configured runtime snapshot was usable.
- The guarded real smoke diagnostic passed.
- The first real single-shard probe for `historical-gauntlet-shard-000`
  completed through Daytona.
- The shard result reported `5` completed full-500 matches, `0` execution
  errors, and mean final rank `2.0`.

The result is infrastructure success, not competitive success. The five losses
against historical champions remain expected gauntlet signal. No remaining
gauntlet shards were run in this cycle, and no Kaggle command or live submission
was used.

Generated package files, Daytona plans, smoke reports, client reports, shard
results, match reports, scoreboards, logs, replays, and temporary files are
`/tmp` artifacts and must not be committed.

Future cycles should build full 500-step local/Daytona gauntlet manifests from
this registry, keeping generated match reports, logs, scoreboards, replays, and
temporary artifacts out of source control.

## Cycle 1 Full-Horizon Scenario Matrix

Cycle 1 adds source-controlled full-horizon manifest definitions only. These
manifests are Daytona-ready inputs for later sharding work, but this cycle does
not run any official-environment matches, Daytona packages, Daytona jobs, or
Kaggle commands.

The committed manifests are:

```text
experiments/manifests/historical-champion-gauntlet-2p-500.json
experiments/manifests/historical-champion-gauntlet-4p-500.json
```

Both manifests use the current modular runtime agent as `candidate_agent` and
schedule only registry entries with `loadability_status == "loadable"`. Every
scenario has `metadata.episode_steps` set to `"500"` so future local and
Daytona runners execute full-horizon gauntlet games intentionally.

The 2P matrix includes every loadable historical champion opponent across both
candidate seats, producing 22 deterministic scenarios. The 4P matrix includes
8 deterministic pool scenarios:

- Top-score champion pools across candidate seats 0, 1, 2, and 3.
- Mixed champion style pools across candidate seats 0 and 2.
- `orbit-wars-2` smoke-reference pools across candidate seats 0 and 3.

Skipped registry entries remain documented in the registry but are not included
in runnable manifests.

Cycle 1 validation is manifest parsing and loadability only:

```bash
.venv/bin/python -m unittest tests.test_historical_champion_registry tests.test_historical_champion_gauntlet_manifests
.venv/bin/python -m unittest tests.test_evaluation_manifest_fixtures tests.test_evaluation_agent_loading tests.test_evaluation_official_runner
git diff --check
```

## Cycle 2 Local Full-500 Micro-Probe

Cycle 2 ran a minimal local official-environment probe to verify that the
committed full-horizon gauntlet matrix is executable before Daytona sharding.
It did not run the full gauntlet, create Daytona jobs, submit to Kaggle, or
write generated artifacts into the repo.

Temporary one-scenario probe manifests were written under `/tmp` from the
committed Cycle 1 manifests. The selected scenarios preserved
`metadata.episode_steps == "500"`. The temporary manifests set
`min_completed_count` to `1` so the micro-probe measured selected-scenario
executability rather than full-matrix promotion thresholds.

Commands:

```bash
.venv/bin/python -m unittest tests.test_historical_champion_registry tests.test_historical_champion_gauntlet_manifests
.venv/bin/python -m unittest tests.test_evaluation_manifest_fixtures tests.test_evaluation_agent_loading tests.test_evaluation_official_runner
.venv/bin/python scripts/run_evaluation_experiment.py /tmp/ow-historical-gauntlet-cycle2-2p-probe-manifest.json --report-output /tmp/ow-historical-gauntlet-cycle2-2p-probe.json
.venv/bin/python scripts/run_evaluation_experiment.py /tmp/ow-historical-gauntlet-cycle2-4p-probe-manifest.json --report-output /tmp/ow-historical-gauntlet-cycle2-4p-probe.json
git diff --check
```

Probe results:

| Probe | Source manifest | Scenario label | Seed | Seat | Opponents | Runtime | Status | Triage | Error count |
|---|---|---|---:|---:|---|---:|---|---|---:|
| 2P | `historical-champion-gauntlet-2p-500.json` | `historical-gauntlet-2p-500-seat-0-vs-claude-v3-wide-search-forecast` | `7210` | `0` | `claude-v3-wide-search-forecast` | `21.21s` | `completed` | `normal_loss` | `0` |
| 4P | `historical-champion-gauntlet-4p-500.json` | `historical-gauntlet-4p-500-top-score-seat-0` | `8100` | `0` | `claude-v3-wide-search-forecast`, `claude-v28-mode-split-champion`, `claude-v37-race-fix-mode-split` | `31.16s` | `completed` | `normal_loss` | `0` |

Both reports had `completed_matches=1`, `error_rate=0.0`,
`promotion_passed=true`, and no timeout or invalid-action errors. The losses
are expected for a micro-probe against historical champions; Cycle 2 validates
that the full-500 matrix can execute through the local harness, not that the
current agent wins.

Generated probe files remained under `/tmp`:

```text
/tmp/ow-historical-gauntlet-cycle2-2p-probe-manifest.json
/tmp/ow-historical-gauntlet-cycle2-2p-probe.json
/tmp/ow-historical-gauntlet-cycle2-4p-probe-manifest.json
/tmp/ow-historical-gauntlet-cycle2-4p-probe.json
```

## Cycle 3 Daytona Shard Plan

Cycle 3 adds deterministic shard planning for the two committed full-horizon
gauntlet manifests. This is plan-only: no gauntlet matches, Daytona packages,
Daytona jobs, uploads, downloads, generated reports, scoreboards, logs, or
replays are created.

The planner API is:

```python
from ow_eval.historical_gauntlet_shards import build_historical_champion_shard_plan

plan = build_historical_champion_shard_plan()
print(plan.summary_text)
```

Default summary:

```text
historical_champion_shard_plan shards=6 total_scenarios=30 scenarios_per_shard=5,5,5,5,5,5 recommended_probe_shard=historical-gauntlet-shard-000
```

The default plan:

- Reads `historical-champion-gauntlet-2p-500.json` and
  `historical-champion-gauntlet-4p-500.json`.
- Assigns all 30 committed scenarios to exactly one shard.
- Preserves `episode_steps == "500"` for every planned scenario.
- Uses six deterministic round-robin shards with five scenarios per shard.
- Records stable shard ids, scenario labels, seeds, controlled seats, player
  counts, opponent names, source manifest names, and intended future output
  paths under `generated_results/historical_champion_gauntlet/`.
- Marks `historical-gauntlet-shard-000` as the recommended next single-shard
  Daytona probe input.

Cycle 3 validation:

```bash
.venv/bin/python -m unittest tests.test_historical_champion_registry tests.test_historical_champion_gauntlet_manifests
.venv/bin/python -m unittest tests.test_historical_champion_gauntlet_shards
.venv/bin/python -m unittest tests.test_evaluation_manifest_fixtures tests.test_evaluation_agent_loading tests.test_evaluation_official_runner
.venv/bin/python - <<'PY'
from ow_eval.historical_gauntlet_shards import build_historical_champion_shard_plan
plan = build_historical_champion_shard_plan()
print(plan.summary_text)
print(len(plan.shards), plan.total_scenarios)
PY
git diff --check
```
