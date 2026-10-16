import os
import re
import time
import mimetypes
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from adm.db.constants import URL
from adm.functions.send_whatsapp_notification import Notification
from adm.models import MarketingBulkWhatsApp, MarketingBulkWhatsAppRecipient


MAX_RECIPIENTS = 5000
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def split_phone_inputs(raw_value):
    return [value.strip() for value in re.split(r'[\s,]+', str(raw_value or '')) if value.strip()]


def normalize_mexican_whatsapp(value):
    digits = re.sub(r'\D+', '', str(value or ''))
    if len(digits) == 10:
        phone = digits
    elif len(digits) == 12 and digits.startswith('52'):
        phone = digits[-10:]
    elif len(digits) == 13 and digits.startswith('521'):
        phone = digits[-10:]
    else:
        return ''
    return f'+521{phone}'


def public_image_url(job):
    if not job.image:
        return ''
    image_url = str(job.image.url or '').strip()
    if image_url.startswith(('http://', 'https://')):
        return image_url
    base_url = (os.getenv('PUBLIC_APP_URL') or URL or '').strip()
    return f"{base_url.rstrip('/')}/{image_url.lstrip('/')}" if base_url else image_url


def _provider_result(job, recipient):
    if job.image:
        mime_type = mimetypes.guess_type(job.image.name or '')[0] or 'image/jpeg'
        return Notification.send_whatsapp_notification_with_media_details(
            job.message_text,
            recipient.normalized_number,
            public_image_url(job),
            mime_type=mime_type,
            file_name=os.path.basename(job.image.name or 'marketing.jpg'),
        )
    return Notification.send_whatsapp_notification_details(
        job.message_text, '', recipient.normalized_number,
    )


def _sleep_until(job_id, deadline):
    while timezone.now() < deadline:
        job = MarketingBulkWhatsApp.objects.only('status').get(pk=job_id)
        if job.status == 'cancelled':
            return False
        time.sleep(min(10, max(1, (deadline - timezone.now()).total_seconds())))
    return True


def process_bulk_job(job_id):
    job = MarketingBulkWhatsApp.objects.get(pk=job_id)
    if job.status in ('completed', 'cancelled', 'failed'):
        return
    if job.status == 'queued':
        job.status = 'running'
        job.started_at = job.started_at or timezone.now()
        job.status_message = 'Preparando el siguiente envío.'
        job.save(update_fields=['status', 'started_at', 'status_message', 'updated_at'])

    while True:
        job.refresh_from_db()
        if job.status == 'cancelled':
            return
        if job.next_action_at and timezone.now() < job.next_action_at:
            job.status = 'waiting'
            job.status_message = 'Esperando el siguiente envío.'
            job.save(update_fields=['status', 'status_message', 'updated_at'])
            if not _sleep_until(job.id, job.next_action_at):
                return
            job.next_action_at = None
            job.status = 'running'
            job.status_message = 'Enviando.'
            job.save(update_fields=['next_action_at', 'status', 'status_message', 'updated_at'])

        recipient = job.recipients.filter(status='pending').order_by('id').first()
        if not recipient:
            job.status = 'completed'
            job.finished_at = timezone.now()
            job.next_action_at = None
            job.pause_until = None
            job.status_message = 'Proceso terminado.'
            job.save(update_fields=['status', 'finished_at', 'next_action_at', 'pause_until', 'status_message', 'updated_at'])
            return

        job.status = 'running'
        job.current_number = recipient.normalized_number
        job.status_message = 'Enviando mensaje.'
        job.save(update_fields=['status', 'current_number', 'status_message', 'updated_at'])
        try:
            result = _provider_result(job, recipient)
            success = bool(result.get('success'))
            response = result.get('detail') or result.get('response_body') or result.get('error') or ''
        except Exception as exc:  # pragma: no cover - protects the worker loop
            success = False
            response = f'{type(exc).__name__}: {exc}'

        now = timezone.now()
        recipient.status = 'sent' if success else 'error'
        recipient.reason = '' if success else response[:2000]
        recipient.provider_response = response[:4000]
        recipient.attempted_at = now
        recipient.sent_at = now if success else None
        recipient.save(update_fields=['status', 'reason', 'provider_response', 'attempted_at', 'sent_at', 'updated_at'])

        job.attempt_count += 1
        if success:
            job.sent_count += 1
        else:
            job.error_count += 1
        remaining = job.recipients.filter(status='pending').exists()
        if remaining:
            if job.attempt_count % job.batch_size == 0:
                from random import uniform
                pause_minutes = uniform(job.batch_pause_min_minutes, job.batch_pause_max_minutes)
                job.pause_until = now + timedelta(minutes=pause_minutes)
                job.next_action_at = job.pause_until
                job.status = 'waiting'
                job.status_message = f'Pausa obligatoria después de {job.batch_size} intentos.'
            else:
                from random import uniform
                delay_minutes = uniform(job.delay_min_minutes, job.delay_max_minutes)
                job.next_action_at = now + timedelta(minutes=delay_minutes)
                job.pause_until = None
                job.status = 'waiting'
                job.status_message = 'Esperando el siguiente envío.'
        job.save(update_fields=[
            'attempt_count', 'sent_count', 'error_count', 'next_action_at',
            'pause_until', 'status', 'status_message', 'updated_at',
        ])


