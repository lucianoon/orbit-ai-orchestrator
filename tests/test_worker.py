"""Roteamento de tools no executor: decide_tool é puro e roteia cada passo."""
import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _executor_settings(monkeypatch):
    """worker.py faz `from settings import settings` (versão do executor).

    Injeta um módulo fake em sys.modules ANTES do primeiro import de worker,
    evitando colisão com orchestrator/settings.py (mesmo nome de módulo).
    """
    fake = types.ModuleType("settings")

    class _Settings:
        redis_url = "redis://fake.invalid:6379/9"
        executor_queue = "executor-tasks"
        searx_url = "http://fake.invalid:8080"
        playwright_ws = None
        code_timeout = 5
        code_mem_mb = 256
        code_fsize_mb = 10

    fake.settings = _Settings()
    monkeypatch.setitem(sys.modules, "settings", fake)


def _get_worker():
    import worker

    return worker


def test_palavras_de_busca_roteiam_para_search():
    assert _get_worker().decide_tool("Pesquise os preços de GPU") == "search"
    assert _get_worker().decide_tool("busque artigos sobre RAG") == "search"


def test_urls_e_abertura_roteiam_para_browser():
    assert _get_worker().decide_tool("Abra https://exemplo.com e capture a pagina") == "browser"
    assert _get_worker().decide_tool("scrape da tabela de preços") == "browser"


def test_calculo_e_codigo_roteiam_para_python():
    assert _get_worker().decide_tool("Calcule 2**10 com um script python") == "python"
    assert _get_worker().decide_tool("rodar o script de validação") == "python"


def test_fallback_sem_keyword_e_search():
    assert _get_worker().decide_tool("resuma este texto em três pontos") == "search"
