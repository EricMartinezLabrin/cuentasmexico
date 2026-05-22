"""
Sincronización PYC basada en Google Sheets como source of truth.
"""

import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.db import transaction

from adm.functions.whatsapp_queue import enqueue_whatsapp
from adm.models import Account, Sale, AccountChangeHistory, PaymentMethod, UserDetail


logger = logging.getLogger(__name__)

DEFAULT_SHEET_ID = "1eY2EWKjarh1a909CLSrL22lP5HVUF5CZzdM9SDHBT3M"

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


def _b64url_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("utf-8")


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


class PycSheetSyncService:
    def __init__(self, sheet_id: Optional[str] = None):
        self.sheet_id = sheet_id or os.getenv("SHEETS_PYC_ID") or DEFAULT_SHEET_ID
        self.summary = {
            "processed": 0,
            "updated_password": 0,
            "updated_external_status": 0,
            "updated_profile": 0,
            "marked_deleted": 0,
            "notified_whatsapp": 0,
            "notified_email": 0,
            "replaced_deleted_accounts": 0,
            "warnings": [],
            "errors": [],
        }

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
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={"fields": "sheets(properties(title))"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        return [
            sheet.get("properties", {}).get("title")
            for sheet in payload.get("sheets", [])
            if sheet.get("properties", {}).get("title")
        ]

    def _build_tab_index(self, token: str) -> Dict[str, Dict[str, SheetRow]]:
        tab_index: Dict[str, Dict[str, SheetRow]] = {}
        tab_names = set(self._fetch_sheet_names(token))
        target_tabs = sorted(set(SERVICE_TAB_MAPPING.values()))
        existing_tabs = [tab_name for tab_name in target_tabs if tab_name in tab_names]
        missing_tabs = [tab_name for tab_name in target_tabs if tab_name not in tab_names]
        for tab_name in missing_tabs:
            self.summary["warnings"].append(f"Pestaña no encontrada en sheet: {tab_name}")

        if not existing_tabs:
            return tab_index

        response = requests.get(
            f"https://sheets.googleapis.com/v4/spreadsheets/{self.sheet_id}/values:batchGet",
            headers={"Authorization": f"Bearer {token}"},
            params=[("ranges", f"'{tab_name}'!A1:ZZ1000") for tab_name in existing_tabs],
            timeout=60,
        )
        response.raise_for_status()

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
            for row in values[1:]:
                email = _normalize_text(row[email_idx] if email_idx < len(row) else "")
                if not email:
                    continue
                password = str(row[password_idx]).strip() if password_idx < len(row) else ""
                status = str(row[status_idx]).strip() if status_idx >= 0 and status_idx < len(row) else ""
                profile = _parse_profile(row[profile_idx]) if profile_idx >= 0 and profile_idx < len(row) else None
                rows_by_email[email] = SheetRow(email=email, password=password, status=status, profile=profile)

            tab_index[tab_name] = rows_by_email

        return tab_index

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

        if row.status and account.external_status != row.status:
            account.external_status = row.status
            self.summary["updated_external_status"] += 1
            changes.append("external_status")

        if row.password and account.password != row.password:
            account.password = row.password
            self.summary["updated_password"] += 1
            password_changed = True
            changes.append("password")

        if row.profile is not None and account.profile != row.profile:
            account.profile = row.profile
            self.summary["updated_profile"] += 1
            changes.append("profile")

        if changes:
            account.save(update_fields=changes)
            if password_changed:
                self._send_notifications(account, row.password)

    @transaction.atomic
    def run(self) -> Dict:
        token = _build_google_access_token()
        tab_index = self._build_tab_index(token)

        pyc_accounts = (
            Account.objects.select_related("account_name", "customer", "customer__userdetail")
            .filter(supplier__name__iexact="pyc")
            .order_by("id")
        )

        for account in pyc_accounts:
            self.summary["processed"] += 1

            tab_name = _tab_from_service(account.account_name.description)
            if not tab_name:
                self.summary["warnings"].append(
                    f"Servicio sin mapeo a pestaña: account_id={account.id} service={account.account_name.description}"
                )
                continue

            row = tab_index.get(tab_name, {}).get(_normalize_text(account.email))
            if not row:
                account.external_status = "deleted"
                account.status = False
                account.save(update_fields=["external_status", "status"])
                self.summary["marked_deleted"] += 1
                self._replace_deleted_account_for_customer(account, trigger="missing_in_sheet")
                continue

            self._apply_sheet_row(account, row)
            if _needs_replacement_by_external_status(account.external_status):
                self._replace_deleted_account_for_customer(account, trigger="status_from_sheet")

        return self.summary


def sync_pyc_sheets() -> Dict:
    service = PycSheetSyncService()
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
    tab_index = service._build_tab_index(token)

    active_sales = (
        Sale.objects.select_related("account", "account__account_name", "customer")
        .filter(customer_id=customer_id, status=True)
        .order_by("id")
    )

    updates = []
    skipped = 0
    replaced_deleted_accounts = 0

    for sale in active_sales:
        account = sale.account
        tab_name = _tab_from_service(account.account_name.description)
        if not tab_name:
            skipped += 1
            continue

        row = tab_index.get(tab_name, {}).get(_normalize_text(account.email))
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

    return {
        "customer_id": customer_id,
        "active_sales": active_sales.count(),
        "updated_count": len(updates),
        "skipped_count": skipped,
        "replaced_deleted_accounts": replaced_deleted_accounts,
        "updates": updates,
    }
