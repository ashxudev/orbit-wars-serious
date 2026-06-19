"""Deterministic experiment report records and JSON persistence.

Evaluation Harness Cycle 15 combines an existing ``ExperimentRunResult`` and
``PromotionGateDecision`` into a local review record. It does not run matches,
submit to live Kaggle, or orchestrate distributed evaluation.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .analysis_pack import PlannerAnalysisItem, PlannerAnalysisPack
from .contracts import EvaluationStatus
from .experiment_runner import ExperimentRunResult
from .promotion_gate import PromotionGateDecision, PromotionGateFailure
from .scoreboard import ScoreboardRecord
from .triage import FailureCategory


@dataclass(frozen=True, slots=True)
class ExperimentReport:
    """Persistent deterministic report for one local experiment run."""

    manifest_name: str
    manifest_version: str | None
    candidate_agent_name: str
    commit: str | None
    run_summary_text: str
    promotion_summary_text: str
    scoreboard_record: ScoreboardRecord
    analysis_pack: PlannerAnalysisPack
    promotion_decision: PromotionGateDecision
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.manifest_name, "manifest_name")
        if self.manifest_version is not None:
            _validate_nonempty_string(self.manifest_version, "manifest_version")
        _validate_nonempty_string(self.candidate_agent_name, "candidate_agent_name")
        if self.commit is not None:
            _validate_nonempty_string(self.commit, "commit")
        _validate_nonempty_string(self.run_summary_text, "run_summary_text")
        _validate_nonempty_string(
            self.promotion_summary_text,
            "promotion_summary_text",
        )
        if not isinstance(self.scoreboard_record, ScoreboardRecord):
            raise ValueError("scoreboard_record must be a ScoreboardRecord")
        if not isinstance(self.analysis_pack, PlannerAnalysisPack):
            raise ValueError("analysis_pack must be a PlannerAnalysisPack")
        if not isinstance(self.promotion_decision, PromotionGateDecision):
            raise ValueError("promotion_decision must be a PromotionGateDecision")
        _validate_metadata(self.metadata)

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "manifest_name": self.manifest_name,
            "manifest_version": self.manifest_version,
            "candidate_agent_name": self.candidate_agent_name,
            "commit": self.commit,
            "run_summary_text": self.run_summary_text,
            "promotion_summary_text": self.promotion_summary_text,
            "scoreboard_record": _scoreboard_record_to_report_dict(
                self.scoreboard_record
            ),
            "analysis_pack": self.analysis_pack.to_dict(),
            "promotion_decision": self.promotion_decision.to_dict(),
            "metadata": [
                {"key": key, "value": value}
                for key, value in self.metadata
            ],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ExperimentReport:
        """Create an ``ExperimentReport`` from a plain dictionary."""

        if not isinstance(data, Mapping):
            raise ValueError("report must be a mapping")
        scoreboard_data = data.get("scoreboard_record")
        if not isinstance(scoreboard_data, Mapping):
            raise ValueError("scoreboard_record must be a mapping")
        analysis_pack_data = data.get("analysis_pack")
        if not isinstance(analysis_pack_data, Mapping):
            raise ValueError("analysis_pack must be a mapping")
        promotion_decision_data = data.get("promotion_decision")
        if not isinstance(promotion_decision_data, Mapping):
            raise ValueError("promotion_decision must be a mapping")
        return cls(
            manifest_name=_string_or_raise(data.get("manifest_name"), "manifest_name"),
            manifest_version=_optional_string(
                data.get("manifest_version"),
                "manifest_version",
            ),
            candidate_agent_name=_string_or_raise(
                data.get("candidate_agent_name"),
                "candidate_agent_name",
            ),
            commit=_optional_string(data.get("commit"), "commit"),
            run_summary_text=_string_or_raise(
                data.get("run_summary_text"),
                "run_summary_text",
            ),
            promotion_summary_text=_string_or_raise(
                data.get("promotion_summary_text"),
                "promotion_summary_text",
            ),
            scoreboard_record=ScoreboardRecord.from_dict(scoreboard_data),
            analysis_pack=_analysis_pack_from_dict(analysis_pack_data),
            promotion_decision=_promotion_decision_from_dict(promotion_decision_data),
            metadata=_metadata_from_data(data.get("metadata")),
        )


def build_experiment_report(
    run_result: ExperimentRunResult,
    decision: PromotionGateDecision,
) -> ExperimentReport:
    """Build a deterministic local report record from completed run artifacts."""

    if not isinstance(run_result, ExperimentRunResult):
        raise ValueError("run_result must be an ExperimentRunResult")
    if not isinstance(decision, PromotionGateDecision):
        raise ValueError("decision must be a PromotionGateDecision")
    return ExperimentReport(
        manifest_name=run_result.manifest.name,
        manifest_version=run_result.manifest.version,
        candidate_agent_name=run_result.manifest.candidate_agent.name,
        commit=run_result.scoreboard_record.commit,
        run_summary_text=run_result.summary_text,
        promotion_summary_text=decision.summary_text,
        scoreboard_record=run_result.scoreboard_record,
        analysis_pack=run_result.analysis_pack,
        promotion_decision=decision,
        metadata=_metadata_from_data(run_result.manifest.metadata),
    )


def write_experiment_report(
    report: ExperimentReport,
    path: str | Path,
) -> Path:
    """Write ``report`` as deterministic UTF-8 JSON."""

    if not isinstance(report, ExperimentReport):
        raise ValueError("report must be an ExperimentReport")
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_dict(), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def read_experiment_report(path: str | Path) -> ExperimentReport:
    """Read a deterministic JSON experiment report from ``path``."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("report JSON must be an object")
    return ExperimentReport.from_dict(payload)


