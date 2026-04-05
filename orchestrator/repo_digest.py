"""Fast repository digest heuristics for RepoDNA extraction.

This layer intentionally stays cheap: it scans the repo tree, README, manifests,
and a handful of high-signal files before any deep graph/indexing work starts.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import subprocess
import tempfile
import tomllib
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

import httpx

from orchestrator.models import (
    RepoDigestAnalyzeRequest,
    RepoDigestResult,
    RepoDigestSummary,
    RepoDNAProfile,
    RepoHotFile,
    RepoIssueTheme,
)


DEFAULT_IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".turbo",
    ".next",
    ".vercel",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".idea",
}
DEFAULT_IGNORED_GLOBS = {
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.webp",
    "*.ico",
    "*.pdf",
    "*.zip",
    "*.tar",
    "*.gz",
    "*.bz2",
    "*.7z",
    "*.mp4",
    "*.mov",
    "*.mp3",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
    "*.class",
    "*.jar",
    "*.lock",
    "*.sqlite",
    "*.sqlite3",
    "*.db",
    "*.pyc",
}
README_CANDIDATES = ("README.md", "readme.md", "README.mdx", "README.rst", "README.txt")
MANIFEST_NAMES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "Pipfile",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "Makefile",
}
SPECIAL_LANGUAGE_NAMES = {
    "dockerfile": "Docker",
    "makefile": "Makefile",
}
LANGUAGE_BY_EXTENSION = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".java": "Java",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".php": "PHP",
    ".cs": "C#",
    ".scala": "Scala",
    ".sql": "SQL",
    ".prisma": "Prisma",
    ".tf": "Terraform",
    ".sh": "Shell",
    ".zsh": "Shell",
    ".bash": "Shell",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    ".md": "Markdown",
    ".mdx": "Markdown",
    ".css": "CSS",
    ".scss": "CSS",
    ".html": "HTML",
}
DEPENDENCY_STACK_ALIASES = {
    "react": "react",
    "next": "next.js",
    "vite": "vite",
    "tailwindcss": "tailwindcss",
    "fastapi": "fastapi",
    "django": "django",
    "flask": "flask",
    "langchain": "langchain",
    "langgraph": "langgraph",
    "openai": "openai",
    "pydantic": "pydantic",
    "sqlalchemy": "sqlalchemy",
    "prisma": "prisma",
    "postgres": "postgres",
    "psycopg": "postgres",
    "redis": "redis",
    "celery": "celery",
    "clickhouse-connect": "clickhouse",
    "neo4j": "neo4j",
    "express": "express",
    "nestjs": "nestjs",
    "electron": "electron",
    "playwright": "playwright",
    "pytest": "pytest",
    "jest": "jest",
    "vitest": "vitest",
    "streamlit": "streamlit",
    "pandas": "pandas",
    "numpy": "numpy",
    "dbt": "dbt",
    "airflow": "airflow",
    "terraform": "terraform",
    "kubernetes": "kubernetes",
    "docker": "docker",
}
DOMAIN_KEYWORDS = {
    "developer-tools": {
        "repo",
        "git",
        "cli",
        "sdk",
        "plugin",
        "tooling",
        "terminal",
        "developer",
        "devtools",
        "code",
    },
    "ai-ml": {
        "ai",
        "agent",
        "llm",
        "model",
        "prompt",
        "openai",
        "langchain",
        "langgraph",
        "rag",
        "embedding",
    },
    "data-analytics": {
        "analytics",
        "dashboard",
        "query",
        "warehouse",
        "insight",
        "metric",
        "data",
        "sql",
        "report",
        "observability",
    },
    "workflow-automation": {
        "workflow",
        "orchestrator",
        "automation",
        "queue",
        "pipeline",
        "task",
        "scheduler",
        "inbox",
        "approval",
    },
    "infrastructure-devops": {
        "docker",
        "terraform",
        "kubernetes",
        "deploy",
        "infra",
        "cloud",
        "helm",
        "ci",
        "runtime",
    },
    "productivity-collaboration": {
        "note",
        "docs",
        "knowledge",
        "meeting",
        "project",
        "team",
        "collaboration",
        "planning",
        "workspace",
    },
}
ISSUE_THEME_KEYWORDS = {
    "onboarding-docs": {"docs", "documentation", "readme", "setup", "install", "example", "guide", "onboard"},
    "integration-friction": {"integration", "connector", "api", "oauth", "webhook", "sync", "import"},
    "reliability-runtime": {"error", "crash", "failed", "failure", "timeout", "retry", "stability", "bug"},
    "performance-scale": {"slow", "performance", "latency", "memory", "scale", "scalability", "throughput"},
    "deployment-config": {"deploy", "deployment", "docker", "config", "environment", "build", "infra"},
    "data-quality": {"data", "schema", "migration", "parsing", "duplicate", "consistency", "indexing"},
    "ux-polish": {"ui", "ux", "design", "layout", "accessibility", "mobile"},
    "testing-gaps": {"test", "coverage", "flaky", "ci", "regression"},
}
THEME_DESCRIPTIONS = {
    "onboarding-docs": "onboarding and documentation drag",
    "integration-friction": "integration and connector friction",
    "reliability-runtime": "runtime reliability edges",
    "performance-scale": "performance and scale bottlenecks",
    "deployment-config": "deployment and configuration drag",
    "data-quality": "data quality and indexing churn",
    "ux-polish": "UI and workflow polish debt",
    "testing-gaps": "testing and regression coverage gaps",
}


@dataclass(slots=True)
class RepoCheckout:
    source: str
    source_key: str
    source_type: str
    repo_root: Path
    repo_name: str
    branch: str | None
    commit_sha: str | None
    owner_repo: str | None = None
    warnings: list[str] = field(default_factory=list)
    temp_dir: tempfile.TemporaryDirectory[str] | None = None


def _run_command(args: list[str], cwd: Path | None = None) -> str | None:
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def _clean_fragment(text: str) -> str:
    value = re.sub(r"\s+", " ", text.strip())
    return value.strip(" -*#`>:")


def _dedupe_keep_order(items: list[str], limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(normalized)
        if limit is not None and len(output) >= limit:
            break
    return output


def _parse_github_source(source: str) -> tuple[str, str, str | None] | None:
    value = source.strip().removesuffix(".git")
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc.lower().endswith("github.com"):
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            return None
        owner_repo = f"{parts[0]}/{parts[1]}"
        branch = None
        if len(parts) >= 4 and parts[2] == "tree":
            branch = "/".join(parts[3:])
        return f"https://github.com/{owner_repo}", owner_repo, branch
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        return f"https://github.com/{value}", value, None
    return None


def _language_for_path(relative_path: str) -> str | None:
    name = Path(relative_path).name
    special = SPECIAL_LANGUAGE_NAMES.get(name.lower())
    if special:
        return special
    return LANGUAGE_BY_EXTENSION.get(Path(relative_path).suffix.lower())


def _is_git_repo(repo_root: Path) -> bool:
    return bool(_run_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_root))


def _git_value(repo_root: Path, *args: str) -> str | None:
    return _run_command(["git", *args], cwd=repo_root)


def _is_ignored(relative_path: str, include_patterns: list[str], exclude_patterns: list[str]) -> bool:
    parts = Path(relative_path).parts
    if any(part in DEFAULT_IGNORED_DIRS for part in parts[:-1]):
        return True
    if any(fnmatch.fnmatch(relative_path, pattern) for pattern in DEFAULT_IGNORED_GLOBS):
        return True
    if any(fnmatch.fnmatch(relative_path, pattern) for pattern in exclude_patterns):
        return True
    if include_patterns and not any(fnmatch.fnmatch(relative_path, pattern) for pattern in include_patterns):
        return True
    return False


def _walk_files(repo_root: Path, request: RepoDigestAnalyzeRequest) -> list[str]:
    if _is_git_repo(repo_root):
        listing = _git_value(repo_root, "ls-files", "-co", "--exclude-standard")
        if listing is not None:
            candidates = [line.strip() for line in listing.splitlines() if line.strip()]
            return sorted(
                rel_path
                for rel_path in candidates
                if not _is_ignored(rel_path, request.include_patterns, request.exclude_patterns)
            )
    output: list[str] = []
    for current_root, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [name for name in dirnames if name not in DEFAULT_IGNORED_DIRS]
        for filename in filenames:
            full_path = Path(current_root) / filename
            rel_path = str(full_path.relative_to(repo_root))
            if _is_ignored(rel_path, request.include_patterns, request.exclude_patterns):
                continue
            output.append(rel_path)
    output.sort()
    return output


def _compute_source_hash(repo_root: Path, files: list[str]) -> str:
    commit_sha = _git_value(repo_root, "rev-parse", "HEAD")
    if commit_sha:
        return commit_sha
    digest = hashlib.sha256()
    for relative_path in files[:1000]:
        file_path = repo_root / relative_path
        try:
            stat_result = file_path.stat()
        except OSError:
            continue
        digest.update(relative_path.encode("utf-8", "ignore"))
        digest.update(str(stat_result.st_size).encode("ascii", "ignore"))
        digest.update(str(stat_result.st_mtime_ns).encode("ascii", "ignore"))
    return digest.hexdigest()


def _read_text(file_path: Path, max_bytes: int = 120_000) -> str:
    try:
        raw = file_path.read_bytes()[:max_bytes]
    except OSError:
        return ""
    return raw.decode("utf-8", errors="ignore")


def _extract_readme_claims(readme_text: str) -> list[str]:
    lines = [_clean_fragment(line) for line in readme_text.splitlines()]
    candidates: list[str] = []
    for line in lines[:120]:
        lower = line.lower()
        if len(line) < 18:
            continue
        if any(keyword in lower for keyword in ("build", "tool", "platform", "autom", "orchestr", "workflow", "discover", "analy")):
            candidates.append(line)
        elif line.startswith(("Provides ", "Generate ", "Turn ", "Create ", "Analyze ")):
            candidates.append(line)
    if not candidates:
        paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", readme_text) if segment.strip()]
        for paragraph in paragraphs[:3]:
            sentences = re.split(r"(?<=[.!?])\s+", paragraph)
            candidates.extend(_clean_fragment(sentence) for sentence in sentences[:2])
    return _dedupe_keep_order(candidates, limit=5)


def _extract_dependencies(repo_root: Path, manifest_paths: list[str]) -> tuple[list[str], list[str]]:
    stack: list[str] = []
    dependency_names: list[str] = []
    for relative_path in manifest_paths:
        path = repo_root / relative_path
        name = Path(relative_path).name
        if name == "package.json":
            try:
                payload = json.loads(_read_text(path))
            except json.JSONDecodeError:
                continue
            for section in ("dependencies", "devDependencies", "peerDependencies"):
                for dependency in (payload.get(section) or {}).keys():
                    dependency_names.append(str(dependency))
        elif name == "pyproject.toml":
            try:
                payload = tomllib.loads(_read_text(path))
            except tomllib.TOMLDecodeError:
                continue
            for dependency in payload.get("project", {}).get("dependencies", []) or []:
                dependency_names.append(str(dependency).split()[0])
            poetry_deps = payload.get("tool", {}).get("poetry", {}).get("dependencies", {})
            dependency_names.extend(str(dep) for dep in poetry_deps.keys())
        elif name in {"requirements.txt", "requirements-dev.txt"}:
            for line in _read_text(path).splitlines():
                cleaned = line.split("#", 1)[0].strip()
                if not cleaned:
                    continue
                dependency_names.append(re.split(r"[<>=~!\[]", cleaned)[0])
        elif name == "Cargo.toml":
            try:
                payload = tomllib.loads(_read_text(path))
            except tomllib.TOMLDecodeError:
                continue
            dependency_names.extend(str(dep) for dep in (payload.get("dependencies") or {}).keys())
        elif name == "go.mod":
            dependency_names.extend(
                match.group(1)
                for match in re.finditer(r"^\s*([A-Za-z0-9_.\-/]+)\s+v[0-9]", _read_text(path), re.MULTILINE)
            )

        lower_name = name.lower()
        if lower_name == "dockerfile" or "docker-compose" in lower_name or lower_name in {"compose.yml", "compose.yaml"}:
            stack.append("docker")
        if lower_name == "makefile":
            stack.append("make")

    for dependency in dependency_names:
        lower = dependency.lower()
        for marker, label in DEPENDENCY_STACK_ALIASES.items():
            if marker in lower:
                stack.append(label)
    return _dedupe_keep_order(stack, limit=12), _dedupe_keep_order(dependency_names, limit=40)


def _build_tree_preview(files: list[str], limit: int = 40) -> list[str]:
    lines: list[str] = []
    seen_dirs: set[str] = set()
    for relative_path in files:
        parts = Path(relative_path).parts
        if not parts:
            continue
        for depth, part in enumerate(parts[:-1]):
            dir_key = "/".join(parts[: depth + 1]) + "/"
            if dir_key in seen_dirs:
                continue
            seen_dirs.add(dir_key)
            lines.append(f"{'  ' * depth}{part}/")
            if len(lines) >= limit:
                return lines
        lines.append(f"{'  ' * (len(parts) - 1)}{parts[-1]}")
        if len(lines) >= limit:
            return lines
    return lines


def _count_imports(text: str, language: str | None) -> int:
    if not text:
        return 0
    if language in {"Python"}:
        return len(re.findall(r"^\s*(from\s+\S+\s+import|import\s+\S+)", text, re.MULTILINE))
    if language in {"TypeScript", "JavaScript"}:
        return len(re.findall(r"^\s*(import\s+.+?\s+from\s+['\"]|const\s+.+?=\s+require\()", text, re.MULTILINE))
    if language in {"Go"}:
        return len(re.findall(r"^\s*import\s+(\(|\"[^\"]+\")", text, re.MULTILINE))
    if language in {"Rust"}:
        return len(re.findall(r"^\s*use\s+\S+", text, re.MULTILINE))
    return 0


def _extract_todo_fragments(repo_root: Path, candidate_paths: list[str], limit: int = 10) -> list[str]:
    snippets: list[str] = []
    for relative_path in candidate_paths:
        if len(snippets) >= limit:
            break
        text = _read_text(repo_root / relative_path, max_bytes=50_000)
        for line in text.splitlines():
            if re.search(r"\b(TODO|FIXME|HACK|BUG)\b", line):
                snippets.append(f"{relative_path}: {_clean_fragment(line)}")
                if len(snippets) >= limit:
                    break
    return snippets


def _build_hot_files(repo_root: Path, files: list[str], limit: int) -> list[RepoHotFile]:
    scored: list[RepoHotFile] = []
    for relative_path in files:
        file_path = repo_root / relative_path
        language = _language_for_path(relative_path)
        text = _read_text(file_path, max_bytes=80_000)
        if not text:
            continue
        line_count = max(text.count("\n") + 1, 1)
        import_count = _count_imports(text, language)
        todo_count = len(re.findall(r"\b(TODO|FIXME|HACK|BUG)\b", text))
        is_entrypoint = Path(relative_path).name.lower() in {
            "main.py",
            "app.py",
            "server.py",
            "index.ts",
            "index.tsx",
            "main.ts",
            "main.tsx",
            "cli.py",
        }
        manifest_bonus = 8 if Path(relative_path).name in MANIFEST_NAMES else 0
        readme_bonus = 12 if Path(relative_path).name in README_CANDIDATES else 0
        score = (
            min(line_count / 12.0, 18.0)
            + (import_count * 1.8)
            + (todo_count * 2.5)
            + (6 if is_entrypoint else 0)
            + manifest_bonus
            + readme_bonus
        )
        reasons: list[str] = []
        if is_entrypoint:
            reasons.append("entrypoint")
        if manifest_bonus:
            reasons.append("manifest")
        if readme_bonus:
            reasons.append("readme")
        if line_count >= 180:
            reasons.append("large-file")
        if import_count >= 6:
            reasons.append("high-import-fan-in")
        if todo_count:
            reasons.append("open-todos")
        if not reasons:
            reasons.append("central-surface")
        scored.append(
            RepoHotFile(
                path=relative_path,
                language=language,
                line_count=line_count,
                importance_score=round(score, 2),
                reasons=reasons,
            )
        )
    scored.sort(key=lambda item: item.importance_score, reverse=True)
    return scored[:limit]


def _infer_domains(fragments: list[str], tech_stack: list[str]) -> list[str]:
    counter: Counter[str] = Counter()
    for fragment in fragments:
        lowered = fragment.lower()
        for label, keywords in DOMAIN_KEYWORDS.items():
            hits = sum(1 for keyword in keywords if keyword in lowered)
            if hits:
                counter[label] += hits
    for label in tech_stack:
        lowered = label.lower()
        if lowered in {"react", "next.js", "vite"}:
            counter["developer-tools"] += 1
        if lowered in {"openai", "langchain", "langgraph"}:
            counter["ai-ml"] += 2
        if lowered in {"clickhouse", "postgres", "dbt"}:
            counter["data-analytics"] += 1
        if lowered in {"docker", "terraform", "kubernetes"}:
            counter["infrastructure-devops"] += 1
    if not counter:
        return ["developer-tools"]
    return [label for label, _score in counter.most_common(3)]


def _extract_issue_themes(issue_texts: list[str], todo_fragments: list[str], readme_claims: list[str]) -> list[RepoIssueTheme]:
    evidence_inputs = [text for text in issue_texts + todo_fragments if text.strip()]
    if not evidence_inputs:
        evidence_inputs = readme_claims
    themes: list[RepoIssueTheme] = []
    for label, keywords in ISSUE_THEME_KEYWORDS.items():
        matched = [fragment for fragment in evidence_inputs if any(keyword in fragment.lower() for keyword in keywords)]
        if matched:
            themes.append(
                RepoIssueTheme(
                    label=label,
                    frequency=len(matched),
                    evidence=_dedupe_keep_order([_clean_fragment(item) for item in matched], limit=3),
                )
            )
    themes.sort(key=lambda item: item.frequency, reverse=True)
    return themes[:4]


def _infer_complexity(file_count: int, language_count: int, tech_stack_size: int, domain_count: int) -> str:
    score = 0
    if file_count >= 40:
        score += 1
    if file_count >= 120:
        score += 1
    if language_count >= 3:
        score += 1
    if tech_stack_size >= 6:
        score += 1
    if domain_count >= 3:
        score += 1
    if score <= 1:
        return "low"
    if score <= 3:
        return "medium"
    if score <= 4:
        return "high"
    return "very_high"


def _repeated_builds(domains: list[str], tech_stack: list[str]) -> list[str]:
    hints: list[str] = []
    if "developer-tools" in domains:
        hints.append("repo-aware developer tooling and operator utilities")
    if "workflow-automation" in domains:
        hints.append("workflow orchestration, routing, and automation loops")
    if "data-analytics" in domains:
        hints.append("evidence dashboards and structured insight surfaces")
    if "ai-ml" in domains:
        hints.append("LLM-assisted research or orchestration layers")
    if "react" in tech_stack and "fastapi" in tech_stack:
        hints.append("typed full-stack products with a clear API seam")
    if not hints:
        hints.append("narrow workflow products around a concrete operator job")
    return _dedupe_keep_order(hints, limit=4)


def _avoids(digest: RepoDigestSummary, tech_stack: list[str], test_file_count: int) -> list[str]:
    avoided: list[str] = []
    if not any(label in tech_stack for label in {"react", "next.js", "tailwindcss"}):
        avoided.append("pixel-heavy frontend surface area")
    if "infrastructure-devops" not in digest.dominant_domains:
        avoided.append("deep platform and infra-heavy bets")
    if test_file_count <= 2:
        avoided.append("large upfront regression harnesses before proving the core loop")
    if digest.file_count < 20:
        avoided.append("broad multi-product platforms")
    return _dedupe_keep_order(avoided, limit=3)


def _adjacent_buyer_pain(recurring_pain_areas: list[str]) -> list[str]:
    output: list[str] = []
    for area in recurring_pain_areas:
        description = THEME_DESCRIPTIONS.get(area, area.replace("-", " "))
        output.append(f"teams lose time to {description}")
    if not output:
        output.append("operators need less manual context stitching between tools")
    return _dedupe_keep_order(output, limit=4)


def _adjacent_opportunities(domains: list[str], recurring_pain_areas: list[str]) -> list[str]:
    output: list[str] = []
    if "developer-tools" in domains and "onboarding-docs" in recurring_pain_areas:
        output.append("developer onboarding copilots that convert repos into compact working context")
    if "workflow-automation" in domains and "integration-friction" in recurring_pain_areas:
        output.append("workflow integration control planes with typed connector health and approvals")
    if "data-analytics" in domains and "data-quality" in recurring_pain_areas:
        output.append("evidence pipelines that keep analytics and sourcing signals trustworthy")
    if "ai-ml" in domains and "reliability-runtime" in recurring_pain_areas:
        output.append("operational safety rails for agentic or LLM-backed automations")
    if not output:
        output.append("adjacent workflow products that remove repeated operator context assembly")
    return _dedupe_keep_order(output, limit=4)


def _build_profile(digest: RepoDigestSummary, tech_stack: list[str], test_file_count: int) -> RepoDNAProfile:
    recurring_pain_areas = [theme.label for theme in digest.issue_themes]
    repeated_builds = _repeated_builds(digest.dominant_domains, tech_stack)
    avoids = _avoids(digest, tech_stack, test_file_count)
    breaks_often = [
        THEME_DESCRIPTIONS.get(theme.label, theme.label.replace("-", " "))
        for theme in digest.issue_themes
    ] or ["integration edges between moving parts"]
    adjacent_buyer_pain = _adjacent_buyer_pain(recurring_pain_areas)
    adjacent_product_opportunities = _adjacent_opportunities(digest.dominant_domains, recurring_pain_areas)
    idea_generation_context = "\n".join(
        [
            f"Repo: {digest.repo_name}",
            f"Domains: {', '.join(digest.dominant_domains)}",
            f"Tech stack: {', '.join(digest.tech_stack[:8])}",
            f"Repeated builds: {', '.join(repeated_builds)}",
            f"Pain areas: {', '.join(THEME_DESCRIPTIONS.get(area, area.replace('-', ' ')) for area in recurring_pain_areas) or 'workflow friction'}",
            f"Hot files: {', '.join(file.path for file in digest.hot_files[:4])}",
        ]
    )
    ranking_priors = _dedupe_keep_order(
        [
            f"Prefer ideas that compound {digest.dominant_domains[0]} strengths into a sellable workflow edge."
            if digest.dominant_domains
            else "",
            f"Bias toward pains already visible in repo evidence: {', '.join(adjacent_buyer_pain[:2])}.",
            "Prefer adjacent opportunities that reuse the current stack before proposing a greenfield platform.",
            "Down-rank ideas that require a completely different buyer, stack, or complexity class.",
        ],
        limit=4,
    )
    swipe_explanation_points = _dedupe_keep_order(
        [
            f"This matches the founder's repeated build pattern: {repeated_builds[0]}.",
            f"The repo already shows evidence for {adjacent_buyer_pain[0]}.",
            f"Hot files cluster around {', '.join(file.path for file in digest.hot_files[:2])}.",
            f"README and issue evidence point toward {adjacent_product_opportunities[0]}.",
        ],
        limit=4,
    )
    return RepoDNAProfile(
        source=digest.source,
        repo_name=digest.repo_name,
        languages=list(digest.languages.keys())[:6],
        domain_clusters=digest.dominant_domains,
        preferred_complexity=_infer_complexity(
            file_count=digest.file_count,
            language_count=len(digest.languages),
            tech_stack_size=len(digest.tech_stack),
            domain_count=len(digest.dominant_domains),
        ),
        recurring_pain_areas=recurring_pain_areas,
        adjacent_product_opportunities=adjacent_product_opportunities,
        repeated_builds=repeated_builds,
        avoids=avoids,
        breaks_often=breaks_often[:4],
        adjacent_buyer_pain=adjacent_buyer_pain,
        idea_generation_context=idea_generation_context,
        ranking_priors=ranking_priors,
        swipe_explanation_points=swipe_explanation_points,
    )


class RepoDigestAnalyzer:
    """Fast digest path inspired by gitingest, repomix, repo-map, and autoresearch."""

    @contextmanager
    def checkout(self, request: RepoDigestAnalyzeRequest) -> Iterator[RepoCheckout]:
        source = request.source.strip()
        source_path = Path(source).expanduser()
        if source_path.exists() and source_path.is_dir():
            repo_root = source_path.resolve()
            yield RepoCheckout(
                source=source,
                source_key=str(repo_root),
                source_type="local",
                repo_root=repo_root,
                repo_name=repo_root.name,
                branch=_git_value(repo_root, "rev-parse", "--abbrev-ref", "HEAD"),
                commit_sha=_git_value(repo_root, "rev-parse", "HEAD"),
            )
            return

        github_source = _parse_github_source(source)
        if github_source is None:
            raise ValueError(f"Unsupported repo source: {source}")

        clone_url, owner_repo, source_branch = github_source
        temp_dir = tempfile.TemporaryDirectory(prefix="quorum-repodna-")
        branch = request.branch or source_branch
        clone_args = ["git", "clone", "--depth", "1", "--filter=blob:none"]
        if branch:
            clone_args.extend(["--branch", branch])
        clone_args.extend([clone_url, temp_dir.name])
        result = subprocess.run(clone_args, capture_output=True, text=True)
        if result.returncode != 0:
            temp_dir.cleanup()
            raise ValueError(result.stderr.strip() or f"Failed to clone {clone_url}")

        repo_root = Path(temp_dir.name).resolve()
        try:
            yield RepoCheckout(
                source=clone_url,
                source_key=clone_url,
                source_type="github",
                repo_root=repo_root,
                repo_name=owner_repo.split("/", 1)[1],
                branch=branch or _git_value(repo_root, "rev-parse", "--abbrev-ref", "HEAD"),
                commit_sha=_git_value(repo_root, "rev-parse", "HEAD"),
                owner_repo=owner_repo,
                temp_dir=temp_dir,
            )
        finally:
            temp_dir.cleanup()

    def analyze_checkout(
        self,
        checkout: RepoCheckout,
        request: RepoDigestAnalyzeRequest,
        source_hash: str,
    ) -> RepoDigestResult:
        files = _walk_files(checkout.repo_root, request)
        language_counter: Counter[str] = Counter()
        for relative_path in files:
            language = _language_for_path(relative_path)
            if language:
                language_counter[language] += 1

        readme_path = next((path for path in files if Path(path).name in README_CANDIDATES), None)
        manifest_paths = [
            path
            for path in files
            if Path(path).name in MANIFEST_NAMES or Path(path).name.lower() in SPECIAL_LANGUAGE_NAMES
        ]
        candidate_source_paths = [
            path
            for path in files
            if _language_for_path(path) not in {None, "Markdown", "JSON", "YAML", "TOML"}
        ][: max(request.max_files, request.hot_file_limit * 4)]
        hot_files = _build_hot_files(
            checkout.repo_root,
            [path for path in [readme_path, *manifest_paths, *candidate_source_paths] if path],
            limit=max(1, request.hot_file_limit),
        )
        readme_text = _read_text(checkout.repo_root / readme_path) if readme_path else ""
        readme_claims = _extract_readme_claims(readme_text)
        tech_stack, dependency_names = _extract_dependencies(checkout.repo_root, manifest_paths)
        for language, _count in language_counter.most_common(4):
            tech_stack.append(language.lower())
        tech_stack = _dedupe_keep_order(tech_stack, limit=12)

        issue_texts = list(request.issue_texts)
        if not issue_texts and checkout.owner_repo and request.issue_limit > 0:
            fetched, warning = self._fetch_github_issue_texts(checkout.owner_repo, request.issue_limit)
            issue_texts.extend(fetched)
            if warning:
                checkout.warnings.append(warning)

        todo_fragments = _extract_todo_fragments(
            checkout.repo_root,
            [item.path for item in hot_files if item.language not in {"Markdown", "JSON"}],
        )
        issue_themes = _extract_issue_themes(issue_texts, todo_fragments, readme_claims)
        dominant_domains = _infer_domains(
            [
                checkout.repo_name,
                *readme_claims,
                *dependency_names,
                *issue_texts,
                *todo_fragments,
                *[file.path for file in hot_files],
            ],
            tech_stack=tech_stack,
        )
        key_paths = _dedupe_keep_order(
            [path for path in [readme_path, *manifest_paths, *[file.path for file in hot_files]] if path],
            limit=12,
        )
        test_file_count = len([path for path in files if re.search(r"(^|/)(test_|tests?/|.*test\.)", path.lower())])
        digest = RepoDigestSummary(
            source=checkout.source,
            source_type=checkout.source_type,
            repo_name=checkout.repo_name,
            repo_root=str(checkout.repo_root) if checkout.source_type == "local" else None,
            branch=checkout.branch,
            commit_sha=checkout.commit_sha or source_hash,
            tree_preview=_build_tree_preview(files[: max(request.max_files, 80)], limit=42),
            languages={language: count for language, count in language_counter.most_common(8)},
            tech_stack=tech_stack,
            dominant_domains=dominant_domains,
            readme_claims=readme_claims,
            issue_themes=issue_themes,
            hot_files=hot_files,
            key_paths=key_paths,
            file_count=len(files),
        )
        profile = _build_profile(digest, tech_stack=tech_stack, test_file_count=test_file_count)
        return RepoDigestResult(digest=digest, profile=profile, warnings=checkout.warnings)

    def source_hash(self, checkout: RepoCheckout, request: RepoDigestAnalyzeRequest) -> str:
        return _compute_source_hash(checkout.repo_root, _walk_files(checkout.repo_root, request))

    def _fetch_github_issue_texts(self, owner_repo: str, limit: int) -> tuple[list[str], str | None]:
        url = f"https://api.github.com/repos/{owner_repo}/issues"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "quorum-repodna",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        try:
            response = httpx.get(
                url,
                headers=headers,
                params={"state": "open", "per_page": max(1, min(limit, 20))},
                timeout=10.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return [], f"GitHub issue fetch skipped: {exc}"
        payload = response.json()
        items: list[str] = []
        for issue in payload:
            if issue.get("pull_request"):
                continue
            title = _clean_fragment(str(issue.get("title") or ""))
            body = _clean_fragment(str(issue.get("body") or ""))
            combined = f"{title}. {body}".strip(". ")
            if combined:
                items.append(combined)
        return _dedupe_keep_order(items, limit=limit), None
