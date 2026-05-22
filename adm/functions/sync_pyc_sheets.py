"""
Sincronización PYC basada en Google Sheets como source of truth.
"""

import base64
import json
import logging
import os
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings
from django.db import transaction

from adm.functions.whatsapp_queue import enqueue_whatsapp
from adm.models import Account, Sale, AccountChangeHistory, PaymentMethod, UserDetail


logger = logging.getLogger(__name__)

DEFAULT_SHEET_ID = "1eY2EWKjarh1a909CLSrL22lP5HVUF5CZzdM9SDHBT3M"
PASSWORD_HISTORY_FILE = "sync_pyc_password_changes_history.jsonl"

# Mapeo explícito de servicio -> pestaña objetivo
SERVICE_TAB_MAPPING = {
    "netflix": "Netflix",
    "netflix personal": "Netflix",
    "prime video": "Prime Video",
    "amazon prime": "Prime Video",
    "disney+": "Disney+",
    "disney plus": "Disney+",
    "hbo max": "HBO Max",
    "max": "HBO Max",
    "paramount+": "Paramount+",
    "paramount plus": "Paramount+",
    "crunchyroll": "Crunchyroll",
    "youtube premium": "YouTube Premium",
    "spotify premium": "Spotify Premium",
    "tnt": "TNT",
    "vix": "Vix",
    "iptv": "IPTV",
    "apple tv": "APPLE TV",
    "chatgpt": "CHATGPT",
    "canva": "CANVA",
    "otro servicio": "Otro Servicio",
    "seguidores o likes": "SEGUIDORES o LIKES",
}

# Servicios acordados para ignorar por completo en sync PYC.
EXPLICIT_IGNORED_UNMAPPED_SERVICES = {
    "disney.",
    "max.",
    "spotify",
    "tidal",
    "vix emergencias",
    "youtube",
}

@dataclass
class SheetRow:
    email: str
    password: str
    status: str
    profile: Optional[int]


def _normalize_text(value: Optional[str]) -> str:
    return (value or "").strip().lower()

def _needs_replacement_by_external_status(value: Optional[str]) -> bool:
    normalized = _normalize_text(value)
    return normalized in {"deleted", "suspendida"}


def _normalize_sheet_status_for_db(value: Optional[str]) -> str:
    normalized = _normalize_text(value)
    if normalized == "activa":
        return "Disponible"
    return (value or "").strip()


def _b64url_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("utf-8")


def _google_get_with_retry(url: str, headers: Dict[str, str], params=None, timeout: int = 30, max_attempts: int = 5):
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            res = requests.get(url, headers=headers, params=params, timeout=timeout)
            if res.status_code in (429, 500, 502, 503, 504):
                if attempt < max_attempts:
                    time.sleep(min(2 ** (attempt - 1), 8))
                    continue
            res.raise_for_status()
            return res
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts:
                time.sleep(min(2 ** (attempt - 1), 8))
                continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("Google request failed without exception")


def _build_google_access_token() -> str:
    service_account_email = os.getenv("GOOGLE_SERVICE_ACCOUNT_EMAIL", "").strip().strip('"')
    private_key = os.getenv("GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY", "").strip().strip('"')

    if not service_account_email or not private_key:
        raise ValueError("Google service account variables missing in .env")

    private_key = private_key.replace("\\n", "\n")

    header = {"alg": "RS256", "typ": "JWT"}
    now = int(time.time())
    claims = {
        "iss": service_account_email,
        "scope": "https://www.googleapis.com/auth/spreadsheets.readonly",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
    }

    encoded_header = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_claims = _b64url_encode(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    unsigned_jwt = f"{encoded_header}.{encoded_claims}"

    signer = serialization.load_pem_private_key(private_key.encode("utf-8"), password=None)
    signature = signer.sign(
        unsigned_jwt.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    signed_jwt = f"{unsigned_jwt}.{_b64url_encode(signature)}"

    token_res = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": signed_jwt,
        },
        timeout=30,
    )
    if token_res.status_code != 200:
        raise ValueError(f"Google token error: {token_res.text}")

    return token_res.json().get("access_token")


