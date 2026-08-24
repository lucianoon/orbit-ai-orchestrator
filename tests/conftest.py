"""Configura o ambiente de teste antes de qualquer import de módulo da aplicação."""
import os
import sys
from pathlib import Path

# make_planner/make_verifier instanciam ChatOpenAI em main.py; sem chave válida
# o construtor falha. Nenhum teste chama a API real da OpenAI.
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-not-real")

ROOT = Path(__file__).resolve().parent.parent
ORCH = str(ROOT / "orchestrator")
EXEC = str(ROOT / "executor")

for path in (EXEC, ORCH):
    if path not in sys.path:
        sys.path.insert(0, path)
