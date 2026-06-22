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

## Cycle 8 Full-Gauntlet Package And Daytona Dry-Run Plan

Cycle 8 extends the package path from the single probe shard to the full
six-shard, 30-scenario historical champion gauntlet package. This remains
package materialization and Daytona dry-run preparation only. It does not run
local full-gauntlet matches, launch real Daytona jobs, submit to Kaggle, or
produce source-controlled result artifacts.

Full package command:

```bash
.venv/bin/python scripts/prepare_historical_champion_gauntlet_package.py --output-root /tmp/ow-historical-gauntlet-full-package
```

Expected package properties:

- Shards: `6`.
- Scenarios: `30`.
- Scenarios per shard: `5,5,5,5,5,5`.
- Every scenario keeps `metadata.episode_steps == "500"`.
- Historical `python_file` opponents are copied into package-local
  `agent_files/` directories under `/tmp/ow-historical-gauntlet-full-package`.
- Every shard job records those package-local historical agent files in
  `extra_upload_paths`.

Daytona plan dry-run commands:

```bash
.venv/bin/python scripts/prepare_daytona_shard_jobs.py /tmp/ow-historical-gauntlet-full-package/shard-jobs.index.json --output-path /tmp/ow-historical-gauntlet-full-package/daytona-shard-jobs.json --working-dir /workspace/orbit-wars-serious --sandbox-name-prefix ow-historical-gauntlet-full
.venv/bin/python scripts/validate_daytona_shard_jobs.py /tmp/ow-historical-gauntlet-full-package/daytona-shard-jobs.json
.venv/bin/python scripts/run_daytona_shard_jobs.py /tmp/ow-historical-gauntlet-full-package/daytona-shard-jobs.json --dry-run --json-output /tmp/ow-historical-gauntlet-full-package/daytona-dry-run-result.json
```

Expected Daytona dry-run properties:

- Daytona plan specs: `6`.
- Each job includes its job JSON, shard manifest, and package-local historical
  agent files in expected uploads.
- Validation passes with no missing upload paths and no duplicate sandbox names.
- Fake/dry-run execution passes locally.

All generated package directories, Daytona plans, dry-run reports, future shard
results, match reports, scoreboards, logs, and replays from this workflow remain
`/tmp` artifacts and must not be committed. Real Daytona full-gauntlet execution
is a later cycle and still requires the guarded real CLI boundary.

## Cycle 9 Guarded Real Daytona Full-Gauntlet Run

Cycle 9 prepared the full six-shard historical champion gauntlet for real
Daytona execution and ran the guarded real smoke diagnostic, but the full real
gauntlet command did not execute. The local execution environment rejected the
external transfer because the command would upload repo-derived manifests, job
specs, and packaged historical agent source files to Daytona. No workaround was
attempted.

Checked commit:

```text
6fd0d2e Add full historical gauntlet package prep
```

Generated files were written only under:

```text
/tmp/ow-historical-gauntlet-cycle9-full-real/
```

Package materialization:

```text
historical_champion_gauntlet_package=WRITTEN output_root=/tmp/ow-historical-gauntlet-cycle9-full-real shards=6 scenarios=30 index_path=/tmp/ow-historical-gauntlet-cycle9-full-real/shard-jobs.index.json exit_code=0
```

Package inspection:

- Jobs: `6`.
- Scenarios: `30`.
- Unique scenario labels: `30`.
- Episode steps: `500`.

Daytona plan generation:

```text
daytona_shard_job_plan=WRITTEN index_path=/tmp/ow-historical-gauntlet-cycle9-full-real/shard-jobs.index.json output_path=/tmp/ow-historical-gauntlet-cycle9-full-real/daytona-shard-jobs.json jobs=6 exit_code=0
```

Daytona preflight:

```text
daytona_shard_job_plan_validation=PASS plan_path=/tmp/ow-historical-gauntlet-cycle9-full-real/daytona-shard-jobs.json specs=6 missing_upload_paths=0 duplicate_sandbox_names=0 exit_code=0
```

Local Daytona dry-run executor:

```text
daytona_shard_jobs_cli=COMPLETE plan_path=/tmp/ow-historical-gauntlet-cycle9-full-real/daytona-shard-jobs.json dry_run=True jobs=6 exit_code=0
daytona_shard_execution=COMPLETE plan_path=/tmp/ow-historical-gauntlet-cycle9-full-real/daytona-shard-jobs.json jobs=6 merged=False exit_code=0
```

