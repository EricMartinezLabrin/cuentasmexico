import base64
import json
import re
from typing import Any, Dict, List

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from CuentasMexico.ai import AIClient
from CuentasMexico.ai.config import (
    get_active_provider,
    get_db_mcp_config,
    get_model_for_task,
    get_provider_api_key,
)
from CuentasMexico.ai.exceptions import AIProviderError
from CuentasMexico.ai.mcp_readonly_db import ReadOnlyDatabaseMCP
from CuentasMexico.ai.model_catalog import chat_model_choices
from CuentasMexico.ai.types import InputPart


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _throttle(request, limit: int = 20, window_sec: int = 60) -> bool:
    ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get(
        "REMOTE_ADDR", "unknown"
    )
    session_key = request.session.session_key or "anon"
    cache_key = f"ai_chat_rl:{ip}:{session_key}"
    current = cache.get(cache_key, 0)
    if current >= limit:
        return False
    cache.set(cache_key, current + 1, timeout=window_sec)
    return True


def _safe_text(value: Any) -> str:
    return (str(value or "")).strip()


def _compact_history(history: List[Dict[str, str]], max_turns: int) -> str:
    if not history:
        return ""
    sliced = history[-max_turns:]
    lines: List[str] = []
    for item in sliced:
        role = _safe_text(item.get("role")).lower()
        content = _safe_text(item.get("content"))
        if not content:
            continue
        short_content = content[:350]
        if role == "assistant":
            lines.append(f"Asistente: {short_content}")
        else:
            lines.append(f"Usuario: {short_content}")
    return "\n".join(lines)


def _looks_like_business_question(message: str) -> bool:
    text = (message or "").lower()
    hints = [
        "cliente",
        "clientes",
        "venta",
        "ventas",
        "facturacion",
        "facturación",
        "ingreso",
        "compras",
        "comprar",
        "sin comprar",
        "inactivo",
        "inactiva",
        "dias sin",
        "top",
        "mejor cliente",
        "ticket",
        "promedio",
    ]
    return any(token in text for token in hints)


def _history_looks_business(history: List[Dict[str, str]]) -> bool:
    if not history:
        return False
    recent = history[-6:]
    for item in recent:
        if _looks_like_business_question(_safe_text(item.get("content"))):
            return True
    return False


def _looks_like_non_db_request(message: str) -> bool:
    text = (message or "").strip().lower()
    if not text:
        return True

    casual_patterns = [
        r"^hola\b",
        r"^buen(?:os|as)\b",
        r"^gracias\b",
        r"^ok\b",
        r"^perfecto\b",
        r"^listo\b",
        r"^sale\b",
        r"^que puedes hacer\b",
        r"^qué puedes hacer\b",
        r"^ayuda\b",
    ]
    if any(re.search(p, text) for p in casual_patterns):
        if len(text) <= 30:
            return True

    content_patterns = [
        r"\btraduce\b",
        r"\bresume\b",
        r"\bparafrasea\b",
        r"\bortografia\b",
        r"\bortografía\b",
        r"\bredacta\b",
        r"\bcopy\b",
        r"\bimagen\b",
        r"\blogo\b",
        r"\bdiseñ[ao]\b",
    ]
    has_content_intent = any(re.search(p, text) for p in content_patterns)
    has_business = _looks_like_business_question(text)
    return has_content_intent and not has_business


