# Segment Workflow

This document defines a reusable coordinator loop for completing one project segment through separate planner/reviewer and implementer threads.

## Configure Per Segment

Before running the loop, set these values:

- Segment name: the workstream being completed, such as `simulator`, `planner`, `evaluator`, or `submission`.
- Completion sentinel: an exact all-caps token for the planner/reviewer to return when the segment is complete, such as `SIMULATOR_SEGMENT_COMPLETE`.
- Planner/reviewer thread: the thread that decides the next cycle, reviews implementation work, and commits clean cycles.
- Implementer thread: the thread that implements one returned goal prompt at a time.
- Out-of-scope paths: any unrelated local files or directories that must not be included in segment commits.

Current configured threads:

- Planner/reviewer thread: `codex://threads/019ece8c-ea4e-7740-bd9b-a21c4639a4f5`
- Implementer thread: `codex://threads/019ece6e-8e2f-7fb3-a345-75579d4c0231`

## Loop

1. Ask the planner/reviewer thread for the next segment-cycle goal prompt:

   ```text
   give me the goal prompt for the next cycle

   If there is no remaining <segment-name> segment work, respond exactly:
   <COMPLETION_SENTINEL>
   ```

2. Wait for the planner/reviewer thread to finish.

3. If the response is exactly `<COMPLETION_SENTINEL>`, stop the loop and report that the segment is complete.

4. Otherwise, send the returned goal prompt to the implementer thread.

5. Wait for the implementer thread to finish. Refer to the Heartbeat Waiting section for how to schedule wakeups and choose the interval.

6. Send the planner/reviewer thread this review request:

   ```text
   review the work from where i sent that prompt onwards. Confirm if it has been done properly.The thread location where the work was done is:

   <IMPLEMENTER_THREAD_URL>

   and if done properly, do the discrete commit(s)
   ```

   If there are out-of-scope paths, append a note like:

   ```text
   Note: `<path>` is unrelated to this segment. Do not include it in the segment commit; only commit the intended implementation/test/doc files if the review is clean.
   ```

7. Wait for the planner/reviewer thread to finish. Refer to the Heartbeat Waiting section for how to schedule wakeups and choose the interval.

8. If the review stage clearly reports no findings, confirms the cycle was implemented properly, and confirms the work was committed, continue the loop.

9. If the implementer or planner/reviewer reports a blocker, failure, regression, missing test, failed validation, ambiguity, or other actual problem, classify it using the Blocker Fix Subloop section before deciding whether to stop.

10. Before asking the planner/reviewer for the next goal prompt, run the OpenUsage budget check. Follow the OpenUsage Budget Check section exactly.

11. If the OpenUsage budget check says to continue, return to step 1.

12. If the review stage is interrupted or ends ambiguously after partial progress, send a narrow recovery prompt asking it to complete only the unfinished review/commit step. Do not start a new cycle until the review stage gives a clear continuation signal.

## Blocker Fix Subloop

Most blockers should be handled inside the loop rather than stopping for the user. Treat the planner/reviewer as the source of truth for diagnosing the blocker and defining the next narrow fix.

Use this subloop when the blocker appears technical, local, or reviewable without user judgment, such as:

- Failing tests, failed full discovery, failed gate, failed preflight, lint or diff-check failures.
- Generated-submission parity failures, test-order contamination, flakiness with a reproducible command, or other harness issues.
- A reviewer finding that identifies a concrete code/test defect.
- An implementer blocker that can be investigated from repository state, logs, traces, fixtures, or test output.
- A minor scope mismatch where planner/reviewer can define a correction without changing segment priorities.

For these normal blockers:

1. Ask the planner/reviewer thread for a detailed fix plan:

   ```text
   make a detailed plan for fixing this blocker

   Context:
   - <briefly summarize the failed cycle/review>
   - <include failing command, test name, file/line, or reviewer finding>
   - <include implementer thread URL if relevant>

   Please explain why this likely happened and produce an implementer-ready fix plan/prompt. Do not commit anything.
   ```

2. Wait for the planner/reviewer thread to return the diagnosis and implementer-ready fix plan. Refer to the Heartbeat Waiting section for how to schedule wakeups and choose the interval.

3. Pass the returned fix plan to the implementer thread. Make clear that it continues from the current dirty cycle state and must not commit.

4. Wait for the implementer thread to finish the fix. Refer to the Heartbeat Waiting section for how to schedule wakeups and choose the interval.

5. Send the planner/reviewer thread a review request for the original cycle plus the blocker fix. Ask it to commit only if the combined cycle is now correct.

6. If the planner/reviewer confirms no findings and commits, run the OpenUsage budget check and continue the main loop.

7. If the planner/reviewer finds another technical blocker, repeat this subloop unless the blocker meets the User-Guidance Stop Conditions below.

Keep each fix plan scoped to the current cycle. Do not ask the planner/reviewer for the next segment-cycle goal until the current cycle is reviewed and committed.

## User-Guidance Stop Conditions

Stop and ask the user instead of entering or repeating the Blocker Fix Subloop when the blocker needs human guidance or external state, such as:

