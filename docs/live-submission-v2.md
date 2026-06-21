# Live Submission V2 No-Submit Mechanism Check

This runbook records the V2 live Kaggle submission mechanism checks. Cycle 0 is
no-submit only: no artifact was built and no upload command was run.

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