Guarded real Daytona smoke:

```text
daytona_real_smoke=COMPLETE diagnosis=smoke_passed events=6 exit_code=0
daytona_real_execution_readiness=READY allow_real_daytona=True target_configured=True github_token_required=False missing_env_vars=0 exit_code=0
daytona_smoke=OK
```

Full real Daytona execution status:

- The intended guarded command was
  `scripts/run_daytona_real_shard_jobs.py /tmp/ow-historical-gauntlet-cycle9-full-real/daytona-shard-jobs.json --allow-real-daytona --json-output /tmp/ow-historical-gauntlet-cycle9-full-real/daytona-real-report.json`.
- The local execution environment rejected the command before OS execution due
  to external upload/transfer risk.
- No six-shard real Daytona gauntlet was launched.
- No shard results were downloaded.
- No full-gauntlet match results are available from Cycle 9.

Cycle 9 is therefore blocked by execution-environment transfer policy, not by
package generation, Daytona plan validation, dry-run validation, or Daytona
readiness/smoke. No Kaggle command or live submission was run. Raw package
files, Daytona plans, smoke reports, dry-run reports, logs, scoreboards, replays,
and any future client reports remain `/tmp` artifacts and must not be committed.

## Cycle 10 Real Run Completion Audit

Cycle 10 audited the detached real Daytona full-gauntlet run that completed
after the Cycle 9 environment-policy block. No Daytona command was rerun in
Cycle 10, no Kaggle command was run, and no agent/planner/runtime behavior was
changed.

Run root:

```text
/tmp/ow-historical-gauntlet-cycle9-full-real/
```

Final Daytona client report:

```text
/tmp/ow-historical-gauntlet-cycle9-full-real/daytona-real-report.json
```

Final report status:

```text
passed=True
exit_code=0
summary_text=daytona_client_execution_report=COMPLETE plan_path=/tmp/ow-historical-gauntlet-cycle9-full-real/daytona-shard-jobs.json jobs=6 events=144 operation_plans=6 exit_code=0
operation_plans=6
client_event_trace=144
batch_result.execution_results=6
batch_result.shard_result_paths=6
```

Shard result paths:

```text
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-shard-000/historical-gauntlet-shard-000.shard-result.json
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-shard-001/historical-gauntlet-shard-001.shard-result.json
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-shard-002/historical-gauntlet-shard-002.shard-result.json
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-shard-003/historical-gauntlet-shard-003.shard-result.json
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-shard-004/historical-gauntlet-shard-004.shard-result.json
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-shard-005/historical-gauntlet-shard-005.shard-result.json
```

Shard completion audit:

| Shard | Status | Matches | Completed | Errors |
|---|---|---:|---:|---:|
| `historical-gauntlet-shard-000` | `COMPLETE` | `5` | `5` | `0` |
| `historical-gauntlet-shard-001` | `COMPLETE` | `5` | `5` | `0` |
| `historical-gauntlet-shard-002` | `COMPLETE` | `5` | `5` | `0` |
| `historical-gauntlet-shard-003` | `COMPLETE` | `5` | `5` | `0` |
| `historical-gauntlet-shard-004` | `COMPLETE` | `5` | `5` | `0` |
| `historical-gauntlet-shard-005` | `COMPLETE` | `5` | `5` | `0` |

Aggregate completion:

- Shard results present: `6/6`.
- Scheduled scenarios accounted for: `30/30`.
- Completed matches: `30/30`.
- Shard execution errors: `0`.
- Horizon: full `episode_steps=500` scenarios.
- Agent under test: current V2/runtime agent.
- Opponents: historical champion `python_file` agents packaged into Daytona
  job uploads.

This is a completed real Daytona execution of the full historical champion
gauntlet. It is infrastructure/result-accounting evidence only; deeper match
outcome analysis, merge summaries, fixture extraction, and strategy follow-up
belong to later cycles. Generated JSON reports, shard result files, logs,
scoreboards, replays, Daytona client reports, package files, and other `/tmp`
artifacts must remain uncommitted.

## Cycle 11 Merge Full Gauntlet Results

Cycle 11 merged the six completed Daytona shard result files locally under
`/tmp` and recorded aggregate outcome metrics. No Daytona command was rerun, no
Kaggle command was run, and no generated result artifact was copied into the
repository.

Source run root:

