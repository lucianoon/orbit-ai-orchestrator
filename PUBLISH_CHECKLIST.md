# Publish Checklist

## Done

- Added a root `.gitignore` for local environments, caches, databases, and logs.
- Moved orchestrator database paths to environment-driven settings.
- Moved auth database path to environment-driven settings.
- Restricted CORS to configured origins instead of allowing every origin.
- Removed the insecure default `JWT_SECRET` fallback from `docker-compose.yml`.
- Expanded `.env.example` with CORS and storage variables.
- Aligned `README.md` with the current token-based auth implementation.

## Still required before GitHub publish

- Repository name finalized as `orbit-ai-orchestrator`.
- Local runtime files removed from the working tree.
- Local `venv/` directory removed from the project tree.
- `LICENSE` file added.

## Still recommended before first public commit

- Review `README.md` one more time for product positioning and screenshots.
- Decide whether to keep the current Docker defaults or split dev/prod compose files.
- Add a minimal CI workflow for syntax checks and tests.

## Still required before production

- Replace the custom token auth with a standard JWT or session implementation.
- Add automated tests for orchestration, auth, and executor integrations.
- Add request throttling and input validation limits.
- Move from SQLite to PostgreSQL for multi-instance production deployments.
- Add structured health endpoints and readiness checks for orchestrator and executor.
- Add CI for lint, tests, and container validation.
