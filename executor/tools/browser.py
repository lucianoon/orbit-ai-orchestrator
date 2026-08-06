from playwright.async_api import async_playwright

async def fetch_page(instruction: str):
    url = next((t for t in instruction.split() if t.startswith("http")), None)
    if not url:
        return "Nenhuma URL encontrada", []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            html = await page.content()
            await browser.close()
    except Exception as exc:
        return f"falha ao abrir página: {exc}", [{"url": url}]
    return f"HTML coletado ({len(html)} chars)", [{"url": url, "html_head": html[:500]}]
