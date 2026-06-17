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

5. Wait for the implementer thread to finish. Refer to the Polling section for how long to wait between checks.

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

7. Wait for the planner/reviewer thread to finish. Refer to the Polling section for how long to wait between checks.

8. Continue the loop only if the review stage clearly reports no findings, confirms the cycle was implemented properly, and confirms the work was committed.

9. If the review stage is interrupted or ends ambiguously after partial progress, send a narrow recovery prompt asking it to complete only the unfinished review/commit step. Do not start a new cycle until the review stage gives a clear continuation signal.

## Stop Conditions

Stop and report back in the coordinating chat if any of these happen:

- The planner/reviewer returns the configured completion sentinel.
- The implementer thread reports a blocker, failure, or incomplete work.
- The planner/reviewer reports findings, regressions, missing tests, failed validation, ambiguity, or any actual problem.
- The planner/reviewer does not confirm that the work was committed.
- The response is ambiguous enough that continuing could create bad follow-on work.
- A recovery prompt fails to produce a clear continuation signal.

## Continuation Standard

The expected successful review shape is similar to:

```text
No findings. Cycle X was implemented properly and I committed it.
```

Anything materially weaker than this should be treated as a stop condition unless the user explicitly says to continue.

## Polling

Use a 3-minute polling interval when waiting for planner/reviewer or implementer threads unless the user requests a different cadence.
