# EventHub — Professional Events Aggregator

A curated aggregator for professional events: conferences, workshops, and meetups. Built with **FastAPI + SQLAlchemy + Jinja2**, deployed to EC2 via GitHub Actions.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Python 3.12 |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 17 |
| Migrations | Alembic |
| Templates | Jinja2 |
| Auth | JWT (HttpOnly cookie + Bearer token) |
| File Storage | AWS S3 |
| Deployment | Docker, GitHub Actions → EC2 |

---

## Project Structure

```
.
├── src/
│   ├── main.py                  # FastAPI entry point
│   ├── core/
│   │   ├── auth.py              # JWT, password hashing
│   │   └── database.py          # AsyncSession, engine
│   ├── models/                  # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── event.py
│   │   ├── organizer.py
│   │   ├── tag.py
│   │   ├── bookmark.py
│   │   ├── city.py
│   │   ├── country.py
│   │   └── audit_log.py
│   ├── schemas/                 # Pydantic schemas
│   ├── routers/
│   │   ├── frontend_route.py    # HTML pages (Jinja2)
│   │   ├── event_route.py       # REST API events
│   │   ├── auth_route.py        # REST API auth
│   │   ├── bookmark_route.py
│   │   ├── organizer_route.py
│   │   ├── tag_route.py
│   │   └── audit_route.py
│   ├── templates/               # Jinja2 templates
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── event_detail.html
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── bookmarks.html
│   │   └── admin/
│   │       ├── dashboard.html
│   │       ├── events.html
│   │       ├── event_form.html
│   │       ├── tags.html
│   │       ├── organizers.html
│   │       └── audit.html
│   └── static/
│       └── style.css
├── alembic/                     # DB migrations
├── Dockerfile
├── compose.yaml
├── requirements.txt
└── .env
```

---

## Local Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/eduardSie/eventhub.git
cd eventhub

python -m venv .venv
source .venv/bin/activate      

pip install -r requirements.txt
```

### 2. Create `.env`

```env
# Database (asyncpg for the app)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/uni_db

# Database (psycopg2 for Alembic)
DB_URL=postgresql://postgres:postgres@localhost:5432/uni_db

# JWT
SECRET_KEY=replace-with-a-random-string-at-least-32-chars
ACCESS_TOKEN_EXPIRE_MINUTES=60

# AWS S3 (optional)
S3_ENDPOINT=
S3_BUCKET=
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_REGION=eu-central-1
S3_PUBLIC_BASE=
```

### 3. Start PostgreSQL

```bash
docker compose up -d db
```

### 4. Apply migrations

```bash
alembic upgrade head
```

### 5. Run the application

```bash
uvicorn src.main:app --reload --port 8000
```

App: **http://localhost:8000**
Swagger UI: **http://localhost:8000/docs**

---

## Initial Data Setup

### Create the first admin

```bash
# Register via /register, then promote to admin:
docker exec -it $(docker compose ps -q db) psql -U postgres -d uni_db
UPDATE users SET role = 'admin' WHERE email = 'your@email.com';
\q
```

### Add data through the Admin Panel (order matters)

```
/admin/organizers  →  create organizers first
/admin/tags        →  create tags
/admin/events/new  →  create events, assign organizer and tags
```

---

## Pages

| URL | Description | Access |
|-----|-------------|--------|
| `/` | Event list with search and filters | Public |
| `/event/{id}` | Event detail page | Public |
| `/organizers` | Organizers list | Public |
| `/login` | Sign in | Guest |
| `/register` | Sign up | Guest |
| `/bookmarks` | Saved events | Authenticated |
| `/admin` | Admin dashboard | Admin |
| `/admin/events` | Manage events | Admin |
| `/admin/organizers` | Manage organizers | Admin |
| `/admin/tags` | Manage tags | Admin |
| `/admin/audit` | Change history log | Admin |
| `/docs` | Swagger UI (REST API) | Public |

---

## REST API

Base path: `/api/v1`

### Auth
| Method | URL | Description |
|--------|-----|-------------|
| POST | `/auth/register` | Register a new user |
| POST | `/auth/login` | Login (returns JWT) |
| GET | `/auth/me` | Get current user |
| PATCH | `/auth/me` | Update profile |

### Events
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/events` | List events (search & filters) |
| GET | `/event/{id}` | Get event by ID |
| POST | `/event` | Create event 🔒 Admin |
| PATCH | `/event/{id}` | Update event 🔒 Admin |
| DELETE | `/event/{id}` | Delete event 🔒 Admin |

### Bookmarks
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/bookmarks` | My bookmarks 🔒 |
| POST | `/bookmarks/{event_id}` | Add bookmark 🔒 |
| DELETE | `/bookmarks/{event_id}` | Remove bookmark 🔒 |

### Organizers / Tags / Audit
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/organizers` | List organizers |
| POST | `/organizers` | Create organizer 🔒 Admin |
| GET | `/tags` | List tags |
| POST | `/tags` | Create tag 🔒 Admin |
| DELETE | `/tags/{id}` | Delete tag 🔒 Admin |
| GET | `/audit` | Audit log 🔒 Admin |

---

## Deployment to EC2

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `EC2_HOST` | Public IP of your EC2 instance |
| `EC2_SSH_KEY` | Full contents of your `.pem` key file |

`GITHUB_TOKEN` is created by GitHub automatically — no action needed.



### Deploy

```bash
# Just push to the main branch
git push origin main
```


## Development

```bash

# Create a new migration after changing models
alembic revision --autogenerate -m "describe the change"
alembic upgrade head

# Roll back the last migration
alembic downgrade -1
```