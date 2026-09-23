"""FastAPI Router for AML Graph Copilot (AI-Assistant)."""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from agent import (
    ask_aml_agent,
    get_node_info,
    find_common_recipients,
    get_cluster_summary,
    AGENT_TOOLS,
    DEFAULT_TOKEN,
)

router = APIRouter(prefix="/api/copilot", tags=["AI Copilot"])


class CopilotQueryRequest(BaseModel):
    query: str = Field(..., description="Вопрос аналитика на естественном языке")
    api_key: Optional[str] = Field(None, description="OpenAI или NVIDIA API ключ (опционально)")
    base_url: Optional[str] = Field(None, description="Пользовательский base_url (например для NVIDIA NIM)")
    model: Optional[str] = Field("gpt-4o-mini", description="Идентификатор модели LLM")


class CopilotQueryResponse(BaseModel):
    query: str
    answer: str
    status: str = "success"


@router.post("/ask", response_model=CopilotQueryResponse, summary="Задать вопрос AI-ассистенту AML Copilot")
async def ask_copilot(payload: CopilotQueryRequest):
    """Принимает вопрос аналитика, вызывает инструменты графовой разведки

    (get_node_info, find_common_recipients, get_cluster_summary) и возвращает
    структурированный аналитический ответ.
    """
    if not payload.query or not payload.query.strip():
        raise HTTPException(status_code=400, detail="Запрос не может быть пустым.")

    try:
        answer = ask_aml_agent(
            query=payload.query.strip(),
            api_key=payload.api_key or DEFAULT_TOKEN,
            base_url=payload.base_url,
            model=payload.model or "gpt-4o-mini"
        )
        return CopilotQueryResponse(
            query=payload.query,
            answer=answer,
            status="success"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обработки запроса агентом: {str(e)}")


@router.get("/tools", summary="Получить спецификацию инструментов агента")
async def list_tools():
    """Возвращает спецификацию 3 инструментов агента в формате OpenAI Function Calling."""
    return {"tools": AGENT_TOOLS}


@router.get("/examples", summary="Примеры типовых вопросов для расследования")
async def list_examples():
    """Возвращает готовые вопросы для комплаенс-офицера."""
    return {
        "examples": [
            {
                "category": "Поиск казначея / аккумулятора",
                "query": "Кто аккумулирует средства с клиентов 100000000331309100 и 100000007629096100?",
                "tool": "find_common_recipients"
            },
            {
                "category": "Финансовый профиль узла",
                "query": "Каков профиль клиента 100000003115284100?",
                "tool": "get_node_info"
            },
            {
                "category": "Анализ сообщества",
                "query": "Дай аналитическую сводку по сообществу 11",
                "tool": "get_cluster_summary"
            },
            {
                "category": "Связи координатора",
                "query": "Покажи финансовый профиль узла 100000000331309100 и его обоснование",
                "tool": "get_node_info"
            }
        ]
    }
