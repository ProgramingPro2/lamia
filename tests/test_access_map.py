"""The viewer access map is a reading of records a run already wrote."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from lamia.interface.viewer.access_map import build_access_map


if TYPE_CHECKING:
    from pathlib import Path


_POC = "POC_SENTINEL_DO_NOT_COPY"


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _run(tmp_path: Path, name: str = "map") -> Path:
    run_dir = tmp_path / "strix_runs" / name
    run_dir.mkdir(parents=True)
    _write(
        run_dir / "run.json",
        {
            "run_name": name,
            "status": "completed",
            "end_time": "2026-01-01T00:00:00Z",
            "targets_info": [{"original": "https://edge.internal"}],
        },
    )
    return run_dir


def _node(graph: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(node for node in graph["nodes"] if node["id"] == node_id)


def _edge(graph: dict[str, Any], edge_id: str) -> dict[str, Any]:
    return next(edge for edge in graph["edges"] if edge["id"] == edge_id)


def test_finding_links_two_assets_without_copying_poc(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    _write(
        run_dir / "vulnerabilities.json",
        [
            {
                "id": "vuln_8f3a",
                "title": "Admin reach from the edge host",
                "target": "edge.internal",
                "endpoint": "https://api.internal/admin",
                "severity": "high",
                "poc_description": _POC,
                "poc_script_code": f"print({_POC!r})",
                "code_locations": [{"file": "src/admin.py", "start_line": 10}],
            }
        ],
    )
    _write(
        run_dir / ".state" / "coverage.json",
        {
            "cov_14": {
                "surface": "https://api.internal/admin",
                "risk_area": "access control",
                "outcome": "reported",
            }
        },
    )

    graph = build_access_map(run_dir)

    assert _node(graph, "host:edge.internal")["in_scope"] is True
    discovered = _node(graph, "host:api.internal")
    assert discovered["in_scope"] is False
    assert discovered["label"] == "api.internal"
    assert _node(graph, "app:api.internal/admin")["type"] == "app"
    assert _node(graph, "app:src/admin.py")["label"] == "src/admin.py"

    edge = _edge(graph, "edge:vuln_8f3a")
    assert edge["type"] == "access_gained"
    assert edge["source"] == "host:edge.internal"
    assert edge["target"] == "app:api.internal/admin"
    assert edge["label"] == "Admin reach from the edge host"
    assert edge["finding_id"] == "vuln_8f3a"
    assert edge["coverage_id"] == "cov_14"
    assert edge["status"] == "confirmed"
    assert _POC not in json.dumps(graph)


def test_discovered_host_is_shown_without_an_approval_gate(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    _write(
        run_dir / ".state" / "coverage.json",
        {
            "cov_lead": {
                "surface": "https://secret.internal/lead",
                "risk_area": "unreviewed lead",
                "outcome": "needs_follow_up",
                "approved": False,
            }
        },
    )

    graph = build_access_map(run_dir)

    assert _node(graph, "host:secret.internal")["in_scope"] is False
    edge = _edge(graph, "edge:cov:cov_lead")
    assert edge["type"] == "proof_gap"
    assert edge["status"] == "proof_gap"
    assert edge["source"] == "host:secret.internal"
    assert edge["target"] == "app:secret.internal/lead"
    assert "approved" not in edge


def test_closed_coverage_draws_nodes_but_no_access_edge(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    _write(
        run_dir / "coverage.json",
        {
            "entries": [
                {
                    "surface": "https://edge.internal/health",
                    "risk_area": "injection",
                    "outcome": "no_issue_found",
                },
                {
                    "surface": "https://edge.internal/legacy",
                    "risk_area": "redirect",
                    "outcome": "ruled_out",
                },
            ]
        },
    )

    graph = build_access_map(run_dir)

    assert _node(graph, "host:edge.internal")["in_scope"] is True
    assert _node(graph, "app:edge.internal/health")
    assert _node(graph, "app:edge.internal/legacy")
    assert graph["edges"]
    assert {edge["type"] for edge in graph["edges"]} == {"contains"}
    assert {(edge["source"], edge["target"]) for edge in graph["edges"]} == {
        ("host:edge.internal", "app:edge.internal/health"),
        ("host:edge.internal", "app:edge.internal/legacy"),
    }


def test_note_can_name_a_role_or_store_but_draws_no_edge(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    _write(
        run_dir / ".state" / "notes.json",
        {
            "n1": {
                "title": "Billing access",
                "category": "wiki",
                "role": "billing-admin",
                "team": "finance",
                "content": _POC,
            },
            "n2": {
                "title": "Jane Doe",
                "category": "general",
                "content": "A person, not an asset.",
            },
            "n3": {
                "title": "Orders database",
                "category": "wiki",
                "content": "Holds order rows.",
            },
            "n4": {
                "title": "Named person as a role",
                "category": "wiki",
                "role": "Jane Doe",
                "team": "finance",
            },
        },
    )

    graph = build_access_map(run_dir)
    ids = {node["id"] for node in graph["nodes"]}

    assert "role:finance:billing-admin" in ids
    assert _node(graph, "role:finance:billing-admin")["label"] == "billing-admin (finance)"
    stores = [node for node in graph["nodes"] if node["type"] == "data_store"]
    assert any("Orders database" in node["label"] for node in stores)
    assert "Jane Doe" not in json.dumps(graph["nodes"])
    assert graph["edges"] == []
    assert _POC not in json.dumps(graph)


def test_threat_model_names_a_store_and_a_crossed_boundary(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    _write(
        run_dir / "vulnerabilities.json",
        [
            {
                "id": "vuln_8f3a",
                "title": "Admin reach from the edge host",
                "target": "edge.internal",
                "endpoint": "https://api.internal/admin",
            }
        ],
    )
    _write(
        run_dir / ".state" / "threat_models.json",
        {
            "edge.internal": {
                "target": "edge.internal",
                "content": (
                    "## Overview\nThe edge.\n\n"
                    "## Trust Boundaries\n"
                    "- edge.internal -> api.internal\n\n"
                    "## Attack Surface\n"
                    "- Postgres orders database\n"
                    "- role: reader, team: analytics\n\n"
                    "## Severity Calibration\nCritical means a data store.\n"
                ),
            }
        },
    )

    graph = build_access_map(run_dir)

    assert any(node["type"] == "data_store" for node in graph["nodes"])
    assert _node(graph, "role:analytics:reader")["label"] == "reader (analytics)"
    edge = _edge(graph, "edge:vuln_8f3a")
    assert edge["type"] == "trust_boundary"
    assert edge["status"] == "confirmed"
    assert edge["finding_id"] == "vuln_8f3a"


def test_empty_run_has_no_devices_and_no_edges(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    (run_dir / ".state").mkdir()
    (run_dir / ".state" / "coverage.json").write_text("{", encoding="utf-8")

    graph = build_access_map(run_dir)

    assert graph == {"nodes": [], "edges": []}


def test_bare_path_is_contained_by_the_in_scope_host(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    _write(
        run_dir / "coverage.json",
        {
            "entries": [
                {
                    "surface": "https://edge.internal",
                    "risk_area": "infrastructure fingerprinting",
                    "outcome": "no_issue_found",
                },
                {
                    "surface": "BidStar module /bidstar/ (proposal generation)",
                    "risk_area": "attack surface mapping",
                    "outcome": "no_issue_found",
                },
            ]
        },
    )

    graph = build_access_map(run_dir)

    assert _node(graph, "app:edge.internal/bidstar")["in_scope"] is True
    assert not any(node["label"] == "/bidstar" for node in graph["nodes"])
    assert {
        (edge["source"], edge["target"]) for edge in graph["edges"] if edge["type"] == "contains"
    } == {("host:edge.internal", "app:edge.internal/bidstar")}


def test_store_stays_with_the_host_named_in_the_same_note(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    title = (
        "Pre-outage evidence preservation — MySQL 3306 & SSH 22 verdicts (sandbox.lodestarbpm.com)"
    )
    _write(
        run_dir / ".state" / "notes.json",
        {
            "mysql": {
                "title": title,
                "category": "general",
                "content": "Preserved before the outage.",
            }
        },
    )

    graph = build_access_map(run_dir)

    stores = [node for node in graph["nodes"] if node["type"] == "data_store"]
    assert len(stores) == 1
    assert "sandbox.lodestarbpm.com" not in stores[0]["label"]
    assert any(
        edge["type"] == "contains"
        and edge["source"] == "host:sandbox.lodestarbpm.com"
        and edge["target"] == stores[0]["id"]
        for edge in graph["edges"]
    )


def test_slash_inside_a_sentence_does_not_become_a_node(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    _write(
        run_dir / "coverage.json",
        {
            "entries": [
                {
                    "surface": "UDP/TCP service fingerprinting",
                    "risk_area": "infrastructure fingerprinting",
                    "outcome": "no_issue_found",
                }
            ]
        },
    )

    graph = build_access_map(run_dir)

    assert graph["nodes"] == []
    assert graph["edges"] == []


def test_host_port_follow_up_is_a_service_gap(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    _write(
        run_dir / ".state" / "coverage.json",
        {
            "mysql": {
                "surface": "sandbox.lodestarbpm.com:3306 (MySQL 5.1.73-log)",
                "risk_area": "database authentication",
                "outcome": "needs_follow_up",
            }
        },
    )

    graph = build_access_map(run_dir)

    assert _node(graph, "host:sandbox.lodestarbpm.com")["type"] == "host"
    assert _node(graph, "svc:sandbox.lodestarbpm.com:3306")["type"] == "service"
    assert all("MySQL" not in node["label"] for node in graph["nodes"])
    edge = _edge(graph, "edge:cov:mysql")
    assert edge["type"] == "proof_gap"
    assert edge["source"] == "host:sandbox.lodestarbpm.com"
    assert edge["target"] == "svc:sandbox.lodestarbpm.com:3306"
    assert not any(item["type"] == "contains" for item in graph["edges"])


def test_queued_title_is_not_a_data_store(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    _write(
        run_dir / ".state" / "notes.json",
        {
            "plan": {
                "title": "Auth & ATO path — pre-outage analysis, evidence, and queued test plan",
                "category": "general",
                "content": "The word queued is a plan, not a queue.",
            }
        },
    )

    graph = build_access_map(run_dir)

    assert graph["nodes"] == []
    assert graph["edges"] == []


def test_lodestar_slice_links_the_dns_service_and_drops_sentences(tmp_path: Path) -> None:
    run_dir = _run(tmp_path, "lodestar-slice")
    _write(
        run_dir / "vulnerabilities.json",
        [
            {
                "id": "vuln-0001",
                "title": "Open Recursive DNS Resolver",
                "target": "sandbox.lodestarbpm.com:53 (UDP/TCP DNS, dnsmasq)",
                "endpoint": "",
            }
        ],
    )
    _write(
        run_dir / ".state" / "coverage.json",
        {
            "dns": {
                "surface": "sandbox.lodestarbpm.com:53 (DNS service fingerprinting)",
                "risk_area": "infrastructure fingerprinting",
                "outcome": "no_issue_found",
            }
        },
    )
    _write(
        run_dir / ".state" / "notes.json",
        {
            "plan": {
                "title": "Auth & ATO path — pre-outage analysis, evidence, and queued test plan",
                "category": "general",
            }
        },
    )

    graph = build_access_map(run_dir)
    labels = [node["label"] for node in graph["nodes"]]

    assert not any("UDP/TCP" in label or "fingerprinting" in label for label in labels)
    assert not any("queued" in label for label in labels)
    assert not any(node["type"] == "data_store" for node in graph["nodes"])
    assert _node(graph, "svc:sandbox.lodestarbpm.com:53")["type"] == "service"
    edge = _edge(graph, "edge:vuln-0001")
    assert edge["type"] == "access_gained"
    assert edge["source"] == "host:sandbox.lodestarbpm.com"
    assert edge["target"] == "svc:sandbox.lodestarbpm.com:53"
