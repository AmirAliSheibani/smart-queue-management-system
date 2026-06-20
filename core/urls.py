from django.urls import path
from .views import (
    CenterCreate, CenterDetail,
    VisitorListCreate, VisitorDetail,
    QueueListCreate,
    QueueUpdateStatus, QueueStatsView, QueueDeleteView, QueueNextView, QueueReorderView, PublicQueueStatsView,
    NotificationsDelete, NotificationList, PublicRateByTokenView
)

app_name = 'core'

urlpatterns = [
    # Centers
    path('centers/', CenterCreate.as_view(), name='center-list-create'),
    path('centers/<int:pk>/', CenterDetail.as_view(), name='center-detail'),

    # Visitors
    path('visitors/', VisitorListCreate.as_view(), name='visitor-list-create'),
    path('visitors/<int:pk>/', VisitorDetail.as_view(), name='visitor-detail'),

    # Queue
    path('queue/<int:center_id>/', QueueListCreate.as_view(), name='queue-list-create'),
    path('queue/<int:pk>/delete', QueueDeleteView.as_view(), name='queue-delete'),

    # Status Update (PATCH)
    path('queue/<int:pk>/status/', QueueUpdateStatus.as_view(), name='queue-update-status'),

    # Queue Statistics
    path('queue/<int:center_id>/stats/', QueueStatsView.as_view(), name='queue-stats'),
    path('public/queue/<str:token>/stats/', PublicQueueStatsView.as_view(), name='public-queue-stats'),
    path('public/queue/rate/', PublicRateByTokenView.as_view(), name='public-queue-rate'),
    path('queue/<int:center_id>/next/', QueueNextView.as_view(), name='queue-next'),
    path('queue/<int:pk>/reorder/', QueueReorderView.as_view(), name='queue-reorder'),
    path('notification/<int:center_id>/', NotificationList.as_view(), name='notification-list'),
    path('notification/<int:center_id>/delete/', NotificationsDelete.as_view(), name='notification-delete'),


]

