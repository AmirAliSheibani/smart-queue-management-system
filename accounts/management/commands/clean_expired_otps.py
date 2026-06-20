from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import ManagerOTP
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Delete expired ManagerOTP records."

    def handle(self, *args, **options):
        now = timezone.now()
        expired_qs = ManagerOTP.objects.filter(expires_at__lte=now)
        count = expired_qs.count()
        if count:
            expired_qs.delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {count} expired OTP record(s)."))
            logger.info("Deleted %d expired OTP record(s).", count)
        else:
            self.stdout.write("No expired OTP records to delete.")