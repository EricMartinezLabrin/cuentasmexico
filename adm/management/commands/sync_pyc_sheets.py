from django.core.management.base import BaseCommand

from adm.functions.sync_pyc_sheets import sync_pyc_sheets


class Command(BaseCommand):
    help = "Sincroniza cuentas PYC desde Google Sheets hacia base de datos"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Iniciando sync PYC desde Google Sheets..."))
        summary = sync_pyc_sheets()
        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Sync PYC completado\n"
                    f"- processed: {summary['processed']}\n"
                    f"- updated_password: {summary['updated_password']}\n"
                    f"- updated_external_status: {summary['updated_external_status']}\n"
                    f"- updated_profile: {summary['updated_profile']}\n"
                    f"- marked_deleted: {summary['marked_deleted']}\n"
                    f"- notified_whatsapp: {summary['notified_whatsapp']}\n"
                    f"- notified_email: {summary['notified_email']}\n"
                    f"- warnings: {len(summary['warnings'])}\n"
                    f"- errors: {len(summary['errors'])}"
                )
            )
        )

