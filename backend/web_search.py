"""
Phase 3: Web Search — DuckDuckGo, no API key needed
"""
import httpx, re
from urllib.parse import quote_plus

async def duckduckgo_search(query: str, max_results: int = 5) -> list[dict]:
    """Search DuckDuckGo instant answers API"""
    results = []
    try:
        # DuckDuckGo Instant Answer API
        url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1&skip_disambig=1"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers={"User-Agent": "KreativOS/1.0"})
            data = resp.json()

        # Abstract (main result)
        if data.get("Abstract"):
            results.append({
                "title":   data.get("Heading", query),
                "snippet": data["Abstract"][:500],
                "url":     data.get("AbstractURL", ""),
                "source":  data.get("AbstractSource", "DuckDuckGo"),
            })

        # Related topics
        for topic in data.get("RelatedTopics", [])[:max_results-1]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title":   topic.get("Text", "")[:80],
                    "snippet": topic.get("Text", "")[:400],
                    "url":     topic.get("FirstURL", ""),
                    "source":  "DuckDuckGo",
                })

        # Results
        for r in data.get("Results", [])[:3]:
            results.append({
                "title":   r.get("Text", "")[:80],
                "snippet": r.get("Text", "")[:400],
                "url":     r.get("FirstURL", ""),
                "source":  "DuckDuckGo",
            })

    except Exception as e:
        results.append({"title": "Search Error", "snippet": str(e), "url": "", "source": "error"})

    return results[:max_results]

def format_results_for_agent(query: str, results: list[dict]) -> str:
    if not results:
        return f"No web search results found for: {query}"
    lines = [f"## Web Search Results for: {query}\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"**{i}. {r['title']}**")
        lines.append(r["snippet"])
        if r["url"]:
            lines.append(f"Source: {r['url']}")
        lines.append("")
    return "\n".join(lines)
