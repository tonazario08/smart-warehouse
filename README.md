# Smart Warehouse

Phase 1 foundation for a warehouse management system.

## Local backend setup

1. Copy `.env.example` to `.env` and replace all placeholder secrets.
2. Create and activate a Python virtual environment.
3. Install development dependencies with `python -m pip install -e ".[dev]"`.
4. Run tests with `pytest`.
5. After applying migrations, seed local development data with `python -m app.seed`. The
   command reads all seed credentials from `.env` and never prints passwords.

Docker Compose configuration is included for PostgreSQL and the API. Docker Desktop must be installed before running `docker compose up --build`.
