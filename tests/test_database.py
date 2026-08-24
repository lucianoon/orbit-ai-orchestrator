"""Persistência de histórico: tasks, steps, join de contagem e deleção."""
import pytest

import database


@pytest.fixture(autouse=True)
def _history_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "history.db"))
    database.init_db()


def test_ciclo_de_vida_da_task():
    task_id = database.create_task("levantar métricas", wide=True)
    assert isinstance(task_id, int)

    database.update_task_status(task_id, "planning")
    database.update_task_status(task_id, "executing")
    database.update_task_status(task_id, "completed", True, "OK: feito")

    detail = database.get_task_detail(task_id)
    assert detail["status"] == "completed"
    assert detail["verified"] in (True, 1)  # SQLite devolve BOOLEAN como INTEGER
    assert detail["summary"] == "OK: feito"
    assert detail["completed_at"] is not None


def test_steps_evidence_json_roundtrip():
    task_id = database.create_task("meta com evidência")
    step_id = database.add_step(task_id, 0, "passo único")
    evidence = [{"artifact": "/tmp/x.py"}, {"url": "https://exemplo.com"}]
    database.update_step(step_id, "completed", "saída do passo", evidence)

    detail = database.get_task_detail(task_id)
    step = detail["steps"][0]
    assert step["status"] == "completed"
    assert step["output"] == "saída do passo"
    assert step["evidence"] == evidence  # sobreviveu ao roundtrip JSON
    assert detail["steps_count"] == 1


def test_history_ordem_limit_e_contagem_de_passos():
    for n in range(3):
        tid = database.create_task(f"goal {n}")
        database.add_step(tid, 0, f"passo {n}-a")
        database.add_step(tid, 1, f"passo {n}-b")

    history = database.get_task_history(limit=2)
    assert len(history) == 2
    assert all(t["steps_count"] == 2 for t in history)

    paginated = database.get_task_history(limit=10, offset=2)
    assert len(paginated) == 1


def test_delete_task_remove_steps_e_retorna_false_na_segunda():
    task_id = database.create_task("para deletar")
    database.add_step(task_id, 0, "passo órfão?")

    assert database.delete_task(task_id) is True
    assert database.get_task_detail(task_id) is None
    assert database.delete_task(task_id) is False