def _tab_from_service(service_name: str) -> Optional[str]:
    return SERVICE_TAB_MAPPING.get(_normalize_text(service_name))


def _is_explicit_ignored_unmapped_service(service_name: str) -> bool:
    return _normalize_text(service_name) in EXPLICIT_IGNORED_UNMAPPED_SERVICES


def _should_skip_email_notification(email: str) -> bool:
    normalized = (email or "").strip().lower()
    return normalized.endswith("@example.com")


def _parse_profile(value) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _password_history_path() -> str:
    logs_dir = os.path.join(settings.BASE_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return os.path.join(logs_dir, PASSWORD_HISTORY_FILE)


def append_password_change_history(entry: Dict):
    payload = dict(entry)
    payload.setdefault("timestamp", datetime.utcnow().isoformat() + "Z")
    with open(_password_history_path(), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def read_password_change_history(limit: int = 200) -> List[Dict]:
    path = _password_history_path()
    if not os.path.exists(path):
        return []
    rows: List[Dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return list(reversed(rows[-max(1, limit):]))


class PycSheetSyncService:
    def __init__(self, sheet_id: Optional[str] = None, progress_callback=None, task_id: Optional[str] = None):
        self.sheet_id = sheet_id or os.getenv("SHEETS_PYC_ID") or DEFAULT_SHEET_ID
        self.progress_callback = progress_callback
        self.task_id = task_id
        self.summary = {
            "processed": 0,
            "updated_password": 0,
            "updated_external_status": 0,
            "updated_profile": 0,
            "reactivated_accounts": 0,
            "marked_deleted": 0,
            "ignored_unmapped": 0,
            "ignored_explicit_unmapped": 0,
            "skipped_delete_by_service_guard": 0,
            "notified_whatsapp": 0,
            "notified_email": 0,
            "replaced_deleted_accounts": 0,
            "aborted": False,
            "abort_reason": "",
            "warnings": [],
            "errors": [],
        }
        self._total_accounts = 0
        self._max_missing_ratio = 0.35
        self._min_index_rows = 200
        self._service_missing_ratio_guard = 0.20
        self._service_missing_min_expected = 20
        # Por defecto: si no existe en su pestaña objetivo, marcar deleted.
        # Se puede desactivar con PYC_SYNC_ALLOW_MISSING_DELETE=false.
        self._allow_missing_delete = os.getenv("PYC_SYNC_ALLOW_MISSING_DELETE", "true").strip().lower() in {
            "1", "true", "yes", "on"
        }
        self._initial_customer_account_ids = set()

    def _progress(self, message: str):
        if self.progress_callback:
            try:
                self.progress_callback(message)
            except Exception:
                pass

    def _replace_deleted_account_for_customer(self, account: Account, trigger: str):
        active_sale = (
            Sale.objects.select_related("customer", "user_seller", "business")
            .filter(account=account, status=True, customer__isnull=False)
            .first()
        )
        if not active_sale:
            return

        replacement = (
            Account.objects.filter(
                account_name=account.account_name,
                status=True,
                customer__isnull=True,
                external_status="Disponible",
            )
            .exclude(pk=account.pk)
            .order_by("expiration_date", "id")
            .first()
        )
        if not replacement:
            self.summary["warnings"].append(
                f"Cuenta deleted sin reemplazo disponible: account_id={account.id} service={account.account_name.description}"
            )
            return

        try:
            payment_change, _ = PaymentMethod.objects.get_or_create(description="Cambio")
            old_sale = active_sale
            old_customer = old_sale.customer

            with transaction.atomic():
                old_sale.status = False
                old_sale.save(update_fields=["status"])

                account.customer = None
                account.status = False
                account.save(update_fields=["customer", "status"])

                new_sale = Sale.objects.create(
                    business=old_sale.business,
                    user_seller=old_sale.user_seller,
                    bank=old_sale.bank,
                    customer=old_customer,
                    account=replacement,
                    status=True,
                    payment_method=payment_change,
                    expiration_date=old_sale.expiration_date,
                    payment_amount=0,
                    invoice="Cambio",
                )

                old_sale.old_acc = new_sale.id
                old_sale.save(update_fields=["old_acc"])

                replacement.customer = old_customer
                replacement.modified_by = old_sale.user_seller
                replacement.save(update_fields=["customer", "modified_by"])

                customer_phone = None
                try:
                    customer_phone = old_customer.userdetail.phone_number
                except Exception:
                    customer_phone = None

                AccountChangeHistory.objects.create(
                    source="admin",
                    customer=old_customer,
                    changed_by=old_sale.user_seller,
                    service=account.account_name,
                    old_sale=old_sale,
                    new_sale=new_sale,
                    old_account=account,
                    new_account=replacement,
                    customer_username=old_customer.username,
                    customer_email=old_customer.email,
                    customer_phone=customer_phone,
                    old_account_email=account.email,
                    new_account_email=replacement.email,
                    old_account_profile=account.profile,
                    new_account_profile=replacement.profile,
                    old_sale_expiration=old_sale.expiration_date,
                    new_sale_expiration=new_sale.expiration_date,
                    notes=f"Cambio automático por sync ({trigger}) al detectar external_status deleted.",
                )

            exp_text = old_sale.expiration_date.strftime("%d/%m/%Y")
            message = (
                f"Detectamos un error en tu cuenta {account.account_name.description} - {account.email}, "
                f"por lo que te la cambiamos.\n"
                f"Nueva cuenta:\n"
                f"Servicio: {replacement.account_name.description}\n"
                f"Email: {replacement.email}\n"
                f"Clave: {replacement.password}\n"
                f"Perfil: {replacement.profile}\n"
                f"Fecha de vencimiento: {exp_text}"
            )
            self._notify_replacement_change(old_customer, message, replacement, exp_text)

            self.summary["replaced_deleted_accounts"] += 1
        except Exception as exc:
            self.summary["errors"].append(
                f"Error cambiando cuenta deleted account_id={account.id}: {exc}"
            )

    def _notify_replacement_change(self, customer, message: str, replacement: Account, exp_text: str):
        # WhatsApp (encolado)
        try:
            detail = UserDetail.objects.get(user=customer)
            enqueue_whatsapp(message=message, lada=str(detail.lada), phone_number=str(detail.phone_number))
            self.summary["notified_whatsapp"] += 1
        except Exception as exc:
            self.summary["warnings"].append(
                f"No se pudo encolar WhatsApp de cambio automático customer_id={customer.id}: {exc}"
            )

        # Email (solo al email del cliente)
        customer_email = (customer.email or "").strip()
        if not customer_email:
            self.summary["warnings"].append(
                f"Cliente sin email para cambio automático customer_id={customer.id}"
            )
            return
        if _should_skip_email_notification(customer_email):
            self.summary["warnings"].append(
                f"Email omitido por dominio bloqueado (@example.com) customer_id={customer.id}"
            )
            return

        try:
            import resend

            resend.Emails.send(
                {
                    "from": "noreply@cuentasmexico.com",
                    "to": customer_email,
                    "subject": f"Cambio de cuenta - {replacement.account_name.description}",
                    "html": (
                        f"<p>Detectamos un error en tu cuenta y la cambiamos automáticamente.</p>"
                        f"<ul>"
                        f"<li><b>Servicio:</b> {replacement.account_name.description}</li>"
                        f"<li><b>Email:</b> {replacement.email}</li>"
                        f"<li><b>Clave:</b> {replacement.password}</li>"
                        f"<li><b>Perfil:</b> {replacement.profile}</li>"
                        f"<li><b>Fecha de vencimiento:</b> {exp_text}</li>"
                        f"</ul>"
                        f"<p>Gracias por tu preferencia.</p>"
                    ),
                }
            )
            self.summary["notified_email"] += 1
        except Exception as exc:
            self.summary["warnings"].append(
                f"No se pudo enviar email de cambio automático customer_id={customer.id}: {exc}"
            )

    def _fetch_sheet_names(self, token: str) -> List[str]:
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{self.sheet_id}"
        response = _google_get_with_retry(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={"fields": "sheets(properties(title))"},
            timeout=30,
        )
        payload = response.json()
        return [
            sheet.get("properties", {}).get("title")
            for sheet in payload.get("sheets", [])
            if sheet.get("properties", {}).get("title")
        ]

    def _build_tab_index(self, token: str) -> Tuple[Dict[str, Dict[str, SheetRow]], Dict[str, Dict[str, List[SheetRow]]]]:
        tab_index: Dict[str, Dict[str, SheetRow]] = {}
        tab_loose_index: Dict[str, Dict[str, List[SheetRow]]] = {}
        tab_names = set(self._fetch_sheet_names(token))
        target_tabs = sorted(set(SERVICE_TAB_MAPPING.values()))
        existing_tabs = [tab_name for tab_name in target_tabs if tab_name in tab_names]
        missing_tabs = [tab_name for tab_name in target_tabs if tab_name not in tab_names]
        for tab_name in missing_tabs:
            self.summary["warnings"].append(f"Pestaña no encontrada en sheet: {tab_name}")

        if not existing_tabs:
            return tab_index, tab_loose_index

        response = _google_get_with_retry(
            f"https://sheets.googleapis.com/v4/spreadsheets/{self.sheet_id}/values:batchGet",
            headers={"Authorization": f"Bearer {token}"},
            params=[("ranges", f"'{tab_name}'!A1:ZZ") for tab_name in existing_tabs],
            timeout=60,
        )

        value_ranges = response.json().get("valueRanges", [])
        for value_range in value_ranges:
            full_range = value_range.get("range", "")
            tab_name = full_range.split("!")[0].strip("'")
            values = value_range.get("values", [])
            if not values:
                continue

            headers = [str(h).strip().upper() for h in values[0]]
            email_idx = headers.index("EMAIL") if "EMAIL" in headers else -1
            password_idx = headers.index("CLAVE") if "CLAVE" in headers else -1
            status_idx = headers.index("STATUS") if "STATUS" in headers else -1
            profile_idx = headers.index("PERFIL") if "PERFIL" in headers else -1

            if email_idx < 0 or password_idx < 0:
                self.summary["warnings"].append(f"Pestaña {tab_name} sin columnas EMAIL/CLAVE")
                continue

            rows_by_email: Dict[str, SheetRow] = {}
            rows_by_loose_email: Dict[str, List[SheetRow]] = {}
            for row in values[1:]:
                email = _normalize_text(row[email_idx] if email_idx < len(row) else "")
                if not email:
                    continue
                password = str(row[password_idx]).strip() if password_idx < len(row) else ""
                status = str(row[status_idx]).strip() if status_idx >= 0 and status_idx < len(row) else ""
                profile = _parse_profile(row[profile_idx]) if profile_idx >= 0 and profile_idx < len(row) else None
                row_data = SheetRow(email=email, password=password, status=status, profile=profile)
                rows_by_email[email] = row_data
                loose_email = email.replace(" ", "")
                rows_by_loose_email.setdefault(loose_email, []).append(row_data)

            tab_index[tab_name] = rows_by_email
            tab_loose_index[tab_name] = rows_by_loose_email

        return tab_index, tab_loose_index

    def _build_notification_message(self, account: Account, new_password: str, expiration_text: str) -> str:
        return (
            f"Hola {account.customer.username}, tu cuenta tuvo un cambio de contraseña.\n"
            f"Servicio: {account.account_name.description}\n"
            f"Email: {account.email}\n"
            f"Contraseña: {new_password}\n"
            f"Perfil: {account.profile}\n"
            f"Fecha de vencimiento: {expiration_text}\n"
            "Gracias por tu preferencia."
        )

    def _send_notifications(self, account: Account, new_password: str):
        if not account.customer:
            return

        last_sale = Sale.objects.filter(account=account, status=True).order_by("-expiration_date").first()
        expiration_text = last_sale.expiration_date.strftime("%d/%m/%Y") if last_sale and last_sale.expiration_date else "No definida"

        message = self._build_notification_message(account, new_password, expiration_text)

        # WhatsApp
        try:
            if hasattr(account.customer, "userdetail") and account.customer.userdetail.phone_number:
                enqueue_whatsapp(
                    message=message,
                    lada=str(account.customer.userdetail.lada),
                    phone_number=str(account.customer.userdetail.phone_number),
                )
                self.summary["notified_whatsapp"] += 1
            else:
                self.summary["warnings"].append(f"Cliente sin teléfono para WhatsApp: account_id={account.id}")
        except Exception as exc:
            self.summary["errors"].append(f"Error encolando WhatsApp account_id={account.id}: {exc}")

        # Email (solo customer.email, jamás account.email)
        customer_email = (account.customer.email or "").strip()
        if not customer_email:
            self.summary["warnings"].append(f"Cliente sin email para notificación: account_id={account.id}")
            return
        if _should_skip_email_notification(customer_email):
            self.summary["warnings"].append(
                f"Email omitido por dominio bloqueado (@example.com): account_id={account.id}"
            )
            return

        try:
            import resend

            resend.Emails.send(
                {
                    "from": "noreply@cuentasmexico.com",
                    "to": customer_email,
                    "subject": f"Cambio de contraseña - {account.account_name.description}",
                    "html": (
                        f"<p>Hola {account.customer.username}, tu cuenta tuvo un cambio de contraseña.</p>"
                        f"<ul>"
                        f"<li><b>Servicio:</b> {account.account_name.description}</li>"
                        f"<li><b>Email:</b> {account.email}</li>"
                        f"<li><b>Contraseña:</b> {new_password}</li>"
                        f"<li><b>Perfil:</b> {account.profile}</li>"
                        f"<li><b>Fecha de vencimiento:</b> {expiration_text}</li>"
                        f"</ul>"
                        f"<p>Gracias por tu preferencia.</p>"
                    ),
                }
            )
            self.summary["notified_email"] += 1
        except Exception as exc:
            self.summary["errors"].append(f"Error enviando email account_id={account.id}: {exc}")

    def _apply_sheet_row(self, account: Account, row: SheetRow):
        changes = []
        password_changed = False
        old_password = account.password

        normalized_status = _normalize_sheet_status_for_db(row.status)
        if normalized_status and account.external_status != normalized_status:
            account.external_status = normalized_status
            self.summary["updated_external_status"] += 1
            changes.append("external_status")

        if row.password and account.password != row.password:
            account.password = row.password
            self.summary["updated_password"] += 1
            password_changed = True
            changes.append("password")
            append_password_change_history(
                {
                    "source": "sync_pyc_full",
                    "task_id": self.task_id,
                    "account_id": account.id,
                    "service": account.account_name.description,
                    "email": account.email,
                    "old_password": old_password,
                    "new_password": row.password,
                }
            )

        if row.profile is not None and account.profile != row.profile:
            account.profile = row.profile
            self.summary["updated_profile"] += 1
            changes.append("profile")

        if not _needs_replacement_by_external_status(row.status) and not account.status:
            account.status = True
            self.summary["reactivated_accounts"] += 1
            changes.append("status")

        if changes:
            account.save(update_fields=changes)
            if password_changed:
                self._send_notifications(account, row.password)

    def _find_row_with_double_check(
        self,
        account: Account,
        tab_name: str,
        tab_index: Dict[str, Dict[str, SheetRow]],
        tab_loose_index: Dict[str, Dict[str, List[SheetRow]]],
    ) -> Tuple[Optional[SheetRow], str]:
        exact_email = _normalize_text(account.email)
        exact_row = tab_index.get(tab_name, {}).get(exact_email)
        if exact_row:
            return exact_row, "exact"

        loose_email = exact_email.replace(" ", "")
        loose_rows = tab_loose_index.get(tab_name, {}).get(loose_email, [])
        if len(loose_rows) == 1:
            return loose_rows[0], "loose_unique"
        if len(loose_rows) > 1:
            self.summary["warnings"].append(
                f"Ambigüedad por email flexible account_id={account.id} tab={tab_name} email={account.email}"
            )
            return None, "ambiguous"

        return None, "not_found"

    def run(self) -> Dict:
        token = _build_google_access_token()
        tab_index, tab_loose_index = self._build_tab_index(token)

        pyc_accounts = (
            Account.objects.select_related("account_name", "customer", "customer__userdetail")
            .filter(supplier__name__iexact="pyc")
            .order_by("id")
        )
        pyc_accounts_list = list(pyc_accounts)
        self._initial_customer_account_ids = {a.id for a in pyc_accounts_list if a.customer_id}
        self._total_accounts = len(pyc_accounts_list)
        self._progress(f"Iniciando sync PYC: 0/{self._total_accounts}")

        indexed_rows = sum(len(rows) for rows in tab_index.values())
        if indexed_rows < self._min_index_rows:
            reason = (
                f"Sync abortado por seguridad: filas indexadas en sheet muy bajas "
                f"({indexed_rows} < {self._min_index_rows})."
            )
            self.summary["aborted"] = True
            self.summary["abort_reason"] = reason
            self.summary["errors"].append(reason)
            self._progress(reason)
            return self.summary

        expected_accounts = 0
        missing_candidates = 0
        per_tab_expected: Dict[str, int] = {}
        per_tab_missing: Dict[str, int] = {}
        for account in pyc_accounts_list:
            tab_name = _tab_from_service(account.account_name.description)
            if not tab_name:
                continue
            expected_accounts += 1
            per_tab_expected[tab_name] = per_tab_expected.get(tab_name, 0) + 1
            row = tab_index.get(tab_name, {}).get(_normalize_text(account.email))
            if not row:
                missing_candidates += 1
                per_tab_missing[tab_name] = per_tab_missing.get(tab_name, 0) + 1

        missing_ratio = (missing_candidates / expected_accounts) if expected_accounts else 0
        if expected_accounts and missing_ratio > self._max_missing_ratio:
            self.summary["warnings"].append(
                f"Faltantes altos en sheet ({missing_candidates}/{expected_accounts}, ratio={missing_ratio:.2%}). "
                f"Auto-deleted por ausencia {'ACTIVO' if self._allow_missing_delete else 'DESACTIVADO'}."
            )

        for idx, account in enumerate(pyc_accounts_list, start=1):
            self.summary["processed"] += 1
            try:
                if _is_explicit_ignored_unmapped_service(account.account_name.description):
                    self.summary["ignored_explicit_unmapped"] += 1
                    continue

                tab_name = _tab_from_service(account.account_name.description)
                if not tab_name:
                    self.summary["ignored_unmapped"] += 1
                    continue

                row, match_type = self._find_row_with_double_check(
                    account=account,
                    tab_name=tab_name,
                    tab_index=tab_index,
                    tab_loose_index=tab_loose_index,
                )
                if not row:
                    if self._allow_missing_delete:
                        tab_expected = per_tab_expected.get(tab_name, 0)
                        tab_missing = per_tab_missing.get(tab_name, 0)
                        tab_missing_ratio = (tab_missing / tab_expected) if tab_expected else 1
                        can_delete_for_tab = (
                            tab_expected >= self._service_missing_min_expected
                            and tab_missing_ratio <= self._service_missing_ratio_guard
                        )
                        if match_type == "not_found" and can_delete_for_tab:
                            account.external_status = "deleted"
                            account.status = False
                            account.save(update_fields=["external_status", "status"])
                            self.summary["marked_deleted"] += 1
                            if account.id in self._initial_customer_account_ids:
                                self._replace_deleted_account_for_customer(account, trigger="missing_in_sheet")
                        elif match_type == "not_found":
                            self.summary["skipped_delete_by_service_guard"] += 1
                    continue

                self._apply_sheet_row(account, row)
                if _needs_replacement_by_external_status(account.external_status):
                    if account.id in self._initial_customer_account_ids:
                        self._replace_deleted_account_for_customer(account, trigger="status_from_sheet")
            except Exception as exc:
                self.summary["errors"].append(f"Error account_id={account.id}: {exc}")
                continue
            finally:
                self._progress(
                    f"Procesadas {idx}/{self._total_accounts} | "
                    f"claves cambiadas: {self.summary['updated_password']} | "
                    f"estados cambiados: {self.summary['updated_external_status']} | "
                    f"reactivadas: {self.summary['reactivated_accounts']} | "
                    f"reemplazos: {self.summary['replaced_deleted_accounts']}"
                )

        return self.summary


def sync_pyc_sheets(progress_callback=None, task_id: Optional[str] = None) -> Dict:
    service = PycSheetSyncService(progress_callback=progress_callback, task_id=task_id)
    summary = service.run()
    logger.info(
        "PYC sync complete processed=%s updated_password=%s updated_external_status=%s updated_profile=%s deleted=%s",
        summary["processed"],
        summary["updated_password"],
        summary["updated_external_status"],
        summary["updated_profile"],
        summary["marked_deleted"],
    )
    return summary


def sync_customer_active_passwords(customer_id: int) -> Dict:
    """
    Sincroniza SOLO contraseñas de cuentas activas (sales status=True)
    del cliente indicado.
    """
    token = _build_google_access_token()
    service = PycSheetSyncService()
    tab_index, tab_loose_index = service._build_tab_index(token)

    active_sales = (
        Sale.objects.select_related("account", "account__account_name", "customer")
        .filter(customer_id=customer_id, status=True)
        .order_by("id")
    )

    updates = []
    skipped = 0
    replaced_deleted_accounts = 0

    for sale in active_sales:
        try:
            account = sale.account
            tab_name = _tab_from_service(account.account_name.description)
            if not tab_name:
                skipped += 1
                continue

            row, match_type = service._find_row_with_double_check(
                account=account,
                tab_name=tab_name,
                tab_index=tab_index,
                tab_loose_index=tab_loose_index,
            )
            if row and _needs_replacement_by_external_status(row.status):
                before = service.summary["replaced_deleted_accounts"]
                service._replace_deleted_account_for_customer(account, trigger="customer_sync_status_from_sheet")
                replaced_deleted_accounts += service.summary["replaced_deleted_accounts"] - before
                skipped += 1
                continue

            if _needs_replacement_by_external_status(account.external_status):
                before = service.summary["replaced_deleted_accounts"]
                service._replace_deleted_account_for_customer(account, trigger="customer_sync_account_deleted")
                replaced_deleted_accounts += service.summary["replaced_deleted_accounts"] - before
                skipped += 1
                continue

            if not row or not row.password:
                skipped += 1
                continue

            if account.password != row.password:
                old_password = account.password
                account.password = row.password
                account.save(update_fields=["password"])
                append_password_change_history(
                    {
                        "source": "sync_pyc_customer",
                        "customer_id": customer_id,
                        "sale_id": sale.id,
                        "account_id": account.id,
                        "service": account.account_name.description,
                        "email": account.email,
                        "old_password": old_password,
                        "new_password": row.password,
                    }
                )
                updates.append(
                    {
                        "sale_id": sale.id,
                        "account_id": account.id,
                        "service": account.account_name.description,
                        "email": account.email,
                        "old_password": old_password,
                        "new_password": row.password,
                    }
                )
        except Exception as exc:
            skipped += 1
            service.summary["errors"].append(f"Error sale_id={sale.id}: {exc}")
            continue

    return {
        "customer_id": customer_id,
        "active_sales": active_sales.count(),
        "updated_count": len(updates),
        "skipped_count": skipped,
        "replaced_deleted_accounts": replaced_deleted_accounts,
        "updates": updates,
    }
