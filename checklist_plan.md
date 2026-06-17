# Orbit Wars Serious Build Checklist

This is the canonical planning ledger for the serious Orbit Wars system build.
This thread maintains this file and does not perform implementation work.

## Coordination Threads

- Planner/reviewer thread: `codex://threads/019ece8c-ea4e-7740-bd9b-a21c4639a4f5`
- Implementation thread: `codex://threads/019ece6e-8e2f-7fb3-a345-75579d4c0231`

## Planning Conventions

- High-level work is grouped into segments.
- Cycle numbering restarts inside each segment.
- Example: the next segment starts at `Planner Cycle 0`, not `Cycle 15`.
- Simulator work is closed unless later planner work exposes a missing mechanical rule.
- This plan should track intended work, completion status, blockers, and next-cycle decisions.

## Current Status

- [x] Simulator segment complete for current planner needs.
- [x] Mission generation segment complete.
- [x] Mission evaluator segment complete.
- [x] Opponent-response segment complete.
- [ ] Commitment-policy segment not started.
- [ ] 2p/4p strategy segment not started.
- [ ] Runtime/submission segment not started.

## Segment 1: Simulator

Status: complete.

Purpose: provide a deterministic, engine-faithful mechanical forward model that planner work can consume.

- [x] Cycle 0: initial simulator skeleton.
- [x] Cycle 1: constants/state/schema groundwork.
- [x] Cycle 2: official observation parsing groundwork.
- [x] Cycle 3: geometry primitives.
- [x] Cycle 4: planet motion/projection.
- [x] Cycle 5: fleet motion/projection.
- [x] Cycle 6: launch arrival and collision forecasting.
- [x] Cycle 7: comet parsing and existing-comet motion.
- [x] Cycle 8: collision/removal facts.
- [x] Cycle 9: combat/event summaries.
- [x] Cycle 10: timeline deltas/events.
- [x] Cycle 11: one-tick next-state construction.
- [x] Cycle 12: idle multi-tick rollout.
- [x] Cycle 13: typed launch insertion what-if API.
- [x] Cycle 14: launch insertion plus rollout composition API.
- [x] Official oracle parity tests added and committed separately.
- [x] Simulator cycle docs moved under `docs/simulator_cycles_md/`.

Implemented simulator capabilities:

- [x] official constants and geometry
- [x] parsed state containers
- [x] planet motion helpers
- [x] fleet motion helpers
- [x] existing comet motion helpers
- [x] collision/removal facts
- [x] combat resolution
- [x] one-tick event summaries and state deltas
- [x] one-tick next-state construction
- [x] idle multi-tick rollout
- [x] typed launch insertion
- [x] launch-plus-rollout composition

Known simulator caveats and intentional deferrals:

- [ ] Future new comet spawning from hidden RNG/seed state.
- [ ] Reward and termination modeling.
- [ ] Kaggle action payload parsing.
- [ ] Branch comparison or candidate search.
- [ ] Planner, mission generation, scoring, or strategy.
- [ ] Submission bundling.

## Segment 2: Planner / Mission Generation

Status: complete.

Purpose: turn simulator facts into plausible action candidates without yet adding heavy scoring or strategy.

### Mission Generation Cycle 0: Planner Package Skeleton And Candidate Types

Status: complete and committed.

- [x] Created separate `ow_planner` package.
- [x] Added typed planner candidate concepts.
- [x] Added deterministic empty `generate_candidates(state, config=None)` boundary.
- [x] Added planner candidate tests.
- [x] Kept simulator modules unchanged.
- [x] Commit: `b2ad9e7 Add planner candidate skeleton`.

### Mission Generation Cycle 1: Legal Launch Action Conversion

Status: complete and committed.

- [x] Added planner-layer action adapter.
- [x] Converted typed `LaunchCandidate` / `MissionCandidate` values to simulator `LaunchOrder` values.
- [x] Converted typed candidates to Kaggle-compatible action rows.
- [x] Added strict validation for source ownership, ship count, angle, and cumulative same-source overspend.
- [x] Preserved launch ordering.
- [x] Added planner action tests.
- [x] Kept simulator modules unchanged.
- [x] Commit: `1d7f2be Add planner launch action conversion`.

