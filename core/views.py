# core/views.py
import random

from django.db.models import F, Avg
from django.db import models, transaction
from django.utils import timezone
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from accounts.views import normalize_phone


from accounts.models import User
from .models import Visitor, Center, Queue, Notification, Rating
from .serializers import (
    VisitorSerializer,
    CenterSerializer,
    QueueSerializer,
    QueueStatusSerializer, NotificationSerializer
)
from .services.queue_service import (
    get_queue_stats,
    update_queue_status,
    create_queue,
    update_center_avg_wait, expire_queue_token
)
from .permissions import IsOwnerOrCenterManager
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


GHASEDAK_API_KEY = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" # add your api
GHASEDAK_URL = "http://api.ghasedaksms.com/v2/send/verify"
FRONTEND_URL = getattr(settings, "FRONTEND_URL", "https://example.com")


def _send_status_sms(phone: str, token: str) -> tuple[bool, str]:
    if not phone:
        return False, "no phone"
    phone = normalize_phone(phone)
    link = f"{FRONTEND_URL.rstrip('/')}/profile?token={token or ''}"
    payload = {
        "receptor": phone,
        "type": 1,
        "template": "status",
        "param1": str(token)
    }
    print(token)
    headers = {"apikey": GHASEDAK_API_KEY, "Content-Type": "application/x-www-form-urlencoded"}

    try:
        resp = requests.post(GHASEDAK_URL, data=payload, headers=headers, timeout=15)

        # LOG
        logger.info("Ghasedak request payload=%s", payload)
        logger.info("Ghasedak response code=%s body=%s", resp.status_code, resp.text)
        print("Ghasedak request payload=%s", payload)
        print("Ghasedak response code=%s body=%s", resp.status_code, resp.text)


        if resp.status_code in (200, 201, 202):
            return True, resp.text
        else:
            return False, f"status={resp.status_code} body={resp.text}"
    except requests.RequestException as e:
        logger.exception("Failed to send status SMS to %s: %s", phone, e)
        print("Failed to send status SMS to %s: %s", phone, e)

        return False, str(e)


def _send_simple_authcode(phone: str, code: str) -> tuple[bool, str]:
    payload = {
        "receptor": phone,
        "type": 1,
        "template": "AuthCode",
        "param1": str(code)
    }
    headers = {"apikey": GHASEDAK_API_KEY, "Content-Type": "application/x-www-form-urlencoded"}
    try:
        resp = requests.post(GHASEDAK_URL, data=payload, headers=headers, timeout=12)
        logger.info("Ghasedak simple resp: %s %s", resp.status_code, resp.text)
        print("Ghasedak simple resp: %s %s", resp.status_code, resp.text)
        return (resp.status_code in (200,201,202)), resp.text
    except Exception as e:
        logger.exception("simple send failed: %s", e)
        return False, str(e)

