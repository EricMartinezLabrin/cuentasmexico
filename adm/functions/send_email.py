from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template
from django.contrib.sites.models import Site
from adm.functions.best import Best


class Email():
    def protocol(request):
        if request.is_secure:
            return 'http://'
        else:
            return 'http://'

    def email_passwords(request, email, acc):
        subject = f'Cuentas Mexico. Tu claves de acceso a {acc[0].account.account_name}.'
        template = get_template('index/emails/template_send_password.html')
        actual = acc[0].account.account_name

        content = template.render({
            'user': email,
            'domain': Site.objects.get_current().domain,
            'protocol': Email.protocol(request),
            'acc': acc,
            'best_sellers': Best.best_sellers(actual.id, 3)
        })

        message = EmailMultiAlternatives(subject,  # Titulo
                                         '',
                                         settings.EMAIL_HOST_USER,  # Remitente
                                         [email])  # Destinatario

        message.attach_alternative(content, 'text/html')
        message.send()
