# Distributed Evaluation And Daytona Sharding Runbook

This runbook covers the local-only distributed-evaluation sharding workflow and the
guarded Daytona execution boundary. The workflow is for local official
`kaggle_environments` evaluation and Daytona-preparation checks only. It does
not submit to live Kaggle, does not spend live Kaggle submissions, and does not
make accidental Daytona calls.
It does not submit to live Kaggle.

Real Daytona execution is guarded. It requires both environment readiness and
the explicit `--allow-real-daytona` CLI flag. Without both gates, the real
Daytona CLI fails before importing `daytona`, constructing an SDK client,
creating sandboxes, uploading files, downloading files, or running worker
commands.

Run commands from `/Users/user/dev/hackathons/orbit-wars-serious`.

## Manifest Inputs

Committed local smoke manifests live under `experiments/manifests/`:

- `experiments/manifests/quick-2p-smoke.json`
- `experiments/manifests/quick-4p-smoke.json`
- `experiments/manifests/promotion-smoke.json`

Use these committed fixtures for local smoke sharding and Daytona preparation.
They are local evaluation manifests, not live Kaggle submission records.

## Workflow Order

0. Run the one-command distributed evaluation preflight. This composes shard
   packaging, Daytona plan writing, Daytona preflight validation, fake executor
   dry-run, fake client-report dry-run, and guarded real-Daytona fail-closed
   validation.

```bash
.venv/bin/python scripts/distributed_evaluation_preflight.py --shard-count 2
```

1. Build a local shard plan and run it sequentially in-process.

```bash
.venv/bin/python scripts/run_evaluation_shards.py experiments/manifests/quick-2p-smoke.json --shard-count 2
```

2. Prepare deterministic shard manifests, job JSON files, and a shard job
   package index. Use an explicit output directory so generated files stay out
   of the repository.

```bash
.venv/bin/python scripts/prepare_evaluation_shards.py experiments/manifests/quick-2p-smoke.json --shard-count 2 --output-dir /tmp/ow-eval-shards
```

3. Run a local package-index workflow sequentially through the same job/index
   boundary that future workers use.

```bash
.venv/bin/python scripts/run_evaluation_shard_index.py /tmp/ow-eval-shards/shard-jobs.index.json
```

4. Convert the shard job index into a Daytona-ready worker job plan JSON.

```bash
.venv/bin/python scripts/prepare_daytona_shard_jobs.py /tmp/ow-eval-shards/shard-jobs.index.json --output-path /tmp/ow-eval-shards/daytona-shard-jobs.json
```

5. Validate the Daytona job plan before any execution boundary uses it.

```bash
.venv/bin/python scripts/validate_daytona_shard_jobs.py /tmp/ow-eval-shards/daytona-shard-jobs.json
```

6. Dry-run the structured Daytona executor boundary. This validates preflight
   and request construction without creating sandboxes, executing worker argv,
   uploading files, downloading files, or running matches.

```bash
.venv/bin/python scripts/run_daytona_shard_jobs.py /tmp/ow-eval-shards/daytona-shard-jobs.json --dry-run --no-upload-path-existence-check
```

7. Dry-run the client-report boundary. This records fake client events and
   operation plans without real Daytona calls.

```bash
.venv/bin/python scripts/run_daytona_client_report.py /tmp/ow-eval-shards/daytona-shard-jobs.json --dry-run --no-upload-path-existence-check
```

8. Use the guarded real-Daytona CLI only when intentionally preparing a real
   Daytona attempt. It still requires environment readiness and
   `--allow-real-daytona`.

```bash
.venv/bin/python scripts/run_daytona_real_shard_jobs.py /tmp/ow-eval-shards/daytona-shard-jobs.json --allow-real-daytona
```

9. Before a full real shard run, use the guarded smoke diagnostic to isolate
   Daytona setup and process-execution failures without uploading a shard
   package or running matches. The default smoke command runs a tiny Python
   import from `DAYTONA_WORKING_DIR`.

```bash
.venv/bin/python scripts/run_daytona_real_smoke.py --allow-real-daytona --json-output /tmp/ow-daytona-smoke/result.json
```