### Mission Generation Cycle 2: Board Feature Extraction

Status: complete and committed.

- [x] Added `ow_planner/features.py`.
- [x] Exported feature API from `ow_planner/__init__.py`.
- [x] Resolved effective player id from explicit argument, then `state.player_id`.
- [x] Partitioned own, neutral, and enemy planets.
- [x] Partitioned own and enemy fleets.
- [x] Built planet and fleet lookups.
- [x] Computed ship totals for planets and fleets.
- [x] Computed production totals by category and owner.
- [x] Computed deterministic source-target distances using `ow_sim.geometry.distance`.
- [x] Computed nearest neutral target per owned source.
- [x] Computed nearest enemy target per owned source.
- [x] Preserved factual target metadata such as production, ships, owner, distance, and comet/static flags.
- [x] Kept outputs immutable or safely side-effect-free.
- [x] Added focused feature extraction tests.
- [x] Did not generate missions, estimate ships, call simulator rollouts, score, rank, or select actions.
- [x] Kept simulator mechanics unchanged.
- [x] Commit: `09d4c79 Add planner board feature extraction`.

### Mission Generation Cycle 3: Source-Target Pair Enumeration

Status: complete and committed.

- [x] Added deterministic source-target pair enumeration.
- [x] Enumerated owned sources against neutral and enemy targets.
- [x] Preserved factual pair data without scoring or ranking.
- [x] Added planner enumeration tests.
- [x] Kept simulator mechanics unchanged.
- [x] Commit: `b3106af Add planner source target enumeration`.

### Mission Generation Cycle 4: Required Ship Estimation

Status: complete and committed.

- [x] Added first-pass ship estimation for neutral captures and enemy attacks.
- [x] Produced affordable launch candidates when source ships were sufficient.
- [x] Preserved deterministic tuple/value-object style.
- [x] Added planner estimation tests.
- [x] Kept scoring, ranking, and simulator rollouts out of the cycle.
- [x] Commit: `0b62ec4 Add planner ship estimation`.

### Mission Generation Cycle 5: Simulator-Validated Candidate Outcomes

Status: complete and committed.

- [x] Added `ow_planner/outcomes.py`.
- [x] Converted affordable estimated pairs through the planner action conversion boundary.
- [x] Ran candidate launches through `simulate_launch_orders(...)`.
- [x] Returned factual source/target after-rollout outcome reports.
- [x] Represented no-launch and simulation-failure cases without crashing.
- [x] Added planner outcome tests.
- [x] Kept scoring, ranking, comparison, and selection out of the cycle.
- [x] Commit: `4e51e53 Add planner candidate outcome validation`.

### Mission Generation Cycle 6: Mission Generator API And Candidate Limits

Status: complete and committed.

- [x] Replaced placeholder `generate_candidates(...)` with a first real deterministic generator.
- [x] Composed source-target enumeration, ship estimation, and simulator-backed outcome validation.
- [x] Returned validated `MissionCandidate` values for affordable neutral/enemy opportunities.
- [x] Mapped neutral captures to `MissionType.CAPTURE_NEUTRAL`.
- [x] Mapped enemy attacks to `MissionType.ATTACK_ENEMY`.
- [x] Added `CandidateGenerationConfig.max_candidates`.
- [x] Applied candidate limits after validation in deterministic order.
- [x] Added generation tests.
- [x] Kept scoring, ranking, opponent modeling, strategy, runtime behavior, and bundling out of the segment.
- [x] Commit: `6cace97 Add bounded planner candidate generation`.

### Mission Generation Segment Deferrals

- [ ] Own-planet defense/reinforcement candidate generation.
- [ ] Evacuation/doomed-source candidate generation.
- [ ] Coordinated multi-source candidate shape.
- [ ] Late-game liquidation candidate shape.
- [ ] More aggressive deterministic pruning for runtime control.
- [ ] Strategic scoring, ranking, and selection.

