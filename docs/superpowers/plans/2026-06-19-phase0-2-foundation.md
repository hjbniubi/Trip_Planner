# Phase 0-2 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the initial backend/frontend project foundation through SPEC Phase 2: directory structure, shared data models, configuration, FastAPI entrypoint, frontend router/API/type skeleton, and tests for backend behavior.

**Architecture:** The backend is a FastAPI application under `backend/app`, with Pydantic schemas in `models`, configuration in `config.py`, and API startup in `api/main.py`. The frontend is a Vite Vue 3 TypeScript app skeleton under `frontend/src`, with TypeScript model contracts mirroring the backend.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, pydantic-settings, pytest, Vue 3, TypeScript, Vite, Ant Design Vue, Axios.

---

### Task 1: Project Structure and Backend Model Tests

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/schemas.py`
- Create: `backend/tests/test_schemas.py`
- Create: `backend/requirements.txt`
- Create: `backend/pytest.ini`

- [ ] **Step 1: Create backend dependency/test config files**

Create `backend/requirements.txt` with FastAPI/Pydantic/runtime/test dependencies and `backend/pytest.ini` with `pythonpath = .`.

- [ ] **Step 2: Write failing schema tests**

Add tests covering valid `TripPlanRequest`, date mismatch rejection, invalid coordinate rejection, mutable-list isolation, budget total validation, and temperature string parsing.

- [ ] **Step 3: Run schema tests and verify they fail**

Run: `python -m pytest backend/tests/test_schemas.py -v`

Expected: import failure for missing `app.models.schemas`.

- [ ] **Step 4: Implement Pydantic schemas**

Implement `Location`, `Attraction`, `Meal`, `Hotel`, `Budget`, `WeatherInfo`, `DayPlan`, `TripPlan`, and `TripPlanRequest` in `backend/app/models/schemas.py`.

- [ ] **Step 5: Run schema tests and verify they pass**

Run: `python -m pytest backend/tests/test_schemas.py -v`

Expected: all schema tests pass.

### Task 2: Backend Configuration and FastAPI Entrypoint

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/main.py`
- Create: `backend/app/api/routes/__init__.py`
- Create: `backend/app/api/routes/health.py`
- Create: `backend/tests/test_config_and_api.py`
- Create: `backend/.env.example`
- Create: `backend/run.py`

- [ ] **Step 1: Write failing config/API tests**

Add tests for default settings, environment overrides, `/api/health`, and CORS middleware registration.

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m pytest backend/tests/test_config_and_api.py -v`

Expected: import failure for missing `app.config` and `app.api.main`.

- [ ] **Step 3: Implement config and FastAPI app**

Implement `Settings`, `get_settings`, FastAPI app creation, health route, CORS config, `.env.example`, and `run.py`.

- [ ] **Step 4: Run config/API tests and verify they pass**

Run: `python -m pytest backend/tests/test_config_and_api.py -v`

Expected: all config/API tests pass.

### Task 3: Frontend Phase 0-2 Skeleton

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/router/index.ts`
- Create: `frontend/src/services/api.ts`
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/views/Home.vue`
- Create: `frontend/src/views/Result.vue`
- Create: `frontend/env.d.ts`
- Create: `frontend/.env.example`

- [ ] **Step 1: Create TypeScript/Vue skeleton files**

Mirror backend schemas in `frontend/src/types/index.ts`, configure Vue Router routes `/` and `/result`, and add Axios `generateTripPlan`.

- [ ] **Step 2: Run frontend install/typecheck when dependencies are available**

Run: `npm install` then `npm run typecheck`.

Expected: TypeScript compile succeeds. If package download fails, report the environment failure and leave the skeleton ready.

### Task 4: Final Verification

**Files:**
- Read: `SPEC.md`
- Read: generated files above

- [ ] **Step 1: Run backend test suite**

Run: `python -m pytest backend/tests -v`

Expected: all backend tests pass.

- [ ] **Step 2: Run Python compile check**

Run: `python -m compileall backend/app backend/tests`

Expected: no syntax errors.

- [ ] **Step 3: Run frontend typecheck if dependencies installed**

Run: `npm run typecheck` from `frontend`.

Expected: TypeScript compile succeeds, or document dependency-install blocker.

- [ ] **Step 4: Report deviations**

Report that git commit steps were skipped because `D:\agent\Trip_Planner` is not currently a git repository.