- Product/strategy/scope decisions where multiple valid directions exist.
- Credentials, account access, Kaggle/live submission authorization, billing, secrets, or other user-owned external systems.
- A request to change segment priorities, skip planned work, accept a known regression, or weaken acceptance criteria.
- A destructive action, broad revert, or cleanup of unrelated dirty files.
- Missing data or artifacts that only the user can provide.
- A repeated blocker where planner/reviewer and implementer have already attempted the same fix pattern twice and the next step is no longer clear.
- Any ambiguity where continuing could commit unrelated work or change behavior outside the segment scope.

## OpenUsage Budget Check

After each completed work cycle, before asking the planner/reviewer for the next goal prompt, check OpenUsage if the local HTTP API is available.

The coordinator has permission to run this local OpenUsage check outside the sandbox when sandbox networking blocks `127.0.0.1:6736`. This permission is limited to the local OpenUsage endpoint at `http://127.0.0.1:6736/v1/usage/codex`.

Do not print or inspect the raw OpenUsage payload. Only run this bundled-Node command and use its compact JSON output. The command checks only the local OpenUsage endpoint and formats only the compact fields:

```bash
/Applications/Codex.app/Contents/Resources/cua_node/bin/node --input-type=module -e 'fetch("http://127.0.0.1:6736/v1/usage/codex",{signal:AbortSignal.timeout(2000)}).then(r=>{if(!r.ok)throw new Error(String(r.status));return r.json()}).then(p=>{const pick=label=>{const l=(p.lines||[]).find(x=>x.type==="progress"&&x.label===label);return l?{used:l.used,limit:l.limit,remainingPct:l.limit-l.used,resetsAt:l.resetsAt}:null};console.log(JSON.stringify({openusage:"ok",providerId:p.providerId,session:pick("Session"),weekly:pick("Weekly")}))}).catch(()=>console.log(JSON.stringify({openusage:"unavailable"})))'
```

Run this command outside the sandbox with permission escalation for the local HTTP call, relying on the user's execpolicy allow rule for the bundled Node prefix so the loop is not stopped by an approval prompt. The command must only target `http://127.0.0.1:6736/v1/usage/codex`, must use a short timeout, and must still reduce the response to the compact JSON shape above before printing.

Interpret the compact output as follows:

- If `openusage` is `"unavailable"`, continue normally.
- If `weekly.remainingPct <= 3`, pause at the next sensible cycle boundary and create a one-time automation to continue the loop at `weekly.resetsAt + 5 minutes`. Do not ask the planner/reviewer for the next goal before pausing.
- Otherwise, if `session.remainingPct <= 5`, pause immediately before asking the planner/reviewer for the next goal and create a one-time automation to continue the loop at `session.resetsAt + 5 minutes`.
- If both thresholds are crossed, weekly takes priority because the session reset will not restore enough useful budget.
- If the relevant `resetsAt` is missing or invalid, stop and ask the user what delay to use rather than guessing.

Use the app automation tool when creating the one-time continuation automation. The reminder should send a message into the coordinating chat saying:

```text
continue running the loop
```

## Stop Conditions

Stop and report back in the coordinating chat if any of these happen:

- The planner/reviewer returns the configured completion sentinel.
- The blocker meets one of the User-Guidance Stop Conditions.
- The planner/reviewer does not confirm that the work was committed after review and any applicable blocker-fix subloop has completed.
- The response is ambiguous enough that continuing could create bad follow-on work and planner/reviewer cannot turn it into a narrow fix plan.
- A recovery prompt fails to produce a clear continuation signal.

## Continuation Standard

The expected successful review shape is similar to:

```text
No findings. Cycle X was implemented properly and I committed it.
```

Anything materially weaker than this should first be classified under the Blocker Fix Subloop. Stop only if it meets the User-Guidance Stop Conditions, a recovery prompt fails, or planner/reviewer cannot produce a narrow fix plan.

## Heartbeat Waiting

Use heartbeat automations instead of active polling by default. After sending work to the planner/reviewer or implementer thread, create a heartbeat automation for the coordinating chat that wakes it up to inspect the relevant thread and continue the loop.

The heartbeat prompt should be specific about the pending state, for example:

```text
continue running the loop: check whether the implementer thread has finished Cycle X, then decide the next workflow step
```

When a heartbeat fires:

1. Read only the latest relevant turns from the pending thread.
2. If the thread is still running or clearly unfinished, create the next heartbeat and wait again.
3. If the thread is done, blocked, or ambiguous, follow the Loop and Stop Conditions sections.
4. Avoid deep thread reads unless the latest status is unclear or a review/commit decision requires more context.

Default heartbeat interval policy, rounded to practical whole-minute values at roughly 70% of the prior polling guidance:

- Use 4 minutes for normal implementer work, since implementation cycles often finish in 3-7 minutes.
- Use 3 minutes for normal planner/reviewer reviews, since reviews often finish in 3-5 minutes.
- Use 2 minutes only for very small expected actions, such as asking planner for the next goal prompt or checking a short review that should already be near completion.
- Use 11 minutes for test-heavy or evaluation-heavy implementation cycles.
- Use 14 minutes for known long validation paths, such as full preflight, full evaluation suites, or full test discovery.
- If the user requests a specific interval, use the user-requested interval.

Prefer a longer interval when uncertain. The goal is to keep the loop moving without spending tokens on frequent no-op checks.