## Segment 3: Mission Evaluator

Status: complete.

Purpose: score candidate missions by comparing future board value with and without the mission.

### Mission Evaluation Cycle 0: Evaluation Types And API Boundary

Status: complete and committed.

- [x] Added planner-layer evaluation contracts.
- [x] Added immutable `MissionEvaluationStatus`, `EvaluationConfig`, `ScoreComponent`, `MissionEvaluationFacts`, and `MissionEvaluation` types.
- [x] Added placeholder `evaluate_candidates(...)` API.
- [x] Wrapped input candidates as `UNEVALUATED` structural records in input order.
- [x] Preserved immutable tuple/value-object style.
- [x] Added focused planner evaluation tests.
- [x] Avoided mission fact extraction, baseline rollout, candidate rollout, scoring, ranking, pruning, and action selection.
- [x] Commit: `7f81926 Add planner evaluation contracts`.

### Mission Evaluation Cycle 1: Candidate Fact Extraction

Status: complete and committed.

- [x] Added deterministic candidate fact extraction for evaluation.
- [x] Kept evaluation structural and factual.
- [x] Avoided scoring, ranking, pruning, and action selection.
- [x] Commit: `178f4b1 Add planner candidate fact extraction`.

### Mission Evaluation Cycle 2: State Lookup Facts

Status: complete and committed.

- [x] Added state lookup facts needed by later evaluation.
- [x] Preserved missing-planet handling as factual data rather than policy.
- [x] Avoided scoring, ranking, pruning, and action selection.
- [x] Commit: `e226657 Add planner state lookup facts`.

### Mission Evaluation Cycle 3: Baseline Future Facts

Status: complete and committed.

- [x] Added idle-baseline future facts for candidate evaluation.
- [x] Established baseline comparison inputs for later cycles.
- [x] Avoided scoring, ranking, pruning, and action selection.
- [x] Commit: `6f6bc34 Add planner baseline future facts`.

### Mission Evaluation Cycle 4: Candidate Future Facts

Status: complete and committed.

- [x] Added mission-future facts for evaluated candidates.
- [x] Captured target/source before-state, idle-baseline, and mission-future fact snapshots.
- [x] Preserved missing planet IDs and mission simulation error facts.
- [x] Avoided scoring, ranking, pruning, and action selection.
- [x] Commit: `ee5deeb Add planner candidate future facts`.

### Mission Evaluation Cycle 5: Mission-Vs-Baseline Delta Facts

Status: complete and committed.

- [x] Added deterministic mission-vs-baseline comparison facts.
- [x] Added planet-level and mission-level future delta dataclasses.
- [x] Compared mission future against idle baseline as the primary mission effect.
- [x] Preserved before-state deltas where useful for source vulnerability.
- [x] Attached delta facts to `MissionEvaluationFacts`.
- [x] Exported delta fact helper(s).
- [x] Handled missing before/baseline/mission facts with safe `None` deltas.
- [x] Preserved mission simulation errors without reinterpretation.
- [x] Avoided scoring, ranking, pruning, opponent modeling, strategy, runtime, and bundling.
- [x] Commit: `79ef5c8 Add planner mission delta facts`.

### Mission Evaluation Cycle 6: Mission Value Facts

Status: complete and committed.

- [x] Added deterministic mission value facts.
- [x] Derived factual value inputs from existing evaluation facts and deltas.
- [x] Kept value extraction separate from scoring weights and selection policy.
- [x] Avoided ranking, pruning, opponent modeling, strategy, runtime, and bundling.
- [x] Commit: `14f5bbc Add planner mission value facts`.

### Mission Evaluation Cycle 7: Mission Scoring Policy

Status: complete and committed.

- [x] Added first-pass mission scoring policy.
- [x] Added scoring configuration and score component handling.
- [x] Kept scoring deterministic and planner-layer only.
- [x] Avoided ranking, pruning, opponent modeling, strategy, runtime, and bundling.
- [x] Commit: `275fe86 Add planner mission scoring policy`.

