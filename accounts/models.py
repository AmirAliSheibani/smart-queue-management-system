from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from datetime import timedelta

class ManagerOTP(models.Model):
    """
    OTP record for manager login. No Redis required.
    - phone: normalized phone string (unique per attempt)
    - code: 6-digit OTP
    - created_at: when record created
    - expires_at: when OTP expires
    - attempts: failed verify attempts counter
    - send_count: times OTP was sent (used for rate limiting)
    - last_sent_at: last time an OTP was sent
    """
    phone = models.CharField(max_length=32, db_index=True, unique=True)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    send_count = models.PositiveIntegerField(default=0)
    last_sent_at = models.DateTimeField(null=True, blank=True)

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def mark_sent(self):
        now = timezone.now()
        # reset send_count if last_sent_at is older than 1 minute
        if self.last_sent_at and (now - self.last_sent_at) > timedelta(minutes=1):
            self.send_count = 0
        self.send_count += 1
        self.last_sent_at = now
        self.save(update_fields=["send_count", "last_sent_at"])

    def touch_new_code(self, code, ttl_seconds):
        """
        Replace code, reset attempts, set expiry and update send metadata.
        """
        now = timezone.now()
        self.code = str(code)
        self.attempts = 0
        self.expires_at = now + timedelta(seconds=ttl_seconds)
        self.last_sent_at = now
        self.send_count = 1
        self.save(update_fields=["code", "attempts", "expires_at", "last_sent_at", "send_count"])

    def increment_attempts(self):
        self.attempts = models.F("attempts") + 1
        self.save(update_fields=["attempts"])
        # refresh from DB to get real integer value
        self.refresh_from_db(fields=["attempts"])
        return self.attempts

    def __str__(self):
        return f"OTP for {self.phone} (expires {self.expires_at})"


class UserManager(BaseUserManager):
    def create_user(self, phone, **extra_fields):
        if not phone:
            raise ValueError('Phone number is required')
        user = self.model(phone=phone, **extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password or "admin")
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField(max_length=15, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_center_manager = models.BooleanField(default=False)

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.phone
