"""Source scanners for research sensing."""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime, timedelta
from typing import Protocol

import httpx

from orchestrator.research.postprocessors import extract_topic_tags, infer_pain_score, infer_trend_score
from orchestrator.research.source_models import ResearchObservation, ResearchSource, default_freshness_deadline
from orchestrator.shared_contracts import Confidence


class SourceScanner(Protocol):
    source: ResearchSource

    async def scan(self, query: str, max_items: int = 5, freshness_window_hours: int = 24) -> list[ResearchObservation]:
        ...


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _observation(
    *,
    source: ResearchSource,
    entity: str,
    query: str,
    url: str,
    raw_text: str,
    metadata: dict,
    freshness_window_hours: int,
) -> ResearchObservation:
    tags = extract_topic_tags(f"{entity} {raw_text}")
    pain = infer_pain_score(raw_text)
    trend = infer_trend_score(raw_text, metadata)
    confidence = Confidence.HIGH if trend >= 0.5 or pain >= 0.5 else Confidence.MEDIUM
    return ResearchObservation(
        source=source,
        entity=entity,
        query=query,
        url=url,
        raw_text=raw_text,
        topic_tags=tags,
        pain_score=pain,
        trend_score=trend,
        evidence_confidence=confidence,
        collected_at=_now(),
        freshness_deadline=default_freshness_deadline(freshness_window_hours),
        metadata=metadata,
    )


class GitHubSearchScanner:
    source: ResearchSource = "github"
    api_url = "https://api.github.com/search/repositories"

    def __init__(self) -> None:
        self.token = os.environ.get("GITHUB_TOKEN", "").strip()

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def scan(self, query: str, max_items: int = 5, freshness_window_hours: int = 24) -> list[ResearchObservation]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                self.api_url,
                params={"q": query, "sort": "stars", "order": "desc", "per_page": min(max_items, 10)},
                headers=self._headers(),
            )
            response.raise_for_status()
            data = response.json()
        items = []
        for repo in data.get("items", [])[:max_items]:
            stars = int(repo.get("stargazers_count", 0) or 0)
            forks = int(repo.get("forks_count", 0) or 0)
            description = (repo.get("description") or "").strip()
            raw = f"{description} Stars={stars}. Forks={forks}. Language={repo.get('language') or 'unknown'}."
            items.append(
                _observation(
                    source=self.source,
                    entity=repo.get("full_name") or repo.get("name") or query,
                    query=query,
                    url=repo.get("html_url") or "",
                    raw_text=raw,
                    metadata={
                        "stars": stars,
                        "forks": forks,
                        "language": repo.get("language"),
                        "updated_at": repo.get("updated_at"),
                    },
                    freshness_window_hours=freshness_window_hours,
                )
            )
        return items


class GitHubTrendingScanner:
    source: ResearchSource = "github_trending"
    api_url = "https://api.github.com/search/repositories"

    def __init__(self) -> None:
        self.token = os.environ.get("GITHUB_TOKEN", "").strip()

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def scan(self, query: str, max_items: int = 5, freshness_window_hours: int = 12) -> list[ResearchObservation]:
        recent_cutoff = (_now() - timedelta(days=14)).strftime("%Y-%m-%d")
        search_query = f"{query} pushed:>={recent_cutoff}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                self.api_url,
                params={"q": search_query, "sort": "updated", "order": "desc", "per_page": min(max_items, 10)},
                headers=self._headers(),
            )
            response.raise_for_status()
            data = response.json()
        observations: list[ResearchObservation] = []
        for repo in data.get("items", [])[:max_items]:
            stars = int(repo.get("stargazers_count", 0) or 0)
            forks = int(repo.get("forks_count", 0) or 0)
            updated_at = repo.get("updated_at") or ""
            description = (repo.get("description") or "").strip()
            raw = f"Trending repository candidate. {description} Updated={updated_at}. Stars={stars}. Forks={forks}."
            observations.append(
                _observation(
                    source=self.source,
                    entity=repo.get("full_name") or query,
                    query=query,
                    url=repo.get("html_url") or "",
                    raw_text=raw,
                    metadata={"stars": stars, "forks": forks, "updated_at": updated_at},
                    freshness_window_hours=freshness_window_hours,
                )
            )
        return observations


