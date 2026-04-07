"""On-demand deep repo intelligence and graph-backed evidence generation."""

from __future__ import annotations

import asyncio
import hashlib
import re
import sqlite3
import threading
from collections import defaultdict
from pathlib import Path

from orchestrator.models import (
    RepoDeepDiveRecord,
    RepoDigestAnalyzeRequest,
    RepoGraphAnalyzeRequest,
    RepoGraphCommunityRecord,
    RepoGraphEdgeRecord,
    RepoGraphEvidenceTrail,
    RepoGraphNodeRecord,
    RepoGraphResult,
    RepoGraphStats,
)
from orchestrator.repo_digest import (
    RepoCheckout,
    RepoDigestAnalyzer,
    _clean_fragment,
    _dedupe_keep_order,
    _language_for_path,
    _read_text,
    _walk_files,
)


_GRAPH_SERVICE_CACHE: dict[str, "RepoGraphService"] = {}
_GRAPH_SERVICE_CACHE_LOCK = threading.Lock()

TEST_FILE_PATTERN = re.compile(r"(^|/)(tests?/|test_|.*test\.)", re.IGNORECASE)
PATH_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,}")
API_PATTERNS = {
    "python": [
        re.compile(r"@\s*(?:app|router)\.(?:get|post|put|patch|delete|options|head)\(\s*[\"']([^\"']+)[\"']"),
        re.compile(r"(?:app|router)\.route\(\s*[\"']([^\"']+)[\"']"),
    ],
    "typescript": [
        re.compile(r"(?:app|router)\.(?:get|post|put|patch|delete|options|head)\(\s*[\"']([^\"']+)[\"']"),
        re.compile(r"export\s+async\s+function\s+(?:GET|POST|PUT|PATCH|DELETE)\b"),
    ],
    "javascript": [
        re.compile(r"(?:app|router)\.(?:get|post|put|patch|delete|options|head)\(\s*[\"']([^\"']+)[\"']"),
        re.compile(r"export\s+async\s+function\s+(?:GET|POST|PUT|PATCH|DELETE)\b"),
    ],
}


def _stable_id(prefix: str, *parts: str) -> str:
    joined = "::".join(str(part) for part in parts)
    return f"{prefix}_{hashlib.sha1(joined.encode('utf-8', 'ignore')).hexdigest()[:12]}"


def _tokenize(value: str) -> set[str]:
    return {match.group(0).lower() for match in PATH_TOKEN_PATTERN.finditer(value)}


def _top_package_for_path(relative_path: str) -> str:
    parts = Path(relative_path).parts
    if len(parts) <= 1:
        return "root"
    if parts[0] in {"src", "app", "lib", "packages", "services", "backend", "frontend"} and len(parts) > 2:
        return "/".join(parts[:2])
    return parts[0]


def _import_targets(text: str, language: str | None) -> list[str]:
    if not text:
        return []
    results: list[str] = []
    if language == "Python":
        results.extend(match.group(1) for match in re.finditer(r"^\s*from\s+([A-Za-z0-9_\.]+)\s+import\b", text, re.MULTILINE))
        results.extend(match.group(1) for match in re.finditer(r"^\s*import\s+([A-Za-z0-9_\.]+)", text, re.MULTILINE))
    elif language in {"TypeScript", "JavaScript"}:
        results.extend(match.group(1) for match in re.finditer(r"from\s+[\"']([^\"']+)[\"']", text))
        results.extend(match.group(1) for match in re.finditer(r"require\(\s*[\"']([^\"']+)[\"']\s*\)", text))
    elif language == "Go":
        results.extend(match.group(1) for match in re.finditer(r"import\s+[\"']([^\"']+)[\"']", text))
    elif language == "Rust":
        results.extend(match.group(1) for match in re.finditer(r"^\s*use\s+([^;]+);", text, re.MULTILINE))
    return _dedupe_keep_order(results, limit=24)


