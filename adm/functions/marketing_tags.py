from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from adm.models import MarketingUserTag, UserDetail
from adm.functions.send_whatsapp_notification import Notification


EVOLUTION_CAMPAIGN_ACTIVE_LABEL = 'Campaña Activa'


def _safe_valid_until_from_campaign(campaign):
    meta = campaign.audience_filters or {}
    promo_params = meta.get('promo_params') if isinstance(meta.get('promo_params'), dict) else {}
    raw = promo_params.get('offer_valid_until') or meta.get('offer_valid_until')
    if raw:
        try:
            dt = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt
        except Exception:
            pass
    base = campaign.sent_at or campaign.updated_at or campaign.created_at or timezone.now()
    return base + timedelta(days=30)


def _campaign_sent_expiration(campaign):
    return _safe_valid_until_from_campaign(campaign) + timedelta(hours=24)


def _cooldown_expiration(campaign):
    now = timezone.now()
    valid_until = _safe_valid_until_from_campaign(campaign)
    remaining_seconds = max(0, int((valid_until - now).total_seconds()))
    ttl_seconds = int(remaining_seconds * 0.25)
    ttl_seconds = max(24 * 3600, min(ttl_seconds, 7 * 24 * 3600))
    return now + timedelta(seconds=ttl_seconds)


def _active_qs():
    now = timezone.now()
    return MarketingUserTag.objects.filter(is_active=True).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    )


def _user_has_active_marketing_tag(user):
    return _active_qs().filter(user=user).exists()


def _sync_user_evolution_campaign_label(user):
    try:
        detail = UserDetail.objects.get(user=user)
    except UserDetail.DoesNotExist:
        return

    if not detail.lada or not detail.phone_number:
        return

    should_have = _user_has_active_marketing_tag(user)
    Notification.set_contact_label_by_name(
        lada=detail.lada,
        phone_number=detail.phone_number,
        label_name=EVOLUTION_CAMPAIGN_ACTIVE_LABEL,
        enabled=should_have,
    )


def cleanup_expired_marketing_tags(user=None):
    now = timezone.now()
    expired_qs = MarketingUserTag.objects.filter(is_active=True, expires_at__isnull=False, expires_at__lte=now)
    if user is not None:
        expired_qs = expired_qs.filter(user=user)
    affected_user_ids = list(expired_qs.values_list('user_id', flat=True).distinct())
    if affected_user_ids:
        expired_qs.update(is_active=False)
        for user_id in affected_user_ids:
            try:
                target_user = User.objects.get(pk=user_id)
                _sync_user_evolution_campaign_label(target_user)
            except User.DoesNotExist:
                continue


def has_active_cooldown(user_id, channel):
    return _active_qs().filter(
        user_id=user_id,
        tag_type=MarketingUserTag.TAG_TYPE_COOLDOWN,
        channel__in=[channel, 'all'],
    ).exists()


def users_with_active_cooldown(channel):
    return set(
        _active_qs()
        .filter(tag_type=MarketingUserTag.TAG_TYPE_COOLDOWN, channel__in=[channel, 'all'])
        .values_list('user_id', flat=True)
    )


def apply_campaign_sent_tags(campaign, user, channel):
    cleanup_expired_marketing_tags(user=user)
    sent_expires_at = _campaign_sent_expiration(campaign)
    cooldown_expires_at = _cooldown_expiration(campaign)

    sent_key = f'campaign_sent:{campaign.id}:{channel}'
    MarketingUserTag.objects.update_or_create(
        user=user,
        tag_key=sent_key,
        defaults={
            'campaign': campaign,
            'tag_type': MarketingUserTag.TAG_TYPE_CAMPAIGN_SENT,
            'channel': channel,
            'label': f'Campaña #{campaign.id} enviada ({channel.upper()})',
            'color': 'primary',
            'metadata': {'campaign_id': campaign.id, 'channel': channel},
            'expires_at': sent_expires_at,
            'is_active': True,
        },
    )

    cooldown_key = f'campaign_cooldown:{channel}'
    MarketingUserTag.objects.update_or_create(
        user=user,
        tag_key=cooldown_key,
        defaults={
            'campaign': campaign,
            'tag_type': MarketingUserTag.TAG_TYPE_COOLDOWN,
            'channel': channel,
            'label': f'Cooldown anti-spam ({channel.upper()})',
            'color': 'danger',
            'metadata': {'campaign_id': campaign.id, 'channel': channel},
            'expires_at': cooldown_expires_at,
            'is_active': True,
        },
    )
    _sync_user_evolution_campaign_label(user)


def marketing_tags_for_sales_view(user):
    cleanup_expired_marketing_tags(user=user)
    _sync_user_evolution_campaign_label(user)
    rows = _active_qs().filter(user=user).order_by('expires_at', '-created_at')
    items = []
    for row in rows:
        expires_txt = ''
        if row.expires_at:
            expires_txt = timezone.localtime(row.expires_at).strftime('%d/%m/%Y %H:%M')
        items.append(
            {
                'label': row.label,
                'color': row.color,
                'channel': row.channel,
                'expires_at': expires_txt,
            }
        )
    return items