### Mission Evaluation Cycle 8: Evaluated Scoring Pipeline

Status: complete and committed.

- [x] Added pipeline composition for evaluating and scoring candidates.
- [x] Integrated evaluation facts with scoring components.
- [x] Preserved input order and immutable output behavior.
- [x] Avoided ranking, pruning, selection, opponent modeling, strategy, runtime, and bundling.
- [x] Commit: `fe39552 Add planner evaluated scoring pipeline`.

### Mission Evaluation Cycle 9: Mission Timing Facts

Status: complete and committed.

- [x] Added deterministic mission timing facts.
- [x] Exposed timing facts for later scoring without recomputing geometry in scoring.
- [x] Kept timing factual and separate from scoring policy.
- [x] Avoided ranking, pruning, selection, opponent modeling, strategy, runtime, and bundling.
- [x] Commit: `664cbc9 Add planner mission timing facts`.

### Mission Evaluation Cycle 10: Timing-Aware Scoring Components

Status: complete and committed.

- [x] Added first-pass scoring support for `MissionTimingFacts`.
- [x] Added timing scoring helper.
- [x] Added timing scoring config fields.
- [x] Kept `score_mission_value_facts(...)` backward-compatible and value-only.
- [x] Updated `score_evaluations(...)` to append timing components after value components.
- [x] Used deterministic timing facts rather than recomputing geometry in scoring.
- [x] Avoided ranking, sorting, pruning, selection, opponent modeling, strategy, runtime, and bundling.
- [x] Commit: `67eb079 Add planner timing-aware scoring`.

### Mission Evaluation Cycle 11: Capture Outcome Scoring

Status: complete and committed.

- [x] Added first-pass capture/retain/loss outcome scoring.
- [x] Kept outcome scoring isolated from value and timing scoring.
- [x] Composed outcome components into evaluated scoring.
- [x] Avoided ranking, sorting, pruning, selection, opponent modeling, strategy, runtime, and bundling.
- [x] Commit: `d2ebcf1 Add planner capture outcome scoring`.

### Mission Evaluation Cycle 12: Source-Drain Opportunity-Cost Scoring

Status: complete and committed.

- [x] Added source-drain opportunity-cost scoring.
- [x] Added source drain fraction and depleted source count components.
- [x] Added incomplete source opportunity penalty.
- [x] Composed source opportunity components after value, timing, and outcome components.
- [x] Kept deeper source danger and enemy punishment deferred to Opponent Response.
- [x] Avoided ranking, sorting, pruning, selection, opponent modeling, strategy, runtime, and bundling.
- [x] Commit: `3c3e792 Add planner source opportunity scoring`.

### Mission Evaluation Cycle 13: Scoring Sanity Scenarios And Assumptions Documentation

Status: complete and committed.

- [x] Added obvious good/bad scoring scenario tests.
- [x] Added one end-to-end `evaluate_and_score_candidates(...)` sanity comparison.
- [x] Documented current score component families.
- [x] Documented assumptions and blind spots.
- [x] Kept tests as score comparisons without adding ranking or selection APIs.
- [x] Avoided opponent modeling, strategy, runtime, and bundling.
- [x] Commit: `08cb1d2 Add planner scoring sanity docs`.

### Mission Evaluation Segment Deferrals

- [ ] Opponent reinforcement modeling.
- [ ] Neutral race/tie modeling.
- [ ] Enemy counterattack/source-threat modeling.
- [ ] Four-player rank/swing modeling.
- [ ] Runtime candidate pruning/selection policy.
- [ ] Autoresearch/tuning loop for first-pass weights.

## Segment 4: Opponent Response Model

Status: complete.

Purpose: estimate punishment, defense, races, and third-party effects.

### Opponent Response Model Cycle 0: API Boundary

Status: complete and committed.

- [x] Defined the stable opponent-response model package/API boundary.
- [x] Kept the first cycle structural and deterministic.
- [x] Avoided strategic response scoring.
- [x] Preserved separation from mission evaluation scoring, commitment policy, 2p/4p strategy, runtime, and bundling.
- [x] Commit: `e54d108 Add planner response model boundary`.