def _count_mcp_score_signals(message: str, history: List[Dict[str, str]]) -> int:
    text = (message or "").lower()
    score = 0

    # Entidades de negocio / ventas.
    business_patterns = [
        r"\bcliente[s]?\b",
        r"\bventa[s]?\b",
        r"\bfacturaci[oó]n\b",
        r"\bingreso[s]?\b",
        r"\bpedido[s]?\b",
        r"\border(?:en|enes)?\b",
        r"\bticket\b",
        r"\bcompr[ao]s?\b",
        r"\bservicio[s]?\b",
        r"\bafiliad[oa]s?\b",
    ]
    if any(re.search(p, text) for p in business_patterns):
        score += 3

    # Intención analítica.
    analytics_patterns = [
        r"\bcu[aá]nt[oa]s?\b",
        r"\btotal(?:es)?\b",
        r"\bpromedio\b",
        r"\bsuma\b",
        r"\branking\b",
        r"\btop\b",
        r"\bcompar[ae]\b",
        r"\bvariaci[oó]n\b",
        r"\btendencia\b",
        r"\bcreci[oó]?\b",
        r"\bbaja\b",
        r"\balza\b",
        r"\blista(?:do)?\b",
        r"\bmuestr[ae]\b",
    ]
    if any(re.search(p, text) for p in analytics_patterns):
        score += 2

    # Ventana temporal o segmentación típica de BI.
    temporal_patterns = [
        r"\bhoy\b",
        r"\bayer\b",
        r"\bsemana\b",
        r"\bmes\b",
        r"\ba[ñn]o\b",
        r"\btrimestre\b",
        r"\bultim[oa]s?\b",
        r"\b20\d{2}\b",
    ]
    segmentation_patterns = [
        r"\bpa[ií]s\b",
        r"\bm[eé]xico\b",
        r"\bchile\b",
        r"\bcolombia\b",
        r"\bper[uú]\b",
        r"\bargentina\b",
        r"\bespa[ñn]a\b",
        r"\bvendedor\b",
        r"\bseller\b",
    ]
    if any(re.search(p, text) for p in temporal_patterns):
        score += 1
    if any(re.search(p, text) for p in segmentation_patterns):
        score += 1

    # Seguimiento conversacional ("y de esos..."), usando contexto de historial.
    follow_up_patterns = [
        r"\by (?:de|del|con)\b",
        r"\bde esos\b",
        r"\bdel top\b",
        r"\bel primero\b",
        r"\bel segundo\b",
        r"\bahora\b",
        r"\by en\b",
    ]
    if any(re.search(p, text) for p in follow_up_patterns) and _history_looks_business(history):
        score += 2

    return score


def _should_auto_use_mcp(message: str, history: List[Dict[str, str]]) -> bool:
    text = (message or "").strip()
    if not text:
        return False

    if _looks_like_non_db_request(text):
        return False

    score = _count_mcp_score_signals(text, history)
    has_fast_path_signal = _is_fast_heuristic_candidate(text)
    has_business_signal = _looks_like_business_question(text)
    follow_up_business = _history_looks_business(history) and len(text) <= 90

    # Regla híbrida: señales explícitas + respaldo por historial de negocio.
    return score >= 3 or has_fast_path_signal or (has_business_signal and follow_up_business)


def _extract_month_year_window(message: str):
    text = (message or "").lower()
    month_map = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "setiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }
    found_month = None
    for name, number in month_map.items():
        if name in text:
            found_month = (name, number)
            break
    if not found_month:
        return None

    year_match = re.search(r"(20\d{2})", text)
    year = int(year_match.group(1)) if year_match else None
    if not year:
        return None

    month_name, month_number = found_month
    start = f"{year:04d}-{month_number:02d}-01"
    if month_number == 12:
        end = f"{year+1:04d}-01-01"
    else:
        end = f"{year:04d}-{month_number+1:02d}-01"
    label = f"{month_name} {year}"
    return start, end, label


def _extract_country_filter(message: str):
    text = (message or "").lower()
    country_aliases = {
        "mexico": "mexico",
        "méxico": "mexico",
        "mx": "mexico",
        "chile": "chile",
        "colombia": "colombia",
        "peru": "peru",
        "perú": "peru",
        "argentina": "argentina",
        "españa": "espana",
        "espana": "espana",
    }
    for alias, normalized in country_aliases.items():
        if alias in text:
            return normalized
    return None