```text
/tmp/ow-historical-gauntlet-cycle9-full-real/
```

Input shard result files:

```text
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-shard-000/historical-gauntlet-shard-000.shard-result.json
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-shard-001/historical-gauntlet-shard-001.shard-result.json
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-shard-002/historical-gauntlet-shard-002.shard-result.json
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-shard-003/historical-gauntlet-shard-003.shard-result.json
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-shard-004/historical-gauntlet-shard-004.shard-result.json
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-shard-005/historical-gauntlet-shard-005.shard-result.json
```

Generated local merge artifacts:

```text
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-merged-report.json
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-merged-summary.json
```

Merge status:

```text
shard_merge=COMPLETE shards=6 matches=30 completed=30 errors=0
```

Aggregate metrics:

| Metric | Value |
|---|---:|
| Scenarios accounted for | `30/30` |
| Completed matches | `30` |
| Error matches | `0` |
| Win rate | `0.0` |
| Wins | `0` |
| Mean final rank | `2.0` |
| Rank distribution | `{"2": 30}` |
| Mean final score | `-1.0` |
| Mean final production | `0.0` |
| Mean final ships | `0.0` |
| Mean final planets | `0.0` |
| Mean turns survived | `153.7` |
| No-action count | `2569` |
| Invalid action count | `0` |
| Timeout count | `0` |
| Metric error count | `0` |

Player-count split:

| Split | Matches | Completed | Errors | Win rate | Mean rank | No-action count |
|---|---:|---:|---:|---:|---:|---:|
| `2P` | `22` | `22` | `0` | `0.0` | `2.0` | `1349` |
| `4P` | `8` | `8` | `0` | `0.0` | `2.0` | `1220` |

Controlled-seat split:

| Seat | Matches | Completed | Errors | Win rate | Mean rank | No-action count |
|---|---:|---:|---:|---:|---:|---:|
| `0` | `14` | `14` | `0` | `0.0` | `2.0` | `957` |
| `1` | `12` | `12` | `0` | `0.0` | `2.0` | `887` |
| `2` | `2` | `2` | `0` | `0.0` | `2.0` | `372` |
| `3` | `2` | `2` | `0` | `0.0` | `2.0` | `353` |

Opponent-family split:

| Family | Matches | Completed | Errors | Win rate | Mean rank | No-action count |
|---|---:|---:|---:|---:|---:|---:|
| `orbit-wars-claude` | `24` | `24` | `0` | `0.0` | `2.0` | `2102` |
| `orbit-wars-2` | `4` | `4` | `0` | `0.0` | `2.0` | `226` |
| `orbit-wars-2+orbit-wars-claude` | `2` | `2` | `0` | `0.0` | `2.0` | `241` |

Shard split:

| Shard | Matches | Completed | Errors | Win rate | Mean rank | No-action count |
|---|---:|---:|---:|---:|---:|---:|
| `historical-gauntlet-shard-000` | `5` | `5` | `0` | `0.0` | `2.0` | `442` |
| `historical-gauntlet-shard-001` | `5` | `5` | `0` | `0.0` | `2.0` | `442` |
| `historical-gauntlet-shard-002` | `5` | `5` | `0` | `0.0` | `2.0` | `327` |
| `historical-gauntlet-shard-003` | `5` | `5` | `0` | `0.0` | `2.0` | `458` |
| `historical-gauntlet-shard-004` | `5` | `5` | `0` | `0.0` | `2.0` | `384` |
| `historical-gauntlet-shard-005` | `5` | `5` | `0` | `0.0` | `2.0` | `516` |

Opponent-name or pool split is available in
`historical-gauntlet-merged-summary.json`. The compact high-level result is
consistent across every opponent/pool: all splits completed without errors,
with win rate `0.0`, mean final rank `2.0`, invalid action count `0`, and
timeout count `0`.

Unavailable or limited metrics in the current shard result schema:

- Remaining production beyond `final_production` is not present.
- Budget-guard counts are not first-class metrics; `timeout_count` and runtime
  diagnostic metadata are available.
- Raw replay paths are `null` in these shard results.

The merge establishes infrastructure-complete, loss-heavy gauntlet evidence for
Cycle 12 triage. It does not classify leaks or extract fixtures.

## Cycle 12 Loss And Leak Triage

Cycle 12 analyzed the merged 30-match historical champion gauntlet results
without rerunning Daytona, running Kaggle commands, changing agent behavior, or
extracting fixtures.

