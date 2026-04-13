# TaskFlow

A task management API where users can register, create projects, add tasks, and assign them to team members. Built with FastAPI, PostgreSQL, and Docker.

**Stack:** Python 3.12 · FastAPI · PostgreSQL 16 · SQLAlchemy Core · Alembic · JWT (HS256) · bcrypt · Docker

## Architecture Decisions

### Why FastAPI over Django/Flask?

FastAPI gives us three things that matter for this project:
1. **Automatic OpenAPI docs** — every endpoint is testable at `/docs` without Postman
2. **Pydantic validation** — request/response schemas are type-checked, and validation errors are automatically structured
3. **Async I/O** — non-blocking database calls via asyncpg, which matters when you're handling concurrent task updates

Django REST Framework would have worked but adds ORM ceremony the spec warns against. Flask would need more boilerplate for validation and docs.

### Why SQLAlchemy Core instead of the ORM?

The spec says: *"Schema must be managed via migrations — not auto-migrate or ORM magic."*

SQLAlchemy Core gives us:
- **Explicit SQL** — every query is visible as a SQL expression, not hidden behind `session.add()`
- **No identity map or lazy loading** — no surprise queries or N+1 problems
- **Migration-friendly** — table definitions serve as documentation, not as the schema source of truth

The tradeoff: more verbose code for inserts/updates. We accept this because transparency is worth more than convenience in a reviewed codebase.

### Repository pattern

Route handlers don't touch the database directly. Instead, they call repository functions (`user_repo.get_by_email()`, `task_repo.list_by_project()`). This keeps:
- **Routes** focused on HTTP: parsing requests, checking auth, returning status codes
- **Repositories** focused on data: building queries, handling filters

This makes each layer independently testable and prevents "god functions" that do everything.

### Authentication vs Authorization separation

- **Authentication (401)**: Handled by `get_current_user` dependency — extracts JWT, validates claims, loads user. If any step fails → 401 "unauthorized"
- **Authorization (403)**: Handled in each route handler — checks `project.owner_id == current_user.id` before allowing updates/deletes. If check fails → 403 "forbidden"

This separation is enforced structurally, not by convention.

### Schema design choices

- **`created_by` on tasks**: The spec requires "Delete task (project owner or task creator only)." Without tracking who created a task, we can't enforce this. This field isn't in the spec's data model, but it's necessary for the business rule.
- **PostgreSQL ENUMs**: `task_status` and `task_priority` are DB-level enums, not application strings. Invalid values are rejected at the database level, not just in Pydantic.
- **`updated_at` trigger**: A PostgreSQL trigger automatically updates `updated_at` on row modification. This is more reliable than application-level logic because it works regardless of how the row is updated.
- **Indexes**: `tasks.project_id`, `tasks.assignee_id`, and `tasks.status` are indexed because the list endpoint filters on all three.

## Running Locally

Prerequisites: Docker and Docker Compose installed.

```bash
git clone https://github.com/your-name/taskflow
cd taskflow
cp .env.example .env
docker compose up --build
# App available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

On first start:
1. PostgreSQL initializes (with healthcheck)
2. API container waits for PostgreSQL, then runs Alembic migrations
3. Seed script creates test user, project, and tasks
4. Uvicorn starts the API server on port 8000

## Running Migrations

Migrations run automatically on container start via `entrypoint.sh`. To run manually:

```bash
# Inside the API container
docker compose exec api alembic upgrade head

