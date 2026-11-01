"""Experiment Manifest：稳定序列化、秘密脱敏与 config/result hash。

原则：
- 只包含影响实验结果的配置；秘密值不落明文，用 sha256 指纹代替，既保密又保留敏感性。
- hash 使用 canonical JSON（sort_keys + 无空格），字段顺序不影响结果。
- config hash 不包含运行生命周期字段（status/finished_at/started_at/result_hash/experiment_id）。
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from typing import Any

from ..config import ROOT, Settings
from ..domain.models import (
    AgentSpec,
    BenchmarkTask,
    ExperimentManifest,
    TaskResult,
)
from .protocol import PROTOCOL_VERSION

EVALUATOR_VERSION = "benchmark-scoring-v1"
PROMPT_VERSION = "claim-extract-v1/relation-v1"
SECRET_MARKERS = ("key", "token", "secret", "password", "authorization", "cookie")
UNKNOWN = "unknown"


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )


def stable_hash(value: Any, *, length: int = 32) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:length]


def redact(value: Any) -> Any:
    """递归脱敏：秘密值替换为 sha256 指纹，保留"变化可检测"能力。"""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if any(marker in str(key).lower() for marker in SECRET_MARKERS):
                result[str(key)] = f"sha256:{stable_hash(item, length=16)}"
            else:
                result[str(key)] = redact(item)
        return result
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def code_commit() -> str:
    for env_name in ("GIT_COMMIT", "RENDER_GIT_COMMIT", "GITHUB_SHA"):
        value = os.environ.get(env_name)
        if value:
            return value[:40]
    try:
        output = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if output.returncode == 0 and output.stdout.strip():
            return output.stdout.strip()[:40]
    except (OSError, subprocess.SubprocessError):
        pass
    return UNKNOWN


def dependency_lock_hash() -> str:
    lock = ROOT / "uv.lock"
    if not lock.is_file():
        return UNKNOWN
    return hashlib.sha256(lock.read_bytes()).hexdigest()[:32]


def dataset_hash(tasks: list[BenchmarkTask]) -> str:
    payload = [task.model_dump(mode="json") for task in sorted(tasks, key=lambda item: item.id)]
    return stable_hash(payload)


def config_hash(manifest: ExperimentManifest) -> str:
    payload = manifest.model_dump(mode="json")
    for field in (
        "config_hash",
        "result_hash",
        "started_at",
        "finished_at",
        "status",
        "experiment_id",
    ):
        payload.pop(field, None)
    return stable_hash(payload)


def result_hash(results: list[TaskResult]) -> str:
    payload = []
    for result in sorted(results, key=lambda item: (item.task_id, item.agent_id)):
        payload.append(
            {
                "task_id": result.task_id,
                "agent_id": result.agent_id,
                "answer": result.answer.model_dump(mode="json"),
                "numeric_accuracy": result.numeric_accuracy,
                "freshness_score": result.freshness_score,
                "stale_claim_rate": result.stale_claim_rate,
                "claim_coverage": result.claim_coverage,
                "supported_claim_rate": result.supported_claim_rate,
                "stable_fact_integrity": result.stable_fact_integrity,
                "evidence_quality": result.evidence_quality,
                "score": result.score,
                "error": result.error,
            }
        )
    return stable_hash(payload)


def build_manifest(
    *,
    experiment_id: str,
    dataset_version: str,
    tasks: list[BenchmarkTask],
    agents: list[AgentSpec],
    cfg: Settings,
    snapshot_ids: list[str],
    started_at: str,
    policy_version: str,
    weights_version: str,
    agent_timeout_s: float,
    max_claims: int,
    detect_freshness: bool,
) -> ExperimentManifest:
    provider = cfg.openai_base_url.rstrip("/")
    if "://" in provider:
        provider = provider.split("://", 1)[1]
    provider = provider.split("/", 1)[0]
    agent_payload = [
        redact(
            {
                "id": spec.id,
                "name": spec.name,
                "kind": spec.kind,
                "config": spec.config,
            }
        )
        for spec in sorted(agents, key=lambda item: item.id)
    ]
    return ExperimentManifest(
        experiment_id=experiment_id,
        dataset_id="freshness-bench",
        dataset_version=dataset_version,
        dataset_hash=dataset_hash(tasks),
        task_ids=[task.id for task in tasks],
        agent_manifest=agent_payload,
        model_provider=provider,
        model_name=cfg.llm_model,
        model_version=cfg.llm_model,
        adapter_protocol_version=PROTOCOL_VERSION,
        tool_configuration={
            "search_depth": cfg.search_depth,
            "max_results_per_query": cfg.max_results_per_query,
            "model_credential_fingerprint": (
                f"sha256:{stable_hash(cfg.openai_api_key, length=16)}"
                if cfg.openai_api_key
                else "none"
            ),
        },
        retrieval_configuration={
            "tavily_base_url": cfg.tavily_base_url,
            "allow_keyless": cfg.tavily_allow_keyless,
            "tavily_credential_fingerprint": (
                f"sha256:{stable_hash(cfg.tavily_api_key, length=16)}"
                if cfg.tavily_api_key
                else "none"
            ),
        },
        budget_configuration={
            "max_queries": cfg.max_queries,
            "max_tavily_credits": cfg.max_tavily_credits,
            "max_wall_clock_seconds": cfg.max_wall_clock_seconds,
        },
        timeout_configuration={
            "agent_timeout_s": agent_timeout_s,
            "detector_max_claims": max_claims,
            "detect_freshness": detect_freshness,
        },
        evaluator_version=EVALUATOR_VERSION,
        policy_version=policy_version,
        weights_version=weights_version,
        prompt_version=PROMPT_VERSION,
        code_commit=code_commit(),
        dependency_lock_hash=dependency_lock_hash(),
        snapshot_ids=sorted(snapshot_ids),
        started_at=started_at,
    )


__all__ = [
    "canonical_json",
    "config_hash",
    "dataset_hash",
    "dependency_lock_hash",
    "build_manifest",
    "redact",
    "result_hash",
    "stable_hash",
]



