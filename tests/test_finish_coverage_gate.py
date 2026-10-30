"""finish_scan confronts the root agent with the coverage the runtime can see."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from agents.tool_context import ToolContext

from lamia.core.agents import AgentCoordinator
from lamia.tools.coverage.tools import _record_impl, hydrate_coverage_from_disk
from lamia.tools.finish.tool import _coverage_summary, finish_scan


if TYPE_CHECKING:
    from pathlib import Path


_GRAPH = {
    "statuses": {"agent-1": "completed"},
    "names": {"agent-1": "injection-tester"},
    "metadata": {"agent-1": {"skills": ["sql_injection", "xss"]}},
}


@pytest.fixture(autouse=True)
def _empty_ledger(tmp_path: Path) -> None:
    hydrate_coverage_from_disk(tmp_path)


def _record(risk_area: str) -> None:
    _record_impl(
        surface="POST /api/orders/{id}",
        risk_area=risk_area,
        outcome="no_issue_found",
        evidence="Parameters fuzzed; no anomalies.",
        agent_id="agent-1",
        agent_name="injection-tester",
    )


def test_unrecorded_risk_class_is_reported_back_to_the_root_agent() -> None:
    _record("SQL injection")

    summary = _coverage_summary(_GRAPH)

    assert summary["coverage_recorded"] == 1
    assert len(summary["coverage_gaps"]) == 1
    assert "xss" in summary["coverage_gaps"][0]
    assert "unexamined" in summary["coverage_gap_warning"]


def test_fully_accounted_coverage_raises_no_gap_warning() -> None:
    _record("SQL injection")
    _record("cross-site scripting")

    summary = _coverage_summary(_GRAPH)

    assert "coverage_gaps" not in summary
    assert "coverage_gap_warning" not in summary


def test_an_empty_ledger_still_warns_first() -> None:
    summary = _coverage_summary(_GRAPH)

    assert summary["coverage_recorded"] == 0
    assert "No coverage was recorded" in summary["coverage_warning"]


class _Run:
    def __init__(self, mode: str) -> None:
        self.scan_config = {"scan_mode": mode}
        self.run_record = {"scan_mode": mode}
        self.vulnerability_reports: list[dict[str, Any]] = []
        self.saved: dict[str, str] = {}

    def update_scan_final_fields(self, **kwargs: str) -> None:
        self.saved = kwargs


async def _finish(
    mode: str, *, accept_unexamined: bool, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, Any], _Run]:
    coordinator = AgentCoordinator()
    await coordinator.register("root", "strix", parent_id=None)
    await coordinator.register(
        "agent-1",
        "injection-tester",
        parent_id="root",
        skills=["sql_injection", "xss"],
    )
    await coordinator.set_status("agent-1", "completed")
    run = _Run(mode)
    ctx = ToolContext(
        context={"coordinator": coordinator, "agent_id": "root", "parent_id": None},
        tool_name="finish_scan",
        tool_call_id="call-1",
        tool_arguments="{}",
    )
    payload = {
        "executive_summary": "Summary of the assessment.",
        "methodology": "Tested the in-scope API.",
        "technical_analysis": "SQL injection was assessed.",
        "recommendations": "Fix the assessed issues.",
        "accept_unexamined": accept_unexamined,
    }
    monkeypatch.setattr("lamia.report.state.get_global_report_state", lambda: run)
    raw = await finish_scan.on_invoke_tool(ctx, json.dumps(payload))
    parsed: dict[str, Any] = json.loads(raw)
    return parsed, run


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["deep", "exhaustive"])
async def test_broad_scan_refuses_unexamined_classes(
    mode: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _record("SQL injection")

    result, run = await _finish(mode, accept_unexamined=False, monkeypatch=monkeypatch)

    assert result["success"] is False
    assert result["scan_completed"] is False
    assert "xss" in result["coverage_gaps"][0]
    assert run.saved == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["deep", "exhaustive"])
async def test_accept_unexamined_finishes_and_records_the_gap(
    mode: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _record("SQL injection")

    result, run = await _finish(mode, accept_unexamined=True, monkeypatch=monkeypatch)

    assert result["scan_completed"] is True
    assert "were not tested" in run.saved["technical_analysis"]
    assert "xss" in run.saved["technical_analysis"]


@pytest.mark.asyncio
async def test_quick_scan_warns_and_still_finishes(monkeypatch: pytest.MonkeyPatch) -> None:
    _record("SQL injection")

    result, run = await _finish("quick", accept_unexamined=False, monkeypatch=monkeypatch)

    assert result["scan_completed"] is True
    assert "unexamined" in result["coverage_gap_warning"]
    assert "were not tested" not in run.saved["technical_analysis"]