class HackerNewsScanner:
    source: ResearchSource = "hackernews"
    api_url = "https://hn.algolia.com/api/v1/search"

    async def scan(self, query: str, max_items: int = 5, freshness_window_hours: int = 12) -> list[ResearchObservation]:
        twelve_months_ago = int((_now() - timedelta(days=365)).timestamp())
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                self.api_url,
                params={
                    "query": query,
                    "tags": "(story,show_hn,ask_hn)",
                    "numericFilters": f"created_at_i>{twelve_months_ago}",
                    "hitsPerPage": min(max_items, 10),
                },
            )
            response.raise_for_status()
            data = response.json()
        observations: list[ResearchObservation] = []
        for hit in data.get("hits", [])[:max_items]:
            title = (hit.get("title") or hit.get("story_title") or query).strip()
            comments = int(hit.get("num_comments", 0) or 0)
            points = int(hit.get("points", 0) or 0)
            url = hit.get("url") or hit.get("story_url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            raw = f"{title}. Points={points}. Comments={comments}."
            observations.append(
                _observation(
                    source=self.source,
                    entity=title,
                    query=query,
                    url=url,
                    raw_text=raw,
                    metadata={"score": points, "comments": comments, "created_at_i": hit.get("created_at_i")},
                    freshness_window_hours=freshness_window_hours,
                )
            )
        return observations


class RedditScanner:
    source: ResearchSource = "reddit"
    api_url = "https://www.reddit.com/search.json"

    async def scan(self, query: str, max_items: int = 5, freshness_window_hours: int = 6) -> list[ResearchObservation]:
        headers = {"User-Agent": "QuorumResearchBot/0.1"}
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(
                self.api_url,
                params={"q": query, "sort": "new", "limit": min(max_items, 10)},
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        observations: list[ResearchObservation] = []
        children = data.get("data", {}).get("children", [])
        for child in children[:max_items]:
            post = child.get("data", {})
            title = (post.get("title") or query).strip()
            score = int(post.get("score", 0) or 0)
            comments = int(post.get("num_comments", 0) or 0)
            permalink = post.get("permalink") or ""
            url = f"https://www.reddit.com{permalink}" if permalink else (post.get("url") or "")
            raw = f"{title}. Score={score}. Comments={comments}. Subreddit={post.get('subreddit') or 'unknown'}."
            observations.append(
                _observation(
                    source=self.source,
                    entity=title,
                    query=query,
                    url=url,
                    raw_text=raw,
                    metadata={"score": score, "comments": comments, "subreddit": post.get("subreddit")},
                    freshness_window_hours=freshness_window_hours,
                )
            )
        return observations


class NpmScanner:
    source: ResearchSource = "npm"
    api_url = "https://registry.npmjs.org/-/v1/search"

    async def scan(self, query: str, max_items: int = 5, freshness_window_hours: int = 24) -> list[ResearchObservation]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(self.api_url, params={"text": query, "size": min(max_items, 10)})
            response.raise_for_status()
            data = response.json()
        observations: list[ResearchObservation] = []
        for item in data.get("objects", [])[:max_items]:
            pkg = item.get("package", {})
            score = float((item.get("score") or {}).get("final", 0) or 0)
            description = (pkg.get("description") or "").strip()
            raw = f"{description} Version={pkg.get('version') or 'unknown'}. Registry score={score}."
            observations.append(
                _observation(
                    source=self.source,
                    entity=pkg.get("name") or query,
                    query=query,
                    url=(pkg.get("links") or {}).get("npm") or f"https://www.npmjs.com/package/{pkg.get('name', '')}",
                    raw_text=raw,
                    metadata={"score": score, "version": pkg.get("version")},
                    freshness_window_hours=freshness_window_hours,
                )
            )
        return observations


class PyPIScanner:
    source: ResearchSource = "pypi"
    search_url = "https://pypi.org/search/"
    count_pattern = re.compile(r'<strong>(?P<count>[\d,]+)</strong>\s*project', re.IGNORECASE)
    package_pattern = re.compile(
        r'<a\s+class="package-snippet"[^>]*href="(?P<url>/project/[^"]+/)"[^>]*>'
        r'.*?<span\s+class="package-snippet__name"[^>]*>(?P<name>[^<]+)</span>'
        r'.*?<span\s+class="package-snippet__version"[^>]*>(?P<version>[^<]+)</span>'
        r'.*?<p\s+class="package-snippet__description"[^>]*>(?P<desc>[^<]*)</p>',
        re.DOTALL,
    )

    async def scan(self, query: str, max_items: int = 5, freshness_window_hours: int = 24) -> list[ResearchObservation]:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(self.search_url, params={"q": query})
            response.raise_for_status()
            html = response.text
        observations: list[ResearchObservation] = []
        for match in self.package_pattern.finditer(html):
            description = match.group("desc").strip()
            observations.append(
                _observation(
                    source=self.source,
                    entity=match.group("name").strip(),
                    query=query,
                    url=f"https://pypi.org{match.group('url').strip()}",
                    raw_text=f"{description} Version={match.group('version').strip()}.",
                    metadata={"version": match.group("version").strip()},
                    freshness_window_hours=freshness_window_hours,
                )
            )
            if len(observations) >= max_items:
                break
        return observations


class ProductHuntScanner:
    source: ResearchSource = "producthunt"
    api_url = "https://api.producthunt.com/v2/api/graphql"

    def __init__(self) -> None:
        self.token = os.environ.get("PRODUCTHUNT_TOKEN", "").strip()

    async def scan(self, query: str, max_items: int = 5, freshness_window_hours: int = 24) -> list[ResearchObservation]:
        if not self.token:
            return []
        graphql = """
        query SearchPosts($query: String!) {
            posts(order: VOTES, search: $query, first: 5) {
                edges {
                    node {
                        name
                        tagline
                        url
                        votesCount
                        createdAt
                    }
                }
            }
        }
        """
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                self.api_url,
                json={"query": graphql, "variables": {"query": query}},
                headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
        observations: list[ResearchObservation] = []
        for edge in (data.get("data") or {}).get("posts", {}).get("edges", [])[:max_items]:
            node = edge.get("node", {})
            tagline = (node.get("tagline") or "").strip()
            votes = int(node.get("votesCount", 0) or 0)
            observations.append(
                _observation(
                    source=self.source,
                    entity=node.get("name") or query,
                    query=query,
                    url=node.get("url") or "",
                    raw_text=f"{tagline} Votes={votes}.",
                    metadata={"votes": votes, "created_at": node.get("createdAt")},
                    freshness_window_hours=freshness_window_hours,
                )
            )
        return observations


class StackOverflowScanner:
    source: ResearchSource = "stackoverflow"
    api_url = "https://api.stackexchange.com/2.3/search"

    def __init__(self) -> None:
        self.key = os.environ.get("STACKEXCHANGE_KEY", "").strip()

    async def scan(self, query: str, max_items: int = 5, freshness_window_hours: int = 24) -> list[ResearchObservation]:
        params: dict[str, object] = {
            "order": "desc",
            "sort": "relevance",
            "intitle": query,
            "site": "stackoverflow",
            "pagesize": min(max_items, 10),
            "filter": "!9_bDDxJY5",
        }
        if self.key:
            params["key"] = self.key
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(self.api_url, params=params)
            response.raise_for_status()
            data = response.json()
        observations: list[ResearchObservation] = []
        for item in data.get("items", [])[:max_items]:
            score = int(item.get("score", 0) or 0)
            answers = int(item.get("answer_count", 0) or 0)
            title = (item.get("title") or query).strip()
            observations.append(
                _observation(
                    source=self.source,
                    entity=title,
                    query=query,
                    url=item.get("link") or "",
                    raw_text=f"{title}. Score={score}. Answers={answers}.",
                    metadata={"score": score, "answers": answers, "tags": item.get("tags") or []},
                    freshness_window_hours=freshness_window_hours,
                )
            )
        return observations


DEFAULT_SCANNERS: dict[ResearchSource, SourceScanner] = {
    "github": GitHubSearchScanner(),
    "github_trending": GitHubTrendingScanner(),
    "hackernews": HackerNewsScanner(),
    "reddit": RedditScanner(),
    "npm": NpmScanner(),
    "pypi": PyPIScanner(),
    "producthunt": ProductHuntScanner(),
    "stackoverflow": StackOverflowScanner(),
}