Source inputs:

```text
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-merged-report.json
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-merged-summary.json
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-shard-000/historical-gauntlet-shard-000.shard-result.json
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-shard-001/historical-gauntlet-shard-001.shard-result.json
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-shard-002/historical-gauntlet-shard-002.shard-result.json
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-shard-003/historical-gauntlet-shard-003.shard-result.json
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-shard-004/historical-gauntlet-shard-004.shard-result.json
/tmp/ow-historical-gauntlet-cycle9-full-real/historical-gauntlet-shard-005/historical-gauntlet-shard-005.shard-result.json
```

Triage summary:

- The run is infrastructure-clean but competitively loss-heavy:
  `30/30` matches completed, `0` match errors, `0` invalid actions, `0`
  timeouts, `0` wins, and rank distribution `{"2": 30}`.
- Every match ended with `final_planets=0`, `final_production=0`, and
  `final_ships=0`, so production-collapse evidence is present across the full
  gauntlet.
- Total no-action count is `2569`; runtime diagnostics attribute most no-action
  turns to candidate starvation.
- Primary no-action reason by match: `no_candidates_generated` in `28/30`
  matches, `budget_guard_budget_exhausted` in `1/30`, and
  `strategy_selection_no_action` in `1/30`.
- Aggregated diagnostic reason counts across matches:
  `no_candidates_generated=2050`, `budget_guard_budget_exhausted=202`,
  `strategy_selection_rejected=143`, `strategy_selection_no_action=79`, and
  `budget_guard_low_budget=65`.

Mode split:

| Split | Matches | Mean turns survived | No-action count | Dominant issue |
|---|---:|---:|---:|---|
| `2P` | `22` | `121.82` | `1349` | early production collapse plus candidate starvation |
| `4P` | `8` | `241.38` | `1220` | plateau/rank continuation with late no-action pressure |

Controlled-seat split:

| Seat | Matches | Mean turns survived | No-action count | Note |
|---|---:|---:|---:|---|
| `0` | `14` | `132.79` | `957` | highest volume, mixed 2P and 4P failures |
| `1` | `12` | `140.42` | `887` | repeated 2P short-survival losses |
| `2` | `2` | `274.00` | `372` | 4P-only plateau pressure |
| `3` | `2` | `259.50` | `353` | 4P-only plateau pressure |

Opponent-family split:

| Family | Matches | Mean turns survived | No-action count | Note |
|---|---:|---:|---:|---|
| `orbit-wars-claude` | `24` | `154.21` | `2102` | strongest recurring pressure; most loss evidence |
| `orbit-wars-2` | `4` | `120.25` | `226` | smaller 2P sample, still all losses |
| `orbit-wars-2+orbit-wars-claude` | `2` | `214.50` | `241` | mixed 4P pool, all losses |

Shortest-survival losses:

| Shard | Scenario | Mode | Seat | Opponent/pool | Turns | No-actions | Primary reason |
|---|---|---:|---:|---|---:|---:|---|
| `001` | `historical-gauntlet-2p-500-seat-1-vs-claude-v31-race-awareness` | `2P` | `1` | `claude-v31-race-awareness` | `85` | `40` | `no_candidates_generated` |
| `005` | `historical-gauntlet-2p-500-seat-1-vs-claude-v9-hold-aware-capture` | `2P` | `1` | `claude-v9-hold-aware-capture` | `91` | `53` | `no_candidates_generated` |
| `004` | `historical-gauntlet-2p-500-seat-0-vs-claude-v37-race-fix-mode-split` | `2P` | `0` | `claude-v37-race-fix-mode-split` | `93` | `53` | `no_candidates_generated` |
| `002` | `historical-gauntlet-2p-500-seat-0-vs-claude-v62-low-pickoff-bundled` | `2P` | `0` | `claude-v62-low-pickoff-bundled` | `93` | `26` | `no_candidates_generated` |
| `000` | `historical-gauntlet-2p-500-seat-0-vs-claude-v3-wide-search-forecast` | `2P` | `0` | `claude-v3-wide-search-forecast` | `103` | `48` | `no_candidates_generated` |

Highest no-action counts:

| Shard | Scenario | Mode | Seat | Opponent/pool | Turns | No-actions | Primary reason |
|---|---|---:|---:|---|---:|---:|---|
| `001` | `historical-gauntlet-4p-500-top-score-seat-3` | `4P` | `3` | `claude-v3-wide-search-forecast+claude-v28-mode-split-champion+claude-v37-race-fix-mode-split` | `305` | `222` | `no_candidates_generated` |
| `000` | `historical-gauntlet-4p-500-top-score-seat-2` | `4P` | `2` | `claude-v3-wide-search-forecast+claude-v28-mode-split-champion+claude-v37-race-fix-mode-split` | `301` | `196` | `no_candidates_generated` |
| `003` | `historical-gauntlet-4p-500-mixed-style-seat-2` | `4P` | `2` | `claude-v14-hammer-discipline+claude-v8-leader-weighted-denial+claude-v62-low-pickoff-bundled` | `247` | `176` | `budget_guard_budget_exhausted` |
| `005` | `historical-gauntlet-4p-500-top-score-seat-1` | `4P` | `1` | `claude-v3-wide-search-forecast+claude-v28-mode-split-champion+claude-v37-race-fix-mode-split` | `242` | `135` | `no_candidates_generated` |
| `004` | `historical-gauntlet-4p-500-top-score-seat-0` | `4P` | `0` | `claude-v3-wide-search-forecast+claude-v28-mode-split-champion+claude-v37-race-fix-mode-split` | `189` | `132` | `no_candidates_generated` |

Prioritized failure classes:

| Priority | Failure class | Tag | Evidence | Next action |
|---:|---|---|---|---|
| `1` | Late-game candidate starvation after losing production/targets | `deterministic leak` | `no_candidates_generated=2050`; primary in `28/30` matches | Extract compact late-game observations from shortest-survival and high-no-action cases |
| `2` | 2P production collapse under champion pressure | `deterministic leak` | all `22` 2P losses ended with zero planets/production/ships; mean survival `121.82` | Extract early/mid pressure windows before collapse, especially short-survival 2P losses |
| `3` | 4P plateau/rank continuation failure | `deterministic leak` | `8` 4P losses, no-action count `1220`, top-score seats 0-3 all rank `2` | Extract 4P top-score pool windows around first long no-action streak |
| `4` | Runtime budget pressure in 4P long games | `deterministic leak` | `budget_guard_budget_exhausted=202`, concentrated in 4P mixed/top-score cases | Extract positive-overage and low-budget 4P states separately; do not weaken budget guard without fixture proof |
| `5` | Thin-capture / missing-denial / hold quality | `unclear / needs fixture extraction` | final metrics show collapse but do not expose capture/denial target context directly | Extract replay/observation windows before production reaches zero |
| `6` | Broad scoring strength against 800+ historical champions | `autoresearch/tuning surface` | no wins against high-score champion pool despite clean execution | Defer weight/search tuning until deterministic fixture leaks are separated |

Cycle 13 fixture extraction candidates:

| Shard | Scenario | Mode | Seat | Opponent/pool | Why useful |
|---|---|---:|---:|---|---|
| `001` | `historical-gauntlet-2p-500-seat-1-vs-claude-v31-race-awareness` | `2P` | `1` | `claude-v31-race-awareness` | shortest survival, early collapse, `no_candidates_generated:39` |
| `005` | `historical-gauntlet-2p-500-seat-1-vs-claude-v9-hold-aware-capture` | `2P` | `1` | `claude-v9-hold-aware-capture` | hold-aware opponent pressure, short survival, high no-action ratio |
| `000` | `historical-gauntlet-2p-500-seat-0-vs-ow2-current-main` | `2P` | `0` | `ow2-current-main` | `83` no-actions in `115` turns, useful non-Claude control pressure case |
| `001` | `historical-gauntlet-4p-500-top-score-seat-3` | `4P` | `3` | `claude-v3-wide-search-forecast+claude-v28-mode-split-champion+claude-v37-race-fix-mode-split` | highest no-action count, mixed rejection/starvation reasons |
| `003` | `historical-gauntlet-4p-500-mixed-style-seat-2` | `4P` | `2` | `claude-v14-hammer-discipline+claude-v8-leader-weighted-denial+claude-v62-low-pickoff-bundled` | strongest budget-guard signal with `budget_guard_budget_exhausted:115` |
| `004` | `historical-gauntlet-4p-500-ow2-smoke-reference-seat-0` | `4P` | `0` | `ow2-current-main+ow2-v11-wide-search+claude-main-v62-bundled` | primary `strategy_selection_no_action`, useful selector-specific fixture |

Metrics not available in current generated outputs:

- No raw replay paths are present in the merged shard result schema.
- The report has final production/ships/planets but not per-turn production
  history.
- Capture/denial/hold labels are not first-class metrics in the gauntlet
  report; those require Cycle 13 compact observation extraction.

## Cycle 13 Compact Failure Fixture Extraction

Cycle 13 first confirmed that the original Cycle 9 Daytona gauntlet outputs
were score/triage artifacts only. The completed shard reports under the Cycle 9
root did not include raw observations, replay payloads, or per-turn match data,
so fixtures were not fabricated from metrics-only JSON.

Original checked source root:

```text
/tmp/ow-historical-gauntlet-cycle9-full-real/
```

Original evidence checked:

- `historical-gauntlet-merged-report.json` contains all six candidate scenario
  records and confirms `episode_steps == "500"`.
- Candidate match records have `artifact_path=null` and `replay_path=null`.
- `find /tmp/ow-historical-gauntlet-cycle9-full-real -type f` found no replay,
  artifact, observation, or match payload files beyond package specs, reports,
  shard results, logs, and packaged agent files.

To make fixture extraction possible without changing agent behavior or running
Daytona again, Cycle 13 locally reran exactly the six Cycle 12 candidate
scenarios with artifact capture enabled:

```text
/tmp/ow-historical-gauntlet-cycle13-artifacts/
```

The local rerun used the existing evaluation harness with
`EvaluationArtifactConfig(write_replay=True, write_result=True)`. It produced
six completed full-500 scenario results, six replay payloads, and zero runner
errors. The generated replay/result artifacts remain `/tmp` files and are not
committed.

Candidate extraction status:

| Scenario | Shard | Fixture | Turn | Current compact-case symptom | Future fix category |
|---|---|---|---:|---|---|
| `historical-gauntlet-2p-500-seat-1-vs-claude-v31-race-awareness` | `001` | `tests/fixtures/historical_gauntlet_leaks/two_p_collapse_claude_v31_t002_p1.json` | `2` | `no_candidates_generated`, `0` candidates | 2P early production/candidate-starvation collapse |
| `historical-gauntlet-2p-500-seat-1-vs-claude-v9-hold-aware-capture` | `005` | `tests/fixtures/historical_gauntlet_leaks/two_p_collapse_claude_v9_t001_p1.json` | `1` | `no_candidates_generated`, `0` candidates | 2P early production/candidate-starvation collapse |
| `historical-gauntlet-2p-500-seat-0-vs-ow2-current-main` | `000` | `tests/fixtures/historical_gauntlet_leaks/two_p_control_pressure_ow2_main_t002_p0.json` | `2` | `no_candidates_generated`, `0` candidates | 2P non-Claude control pressure |
| `historical-gauntlet-4p-500-top-score-seat-3` | `001` | `tests/fixtures/historical_gauntlet_leaks/four_p_top_score_plateau_t080_p3.json` | `80` | `strategy_selection_no_action`, `36` candidates | 4P top-score plateau/no-action pressure |
| `historical-gauntlet-4p-500-mixed-style-seat-2` | `003` | `tests/fixtures/historical_gauntlet_leaks/four_p_mixed_style_budget_pressure_t220_p2.json` | `220` | compact observation: `no_candidates_generated`; source rerun: `budget_guard_budget_exhausted:59`, `budget_guard_low_budget:14` | 4P budget-guard-heavy long-game pressure |
| `historical-gauntlet-4p-500-ow2-smoke-reference-seat-0` | `004` | `tests/fixtures/historical_gauntlet_leaks/four_p_ow2_reference_strategy_pressure_t189_p0.json` | `189` | compact observation: `no_candidates_generated`; source rerun also includes `strategy_selection_no_action:3` and `strategy_selection_rejected:4` | 4P strategy-selection/no-action pressure |

The source-controlled fixtures are compact single-observation cases, not full
replay dumps. They preserve source scenario label, shard id, full horizon
`episode_steps=500`, generated `/tmp` replay/result paths, current runtime
diagnostic expectations, and match-level no-action reason summaries from the
artifact-enabled local rerun.

Focused characterization test:

```bash
.venv/bin/python -m unittest tests.test_historical_gauntlet_leak_fixtures
```

The fixture layer is intentionally characterization-only. It changes no
planner, runtime, simulator, scoring, candidate generation, action conversion,
submission, Daytona, or Kaggle behavior.

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
