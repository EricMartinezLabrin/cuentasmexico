from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template
from django.contrib.sites.models import Site
from adm.functions.best import Best
import logging
import os

logger = logging.getLogger(__name__)


class Email():
    def protocol(request):
        """Retorna el protocolo correcto (http o https)"""
        if request and hasattr(request, 'is_secure') and request.is_secure():
            return 'https://'
        else:
            return 'http://'

    def email_passwords(request, email, acc):
        """
        Envía las claves de acceso al cliente usando Resend API.
        Si el email es 'example@example.com' o está vacío, no envía.
        
        IMPORTANTE: El dominio de Resend debe estar verificado. 
        Por ahora se usa 'noreply@resend.dev' como remitente (dominio de prueba de Resend)
        """
        # No enviar a emails de ejemplo o vacíos
        if not email or email == 'example@example.com':
            logger.info(f"Email no válido para envío: {email}")
            return False
            
        try:
            from django.contrib.auth.models import User
            from adm.models import UserDetail, Business
            import resend
            
            subject = f'Cuentas Mexico - Claves de acceso a {acc[0].account.account_name}.'
            template = get_template('index/emails/template_send_password.html')
            actual = acc[0].account.account_name

            # Obtener detalles del usuario para free_days
            try:
                user = User.objects.get(email=email)
                user_detail = UserDetail.objects.get(user=user)
                free_days = user_detail.free_days
            except (User.DoesNotExist, UserDetail.DoesNotExist):
                free_days = 0

            # Obtener logo de Business (Cuentas México)
            try:
                business_logo_url = Business.objects.first().logo.url if Business.objects.first() and Business.objects.first().logo else ''
            except:
                business_logo_url = ''

            # Procesar best_sellers: Best.best_sellers() retorna lista de tuplas (Service, count)
            best_sellers_list = []
            for service, count in Best.best_sellers(actual.id, 3):
                best_sellers_list.append({
                    'service': service,
                    'count': count,
                    'logo_url': service.logo.url if service.logo else '',
                    'description': service.description,
                    'id': service.id
                })

            # Preparar datos contextuales
            context_data = {
                'user': email,
                'domain': Site.objects.get_current().domain,
                'protocol': Email.protocol(request),
                'acc': acc,
                'best_sellers': best_sellers_list,
                'free_days': free_days,
                # Pasar URLs de Backblaze B2
                'account_logo_url': actual.logo.url if actual.logo else '',
                'business_logo_url': business_logo_url,
            }

            html_content = template.render(context_data)

            # Usar Resend API
            resend_api_key = os.getenv('RESEND_API_KEY')
            if not resend_api_key:
                logger.error("RESEND_API_KEY no está configurada")
                return False
            
            # Configurar la API key
            resend.api_key = resend_api_key
            
            # NOTA: Usar noreply@resend.dev mientras se verifica el dominio cuentasmexico.com en Resend
            # Una vez verificado el dominio, cambiar a: "from": "noreply@cuentasmexico.com"
            response = resend.Emails.send({
                "from": "noreply@cuentasmexico.com",
                "to": email,
                "subject": subject,
                "html": html_content,
            })
            
            logger.info(f"Email enviado exitosamente a {email} con Resend. Response: {response}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando email con Resend a {email}: {str(e)}", exc_info=True)
            return False

