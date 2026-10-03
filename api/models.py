from django.db import models


class PhoneOtpChallenge(models.Model):
    phone_e164 = models.CharField(max_length=15, db_index=True)
    code_hash = models.CharField(max_length=256)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    request_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['phone_e164', 'expires_at'])]


class PhoneSession(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='phone_sessions')
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'expires_at'])]

# Create your models here.