### Opponent Response Model Cycle 1: Target Reinforcement Response Facts

Status: complete and committed.

- [x] Added deterministic target reinforcement response facts.
- [x] Exposed whether opponents can reinforce the target before/around mission arrival.
- [x] Kept facts conservative and non-scoring.
- [x] Avoided ranking, pruning, selection, strategy, runtime, and bundling.
- [x] Commit: `ea8c092 Add planner reinforcement response facts`.

### Opponent Response Model Cycle 2: Target Race Response Facts

Status: complete and committed.

- [x] Added deterministic target race response facts.
- [x] Exposed neutral/enemy race-risk facts without deciding mission quality.
- [x] Kept response facts separate from scoring and policy.
- [x] Avoided ranking, pruning, selection, strategy, runtime, and bundling.
- [x] Commit: `0898870 Add planner target race response facts`.

### Opponent Response Model Cycle 3: Source Counterattack Response Facts

Status: complete and committed.

- [x] Added deterministic source counterattack response facts.
- [x] Exposed whether drained sources are vulnerable to enemy counterattack facts.
- [x] Kept deeper source danger as factual response data, not strategy.
- [x] Avoided ranking, pruning, selection, strategy, runtime, and bundling.
- [x] Commit: `7b5900b Add planner source counterattack response facts`.

### Opponent Response Model Cycle 4: FFA Third-Party Benefit Facts

Status: complete and committed.

- [x] Added deterministic FFA third-party benefit facts.
- [x] Added `ThirdPartyOwnerFacts` and `ThirdPartyBenefitFacts`.
- [x] Attached third-party facts to `MissionResponseFacts`.
- [x] Exposed `third_party_benefit_facts(...)`.
- [x] Summarized unaffected non-player owners in four-player/free-for-all settings.
- [x] Treated two-player/no-third-party cases conservatively.
- [x] Kept the FFA model factual and conservative.
- [x] Avoided response scoring, ranking, pruning, selection, strategy, runtime, and bundling.
- [x] Commit: `6ef77f4 Add planner third-party response facts`.

### Opponent Response Model Cycle 5: Response Summary Labels

Status: complete and committed.

- [x] Added deterministic response summary labels.
- [x] Added `ResponseSummaryFacts`.
- [x] Populated `MissionResponseFacts.response_labels` from summary labels.
- [x] Kept labels factual and stable.
- [x] Avoided response scoring, ranking, pruning, selection, strategy, runtime, and bundling.
- [x] Commit: `2ad4648 Add planner response summary labels`.

### Opponent Response Model Cycle 6: Responding Source Pressure Facts

Status: complete and committed.

- [x] Added deterministic pinned/threatened responding-source facts.
- [x] Added `RespondingSourcePressureFacts` and `ResponseSourcePressureFacts`.
- [x] Attached source pressure facts to `MissionResponseFacts`.
- [x] Kept source pressure factual and separate from classification.
- [x] Avoided response scoring, ranking, pruning, selection, strategy, runtime, and bundling.
- [x] Commit: `603569f Add planner response source pressure facts`.

### Opponent Response Model Cycle 7: Response Classification Labels

Status: complete and committed.

- [x] Added isolated first-pass response classification labels.
- [x] Added `ResponseClassificationFacts` and `classify_response_facts(...)`.
- [x] Kept classification separate from deterministic response fact extraction.
- [x] Covered undefendable, defendable-profitable, donation, race-risk, and source-drain bait labels.
- [x] Avoided ranking, pruning, selection, commitment policy, strategy, runtime, and bundling.
- [x] Commit: `bfa50c3 Add planner response classification labels`.

### Opponent Response Model Segment Deferrals

- [ ] Tune first-pass classification rules through evaluation/autoresearch.
- [ ] Integrate response classifications into downstream commitment and strategy policy.

## Segment 5: Commitment Policy