# -------------------------------
# Center Views
# -------------------------------
class CenterCreate(APIView):
    """
    Handle creation of a Center by an authenticated user.
    Restricts users from creating multiple centers or creating
    a center while they are already registered as a Visitor.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=CenterSerializer)
    def post(self, request):
        user = request.user
        # Ensure the user doesn't already own a center
        if Center.objects.filter(user=user).exists():
            return Response({"detail": "You already have a center."}, status=status.HTTP_400_BAD_REQUEST)

        # Prevent visitors from creating centers
        if Visitor.objects.filter(user=user).exists() or not request.user.is_center_manager:
            return Response({"detail": "Visitors cannot create centers."}, status=status.HTTP_400_BAD_REQUEST)

        # Serialize and save new center
        serializer = CenterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=user, phone=user.phone)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CenterDetail(APIView):
    """
    Retrieve or delete a specific Center.
    Only the center owner (manager) is authorized to access or delete it.
    """
    permission_classes = [IsAuthenticated, IsOwnerOrCenterManager]

    def get(self, request, pk):
        center = get_object_or_404(Center, user_id=pk)
        self.check_object_permissions(request, center)
        return Response(CenterSerializer(center).data)

    def delete(self, request, pk):
        center = get_object_or_404(Center, user_id=pk)
        self.check_object_permissions(request, center)
        center.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# -------------------------------
# Visitor Views
# -------------------------------
class VisitorListCreate(APIView):
    """
    Handle creation and listing of visitors.
    - Managers can see visitors of their centers.
    - Visitors can only see their own profile.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if getattr(user, 'is_center_manager', False):
            # Managers view all visitors of their center
            visitors = Visitor.objects.filter(queues__center__user=user).distinct()
        else:
            # Regular visitors see only their own record
            visitors = Visitor.objects.filter(user=user)

        return Response(VisitorSerializer(visitors, many=True).data)

    @swagger_auto_schema(request_body=VisitorSerializer)
    def post(self, request):
        user = request.user
        is_manager = getattr(user, "is_center_manager", False)

        if not is_manager:
            return Response({"detail": "You are not allowed to create visitors."}, status=status.HTTP_403_FORBIDDEN)

        serializer = VisitorSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone = serializer.validated_data.get("phone")
        if not phone:
            return Response({"detail": "Phone is required."}, status=status.HTTP_400_BAD_REQUEST)

        existing = User.objects.filter(phone=phone).first()
        if existing and existing.is_center_manager:
            return Response({"detail": "این شماره مربوط به یک مدیر است."}, 400)

        visitor_user, _ = User.objects.get_or_create(
            phone=phone,
            defaults={"is_center_manager": False}
        )

        center = get_object_or_404(Center, user=user)

        with transaction.atomic():
            # save visitor (serializer باید فقط فیلدهای مدل Visitor رو قبول کنه)
            visitor = serializer.save(user=visitor_user)

            # create queue (create_queue باید توکن و expires رو تنظیم کنه)
            queue = create_queue(center_id=user.id, visitor=visitor)

        # send SMS (non-blocking for DB changes; but we wait for response to report status)
        sms_ok, sms_resp = _send_status_sms(phone=visitor.phone, token=queue.access_token)


        resp_data = {
            "visitor": VisitorSerializer(visitor).data,
            "queue_id": queue.id,
            "access_token": queue.access_token,
            "token_expires_at": queue.token_expires_at,
            "position": queue.position,
            "sms_sent": sms_ok
        }
        if not sms_ok:
            resp_data["sms_error"] = sms_resp

        return Response(resp_data, status=status.HTTP_201_CREATED)

class VisitorDetail(APIView):
    """
    Retrieve, update, or delete a Visitor record.
    Permission: only the owner (visitor) or the associated center manager.
    """
    permission_classes = [IsAuthenticated, IsOwnerOrCenterManager]

    def get(self, request, pk):
        visitor = get_object_or_404(Visitor, user_id=pk)
        self.check_object_permissions(request, visitor)
        return Response(VisitorSerializer(visitor).data)

    def delete(self, request, pk):
        visitor = get_object_or_404(Visitor, user_id=pk)
        self.check_object_permissions(request, visitor)
        visitor.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @swagger_auto_schema(request_body=VisitorSerializer)
    def patch(self, request, pk):
        visitor = get_object_or_404(Visitor, user_id=pk)
        self.check_object_permissions(request, visitor)
        serializer = VisitorSerializer(visitor, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -------------------------------
# Queue Views
# -------------------------------
class QueueListCreate(APIView):
    """
    Retrieve or create queue entries.
    - Managers: see queues of their centers.
    - Visitors: see only their own queue entries.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, center_id):
        user = request.user

        if getattr(user, 'is_center_manager', False):
            # Managers see all queues for their center
            queues = Queue.objects.filter(center__user_id=center_id, center__user=user).order_by('position')
        else:
            # Visitors see only their own queue entries
            try:
                visitor = Visitor.objects.get(user=user)
                queues = Queue.objects.filter(center__user_id=center_id, visitor=visitor).order_by('position')
            except Visitor.DoesNotExist:
                queues = Queue.objects.none()

        return Response(QueueSerializer(queues, many=True).data)

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['visitor_id'],
            properties={'visitor_id': openapi.Schema(type=openapi.TYPE_INTEGER)}
        )
    )
    def post(self, request, center_id):
        user = request.user
        center = get_object_or_404(Center, user_id=center_id)

        # Validate data and create queue
        serializer = QueueSerializer(data=request.data, context={'center': center})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        visitor = serializer.validated_data['visitor']

        if getattr(user, 'is_center_manager', False):
            # Ensure manager owns this center
            if center.user != user:
                return Response({'detail': 'Not allowed to add queue to this center.'}, status=status.HTTP_403_FORBIDDEN)
        else:
            # Visitors can only queue themselves
            if not hasattr(visitor, 'user') or visitor.user != user:
                return Response({'detail': 'You can only add yourself to the queue.'}, status=status.HTTP_403_FORBIDDEN)

        queue_item = create_queue(center_id, visitor)
        return Response(QueueSerializer(queue_item).data, status=status.HTTP_201_CREATED)


class QueueUpdateStatus(APIView):
    """
    Update the status of a queue item.
    Only the queue owner or the center manager can change status.
    """
    permission_classes = [IsAuthenticated, IsOwnerOrCenterManager]

    @swagger_auto_schema(request_body=QueueStatusSerializer)
    def patch(self, request, pk):
        queue_item = get_object_or_404(Queue, pk=pk)
        self.check_object_permissions(request, queue_item)

        serializer = QueueStatusSerializer(queue_item, data=request.data, partial=True)
        if serializer.is_valid():
            queue_item = update_queue_status(pk, serializer.validated_data['status'])

            # If completed, update center's average waiting time
            avg_wait = None
            if queue_item.status == 'done':
                avg_wait = update_center_avg_wait(queue_item.center)

            data = QueueSerializer(queue_item).data
            data['avg_wait_seconds'] = avg_wait if avg_wait is not None else queue_item.center.avg_wait_seconds
            return Response(data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class QueueStatsView(APIView):
    """
    Return overall queue statistics for a given center.
    - Managers: can view their own center stats.
    - Visitors: can only view stats if they belong to that center.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, center_id):
        user = request.user
        center = get_object_or_404(Center, user_id=center_id)

        if getattr(user, 'is_center_manager', False):
            if center.user != user:
                return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        else:
            # Ensure the visitor is linked to this center
            try:
                visitor = Visitor.objects.get(user=user)
            except Visitor.DoesNotExist:
                return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

            if not Queue.objects.filter(center=center, visitor=visitor).exists():
                return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        stats = get_queue_stats(center_id)
        return Response(stats)


