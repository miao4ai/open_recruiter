"""Job Search Agent — search the web for job postings using DuckDuckGo."""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def search_jobs_web(
    query: str,
    location: str = "",
    n_results: int = 10,
) -> list[dict[str, Any]]:
    """Search the web for job postings.

    Returns a list of dicts with: title, url, snippet, source.
    """
    from ddgs import DDGS

    # Build search query targeting job sites
    search_query = query
    if location:
        search_query += f" {location}"
    search_query += " job posting hiring"

    results: list[dict[str, Any]] = []
    try:
        ddgs = DDGS()
        raw = ddgs.text(search_query, max_results=n_results * 2)

        for item in raw:
            title = item.get("title", "")
            url = item.get("href", "")
            snippet = item.get("body", "")

            # Extract source domain
            source = ""
            if url:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                source = parsed.netloc.replace("www.", "")

            results.append({
                "title": title,
                "url": url,
                "snippet": snippet,
                "source": source,
            })

            if len(results) >= n_results:
                break

    except Exception as e:
        log.error("DuckDuckGo search failed: %s", e)

    return results


def search_jobs_enriched(
    cfg,
    query: str,
    profile: dict | None = None,
    location: str = "",
    n_results: int = 10,
) -> list[dict[str, Any]]:
    """Search the web for jobs and optionally enrich with LLM parsing.

    If an LLM config is available, parses search results into structured
    job data. Otherwise returns raw search results.
    """
    raw_results = search_jobs_web(query, location, n_results)
    if not raw_results:
        return []

    # Try to enrich with LLM: extract structured job info from snippets
    try:
        from app.llm import chat_json

        results_text = "\n\n".join(
            f"### Result {i+1}\n"
            f"Title: {r['title']}\n"
            f"URL: {r['url']}\n"
            f"Source: {r['source']}\n"
            f"Snippet: {r['snippet']}"
            for i, r in enumerate(raw_results)
        )

        system_prompt = """\
You are a job listing parser. Given web search results for job postings, \
extract structured job information from each result.

Return a JSON array, one object per result, with:
- "title": the job title (clean, without company name)
- "company": the company name if identifiable from the snippet or title
- "location": location if mentioned in the snippet or title
- "url": the original URL — copy it EXACTLY as provided, do NOT modify
- "source": the source website — copy it EXACTLY as provided, do NOT modify
- "snippet": a 1-2 sentence summary of the role from the original snippet
- "salary_range": salary if mentioned, empty string otherwise

CRITICAL RULES:
- ONLY use information that is explicitly present in the search results
- NEVER invent or hallucinate data — if company name is not clear, use empty string ""
- NEVER use placeholders like "[Company Name]", "[City, State]", "[Company]"
- Copy url and source fields verbatim from the input — do NOT change them
- Only include results that are actual job postings. Skip generic articles.
- Output valid JSON array only."""

        data = chat_json(
            cfg,
            system=system_prompt,
            messages=[{"role": "user", "content": results_text}],
        )

        enriched = None
        if isinstance(data, list):
            enriched = data[:n_results]
        elif isinstance(data, dict) and "jobs" in data:
            enriched = data["jobs"][:n_results]

        # Validate: reject if LLM hallucinated placeholders
        if enriched:
            placeholder_count = sum(
                1 for r in enriched
                if any(p in str(r) for p in ["[Company", "[City", "[State", "[Location", "[Salary"])
            )
            if placeholder_count > len(enriched) // 2:
                log.warning("LLM enrichment produced placeholders, using raw results")
            else:
                return enriched
    except Exception as e:
        log.warning("LLM enrichment failed, using raw results: %s", e)

    # Fallback: return raw results as-is
    return raw_results
