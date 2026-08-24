"""API REST: /task ponta a ponta com LLM e Celery simulados, histórico e auth."""
import types

import pytest
from fastapi.testclient import TestClient

import auth
import database
from main import app


@pytest.fixture()
def client():
    return TestClient(app)


# ===== stubs de colaboradores externos =====

class _FakeTask:
    def __init__(self, task_id):
        self.id = task_id


class _StubCelery:
    """Substitui o celery_app de main.py sem tocar em Redis/broker real."""

    def __init__(self):
        self.dispatched = {}

    def send_task(self, name, args=None):
        step_text = (args or [""])[0]
        task_id = f"celery-{len(self.dispatched) + 1}"
        self.dispatched[task_id] = step_text
        return _FakeTask(task_id)


def _patch_happy_path(monkeypatch):
    stub_celery = _StubCelery()

    async def fake_plan(llm, goal):
        return ["passo um", "passo dois"]

    async def fake_poll(task_id):
        return {
            "step": stub_celery.dispatched[task_id],
            "output": "saída determinística",
            "evidence": [{"source": "teste"}],
        }

    async def fake_verify(llm, goal, lines):
        return True, "OK: cobertura confirmada"

    monkeypatch.setattr("main.celery_app", stub_celery)
    monkeypatch.setattr("main.plan", fake_plan)
    monkeypatch.setattr("main.poll_result", fake_poll)
    monkeypatch.setattr("main.verify", fake_verify)
    return stub_celery


# ===== POST /task =====

def test_task_fluxo_completo(client, monkeypatch):
    stub = _patch_happy_path(monkeypatch)

    resp = client.post("/task", json={"goal": "levantar métricas de venda", "wide": False})

    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is True
    assert "OK" in body["summary"]
    assert [s["step"] for s in body["steps"]] == ["passo um", "passo dois"]
    assert all(s["output"] == "saída determinística" for s in body["steps"])
    assert len(stub.dispatched) == 2  # cada passo virou uma tarefa no executor


def test_task_wide_limita_fanout(client, monkeypatch):
    stub = _patch_happy_path(monkeypatch)

    async def fake_plan_muitos_passos(llm, goal):
        return [f"passo {n}" for n in range(20)]

    monkeypatch.setattr("main.plan", fake_plan_muitos_passos)
    resp = client.post("/task", json={"goal": "varredura ampla", "wide": True})

    assert resp.status_code == 200
    assert len(resp.json()["steps"]) == 8  # settings.max_fanout


def test_planejamento_vazio_retorna_400(client, monkeypatch):
    _patch_happy_path(monkeypatch)

    async def fake_plan_vazio(llm, goal):
        return []

    monkeypatch.setattr("main.plan", fake_plan_vazio)
    resp = client.post("/task", json={"goal": "objetivo impossível"})

    assert resp.status_code == 400
    assert "Planejamento vazio" in resp.json()["detail"]


def test_falha_de_despacho_retorna_502(client, monkeypatch):
    class _BrokenCelery:
        def send_task(self, name, args=None):
            raise ConnectionError("broker offline")

    async def fake_plan(llm, goal):
        return ["único passo"]

    monkeypatch.setattr("main.celery_app", _BrokenCelery())
    monkeypatch.setattr("main.plan", fake_plan)

    resp = client.post("/task", json={"goal": "qualquer coisa"})
    assert resp.status_code == 502
    assert "despachar" in resp.json()["detail"]


# ===== histórico =====

def test_history_crud(client, tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "h.db"))
    database.init_db()
    task_id = database.create_task("meta do histórico")

    lista = client.get("/history").json()["tasks"]
    assert any(t["goal"] == "meta do histórico" for t in lista)

    detalhe = client.get(f"/history/{task_id}")
    assert detalhe.status_code == 200
    assert detalhe.json()["steps"] == []

    assert client.get("/history/999999").status_code == 404

    assert client.delete(f"/history/{task_id}").json()["id"] == task_id
    assert client.delete(f"/history/{task_id}").status_code == 404


# ===== autenticação =====

@pytest.fixture()
def _auth_db(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "AUTH_DB_PATH", str(tmp_path / "auth.db"))
    auth.init_auth_db()


def test_registro_login_me_e_logout(client, _auth_db):
    registro = client.post(
        "/auth/register",
        params={"username": "ana", "password": "secreta123", "email": "ana@ex.com"},
    )
    assert registro.status_code == 200
    token = registro.json()["access_token"]

    # duplicado rejeitado
    dup = client.post("/auth/register", params={"username": "ana", "password": "outra456"})
    assert dup.status_code == 400

    # validações de entrada
    curto = client.post("/auth/register", params={"username": "ab", "password": "x" * 8})
    assert curto.status_code == 400

    login_errado = client.post("/auth/login", params={"username": "ana", "password": "errada"})
    assert login_errado.status_code == 401

    login = client.post("/auth/login", params={"username": "ana", "password": "secreta123"})
    assert login.status_code == 200

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "ana"

    # token inválido é barrado
    assert (
        client.get("/auth/me", headers={"Authorization": "Bearer invalido"}).status_code == 401
    )
    # sem header também (get_current_user permite anônimo, require_auth bloqueia)
    assert client.get("/auth/me").status_code == 401

    sair = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert sair.status_code == 200
    # logout invalidou o token
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
