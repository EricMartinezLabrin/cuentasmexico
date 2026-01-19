#!/usr/bin/env python
"""
Script helper para operaciones de sincronización de Google Sheets.

Uso:
    python scripts/sync_helper.py --status          # Ver estado
    python scripts/sync_helper.py --sync            # Ejecutar sincronización
    python scripts/sync_helper.py --test            # Ejecutar tests
    python scripts/sync_helper.py --logs            # Ver logs
    python scripts/sync_helper.py --setup-cron      # Configurar cron
"""

import os
import sys
import argparse
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Añadir el directorio del proyecto al path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CuentasMexico.settings')
import django
django.setup()

from django.core.management import call_command
from adm.functions.sync_google_sheets import sync_google_sheets
from django.core.cache import cache
from django.utils import timezone


class SyncHelper:
    """Helper para operaciones de sincronización"""
    
    def __init__(self):
        self.log_file = project_root / "logs" / "sync_sheets.log"
    
    def status(self):
        """Mostrar estado actual"""
        print("\n📊 ESTADO DE SINCRONIZACIÓN\n")
        
        # Obtener última sincronización del cache
        last_sync = cache.get('last_google_sheets_sync', None)
        
        if last_sync:
            timestamp = last_sync.get('timestamp')
            print(f"✅ Última sincronización: {timestamp}")
            print(f"   Actualizadas: {last_sync.get('total_updated', 0)}")
            print(f"   Creadas: {last_sync.get('total_created', 0)}")
            print(f"   Suspendidas: {last_sync.get('total_suspended', 0)}")
        else:
            print("❌ No hay registro de sincronización anterior")
        
        # Ver logs más recientes
        if self.log_file.exists():
            print("\n📋 Últimas 5 líneas de logs:")
            with open(self.log_file, 'r') as f:
                lines = f.readlines()[-5:]
                for line in lines:
                    print(f"   {line.rstrip()}")
        
        print()
    
    def sync(self, verbose=False):
        """Ejecutar sincronización"""
        print("\n🔄 INICIANDO SINCRONIZACIÓN\n")
        
        try:
            if verbose:
                # Ejecutar con verbose
                call_command('sync_google_sheets', '--verbose')
            else:
                # Ejecutar sin verbose
                summary = sync_google_sheets()
                print(f"✅ Sincronización completada!")
                print(f"   ✏️ Actualizadas: {summary['total_updated']}")
                print(f"   ✨ Creadas: {summary['total_created']}")
                print(f"   ⏸️ Suspendidas: {summary['total_suspended']}")
                print(f"   🔐 Cambios de contraseña: {summary['password_changes']}")
                print(f"   ❌ Errores: {summary['total_errors']}")
        
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        
        print()
    
    def test(self):
        """Ejecutar tests"""
        print("\n🧪 EJECUTANDO TESTS\n")
        
        try:
            call_command('test', 'adm.tests_sync', '-v', '2')
        except Exception as e:
            print(f"❌ Error ejecutando tests: {str(e)}")
        
        print()
    
    def logs(self, lines=20):
        """Mostrar logs"""
        print(f"\n📝 ÚLTIMAS {lines} LÍNEAS DE LOGS\n")
        
        if self.log_file.exists():
            with open(self.log_file, 'r') as f:
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:]
                for line in recent_lines:
                    print(line.rstrip())
        else:
            print("❌ No hay logs todavía")
        
        print()
    
    def setup_cron(self):
        """Configurar cron job"""
        print("\n⏰ CONFIGURACIÓN DE CRON\n")
        
        cron_command = f"0 */2 * * * cd {project_root} && python manage.py sync_google_sheets >> logs/sync_sheets.log 2>&1"
        
        print("Para ejecutar cada 2 horas, agrega esta línea a crontab:")
        print(f"\n  {cron_command}\n")
        
        print("Pasos:")
        print("  1. Ejecuta: crontab -e")
        print("  2. Pega la línea arriba")
        print("  3. Guarda y cierra")
        print()
        
        # Intentar agregar automáticamente
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                f.write(f"{cron_command}\n")
                temp_file = f.name
            
            subprocess.run(['crontab', temp_file], check=True)
            os.unlink(temp_file)
            print("✅ Cron job agregado exitosamente!")
        
        except Exception as e:
            print(f"⚠️ Agregación automática falló: {str(e)}")
            print("   Agrega manualmente usando: crontab -e")
        
        print()
    
    def check_health(self):
        """Verificar salud del sistema"""
        print("\n💉 HEALTH CHECK\n")
        
        checks = {
            "Archivo de log": self.log_file.exists(),
            "Directorio de logs": self.log_file.parent.exists(),
            "Conexión a BD": self._check_db(),
            "Conexión a Google Sheets": self._check_google_sheets(),
        }
        
        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check_name}")
        
        print()
    
    def _check_db(self):
        """Verificar conexión a BD"""
        try:
            from adm.models import Account
            Account.objects.count()
            return True
        except:
            return False
    
    def _check_google_sheets(self):
        """Verificar conexión a Google Sheets"""
        try:
            import requests
            response = requests.post(
                'https://servertools.bdpyc.cl/api/google-sheets/1eY2EWKjarh1a909CLSrL22lP5HVUF5CZzdM9SDHBT3M?format=n8n',
                json={},
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def report(self):
        """Generar reporte completo"""
        print("\n📈 REPORTE DE SINCRONIZACIÓN\n")
        
        from adm.models import Account
        
        total_accounts = Account.objects.count()
        active_accounts = Account.objects.filter(status=1).count()
        inactive_accounts = Account.objects.filter(status=0).count()
        
        print(f"📊 ESTADÍSTICAS GENERALES:")
        print(f"   Total de cuentas: {total_accounts}")
        print(f"   Activas: {active_accounts}")
        print(f"   Inactivas: {inactive_accounts}")
        
        # Contar por servicio
        from django.db.models import Count
        services = Account.objects.values('account_name__description').annotate(
            count=Count('id')
        ).order_by('-count')
        
        print(f"\n📱 CUENTAS POR SERVICIO:")
        for service in services[:10]:
            print(f"   {service['account_name__description']}: {service['count']}")
        
        # Mostrar última sincronización
        self.status()


def main():
    parser = argparse.ArgumentParser(
        description='Helper para sincronización de Google Sheets'
    )
    
    parser.add_argument('--status', action='store_true', help='Ver estado')
    parser.add_argument('--sync', action='store_true', help='Ejecutar sincronización')
    parser.add_argument('--verbose', action='store_true', help='Modo verbose')
    parser.add_argument('--test', action='store_true', help='Ejecutar tests')
    parser.add_argument('--logs', type=int, nargs='?', const=20, help='Ver logs (líneas)')
    parser.add_argument('--setup-cron', action='store_true', help='Configurar cron')
    parser.add_argument('--health', action='store_true', help='Health check')
    parser.add_argument('--report', action='store_true', help='Reporte completo')
    
    args = parser.parse_args()
    
    helper = SyncHelper()
    
    if args.status:
        helper.status()
    elif args.sync:
        helper.sync(verbose=args.verbose)
    elif args.test:
        helper.test()
    elif args.logs is not None:
        helper.logs(lines=args.logs)
    elif args.setup_cron:
        helper.setup_cron()
    elif args.health:
        helper.check_health()
    elif args.report:
        helper.report()
    else:
        parser.print_help()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏸️ Operación cancelada por usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)