Status: not started.

Purpose: choose ship sizing as an evaluated decision rather than a fixed rule.

- [ ] Generate minimum-capture sizing.
- [ ] Generate capture-and-hold sizing.
- [ ] Generate reserve-preserving sizing.
- [ ] Generate full-source attack sizing.
- [ ] Generate coordinated multi-source sizing.
- [ ] Include no-attack as an explicit option.
- [ ] Add tests showing full-send is available when profitable but not globally forced.

## Segment 6: 2p / 4p Strategy Modes

Status: not started.

Purpose: separate direct duel optimization from rank-aware free-for-all play.

### Two-Player Mode

- [ ] Maximize advantage over single opponent.
- [ ] Prioritize production denial.
- [ ] Favor direct tactical exchanges when profitable.
- [ ] Add 2p fixture/scenario tests.

### Four-Player Mode

- [ ] Maximize final rank, not just raw board value.
- [ ] Avoid becoming exposed leader too early.
- [ ] Attack current leader when profitable.
- [ ] Preserve survival paths while behind.
- [ ] Exploit late rank-swing opportunities.
- [ ] Add 4p fixture/scenario tests.

## Segment 7: Runtime / Submission

Status: not started.

Purpose: convert planner components into a reliable Kaggle agent with strict runtime control.

- [ ] Build per-turn runtime budget.
- [ ] Add cheap candidate prefilter.
- [ ] Fully evaluate only top candidates.
- [ ] Greedily commit compatible missions.
- [ ] Add low-time fallback behavior.
- [ ] Add deterministic smoke-run script for an agent turn.
- [ ] Add local evaluation harness.
- [ ] Add submission bundler only after a real agent imports `ow_sim`.

### Packaging / Bundling Later

- [ ] Create `scripts/build_submission.py`.
- [ ] Input: agent entrypoint, likely `agents/submission_agent.py`.
- [ ] Output: Kaggle-ready single-file `submission.py`.
- [ ] Inline only required runtime modules.
- [ ] Exclude tests, docs, oracle tooling, and development-only scripts.
- [ ] Rewrite/remove package imports cleanly.
- [ ] Run syntax/import smoke check on generated file.
- [ ] Run behavior parity check between package version and bundled version on a fixture.

## Open Questions

- [x] Planner package boundary chosen: `ow_planner`.
- [x] Initial candidate types implemented for neutral captures and enemy attacks.
- [ ] What horizon should candidate simulation use initially?
- [ ] What is the first local benchmark/evaluation standard before Kaggle submission?

## Update Log

- 2026-06-17: Created canonical checklist plan. Recorded simulator complete, next segment as Planner Cycle 0, and segment-local cycle numbering.
- 2026-06-17: Updated mission-generation status from thread poll. Mission Generation Cycle 0 and Cycle 1 are complete and committed; Cycle 2 board feature extraction is in progress.
- 2026-06-17: Poll confirmed `MISSION_GENERATION_SEGMENT_COMPLETE`. Marked Mission Generation Cycles 0-6 complete and set Mission Evaluation as the next segment.
- 2026-06-17: Poll found Mission Evaluation Cycle 0 complete and committed as `7f81926 Add planner evaluation contracts`.
- 2026-06-17: Poll found Mission Evaluation Cycles 1-4 complete and committed. Mission Evaluation Cycle 5 delta facts is in progress.
- 2026-06-17: Poll found Mission Evaluation Cycles 5-9 complete and committed. Mission Evaluation Cycle 10 timing-aware scoring is in progress.
- 2026-06-17: Poll found Mission Evaluation Cycles 10-13 complete and committed. Planner confirmed `MISSION_EVALUATION_SEGMENT_COMPLETE`; Opponent Response is next.
- 2026-06-17: Poll found planner/reviewer actively preparing Opponent Response Model Cycle 0 as the API boundary cycle.
- 2026-06-17: Poll found Opponent Response Cycles 0-3 complete and committed. Cycle 4 FFA third-party benefit facts is implemented in the implementation thread and pending review/commit.
