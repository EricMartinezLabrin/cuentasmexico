import time

from django.core.management.base import BaseCommand

from adm.functions.marketing_bulk import claim_next_job, process_bulk_job


class Command(BaseCommand):
    help = 'Procesa envíos masivos persistentes de WhatsApp de Marketing IA.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Procesa un trabajo disponible y termina.')
        parser.add_argument('--poll-seconds', type=int, default=5)

    def handle(self, *args, **options):
        poll_seconds = max(1, options['poll_seconds'])
        while True:
            job_id = claim_next_job()
            if job_id:
                try:
                    process_bulk_job(job_id)
                except Exception:
                    self.stderr.write(f'Error procesando el trabajo masivo #{job_id}.')
                if options['once']:
                    return
                continue
            if options['once']:
                return
            time.sleep(poll_seconds)
