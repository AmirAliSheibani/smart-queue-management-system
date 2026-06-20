from django.urls import path
from .views import (
    VisitorLoginView,
    ManagerLoginStartView,
    ManagerLoginTestView,
    ManagerVerifyView,
)
from rest_framework_simplejwt.views import TokenRefreshView

app_name = 'accounts'

urlpatterns = [
    path("auth/login/visitor/", VisitorLoginView.as_view(), name="login-visitor"),
    path("auth/login/manager/", ManagerLoginStartView.as_view(), name="login-manager-start"),
    path("auth/test-login/manager/", ManagerLoginTestView.as_view(), name="test-login-manager-start"),
    path("auth/login/manager/verify/", ManagerVerifyView.as_view(), name="login-manager-verify"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
]