.PHONY: web web-dev test lint
web:            ## build the frontend bundle into clue/web/static (commit the result)
	cd web && npm ci && npm run build
web-dev:        ## hot-reloading frontend on :5173 proxied to a backend on :8000
	cd web && npm run dev
test:
	pytest -q && cd web && npm test
lint:
	ruff check clue tests && ruff format --check clue tests && mypy clue && cd web && npm run typecheck
