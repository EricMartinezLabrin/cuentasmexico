"""
Email verification module for authenticated users.
"""
import os
import random
import string

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail


class EmailVerification:
    """Handle email verification codes."""

    @staticmethod
    def generate_verification_code(length=6):
        return ''.join(random.choices(string.digits, k=length))

    @staticmethod
    def _cache_key(user_id, email):
        return f"email_verify_{user_id}_{email.lower()}"

    @staticmethod
    def send_verification_code(user_id, email, code):
        """
        Send a verification code to the provided email.
        Stores code in cache for 10 minutes on success.
        """
        email = email.strip().lower()
        subject = "Tu codigo de verificacion - Cuentas Mexico"
        message = (
            f"Tu codigo de verificacion para Cuentas Mexico es: {code}\n\n"
            "Este codigo expira en 10 minutos."
        )

        try:
            sent = False
            resend_api_key = os.getenv("RESEND_API_KEY")

            if resend_api_key:
                try:
                    import resend

                    resend.api_key = resend_api_key
                    resend.Emails.send({
                        "from": "noreply@cuentasmexico.com",
                        "to": email,
                        "subject": subject,
                        "text": message,
                    })
                    sent = True
                except Exception:
                    sent = False

            if not sent:
                from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@cuentasmexico.com")
                sent_count = send_mail(
                    subject=subject,
                    message=message,
                    from_email=from_email,
                    recipient_list=[email],
                    fail_silently=False
                )
                sent = sent_count > 0

            if sent:
                cache.set(EmailVerification._cache_key(user_id, email), code, timeout=600)
                return {"success": True, "message": "Codigo enviado correctamente"}

            return {"success": False, "message": "No fue posible enviar el codigo"}
        except Exception as e:
            return {"success": False, "message": f"Error al enviar codigo: {str(e)}"}

    @staticmethod
    def verify_code(user_id, email, code):
        """
        Verify code for specific user+email.
        """
        email = email.strip().lower()
        cache_key = EmailVerification._cache_key(user_id, email)
        stored_code = cache.get(cache_key)

        if not stored_code:
            return {"success": False, "message": "Codigo expirado o no encontrado. Solicita uno nuevo."}

        if stored_code == code:
            cache.delete(cache_key)
            return {"success": True, "message": "Email verificado correctamente"}

        return {"success": False, "message": "Codigo incorrecto"}
