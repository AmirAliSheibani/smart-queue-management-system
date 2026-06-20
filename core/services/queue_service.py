from django.db.models import Avg, ExpressionWrapper, DurationField
from core.models import Queue, Center
import secrets
from datetime import timedelta
from django.db.models import Count, Case, When, IntegerField, F, Q
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from django.conf import settings
from django.shortcuts import get_object_or_404
 # adjust import path if needed
# Token & rating TTLs
QUEUE_TOKEN_TTL = getattr(settings, "QUEUE_TOKEN_TTL", timedelta(days=14))       # original token TTL on creation
RATING_WINDOW = getattr(settings, "QUEUE_RATING_WINDOW", timedelta(hours=12))    # keep token available for rating after done
TOKEN_BYTE_LENGTH = getattr(settings, "QUEUE_TOKEN_BYTES", 25)
MAX_TOKEN_GEN_ATTEMPTS = getattr(settings, "QUEUE_TOKEN_MAX_ATTEMPTS", 5)

def _generate_token(byte_length: int = 32) -> str:
    """Return a numeric token of exact length."""
    return ''.join(str(secrets.randbelow(10)) for _ in range(byte_length))

def create_queue(center_id, visitor):
    """
    Create a Queue row with consistent `position` under transaction and
    a unique access_token + token_expires_at.
    """
    center = get_object_or_404(Center, user_id=center_id)
    now = timezone.now()

    with transaction.atomic():
        last_pos = (
            Queue.objects.select_for_update()
            .filter(center=center)
            .aggregate(max_pos=Max("position"))["max_pos"]
            or 0
        )
        position = last_pos + 1

        for _ in range(MAX_TOKEN_GEN_ATTEMPTS):
            token = _generate_token()
            try:
                q = Queue.objects.create(
                    center=center,
                    visitor=visitor,
                    position=position,
                    access_token=token,
                    token_expires_at=now + QUEUE_TOKEN_TTL,
                    token_expired=False,
                )
                return q
            except IntegrityError:
                continue

        # fallback loop (should be very rare)
        while True:
            token = _generate_token()
            try:
                q = Queue.objects.create(
                    center=center,
                    visitor=visitor,
                    position=position,
                    access_token=token,
                    token_expires_at=now + QUEUE_TOKEN_TTL,
                    token_expired=False,
                )
                return q
            except IntegrityError:
                continue

def update_queue_status(queue_id, status):
    """
    Safely update a queue's status.
    When status transitions to 'done' (from non-done), we:
      - keep the access_token but set token_expires_at to now + RATING_WINDOW
        so the visitor can submit a rating within that window.
      - do not immediately clear the token (visitor needs it to rate).
      - shift subsequent queue positions down by 1 (for done).
    If status is set to 'done' again (already done), no-op.
    """
    with transaction.atomic():
        q = Queue.objects.select_for_update().get(pk=queue_id)
        old_status = q.status
        q.status = status

        now = timezone.now()

        if status == 'done' and old_status != 'done':
            # allow rating for RATING_WINDOW after completion
            q.token_expired = False
            q.token_expires_at = now + RATING_WINDOW
            # keep access_token so the visitor can rate via token
            q.save()

            # shift positions of later items up by -1
            Queue.objects.filter(
                center=q.center,
                position__gt=q.position
            ).update(position=F('position') - 1)
        else:
            q.save()

    return q

def expire_queue_token(queue: Queue):
    """
    Immediate expire: clear token and mark expired (used after rating).
    """
    queue.access_token = None
    queue.token_expires_at = timezone.now()
    queue.token_expired = True
    queue.save(update_fields=['access_token', 'token_expires_at', 'token_expired'])

def get_queue_stats(center_id, queue=None):
    """
    Super optimized version.
    Uses 1 aggregate query + 1 lightweight center-only query.
    """
    qs = Queue.objects.filter(center_id=center_id)

    # Heavy aggregation - optimized
    counts = qs.aggregate(
        waiting=Count('id', filter=Q(status='waiting')),
        in_progress=Count('id', filter=Q(status='in_progress')),
        done=Count('id', filter=Q(status='done')),
        total=Count('id'),
    )

    # Ultra lightweight fetch
    center = Center.objects.only(
        'latitude', 'longitude', 'avg_wait_seconds'
    ).get(user=center_id)

    # Attach center info
    counts.update({
        'latitude': center.latitude,
        'longitude': center.longitude,
        'avg_wait_seconds': center.avg_wait_seconds,
    })

    # Optional queue row
    if queue:
        counts['position'] = queue.position
        counts['status'] = queue.status

    return counts

def update_center_avg_wait(center):
    done_queues = center.queues.filter(status='done')
    if not done_queues.exists():
        center.avg_wait_seconds = 0
        center.save(update_fields=['avg_wait_seconds'])
        return 0

    avg_wait = done_queues.annotate(
        wait_time=ExpressionWrapper(
            F('updated_at') - F('created_at'),
            output_field=DurationField()
        )
    ).aggregate(avg_time=Avg('wait_time'))['avg_time']

    seconds = avg_wait.total_seconds() if avg_wait else 0
    center.avg_wait_seconds = seconds
    center.save(update_fields=['avg_wait_seconds'])
    return seconds

