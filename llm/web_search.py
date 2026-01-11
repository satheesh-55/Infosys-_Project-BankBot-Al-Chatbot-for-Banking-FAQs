from duckduckgo_search import DDGS


def web_search(query: str) -> str:
    """
    Perform a web search using DuckDuckGo.
    Returns summarized text.
    """
    results = []

    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=5):
            if r.get("body"):
                results.append(f"• {r['title']}\n  {r['body']}")

    if not results:
        return "I couldn’t find relevant information on the web."

    return "\n\n".join(results)


def latest_news() -> str:
    """
    Fetch latest news headlines
    """
    headlines = []

    with DDGS() as ddgs:
        for r in ddgs.news("latest news", max_results=5):
            headlines.append(f"• {r['title']}")

    if not headlines:
        return "I couldn’t fetch the latest news right now."

    return "\n".join(headlines)

