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
    JOB_DUE_TODAY,
    finish_job,
    get_control,
    init_job,
    set_job_message,
    stop_job,
    update_recipient,
)
from adm.models import Sale


SPANISH_WEEKDAYS = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo']
SPANISH_MONTHS = [None, 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']


class Command(BaseCommand):
    help = 'Envia WhatsApp a clientes con cuentas vencidas hoy durante horario laboral.'

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
        today = now.date() if target_date is None else datetime.strptime(target_date, '%Y-%m-%d').date()
        work_start = timezone.make_aware(datetime.combine(today, time(start_hour, start_minute)))
        work_end = timezone.make_aware(datetime.combine(today, time(end_hour, end_minute)))

        if now < work_start:
            time_module.sleep(int((work_start - now).total_seconds()))
        if timezone.localtime() > work_end:
            return

        sent_registry = self._load_sent_registry()
        day_key = today.isoformat()
        sent_today = set(sent_registry.get(day_key, []))
        notification_history = self._load_notification_history()

        day_start = timezone.make_aware(datetime.combine(today, time.min))
        day_end = timezone.make_aware(datetime.combine(today, time.max))

        sales = list(
            Sale.objects.select_related('customer__userdetail', 'account__account_name')
            .filter(expiration_date__gte=day_start, expiration_date__lte=day_end, status=True)
            .order_by('expiration_date', 'customer__userdetail__lada', 'customer__userdetail__phone_number')
        )

        recipients = []
        for sale in sales:
            ud = getattr(sale.customer, 'userdetail', None)
            recipients.append({
                'sale_id': sale.id,
                'customer': sale.customer.username,
                'phone': f"+{getattr(ud, 'lada', '')}{getattr(ud, 'phone_number', '')}",
                'status': 'pending',
                'note': '',
            })
        init_job(JOB_DUE_TODAY, recipients)

        if not sales:
            finish_job(JOB_DUE_TODAY, 'Sin cuentas vencidas hoy')
            return

        for idx, sale in enumerate(sales):
            if self._should_stop(JOB_DUE_TODAY):
                stop_job(JOB_DUE_TODAY, 'Detenido por operador')
                return

            now = timezone.localtime()
            if now > work_end:
                finish_job(JOB_DUE_TODAY, 'Finalizado por fin de horario')
                return

            if sale.id in sent_today and not dry_run:
                update_recipient(JOB_DUE_TODAY, sale.id, 'skipped', 'Ya notificado hoy')
                continue

            userdetail = getattr(sale.customer, 'userdetail', None)
            if not userdetail or not userdetail.phone_number or not userdetail.lada:
                update_recipient(JOB_DUE_TODAY, sale.id, 'skipped', 'Sin telefono/lada')
                continue

            service = sale.account.account_name
            service_name = service.description if service else 'Servicio'
            account_email = sale.account.email or 'sin-email'
            account_profile = sale.account.profile or 1
            service_price = int(service.price or 0)
            discounted_price = int(round(service_price * 0.8))
            discounted_total_3m = discounted_price * 3
            today_str = self._format_spanish_date(today)

            message = (
                f'Hola. Tu cuenta {service_name} ({account_email}, perfil {account_profile}) vence hoy, {today_str}.\n\n'
                f'Si renuevas hoy por 3 meses o mas, tienes 20 por ciento de descuento: '
                f'${discounted_price} por mes (precio normal ${service_price} por mes). '
                f'Total por 3 meses: ${discounted_total_3m}.\n'
                f'Tambien puedes renovar 1 mes por ${service_price}.\n\n'
                f'Responde este mensaje para renovarte hoy: https://wa.me/5218335355863'
            )

            set_job_message(JOB_DUE_TODAY, f'Enviando a venta {sale.id}')
            if dry_run:
                update_recipient(JOB_DUE_TODAY, sale.id, 'sent', 'Dry run')
            else:
                status_code = Notification.send_whatsapp_notification(message, userdetail.lada, userdetail.phone_number)
                if status_code in (200, 201):
                    update_recipient(JOB_DUE_TODAY, sale.id, 'sent', f'Enviado ({status_code})')
                    sent_today.add(sale.id)
                    sent_registry[day_key] = sorted(sent_today)
                    self._save_sent_registry(sent_registry)
                    row = notification_history.get(str(sale.id), {})
                    row['last_due_today_notified_at'] = timezone.now().isoformat()
                    notification_history[str(sale.id)] = row
                    self._save_notification_history(notification_history)
                else:
                    update_recipient(JOB_DUE_TODAY, sale.id, 'failed', f'Error ({status_code})')

            if idx < len(sales) - 1:
                if self._sleep_with_control(random.randint(180, 300), JOB_DUE_TODAY, work_end):
                    stop_job(JOB_DUE_TODAY, 'Detenido por operador')
                    return

        finish_job(JOB_DUE_TODAY, 'Proceso finalizado')

    def _format_spanish_date(self, date_value):
        return f"{SPANISH_WEEKDAYS[date_value.weekday()]} {date_value.day} de {SPANISH_MONTHS[date_value.month]} del {date_value.year}"

    def _sent_registry_path(self):
        logs_dir = os.path.join(settings.BASE_DIR, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        return os.path.join(logs_dir, 'send_due_today_registry.json')

    def _load_sent_registry(self):
        path = self._sent_registry_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_sent_registry(self, registry):
        with open(self._sent_registry_path(), 'w', encoding='utf-8') as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)

    def _notification_history_path(self):
        logs_dir = os.path.join(settings.BASE_DIR, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        return os.path.join(logs_dir, 'receivable_notifications_history.json')

    def _load_notification_history(self):
        path = self._notification_history_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_notification_history(self, history):
        with open(self._notification_history_path(), 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

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
