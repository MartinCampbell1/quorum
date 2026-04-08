"""Founder GitHub bootstrap pipeline orchestrator.

Runs a portfolio-level analysis over a founder's public GitHub repos to infer
interest clusters, synthesise a founder profile, and seed initial opportunity
hypotheses — without requiring the founder to answer any intake questions.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections import Counter, defaultdict
from typing import Any

import httpx

from orchestrator.models_bootstrap import (
    FounderBootstrapRequest,
    FounderBootstrapResponse,
    FounderProfileSynthesis,
    InterestCluster,
    OpportunityHypothesis,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GitHub portfolio client
# ---------------------------------------------------------------------------


class GitHubPortfolioClient:
    """Lists public repositories for a GitHub user via the REST API."""

    API_BASE = "https://api.github.com"

    def __init__(self, token: str | None = None) -> None:
        self.token = (token or "").strip()

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def list_repos(
        self,
        username: str,
        *,
        max_repos: int = 100,
        include_forks: bool = False,
        include_archived: bool = False,
    ) -> list[dict]:
        """Fetch public repos for *username*, paginating up to *max_repos*."""
        repos: list[dict] = []
        page = 1
        per_page = min(max_repos, 100)

        async with httpx.AsyncClient(timeout=30.0) as client:
            while len(repos) < max_repos:
                url = f"{self.API_BASE}/users/{username}/repos"
                params = {
                    "type": "owner",
                    "sort": "updated",
                    "direction": "desc",
                    "per_page": per_page,
                    "page": page,
                }
                response = await client.get(url, params=params, headers=self._headers())
                response.raise_for_status()
                batch = response.json()
                if not batch:
                    break

                for repo in batch:
                    if not include_forks and repo.get("fork", False):
                        continue
                    if not include_archived and repo.get("archived", False):
                        continue
                    repos.append(repo)
                    if len(repos) >= max_repos:
                        break

                page += 1

        return repos


def get_github_portfolio_client() -> GitHubPortfolioClient:
    """Return a GitHubPortfolioClient with an optional token for public GitHub access."""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    return GitHubPortfolioClient(token=token or None)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class FounderBootstrapPipeline:
    """Portfolio-level orchestrator for the founder GitHub bootstrap flow."""

    # Topics that map 1:1 to a programming language — used only for enrichment,
    # not as standalone cluster labels.
    _LANGUAGE_TOPICS = {
        "python", "javascript", "typescript", "ruby", "go", "golang",
        "rust", "java", "kotlin", "swift", "c", "cpp", "c++", "csharp",
        "haskell", "scala", "elixir", "erlang", "clojure", "lua",
        "r", "matlab", "php", "perl", "bash", "shell",
    }

    # ---------------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------------

    def _build_inventory(self, raw_repos: list[dict]) -> list[dict]:
        """Normalise raw GitHub API repo payloads into a minimal inventory list."""
        inventory: list[dict] = []
        for repo in raw_repos:
            inventory.append(
                {
                    "name": repo.get("name") or repo.get("full_name", ""),
                    "full_name": repo.get("full_name", ""),
                    "html_url": repo.get("html_url", ""),
                    "description": repo.get("description") or "",
                    "topics": list(repo.get("topics") or []),
                    "language": repo.get("language") or "",
                    "stargazers_count": int(repo.get("stargazers_count") or 0),
                    "fork": bool(repo.get("fork", False)),
                    "archived": bool(repo.get("archived", False)),
                }
            )
        return inventory

    def _cluster_by_theme(self, inventory: list[dict]) -> list[InterestCluster]:
        """Group repos into interest clusters by shared topic tags.

        Algorithm:
        1. Build topic -> [repo_name, ...] mapping from every repo's topics list.
        2. Sort by cluster size descending.
        3. Skip language-only topics (they serve as enrichment signals, not themes).
        4. Assign strength = min(cluster_repo_count / total_repos, 1.0).
        5. Track seen repos so a repo only appears in its most prominent cluster.
        """
        total_repos = len(inventory)
        if total_repos == 0:
            return []

        topic_to_repos: dict[str, list[str]] = defaultdict(list)
        for repo in inventory:
            repo_name = repo["name"]
            for topic in repo.get("topics") or []:
                topic_to_repos[topic].append(repo_name)

        # Sort topics by number of associated repos (largest clusters first)
        sorted_topics = sorted(
            topic_to_repos.items(), key=lambda kv: len(kv[1]), reverse=True
        )

        clusters: list[InterestCluster] = []
        seen_repos: set[str] = set()

        for topic, repo_names in sorted_topics:
            # Skip pure language topics
            if topic.lower() in self._LANGUAGE_TOPICS:
                continue

            # Only include repos not yet assigned to an earlier (larger) cluster
            new_repos = [r for r in repo_names if r not in seen_repos]
            if not new_repos:
                continue

            seen_repos.update(new_repos)

            # Gather languages for all repos in this cluster
            languages: list[str] = []
            for repo in inventory:
                if repo["name"] in new_repos and repo.get("language"):
                    lang = repo["language"]
                    if lang not in languages:
                        languages.append(lang)

            strength = min(len(new_repos) / total_repos, 1.0)

            clusters.append(
                InterestCluster(
                    cluster_id=str(uuid.uuid4()),
                    label=topic,
                    repos=new_repos,
                    topics=[topic],
                    languages=languages,
                    strength=strength,
                )
            )

        return clusters

    async def _deep_scan_repos(
        self,
        deep_scan_repos: list[dict],
        repo_digest: Any,
    ) -> list[Any]:
        """Run repo-digest analysis on top repos and return RepoDNAProfiles."""
        from orchestrator.models import RepoDigestAnalyzeRequest

        profiles: list[Any] = []
        for repo in deep_scan_repos:
            source = repo.get("html_url") or repo.get("full_name") or repo.get("name")
            if not source:
                continue
            try:
                request = RepoDigestAnalyzeRequest(source=source, refresh=False)
                with repo_digest.checkout(request) as checkout:
                    source_hash = checkout.commit_sha or checkout.source_key
                    result = repo_digest.analyze_checkout(checkout, request, source_hash)
                    profiles.append(result.profile)
            except Exception as exc:
                logger.warning("Deep scan failed for %s: %s", source, exc)
        return profiles

    def _synthesise_profile(
        self,
        inventory: list[dict],
        clusters: list[InterestCluster],
        deep_profiles: list[Any],
    ) -> FounderProfileSynthesis:
        """Build a synthesis from inventory, clusters, and deep-scanned profiles."""
        all_topics: list[str] = []
        all_languages: list[str] = []
        for repo in inventory:
            for topic in repo.get("topics") or []:
                if topic not in all_topics:
                    all_topics.append(topic)
            lang = repo.get("language") or ""
            if lang and lang not in all_languages:
                all_languages.append(lang)

        # Aggregate deep-scan signals
        all_pain_areas: list[str] = []
        all_opportunities: list[str] = []
        all_repeated_builds: list[str] = []
        all_buyer_pain: list[str] = []
        all_domain_clusters: list[str] = []
        all_wedges: list[str] = []

        for profile in deep_profiles:
            for item in getattr(profile, "recurring_pain_areas", []):
                if item and item not in all_pain_areas:
                    all_pain_areas.append(item)
            for item in getattr(profile, "adjacent_product_opportunities", []):
                if item and item not in all_opportunities:
                    all_opportunities.append(item)
            for item in getattr(profile, "repeated_builds", []):
                if item and item not in all_repeated_builds:
                    all_repeated_builds.append(item)
            for item in getattr(profile, "adjacent_buyer_pain", []):
                if item and item not in all_buyer_pain:
                    all_buyer_pain.append(item)
            for item in getattr(profile, "domain_clusters", []):
                if item and item not in all_domain_clusters:
                    all_domain_clusters.append(item)

        # Derive distribution wedges from dominant domain clusters + languages
        if all_domain_clusters:
            top_domains = all_domain_clusters[:3]
            all_wedges = [f"GitHub-native {d} workflows" for d in top_domains]

        # Unfair advantages from language depth + repeat patterns
        unfair_advantages: list[str] = []
        lang_counter = Counter(repo.get("language") or "" for repo in inventory if repo.get("language"))
        for lang, count in lang_counter.most_common(3):
            if count >= 2:
                unfair_advantages.append(f"Deep {lang} expertise ({count} repos)")

        # Likely ICPs from pain areas and opportunities
        likely_icps: list[str] = []
        if all_pain_areas:
            likely_icps.append(f"Teams experiencing: {', '.join(all_pain_areas[:3])}")
        if all_buyer_pain:
            likely_icps.extend(all_buyer_pain[:2])

        return FounderProfileSynthesis(
            interests=all_topics[:20],
            strengths=all_languages,
            repeat_patterns=[c.label for c in clusters[:5]] + all_repeated_builds[:3],
            unfair_advantages=unfair_advantages,
            likely_icps=likely_icps[:5],
            natural_distribution_wedges=all_wedges[:3],
        )

    def _build_hypotheses(
        self,
        clusters: list[InterestCluster],
        deep_profiles: list[Any],
    ) -> list[OpportunityHypothesis]:
        """Generate opportunity hypotheses from clusters enriched with deep-scan data."""
        # Aggregate deep profile signals for enrichment
        all_pain: list[str] = []
        all_opportunities: list[str] = []
        all_buyer_pain: list[str] = []
        for profile in deep_profiles:
            all_pain.extend(getattr(profile, "recurring_pain_areas", []))
            all_opportunities.extend(getattr(profile, "adjacent_product_opportunities", []))
            all_buyer_pain.extend(getattr(profile, "adjacent_buyer_pain", []))

        # Count recurring signals for relevance scoring
        pain_counter = Counter(all_pain)
        opp_counter = Counter(all_opportunities)

        hypotheses: list[OpportunityHypothesis] = []
        for cluster in clusters[:5]:
            # Find relevant signals from deep-scan data
            relevant_pain = [p for p, _ in pain_counter.most_common(3) if p]
            relevant_opps = [o for o, _ in opp_counter.most_common(3) if o]

            # Build a richer description than just "Build tooling for X"
            desc_parts = [
                f"Portfolio analysis shows repeated investment in "
                f"'{cluster.label}' across {len(cluster.repos)} repo(s).",
            ]
            if relevant_pain:
                desc_parts.append(
                    f"Recurring pain areas: {', '.join(relevant_pain[:2])}."
                )
            if relevant_opps:
                desc_parts.append(
                    f"Adjacent opportunities: {', '.join(relevant_opps[:2])}."
                )
            desc_parts.append(
                "This pattern suggests genuine domain depth and "
                "potential for a targeted developer tooling product."
            )

            # Build a more specific title when enrichment data is available
            if relevant_opps:
                title = f"Opportunity in '{cluster.label}': {relevant_opps[0]}"
            elif relevant_pain:
                title = f"Solve '{relevant_pain[0]}' in the {cluster.label} space"
            else:
                title = f"Build tooling for the '{cluster.label}' space"

            # Truncate title to reasonable length
            if len(title) > 120:
                title = title[:117] + "..."

            hypothesis = OpportunityHypothesis(
                hypothesis_id=str(uuid.uuid4()),
                title=title,
                description=" ".join(desc_parts),
                source_clusters=[cluster.cluster_id],
                unfair_advantages=cluster.languages,
                likely_icps=all_buyer_pain[:3] if all_buyer_pain else [],
                confidence=cluster.strength,
                provenance="github_portfolio",
            )
            hypotheses.append(hypothesis)

        return hypotheses

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    async def run(
        self,
        request: FounderBootstrapRequest,
        *,
        github_client: Any = None,
        repo_digest: Any = None,
        discovery_store: Any = None,
    ) -> FounderBootstrapResponse:
        """Execute the full bootstrap pipeline and return a structured response.

        Parameters
        ----------
        request:
            Bootstrap configuration (username, scan limits, filters).
        github_client:
            Injected client.  Must expose
            ``async list_repos(username, max_repos, include_forks,
            include_archived) -> list[dict]``.
        repo_digest:
            Optional repo-digest analyser (``RepoDigestAnalyzer``).  When
            provided the pipeline runs deep scans on top-N repos.
        discovery_store:
            Optional discovery store.  When provided the pipeline seeds an
            initial idea candidate for each top-3 hypothesis.

        Raises
        ------
        ValueError
            If ``github_client`` is None (caller should check beforehand).
        """
        if github_client is None:
            raise ValueError(
                "github_client is required for the bootstrap pipeline. "
                "Ensure a GitHub portfolio client is provided."
            )

        # ------------------------------------------------------------------
        # 1. Fetch raw repo list
        # ------------------------------------------------------------------
        raw_repos = await github_client.list_repos(
            request.github_username,
            max_repos=request.max_repos,
            include_forks=request.include_forks,
            include_archived=request.include_archived,
        )

        # ------------------------------------------------------------------
        # 2. Normalise into inventory
        # ------------------------------------------------------------------
        inventory = self._build_inventory(raw_repos)

        # ------------------------------------------------------------------
        # 3. Cluster by theme
        # ------------------------------------------------------------------
        clusters = self._cluster_by_theme(inventory)

        # ------------------------------------------------------------------
        # 4. Pick top-N repos by star count for deep scan
        # ------------------------------------------------------------------
        sorted_by_stars = sorted(
            inventory, key=lambda r: r["stargazers_count"], reverse=True
        )
        deep_scan_repos = sorted_by_stars[: request.deep_scan_top_n]
        repos_deep_scanned = 0

        # ------------------------------------------------------------------
        # 5. Run deep scans if repo_digest is available
        # ------------------------------------------------------------------
        deep_profiles: list[Any] = []
        if repo_digest is not None and deep_scan_repos:
            deep_profiles = await self._deep_scan_repos(deep_scan_repos, repo_digest)
            repos_deep_scanned = len(deep_profiles)

        # ------------------------------------------------------------------
        # 6. Synthesise founder profile
        # ------------------------------------------------------------------
        profile = self._synthesise_profile(inventory, clusters, deep_profiles)

        # ------------------------------------------------------------------
        # 7. Generate opportunity hypotheses (enriched with deep-scan data)
        # ------------------------------------------------------------------
        hypotheses = self._build_hypotheses(clusters, deep_profiles)

        # ------------------------------------------------------------------
        # 8. Seed discovery store (optional)
        # ------------------------------------------------------------------
        discovery_seed_attempted = discovery_store is not None
        discovery_seeded_count = 0
        discovery_seed_errors: list[str] = []
        if discovery_store is not None:
            for hypothesis in hypotheses[:3]:
                try:
                    from orchestrator.discovery_models import IdeaCreateRequest

                    await asyncio.to_thread(
                        discovery_store.create_idea,
                        IdeaCreateRequest(
                            title=hypothesis.title,
                            description=hypothesis.description,
                            source="github_bootstrap",
                            portfolio_id=request.portfolio_id,
                        )
                    )
                    discovery_seeded_count += 1
                except Exception as exc:
                    message = f"{hypothesis.title}: {exc}"
                    discovery_seed_errors.append(message)
                    logger.warning("Discovery seeding failed for '%s': %s", hypothesis.title, exc)

        warnings = list(discovery_seed_errors)

        # ------------------------------------------------------------------
        # 9. Assemble and return response
        # ------------------------------------------------------------------
        return FounderBootstrapResponse(
            github_username=request.github_username,
            repos_scanned=len(inventory),
            repos_deep_scanned=repos_deep_scanned,
            hypotheses_count=len(hypotheses),
            discovery_seed_attempted=discovery_seed_attempted,
            discovery_seeded_count=discovery_seeded_count,
            discovery_seed_errors=discovery_seed_errors,
            warnings=warnings,
            profile=profile,
            clusters=clusters,
            hypotheses=hypotheses,
        )
