# Contributing

Thanks for contributing to `orbit-ai-orchestrator`.

## Development flow

- Create a branch from `main`.
- Keep changes scoped and reviewable.
- Update documentation when behavior changes.
- Do not commit `.env`, local databases, or generated caches.

## Local validation

Run basic Python validation before opening a pull request:

```bash
python -m compileall orchestrator executor
```

If you change dependencies, verify both components still install correctly:

```bash
pip install -r orchestrator/requirements.txt
pip install -r executor/requirements.txt
```

## Pull requests

- Describe the user-facing or system-facing change clearly.
- Mention any deployment or environment variable impact.
- Keep secrets and local infrastructure details out of the diff.
