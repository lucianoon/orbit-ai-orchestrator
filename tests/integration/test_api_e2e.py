"""Ponta a ponta da API: POST /task com broker, worker e sandbox REAIS.

Apenas o plano (LLM) e o veredito (LLM) são simulados — tudo entre eles é
infraestrutura de verdade: FastAPI -> Celery -> Redis -> worker -> rlimits.
"""
import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture()
def client():
    return TestClient(app)


def test_task_end_to_end_com_executor_real(client, worker_process, monkeypatch):
    # O texto do passo É o código executado pelo sandbox; o comentário "# calcule"
    # garante o roteamento para a tool python sem invalidar a sintaxe.
    async def fake_plan(llm, goal):
        return ["print('passo-e2e-ok')  # calcule", "print(6 * 7)  # calcule"]

    async def fake_verify(llm, goal, lines):
        joined = "\n".join(lines)
        return "passo-e2e-ok" in joined and "42" in joined, "OK: e2e confirmado"

    monkeypatch.setattr("main.plan", fake_plan)
    monkeypatch.setattr("main.verify", fake_verify)
    # celery_app e poll_result NÃO são mexidos: despacho e polling reais.

    resp = client.post("/task", json={"goal": "executar cálculos", "wide": False})

    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is True
    outputs = [s["output"] for s in body["steps"]]
    assert outputs == ["passo-e2e-ok", "42"]
    assert all(s["evidence"] for s in body["steps"])
