from __future__ import annotations

from typing import Protocol

import httpx

from app.config import Settings
from app.prompts.legal_assistant import SYSTEM_PROMPT


class LLMService(Protocol):
    async def answer(self, question: str, contexts: list[dict], history: list[dict]) -> str: ...

    async def health_check(self) -> dict[str, object]: ...


class OpenAICompatibleLLMService:
    def __init__(self, settings: Settings, fallback: LLMService | None = None):
        self.base_url = self._normalize_base_url(settings.resolved_llm_base_url)
        self.api_key = settings.resolved_llm_api_key
        self.model = settings.resolved_llm_model
        self.timeout = settings.llm_timeout_seconds
        self.max_retries = settings.llm_max_retries
        self.fallback = fallback

    async def answer(self, question: str, contexts: list[dict], history: list[dict]) -> str:
        context_text = "\n\n".join(
            f"[{item['title']} - {item.get('article') or 'không rõ điều'}] {item['content']}" for item in contexts
        )
        history_text = "\n".join(f"{item['role']}: {item['content']}" for item in history)
        try:
            payload = await self._post_json(
                "/chat/completions",
                {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": (
                                f"Hội thoại gần đây:\n{history_text or 'Chưa có'}\n\n"
                                f"Câu hỏi hiện tại: {question}\n\nNgữ cảnh truy xuất:\n{context_text}"
                            ),
                        },
                    ],
                    "temperature": 0.1,
                },
            )
            if payload:
                return payload["choices"][0]["message"]["content"].strip()
        except (httpx.HTTPError, KeyError, IndexError, TypeError):
            if self.fallback is None:
                raise
            return await self.fallback.answer(question, contexts, history)

    async def health_check(self) -> dict[str, object]:
        try:
            payload = await self._get_json("/models")
            models = [item.get("id") for item in payload.get("data", []) if isinstance(item, dict)]
            model_ready = not models or self.model in models
            result: dict[str, object] = {
                "ready": model_ready,
                "operational": model_ready or self.fallback is not None,
                "mode": "remote",
                "base_url": self.base_url,
                "model": self.model,
                "fallback_available": self.fallback is not None,
            }
            if not model_ready:
                result["error"] = f"Configured model '{self.model}' not exposed by remote LLM server"
                if self.fallback is not None:
                    result["degraded_reason"] = "Using fallback answerer because the configured remote model is unavailable"
            return result
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            return {
                "ready": False,
                "operational": self.fallback is not None,
                "mode": "remote",
                "base_url": self.base_url,
                "model": self.model,
                "fallback_available": self.fallback is not None,
                "error": str(exc),
                "degraded_reason": "Using fallback answerer because the remote LLM health check failed"
                if self.fallback is not None
                else "Remote LLM health check failed",
            }

    async def _post_json(self, path: str, payload: dict) -> dict:
        last_error: Exception | None = None
        for _ in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}{path}",
                        headers=self._headers(),
                        json=payload,
                    )
                    response.raise_for_status()
                    return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    async def _get_json(self, path: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}{path}", headers=self._headers())
            response.raise_for_status()
            return response.json()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        base = base_url.rstrip("/")
        return base if base.endswith("/v1") else f"{base}/v1"


class ExtractiveLLMService:
    async def answer(self, question: str, contexts: list[dict], history: list[dict]) -> str:
        if not contexts:
            return "Chưa có căn cứ trong kho dữ liệu để trả lời câu hỏi này. Hãy nạp thêm văn bản pháp luật liên quan."

        lead = "Dựa trên các văn bản đã nạp, tôi tìm được các căn cứ sau:"
        lines: list[str] = [lead]
        if history:
            last_user_question = next((item["content"] for item in reversed(history) if item["role"] == "user"), None)
            if last_user_question and last_user_question != question:
                lines.append(f"- Bối cảnh hội thoại trước đó: {last_user_question}")
        seen_articles: set[tuple[str, str | None]] = set()
        for item in contexts[:3]:
            key = (item["title"], item.get("article"))
            if key in seen_articles:
                continue
            seen_articles.add(key)
            article_label = item.get("article") or "Đoạn liên quan"
            excerpt = " ".join(item["content"].split())
            excerpt = excerpt[:220] + "..." if len(excerpt) > 220 else excerpt
            lines.append(f"- {item['title']} - {article_label}: {excerpt}")
        lines.append("Kết luận chỉ nên được sử dụng như công cụ tra cứu ban đầu; cần đối chiếu văn bản gốc trước khi áp dụng.")
        return "\n".join(lines)

    async def health_check(self) -> dict[str, object]:
        return {"ready": True, "operational": True, "mode": "local_fallback"}



def build_llm_service(settings: Settings) -> LLMService:
    fallback = ExtractiveLLMService()
    if settings.resolved_llm_base_url and settings.resolved_llm_model:
        return OpenAICompatibleLLMService(settings, fallback=fallback)
    return fallback
