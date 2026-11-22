# TaskAPI

Task management REST API with FastAPI, SQLite, Argon2 password hashes, expiring JWTs, per-user task isolation and interactive OpenAPI docs.

## Setup

Install Python 3.12 and run `pip install -r requirements.txt`. Generate a private secret with `python -c "import secrets; print(secrets.token_hex(32))"`. Copy `.env.example` to `.env` and set `JWT_SECRET` to that value. Run `uvicorn app:app --env-file .env` (install python-dotenv if needed) or export the variables and run `uvicorn app:app`. Open http://127.0.0.1:8000/docs. Register, authorize with your credentials, and create tasks.

Docker: `docker build -t taskapi .` then `docker run --env-file .env -p 127.0.0.1:8000:8000 taskapi`. Use a persistent writable volume for permanent data. Use HTTPS and rate limiting in production.

Tests: `pip install -r requirements-dev.txt` and `pytest -q`.
