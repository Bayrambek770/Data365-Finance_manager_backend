import json
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import date
import uuid

from backend.core.dependencies import verify_internal_key, get_db
from backend.core.config import settings
from backend.models.user import User, generate_unique_code
from backend.models.transaction import Transaction
from backend.models.category import Category
from backend.schemas.user import BotRegisterRequest, BotRegisterResponse
from backend.schemas.transaction import BotTransactionCreate, TransactionResponse
from backend.services import transaction_service
from backend.services.budget_service import check_budget_warning

router = APIRouter(prefix="/bot", tags=["bot-internal"])


# ── Register / User ──────────────────────────────────────────────────────────

@router.post("/register", response_model=BotRegisterResponse)
def bot_register(
    data: BotRegisterRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_key),
):
    is_new_user = False
    user = db.query(User).filter(User.telegram_id == data.telegram_id).first()

    if not user:
        is_new_user = True
        unique_code = generate_unique_code()
        # Ensure uniqueness
        while db.query(User).filter(User.unique_code == unique_code).first():
            unique_code = generate_unique_code()

        user = User(
            telegram_id=data.telegram_id,
            phone_number=data.phone_number,
            full_name=data.full_name,
            username=data.username,
            language=data.language,
            unique_code=unique_code,
            is_registered=not data.phone_number.startswith("tg_"),
        )
        db.add(user)
    else:
        # Update mutable fields
        if data.phone_number and not data.phone_number.startswith("tg_"):
            user.phone_number = data.phone_number
            user.is_registered = True
        if data.full_name:
            user.full_name = data.full_name
        if data.username:
            user.username = data.username
        if data.language:
            user.language = data.language

    db.commit()
    db.refresh(user)

    dashboard_url = f"{settings.FRONTEND_URL}/dashboard/{user.unique_code}"
    return {
        "unique_code": user.unique_code,
        "dashboard_url": dashboard_url,
        "is_new_user": is_new_user,
        "is_registered": user.is_registered,
    }


# ── Transactions ──────────────────────────────────────────────────────────────

@router.post("/transactions")
def bot_create_transaction(
    data: BotTransactionCreate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_key),
):
    user = db.query(User).filter(User.telegram_id == data.telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from backend.schemas.transaction import TransactionCreate

    tx_data = TransactionCreate(
        amount=data.amount,
        currency=data.currency,
        type=data.type,
        category_id=data.category_id,
        date=data.date,
        note=data.note,
        source="bot",
    )
    return transaction_service.create_transaction(db, tx_data, user.id, source="bot")


@router.get("/categories")
def bot_get_categories(
    telegram_id: int = Query(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_key),
):
    categories = db.query(Category).order_by(Category.type, Category.name).all()
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "type": c.type.value,
            "is_default": c.is_default,
        }
        for c in categories
    ]


@router.post("/categories")
def bot_create_category(
    body: dict,
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_key),
):
    name = (body.get("name") or "").strip()
    cat_type = (body.get("type") or "").strip().lower()
    if not name:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Category name is required")
    if cat_type not in ("income", "expense"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Type must be income or expense")
    existing = db.query(Category).filter(Category.name.ilike(name)).first()
    if existing:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="Category already exists")
    cat = Category(name=name, type=cat_type, is_default=False)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return {"id": str(cat.id), "name": cat.name, "type": cat.type.value}


@router.get("/transactions")
def bot_list_transactions(
    telegram_id: int = Query(...),
    limit: int = Query(10),
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_key),
):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    txs = (
        db.query(Transaction)
        .filter(Transaction.user_id == user.id)
        .order_by(Transaction.date.desc(), Transaction.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(tx.id),
            "date": tx.date.isoformat(),
            "category_name": tx.category.name if tx.category else "",
            "type": tx.type.value,
            "amount": float(tx.amount),
            "currency": tx.currency,
            "note": tx.note or "",
        }
        for tx in txs
    ]