def _resolve_import(relative_path: str, target: str, known_files: set[str]) -> str | None:
    current = Path(relative_path)
    if target.startswith("./") or target.startswith("../"):
        candidates = [current.parent / target]
    elif target.startswith("."):
        leading = len(target) - len(target.lstrip("."))
        module = target.lstrip(".")
        ancestor = current.parent
        for _ in range(max(leading - 1, 0)):
            ancestor = ancestor.parent
        module_path = Path(*[part for part in module.split(".") if part]) if module else Path()
        candidates = [ancestor / module_path]
    else:
        module_path = Path(*[part for part in target.replace("::", ".").split(".") if part and part not in {"crate", "self", "super"}])
        candidates = [module_path]

    extensions = ("", ".py", ".ts", ".tsx", ".js", ".jsx", "/__init__.py", "/index.ts", "/index.tsx", "/index.js")
    for candidate in candidates:
        candidate_str = str(candidate).lstrip("./")
        for suffix in extensions:
            probe = f"{candidate_str}{suffix}".replace("\\", "/")
            if probe in known_files:
                return probe
    return None


def _extract_api_specs(relative_path: str, text: str, language: str | None) -> list[dict[str, str]]:
    if not text:
        return []
    patterns = API_PATTERNS.get((language or "").lower(), [])
    output: list[dict[str, str]] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            path = match.group(1) if match.groups() else ""
            if not path and "export async function" in match.group(0):
                method = match.group(0).split()[-1]
                path = f"next:{method}"
            label = path or match.group(0)
            output.append({"label": label, "file": relative_path})
    return output[:10]


