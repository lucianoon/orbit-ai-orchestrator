import asyncio
from celery import Celery
from settings import settings
from tools.search import search_web
from tools.browser import fetch_page
from tools.run_code import run_python

celery_app = Celery("executor", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_default_queue = settings.executor_queue


def decide_tool(step: str) -> str:
    s = step.lower()
    if any(k in s for k in ["pesquise", "buscar", "search", "encontre"]):
        return "search"
    if any(k in s for k in ["http://", "https://", "abra", "scrape", "capturar", "pagina"]):
        return "browser"
    if any(k in s for k in ["calcule", "script", "python", "executar código", "compute", "rodar"]):
        return "python"
    return "search"


@celery_app.task(name="executor.run_step", autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 2})
def run_step(step: str):
    tool = decide_tool(step)
    if tool == "search":
        output, evidence = asyncio.run(search_web(step))
    elif tool == "browser":
        output, evidence = asyncio.run(fetch_page(step))
    else:
        output, evidence = asyncio.run(run_python(step))
    return {"step": step, "output": output, "evidence": evidence}