def _is_fast_heuristic_candidate(message: str) -> bool:
    text = (message or "").lower()
    has_date_window = _extract_month_year_window(message) is not None
    has_country = _extract_country_filter(message) is not None
    has_sales_intent = any(
        token in text
        for token in ["vend", "venta", "ventas", "facturacion", "facturación", "ingreso", "compras"]
    )
    has_inactivity_intent = any(
        token in text for token in ["sin comprar", "inactivo", "inactiva", "dias sin", "días sin"]
    )
    has_trend_intent = any(
        token in text
        for token in [
            "alza",
            "baja",
            "tendencia",
            "ultimos 3 años",
            "últimos 3 años",
            "ultimos tres años",
            "últimos tres años",
            "3 años",
        ]
    )
    return (
        (has_date_window and has_sales_intent)
        or (has_country and has_sales_intent)
        or has_inactivity_intent
        or has_trend_intent
    )


def _extract_json_object(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    # Limpieza de bloque markdown ```json ... ```
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    # Intento directo
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass
    # Intento por primer bloque {...}
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        chunk = raw[start : end + 1]
        try:
            obj = json.loads(chunk)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def _plan_dynamic_queries(
    *,
    question: str,
    history_text: str,
    provider: str,
    model: str,
    timeout_sec: int,
    mcp: ReadOnlyDatabaseMCP,
    schema_context: Dict[str, Any],
    previous_results: List[Dict[str, Any]],
    previous_errors: List[Dict[str, Any]],
    round_number: int,
) -> List[str]:
    planner_prompt = (
        "Eres un planificador SQL para MySQL en modo solo lectura.\n"
        "Tu tarea: generar consultas SQL que respondan la pregunta del usuario usando SOLO tablas/columnas del esquema.\n"
        "Relaciones clave del dominio:\n"
        "- adm_sale.customer_id -> auth_user.id\n"
        "- adm_userdetail.user_id -> auth_user.id\n"
        "- El país del cliente está en adm_userdetail.country\n"
        "Puedes usar TODOS los JOIN que necesites. No hay límite de joins por consulta.\n"
        "Reglas:\n"
        "1) Solo SELECT/WITH/SHOW/DESCRIBE/EXPLAIN.\n"
        "2) No escribas UPDATE/DELETE/INSERT.\n"
        "3) Máximo 4 consultas por ronda.\n"
        "4) Devuelve SOLO JSON válido con este formato:\n"
        '{"done":false,"queries":[{"name":"q1","sql":"SELECT ...","why":"..."}]}\n'
        "5) Si ya tienes evidencia suficiente, devuelve done=true y queries=[].\n"
        "6) Si hubo errores previos, corrige SQL basándote en esos errores.\n"
        "5) Usa aliases claros y fechas explícitas cuando aplique.\n\n"
        f"Ronda actual: {round_number}\n"
        f"Historial:\n{history_text or '(sin historial)'}\n\n"
        f"Pregunta:\n{question}\n\n"
        f"Resultados previos:\n{json.dumps(previous_results, ensure_ascii=False, default=str)}\n\n"
        f"Errores previos:\n{json.dumps(previous_errors, ensure_ascii=False, default=str)}\n\n"
        f"Esquema:\n{json.dumps(schema_context, ensure_ascii=False, default=str)}"
    )
    planner_client = AIClient.from_settings(timeout=timeout_sec)
    planner_result = planner_client.generate(
        model=model,
        prompt=planner_prompt,
        system_prompt="Devuelve únicamente JSON válido.",
        temperature=0.1,
        max_output_tokens=700,
    )
    payload = _extract_json_object(planner_result.text)
    queries: List[str] = []
    done = bool(payload.get("done")) if isinstance(payload, dict) else False
    for item in payload.get("queries", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        sql = _safe_text(item.get("sql"))
        if sql:
            queries.append(sql)
    return queries[:4], done


def _execute_queries_as_context(mcp: ReadOnlyDatabaseMCP, question: str, queries: List[str]) -> str:
    results = []
    for sql in queries:
        query_result = mcp.query(sql, limit=20)
        results.append(
            {
                "sql": query_result.sql,
                "row_count": query_result.row_count,
                "rows": query_result.rows,
            }
        )
    payload = {
        "question": question,
        "query_results": results,
    }
    return (
        "Contexto MCP (base de datos, solo lectura):\n"
        + json.dumps(payload, ensure_ascii=False, default=str, indent=2)
    )


def _run_universal_mcp_context(
    *,
    question: str,
    history_text: str,
    provider: str,
    model: str,
    timeout_sec: int,
    mcp: ReadOnlyDatabaseMCP,
) -> str:
    max_rounds = 2
    all_results: List[Dict[str, Any]] = []
    all_errors: List[Dict[str, Any]] = []
    try:
        schema_context = mcp.get_schema_context()
    except Exception:
        schema_context = {"tables": []}

    for round_number in range(1, max_rounds + 1):
        queries, done = _plan_dynamic_queries(
            question=question,
            history_text=history_text,
            provider=provider,
            model=model,
            timeout_sec=timeout_sec,
            mcp=mcp,
            schema_context=schema_context,
            previous_results=all_results,
            previous_errors=all_errors,
            round_number=round_number,
        )
        if done and all_results:
            break
        if not queries:
            break

        for sql in queries:
            try:
                result = mcp.query(sql, limit=20)
                all_results.append(
                    {
                        "sql": result.sql,
                        "row_count": result.row_count,
                        "rows": result.rows,
                    }
                )
            except Exception as exc:
                all_errors.append({"sql": sql, "error": str(exc)})

    payload = {
        "question": question,
        "query_results": all_results,
        "query_errors": all_errors,
    }
    return (
        "Contexto MCP (base de datos, solo lectura):\n"
        + json.dumps(payload, ensure_ascii=False, default=str, indent=2)
    )


def _build_mcp_business_context(question: str, *, user_id: int, is_superuser: bool) -> str:
    cfg = get_db_mcp_config()
    mcp = ReadOnlyDatabaseMCP(
        allowed_tables=cfg["allowed_tables"] or None,
        max_rows=min(int(cfg["max_rows"]), 30),
        include_schema=False,  # acelerar chat
    )
    q = (question or "").lower()
    country_filter = _extract_country_filter(question)
    if country_filter:
        country_sql = (
            f" AND LOWER(REPLACE(COALESCE(ud.country, ''), 'é', 'e')) LIKE '%{country_filter}%' "
        )
    else:
        country_sql = ""

    date_window = _extract_month_year_window(question)
    if any(
        k in q
        for k in [
            "alza",
            "baja",
            "tendencia",
            "ultimos 3 años",
            "últimos 3 años",
            "ultimos tres años",
            "últimos tres años",
            "3 años",
        ]
    ):
        seller_filter = "" if is_superuser else f" AND s.user_seller_id = {int(user_id)} "
        queries = [
            f"""
            SELECT
                YEAR(s.created_at) AS year,
                COUNT(*) AS total_sales,
                COALESCE(SUM(s.payment_amount), 0) AS total_revenue,
                COALESCE(AVG(s.payment_amount), 0) AS avg_ticket
            FROM adm_sale s
            INNER JOIN auth_user u ON u.id = s.customer_id
            LEFT JOIN adm_userdetail ud ON ud.user_id = u.id
            WHERE s.created_at >= DATE_SUB(CURDATE(), INTERVAL 3 YEAR)
              {seller_filter}
              {country_sql}
            GROUP BY YEAR(s.created_at)
            ORDER BY year ASC
            LIMIT 4
            """,
            f"""
            SELECT
                DATE_FORMAT(s.created_at, '%%Y-%%m') AS period_month,
                COUNT(*) AS total_sales,
                COALESCE(SUM(s.payment_amount), 0) AS total_revenue
            FROM adm_sale s
            INNER JOIN auth_user u ON u.id = s.customer_id
            LEFT JOIN adm_userdetail ud ON ud.user_id = u.id
            WHERE s.created_at >= DATE_SUB(CURDATE(), INTERVAL 36 MONTH)
              {seller_filter}
              {country_sql}
            GROUP BY DATE_FORMAT(s.created_at, '%%Y-%%m')
            ORDER BY period_month ASC
            LIMIT 36
            """,
        ]
    elif date_window:
        start, end, label = date_window
        seller_filter = "" if is_superuser else f" AND s.user_seller_id = {int(user_id)} "
        queries = [
            f"""
            SELECT
                '{label}' AS period_label,
                COALESCE(ud.country, 'Sin país') AS country,
                COUNT(*) AS total_sales,
                COALESCE(SUM(s.payment_amount), 0) AS total_revenue,
                MIN(s.created_at) AS first_sale_at,
                MAX(s.created_at) AS last_sale_at
            FROM adm_sale s
            INNER JOIN auth_user u ON u.id = s.customer_id
            LEFT JOIN adm_userdetail ud ON ud.user_id = u.id
            WHERE s.created_at >= '{start}'
              AND s.created_at < '{end}'
              {seller_filter}
              {country_sql}
            GROUP BY COALESCE(ud.country, 'Sin país')
            ORDER BY total_revenue DESC
            """,
            f"""
            SELECT
                DATE(s.created_at) AS sale_date,
                COUNT(*) AS sales_count,
                COALESCE(SUM(s.payment_amount), 0) AS revenue
            FROM adm_sale s
            INNER JOIN auth_user u ON u.id = s.customer_id
            LEFT JOIN adm_userdetail ud ON ud.user_id = u.id
            WHERE s.created_at >= '{start}'
              AND s.created_at < '{end}'
              {seller_filter}
              {country_sql}
            GROUP BY DATE(s.created_at)
            ORDER BY sale_date ASC
            LIMIT 31
            """,
            f"""
            SELECT
                u.id AS customer_id,
                u.username,
                COALESCE(u.email, '') AS email,
                COALESCE(ud.country, 'Sin país') AS country,
                COUNT(s.id) AS total_orders,
                COALESCE(SUM(s.payment_amount), 0) AS total_revenue
            FROM adm_sale s
            INNER JOIN auth_user u ON u.id = s.customer_id
            LEFT JOIN adm_userdetail ud ON ud.user_id = u.id
            WHERE s.created_at >= '{start}'
              AND s.created_at < '{end}'
              {seller_filter}
              {country_sql}
            GROUP BY u.id, u.username, u.email
            ORDER BY total_revenue DESC, total_orders DESC
            LIMIT 10
            """,
        ]
    elif any(k in q for k in ["sin comprar", "inactivo", "inactiva", "dias sin", "días sin", "lleva mas tiempo"]):
        seller_filter = "" if is_superuser else f" AND s.user_seller_id = {int(user_id)} "
        queries = [
            f"""
            SELECT
                u.id AS customer_id,
                u.username,
                COALESCE(u.email, '') AS email,
                COALESCE(ud.country, 'Sin país') AS country,
                MAX(s.created_at) AS last_purchase_at,
                TIMESTAMPDIFF(DAY, MAX(s.created_at), NOW()) AS days_since_last_purchase
            FROM adm_sale s
            INNER JOIN auth_user u ON u.id = s.customer_id
            LEFT JOIN adm_userdetail ud ON ud.user_id = u.id
            WHERE s.status = 1
              {seller_filter}
              {country_sql}
            GROUP BY u.id, u.username, u.email
            ORDER BY last_purchase_at ASC
            LIMIT 10
            """
        ]
    elif any(k in q for k in ["mejor cliente", "top cliente", "mas compra", "más compra", "facturacion", "facturación"]):
        seller_filter = "" if is_superuser else f" AND s.user_seller_id = {int(user_id)} "
        queries = [
            f"""
            SELECT
                u.id AS customer_id,
                u.username,
                COALESCE(u.email, '') AS email,
                COALESCE(ud.country, 'Sin país') AS country,
                COUNT(s.id) AS total_orders,
                COALESCE(SUM(s.payment_amount), 0) AS total_revenue
            FROM adm_sale s
            INNER JOIN auth_user u ON u.id = s.customer_id
            LEFT JOIN adm_userdetail ud ON ud.user_id = u.id
            WHERE s.status = 1
              {seller_filter}
              {country_sql}
            GROUP BY u.id, u.username, u.email
            ORDER BY total_revenue DESC, total_orders DESC
            LIMIT 10
            """
        ]
    else:
        seller_filter = "" if is_superuser else f" AND s.user_seller_id = {int(user_id)} "
        queries = [
            f"""
            SELECT
                u.id AS customer_id,
                u.username,
                COALESCE(u.email, '') AS email,
                COALESCE(ud.country, 'Sin país') AS country,
                COUNT(s.id) AS total_orders,
                COALESCE(SUM(s.payment_amount), 0) AS total_revenue
            FROM adm_sale s
            INNER JOIN auth_user u ON u.id = s.customer_id
            LEFT JOIN adm_userdetail ud ON ud.user_id = u.id
            WHERE s.status = 1
              {seller_filter}
              {country_sql}
            GROUP BY u.id, u.username, u.email
            ORDER BY total_revenue DESC, total_orders DESC
            LIMIT 10
            """,
            """
            SELECT
                COUNT(*) AS total_active_sales,
                COALESCE(SUM(payment_amount), 0) AS total_revenue_active,
                COALESCE(AVG(payment_amount), 0) AS avg_ticket
            FROM adm_sale
            WHERE status = 1
            """,
        ]
    return mcp.build_context_text(question=question, queries=queries, limit=10)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def ai_chat(request):
    referer = str(request.META.get("HTTP_REFERER", "") or "")
    if "/adm/" not in referer:
        return JsonResponse(
            {"success": False, "error": "El chat IA solo está disponible dentro de /adm."},
            status=403,
        )

    chat_enabled = _as_bool(getattr(settings, "AI_CHAT_ENABLED", True), True)
    if not chat_enabled:
        return JsonResponse({"success": False, "error": "El chat IA está deshabilitado."}, status=403)

    if not _throttle(
        request,
        limit=int(getattr(settings, "AI_CHAT_RATE_LIMIT", 20)),
        window_sec=int(getattr(settings, "AI_CHAT_RATE_WINDOW_SEC", 60)),
    ):
        return JsonResponse(
            {"success": False, "error": "Demasiadas solicitudes. Intenta de nuevo en un minuto."},
            status=429,
        )

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"success": False, "error": "JSON inválido."}, status=400)

    message = _safe_text(payload.get("message"))
    history = payload.get("history") if isinstance(payload.get("history"), list) else []
    images = payload.get("images") if isinstance(payload.get("images"), list) else []
    model_override = _safe_text(payload.get("model_override"))
    mcp_mode = _safe_text(payload.get("mcp_mode")).lower() or "auto"

    max_message_chars = int(getattr(settings, "AI_CHAT_MAX_MESSAGE_CHARS", 4000))
    max_images = int(getattr(settings, "AI_CHAT_MAX_IMAGES", 3))
    max_image_mb = int(getattr(settings, "AI_CHAT_MAX_IMAGE_MB", 4))
    history_turns = int(getattr(settings, "AI_CHAT_HISTORY_TURNS", 4))
    system_prompt = _safe_text(
        getattr(
            settings,
            "AI_CHAT_SYSTEM_PROMPT",
            "Eres un asistente útil para clientes de Cuentas México. "
            "Sé claro, breve y accionable. Si no sabes algo, dilo con honestidad.",
        )
    )

    if not message and not images:
        return JsonResponse({"success": False, "error": "Debes escribir un mensaje o adjuntar una imagen."}, status=400)

    if len(message) > max_message_chars:
        return JsonResponse(
            {"success": False, "error": f"Tu mensaje excede el máximo de {max_message_chars} caracteres."},
            status=400,
        )

    if len(images) > max_images:
        return JsonResponse(
            {"success": False, "error": f"Solo puedes enviar hasta {max_images} imágenes por mensaje."},
            status=400,
        )

    parts: List[InputPart] = []

    max_image_bytes = max_image_mb * 1024 * 1024
    accepted_mimes = {"image/png", "image/jpeg", "image/jpg", "image/webp"}

    for img in images:
        if not isinstance(img, dict):
            continue
        mime_type = _safe_text(img.get("mime_type")).lower() or "image/png"
        data_base64 = _safe_text(img.get("data_base64"))
        if not data_base64:
            continue
        if mime_type not in accepted_mimes:
            return JsonResponse(
                {"success": False, "error": f"Formato no permitido: {mime_type}"},
                status=400,
            )
        try:
            raw = base64.b64decode(data_base64, validate=True)
        except Exception:
            return JsonResponse({"success": False, "error": "Imagen inválida (base64)."}, status=400)
        if len(raw) > max_image_bytes:
            return JsonResponse(
                {"success": False, "error": f"Cada imagen debe pesar máximo {max_image_mb}MB."},
                status=400,
            )
        parts.append(InputPart.from_image(data=raw, mime_type=mime_type))

    context_history = _compact_history(history, history_turns)
    prompt_with_context = message
    if context_history:
        prompt_with_context = (
            "Historial reciente de conversación:\n"
            f"{context_history}\n\n"
            "Pregunta actual del usuario:\n"
            f"{message}"
        )

    provider = get_active_provider()
    # Para bajar latencia usamos modelo de texto cuando no hay imágenes.
    task = "hybrid" if len(parts) > 0 else "text"
    default_model = get_model_for_task(task, provider=provider) or get_model_for_task("text", provider=provider)
    model = default_model
    allowed_models = {value for value, _ in chat_model_choices(provider)}
    if model_override:
        if model_override not in allowed_models:
            return JsonResponse(
                {"success": False, "error": f"Modelo no permitido para chat: {model_override}"},
                status=400,
            )
        model = model_override

    if not model:
        return JsonResponse({"success": False, "error": "No hay modelo configurado para IA."}, status=500)
    provider_key = get_provider_api_key(provider)
    if not provider_key:
        return JsonResponse(
            {
                "success": False,
                "error": f"Falta API key para {provider}. Configúrala en /adm/settings/ai/update",
            },
            status=500,
        )

    try:
        using_mcp = False
        mcp_context = ""
        mcp_error = ""
        use_db_context = _as_bool(getattr(settings, "AI_CHAT_USE_DB_CONTEXT", True), True)
        should_try_mcp = (
            use_db_context
            and not parts
            and (
                mcp_mode == "force"
                or (mcp_mode == "auto" and _should_auto_use_mcp(message, history))
            )
        )
        if should_try_mcp:
            using_mcp = True
            try:
                mcp_cfg = get_db_mcp_config()
                allowed_tables = set(mcp_cfg["allowed_tables"] or [])
                if allowed_tables:
                    # Tablas base mínimas para cruzar ventas -> usuario -> user detail
                    allowed_tables.update({"adm_sale", "auth_user", "adm_userdetail"})
                mcp = ReadOnlyDatabaseMCP(
                    allowed_tables=allowed_tables or None,
                    max_rows=min(int(mcp_cfg["max_rows"]), 50),
                    include_schema=False,
                )
                fast_path = _is_fast_heuristic_candidate(message)
                # En modo force también usamos primero el motor universal iterativo.
                if mcp_mode == "force":
                    if fast_path:
                        mcp_context = _build_mcp_business_context(
                            question=message,
                            user_id=request.user.id,
                            is_superuser=bool(request.user.is_superuser),
                        )
                    else:
                        planning_model = get_model_for_task("text", provider=provider) or model
                        try:
                            mcp_context = _run_universal_mcp_context(
                                question=message,
                                history_text=context_history,
                                provider=provider,
                                model=planning_model,
                                timeout_sec=int(getattr(settings, "AI_CHAT_TIMEOUT_SEC", 25)),
                                mcp=mcp,
                            )
                        except Exception:
                            mcp_context = _build_mcp_business_context(
                                message,
                                user_id=request.user.id,
                                is_superuser=bool(request.user.is_superuser),
                            )
                else:
                    if fast_path:
                        mcp_context = _build_mcp_business_context(
                            message,
                            user_id=request.user.id,
                            is_superuser=bool(request.user.is_superuser),
                        )
                    else:
                        planning_model = get_model_for_task("text", provider=provider) or model
                        try:
                            mcp_context = _run_universal_mcp_context(
                                question=message,
                                history_text=context_history,
                                provider=provider,
                                model=planning_model,
                                timeout_sec=int(getattr(settings, "AI_CHAT_TIMEOUT_SEC", 25)),
                                mcp=mcp,
                            )
                        except Exception:
                            mcp_context = _build_mcp_business_context(
                                message,
                                user_id=request.user.id,
                                is_superuser=bool(request.user.is_superuser),
                            )
            except Exception as exc:
                # El chat debe seguir funcionando aunque falle el contexto DB.
                using_mcp = False
                mcp_context = ""
                mcp_error = f"No se pudo obtener contexto MCP de la base de datos. Detalle: {str(exc)}"
                if mcp_mode == "force":
                    return JsonResponse(
                        {
                            "success": False,
                            "error": "MCP forzado y falló la lectura de BD.",
                            "details": mcp_error,
                        },
                        status=500,
                    )

        if mcp_context:
            prompt_with_context = (
                (prompt_with_context or message or "")
                + "\n\n"
                + "Contexto MCP (base de datos, solo lectura):\n"
                + mcp_context
                + "\n\n"
                + "Si la pregunta pide datos de clientes/ventas, usa este contexto y menciónalo. "
                + "Cuando existan datos temporales (mes/año), responde con fechas concretas y números."
            )

        client = AIClient.from_settings(timeout=int(getattr(settings, "AI_CHAT_TIMEOUT_SEC", 25)))
        result = client.generate(
            model=model,
            prompt=prompt_with_context if prompt_with_context else None,
            parts=parts if parts else None,
            system_prompt=system_prompt,
            temperature=float(getattr(settings, "AI_CHAT_TEMPERATURE", 0.2)),
            max_output_tokens=int(getattr(settings, "AI_CHAT_MAX_OUTPUT_TOKENS", 220)),
        )
        answer = _safe_text(result.text) or "No pude generar una respuesta en este momento."
        return JsonResponse(
            {
                "success": True,
                "answer": answer,
                "provider": provider,
                "model": model,
                "default_model": default_model,
                "mcp_used": using_mcp,
                "mcp_mode": mcp_mode,
                "mcp_error": mcp_error,
            }
        )
    except AIProviderError as exc:
        details = ""
        if getattr(exc, "details", None):
            details = str(exc.details)
        return JsonResponse(
            {
                "success": False,
                "error": f"Error del proveedor IA: {str(exc)}",
                "details": details[:600],
            },
            status=500,
        )
    except Exception as exc:
        return JsonResponse(
            {
                "success": False,
                "error": f"No fue posible obtener respuesta del asistente: {str(exc)}",
                "details": str(exc)[:600],
            },
            status=500,
        )


@csrf_exempt
@login_required
@require_http_methods(["GET"])
def ai_chat_meta(request):
    referer = str(request.META.get("HTTP_REFERER", "") or "")
    if "/adm/" not in referer:
        return JsonResponse({"success": False, "error": "Disponible solo dentro de /adm."}, status=403)

    provider = get_active_provider()
    default_model = get_model_for_task("text", provider=provider) or ""
    options = [{"value": value, "label": label} for value, label in chat_model_choices(provider)]
    return JsonResponse(
        {
            "success": True,
            "provider": provider,
            "default_model": default_model,
            "options": options,
        }
    )
