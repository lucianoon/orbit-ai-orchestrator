"""plan/verify sobre LLM fake: parsing de lista e do prefixo OK/FALHA."""
from types import SimpleNamespace

from graph import make_planner, make_verifier, plan, verify


class FakeLLM:
    def __init__(self, content: str):
        self.content = content
        self.prompts = []

    async def ainvoke(self, prompt):
        self.prompts.append(prompt)
        return SimpleNamespace(content=self.content)


async def test_plan_extrai_passos_limpos():
    llm = FakeLLM("1. buscar dados\n2. - calcular média\n\n3. gerar relatório")
    steps = await plan(llm, "resumo de vendas")
    # strip(" -") remove espaços/hífens só das pontas; marcadores internos permanecem
    assert steps == ["1. buscar dados", "2. - calcular média", "3. gerar relatório"]
    # prompt contém instrução de sistema e o objetivo
    system, human = llm.prompts[0]
    assert "planejador" in system.content.lower()
    assert "resumo de vendas" in human.content


async def test_plan_com_resposta_vazia_retorna_lista_vazia():
    assert await plan(FakeLLM(""), "qualquer objetivo") == []


async def test_verify_reconhece_ok_e_falha():
    ok_llm = FakeLLM("OK: resultados consistentes e cobrem o objetivo")
    aprovado, resumo = await verify(ok_llm, "meta", ["passo\nsaída"])
    assert aprovado is True
    assert "consistentes" in resumo

    fail_llm = FakeLLM("FALHA: saída contradiz o objetivo")
    aprovado, resumo = await verify(fail_llm, "meta", ["passo\nsaída"])
    assert aprovado is False
    assert "contradiz" in resumo


def test_factories_diferenciam_temperatura():
    planner = make_planner("gpt-4.1")
    verifier = make_verifier("gpt-4.1")
    assert planner.temperature == 0.2
    assert verifier.temperature == 0.1
