# Live Submission V2 Runbook

This runbook records the V2 live Kaggle submission mechanism checks and the
exactly-once live upload record.

## Cycle 0 Status

- Cycle: Live Submission V2 Segment Cycle 0.
- Competition slug: `orbit-wars`.
- Checked HEAD: `fd80611 Record V1 deterministic readiness`.
- Kaggle CLI path: `.venv/bin/kaggle`.
- Kaggle CLI version: `Kaggle CLI 2.2.2`.
- Non-upload access check:
  `.venv/bin/kaggle competitions submissions -c orbit-wars` succeeded and
  listed existing `orbit-wars` submissions.
- Credential file check: `~/.kaggle/kaggle.json` is not present, so local
  `username` and `key` fields are not available there.
- Standard environment variable check: `KAGGLE_USERNAME`, `KAGGLE_KEY`, and
  `KAGGLE_API_TOKEN` were not present in the checked shell environment.
- Credential status: despite the missing `kaggle.json` and standard env vars,
  the venv Kaggle CLI is authenticated through existing local Kaggle
  configuration because the non-upload submissions-list command succeeded. No
  token or secret value was printed or inspected.
- Upload status: no `.venv/bin/kaggle competitions submit` command was run.
- Generated artifact status: no V2 upload artifact was built in this cycle.
- Cycle 1 readiness: proceed. The submission mechanism is available for final
  artifact freeze/readiness, after rebuilding a fresh V2 artifact under `/tmp`
  and rerunning local readiness checks.

Latest visible serious submissions from the non-upload list:

| Ref | File | Date | Description | Status | Public score |
|---:|---|---|---|---|---:|
| `53894832` | `orbit_wars_v1_submission.py` | `2026-06-20 22:50:27.763000` | `serious-v1 local readiness passed 4e66048` | `SubmissionStatus.COMPLETE` | `435.8` |
| `53862054` | `orbit_wars_v0_submission.py` | `2026-06-19 22:55:09.443000` | `serious-v0 local preflight passed c558a30` | `SubmissionStatus.COMPLETE` | `373.8` |

## Commands Run

```bash
git log -1 --oneline
git status --short
.venv/bin/kaggle --version
.venv/bin/kaggle competitions submissions -c orbit-wars
git diff --check
```

The first sandboxed `.venv/bin/kaggle --version` attempt could not resolve
`api.kaggle.com` from the restricted sandbox. The same non-upload check and the
submissions-list check were rerun with network permission and succeeded. No
upload command was invoked.

## Later Live Submit Command Template

Do not run this in Cycle 0. For a later exactly-once V2 upload cycle, rebuild a
fresh artifact under `/tmp`, rerun local readiness, and use a message tied to
that segment's checked commit.

```bash
.venv/bin/kaggle competitions submit -c orbit-wars -f /tmp/orbit_wars_v2_submission.py -m "serious-v2 local readiness passed <commit>"
```

Do not commit generated submissions, reports, logs, scoreboards, match outputs,
replays, credentials, or temporary files.

## Cycle 1 Live Upload Record

- Cycle: Live Submission V2 Segment Cycle 1.
- Checked HEAD: `75867e3 Add V2 live submission mechanism check`.
- Competition slug: `orbit-wars`.
- Kaggle CLI path: `.venv/bin/kaggle`.
- Kaggle CLI version: `Kaggle CLI 2.2.2`.
- Pre-submit non-upload Kaggle access:
  `.venv/bin/kaggle competitions submissions -c orbit-wars` succeeded before
  upload.
- Pre-submit focused V1 replay checks:
  `.venv/bin/python -m unittest tests.test_v1_replay_leak_fixtures tests.test_v1_replay_regression`
  passed, `22 tests`.
- Pre-submit full discovery:
  `.venv/bin/python -m unittest discover -s tests` passed, `1328 tests`.
- Pre-submit evaluation gate:
  `gate=PASS matches=2 win_rate=1 mean_rank=1 error_rate=0 parity=pass failures=0`.
- Pre-submit submission preflight:
  `submission_preflight=PASS total=4 passed=4 failed=0 failed_checks=none exit_code=0`.
- Pre-submit V1 replay regression summary:
  `v1_replay_regression cases=10 live_actions=9 live_no_actions=1 unresolved_planner_no_actions=0 reduced_active_owner_caveats=1 owned_pressure=8 own_transfer_spam=3 enemy_denial_safety_blocked=1 four_player_plateau_actions=3 four_player_plateau_no_actions=1 rank_aware_continuations=2 thin_capture_risks=2`.
- Pre-submit `git diff --check`: passed.
- Fresh artifact path: `/tmp/orbit_wars_v2_submission.py`.
- Fresh artifact size: `411942` bytes.
- Fresh artifact SHA256:
  `1cc8143dbb06719c2a2cb858f4630b344746c5478b1a51aed99cd2f44d07a940`.
- Upload command count: exactly one upload command was invoked.
- Secrets status: no credential, token, `kaggle.json`, or secret environment
  variable value was printed or committed.

Exact upload command used:

```bash
.venv/bin/kaggle competitions submit -c orbit-wars -f /tmp/orbit_wars_v2_submission.py -m "serious-v2 deterministic readiness passed 75867e3"
```

Kaggle CLI acceptance output summary:

```text
Successfully submitted to Orbit Wars
```

Post-submit submissions-list evidence:

| Ref | File | Date | Description | Status | Public score |
|---:|---|---|---|---|---:|
| `53925932` | `orbit_wars_v2_submission.py` | `2026-06-21 22:34:06.907000` | `serious-v2 deterministic readiness passed 75867e3` | `SubmissionStatus.COMPLETE` | `600.0` |
| `53894832` | `orbit_wars_v1_submission.py` | `2026-06-20 22:50:27.763000` | `serious-v1 local readiness passed 4e66048` | `SubmissionStatus.COMPLETE` | `410.5` |
| `53862054` | `orbit_wars_v0_submission.py` | `2026-06-19 22:55:09.443000` | `serious-v0 local preflight passed c558a30` | `SubmissionStatus.COMPLETE` | `360.9` |

Reviewer read-only status check before commit observed V2 ref `53925932`
as `SubmissionStatus.COMPLETE` with public score `600.0`.

Segment status: `LIVE_SUBMISSION_V2_SEGMENT_COMPLETE`.
