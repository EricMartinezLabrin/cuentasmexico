from __future__ import annotations

from typing import Optional, Sequence

from .client import AIClient
from .config import get_active_provider, get_db_mcp_config, get_model_for_task
from .mcp_readonly_db import ReadOnlyDatabaseMCP


def build_default_db_mcp() -> ReadOnlyDatabaseMCP:
    cfg = get_db_mcp_config()
    return ReadOnlyDatabaseMCP(
        allowed_tables=cfg["allowed_tables"] or None,
        max_rows=int(cfg["max_rows"]),
        include_schema=bool(cfg["include_schema"]),
    )


def answer_question_with_db_context(
    *,
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
    question: str,
    queries: Sequence[str],
    system_prompt: Optional[str] = None,
    params_list: Optional[Sequence[Sequence[object]]] = None,
    limit: Optional[int] = None,
) -> str:
    """
    Ejecuta queries de solo lectura y responde con IA usando ese contexto.
    Compatible con OpenAI y Gemini.
    """
    mcp = build_default_db_mcp()
    context_text = mcp.build_context_text(
        question=question,
        queries=queries,
        params_list=params_list,
        limit=limit,
    )
    provider = provider_name or get_active_provider()
    model_name = model or get_model_for_task("text", provider=provider)
    if not model_name:
        raise ValueError(f"No hay modelo configurado para provider={provider} task=text")

    client = AIClient.from_provider_name(provider)
    result = client.generate(
        model=model_name,
        system_prompt=system_prompt
        or (
            "Eres analista de negocio. "
            "Responde con datos verificables del contexto SQL. "
            "Si no hay evidencia suficiente, dilo claramente."
        ),
        prompt=context_text,
    )
    return result.text
