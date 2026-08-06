from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


def make_planner(model_name: str):
    return ChatOpenAI(model=model_name, temperature=0.2)


def make_verifier(model_name: str):
    return ChatOpenAI(model=model_name, temperature=0.1)


async def plan(llm, goal: str):
    prompt = [
        SystemMessage(content="Você é um planejador que gera passos paralelizáveis e sucintos."),
        HumanMessage(content=f"Tarefa: {goal}\nListe passos numerados.")
    ]
    msg = await llm.ainvoke(prompt)
    return [s.strip(" -") for s in msg.content.splitlines() if s.strip()]


async def verify(llm, goal: str, results: list[str]):
    summary_text = "\n".join(results)
    prompt = [
        SystemMessage(content="Verifique factualidade, consistência e cobertura. Responda 'OK: resumo' ou 'FALHA: motivo'."),
        HumanMessage(content=f"Objetivo: {goal}\nResultados:\n{summary_text}")
    ]
    msg = await llm.ainvoke(prompt)
    content = msg.content.strip()
    return content.upper().startswith("OK"), content