def claim_next_job():
    with transaction.atomic():
        job = (
            MarketingBulkWhatsApp.objects.select_for_update()
            .filter(status='queued')
            .order_by('created_at', 'id')
            .first()
        )
        if not job:
            job = (
                MarketingBulkWhatsApp.objects.select_for_update()
                .filter(status='waiting', next_action_at__lte=timezone.now())
                .order_by('next_action_at', 'id')
                .first()
            )
        if job:
            now = timezone.now()
            job.status = 'running'
            job.started_at = job.started_at or now
            job.status_message = 'Preparando el siguiente envío.'
            job.save(update_fields=['status', 'started_at', 'status_message', 'updated_at'])
            return job.id
    return None


def create_bulk_job(*, user, raw_numbers, message, image, delay_min, delay_max):
    values = split_phone_inputs(raw_numbers)
    if not values:
        raise ValueError('Agrega al menos un número de WhatsApp.')
    if len(values) > MAX_RECIPIENTS:
        raise ValueError(f'El máximo es de {MAX_RECIPIENTS} números por proceso.')
    if not message.strip() and not image:
        raise ValueError('Agrega un mensaje, una imagen o ambos.')
    if image and image.size > MAX_IMAGE_BYTES:
        raise ValueError('La imagen no puede superar 10 MB.')
    if delay_min < 1 or delay_max < delay_min or delay_max > 60:
        raise ValueError('El intervalo debe estar entre 1 y 60 minutos y ser válido.')

    with transaction.atomic():
        job = MarketingBulkWhatsApp.objects.create(
            created_by=user,
            message_text=message,
            image=image,
            delay_min_minutes=delay_min,
            delay_max_minutes=delay_max,
            total_count=len(values),
            status_message='Proceso en cola.',
        )
        seen = set()
        for value in values:
            normalized = normalize_mexican_whatsapp(value)
            reason = ''
            status = 'pending'
            if not normalized:
                status, reason = 'ignored', 'Número mexicano inválido.'
            elif normalized in seen:
                status, reason = 'ignored', 'Número duplicado después de normalizar.'
            else:
                seen.add(normalized)
            MarketingBulkWhatsAppRecipient.objects.create(
                job=job,
                original_value=value,
                normalized_number=normalized,
                status=status,
                reason=reason,
            )
        job.ignored_count = job.recipients.filter(status='ignored').count()
        job.save(update_fields=['ignored_count', 'updated_at'])
    return job
