import os
import json
import random
import time as time_module
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from adm.functions.send_whatsapp_notification import Notification
from adm.functions.receivable_bulk_jobs import (
    JOB_OVERDUE_PENDING,
    finish_job,
    get_control,
    init_job,
    set_job_message,
    stop_job,
    update_recipient,
)
from adm.models import Sale


class Command(BaseCommand):
    help = 'Envia WhatsApp a cuentas vencidas y no renovadas.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--date', type=str)

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        target_date = options.get('date')

        working_start = os.getenv('WORKING_HOURS_START', '09:00')
        working_end = os.getenv('WORKING_HOURS_END', '21:00')
        start_hour, start_minute = [int(v) for v in working_start.split(':')]
        end_hour, end_minute = [int(v) for v in working_end.split(':')]

        now = timezone.localtime()
        base_day = now.date() if target_date is None else datetime.strptime(target_date, '%Y-%m-%d').date()
        work_start = timezone.make_aware(datetime.combine(base_day, time(start_hour, start_minute)))
        work_end = timezone.make_aware(datetime.combine(base_day, time(end_hour, end_minute)))
        self.stdout.write(f'[overdue_pending] now={timezone.localtime()} start={work_start} end={work_end} dry_run={dry_run}')

        if now < work_start:
            self.stdout.write(f'[overdue_pending] Esperando inicio de horario ({work_start})')
            time_module.sleep(int((work_start - now).total_seconds()))
        if timezone.localtime() > work_end:
            self.stdout.write('[overdue_pending] Fuera de horario, sin ejecucion')
            return

        sent_registry = self._load_registry()
        day_key = base_day.isoformat()
        sent_today = set(sent_registry.get(day_key, []))

        history = self._load_notification_history()
        yesterday_end = timezone.make_aware(datetime.combine(base_day - timedelta(days=1), time.max))
        expired_end = timezone.make_aware(datetime.combine(base_day - timedelta(days=1), time.max))

        candidates = list(
            Sale.objects.select_related('customer__userdetail', 'account__account_name')
            .filter(expiration_date__lte=expired_end, status=True)
            .order_by('expiration_date', 'customer__userdetail__lada', 'customer__userdetail__phone_number')
        )

        sales = []
        for sale in candidates:
            last_due_raw = (history.get(str(sale.id)) or {}).get('last_due_today_notified_at')
            if not last_due_raw:
                sales.append(sale)
                continue
            try:
                last_due_dt = datetime.fromisoformat(str(last_due_raw).replace('Z', '+00:00'))
                if timezone.is_naive(last_due_dt):
                    last_due_dt = timezone.make_aware(last_due_dt)
                if last_due_dt <= yesterday_end:
                    sales.append(sale)
            except Exception:
                sales.append(sale)

        recipients = []
        for sale in sales:
            ud = getattr(sale.customer, 'userdetail', None)
            recipients.append({'sale_id': sale.id, 'customer': sale.customer.username, 'phone': f"+{getattr(ud, 'lada', '')}{getattr(ud, 'phone_number', '')}", 'status': 'pending', 'note': ''})
        init_job(JOB_OVERDUE_PENDING, recipients)
        self.stdout.write(f'[overdue_pending] Candidatos: {len(sales)}')

        if not sales:
            finish_job(JOB_OVERDUE_PENDING, 'Sin cuentas vencidas pendientes')
            self.stdout.write('[overdue_pending] Sin cuentas vencidas pendientes')
            return

        for idx, sale in enumerate(sales):
            if self._should_stop(JOB_OVERDUE_PENDING):
                stop_job(JOB_OVERDUE_PENDING, 'Detenido por operador')
                return

            if timezone.localtime() > work_end:
                finish_job(JOB_OVERDUE_PENDING, 'Finalizado por fin de horario')
                return

            if sale.id in sent_today and not dry_run:
                update_recipient(JOB_OVERDUE_PENDING, sale.id, 'skipped', 'Ya notificado hoy')
                continue

            userdetail = getattr(sale.customer, 'userdetail', None)
            if not userdetail or not userdetail.phone_number or not userdetail.lada:
                update_recipient(JOB_OVERDUE_PENDING, sale.id, 'skipped', 'Sin telefono/lada')
                continue

            service = sale.account.account_name
            service_name = service.description if service else 'Servicio'
            account_email = sale.account.email or 'sin-email'
            account_profile = sale.account.profile or 1
            service_price = int(service.price or 0) if service else 0
            discounted_price = int(round(service_price * 0.8))
            discounted_total_3m = discounted_price * 3
            expired_on = timezone.localtime(sale.expiration_date).date()
            grace_days = max(0, (base_day - expired_on).days)

            message = (
                f'Hola. Te compartimos un recordatorio de tu cuenta {service_name} ({account_email}, perfil {account_profile}).\n\n'
                f'Vencio el {expired_on.strftime("%d-%m-%Y")} y te hemos mantenido el servicio activo por {grace_days} dia(s) para evitarte interrupciones.\n\n'
                f'Si renuevas hoy, tienes 20 por ciento de descuento: ${discounted_price} por mes '
                f'(precio normal ${service_price} por mes). Total por 3 meses: ${discounted_total_3m}.\n\n'
                f'Cuando gustes te ayudamos a renovarla. Responde aqui: https://wa.me/5218335355863'
            )

            set_job_message(JOB_OVERDUE_PENDING, f'Enviando a venta {sale.id}')
            self.stdout.write(f'[overdue_pending] Procesando sale_id={sale.id}')
            if dry_run:
                update_recipient(JOB_OVERDUE_PENDING, sale.id, 'sent', 'Dry run')
                self.stdout.write(f'[overdue_pending] DRY-RUN enviado sale_id={sale.id}')
            else:
                status_code = Notification.send_whatsapp_notification(message, userdetail.lada, userdetail.phone_number)
                if status_code in (200, 201):
                    update_recipient(JOB_OVERDUE_PENDING, sale.id, 'sent', f'Enviado ({status_code})')
                    self.stdout.write(f'[overdue_pending] OK sale_id={sale.id} status={status_code}')
                    sent_today.add(sale.id)
                    sent_registry[day_key] = sorted(sent_today)
                    self._save_registry(sent_registry)
                else:
                    update_recipient(JOB_OVERDUE_PENDING, sale.id, 'failed', f'Error ({status_code})')
                    self.stdout.write(f'[overdue_pending] FAIL sale_id={sale.id} status={status_code}')

            if idx < len(sales) - 1:
                if dry_run:
                    continue
                if self._sleep_with_control(random.randint(180, 300), JOB_OVERDUE_PENDING, work_end):
                    stop_job(JOB_OVERDUE_PENDING, 'Detenido por operador')
                    self.stdout.write('[overdue_pending] Detenido durante espera')
                    return

        finish_job(JOB_OVERDUE_PENDING, 'Proceso finalizado')
        self.stdout.write('[overdue_pending] Proceso finalizado')

    def _registry_path(self):
        logs_dir = os.path.join(settings.BASE_DIR, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        return os.path.join(logs_dir, 'send_overdue_pending_registry.json')

    def _history_path(self):
        logs_dir = os.path.join(settings.BASE_DIR, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        return os.path.join(logs_dir, 'receivable_notifications_history.json')

    def _load_registry(self):
        path = self._registry_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_registry(self, registry):
        with open(self._registry_path(), 'w', encoding='utf-8') as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)

    def _load_notification_history(self):
        path = self._history_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _should_stop(self, job_key):
        while True:
            control = get_control(job_key)
            if control.get('stop_requested'):
                return True
            if not control.get('paused'):
                return False
            time_module.sleep(2)

    def _sleep_with_control(self, seconds, job_key, work_end):
        remaining = int(seconds)
        while remaining > 0:
            if self._should_stop(job_key):
                return True
            if timezone.localtime() > work_end:
                return True
            chunk = 2 if remaining >= 2 else 1
            time_module.sleep(chunk)
            remaining -= chunk
        return False