class PublicRateByTokenView(APIView):
    """
    Public endpoint to submit a rating using the queue access_token.
    No authentication required — token proves ownership.
    Rules:
      - token must exist, belong to a queue with status == 'done'
      - token_expires_at must be in the future (within RATING_WINDOW)
      - rating is 0..5 (integer)
      - after successful rating, the queue token is expired (cleared)
      - rating is persisted and center's average can be computed via other endpoints
    """
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['token', 'score'],
            properties={
                'token': openapi.Schema(type=openapi.TYPE_STRING),
                'score': openapi.Schema(type=openapi.TYPE_INTEGER, description='Integer between 0 and 5')
            }
        )
    )
    def post(self, request):
        token = request.data.get('token')
        score = request.data.get('score')

        if not token:
            return Response({'detail': 'token required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            score = int(score)
        except (TypeError, ValueError):
            return Response({'detail': 'score must be an integer 0..5'}, status=status.HTTP_400_BAD_REQUEST)

        if score < 0 or score > 5:
            return Response({'detail': 'score must be between 0 and 5'}, status=status.HTTP_400_BAD_REQUEST)

        queue = get_object_or_404(Queue, access_token=token)

        now = timezone.now()
        if queue.status != 'done':
            return Response({'detail': 'Rating allowed only after your queue is done.'}, status=status.HTTP_400_BAD_REQUEST)

        if not queue.token_expires_at or queue.token_expires_at < now or queue.token_expired:
            return Response({'detail': 'Token expired.'}, status=status.HTTP_400_BAD_REQUEST)

        # persist rating: need visitor (queue.visitor)
        visitor = queue.visitor
        center = queue.center

        with transaction.atomic():
            # create or update rating for (center, visitor)
            rating, created = Rating.objects.update_or_create(
                center=center,
                visitor=visitor,
                defaults={'score': score}
            )

            # expire token immediately after rating so it cannot be reused
            expire_queue_token(queue)

        # return aggregated result
        avg = center.ratings.aggregate(avg=Avg('score'))['avg'] or 0.0
        satisfaction = round((avg / 5.0) * 100.0, 2)
        return Response({
            'detail': 'Rating saved.',
            'center_id': center.user_id,
            'score': rating.score,
            'average_score': round(avg, 2),
            'satisfaction_percent': satisfaction,
            'ratings_count': center.ratings.count()
        }, status=status.HTTP_200_OK)


# Update PublicQueueStatsView to accept optional token and return same structure
class PublicQueueStatsView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, token):
        if not token:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        queue = get_object_or_404(Queue, access_token=token)
        center_id = queue.center_id

        stats = get_queue_stats(center_id, queue)
        # attach rating summary
        center = queue.center
        avg = center.ratings.aggregate(avg=Avg('score'))['avg'] or 0.0
        stats['average_score'] = round(avg, 2)
        stats['satisfaction_percent'] = round((avg / 5.0) * 100.0, 2)
        stats['ratings_count'] = center.ratings.count()

        return Response(stats, status=status.HTTP_200_OK)

class QueueDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsOwnerOrCenterManager]

    def delete(self, request, pk):
        queue_item = get_object_or_404(Queue, pk=pk)
        self.check_object_permissions(request, queue_item)

        visitor = queue_item.visitor
        user = visitor.user

        # اگر مدیر مرکز نیست (یعنی خود visitor حذفش کند)
        if not request.user.is_center_manager:
            notification = Notification.objects.create(
                phone=visitor.phone,
                name=visitor.name
            )
            # حذف واقعی: فقط User
            user.delete()

            serializer = NotificationSerializer(notification)
            return Response(serializer.data, status=status.HTTP_204_NO_CONTENT)

        # اگر مدیر هست
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationsDelete(APIView):
    permission_classes = [IsAuthenticated, IsOwnerOrCenterManager]
    def delete(self, request, center_id):
        notification = Notification.objects.filter(center__user_id=center_id)
        notification.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationList(APIView):
    permission_classes = [IsAuthenticated, IsOwnerOrCenterManager]

    def get(self, request, center_id):
        notifications = Notification.objects.filter(center__user_id=center_id)
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class QueueNextView(APIView):
    """
    Advance the queue:
    - Marks the current 'in_progress' visitor as 'done'
    - Moves the next 'waiting' visitor to 'in_progress'
    """
    permission_classes = [IsAuthenticated, IsOwnerOrCenterManager]

    def post(self, request, center_id):
        center = get_object_or_404(Center, user_id=center_id)
        self.check_object_permissions(request, center)

        # Mark the current active queue as done
        current = Queue.objects.filter(center=center, status='in_progress').order_by('position').first()
        if current:
            current.status = 'done'
            current.save()

        # Move the next waiting visitor into progress
        next_queue = Queue.objects.filter(center=center, status='waiting').order_by('position').first()
        if not next_queue:
            return Response({'detail': 'No more visitors in queue.'}, status=status.HTTP_200_OK)

        next_queue.status = 'in_progress'
        next_queue.save()

        data = {
            'done': QueueSerializer(current).data if current else None,
            'now_in_progress': QueueSerializer(next_queue).data
        }
        return Response(data, status=status.HTTP_200_OK)


