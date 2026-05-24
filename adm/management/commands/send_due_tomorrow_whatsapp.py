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
    JOB_DUE_TOMORROW,
    finish_job,
    get_control,
    init_job,
    rollover_cleanup_if_stale,
    set_job_message,
    stop_job,
    update_recipient,
)
from adm.models import Sale


class Command(BaseCommand):
    help = 'Envia WhatsApp a clientes cuyas cuentas vencen mañana.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--date', type=str)
        parser.add_argument('--ignore-schedule', action='store_true')

    def handle(self, *args, **options):
        rollover_cleanup_if_stale(JOB_DUE_TOMORROW)
        dry_run = options['dry_run']
        target_date = options.get('date')
        ignore_schedule = options.get('ignore_schedule', False)
        working_start = os.getenv('WORKING_HOURS_START', '09:00')
        working_end = os.getenv('WORKING_HOURS_END', '21:00')
        start_hour, start_minute = [int(v) for v in working_start.split(':')]
        end_hour, end_minute = [int(v) for v in working_end.split(':')]

        now = timezone.localtime()
        base_day = now.date() if target_date is None else datetime.strptime(target_date, '%Y-%m-%d').date()
        target_day = base_day + timedelta(days=1)
        work_start = timezone.make_aware(datetime.combine(base_day, time(start_hour, start_minute)))
        work_end = timezone.make_aware(datetime.combine(base_day, time(end_hour, end_minute)))
        self.stdout.write(f'[due_tomorrow] now={timezone.localtime()} start={work_start} end={work_end} dry_run={dry_run}')

        if (not ignore_schedule) and now < work_start:
            self.stdout.write(f'[due_tomorrow] Esperando inicio de horario ({work_start})')
            time_module.sleep(int((work_start - now).total_seconds()))
        if (not ignore_schedule) and timezone.localtime() > work_end:
            self.stdout.write('[due_tomorrow] Fuera de horario, sin ejecucion')
            return

        sent_registry = self._load_registry()
        day_key = base_day.isoformat()
        sent_today = set(sent_registry.get(day_key, []))

        day_start = timezone.make_aware(datetime.combine(target_day, time.min))
        day_end = timezone.make_aware(datetime.combine(target_day, time.max))

        sales = list(
            Sale.objects.select_related('customer__userdetail', 'account__account_name')
            .filter(expiration_date__gte=day_start, expiration_date__lte=day_end, status=True)
            .order_by('expiration_date', 'customer__userdetail__lada', 'customer__userdetail__phone_number')
        )

        recipients = []
        for sale in sales:
            ud = getattr(sale.customer, 'userdetail', None)
            recipients.append({'sale_id': sale.id, 'customer': sale.customer.username, 'phone': f"+{getattr(ud, 'lada', '')}{getattr(ud, 'phone_number', '')}", 'status': 'pending', 'note': ''})
        init_job(JOB_DUE_TOMORROW, recipients)
        self.stdout.write(f'[due_tomorrow] Candidatos: {len(sales)}')

        if not sales:
            finish_job(JOB_DUE_TOMORROW, 'Sin cuentas por vencer mañana')
            self.stdout.write('[due_tomorrow] Sin cuentas por vencer mañana')
            return

        for idx, sale in enumerate(sales):
            if self._should_stop(JOB_DUE_TOMORROW):
                stop_job(JOB_DUE_TOMORROW, 'Detenido por operador')
                return

            if timezone.localtime() > work_end:
                finish_job(JOB_DUE_TOMORROW, 'Finalizado por fin de horario')
                return

            if sale.id in sent_today and not dry_run:
                update_recipient(JOB_DUE_TOMORROW, sale.id, 'skipped', 'Ya notificado hoy')
                continue

            userdetail = getattr(sale.customer, 'userdetail', None)
            if not userdetail or not userdetail.phone_number or not userdetail.lada:
                update_recipient(JOB_DUE_TOMORROW, sale.id, 'skipped', 'Sin telefono/lada')
                continue

            service = sale.account.account_name
            service_name = service.description if service else 'Servicio'
            account_email = sale.account.email or 'sin-email'
            account_profile = sale.account.profile or 1
            service_price = int(service.price or 0)
            discounted_price = int(round(service_price * 0.75))
            discounted_total_3m = discounted_price * 3

            message = (
                f'Hola. Tu cuenta {service_name} ({account_email}, perfil {account_profile}) vence mañana '
                f'({target_day.strftime("%Y-%m-%d")}).\n\n'
                f'Este descuento aplica solo hoy ({base_day.strftime("%d-%m-%Y")}).\n\n'
                f'Hoy tienes 2 opciones de renovacion:\n'
                f'1. Renovar 3 meses con 25 por ciento de descuento:\n'
                f'- Precio normal: ${service_price} por mes\n'
                f'- Precio con descuento: ${discounted_price} por mes\n'
                f'- Total final por 3 meses: ${discounted_total_3m}\n'
                f'2. Renovar 1 mes a precio normal: ${service_price}\n\n'
                f'Cuando gustes te ayudamos a renovarla: https://wa.me/5218335355863'
            )

            set_job_message(JOB_DUE_TOMORROW, f'Enviando a venta {sale.id}')
            self.stdout.write(f'[due_tomorrow] Procesando sale_id={sale.id}')
            if dry_run:
                update_recipient(JOB_DUE_TOMORROW, sale.id, 'sent', 'Dry run')
                self.stdout.write(f'[due_tomorrow] DRY-RUN enviado sale_id={sale.id}')
            else:
                status_code = Notification.send_whatsapp_notification(message, userdetail.lada, userdetail.phone_number)
                if status_code in (200, 201):
                    update_recipient(JOB_DUE_TOMORROW, sale.id, 'sent', f'Enviado ({status_code})')
                    self.stdout.write(f'[due_tomorrow] OK sale_id={sale.id} status={status_code}')
                    sent_today.add(sale.id)
                    sent_registry[day_key] = sorted(sent_today)
                    self._save_registry(sent_registry)
                else:
                    update_recipient(JOB_DUE_TOMORROW, sale.id, 'failed', f'Error ({status_code})')
                    self.stdout.write(f'[due_tomorrow] FAIL sale_id={sale.id} status={status_code}')

            if idx < len(sales) - 1:
                if dry_run:
                    continue
                if self._sleep_with_control(random.randint(180, 300), JOB_DUE_TOMORROW, work_end):
                    stop_job(JOB_DUE_TOMORROW, 'Detenido por operador')
                    self.stdout.write('[due_tomorrow] Detenido durante espera')
                    return

        finish_job(JOB_DUE_TOMORROW, 'Proceso finalizado')
        self.stdout.write('[due_tomorrow] Proceso finalizado')

    def _registry_path(self):
        logs_dir = os.path.join(settings.BASE_DIR, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        return os.path.join(logs_dir, 'send_due_tomorrow_registry.json')

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
