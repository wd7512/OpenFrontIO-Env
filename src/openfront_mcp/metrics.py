"""Behavioural metrics, ported from CivBench (see docs/paper-summary.md section 4)."""

from __future__ import annotations


def pmr(monitoring_calls: int, non_infra_calls: int) -> float:
    """Proactive monitoring rate: strategic monitoring / non-infrastructure calls."""
    if non_infra_calls <= 0:
        return 0.0
    return monitoring_calls / non_infra_calls


def rag_at_k(met: int, partial: int, total_commitments: int) -> float:
    """Reflection-action gap: (Y + 0.5P) / total commitments over K decision points."""
    if total_commitments <= 0:
        return 0.0
    return (met + 0.5 * partial) / total_commitments
