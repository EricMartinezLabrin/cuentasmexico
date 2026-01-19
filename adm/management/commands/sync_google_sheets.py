"""
Comando Django para sincronizar Google Sheets.

Uso:
    python manage.py sync_google_sheets
    python manage.py sync_google_sheets --verbose
"""

from django.core.management.base import BaseCommand
from adm.functions.sync_google_sheets import sync_google_sheets


class Command(BaseCommand):
    help = "Sincroniza datos de Google Sheets con la base de datos"

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Muestra información detallada',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔄 Iniciando sincronización de Google Sheets...')
        )
        
        try:
            summary = sync_google_sheets()
            
            # Mostrar resumen
            self.stdout.write(
                self.style.SUCCESS(f"""
✅ SINCRONIZACIÓN COMPLETADA

📊 Estadísticas:
  ✏️  Actualizadas: {summary['total_updated']}
  ✨ Creadas: {summary['total_created']}
  ⏸️  Suspendidas: {summary['total_suspended']}
  🔐 Cambios de contraseña: {summary['password_changes']}
  📊 Cambios de estado: {summary['status_changes']}
  ❌ Errores: {summary['total_errors']}
  ⏰ Timestamp: {summary['timestamp']}
            """)
            )
            
            # Mostrar detalles si se pide
            if options['verbose']:
                self.stdout.write(
                    self.style.WARNING('\n📋 DETALLES:\n')
                )
                
                if summary['details']['password_changes']:
                    self.stdout.write(self.style.WARNING('🔐 Cambios de contraseña:'))
                    for change in summary['details']['password_changes']:
                        self.stdout.write(
                            f"   - {change['email']} ({change['servicio']}): {change['old_password']} → {change['new_password']}"
                        )
                
                if summary['details']['status_changes']:
                    self.stdout.write(self.style.WARNING('\n📊 Cambios de estado:'))
                    for change in summary['details']['status_changes']:
                        old = "Activa" if change['old_status'] else "Inactiva"
                        new = "Activa" if change['new_status'] else "Inactiva"
                        self.stdout.write(
                            f"   - {change['email']} ({change['servicio']}): {old} → {new}"
                        )
                
                if summary['details']['errors']:
                    self.stdout.write(self.style.ERROR('\n❌ Errores encontrados:'))
                    for error in summary['details']['errors']:
                        self.stdout.write(f"   - {error}")
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error: {str(e)}')
            )