# To rollback
docker compose exec api alembic downgrade -1
```

## Test Credentials

Seed data is created automatically on first startup:

```
Email:    test@example.com
Password: password123
```

This user owns a project called "Website Redesign" with 3 tasks in different statuses (todo, in_progress, done).

## API Reference

All endpoints return `Content-Type: application/json`. Non-auth endpoints require `Authorization: Bearer <token>`.

Once the server is running, open **http://localhost:8000/docs** in your browser to access the interactive Swagger UI. You can test every endpoint directly from the browser:

1. Call `POST /auth/login` with `{"email":"test@example.com","password":"password123"}`
2. Copy the `token` from the response
3. Click the **Authorize** button (top right), paste the token, and click **Authorize**
4. All subsequent requests will include the JWT automatically


### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register with name, email, password |
| POST | `/auth/login` | Returns a JWT access token |

**Register:**
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name": "Jane Doe", "email": "jane@example.com", "password": "secret123"}'
```
Response (201):
```json
{
  "token": "<jwt>",
  "user": { "id": "uuid", "name": "Jane Doe", "email": "jane@example.com", "created_at": "..." }
}
```

**Login:**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
```
Response (200): Same shape as register.

### Projects

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/projects` | List projects (supports `?page=` and `?limit=`) |
| POST | `/projects` | Create a project (owner = current user) |
| GET | `/projects/:id` | Get project details + its tasks |
| PATCH | `/projects/:id` | Update name/description (owner only) |
| DELETE | `/projects/:id` | Delete project and all its tasks (owner only) |
| GET | `/projects/:id/stats` | Task counts by status and by assignee (bonus) |

**List projects (with pagination):**
```bash
curl "http://localhost:8000/projects?page=1&limit=10" -H "Authorization: Bearer <token>"
```
Response (200):
```json
{
  "projects": [
    { "id": "uuid", "name": "Website Redesign", "description": "Q2 project", "owner_id": "uuid", "created_at": "..." }
  ],
  "page": 1,
  "limit": 10,
  "total": 1
}
```

**Create project:**
```bash
curl -X POST http://localhost:8000/projects \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Q3 Launch", "description": "Product launch tasks"}'
```
Response (201): Returns the created project object.

**Get project detail:**
```bash
curl http://localhost:8000/projects/<id> -H "Authorization: Bearer <token>"
```
Response (200): Project object with `tasks` array included.

**Update project:**
```bash
curl -X PATCH http://localhost:8000/projects/<id> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Updated Name"}'
```
Response (200): Returns updated project object.

**Delete project:**
```bash
curl -X DELETE http://localhost:8000/projects/<id> -H "Authorization: Bearer <token>"
```
Response: 204 No Content

**Project stats (bonus):**
```bash
curl http://localhost:8000/projects/<id>/stats -H "Authorization: Bearer <token>"
```
Response (200):
```json
{
  "total": 3,
  "by_status": { "todo": 1, "in_progress": 1, "done": 1 },
  "by_assignee": { "<user_uuid>": 2, "unassigned": 1 }
}

### Tasks

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/projects/:id/tasks` | List tasks — supports `?status=`, `?assignee=`, `?page=`, `?limit=` |
| POST | `/projects/:id/tasks` | Create a task |
| PATCH | `/tasks/:id` | Update title, description, status, priority, assignee, due_date |
| DELETE | `/tasks/:id` | Delete task (project owner or task creator only) |

**List tasks with filters and pagination:**
```bash
curl "http://localhost:8000/projects/<id>/tasks?status=todo&page=1&limit=10" \
  -H "Authorization: Bearer <token>"
```
Response (200):
```json
{
  "tasks": [ { "id": "uuid", "title": "Design homepage", "status": "todo", ... } ],
  "page": 1,
  "limit": 10,
  "total": 1
}
```

**Create task:**
```bash
curl -X POST http://localhost:8000/projects/<project_id>/tasks \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Design homepage", "priority": "high", "assignee_id": "uuid", "due_date": "2026-05-01"}'
```
Response (201): Returns created task object.

**Update task:**
```bash
curl -X PATCH http://localhost:8000/tasks/<task_id> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"status": "done", "priority": "low"}'
```
Response (200): Returns updated task object.

**Delete task:**
```bash
curl -X DELETE http://localhost:8000/tasks/<task_id> -H "Authorization: Bearer <token>"
```
Response: 204 No Content

