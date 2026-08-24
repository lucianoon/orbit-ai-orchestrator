"""Sandbox de execução de código: geração do runner com rlimits e execução real."""
import sys
import types

import pytest


@pytest.fixture()
def run_code_module(monkeypatch):
    """Importa executor/tools/run_code.py com settings do executor (fake)."""
    fake = types.ModuleType("settings")

    class _Settings:
        code_timeout = 5
        code_mem_mb = 256
        code_fsize_mb = 10

    fake.settings = _Settings()
    monkeypatch.setitem(sys.modules, "settings", fake)

    from tools import run_code

    return run_code


def test_runner_aplica_rlimits(run_code_module, tmp_path):
    alvo = tmp_path / "user_code.py"
    alvo.write_text("print('x')")
    runner_path = run_code_module._make_runner(str(alvo), timeout=7, mem_mb=128, fsize_mb=5)
    try:
        conteudo = open(runner_path).read()
        assert "_set_limit(resource.RLIMIT_CPU, 7)" in conteudo
        assert "_set_limit(resource.RLIMIT_AS, " + str(128 * 1024 * 1024) + ")" in conteudo
        assert "_set_limit(resource.RLIMIT_FSIZE, " + str(5 * 1024 * 1024) + ")" in conteudo
        assert "_set_limit(resource.RLIMIT_CORE, 0)" in conteudo  # sem core dumps
        assert str(alvo) in conteudo
    finally:
        import os

        os.remove(runner_path)


async def test_run_python_executa_codigo_real(run_code_module):
    output, evidence = await run_code_module.run_python("print('orbit-ok')")
    assert output == "orbit-ok"
    assert isinstance(evidence, list) and len(evidence) == 1


async def test_run_python_captura_stderr_e_limpa_temporarios(run_code_module):
    output, _ = await run_code_module.run_python("raise ValueError('boom')")
    assert "ValueError" in output and "boom" in output


async def test_run_python_trunca_saida_longa(run_code_module):
    output, _ = await run_code_module.run_python("print('a' * 6000)")
    assert len(output) <= 4000 + len("...(truncado)")
    assert output.endswith("...(truncado)")
