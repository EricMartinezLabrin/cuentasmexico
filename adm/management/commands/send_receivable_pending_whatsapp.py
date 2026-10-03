from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from adm.functions.send_whatsapp_notification import Notification
from adm.models import Business, Sale


TARGET_LADA = '52'
TARGET_PHONE = '8334482256'
START_TIME = time(12, 0)
END_TIME = time(21, 0)
INTERVAL = timedelta(hours=3)


class Command(BaseCommand):
    help = 'Envia recordatorio de cuentas pendientes de liberar a administracion.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Ignora ventana horaria e intervalo; respeta toggle.')

    def handle(self, *args, **options):
        business = Business.objects.filter(pk=1).first()
        if not business:
            self.stdout.write('Sin negocio configurado.')
            return
        if not business.receivable_pending_whatsapp_enabled:
            self.stdout.write('Avisos desactivados desde Configuracion.')
            return

        now = timezone.localtime()
        force = options.get('force', False)
        if not force and not (START_TIME <= now.time() <= END_TIME):
            self.stdout.write('Fuera de horario CDMX.')
            return
        if not force and business.receivable_pending_whatsapp_last_sent_at:
            last_sent = timezone.localtime(business.receivable_pending_whatsapp_last_sent_at)
            if now - last_sent < INTERVAL:
                self.stdout.write('Intervalo de 3 horas aun no cumplido.')
                return

        end_of_day = timezone.make_aware(datetime.combine(now.date(), time.max))
        pending_count = Sale.objects.filter(
            status=True,
            expiration_date__lte=end_of_day,
        ).count()
        if not pending_count:
            self.stdout.write('Sin cuentas pendientes de liberar.')
            return

        message = (
            f'Hay {pending_count} cuenta(s) pendientes de liberar en /adm/receivable/. '
            'Debe cortar las cuentas pendientes.'
        )
        status_code = Notification.send_whatsapp_notification(message, TARGET_LADA, TARGET_PHONE)
        if status_code not in (200, 201):
            self.stderr.write(f'WhatsApp no acepto mensaje. status={status_code}')
            return

        business.receivable_pending_whatsapp_last_sent_at = timezone.now()
        business.save(update_fields=['receivable_pending_whatsapp_last_sent_at'])
        self.stdout.write(f'Recordatorio enviado. pendientes={pending_count} status={status_code}')