### Error Responses

| Status | Body | When |
|--------|------|------|
| 400 | `{"error": "validation failed", "fields": {"email": "is required"}}` | Invalid request body |
| 401 | `{"error": "unauthorized"}` | Missing/invalid JWT or wrong credentials |
| 403 | `{"error": "forbidden"}` | Valid user but not allowed (e.g., non-owner update) |
| 404 | `{"error": "not found"}` | Resource doesn't exist |
| 409 | `{"error": "email already registered"}` | Duplicate email on register |

## Project Structure

```
taskflow/
├── docker-compose.yml          # PostgreSQL + API services
├── .env.example                # All required env vars with defaults
├── README.md
└── backend/
    ├── Dockerfile              # Multi-stage: builder → runtime (non-root)
    ├── entrypoint.sh           # Wait for DB → migrate → seed → start
    ├── requirements.txt        # Pinned dependencies
    ├── alembic.ini
    ├── alembic/
    │   ├── env.py
    │   └── versions/
    │       └── 001_initial_schema.py   # Up + down migration
    ├── seed.py                 # Idempotent test data
    ├── tests/                  # Integration tests (pytest)
    │   ├── conftest.py
    │   ├── test_integration_auth.py
    │   ├── test_integration_projects.py
    │   └── test_integration_tasks.py
    └── app/
        ├── main.py             # App setup, CORS, shutdown
        ├── config.py           # Env var loading via Pydantic
        ├── database.py         # Async connection pool
        ├── models.py           # SQLAlchemy Core tables
        ├── security.py         # JWT + bcrypt
        ├── dependencies.py     # get_current_user DI
        ├── exceptions.py       # Error handlers (400/401/403/404)
        ├── schemas/            # Pydantic request/response models
        │   ├── auth.py
        │   ├── project.py
        │   └── task.py
        ├── routes/             # API endpoints
        │   ├── auth.py
        │   ├── projects.py
        │   └── tasks.py
        └── repositories/       # Database queries
            ├── user_repo.py
            ├── project_repo.py
            └── task_repo.py
```

## Bonus Features Implemented

- **Pagination**: All list endpoints support `?page=` and `?limit=` with total count in responses.
- **Stats endpoint**: `GET /projects/:id/stats` returns task counts grouped by status and by assignee.
- **Integration tests**: 65 tests covering all endpoints, validation, authorization, error cases, and edge cases. Run with `docker compose exec api pytest tests/ -v`.

## What I'd Do With More Time

### Things I'd add

- **Rate limiting**: Auth endpoints are vulnerable to brute force. Would add `slowapi` or handle at the reverse proxy level.
- **Request ID tracing**: Add `X-Request-ID` header propagation so logs can be correlated across requests.

### Shortcuts I took

- **CORS is wide open** (`allow_origins=["*"]`): Fine for development, but production would restrict to the frontend domain.
- **No refresh tokens**: Single 24h JWT. Production would use short-lived access tokens with refresh token rotation.
- **Seed script uses sync driver**: The seed runs at startup with psycopg2 (sync) because it's simpler than setting up async for a one-time script. This is fine for a startup task.
- **No email verification**: Users can register with any email. Production would verify ownership before activating.
- **Password policy is minimal**: We enforce 6+ characters. Production would check against breach databases (Have I Been Pwned k-anonymity API).

### Design tradeoffs

- **Repository functions vs ORM models**: More boilerplate per query, but every SQL operation is explicit and reviewable. For a project this size, the overhead is minimal.
- **Global exception handlers vs per-route try/catch**: We chose global handlers for consistency. The risk is that unexpected exceptions could leak info — but our handlers only return generic messages.
- **PostgreSQL ENUMs vs check constraints**: ENUMs are stricter but harder to modify (requires migration to add values). For a stable set like `todo/in_progress/done`, this is the right call.
