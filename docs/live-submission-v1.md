# Live Submission V1 No-Submit Mechanism Check

This runbook records the V1 live Kaggle submission mechanism checks, final
artifact freeze, and live upload result.

## Cycle 0 Status

- Cycle: Live Submission V1 Segment Cycle 0.
- Competition slug: `orbit-wars`.
- Checked HEAD: `3641021 Record V1 replay leak readiness`.
- Kaggle CLI path: `.venv/bin/kaggle`.
- Kaggle CLI version: `Kaggle CLI 2.2.2`.
- Non-upload access check:
  `.venv/bin/kaggle competitions submissions -c orbit-wars` succeeded and listed
  existing `orbit-wars` submissions.
- Credential file check: `~/.kaggle/kaggle.json` is not present, so local
  `username` and `key` fields are not available there.
- Credential status: despite the missing `kaggle.json`, the venv Kaggle CLI is
  authenticated through the existing local Kaggle access-token configuration.
  The token value was not printed or inspected.
- Upload status: no `.venv/bin/kaggle competitions submit` command was run.
- Generated artifact status: no V1 upload artifact was built in this cycle.
- Cycle 1 readiness: proceed. The mechanism is available for a later exactly
  once live upload cycle, after rebuilding a fresh final V1 artifact under
  `/tmp` and rerunning the required local readiness checks.

## Cycle 1 Artifact Freeze And Local Readiness

- Cycle: Live Submission V1 Segment Cycle 1.
- Checked HEAD: `519e1a2 Add V1 live submission mechanism check`.
- Fresh artifact path: `/tmp/orbit_wars_v1_submission.py`.
- Fresh artifact size: `316055` bytes.
- Fresh artifact SHA256:
  `b05984e62d14190cf937c0b749862304e4a67a28e822c901fd47a7fbc57cc514`.
- Upload status: no `.venv/bin/kaggle competitions submit` command was run.
- Cycle 2 readiness: proceed. Rebuild and hash the final artifact immediately
  before the live cycle upload, rerun the required readiness checks, then make
  exactly one live Kaggle submission if those checks remain green.

Replay regression:

```text
v0_replay_regression cases=7 live_actions=5 live_no_actions=2 budget_guarded=1 budgetless_actions=7 pressure_actions=4 risky_thin_captures=0 unresolved_planner_no_actions=0
```

Local readiness checks:

```text
.venv/bin/python scripts/evaluation_gate.py
gate=PASS matches=2 win_rate=1 mean_rank=1 error_rate=0 parity=pass failures=0

.venv/bin/python scripts/submission_preflight.py
submission_preflight=PASS total=4 passed=4 failed=0 failed_checks=none exit_code=0
preflight_check=submission_build status=PASS exit_code=0
preflight_check=submission_parity status=PASS mismatches=0 exit_code=0
preflight_check=regression_gate status=PASS failures=0 exit_code=0
preflight_check=experiment_suite status=PASS exit_code=0
```

Bounded smoke benchmarks:

```text
legacy-opponent-smoke 4 0.0 True
competitive-baseline-smoke 6 0.0 True
```

## Cycle 2 Live V1 Submission Result

- Cycle: Live Submission V1 Segment Cycle 2.
- Checked HEAD: `4e66048 Record V1 final artifact readiness`.
- Pre-upload non-upload Kaggle access:
  `.venv/bin/kaggle competitions submissions -c orbit-wars` succeeded.
- Replay regression:
  `v0_replay_regression cases=7 live_actions=5 live_no_actions=2 budget_guarded=1 budgetless_actions=7 pressure_actions=4 risky_thin_captures=0 unresolved_planner_no_actions=0`.
- Evaluation gate:
  `gate=PASS matches=2 win_rate=1 mean_rank=1 error_rate=0 parity=pass failures=0`.
- Submission preflight:
  `submission_preflight=PASS total=4 passed=4 failed=0 failed_checks=none exit_code=0`.
- Fresh artifact path: `/tmp/orbit_wars_v1_submission.py`.
- Fresh artifact size: `316055` bytes.
- Fresh artifact SHA256:
  `b05984e62d14190cf937c0b749862304e4a67a28e822c901fd47a7fbc57cc514`.
- Live upload count for this cycle: exactly one.
- Upload acceptance output: `Successfully submitted to Orbit Wars`.
- Kaggle submission ref: `53894832`.
- Kaggle listed file: `orbit_wars_v1_submission.py`.
- Kaggle listed description: `serious-v1 local readiness passed 4e66048`.
- Kaggle listed date: `2026-06-20 22:50:27.763000`.
- Kaggle listed status immediately after upload: `SubmissionStatus.PENDING`.
- Segment sentinel: `LIVE_SUBMISSION_V1_SEGMENT_COMPLETE`.

Exact live upload command used:

```bash
.venv/bin/kaggle competitions submit -c orbit-wars -f /tmp/orbit_wars_v1_submission.py -m "serious-v1 local readiness passed 4e66048"
```

## Non-Upload Commands Run

```bash
git log -1 --oneline
git status --short
.venv/bin/kaggle --version
.venv/bin/kaggle competitions submissions -c orbit-wars
git diff --check
```

The first sandboxed `.venv/bin/kaggle --version` attempt could not resolve
`api.kaggle.com` from the restricted sandbox. The same non-upload check was
rerun with network permission and succeeded. No upload command was invoked.

## Live Submit Command Template

The Cycle 2 command above has already been used once. Do not rerun it blindly.
For any later segment, rebuild a fresh artifact under `/tmp`, rerun local
readiness, and use a new message tied to that segment's checked commit.

```bash
.venv/bin/kaggle competitions submit -c orbit-wars -f /tmp/orbit_wars_vN_submission.py -m "serious-vN local readiness passed <commit>"
```

Do not commit generated submissions, reports, logs, scoreboards, match outputs,
replays, credentials, or temporary files.
