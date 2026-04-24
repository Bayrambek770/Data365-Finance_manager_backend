# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Data365 Finance Manager is a business finance tracking system for small businesses in Uzbekistan. It consists of:

1. **FastAPI Backend** - REST API for managing transactions, budgets, categories, and analytics
2. **Telegram Bot** - Voice and text interface using Groq AI for natural language transaction logging
3. **PostgreSQL Database** - Stores users, transactions, categories, and budgets

The system supports multi-language input (Uzbek, Russian, English) and uses Groq's LLM for intent parsing and voice transcription.

## Architecture

### Database Models

All models use UUIDs for primary keys and inherit from `backend.database.Base`:

- **User** (`backend/models/user.py`): Identified by `telegram_id`, has unique `phone_number` and auto-generated `unique_code`
- **Category** (`backend/models/category.py`): Either "income" or "expense" type, can be default or custom
- **Transaction** (`backend/models/transaction.py`): Links user + category, tracks amount/currency/date/note, can originate from "bot" or "dashboard"
- **Budget** (`backend/models/budget.py`): One per expense category, defines monthly spending limit

### Backend Structure

- `backend/main.py` - FastAPI app initialization, CORS, logging, router registration under `/api/v1`
- `backend/routers/` - API endpoints (users, transactions, categories, budgets, analytics, overview, bot)
- `backend/services/` - Business logic (analytics calculations, budget status checking, transaction operations)
- `backend/schemas/` - Pydantic models for request/response validation
- `backend/core/config.py` - Environment-based settings (DATABASE_URL, GROQ_API_KEY, TELEGRAM_BOT_TOKEN, etc.)
- `backend/core/dependencies.py` - Dependency injection for DB sessions and user authentication

### Bot Structure

The Telegram bot (`bot/main.py`) handles:
- `/start` command and phone number registration
- Voice messages (transcribed via Groq Whisper)
- Text messages (parsed via Groq LLM for transaction intent)
- Inline keyboard callbacks

Key bot components:
- `bot/utils/groq_client.py` - Groq API wrapper for transcription, intent parsing, query answering
- `bot/utils/intent_parser.py` - Extracts transaction details from user messages, matches categories
- `bot/utils/api_client.py` - HTTP client for backend API calls
- `bot/handlers/` - Message/command handlers organized by type

### Database Management

- Migrations managed via **Alembic**
- Connection pooling enabled with `pool_pre_ping=True`
- Schema defined in `alembic/versions/001_initial_schema.py`
- Default categories seeded via `backend/seed.py` (run once on startup if categories table is empty)

### Analytics Engine

`backend/services/analytics_service.py` provides complex aggregations:
- Period-based comparisons (week, month, quarter, year) with trend calculations
- Category breakdowns with percentage of total and period-over-period changes
- Expense distribution by weekday
- Top categories by transaction count and amount
- 6-month income/expense history

## Development Commands

### Local Development (without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Setup database
createdb xisob
alembic upgrade head
python -m backend.seed

# Run backend
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Run bot (in separate terminal)
python -m bot.main
```

### Docker Deployment

```bash
# Start all services (db, backend, bot, frontend)
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f bot

# Stop services
docker-compose down

# Rebuild after code changes
docker-compose up -d --build
```

The Docker setup automatically runs migrations and seeds on startup via the backend service command.

### Database Operations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

## Environment Configuration

Required environment variables (see `.env.example`):

- `DATABASE_URL` - PostgreSQL connection string
- `GROQ_API_KEY` - For LLM and voice transcription
- `TELEGRAM_BOT_TOKEN` - Bot authentication
- `SECRET_KEY` - Application secret for sessions
- `BACKEND_URL` - Backend service URL (for bot communication)
- `FRONTEND_URL` - Frontend URL (for CORS)

## Key Implementation Details

### Transaction Source Tracking

Transactions have a `source` field indicating origin:
- `TransactionSource.bot` - Created via Telegram bot
- `TransactionSource.dashboard` - Created via web dashboard

### Budget Status Logic

Budget status determined in `backend/services/budget_service.py:get_budget_status()`:
- "exceeded" - >100% of limit spent
- "approaching" - 80-100% spent
- "safe" - <80% spent
- "no_budget" - No budget set

### Intent Parsing Flow

1. User sends voice/text to Telegram bot
2. Voice → Groq Whisper transcription
3. Text → `bot/utils/groq_client.py:parse_intent()` with category list context
4. LLM extracts: intent type, amount, currency, category, date, note, confidence
5. Category name matched to ID via fuzzy matching in `bot/utils/intent_parser.py`
6. Missing fields tracked in `missing_fields` array for follow-up prompts

### Analytics Period Calculations

`backend/services/analytics_service.py:get_period_bounds()` calculates current and previous period dates for trend comparisons. Week periods start on Monday.

## Testing

No test suite currently exists. When adding tests:
- Use pytest with async support for FastAPI endpoints
- Mock Groq API calls to avoid rate limits
- Use test database separate from development

## Common Patterns

### Adding a New Router

1. Create `backend/routers/new_router.py` with `APIRouter` instance
2. Import router in `backend/main.py`
3. Register with `app.include_router(new_router.router, prefix=PREFIX)`

### Adding New Bot Handler

1. Create handler function in `bot/handlers/`
2. Register in `bot/main.py` via `app.add_handler()`
3. Use `bot/utils/api_client.py` functions for backend communication

### Database Schema Changes

1. Modify model in `backend/models/`
2. Generate migration: `alembic revision --autogenerate -m "description"`
3. Review generated migration in `alembic/versions/`
4. Apply: `alembic upgrade head`