def _scoreboard_record_to_report_dict(
    record: ScoreboardRecord,
) -> dict[str, object]:
    data = record.to_dict()
    data["completed_matches"] = record.completed_count
    return data


def _analysis_pack_from_dict(data: Mapping[str, object]) -> PlannerAnalysisPack:
    items_data = data.get("items", ())
    if not isinstance(items_data, Sequence) or isinstance(items_data, (str, bytes)):
        raise ValueError("analysis_pack.items must be a sequence")
    items = []
    for index, item_data in enumerate(items_data):
        if not isinstance(item_data, Mapping):
            raise ValueError(f"analysis_pack.items[{index}] must be a mapping")
        items.append(_analysis_item_from_dict(item_data))
    return PlannerAnalysisPack(
        items=tuple(items),
        total_results=_nonnegative_int_or_default(
            data.get("total_results"),
            "analysis_pack.total_results",
            0,
        ),
        included_count=_nonnegative_int_or_default(
            data.get("included_count"),
            "analysis_pack.included_count",
            0,
        ),
        omitted_count=_nonnegative_int_or_default(
            data.get("omitted_count"),
            "analysis_pack.omitted_count",
            0,
        ),
        triage_category_counts=_category_counts_from_data(
            data.get("triage_category_counts"),
        ),
    )


def _analysis_item_from_dict(data: Mapping[str, object]) -> PlannerAnalysisItem:
    return PlannerAnalysisItem(
        batch_index=_nonnegative_int_or_raise(
            data.get("batch_index"),
            "batch_index",
        ),
        label=_optional_string(data.get("label"), "label"),
        seed=_int_or_raise(data.get("seed"), "seed"),
        player_count=_int_or_raise(data.get("player_count"), "player_count"),
        controlled_seat=_int_or_raise(
            data.get("controlled_seat"),
            "controlled_seat",
        ),
        candidate_agent_name=_string_or_raise(
            data.get("candidate_agent_name"),
            "candidate_agent_name",
        ),
        opponent_names=_string_tuple_from_data(
            data.get("opponent_names", ()),
            "opponent_names",
        ),
        status=EvaluationStatus(data.get("status")),
        triage_category=FailureCategory(data.get("triage_category")),
        triage_reason=_string_or_raise(data.get("triage_reason"), "triage_reason"),
        final_rank=_optional_int(data.get("final_rank"), "final_rank"),
        final_score=_optional_float(data.get("final_score"), "final_score"),
        final_planets=_optional_int(data.get("final_planets"), "final_planets"),
        final_ships=_optional_int(data.get("final_ships"), "final_ships"),
        final_production=_optional_int(
            data.get("final_production"),
            "final_production",
        ),
        turns_survived=_optional_int(data.get("turns_survived"), "turns_survived"),
        no_action_count=_optional_int(
            data.get("no_action_count"),
            "no_action_count",
        ),
        invalid_action_count=_optional_int(
            data.get("invalid_action_count"),
            "invalid_action_count",
        ),
        timeout_count=_optional_int(data.get("timeout_count"), "timeout_count"),
        error_count=_optional_int(data.get("error_count"), "error_count"),
        error_text=_optional_string(data.get("error_text"), "error_text"),
        replay_path=_optional_string(data.get("replay_path"), "replay_path"),
        artifact_path=_optional_string(data.get("artifact_path"), "artifact_path"),
        selected_metadata=_metadata_from_data(data.get("selected_metadata")),
        diagnostic_metadata=_metadata_from_data(data.get("diagnostic_metadata")),
    )