class _GraphAccumulator:
    def __init__(self) -> None:
        self.nodes: dict[str, RepoGraphNodeRecord] = {}
        self.edges: dict[str, RepoGraphEdgeRecord] = {}
        self.adjacency: dict[str, set[str]] = defaultdict(set)

    def add_node(
        self,
        kind: str,
        label: str,
        *,
        source_ref: str | None = None,
        weight: float = 1.0,
        metadata: dict[str, object] | None = None,
    ) -> str:
        node_id = _stable_id("node", kind, label, source_ref or "")
        existing = self.nodes.get(node_id)
        if existing is None:
            self.nodes[node_id] = RepoGraphNodeRecord(
                node_id=node_id,
                kind=kind,
                label=label,
                source_ref=source_ref,
                weight=weight,
                metadata=metadata or {},
            )
        else:
            if metadata:
                existing.metadata.update(metadata)
            existing.weight = max(existing.weight, weight)
        return node_id

    def add_edge(
        self,
        kind: str,
        source_node_id: str,
        target_node_id: str,
        *,
        weight: float = 1.0,
        evidence: list[str] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> str:
        edge_id = _stable_id("edge", kind, source_node_id, target_node_id)
        existing = self.edges.get(edge_id)
        if existing is None:
            self.edges[edge_id] = RepoGraphEdgeRecord(
                edge_id=edge_id,
                kind=kind,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                weight=weight,
                evidence=evidence or [],
                metadata=metadata or {},
            )
        else:
            existing.weight = max(existing.weight, weight)
            if evidence:
                existing.evidence = _dedupe_keep_order([*existing.evidence, *evidence], limit=6)
            if metadata:
                existing.metadata.update(metadata)
        self.adjacency[source_node_id].add(target_node_id)
        self.adjacency[target_node_id].add(source_node_id)
        return edge_id


class RepoGraphIndex:
    def __init__(self, db_path: str):
        self._db_path = Path(db_path).expanduser().resolve()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS repo_graph_results (
                    graph_id TEXT PRIMARY KEY,
                    source_key TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    repo_name TEXT NOT NULL,
                    generated_at REAL NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(source_key, source_hash, trigger)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_repo_graph_generated_at ON repo_graph_results(generated_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_repo_graph_source_hash ON repo_graph_results(source_key, source_hash)")

    @staticmethod
    def _decode(payload_json: str) -> RepoGraphResult:
        return RepoGraphResult.model_validate_json(payload_json)

    def get_cached(self, source_key: str, source_hash: str, trigger: str) -> RepoGraphResult | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM repo_graph_results
                WHERE source_key = ? AND source_hash = ? AND trigger = ?
                """,
                (source_key, source_hash, trigger),
            ).fetchone()
        return self._decode(row["payload_json"]) if row else None

    def save_result(self, source_key: str, source_hash: str, result: RepoGraphResult) -> RepoGraphResult:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO repo_graph_results (
                    graph_id, source_key, source_hash, trigger, repo_name, generated_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.graph_id,
                    source_key,
                    source_hash,
                    result.trigger,
                    result.repo_name,
                    float(result.generated_at),
                    result.model_dump_json(),
                ),
            )
        return result

    def list_results(self, limit: int = 50) -> list[RepoGraphResult]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM repo_graph_results
                ORDER BY generated_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._decode(row["payload_json"]) for row in rows]

    def get_result(self, graph_id: str) -> RepoGraphResult | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM repo_graph_results WHERE graph_id = ?",
                (graph_id,),
            ).fetchone()
        return self._decode(row["payload_json"]) if row else None


class RepoGraphAnalyzer:
    def __init__(self) -> None:
        self._digest_analyzer = RepoDigestAnalyzer()

    def checkout(self, request: RepoGraphAnalyzeRequest):
        digest_request = RepoDigestAnalyzeRequest(
            source=request.source,
            branch=request.branch,
            issue_texts=request.issue_texts,
            max_files=request.max_files,
            refresh=request.refresh,
        )
        return self._digest_analyzer.checkout(digest_request)

    def source_hash(self, checkout: RepoCheckout, request: RepoGraphAnalyzeRequest) -> str:
        digest_request = RepoDigestAnalyzeRequest(
            source=request.source,
            branch=request.branch,
            issue_texts=request.issue_texts,
            max_files=request.max_files,
            refresh=request.refresh,
        )
        return self._digest_analyzer.source_hash(checkout, digest_request)

    def analyze_checkout(self, checkout: RepoCheckout, request: RepoGraphAnalyzeRequest, source_hash: str) -> RepoGraphResult:
        digest_request = RepoDigestAnalyzeRequest(
            source=request.source,
            branch=request.branch,
            issue_texts=request.issue_texts,
            max_files=request.max_files,
            refresh=request.refresh,
        )
        digest_result = self._digest_analyzer.analyze_checkout(checkout, digest_request, source_hash)
        files = _walk_files(checkout.repo_root, digest_request)
        selected_files = self._select_files(files, digest_result.digest.hot_files, max_files=request.max_files)
        known_files = set(files)

        graph = _GraphAccumulator()
        repo_node = graph.add_node(
            "repo",
            digest_result.digest.repo_name,
            source_ref=digest_result.digest.source,
            metadata={
                "source_type": digest_result.digest.source_type,
                "branch": digest_result.digest.branch or "",
                "commit_sha": digest_result.digest.commit_sha or source_hash,
            },
        )

        domain_nodes: dict[str, str] = {}
        for domain in digest_result.digest.dominant_domains:
            domain_nodes[domain] = graph.add_node("domain", domain, weight=1.4)
            graph.add_edge("focuses_on", repo_node, domain_nodes[domain], evidence=[domain])

        interest_nodes: dict[str, str] = {}
        for interest in digest_result.profile.repeated_builds:
            interest_nodes[interest] = graph.add_node("founder_interest", interest, weight=1.2)
            graph.add_edge("suggests_interest", repo_node, interest_nodes[interest], evidence=[interest])
            for domain, domain_node_id in domain_nodes.items():
                if _tokenize(interest) & _tokenize(domain):
                    graph.add_edge("aligns_with", interest_nodes[interest], domain_node_id, evidence=[interest, domain])

        claim_nodes: dict[str, str] = {}
        for claim in digest_result.digest.readme_claims:
            claim_node_id = graph.add_node("claim", claim, source_ref="README", weight=1.1)
            claim_nodes[claim] = claim_node_id
            graph.add_edge("asserts", repo_node, claim_node_id, evidence=[claim])
            claim_tokens = _tokenize(claim)
            for domain, domain_node_id in domain_nodes.items():
                if claim_tokens & _tokenize(domain.replace("-", " ")):
                    graph.add_edge("supports", claim_node_id, domain_node_id, evidence=[claim, domain])

        problem_nodes: dict[str, str] = {}
        for theme in digest_result.digest.issue_themes:
            label = theme.label
            problem_node_id = graph.add_node(
                "problem",
                label,
                weight=1.15 + (theme.frequency * 0.05),
                metadata={"evidence": theme.evidence, "frequency": theme.frequency},
            )
            problem_nodes[label] = problem_node_id
            graph.add_edge("exhibits_pain", repo_node, problem_node_id, evidence=theme.evidence[:2], weight=max(theme.frequency, 1))

        package_nodes: dict[str, str] = {}
        file_nodes: dict[str, str] = {}
        api_nodes: dict[str, str] = {}
        hot_file_paths = {item.path: item for item in digest_result.digest.hot_files}
        internal_import_links: list[tuple[str, str, list[str]]] = []

        for relative_path in selected_files:
            language = _language_for_path(relative_path)
            text = _read_text(checkout.repo_root / relative_path, max_bytes=90_000)
            line_count = max(text.count("\n") + 1, 1) if text else 0
            file_weight = 1.0 + (0.25 if relative_path in hot_file_paths else 0.0)
            file_node_id = graph.add_node(
                "file",
                relative_path,
                source_ref=relative_path,
                weight=file_weight,
                metadata={"language": language or "", "line_count": line_count, "is_test": bool(TEST_FILE_PATTERN.search(relative_path))},
            )
            file_nodes[relative_path] = file_node_id

            package_label = _top_package_for_path(relative_path)
            package_node_id = package_nodes.get(package_label)
            if package_node_id is None:
                package_node_id = graph.add_node("package", package_label, source_ref=package_label)
                package_nodes[package_label] = package_node_id
                graph.add_edge("contains", repo_node, package_node_id, evidence=[package_label])
            graph.add_edge("contains", package_node_id, file_node_id, evidence=[relative_path])

            import_targets = _import_targets(text, language)
            for target in import_targets:
                resolved = _resolve_import(relative_path, target, known_files)
                if resolved:
                    internal_import_links.append((relative_path, resolved, [target]))

            for api_spec in _extract_api_specs(relative_path, text, language):
                api_label = api_spec["label"]
                api_node_id = api_nodes.get(api_label)
                if api_node_id is None:
                    api_node_id = graph.add_node("api", api_label, source_ref=relative_path, weight=1.2)
                    api_nodes[api_label] = api_node_id
                graph.add_edge("defines_api", file_node_id, api_node_id, evidence=[api_label])
                for domain, domain_node_id in domain_nodes.items():
                    if _tokenize(api_label) & _tokenize(domain.replace("-", " ")):
                        graph.add_edge("supports", api_node_id, domain_node_id, evidence=[api_label, domain])

            if relative_path in hot_file_paths:
                hot = hot_file_paths[relative_path]
                for reason in hot.reasons:
                    graph.add_edge("hotspot_reason", repo_node, file_node_id, evidence=[reason], weight=hot.importance_score / 10.0)

        for source_path, target_path, evidence in internal_import_links:
            source_node_id = file_nodes.get(source_path)
            target_node_id = file_nodes.get(target_path)
            if source_node_id and target_node_id:
                graph.add_edge("imports", source_node_id, target_node_id, evidence=evidence, weight=1.1)

        for label, problem_node_id in problem_nodes.items():
            problem_tokens = _tokenize(label.replace("-", " "))
            for relative_path, file_node_id in file_nodes.items():
                matched = problem_tokens & _tokenize(relative_path)
                if relative_path in hot_file_paths:
                    matched |= set(hot_file_paths[relative_path].reasons)
                if matched or relative_path in hot_file_paths:
                    graph.add_edge("impacts", problem_node_id, file_node_id, evidence=list(matched)[:2] or [label])
            for domain, domain_node_id in domain_nodes.items():
                if problem_tokens & _tokenize(domain.replace("-", " ")):
                    graph.add_edge("constrains", problem_node_id, domain_node_id, evidence=[label, domain])

        communities = self._build_communities(graph, domain_nodes, claim_nodes, problem_nodes, interest_nodes, api_nodes, file_nodes)
        result = RepoGraphResult(
            source=digest_result.digest.source,
            source_type=digest_result.digest.source_type,
            repo_name=digest_result.digest.repo_name,
            branch=digest_result.digest.branch,
            commit_sha=digest_result.digest.commit_sha or source_hash,
            trigger=request.trigger,
            repo_dna_profile=digest_result.profile,
            nodes=sorted(graph.nodes.values(), key=lambda item: (item.kind, item.label)),
            edges=sorted(graph.edges.values(), key=lambda item: (item.kind, item.source_node_id, item.target_node_id)),
            communities=communities,
            deep_dive=self._build_deep_dive(
                repo_name=digest_result.digest.repo_name,
                graph_id="",
                digest_result=digest_result,
                graph=graph,
                communities=communities,
                domain_nodes=domain_nodes,
                problem_nodes=problem_nodes,
                claim_nodes=claim_nodes,
                interest_nodes=interest_nodes,
            ),
            stats=RepoGraphStats(
                node_count=len(graph.nodes),
                edge_count=len(graph.edges),
                community_count=len(communities),
                api_count=len(api_nodes),
                package_count=len(package_nodes),
                problem_count=len(problem_nodes),
            ),
            warnings=checkout.warnings,
        )
        result.deep_dive.graph_id = result.graph_id
        return result

    def _select_files(self, files: list[str], hot_files: list, max_files: int) -> list[str]:
        selected: list[str] = []
        seen: set[str] = set()
        priority = [
            *(item.path for item in hot_files),
            *[path for path in files if Path(path).name.lower().startswith("readme")],
            *[path for path in files if Path(path).name in {"package.json", "pyproject.toml", "requirements.txt", "go.mod", "Cargo.toml"}],
            *[path for path in files if TEST_FILE_PATTERN.search(path)],
            *[path for path in files if _language_for_path(path) in {"Python", "TypeScript", "JavaScript", "Go", "Rust"}],
        ]
        for path in priority:
            if path in seen or path not in files:
                continue
            seen.add(path)
            selected.append(path)
            if len(selected) >= max(1, min(max_files, 500)):
                break
        return selected

    def _build_communities(
        self,
        graph: _GraphAccumulator,
        domain_nodes: dict[str, str],
        claim_nodes: dict[str, str],
        problem_nodes: dict[str, str],
        interest_nodes: dict[str, str],
        api_nodes: dict[str, str],
        file_nodes: dict[str, str],
    ) -> list[RepoGraphCommunityRecord]:
        communities: list[RepoGraphCommunityRecord] = []
        reverse_lookup = {node_id: node for node_id, node in graph.nodes.items()}
        for domain, domain_node_id in domain_nodes.items():
            related = {domain_node_id, *graph.adjacency.get(domain_node_id, set())}
            related.update(
                neighbor
                for node_id in related.copy()
                for neighbor in graph.adjacency.get(node_id, set())
            )
            related = {node_id for node_id in related if node_id in reverse_lookup}
            related_nodes = [reverse_lookup[node_id] for node_id in related]
            claims = [node.label for node in related_nodes if node.kind == "claim"][:2]
            problems = [node.label for node in related_nodes if node.kind == "problem"][:2]
            apis = [node.label for node in related_nodes if node.kind == "api"][:2]
            files = [node.label for node in related_nodes if node.kind == "file"][:2]
            findings = _dedupe_keep_order(
                [
                    *(f"README claim: {value}" for value in claims),
                    *(f"Pressure point: {value}" for value in problems),
                    *(f"API surface: {value}" for value in apis),
                    *(f"Key file: {value}" for value in files),
                ],
                limit=5,
            )
            score = round((len(related) * 0.1) + (len(problems) * 0.4) + (len(apis) * 0.25), 3)
            communities.append(
                RepoGraphCommunityRecord(
                    community_id=_stable_id("community", domain),
                    title=domain,
                    summary=f"{domain} cluster ties together claims, pain edges, and implementation surfaces.",
                    node_ids=sorted(related),
                    finding_points=findings or [f"{domain} has structural evidence across repo surfaces."],
                    rank_score=score,
                )
            )
        if not communities:
            communities.append(
                RepoGraphCommunityRecord(
                    community_id=_stable_id("community", "repo-core"),
                    title="repo-core",
                    summary="Fallback structural community for the repository core.",
                    node_ids=sorted(graph.nodes.keys())[:24],
                    finding_points=["Graph built without enough domain anchors; inspect hot files and imports."],
                    rank_score=0.1,
                )
            )
        communities.sort(key=lambda item: item.rank_score, reverse=True)
        return communities[:4]

    def _build_deep_dive(
        self,
        *,
        repo_name: str,
        graph_id: str,
        digest_result,
        graph: _GraphAccumulator,
        communities: list[RepoGraphCommunityRecord],
        domain_nodes: dict[str, str],
        problem_nodes: dict[str, str],
        claim_nodes: dict[str, str],
        interest_nodes: dict[str, str],
    ) -> RepoDeepDiveRecord:
        territories = digest_result.profile.adjacent_product_opportunities[:4]
        architectural_focus = _dedupe_keep_order(
            [
                f"Hot files concentrate in {hot.path}" for hot in digest_result.digest.hot_files[:3]
            ]
            + [
                f"Strongest domain cluster: {community.title}" for community in communities[:2]
            ],
            limit=5,
        )
        risk_hotspots = _dedupe_keep_order(
            [
                f"{theme.label}: {', '.join(theme.evidence[:1]) or 'structural risk surfaced in the graph'}"
                for theme in digest_result.digest.issue_themes[:4]
            ]
            + [
                f"{hot.path}: {', '.join(hot.reasons)}" for hot in digest_result.digest.hot_files[:3]
            ],
            limit=6,
        )
        why_now = _dedupe_keep_order(
            [
                f"Pain cluster visible: {theme.label}" for theme in digest_result.digest.issue_themes[:3]
            ]
            + [
                f"README already frames the repo as {claim}" for claim in digest_result.digest.readme_claims[:2]
            ],
            limit=5,
        )
        evidence_trails: list[RepoGraphEvidenceTrail] = []
        edge_lookup = graph.edges
        for territory in territories[:3]:
            tokens = _tokenize(territory)
            supporting_nodes = [
                node.node_id
                for node in graph.nodes.values()
                if tokens & _tokenize(node.label)
                or node.node_id in domain_nodes.values()
                or node.node_id in problem_nodes.values()
            ][:6]
            supporting_edges = [
                edge.edge_id
                for edge in edge_lookup.values()
                if edge.source_node_id in supporting_nodes or edge.target_node_id in supporting_nodes
            ][:8]
            explanation = (
                f"{territory} is backed by domain focus, explicit pain edges, and the repo's implementation surfaces."
            )
            evidence_trails.append(
                RepoGraphEvidenceTrail(
                    trail_id=_stable_id("trail", territory),
                    thesis=territory,
                    explanation=explanation,
                    supporting_node_ids=supporting_nodes,
                    supporting_edge_ids=supporting_edges,
                )
            )
        if not evidence_trails:
            evidence_trails.append(
                RepoGraphEvidenceTrail(
                    trail_id=_stable_id("trail", repo_name),
                    thesis=f"{repo_name} suggests adjacent workflow territory",
                    explanation="The deep graph shows repeated workflow, claim, and pain clusters even without a single dominant opportunity thesis.",
                    supporting_node_ids=list(domain_nodes.values())[:4],
                    supporting_edge_ids=list(edge_lookup.keys())[:6],
                )
            )
        return RepoDeepDiveRecord(
            deep_dive_id=_stable_id("deepdive", repo_name, digest_result.profile.profile_id),
            graph_id=graph_id,
            startup_territories=territories,
            architectural_focus=architectural_focus,
            risk_hotspots=risk_hotspots,
            adjacency_opportunities=digest_result.profile.adjacent_product_opportunities[:4],
            why_now=why_now,
            evidence_trails=evidence_trails,
        )


class RepoGraphService:
    def __init__(self, index: RepoGraphIndex, analyzer: RepoGraphAnalyzer | None = None):
        self._index = index
        self._analyzer = analyzer or RepoGraphAnalyzer()

    async def analyze(self, request: RepoGraphAnalyzeRequest) -> RepoGraphResult:
        return await asyncio.to_thread(self._analyze_sync, request)

    def _analyze_sync(self, request: RepoGraphAnalyzeRequest) -> RepoGraphResult:
        with self._analyzer.checkout(request) as checkout:
            source_hash = self._analyzer.source_hash(checkout, request)
            if not request.refresh:
                cached = self._index.get_cached(checkout.source_key, source_hash, request.trigger)
                if cached is not None:
                    return cached.model_copy(update={"cache_hit": True})
            result = self._analyzer.analyze_checkout(checkout, request, source_hash)
            self._index.save_result(checkout.source_key, source_hash, result)
            return result

    def list_results(self, limit: int = 50) -> list[RepoGraphResult]:
        return self._index.list_results(limit=limit)

    def get_result(self, graph_id: str) -> RepoGraphResult | None:
        return self._index.get_result(graph_id)


def get_repo_graph_service(db_path: str) -> RepoGraphService:
    normalized = str(Path(db_path).expanduser().resolve())
    with _GRAPH_SERVICE_CACHE_LOCK:
        service = _GRAPH_SERVICE_CACHE.get(normalized)
        if service is None:
            service = RepoGraphService(RepoGraphIndex(normalized))
            _GRAPH_SERVICE_CACHE[normalized] = service
        return service


def clear_repo_graph_service_cache() -> None:
    with _GRAPH_SERVICE_CACHE_LOCK:
        _GRAPH_SERVICE_CACHE.clear()
