# Internet Applications Tournament System

## Objective
Create a full-featured online tournament management platform using Flask and PostgreSQL that satisfies the laboratory requirements (registration, tournament CRUD, participant workflows, ladders, result entry, and visualizations) before 22.01.2026.

## Target Stack
- **Backend:** Flask 3.x, SQLAlchemy ORM, Marshmallow for validation/serialization.
- **Database:** PostgreSQL 16 with alembic-managed migrations.
- **Auth:** Flask-Security-Too (or Flask-Login + custom flows) with JWT support for future extensions.
- **Frontend:** Server-side rendered Jinja templates enhanced with HTMX/Tailwind for interactivity (later can host SPA if needed).
- **Background/Async:** Celery + Redis (optional) for email confirmation, result reconciliation, and reminder emails.
- **Deployment:** Gunicorn + Nginx or Render/Fly.io; `.env` managed via python-dotenv.

## High-Level Architecture
- `app/__init__.py` creates the Flask app, configures DB, login manager, mail, rate limiting.
- Modular blueprints:
  - `auth`: registration, login, password reset, email confirmation.
  - `tournaments`: CRUD, sponsor assets, ladder visualization, search, signup flows.
  - `matches`: ladder generation, result entry, conflict handling.
  - `users`: dashboards for upcoming games/tournaments.
  - `admin`: management utilities, background job triggers.
- Services layer encapsulates business logic (e.g., `TournamentService`, `MatchService`).
- Repository layer for complex transactional queries to guarantee concurrent safety (uses `SELECT ... FOR UPDATE`).
- Scheduled jobs (Celery beat or APScheduler) to lock brackets once signup deadline passes and seed ladders.

## Data Model (first iteration)
- `users`: id, first_name, last_name, email (unique), password_hash, is_active, confirmation_token, confirmed_at, created_at, updated_at.
- `password_resets`: id, user_id, token, expires_at, used_at.
- `tournaments`: id, organizer_id (FK users), name, discipline, description, venue_name, location_lat, location_lng, google_maps_url, start_at, signup_deadline, max_participants, sponsor_assets (json), status, created_at, updated_at.
- `tournament_participants`: id, tournament_id, user_id, license_number (unique per tournament), ranking (unique per tournament), status (pending, accepted, waitlisted), seed, joined_at.
- `matches`: id, tournament_id, round_number, bracket_position, player_a_id, player_b_id, winner_id, reported_by_a, reported_by_b, report_status, played_at, locked_at.
- `notifications`: id, user_id, type, payload_json, sent_at.
- `audit_logs`: id, user_id, action, entity_type, entity_id, diff_json, created_at.

## Core Flows
1. **Registration & Confirmation**
   - POST `/auth/register` -> create inactive user, send Celery email with signed URL expiring in 24h.
   - GET `/auth/confirm/<token>` -> validate token, activate account.
2. **Login & Password Reset**
   - Session cookies with `Flask-Login`.
   - Forgot password issues signed token; user sets new password.
3. **Tournament Discovery**
   - `/` shows paginated upcoming tournaments sorted by start date, optional text search + filters.
4. **Tournament Management**
   - Organizer dashboard to create/edit tournaments; server validates no past dates, sponsor uploads stored on S3/bucket.
5. **Signup & Capacity Control**
   - POST `/tournaments/<id>/signup` with license/ranking.
   - DB transaction ensures uniqueness and seat availability (`SELECT ... FOR UPDATE` on tournament row and unique indexes on license/ranking per tournament).
6. **Ladder Generation**
   - After deadline `TournamentService.generate_ladder()` seeds participants (ranking-based) and creates matches tree depending on discipline (single elimination by default, adaptable plugin pattern).
7. **Result Entry & Conflict Resolution**
   - Both participants need to submit winner. If mismatch, mark conflict and push notification; allow re-entry after clearing.
8. **Visualization**
   - Bracket rendering using lightweight JS library (e.g., BracketBird) or custom SVG via HTMX partial updates.
9. **User Dashboard**
   - `/me` shows tournaments organizing, participating, and upcoming matches with statuses.

## Concurrency & Data Integrity
- Wrap signup and result entry in DB transactions using SQLAlchemy session scopes.
- Use DB-level constraints: composite unique indexes on (`tournament_id`, `license_number`) and (`tournament_id`, `ranking`).
- For ladder locking, store `status` (draft, seeded, running, completed) and block edits once seeded.
- Version columns (`updated_at`, `version`) for optimistic locking in critical tables.

## Security & Compliance
- Password hashing via `argon2-cffi` or `werkzeug.security.generate_password_hash` (pbkdf2:sha256).
- CSRF protection via Flask-WTF, forms use POST/Redirect/GET.
- Input validation with Marshmallow schemas per request.
- File uploads (sponsor logos) validated for type/size, stored in `/uploads` or cloud bucket with signed URLs.

## Testing Strategy
- Pytest with coverage, using `pytest-flask` fixture.
- Factories with `factory_boy`, Faker for sample data.
- Integration tests for signup race conditions (simulate concurrent inserts using threads + transactional rollbacks).

## Roadmap
1. Scaffold Flask project with config, env loading, database connection, and base blueprints.
2. Implement auth (registration, confirmation, login, reset) with tests.
3. Build tournament CRUD + listing/search with pagination.
4. Add signup flow + concurrency safeguards.
5. Implement ladder generation + visualization.
6. Implement match result workflows + user dashboards.
7. Polish UX, add sponsor/logo handling, finalize deployment pipeline.

## Immediate Next Steps
- Set up virtual environment, install dependencies, create `.env` template.
- Configure PostgreSQL connection and Alembic migrations.
- Build skeleton blueprints and templates.