def _promotion_decision_from_dict(
    data: Mapping[str, object],
) -> PromotionGateDecision:
    failures_data = data.get("failures", ())
    if not isinstance(failures_data, Sequence) or isinstance(
        failures_data,
        (str, bytes),
    ):
        raise ValueError("promotion_decision.failures must be a sequence")
    failures = []
    for index, failure_data in enumerate(failures_data):
        if not isinstance(failure_data, Mapping):
            raise ValueError(
                f"promotion_decision.failures[{index}] must be a mapping"
            )
        failures.append(_promotion_failure_from_dict(failure_data))
    return PromotionGateDecision(
        passed=_bool_or_raise(data.get("passed"), "promotion_decision.passed"),
        failures=tuple(failures),
        summary_text=_string_or_raise(
            data.get("summary_text"),
            "promotion_decision.summary_text",
        ),
    )


def _promotion_failure_from_dict(
    data: Mapping[str, object],
) -> PromotionGateFailure:
    return PromotionGateFailure(
        code=_string_or_raise(data.get("code"), "promotion failure code"),
        message=_string_or_raise(data.get("message"), "promotion failure message"),
        observed=_optional_number(data.get("observed"), "promotion failure observed"),
        threshold=_number_or_raise(data.get("threshold"), "promotion failure threshold"),
    )


def _metadata_from_data(value: object) -> tuple[tuple[str, str], ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        return tuple(sorted((str(key), str(item)) for key, item in value.items()))
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("metadata must be a mapping or sequence")
    metadata = []
    for index, item in enumerate(value):
        if isinstance(item, Mapping):
            key = item.get("key")
            item_value = item.get("value")
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
            if len(item) != 2:
                raise ValueError(f"metadata[{index}] must have length 2")
            key = item[0]
            item_value = item[1]
        else:
            raise ValueError(f"metadata[{index}] must be a mapping or pair")
        if not isinstance(key, str) or not key:
            raise ValueError("metadata keys must be non-empty strings")
        if not isinstance(item_value, str):
            raise ValueError("metadata values must be strings")
        metadata.append((key, item_value))
    return tuple(sorted(metadata))


def _category_counts_from_data(value: object) -> tuple[tuple[str, int], ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("triage_category_counts must be a sequence")
    counts = []
    for index, item in enumerate(value):
        if isinstance(item, Mapping):
            category = _string_or_raise(
                item.get("category"),
                f"triage_category_counts[{index}].category",
            )
            count = item.get("count")
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
            if len(item) != 2:
                raise ValueError("triage_category_counts entries must have length 2")
            category = _string_or_raise(item[0], "triage category")
            count = item[1]
        else:
            raise ValueError("triage_category_counts entries must be mappings")
        counts.append((category, _nonnegative_int_or_raise(count, "triage count")))
    return tuple(counts)


def _validate_metadata(value: tuple[tuple[str, str], ...]) -> None:
    if not isinstance(value, tuple):
        raise ValueError("metadata must be a tuple")
    for item in value:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError("metadata entries must be key/value tuples")
        _validate_nonempty_string(item[0], "metadata key")
        if not isinstance(item[1], str):
            raise ValueError("metadata values must be strings")


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _string_or_raise(value: object, name: str) -> str:
    _validate_nonempty_string(value, name)
    return value


def _optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    _validate_nonempty_string(value, name)
    return value


def _bool_or_raise(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _int_or_raise(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _nonnegative_int_or_raise(value: object, name: str) -> int:
    int_value = _int_or_raise(value, name)
    if int_value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return int_value


def _nonnegative_int_or_default(value: object, name: str, default: int) -> int:
    if value is None:
        return default
    return _nonnegative_int_or_raise(value, name)


def _optional_int(value: object, name: str) -> int | None:
    if value is None:
        return None
    return _int_or_raise(value, name)


def _number_or_raise(value: object, name: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    return value


def _optional_number(value: object, name: str) -> int | float | None:
    if value is None:
        return None
    return _number_or_raise(value, name)


def _optional_float(value: object, name: str) -> float | None:
    if value is None:
        return None
    return float(_number_or_raise(value, name))


def _string_tuple_from_data(value: object, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    result = tuple(value)
    for item in result:
        _validate_nonempty_string(item, name)
    return result


__all__ = (
    "ExperimentReport",
    "build_experiment_report",
    "read_experiment_report",
    "write_experiment_report",
)
