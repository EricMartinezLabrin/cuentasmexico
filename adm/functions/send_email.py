from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template

class Email():
    def email_passwords(user):
        subject = 'Titulo del correo'
        template = get_template('index/emails/template_send_password.html')

        content = template.render({
            'user': user,
        })

        message = EmailMultiAlternatives(subject, #Titulo
                                        '',
                                        settings.EMAIL_HOST_USER, #Remitente
                                        [user]) #Destinatario

        message.attach_alternative(content, 'text/html')
        message.send()