import os
import httpx
import logging

logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

HEADERS = {"X-Internal-Key": SECRET_KEY}


async def register_user(telegram_id: int, phone_number: str, full_name: str, username: str, language: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{BACKEND_URL}/api/v1/bot/register",
            json={
                "telegram_id": telegram_id,
                "phone_number": phone_number,
                "full_name": full_name,
                "username": username,
                "language": language,
            },
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def get_categories(telegram_id: int) -> list:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{BACKEND_URL}/api/v1/bot/categories",
            params={"telegram_id": telegram_id},
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def get_last_transaction(telegram_id: int) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{BACKEND_URL}/api/v1/bot/last-transaction",
            params={"telegram_id": telegram_id},
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def create_transaction(
    telegram_id: int,
    amount: float,
    currency: str,
    tx_type: str,
    category_id: str,
    tx_date: str,
    note: str,
) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{BACKEND_URL}/api/v1/bot/transactions",
            json={
                "telegram_id": telegram_id,
                "amount": amount,
                "currency": currency,
                "type": tx_type,
                "category_id": category_id,
                "date": tx_date,
                "note": note,
            },
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def delete_transaction(telegram_id: int, transaction_id: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.delete(
            f"{BACKEND_URL}/api/v1/bot/transactions/{transaction_id}",
            params={"telegram_id": telegram_id},
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def update_transaction(telegram_id: int, transaction_id: str, fields: dict) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.put(
            f"{BACKEND_URL}/api/v1/bot/transactions/{transaction_id}",
            params={"telegram_id": telegram_id},
            json=fields,
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def create_category(telegram_id: int, name: str, cat_type: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{BACKEND_URL}/api/v1/bot/categories",
            json={"name": name, "type": cat_type, "telegram_id": telegram_id},
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def list_transactions(telegram_id: int, limit: int = 10) -> list:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{BACKEND_URL}/api/v1/bot/transactions",
            params={"telegram_id": telegram_id, "limit": limit},
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def query_natural_language(telegram_id: int, question: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BACKEND_URL}/api/v1/bot/query",
            json={"telegram_id": telegram_id, "question": question},
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json()
