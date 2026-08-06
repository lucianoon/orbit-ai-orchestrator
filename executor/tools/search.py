import httpx
from settings import settings

async def search_web(query: str):
    params = {"q": query, "format": "json", "language": "pt"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f"{settings.searx_url}/search", params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        return f"busca falhou: {exc}", []

    hits = data.get("results", [])[:3]
    summary = "; ".join([h.get("title", "") for h in hits]) or "sem resultados"
    ev = [{"url": h.get("url"), "title": h.get("title"), "snippet": h.get("content")}
          for h in hits]
    return summary, ev
