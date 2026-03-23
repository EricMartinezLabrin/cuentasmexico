from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from django.db import connection

from .exceptions import AIProviderError


READONLY_START_RE = re.compile(r"^\s*(select|with|show|describe|desc|explain)\b", re.IGNORECASE)
FORBIDDEN_SQL_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|lock|unlock|call|set|use|commit|rollback)\b",
    re.IGNORECASE,
)


@dataclass
class QueryResult:
    sql: str
    rows: List[Dict[str, Any]]
    row_count: int


class ReadOnlyDatabaseMCP:
    """
    MCP local para exponer contexto de base de datos al LLM, en modo solo lectura.
    """

    def __init__(
        self,
        *,
        allowed_tables: Optional[Iterable[str]] = None,
        max_rows: int = 200,
        include_schema: bool = True,
    ) -> None:
        self.allowed_tables = set(t.strip() for t in (allowed_tables or []) if t.strip())
        self.max_rows = max_rows
        self.include_schema = include_schema

    def _strip_comments(self, sql: str) -> str:
        sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
        sql = re.sub(r"--.*?$", " ", sql, flags=re.MULTILINE)
        sql = re.sub(r"#.*?$", " ", sql, flags=re.MULTILINE)
        return sql.strip()

    def _validate_sql(self, sql: str) -> None:
        cleaned = self._strip_comments(sql)
        if not cleaned:
            raise AIProviderError("SQL vacío")
        if ";" in cleaned:
            raise AIProviderError("No se permiten múltiples sentencias SQL")
        if not READONLY_START_RE.search(cleaned):
            raise AIProviderError("Solo se permiten consultas de lectura")
        if FORBIDDEN_SQL_RE.search(cleaned):
            raise AIProviderError("Consulta contiene palabras no permitidas para modo solo lectura")

        if self.allowed_tables:
            lowered = cleaned.lower()
            touched = set()
            for table in self.allowed_tables:
                if re.search(rf"\b{re.escape(table.lower())}\b", lowered):
                    touched.add(table)
            table_like_refs = re.findall(r"(?:from|join)\s+([`\"\w\.]+)", lowered, flags=re.IGNORECASE)
            normalized_refs = {ref.replace("`", "").replace('"', "").split(".")[-1] for ref in table_like_refs}
            disallowed = normalized_refs - {t.lower() for t in self.allowed_tables}
            if disallowed:
                raise AIProviderError(
                    f"La consulta referencia tablas no permitidas: {', '.join(sorted(disallowed))}"
                )

    def _append_limit_if_needed(self, sql: str, limit: int) -> str:
        cleaned = sql.strip().lower()
        if cleaned.startswith(("show", "describe", "desc", "explain")):
            return sql
        if re.search(r"\blimit\s+\d+", cleaned):
            return sql
        return f"{sql.rstrip()} LIMIT {limit}"

    def get_schema_context(self) -> Dict[str, Any]:
        schema: Dict[str, Any] = {"tables": []}
        with connection.cursor() as cursor:
            tables = connection.introspection.table_names(cursor)
            if self.allowed_tables:
                tables = [t for t in tables if t in self.allowed_tables]
            for table in tables:
                description = connection.introspection.get_table_description(cursor, table)
                cols = []
                for col in description:
                    cols.append(
                        {
                            "name": col.name,
                            "type_code": str(getattr(col, "type_code", "")),
                            "null_ok": bool(getattr(col, "null_ok", True)),
                        }
                    )
                schema["tables"].append({"name": table, "columns": cols})
        return schema

    def query(
        self,
        sql: str,
        *,
        params: Optional[Sequence[Any]] = None,
        limit: Optional[int] = None,
    ) -> QueryResult:
        self._validate_sql(sql)
        hard_limit = min(limit or self.max_rows, self.max_rows)
        limited_sql = self._append_limit_if_needed(sql, hard_limit)

        with connection.cursor() as cursor:
            if params:
                cursor.execute(limited_sql, params)
            else:
                cursor.execute(limited_sql)
            columns = [col[0] for col in (cursor.description or [])]
            rows_raw = cursor.fetchall() if cursor.description else []

        rows = [dict(zip(columns, row)) for row in rows_raw]
        return QueryResult(sql=limited_sql, rows=rows, row_count=len(rows))

    def build_context_payload(
        self,
        *,
        question: str,
        queries: Sequence[str],
        params_list: Optional[Sequence[Sequence[Any]]] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        params_list = params_list or [()] * len(queries)
        if len(params_list) != len(queries):
            raise AIProviderError("params_list debe coincidir con la cantidad de queries")

        query_results: List[Dict[str, Any]] = []
        for sql, params in zip(queries, params_list):
            result = self.query(sql, params=params, limit=limit)
            query_results.append(
                {
                    "sql": result.sql,
                    "row_count": result.row_count,
                    "rows": result.rows,
                }
            )

        payload: Dict[str, Any] = {
            "question": question,
            "query_results": query_results,
        }
        if self.include_schema:
            payload["schema"] = self.get_schema_context()
        return payload

    def build_context_text(
        self,
        *,
        question: str,
        queries: Sequence[str],
        params_list: Optional[Sequence[Sequence[Any]]] = None,
        limit: Optional[int] = None,
    ) -> str:
        payload = self.build_context_payload(
            question=question,
            queries=queries,
            params_list=params_list,
            limit=limit,
        )
        return (
            "Contexto de base de datos (solo lectura).\n"
            "Responde usando unicamente la evidencia del contexto.\n\n"
            f"{json.dumps(payload, ensure_ascii=False, default=str, indent=2)}"
        )
