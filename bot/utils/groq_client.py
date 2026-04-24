import json
import os
from datetime import date
from typing import Optional
from groq import Groq


class GroqClient:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))

    def transcribe_voice(self, audio_file_path: str) -> str:
        with open(audio_file_path, "rb") as f:
            result = self.client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=f,
            )
        return result.text

    def parse_intent(self, text: str, categories: list) -> dict:
        categories_str = ", ".join(
            f"{c['name']} ({c['type']})" for c in categories
        )
        today = date.today().isoformat()

        system_prompt = f"""You are a financial assistant for a small business in Uzbekistan. \
The user may write in Uzbek, Russian, or English. Extract financial transaction information.

Available categories: {categories_str}
Today's date: {today}

Return ONLY valid JSON with this structure:
{{
  "intent": "log_transaction" | "query" | "edit_last" | "delete_last" | "unknown",
  "amount": number or null,
  "currency": "UZS" | "USD" or null,
  "type": "income" | "expense" or null,
  "category": "exact category name" or null,
  "date": "YYYY-MM-DD" or null,
  "note": "extracted note" or null,
  "missing_fields": ["amount", "category", ...],
  "confidence": 0.0 to 1.0,
  "original_language": "en" | "ru" | "uz"
}}

Rules:
- If amount is missing → add "amount" to missing_fields
- If type is missing but category suggests it → infer it
- If category is unclear → make best guess, set confidence below 0.8
- Never return null for intent"""

        response = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {
                "intent": "unknown",
                "missing_fields": [],
                "confidence": 0.0,
                "original_language": "en",
            }

    def answer_query(self, question: str, db_result: dict) -> str:
        response = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Convert this database query result into a natural language answer. "
                        "Respond in the same language as the question. "
                        "Be concise and use proper number formatting."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question: {question}\n\nData: {json.dumps(db_result, default=str)}"
                    ),
                },
            ],
            temperature=0,
        )
        return response.choices[0].message.content

    def translate_to_language(self, text: str, language: str) -> str:
        if language == "en":
            return text
        lang_names = {"ru": "Russian", "uz": "Uzbek"}
        lang_name = lang_names.get(language, "English")
        response = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Translate the following text to {lang_name}. "
                        "Return only the translation, no explanations."
                    ),
                },
                {"role": "user", "content": text},
            ],
            temperature=0,
        )
        return response.choices[0].message.content