@router.get("/last-transaction")
def bot_last_transaction(
    telegram_id: int = Query(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_key),
):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    tx = (
        db.query(Transaction)
        .filter(Transaction.user_id == user.id)
        .order_by(Transaction.created_at.desc())
        .first()
    )
    if not tx:
        raise HTTPException(status_code=404, detail="No transactions found")

    return {
        "id": str(tx.id),
        "date": tx.date.isoformat(),
        "category_id": str(tx.category_id),
        "category_name": tx.category.name if tx.category else "",
        "note": tx.note,
        "amount": float(tx.amount),
        "currency": tx.currency,
        "type": tx.type.value,
        "source": tx.source.value,
    }


@router.put("/transactions/{transaction_id}")
def bot_update_transaction(
    transaction_id: uuid.UUID,
    data: dict,
    telegram_id: int = Query(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_key),
):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if str(tx.user_id) != str(user.id):
        raise HTTPException(status_code=403, detail="You can only edit your own transactions")

    from backend.schemas.transaction import TransactionUpdate

    update_data = TransactionUpdate(**{k: v for k, v in data.items() if v is not None})
    return transaction_service.update_transaction(db, tx, update_data)


@router.delete("/transactions/{transaction_id}")
def bot_delete_transaction(
    transaction_id: uuid.UUID,
    telegram_id: int = Query(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_key),
):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if str(tx.user_id) != str(user.id):
        raise HTTPException(status_code=403, detail="You can only delete your own transactions")

    transaction_service.delete_transaction(db, tx)
    return {"success": True}


# ── Natural Language Query ───────────────────────────────────────────────────

ALLOWED_SQL_PATTERN = re.compile(r"^\s*SELECT\b", re.IGNORECASE)

SAFE_TABLE_WHITELIST = {"transactions", "categories", "users", "budgets"}


def _is_safe_sql(sql: str) -> bool:
    stripped = sql.strip()
    if not ALLOWED_SQL_PATTERN.match(stripped):
        return False
    # Block destructive keywords
    for kw in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"):
        if re.search(rf"\b{kw}\b", stripped, re.IGNORECASE):
            return False
    return True


@router.post("/query")
def bot_query(
    body: dict,
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_key),
):
    telegram_id = body.get("telegram_id")
    question = body.get("question", "")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        from groq import Groq as GroqClient

        client = GroqClient(api_key=settings.GROQ_API_KEY)

        schema_ctx = """
Tables (PostgreSQL):
- transactions: id UUID, user_id UUID, amount NUMERIC, currency TEXT, type TEXT('income'/'expense'),
  category_id UUID, date DATE, note TEXT, source TEXT, created_at TIMESTAMP
- categories: id UUID, name TEXT, type TEXT('income'/'expense'), is_default BOOL
- users: id UUID, telegram_id BIGINT, phone_number TEXT, full_name TEXT, unique_code TEXT
- budgets: id UUID, category_id UUID, amount_limit NUMERIC, currency TEXT
"""
        sql_response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a SQL expert. Generate a safe, read-only PostgreSQL SELECT query.\n"
                        f"{schema_ctx}\n"
                        f"Always filter transactions to user_id = '{user.id}'.\n"
                        f"Return ONLY the raw SQL query with no markdown, backticks, or explanation."
                    ),
                },
                {"role": "user", "content": question},
            ],
            temperature=0,
        )

        raw_sql = sql_response.choices[0].message.content.strip()
        # Strip markdown code blocks if present
        raw_sql = re.sub(r"^```[a-z]*\n?", "", raw_sql, flags=re.IGNORECASE)
        raw_sql = re.sub(r"\n?```$", "", raw_sql)
        raw_sql = raw_sql.strip()

        if not _is_safe_sql(raw_sql):
            raise HTTPException(status_code=400, detail="Query not allowed")

        result = db.execute(text(raw_sql))
        rows = [dict(zip(result.keys(), row)) for row in result.fetchall()]

        answer_response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Convert this database query result into a natural language answer. "
                        "Respond in the same language as the question. Be concise."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nData: {json.dumps(rows, default=str)}",
                },
            ],
            temperature=0,
        )
        answer = answer_response.choices[0].message.content

        return {"answer": answer, "raw_data": rows}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(exc)}")