class QueueReorderView(APIView):
    """
    Reorder a queue item to the first or last position in its center queue.
    Example request:
      POST /api/queue/{pk}/reorder/
      Body: { "action": "to_first" }  or  { "action": "to_last" }
    """
    permission_classes = [IsAuthenticated, IsOwnerOrCenterManager]

    @transaction.atomic
    def post(self, request, pk):
        queue_item = Queue.objects.select_related('center').select_for_update().get(pk=pk)
        self.check_object_permissions(request, queue_item)

        action = request.data.get('action')
        if action not in ('to_first', 'to_last'):
            return Response({'detail': 'Invalid action. Use "to_first" or "to_last".'},
                            status=status.HTTP_400_BAD_REQUEST)

        center = queue_item.center

        if action == 'to_first':
            # Shift all positions below upward by one
            Queue.objects.filter(center=center, position__lt=queue_item.position).update(position=F('position') + 1)
            queue_item.position = 1

        elif action == 'to_last':
            # Shift all positions above downward by one
            max_pos = Queue.objects.filter(center=center).aggregate(max_pos=models.Max('position'))['max_pos'] or 0
            Queue.objects.filter(center=center, position__gt=queue_item.position).update(position=F('position') - 1)
            queue_item.position = max_pos

        queue_item.save()
        return Response(QueueSerializer(queue_item).data, status=status.HTTP_200_OK)
