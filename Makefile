# test: backend + frontend unit tests
# test-e2e: run after starting the app (e.g. docker compose up)
.PHONY: test test-backend test-frontend test-e2e

test: test-backend test-frontend
	@echo "Backend and frontend unit tests passed."

test-backend:
	cd backend && pip install -q -r requirements.txt && python -m pytest tests -v

# Coverage gate: fail if coverage drops below threshold (raise over time).
test-backend-cov:
	cd backend && pip install -q -r requirements.txt && python -m pytest tests --cov=app --cov-report=term-missing --cov-fail-under=25 -q

test-frontend:
	cd frontend && pnpm install --frozen-lockfile && pnpm run test:run

test-frontend-cov:
	cd frontend && pnpm run test:coverage

# E2E requires the app to be running (e.g. docker compose up).
test-e2e:
	cd frontend && pnpm run test:e2e