10. If no prebuilt Daytona snapshot or image exists yet, prepare a clean runtime
   snapshot context from committed tracked source. The default command is a
   local dry-run: it uses `git archive HEAD`, writes the materialized source and
   dependency lock context under `/tmp`, and does not create a Daytona resource.

```bash
.venv/bin/python scripts/prepare_daytona_runtime_snapshot.py --output-dir /tmp/ow-daytona-runtime-snapshot
```

11. Create the real runtime snapshot only after the dry-run context looks
    correct and real Daytona readiness is intentionally enabled. This command is
    the setup step that creates one reusable Daytona snapshot; it still does not
    run gauntlet matches or submit to Kaggle.

```bash
.venv/bin/python scripts/prepare_daytona_runtime_snapshot.py --allow-real-daytona --json-output /tmp/ow-daytona-runtime-snapshot/result.json
```

## Scripts And Responsibilities

- `scripts/run_evaluation_shards.py`: local sequential multi-shard workflow
  from manifest paths to shard runs and merged in-memory results.
- `scripts/prepare_evaluation_shards.py`: no-execution shard job package and
  index preparation.
- `scripts/run_evaluation_shard_job.py`: local single-shard job worker boundary
  for one packaged job JSON.
- `scripts/run_evaluation_shard_index.py`: local sequential shard job index
  runner and merge workflow.
- `scripts/prepare_daytona_shard_jobs.py`: writes a deterministic Daytona job
  plan JSON from a shard job index.
- `scripts/validate_daytona_shard_jobs.py`: reads and preflights a Daytona job
  plan JSON.
- `scripts/run_daytona_shard_jobs.py`: dry-run executor boundary over a Daytona
  job plan.
- `scripts/run_daytona_client_report.py`: dry-run client-report workflow with
  fake client event traces and operation plans.
- `scripts/run_daytona_real_shard_jobs.py`: guarded real-Daytona execution
  boundary requiring both env readiness and `--allow-real-daytona`. The
  official SDK path creates sandboxes from `DAYTONA_SNAPSHOT_ID`, or from
  `DAYTONA_IMAGE` when no snapshot is configured.
- `scripts/run_daytona_real_smoke.py`: guarded real-Daytona smoke diagnostic
  that opens one sandbox, runs one tiny command, closes the sandbox, and
  classifies the failure layer before a full shard attempt.
- `scripts/prepare_daytona_runtime_snapshot.py`: guarded runtime snapshot
  setup. The default mode materializes committed tracked source under `/tmp`;
  `--allow-real-daytona` creates the reusable Daytona snapshot after readiness
  passes.
- `scripts/distributed_evaluation_preflight.py`: one-command local acceptance
  gate over shard packaging, Daytona plan generation, preflight validation,
  fake dry-runs, and guarded real-Daytona fail-closed behavior.

## Modules

- `ow_eval/sharding.py`: deterministic shard-plan contracts.
- `ow_eval/shard_runner.py`: local single-shard runner.
- `ow_eval/shard_persistence.py`: single-shard result JSON persistence.
- `ow_eval/shard_merge.py`: deterministic shard result merge.
- `ow_eval/shard_cli.py`: local sequential multi-shard workflow.
- `ow_eval/shard_manifests.py`: per-shard experiment manifest materialization.
- `ow_eval/shard_jobs.py`: portable shard job specs and package index.
- `ow_eval/shard_package_cli.py`: shard job package preparation CLI workflow.
- `ow_eval/shard_job_runner.py`: local single packaged job runner.
- `ow_eval/shard_index_runner.py`: local sequential package-index runner.
- `ow_eval/daytona_jobs.py`: Daytona-ready worker job spec contracts.
- `ow_eval/daytona_plan_cli.py`: deterministic Daytona job plan writer.
- `ow_eval/daytona_preflight.py`: plan reader and preflight validation.
- `ow_eval/daytona_executor.py`: injected executor protocol boundary.
- `ow_eval/daytona_executor_cli.py`: fake dry-run executor CLI.
- `ow_eval/daytona_operations.py`: explicit upload, command, and download
  operation plans.
- `ow_eval/daytona_client_executor.py`: injected Daytona-like client executor.
- `ow_eval/daytona_client_report.py`: client event trace and operation plan
  report contract.
