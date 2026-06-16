# Simulator Workflow

This document defines the coordinator loop for finishing the simulator segment of work.

## Threads

- Planner/reviewer thread: `codex://threads/019ece8c-ea4e-7740-bd9b-a21c4639a4f5`
- Implementer thread: `codex://threads/019ece6e-8e2f-7fb3-a345-75579d4c0231`

## Loop

1. Ask the planner/reviewer thread for the next simulator-cycle goal prompt:

   ```text
   give me the goal prompt for the next cycle

   If there is no remaining simulator-segment work, respond exactly:
   SIMULATOR_SEGMENT_COMPLETE
   ```

2. Wait for the planner/reviewer thread to finish.

3. If the response is `SIMULATOR_SEGMENT_COMPLETE`, stop the loop and report that the simulator segment is complete.

4. Otherwise, send the returned goal prompt to the implementer thread.

5. Wait for the implementer thread to finish.

6. Send the planner/reviewer thread this review request:

   ```text
   review the work from where i sent that prompt onwards. Confirm if it has been done properly.The thread location where the work was done is:

   codex://threads/019ece6e-8e2f-7fb3-a345-75579d4c0231

   and if done properly, do the discrete commit(s)
   ```

7. Wait for the planner/reviewer thread to finish.

8. Continue the loop only if the review stage clearly reports no findings, confirms the cycle was implemented properly, and confirms the work was committed.

## Stop Conditions

Stop and report back in the coordinating chat if any of these happen:

- The planner/reviewer returns `SIMULATOR_SEGMENT_COMPLETE`.
- The implementer thread reports a blocker, failure, or incomplete work.
- The planner/reviewer reports findings, regressions, missing tests, failed validation, ambiguity, or any actual problem.
- The planner/reviewer does not confirm that the work was committed.
- The response is ambiguous enough that continuing could create bad follow-on work.

## Continuation Standard

The expected successful review shape is similar to:

```text
No findings. Cycle X was implemented properly and I committed it.
```

Anything materially weaker than this should be treated as a stop condition unless the user explicitly says to continue.
