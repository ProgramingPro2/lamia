"""Access map for the local viewer.

The map is a reading of records a run already wrote: findings, coverage,
notes, and the threat model. A host, app, role, or data store that appears
in any of those records is shown. Nothing here waits for an operator to
approve a discovered asset, and nothing here copies proof-of-concept text.
The arrow keeps a short phrase and the finding id; the finding itself is
where the detail lives. A contains edge only says which host owns a
service, app, or store. It is not access.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from lamia.interface.viewer.transcript import read_run_summary, read_vulnerabilities


if TYPE_CHECKING:
    from pathlib import Path


_HOST_SUFFIXES = frozenset(
    {
        "ai",
        "app",
        "arpa",
        "au",
        "biz",
        "cloud",
        "cn",
        "co",
        "com",
        "corp",
        "de",
        "dev",
        "edu",
        "example",
        "fr",
        "gov",
        "home",
        "info",
        "internal",
        "invalid",
        "io",
        "jp",
        "lan",
        "local",
        "net",
        "network",
        "org",
        "ru",
        "systems",
        "tech",
        "test",
        "uk",
        "xyz",
    }
)
_CODE_SUFFIXES = frozenset(
    {
        ".c",
        ".cc",
        ".cs",
        ".go",
        ".h",
        ".html",
        ".java",
        ".js",
        ".json",
        ".jsx",
        ".md",
        ".php",
        ".py",
        ".rb",
        ".rs",
        ".toml",
        ".ts",
        ".tsx",
        ".txt",
        ".xml",
        ".yaml",
        ".yml",
    }
)
_STORE_WORDS = (
    "bigquery",
    "blob",
    "bucket",
    "database",
    "datastore",
    "data store",
    "dynamodb",
    "elasticsearch",
    "kafka",
    "mariadb",
    "mongo",
    "mongodb",
    "mysql",
    "opensearch",
    "postgres",
    "postgresql",
    "queue",
    "redis",
    "s3",
    "snowflake",
    "sqlite",
    "warehouse",
)
_NO_ACCESS_OUTCOMES = frozenset({"ruled_out", "no_issue_found", "not_applicable"})
_PERSON_NAME = re.compile(
    r"^[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?(?:\s+[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?){1,2}$"
)
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*?)\s*$", re.MULTILINE)
_ARROW = re.compile(r"\s*(?:->|→|=>)\s*")
_ROLE_FIELD = re.compile(r"\brole\s*[:=]\s*([^,;\n]+)", re.IGNORECASE)
_TEAM_FIELD = re.compile(r"\bteam\s*[:=]\s*([^,;\n]+)", re.IGNORECASE)
_HOST_TOKEN = re.compile(
    r"\b(?:https?://[^\s,;]+|localhost|(?:\d{1,3}\.){3}\d{1,3}|(?:[a-z0-9-]+\.)+[a-z]{2,})\b",
    re.IGNORECASE,
)
_URL_TOKEN = re.compile(r"https?://[^\s,;'\"<>]+", re.IGNORECASE)
_HOST_PORT_TOKEN = re.compile(
    r"\b((?:(?:\d{1,3}\.){3}\d{1,3})|(?:[a-z0-9-]+\.)+[a-z]{2,}|localhost):(\d{2,5})\b",
    re.IGNORECASE,
)
# A real path, not a slash inside a word such as UDP/TCP.
_PATH_TOKEN = re.compile(r"(?<![\w./-])(/[\w.~%:@+-]+(?:/[\w.~%:@+-]+)*|/\?[^\s,;'\"<>)\]]+)")
_LABEL_LIMIT = 80

Asset = dict[str, str]


def build_access_map(run_dir: Path) -> dict[str, Any]:
    """Nodes and edges for one run directory.

    Missing or unreadable artifacts contribute nothing. A self-discovered
    host is included the moment a record names it.
    """
    record = read_run_summary(run_dir)
    scope = _scope_hosts(record if isinstance(record, dict) else {})
    graph = _Graph(scope)
    findings = [item for item in read_vulnerabilities(run_dir) if isinstance(item, dict)]
    coverage = _coverage_entries(run_dir)
    reported = [entry for entry in coverage if str(entry.get("outcome", "")).lower() == "reported"]

    for finding in findings:
        _add_finding(graph, finding, reported)
    for entry in coverage:
        _add_coverage(graph, entry, findings)
    for note_id, note in _notes(run_dir):
        _add_note(graph, note_id, note)
    for model_id, model in _threat_models(run_dir):
        _add_threat_model(graph, model_id, model)
    graph.link_contained()
    graph.apply_trust_boundaries()
    return graph.payload()


class _Graph:
    """Accumulates nodes and edges, merging records that name the same asset."""

    def __init__(self, scope_hosts: set[str]) -> None:
        self.scope_hosts = scope_hosts
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: dict[str, dict[str, Any]] = {}
        self.boundaries: list[str] = []

    def add_asset(self, asset: Asset, *, kind: str, source_id: str) -> None:
        node_id = asset["id"]
        label = asset["label"]
        in_scope = _in_scope(asset, self.scope_hosts)
        node = self.nodes.get(node_id)
        if node is None:
            node = {
                "id": node_id,
                "type": asset["type"],
                "label": label,
                "in_scope": in_scope,
                "sources": [],
            }
            self.nodes[node_id] = node
        elif in_scope:
            node["in_scope"] = True
        _add_source(node, kind, source_id)

    def add_assets(self, assets: list[Asset], *, kind: str, source_id: str) -> None:
        seen: set[str] = set()
        for asset in assets:
            if asset["id"] in seen:
                continue
            seen.add(asset["id"])
            self.add_asset(asset, kind=kind, source_id=source_id)

    def add_edge(self, edge: dict[str, Any]) -> None:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        edge_id = str(edge.get("id", ""))
        if not edge_id or not source or not target or source == target:
            return
        if source not in self.nodes or target not in self.nodes:
            return
        self.edges[edge_id] = edge

    def add_contains(self, source: str, target: str) -> None:
        """A structural parent edge. Skipped when any edge already joins the pair."""
        if not source or not target or source == target:
            return
        if source not in self.nodes or target not in self.nodes:
            return
        for edge in self.edges.values():
            pair = {str(edge.get("source", "")), str(edge.get("target", ""))}
            if pair == {source, target}:
                return
        edge_id = f"edge:contains:{source}:{target}"
        self.edges[edge_id] = {
            "id": edge_id,
            "type": "contains",
            "source": source,
            "target": target,
            "label": "",
            "finding_id": None,
            "status": "contains",
        }

    def link_contained(self) -> None:
        """Parent services, apps, and stores that have no access edge yet.

        Closed coverage and notes stay free of access arrows. The host edge
        is what keeps those assets from sitting as orphan points.
        """
        self._adopt_unqualified_paths()
        hosts = [node for node in self.nodes.values() if node.get("type") == "host"]
        for node in list(self.nodes.values()):
            parent = _containing_host(node, hosts)
            if parent is None:
                continue
            self.add_contains(str(parent["id"]), str(node["id"]))

    def _adopt_unqualified_paths(self) -> None:
        """Hang a bare path off the only in-scope host so it is not an orphan."""
        parents = [
            node
            for node in self.nodes.values()
            if node.get("type") == "host" and node.get("in_scope") is True
        ]
        if len(parents) != 1:
            return
        host_label = str(parents[0].get("label", "")).lower()
        moves: list[tuple[str, str, str]] = []
        for node in self.nodes.values():
            if node.get("type") != "app":
                continue
            label = str(node.get("label", ""))
            if not label.startswith("/"):
                continue
            if _host_key({"id": "", "type": "app", "label": label}) is not None:
                continue
            qualified = f"{host_label}{label}".lower()
            moves.append((str(node["id"]), f"app:{qualified}", qualified))
        for old_id, new_id, qualified in moves:
            old = self.nodes.pop(old_id, None)
            if old is None:
                continue
            target = self.nodes.get(new_id)
            if target is None:
                target = {
                    "id": new_id,
                    "type": "app",
                    "label": qualified,
                    "in_scope": True,
                    "sources": [],
                }
                self.nodes[new_id] = target
            for source in old.get("sources", []):
                if isinstance(source, dict):
                    _add_source(target, str(source.get("kind", "")), str(source.get("id", "")))
            self._retarget(old_id, new_id)

    def _retarget(self, old_id: str, new_id: str) -> None:
        for edge in self.edges.values():
            if edge.get("source") == old_id:
                edge["source"] = new_id
            if edge.get("target") == old_id:
                edge["target"] = new_id

    def apply_trust_boundaries(self) -> None:
        if not self.boundaries:
            return
        for edge in self.edges.values():
            if edge.get("type") != "access_gained":
                continue
            source = self.nodes.get(str(edge.get("source")))
            target = self.nodes.get(str(edge.get("target")))
            if source and target and _crosses_boundary(source, target, self.boundaries):
                edge["type"] = "trust_boundary"

    def payload(self) -> dict[str, Any]:
        nodes = sorted(self.nodes.values(), key=lambda item: str(item["id"]))
        for node in nodes:
            node["sources"] = sorted(
                node["sources"],
                key=lambda item: (str(item.get("kind")), str(item.get("id"))),
            )
        edges = sorted(self.edges.values(), key=lambda item: str(item["id"]))
        return {"nodes": nodes, "edges": edges}


def _add_source(node: dict[str, Any], kind: str, source_id: str) -> None:
    if not source_id:
        return
    item = {"kind": kind, "id": source_id}
    sources: list[dict[str, str]] = node["sources"]
    if item not in sources:
        sources.append(item)


def _add_finding(graph: _Graph, finding: dict[str, Any], reported: list[dict[str, Any]]) -> None:
    finding_id = _text(finding.get("id"))
    source, dest, assets = _finding_assets(finding)
    graph.add_assets(assets, kind="finding", source_id=finding_id)
    if source is None or dest is None or source["id"] == dest["id"]:
        return
    coverage_id = _matching_coverage_id(finding, reported)
    edge: dict[str, Any] = {
        "id": f"edge:{finding_id or source['id']}",
        "type": "access_gained",
        "source": source["id"],
        "target": dest["id"],
        "label": _short_phrase(_text(finding.get("title")), fallback="Access recorded"),
        "finding_id": finding_id or None,
        "status": "confirmed",
    }
    if coverage_id:
        edge["coverage_id"] = coverage_id
    graph.add_edge(edge)


def _add_coverage(graph: _Graph, entry: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    surface = _text(entry.get("surface"))
    if not surface:
        return
    outcome = str(entry.get("outcome", "")).lower()
    coverage_id = _text(entry.get("entry_id"))
    source, dest, assets = _coverage_assets(surface)
    graph.add_assets(assets, kind="coverage", source_id=coverage_id)
    if outcome in _NO_ACCESS_OUTCOMES or outcome == "reported":
        return
    if outcome != "needs_follow_up" or source is None or dest is None:
        return
    if source["id"] == dest["id"]:
        return
    edge: dict[str, Any] = {
        "id": f"edge:cov:{coverage_id or source['id']}",
        "type": "proof_gap",
        "source": source["id"],
        "target": dest["id"],
        "label": _short_phrase(_text(entry.get("risk_area")), fallback="Needs follow-up"),
        "finding_id": _matching_finding_id(surface, findings),
        "coverage_id": coverage_id or None,
        "status": "proof_gap",
    }
    graph.add_edge(edge)


def _add_note(graph: _Graph, note_id: str, note: dict[str, Any]) -> None:
    """A note can name an asset. It never draws an access edge."""
    assets = _note_assets(note)
    graph.add_assets(assets, kind="note", source_id=note_id)
    _contain_noted_stores(graph, assets)


def _add_threat_model(graph: _Graph, model_id: str, model: dict[str, Any]) -> None:
    text = _model_text(model)
    assets, boundaries = _threat_sections(text)
    graph.add_assets(assets, kind="threat_model", source_id=model_id)
    graph.boundaries.extend(boundaries)


def _finding_assets(finding: dict[str, Any]) -> tuple[Asset | None, Asset | None, list[Asset]]:
    origin = _parse_assets(_text(finding.get("target")))
    hint = _host_label(origin)
    dest = _parse_assets(_text(finding.get("endpoint")), host_hint=hint)
    assets = [*origin, *dest, *_code_assets(finding)]
    role = _role_asset(finding)
    if role is not None:
        assets.append(role)
    return (*_pick_edge(origin, dest, role), assets)


def _coverage_assets(surface: str) -> tuple[Asset | None, Asset | None, list[Asset]]:
    sides = _relation_sides(surface)
    if sides is not None:
        left = _parse_assets(sides[0])
        right = _parse_assets(sides[1])
        return (
            _prefer(left, "host"),
            _child_asset(right) or _prefer(right, "host"),
            [
                *left,
                *right,
            ],
        )
    assets = _parse_assets(surface)
    assets.extend(_embedded_assets(surface))
    return _prefer(assets, "host"), _child_asset(assets), _dedupe(assets)


def _pick_edge(
    origin: list[Asset], dest: list[Asset], role: Asset | None
) -> tuple[Asset | None, Asset | None]:
    source = _prefer(origin, "host") or _first(origin)
    target = _child_asset(dest) or _prefer(dest, "host") or _last(dest)
    if source and target and source["id"] != target["id"]:
        return source, target
    host = _prefer(origin, "host")
    app = _prefer(origin, "app")
    if host and app and host["id"] != app["id"]:
        return host, app
    service = _prefer(origin, "service") or _prefer(dest, "service")
    if host and service and host["id"] != service["id"]:
        return host, service
    network = (
        target or _prefer(origin, "app") or _prefer(origin, "service") or _prefer(origin, "host")
    )
    if role is not None and network is not None and role["id"] != network["id"]:
        return role, network
    return None, None


def _note_assets(note: dict[str, Any]) -> list[Asset]:
    assets: list[Asset] = []
    role = _role_asset(note)
    if role is not None:
        assets.append(role)
    for key in ("data_store", "store"):
        store = _store_from_text(_text(note.get(key)))
        if store is not None:
            assets.append(store)
    kind = str(note.get("asset_type") or note.get("kind") or "").strip().lower()
    if kind in {"data_store", "store", "datastore"}:
        store = _store_from_text(_text(note.get("title")) or _text(note.get("data_store")))
        if store is not None:
            assets.append(store)
    for key in ("host", "asset", "surface", "endpoint", "target"):
        assets.extend(_parse_assets(_text(note.get(key))))
    category = str(note.get("category") or "general").strip().lower()
    title = _text(note.get("title"))
    if category in {"wiki", "general"} and title and not _is_personal_name(title):
        if _mentions_store(title):
            store = _store_from_text(title)
            if store is not None:
                assets.append(store)
        assets.extend(_parse_assets(title))
        assets.extend(_embedded_assets(title))
    return _dedupe(assets)


def _threat_sections(text: str) -> tuple[list[Asset], list[str]]:
    assets: list[Asset] = []
    for bullet in _bullets(_section_body(text, "attack surface")):
        role = _role_from_prose(bullet)
        if role is not None:
            assets.append(role)
        if _mentions_store(bullet):
            store = _store_from_text(bullet)
            if store is not None:
                assets.append(store)
        assets.extend(_parse_assets(bullet))
        assets.extend(_embedded_assets(bullet))
    boundaries = [bullet.lower() for bullet in _bullets(_section_body(text, "trust boundar"))]
    return _dedupe(assets), boundaries


def _parse_assets(text: str, *, host_hint: str | None = None) -> list[Asset]:
    raw = text.strip().strip("`").strip()
    if not raw or _is_personal_name(raw):
        return []
    if any(char.isspace() for char in raw):
        return _prose_assets(raw)
    return _token_assets(raw, host_hint)


def _token_assets(raw: str, host_hint: str | None) -> list[Asset]:
    if raw.lower().startswith(("http://", "https://")):
        return _host_assets(raw)
    if raw.startswith(("/", "\\")):
        return _path_asset(raw.replace("\\", "/"), host_hint)
    hosted = _host_assets(raw)
    if hosted or not _is_code_path(raw):
        return hosted
    return [_asset("app", raw, raw)]


def _path_asset(raw: str, host_hint: str | None) -> list[Asset]:
    path = _strip_decorations(raw)
    if path in {"", "/"}:
        if path == "/" and host_hint:
            label = f"{host_hint}/".lower()
            return [_asset("app", label, label)]
        return []
    if not path.startswith("/"):
        path = f"/{path}"
    if host_hint:
        label = f"{host_hint}{path}".lower()
        return [_asset("app", label, label)]
    return [_asset("app", path, path)]


def _host_assets(raw: str) -> list[Asset]:
    located = _hostname_and_path(raw)
    if located is None:
        return []
    host, port, path = located
    return _assets_for_endpoint(host, port, path)


def _assets_for_endpoint(host: str, port: int | None, path: str) -> list[Asset]:
    """A host, plus a service when the port is not the web default, plus a path."""
    assets = [_asset("host", host, host)]
    if port is not None and port not in {80, 443} and 0 < port <= 65535:
        label = f"{host}:{port}"
        assets.append(_asset("service", label, label))
    if path == "/":
        label = f"{host}/"
        assets.append(_asset("app", label, label))
    elif path:
        label = f"{host}{path}".lower()
        assets.append(_asset("app", label, label))
    return assets


def _embedded_assets(text: str) -> list[Asset]:
    if " " not in text and "://" not in text:
        return []
    return _prose_assets(text)


def _prose_assets(text: str) -> list[Asset]:
    """Hosts, ports, and paths mentioned in a sentence. The sentence itself is not an asset."""
    occupied: list[tuple[int, int]] = []
    assets: list[Asset] = []

    def overlaps(start: int, end: int) -> bool:
        return any(start < right and end > left for left, right in occupied)

    for match in _URL_TOKEN.finditer(text):
        token = match.group(0).rstrip(").,")
        assets.extend(_host_assets(token))
        occupied.append(match.span())
    for match in _HOST_PORT_TOKEN.finditer(text):
        if overlaps(*match.span()):
            continue
        port = int(match.group(2))
        assets.extend(_service_assets(match.group(1), port))
        occupied.append(match.span())
    for match in _HOST_TOKEN.finditer(text):
        if overlaps(*match.span()):
            continue
        token = match.group(0).rstrip(").,")
        hosted = _host_assets(token)
        if not hosted:
            continue
        assets.extend(hosted)
        occupied.append(match.span())

    host_labels = [asset["label"] for asset in assets if asset["type"] == "host"]
    unique_hosts = {_host_name(label) for label in host_labels}
    hint = host_labels[0] if len(unique_hosts) == 1 else None
    for match in _PATH_TOKEN.finditer(text):
        if overlaps(*match.span()):
            continue
        assets.extend(_path_asset(match.group(1).rstrip(").,"), hint))
    return _dedupe(assets)


def _service_assets(host: str, port: int) -> list[Asset]:
    cleaned = host.rstrip(".").lower()
    if not _is_host_name(cleaned):
        return []
    if port in {80, 443} or not 0 < port <= 65535:
        return [_asset("host", cleaned, cleaned)]
    return _assets_for_endpoint(cleaned, port, "")


def _code_assets(finding: dict[str, Any]) -> list[Asset]:
    locations = finding.get("code_locations")
    if not isinstance(locations, list):
        return []
    assets: list[Asset] = []
    for location in locations:
        if not isinstance(location, dict):
            continue
        file_name = _text(location.get("file"))
        if file_name and not _is_personal_name(file_name):
            assets.append(_asset("app", file_name, file_name))
    return assets


def _role_asset(record: dict[str, Any]) -> Asset | None:
    role = _text(record.get("role"))
    team = _text(record.get("team"))
    if not role or not team or _is_personal_name(role) or _is_personal_name(team):
        return None
    return _asset("role", f"{_slug(team)}:{_slug(role)}", f"{role} ({team})")


def _role_from_prose(text: str) -> Asset | None:
    role_match = _ROLE_FIELD.search(text)
    team_match = _TEAM_FIELD.search(text)
    if role_match is None or team_match is None:
        return None
    return _role_asset({"role": role_match.group(1).strip(), "team": team_match.group(1).strip()})


def _store_from_text(text: str) -> Asset | None:
    cleaned = _short_phrase(text, fallback="")
    if not cleaned or _is_personal_name(cleaned):
        return None
    return _asset("data_store", _slug(cleaned), cleaned)


def _asset(kind: str, identity: str, label: str) -> Asset:
    prefix = {
        "host": "host",
        "app": "app",
        "role": "role",
        "data_store": "store",
        "service": "svc",
    }[kind]
    return {"id": f"{prefix}:{identity}", "type": kind, "label": label}


def _hostname_and_path(text: str) -> tuple[str, int | None, str] | None:
    raw = text.strip()
    if not raw or any(char.isspace() for char in raw):
        return None
    prefixed = raw if "://" in raw else f"//{raw}"
    parts = urlsplit(prefixed)
    host = (parts.hostname or "").rstrip(".").lower()
    if not _is_host_name(host):
        return None
    path = _strip_decorations(parts.path or "")
    return host, parts.port, path


def _is_host_name(host: str) -> bool:
    if host == "localhost":
        return True
    if _is_ip(host):
        return True
    labels = host.split(".")
    if len(labels) < 2 or labels[-1] not in _HOST_SUFFIXES:
        return False
    return all(_is_dns_label(label) for label in labels)


def _is_dns_label(label: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label))


def _is_ip(host: str) -> bool:
    pieces = host.split(".")
    if len(pieces) != 4:
        return False
    for piece in pieces:
        if not piece.isdigit():
            return False
        number = int(piece)
        if number > 255 or (len(piece) > 1 and piece.startswith("0")):
            return False
    return True


def _is_code_path(text: str) -> bool:
    """A single file token. A sentence that merely contains a slash is not one."""
    if any(char.isspace() for char in text):
        return False
    lowered = text.lower()
    if lowered.startswith(("http://", "https://")):
        return False
    if text.startswith(("/", "\\")):
        return True
    return any(lowered.endswith(suffix) for suffix in _CODE_SUFFIXES)


def _is_personal_name(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned or any(char in cleaned for char in ".@/:\\"):
        return False
    return _PERSON_NAME.match(cleaned) is not None


def _mentions_store(text: str) -> bool:
    lowered = text.lower()
    for word in _STORE_WORDS:
        if re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", lowered):
            return True
    return bool(re.search(r"(?<![a-z0-9])db(?![a-z0-9])", lowered))


def _strip_decorations(path: str) -> str:
    trimmed = path.split("?", 1)[0].split("#", 1)[0]
    if len(trimmed) > 1:
        trimmed = trimmed.rstrip("/")
    return trimmed


def _relation_sides(text: str) -> tuple[str, str] | None:
    parts = _ARROW.split(text, maxsplit=1)
    if len(parts) != 2:
        return None
    left, right = parts[0].strip(), parts[1].strip()
    if not left or not right:
        return None
    return left, right


def _section_body(content: str, needle: str) -> str:
    matches = list(_HEADING.finditer(content))
    chunks: list[str] = []
    for index, match in enumerate(matches):
        if needle not in match.group(1).lower():
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        chunks.append(content[start:end])
    return "\n".join(chunks)


def _bullets(text: str) -> list[str]:
    return [match.group(1).strip() for match in _BULLET.finditer(text) if match.group(1).strip()]


def _model_text(model: dict[str, Any]) -> str:
    parts = [_text(model.get("content"))]
    amendments = model.get("amendments")
    if isinstance(amendments, list):
        for item in amendments:
            if isinstance(item, dict):
                parts.append(_text(item.get("content") or item.get("text")))
            elif isinstance(item, str):
                parts.append(item.strip())
    return "\n".join(part for part in parts if part)


def _scope_hosts(record: dict[str, Any]) -> set[str]:
    values: list[str] = []
    info = record.get("targets_info")
    if isinstance(info, list):
        for entry in info:
            if isinstance(entry, dict) and isinstance(entry.get("original"), str):
                values.append(entry["original"])
            elif isinstance(entry, str):
                values.append(entry)
    targets = record.get("targets")
    if isinstance(targets, list):
        values.extend(item for item in targets if isinstance(item, str))
    hosts: set[str] = set()
    for value in values:
        for asset in [*_parse_assets(value), *_embedded_assets(value)]:
            host = _host_key(asset)
            if host:
                hosts.add(host)
    return hosts


def _in_scope(asset: Asset, scope_hosts: set[str]) -> bool:
    if asset["type"] in {"role", "data_store"}:
        return True
    host = _host_key(asset)
    if host is None:
        return True
    return host in scope_hosts


def _host_key(asset: Asset) -> str | None:
    label = asset["label"].lower()
    if asset["type"] == "host":
        return _host_name(label)
    if asset["type"] == "service":
        return _host_name(label.rsplit(":", 1)[0])
    if asset["type"] != "app":
        return None
    candidate = label.split("/", 1)[0]
    bare = _host_name(candidate.split(":", 1)[0])
    if bare and (_is_host_name(bare) or bare == "localhost"):
        return bare
    return None


def _host_name(label: str) -> str:
    return label.split(":", 1)[0].rstrip(".")


def _containing_host(node: dict[str, Any], hosts: list[dict[str, Any]]) -> dict[str, Any] | None:
    kind = str(node.get("type", ""))
    label = str(node.get("label", ""))
    if kind in {"app", "service"}:
        key = _host_key({"id": "", "type": kind, "label": label})
        if key is None:
            return None
        for host in hosts:
            host_key = _host_key({"id": "", "type": "host", "label": str(host.get("label", ""))})
            if host_key == key:
                return host
        return None
    if kind != "data_store":
        return None
    matches = [
        host for host in hosts if _contains_label(label.lower(), str(host.get("label", "")).lower())
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _child_asset(assets: list[Asset]) -> Asset | None:
    return _prefer(assets, "app") or _prefer(assets, "service")


def _contain_noted_stores(graph: _Graph, assets: list[Asset]) -> None:
    """A store named beside one host in the same note belongs to that host."""
    hosts = [asset for asset in assets if asset["type"] == "host"]
    host_ids = {asset["id"] for asset in hosts}
    if len(host_ids) != 1:
        return
    parent_id = next(iter(host_ids))
    for asset in assets:
        if asset["type"] == "data_store":
            graph.add_contains(parent_id, asset["id"])


def _host_label(assets: list[Asset]) -> str | None:
    host = _prefer(assets, "host")
    if host is None:
        return None
    return host["label"]


def _prefer(assets: list[Asset], kind: str) -> Asset | None:
    matches = [asset for asset in assets if asset["type"] == kind]
    if not matches:
        return None
    if kind == "app":
        return max(matches, key=lambda asset: len(asset["label"]))
    return matches[0]


def _first(assets: list[Asset]) -> Asset | None:
    return assets[0] if assets else None


def _last(assets: list[Asset]) -> Asset | None:
    return assets[-1] if assets else None


def _dedupe(assets: list[Asset]) -> list[Asset]:
    seen: set[str] = set()
    unique: list[Asset] = []
    for asset in assets:
        if asset["id"] in seen:
            continue
        seen.add(asset["id"])
        unique.append(asset)
    return unique


def _crosses_boundary(source: dict[str, Any], target: dict[str, Any], lines: list[str]) -> bool:
    left = _match_labels(source)
    right = _match_labels(target)
    for line in lines:
        if _line_mentions(line, left, right) and _line_mentions(line, right, left):
            return True
    return False


def _match_labels(node: dict[str, Any]) -> list[str]:
    label = str(node.get("label", "")).lower()
    labels = [label] if label else []
    host = _host_key({"id": "", "type": str(node.get("type", "")), "label": label})
    if host and host not in labels:
        labels.append(host)
    return labels


def _line_mentions(line: str, labels: list[str], other: list[str]) -> bool:
    others = [item for item in other if item]
    for label in labels:
        if not label or label in others:
            continue
        if _contains_label(line, label):
            return True
    return False


def _contains_label(line: str, label: str) -> bool:
    # A slash keeps going, so "api.internal" does not match inside
    # "api.internal/admin". The boundary has to name the asset itself.
    pattern = re.compile(rf"(?<![\w./-]){re.escape(label)}(?![\w./-])")
    return pattern.search(line) is not None


def _matching_coverage_id(finding: dict[str, Any], entries: list[dict[str, Any]]) -> str:
    for entry in entries:
        surface = _text(entry.get("surface"))
        if surface and _surface_matches(surface, finding):
            return _text(entry.get("entry_id"))
    return ""


def _matching_finding_id(surface: str, findings: list[dict[str, Any]]) -> str | None:
    for finding in findings:
        if _surface_matches(surface, finding):
            return _text(finding.get("id")) or None
    return None


def _surface_matches(surface: str, finding: dict[str, Any]) -> bool:
    surface_norm = _norm(surface)
    if len(surface_norm) < 3:
        return False
    target = _text(finding.get("target"))
    endpoint = _text(finding.get("endpoint"))
    combined = target
    if endpoint.startswith("/"):
        combined = f"{target.rstrip('/')}/{endpoint.lstrip('/')}"
    for candidate in (target, endpoint, combined):
        candidate_norm = _norm(candidate)
        if not candidate_norm:
            continue
        if surface_norm == candidate_norm or surface_norm in candidate_norm:
            return True
        if candidate_norm in surface_norm and len(candidate_norm) >= 3:
            return True
    return False


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text).lower().rstrip("/")


def _short_phrase(text: str, *, fallback: str) -> str:
    cleaned = " ".join(text.split())
    if not cleaned:
        return fallback
    if len(cleaned) <= _LABEL_LIMIT:
        return cleaned
    cut = cleaned[:_LABEL_LIMIT].rsplit(" ", 1)[0].strip()
    return cut or cleaned[:_LABEL_LIMIT]


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug[:80] or "asset"


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _coverage_entries(run_dir: Path) -> list[dict[str, Any]]:
    state_entries = _as_coverage_entries(_load_json(run_dir / ".state" / "coverage.json"))
    if state_entries:
        return state_entries
    return _as_coverage_entries(_load_json(run_dir / "coverage.json"))


def _as_coverage_entries(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        return _rows_from_list(data["entries"])
    if isinstance(data, dict):
        rows: list[dict[str, Any]] = []
        for key, entry in data.items():
            if isinstance(key, str) and isinstance(entry, dict) and _text(entry.get("surface")):
                row = dict(entry)
                row.setdefault("entry_id", key)
                rows.append(row)
        return rows
    if isinstance(data, list):
        return _rows_from_list(data)
    return []


def _rows_from_list(entries: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or not _text(entry.get("surface")):
            continue
        row = dict(entry)
        if not _text(row.get("entry_id")):
            row["entry_id"] = f"cov-{index + 1}"
        rows.append(row)
    return rows


def _notes(run_dir: Path) -> list[tuple[str, dict[str, Any]]]:
    data = _load_json(run_dir / ".state" / "notes.json")
    if not isinstance(data, dict):
        return []
    return [
        (key, note) for key, note in data.items() if isinstance(key, str) and isinstance(note, dict)
    ]


def _threat_models(run_dir: Path) -> list[tuple[str, dict[str, Any]]]:
    data = _load_json(run_dir / ".state" / "threat_models.json")
    if not isinstance(data, dict):
        return []
    return [
        (key, model)
        for key, model in data.items()
        if isinstance(key, str) and isinstance(model, dict)
    ]


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
