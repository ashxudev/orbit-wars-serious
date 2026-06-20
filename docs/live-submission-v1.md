# Live Submission V1 No-Submit Mechanism Check

This runbook records the final no-submit mechanism check for the later Orbit
Wars V1 live Kaggle submission. It does not authorize or perform a live upload.

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

## Later Live Submit Command

Use this only in the later live-submission cycle after final artifact freeze,
local readiness rerun, and explicit live-submission approval.

```bash
.venv/bin/kaggle competitions submit -c orbit-wars -f /tmp/orbit_wars_v1_submission.py -m "serious-v1 local readiness passed 3641021"
```

Do not commit generated submissions, reports, logs, scoreboards, match outputs,
replays, credentials, or temporary files.
