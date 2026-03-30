"""
Notificaciones por email usando Resend.com
"""
import os
import requests
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


class ResendEmail:
    """Clase para enviar emails usando la API de Resend"""

    API_URL = "https://api.resend.com/emails"

    @staticmethod
    def send_email(to: str, subject: str, html: str, from_email: str = None) -> bool:
        """
        Envía un email usando Resend API

        Args:
            to: Email destinatario
            subject: Asunto del email
            html: Contenido HTML del email
            from_email: Email remitente (opcional, usa default)

        Returns:
            True si se envió correctamente, False en caso contrario
        """
        api_key = os.environ.get('RESEND_API_KEY')

        if not api_key:
            logger.error("RESEND_API_KEY no está configurado en .env")
            return False

        if not from_email:
            from_email = os.environ.get('RESEND_FROM_EMAIL', 'Cuentas Mexico <noreply@cuentasmexico.com>')

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "from": from_email,
            "to": [to] if isinstance(to, str) else to,
            "subject": subject,
            "html": html
        }

        try:
            response = requests.post(
                ResendEmail.API_URL,
                headers=headers,
                json=data,
                timeout=10
            )

            if 200 <= response.status_code < 300:
                logger.info(f"Email enviado exitosamente a {to}")
                return True
            else:
                logger.error(f"Error enviando email: {response.status_code} - {response.text}")
                return False

        except requests.RequestException as e:
            logger.exception(f"Error de conexión enviando email: {e}")
            return False

    @staticmethod
    def _send_email_fallback(to, subject: str, html: str) -> bool:
        """
        Fallback con backend SMTP de Django cuando Resend falla.
        """
        recipients = [to] if isinstance(to, str) else list(to or [])
        if not recipients:
            return False
        try:
            from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@cuentasmexico.com")
            sent = send_mail(
                subject=subject,
                message=strip_tags(html),
                from_email=from_email,
                recipient_list=recipients,
                html_message=html,
                fail_silently=False,
            )
            if sent:
                logger.info(f"Email fallback enviado por SMTP a {recipients}")
                return True
            logger.error(f"Fallback SMTP no envió correos a {recipients}")
            return False
        except Exception:
            logger.exception("Error enviando fallback SMTP")
            return False

    @staticmethod
    def _get_support_whatsapp() -> str:
        """
        Obtiene el WhatsApp de soporte desde configuración y usa un fallback seguro.
        """
        support_whatsapp = (
            os.environ.get('SUPPORT_WHATSAPP')
            or os.environ.get('WHATSAPP_SUPPORT')
            or getattr(settings, 'SUPPORT_WHATSAPP', None)
            or '+521 833 535 5863'
        )
        return str(support_whatsapp).strip()

    @staticmethod
    def notify_no_stock(customer_info: dict, cart_details: list, payment_info: dict) -> bool:
        """
        Notifica al admin que no hay stock y se requiere entrega manual

        Args:
            customer_info: Información del cliente (username, email, etc)
            cart_details: Lista de productos comprados
            payment_info: Información del pago (payment_id, amount, etc)
        """
        admin_email_raw = (
            os.environ.get('ADMIN_EMAILS')
            or os.environ.get('ADMIN_EMAIL')
            or getattr(settings, 'ADMIN_EMAIL', None)
            or 'contacto@cuentasmexico.com'
        )
        admin_email = [email.strip() for email in str(admin_email_raw).split(',') if email.strip()]
        support_whatsapp = ResendEmail._get_support_whatsapp()
        support_whatsapp_digits = ''.join(ch for ch in support_whatsapp if ch.isdigit())
        wa_link = f"https://wa.me/{support_whatsapp_digits}" if support_whatsapp_digits else ""

        # Construir tabla de productos
        products_html = ""
        for item in cart_details:
            products_html += f"""
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">{item.get('service_name', 'N/A')}</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{item.get('months', 'N/A')} mes(es)</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{item.get('profiles', 'N/A')}</td>
                <td style="padding: 8px; border: 1px solid #ddd;">${item.get('price', 'N/A')}</td>
            </tr>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: #dc3545; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                <h1 style="margin: 0;">⚠️ Sin Stock - Entrega Manual Requerida</h1>
            </div>

            <div style="background: #f8f9fa; padding: 20px; border: 1px solid #ddd;">
                <h2 style="color: #333;">Información del Cliente</h2>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px;"><strong>Usuario:</strong></td>
                        <td style="padding: 8px;">{customer_info.get('username', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px;"><strong>Email:</strong></td>
                        <td style="padding: 8px;">{customer_info.get('email', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px;"><strong>ID Usuario:</strong></td>
                        <td style="padding: 8px;">{customer_info.get('user_id', 'N/A')}</td>
                    </tr>
                </table>

                <h2 style="color: #333; margin-top: 20px;">Información del Pago</h2>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px;"><strong>Payment ID:</strong></td>
                        <td style="padding: 8px;">{payment_info.get('payment_id', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px;"><strong>Monto:</strong></td>
                        <td style="padding: 8px;">${payment_info.get('amount', 'N/A')} MXN</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px;"><strong>Tipo de Pago:</strong></td>
                        <td style="padding: 8px;">{payment_info.get('payment_type', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px;"><strong>Cart ID:</strong></td>
                        <td style="padding: 8px;">{payment_info.get('cart_id', 'N/A')}</td>
                    </tr>
                </table>

                <h2 style="color: #333; margin-top: 20px;">Productos Comprados (Sin Stock)</h2>
                <table style="width: 100%; border-collapse: collapse; background: white;">
                    <thead>
                        <tr style="background: #333; color: white;">
                            <th style="padding: 10px; text-align: left;">Servicio</th>
                            <th style="padding: 10px; text-align: left;">Duración</th>
                            <th style="padding: 10px; text-align: left;">Perfiles</th>
                            <th style="padding: 10px; text-align: left;">Precio</th>
                        </tr>
                    </thead>
                    <tbody>
                        {products_html}
                    </tbody>
                </table>

                <div style="background: #fff3cd; border: 1px solid #ffc107; padding: 15px; margin-top: 20px; border-radius: 4px;">
                    <strong>⏰ Acción Requerida:</strong><br>
                    Por favor, entrega las cuentas manualmente al cliente lo antes posible.
                    El cliente ha sido notificado que recibirá sus claves dentro de 24 horas.
                </div>
                
                <div style="background: #e7f5ec; border: 1px solid #8fd19e; padding: 15px; margin-top: 14px; border-radius: 4px;">
                    <strong>📱 WhatsApp de soporte:</strong> {support_whatsapp}<br>
                    {'<a href="' + wa_link + '" style="display:inline-block; margin-top:10px; background:#25D366; color:#fff; text-decoration:none; padding:8px 14px; border-radius:4px;">Abrir WhatsApp</a>' if wa_link else ''}
                </div>
            </div>

            <div style="background: #333; color: white; padding: 15px; text-align: center; border-radius: 0 0 8px 8px;">
                <small>Este es un mensaje automático de Cuentas México</small>
            </div>
        </body>
        </html>
        """

        subject = f"🚨 Sin Stock - Entrega Manual Requerida - {customer_info.get('username', 'Cliente')}"
        sent = ResendEmail.send_email(
            to=admin_email,
            subject=subject,
            html=html
        )
        if sent:
            return True

        logger.warning("Reintentando notificación sin stock por SMTP fallback")
        return ResendEmail._send_email_fallback(
            to=admin_email,
            subject=subject,
            html=html
        )

    @staticmethod
    def notify_customer_pending_delivery(customer_email: str, customer_name: str, products: list) -> bool:
        """
        Notifica al cliente que su pedido está siendo procesado manualmente

        Args:
            customer_email: Email del cliente
            customer_name: Nombre del cliente
            products: Lista de productos comprados
        """
        products_html = ""
        for product in products:
            products_html += f"<li>{product}</li>"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: #28a745; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                <h1 style="margin: 0;">✅ Pago Recibido</h1>
            </div>

            <div style="background: #f8f9fa; padding: 20px; border: 1px solid #ddd;">
                <h2 style="color: #333;">¡Hola {customer_name}!</h2>

                <p>Hemos recibido tu pago correctamente. Tu pedido está siendo procesado.</p>

                <h3 style="color: #333;">Productos:</h3>
                <ul>
                    {products_html}
                </ul>

                <div style="background: #d1ecf1; border: 1px solid #bee5eb; padding: 15px; margin-top: 20px; border-radius: 4px;">
                    <strong>📧 Entrega de Claves:</strong><br>
                    Recibirás las claves de acceso en tu correo electrónico dentro de las próximas <strong>24 horas</strong>.<br><br>
                    Si tienes alguna duda, puedes contactarnos por WhatsApp.
                </div>

                <p style="margin-top: 20px;">
                    <a href="https://wa.me/5218335355863" style="background: #25D366; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; display: inline-block;">
                        💬 Contactar por WhatsApp
                    </a>
                </p>
            </div>

            <div style="background: #333; color: white; padding: 15px; text-align: center; border-radius: 0 0 8px 8px;">
                <small>Gracias por tu compra - Cuentas México</small>
            </div>
        </body>
        </html>
        """

        return ResendEmail.send_email(
            to=customer_email,
            subject="✅ Pago Recibido - Tus claves llegarán pronto",
            html=html
        )
