"""Roundtrip real: broker Redis -> worker Celery -> sandbox de código."""
import os


def test_despacho_e_resultado_via_broker_real(celery_client, worker_process):
    """send_task por nome atravessa o Redis e o worker devolve output do sandbox."""
    async_result = celery_client.send_task(
        "executor.run_step", args=["print('calcule-ok')"]
    )
    result = async_result.get(timeout=60)

    assert result["output"] == "calcule-ok"
    assert result["step"] == "print('calcule-ok')"
    assert isinstance(result["evidence"], list)


def test_busca_indisponivel_degrada_sem_quebrar_task(celery_client, worker_process):
    """SearXNG aponta para porta fechada: search_web degrada graciosamente.

    A task NÃO falha — retorna mensagem de erro como output, evidência vazia
    (o mesmo comportamento que o orquestrador recebe em produção).
    """
    async_result = celery_client.send_task(
        "executor.run_step", args=["pesquise notícias sobre RAG"]
    )
    result = async_result.get(timeout=60)

    assert result["output"].startswith("busca falhou")
    assert result["evidence"] == []
    assert async_result.failed() is False


def test_config_do_orchestrator_aponta_para_o_mesmo_broker(worker_process):
    """Orquestrador e executor precisam dividir broker E fila."""
    from settings import settings  # orchestrator (path priorizado pelo conftest raiz)

    expected_broker = os.environ.get("REDIS_URL", "redis://localhost:6379/15")
    assert settings.redis_url == expected_broker
    assert settings.executor_queue == "executor-tasks"