- `ow_eval/daytona_client_report_cli.py`: fake client-report dry-run CLI.
- `ow_eval/daytona_real_config.py`: real-execution config and readiness gate.
- `ow_eval/daytona_sdk_adapter.py`: SDK adapter and fake-compatible protocol
  facade.
- `ow_eval/daytona_real_cli.py`: guarded real-Daytona client-report CLI.
- `ow_eval/distributed_preflight.py`: one-command distributed evaluation
  acceptance preflight.

## Real Execution Configuration

Real Daytona execution is blocked by default. The guarded CLI reads config from
environment variables. When `env` is not passed explicitly, the config reader
also loads a local `.env` file through `python-dotenv` with `override=False`.
That lets shell-provided values win over `.env` values.

The recommended setup for repeated full-horizon historical gauntlets is a
prebuilt Daytona snapshot or image that already has this repository checked out
at `DAYTONA_WORKING_DIR` with `.venv` dependencies installed. That keeps shard
startup fast and avoids passing a GitHub token into every sandbox.

When no prepared snapshot/image exists, create one through
`scripts/prepare_daytona_runtime_snapshot.py`. It deliberately packages only
committed tracked files via `git archive HEAD`, so `.env`, `.venv`, untracked
analysis files, generated reports, logs, and scratch artifacts are excluded from
the snapshot source context. Commit intended setup changes before creating a
snapshot if those changes must exist inside the remote runtime.

Copy `.env.example` to `.env` and fill local values. `.env` must stay
untracked.

Recommended prebuilt snapshot/image variables:

- `OW_EVAL_ALLOW_REAL_DAYTONA`: must be truthy, for example `1` or `true`.
- `DAYTONA_API_KEY_ENV_VAR`: optional name of the token env var. Defaults to
  `DAYTONA_API_KEY`.
- `DAYTONA_API_KEY`: default required token env var unless
  `DAYTONA_API_KEY_ENV_VAR` names a different variable.
- `DAYTONA_TARGET`: optional Daytona runner target/region, for example `us`.
- `DAYTONA_API_URL`: optional Daytona API URL override. Leave unset for the SDK
  default.
- `DAYTONA_SNAPSHOT_ID`: optional prepared snapshot identifier.
- `DAYTONA_IMAGE`: optional prepared image identifier.
- `DAYTONA_WORKING_DIR`: optional worker working directory override. Defaults
  to `/workspace/orbit-wars-serious`.
- `DAYTONA_SANDBOX_NAME_PREFIX`: optional sandbox name prefix override.

Optional clone-bootstrap variables:

- `OW_EVAL_REQUIRE_GITHUB_TOKEN`: set to `1` only for a clone-bootstrap path
  where the remote sandbox must clone a private GitHub repository.
- `GITHUB_TOKEN_ENV_VAR`: optional name of the GitHub token env var. Defaults
  to `GITHUB_TOKEN`.
- `GITHUB_TOKEN`: required only when `OW_EVAL_REQUIRE_GITHUB_TOKEN=1`.

Legacy/placeholder variables still parsed for compatibility:

- `DAYTONA_PROJECT_ID`: optional future project identifier.
- `DAYTONA_WORKSPACE_ID`: optional future workspace identifier.

Both gates are required:

```bash
OW_EVAL_ALLOW_REAL_DAYTONA=1 DAYTONA_API_KEY=... .venv/bin/python scripts/run_daytona_real_shard_jobs.py /tmp/ow-eval-shards/daytona-shard-jobs.json --allow-real-daytona
```

For actual shard execution, set `DAYTONA_SNAPSHOT_ID` to the reusable runtime
snapshot created by `scripts/prepare_daytona_runtime_snapshot.py`. Keep
`DAYTONA_IMAGE` unset unless intentionally testing a raw image path.

If `OW_EVAL_ALLOW_REAL_DAYTONA` or the required Daytona token env var is
missing, the CLI returns a structured failure before importing `daytona` or
touching any SDK client. If `OW_EVAL_REQUIRE_GITHUB_TOKEN=1`, the configured
GitHub token env var is also required. If `--allow-real-daytona` is missing,
readiness alone is not enough and the CLI still fails closed.

Install the Daytona Python SDK into the local launcher environment before a real
attempt:

```bash
.venv/bin/python -m pip install daytona
```

The current guarded adapter still uses the repo's typed client boundary. Before
a real multi-shard run, verify the adapter path matches the installed Daytona
SDK version and the chosen remote bootstrap mode.

## Cycle 7 Daytona Setup Consolidation Status

Cycle 7 consolidated the real Daytona setup path from the previous blocked
state into a working guarded execution workflow. The implementation now supports
local `.env` loading, runtime snapshot preparation, a guarded real smoke
diagnostic, package-local uploads for historical `python_file` opponents, and
session-based Daytona command execution for long-running shard jobs.

Current non-secret setup evidence:

- Daytona auth works through the local `.env`/environment readiness path.
- A runtime snapshot exists and is configured through `DAYTONA_SNAPSHOT_ID`.
- `scripts/run_daytona_real_smoke.py --allow-real-daytona` passed against the
  configured snapshot.
- A synchronous full-shard command attempt hit a Daytona proxy disconnect, so
  long worker commands must use Daytona process sessions instead of relying on
  one long `process.exec` call.
- Session-based command execution completed
  `historical-gauntlet-shard-000` through real Daytona.
- The completed single-shard probe produced infrastructure-success evidence:
  `5` completed matches, `0` execution errors, and mean final rank `2.0`.

Generated smoke reports, client reports, shard results, match reports,
scoreboards, logs, replays, and package directories from that work remain `/tmp`
artifacts and must not be committed. The real single-shard result is setup
evidence only; it is not a full historical champion gauntlet and does not
authorize running the remaining shards without a separate cycle.

## Artifact Policy

Generated plans, shard manifests, job JSON files, shard result files, logs,
reports, scoreboards, replay JSON, match outputs, generated submissions, and
temporary artifacts should not be committed unless explicitly intended as source
fixtures. Prefer `/tmp/ow-eval-shards` or another ignored local directory for
generated output.

Use explicit output arguments such as `--output-dir`, `--output-path`,
`--json-output`, or report paths only when you intentionally want files written.
Do not commit routine generated Daytona plans, shard result JSON files, client
reports, logs, scoreboards, or temporary package directories.

## Safety Policy

- No live Kaggle submissions are part of this workflow.
- Fake Daytona dry-runs do not create sandboxes, execute worker argv, upload
  files, download files, or run matches.
- Real Daytona execution cannot happen accidentally; it requires both env
  readiness and `--allow-real-daytona`.
- Do not execute generated `worker_argv` strings directly. Use the typed
  runner boundaries.
- Do not bypass preflight validation before real execution.

## Troubleshooting

- Missing upload paths: run `scripts/validate_daytona_shard_jobs.py` and confirm
  every job JSON and materialized shard manifest path exists. Re-run
  `scripts/prepare_evaluation_shards.py` if inputs were deleted.
- Duplicate sandbox names: regenerate the Daytona plan with a unique sandbox
  prefix, or use `--allow-duplicate-sandbox-names` only for local validation
  cases where duplicate names are intentional.
- Missing env/token: set `OW_EVAL_ALLOW_REAL_DAYTONA=1`, `DAYTONA_API_KEY`,
  and `DAYTONA_TARGET` before using the guarded real CLI. If using
  clone-bootstrap, also set `OW_EVAL_REQUIRE_GITHUB_TOKEN=1` and `GITHUB_TOKEN`.
- Blocked readiness: inspect the readiness error. Common causes are missing
  `OW_EVAL_ALLOW_REAL_DAYTONA`, missing token env vars, or forgetting
  `--allow-real-daytona`.
- Daytona SDK/proxy failures: run `scripts/run_daytona_real_smoke.py` first.
  `diagnosis=command_transport_failed` means sandbox creation succeeded but the
  Daytona process-execution endpoint failed before the smoke command returned.
  `diagnosis=snapshot_command_failed` means the endpoint worked and the command
  ran inside the sandbox but the snapshot command failed, usually because the
  working directory or dependencies are wrong.
- No-op-heavy regression gate failures: run the local regression gate and
  analysis pack workflow from `docs/evaluation-harness.md`, then inspect triage
  and planner diagnostics before attempting distributed or real Daytona work.
