# Evaluation Harness Runbook

This harness is for local evaluation only. It runs local `kaggle_environments`
Orbit Wars matches and local repository checks so the agent can be screened
before spending scarce live Kaggle competition submissions. It does not submit
to live Kaggle, upload agents, or automate live submission decisions.
It is local evaluation, not live Kaggle submission.
The local harness does not submit to live Kaggle.

Live competition submissions are limited. Run the local preflight and relevant
evaluation commands before asking to spend a live submission attempt.

## Local Workflow

Run the checks from `/Users/user/dev/hackathons/orbit-wars-serious`.

1. Run unit and discovery tests.

```bash
.venv/bin/python -m unittest discover -s tests
```

2. Build a deterministic single-file submission into a temporary or explicit
   local output path.

```bash
.venv/bin/python scripts/build_submission.py --output /tmp/orbit_wars_submission.py
```

3. Run the quick local regression gate.

```bash
.venv/bin/python scripts/evaluation_gate.py
```

4. Run one manifest through the local experiment workflow.

```bash
.venv/bin/python scripts/run_evaluation_experiment.py experiments/manifests/quick-2p-smoke.json
```

5. Run a suite of manifests. With no manifest arguments, the command uses the
   committed smoke fixtures under `experiments/manifests/`.

```bash
.venv/bin/python scripts/run_evaluation_suite.py
```

6. Run the submission-readiness preflight. This composes submission build,
   generated-submission parity, the quick regression gate, and the experiment
   suite.

```bash
.venv/bin/python scripts/submission_preflight.py
```

The default smoke suite used by `scripts/run_evaluation_suite.py` and
`scripts/submission_preflight.py` is intentionally bounded for local readiness:
each default-suite scenario sets `metadata.episode_steps` to `5`. This keeps the
preflight practical while still exercising local official-environment execution,
generated-submission parity, regression-gate checks, and manifest expansion.
Slower or larger evaluation runs should use explicit manifests or explicitly
edited scenario metadata instead of relying on the default preflight suite.

## Modules And Scripts

- `ow_eval/contracts.py`: immutable result, metric, agent, and match config contracts.
- `ow_eval/agent_loading.py`: local agent loading for modules, Python files, submission files, and built-in baselines.
- `ow_eval/baselines.py`: deterministic built-in local opponents such as `noop` and `nearest_neutral`.
- `ow_eval/official_runner.py`: one local official-environment match runner.
- `ow_eval/artifacts.py`: explicit JSON artifact writing helpers for one match.
- `ow_eval/metrics.py`: extraction of deterministic match metrics from official replay payloads.
- `ow_eval/batch_runner.py`: sequential in-memory batch execution and summaries.
- `ow_eval/parity.py`: modular-agent versus generated-submission parity checks.
- `ow_eval/triage.py`: deterministic failure category classification.
- `ow_eval/scoreboard.py`: persistent JSONL scoreboard records from batch results.
- `ow_eval/regression_gate.py` and `scripts/evaluation_gate.py`: quick local gate for crashes, severe triage categories, parity, and smoke thresholds.
- `ow_eval/analysis_pack.py`: planner-improvement diagnostics from completed local results.
- `ow_eval/experiment_manifest.py`: experiment manifest and promotion threshold contracts.
- `ow_eval/experiment_runner.py`: manifest expansion plus batch execution, scoreboard, and analysis pack composition.
- `ow_eval/promotion_gate.py`: in-memory promotion threshold decision evaluation.
- `ow_eval/experiment_report.py`: local report records and explicit JSON report persistence.
- `ow_eval/experiment_cli.py` and `scripts/run_evaluation_experiment.py`: one-manifest local experiment workflow.
- `ow_eval/experiment_suite.py` and `scripts/run_evaluation_suite.py`: ordered multi-manifest local experiment workflow.
- `ow_eval/submission_preflight.py` and `scripts/submission_preflight.py`: local pre-submission checklist over build, parity, gate, and suite checks.
- `scripts/build_submission.py`: deterministic single-file submission builder.

## Manifest Fixtures

Canonical local smoke manifests live in `experiments/manifests/`:

- `experiments/manifests/quick-2p-smoke.json`
- `experiments/manifests/quick-4p-smoke.json`
- `experiments/manifests/promotion-smoke.json`

These are JSON `ExperimentManifest` records. They use the modular runtime agent
as the candidate and built-in baseline opponents only. They are intended for
local official-environment evaluation and for deterministic pre-submission
checks. The default smoke fixtures are bounded through per-scenario
`metadata.episode_steps`; broader evaluation should be launched explicitly.

## Output And Artifact Policy

Generated submissions, logs, match outputs, reports, scoreboards, replays, and
temporary artifacts should not be committed unless they are explicitly intended
source artifacts. Prefer `/tmp` or another ignored local output directory for
generated files. The harness writes reports or match artifacts only when an
explicit output path, output directory, report path, report directory, or
artifact config is supplied.

Do not commit generated submission files from `scripts/build_submission.py`,
JSON reports from `write_experiment_report(...)`, scoreboard JSONL output,
replay JSON, official match result artifacts, logs, or scratch diagnostics as
part of routine local evaluation.

## Interpreting Results

- Triage categories group failures into parse crashes, planner crashes, action
  conversion crashes, timeout or budget fallback, invalid or no-op-heavy
  behavior, normal losses, clean results, and other failures. Severe categories
  should be investigated before live submission.
- Scoreboards summarize completed counts, wins, losses, error rates, mean rank,
  mean score, and triage category counts for a batch.
- Analysis packs list concrete local match diagnostics that are useful for
  planner-improvement work, especially losses and severe triage cases.
- Experiment reports combine an experiment run, scoreboard record, analysis
  pack, and promotion decision into one local review JSON document.
- Regression gates are quick crash and parity screens. They are not strength
  proof, but they should pass before promotion or live-submission discussion.
- Promotion gates compare a completed experiment run against that manifest's
  `PromotionThresholds`. A failed promotion gate means the candidate did not
  meet the configured local criteria.
- Submission preflight failures identify which readiness check failed:
  submission build, generated-submission parity, quick regression gate, or
  experiment suite. Any failed preflight check should be resolved before asking
  to spend a live Kaggle submission.
