
import logging
import random
from datetime import timedelta
import requests
from django.utils import timezone
from django.conf import settings
from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .models import ManagerOTP

logger = logging.getLogger(__name__)

# تنظیمات Ghasedak
GHASEDAK_API_KEY = "P/gEN/k+t6qVTLRd1Fzede42XCe+wJjYkGsLKx2ZaGM"
GHASEDAK_URL = "http://api.ghasedaksms.com/v2/send/verify"


def _issue_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}

def normalize_phone(phone: str) -> str:
    """حذف فاصله‌ها و کاراکترهای اضافی"""
    if not phone:
        return ""
    phone = phone.strip().replace(" ", "").replace("-", "")
    return phone


class ManagerLoginStartView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = normalize_phone(request.data.get("phone"))
        if not phone:
            return Response({"detail": "Phone number required"}, status=status.HTTP_400_BAD_REQUEST)

        # ایجاد یا دریافت کاربر
        user, _ = User.objects.get_or_create(phone=phone)

        # تولید کد OTP
        otp_code = random.randint(100000, 999999)

        # ذخیره یا بروزرسانی OTP در دیتابیس
        otp_obj, _ = ManagerOTP.objects.get_or_create(phone=phone)
        otp_obj.touch_new_code(code=otp_code, ttl_seconds=300)

        # ارسال پیامک
        payload = {
            "receptor": phone,
            "type": 1,
            "template": "AuthCode",
            "param1": str(otp_code)
        }
        headers = {"apikey": GHASEDAK_API_KEY, "Content-Type": "application/x-www-form-urlencoded"}
        try:
            resp = requests.post(GHASEDAK_URL, data=payload, headers=headers, timeout=15)
            print(resp.status_code, resp.text)
            return Response({"detail": "OTP sent"}, status=status.HTTP_200_OK)
        except requests.exceptions.RequestException as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ManagerVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = normalize_phone(request.data.get("phone"))
        code = request.data.get("code")
        if not phone or not code:
            return Response({"detail": "Phone and code required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            otp_obj = ManagerOTP.objects.get(phone=phone)
        except ManagerOTP.DoesNotExist:
            return Response({"detail": "No OTP request found or expired."}, status=status.HTTP_400_BAD_REQUEST)

        if otp_obj.is_expired():
            otp_obj.delete()
            return Response({"detail": "OTP expired."}, status=status.HTTP_400_BAD_REQUEST)

        if str(otp_obj.code) != str(code):
            otp_obj.increment_attempts()
            return Response({"detail": "Invalid code."}, status=status.HTTP_400_BAD_REQUEST)

        # موفقیت: OTP پاک و کاربر مرکز مدیر شود، توکن JWT داده شود
        otp_obj.delete()
        user, _ = User.objects.get_or_create(phone=phone)
        user.is_center_manager = True
        user.save(update_fields=["is_center_manager"])

        refresh = RefreshToken.for_user(user)
        return Response({
            "is_center_manager": True,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }, status=status.HTTP_200_OK)


# class ManagerLoginStartView(APIView):
#     permission_classes = [AllowAny]
#
#     def post(self, request):
#         raw_phone = request.data.get("phone")
#         phone = normalize_phone(raw_phone)
#         if not phone:
#             return Response({"detail": "Phone number required"}, status=status.HTTP_400_BAD_REQUEST)
#
#         # ایجاد یا دریافت کاربر
#         user, created = User.objects.get_or_create(phone=phone)
#         user.is_center_manager = True
#         user.save(update_fields=["is_center_manager"])
#
#         # تولید کد OTP ساده
#         otp_code = random.randint(100000, 999999)
#         payload = {
#             "receptor": phone,
#             "type": 1,
#             "template": "AuthCode",
#             "param1": str(otp_code)
#         }
#         headers = {"apikey": GHASEDAK_API_KEY, "Content-Type": "application/x-www-form-urlencoded"}
#
#         try:
#             resp = requests.post(GHASEDAK_URL, data=payload, headers=headers, timeout=15)
#             print(resp.status_code, resp.text)
#             # ایجاد توکن JWT
#             refresh = RefreshToken.for_user(user)
#             return Response({
#                 "created": created,
#                 "is_center_manager": True,
#                 "otp_code": otp_code,
#                 "access": str(refresh.access_token),
#                 "refresh": str(refresh),
#             }, status=status.HTTP_200_OK)
#         except requests.exceptions.RequestException as e:
#             return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# VISITOR (unchanged logic except normalization)
class VisitorLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = normalize_phone(request.data.get("phone"))
        if not phone:
            return Response({"detail": "Phone number required"}, status=status.HTTP_400_BAD_REQUEST)

        user, created = User.objects.get_or_create(phone=phone, defaults={"is_center_manager": False})
        if user.is_center_manager:
            return Response({"detail": "This account is a center manager. Use manager login."}, status=status.HTTP_400_BAD_REQUEST)

        tokens = _issue_tokens_for_user(user)
        return Response({"created": created, **tokens, "is_center_manager": False}, status=status.HTTP_200_OK)


# MANAGER: start (create OTP)
# class ManagerLoginStartView(APIView):
#     permission_classes = [AllowAny]
#
#     OTP_TTL_SECONDS = getattr(settings, "OTP_TTL_SECONDS", 300)
#     MAX_SENDS_PER_MINUTE = getattr(settings, "OTP_SEND_RATE_LIMIT", 5)
#
#     def post(self, request):
#         raw_phone = request.data.get("phone")
#         phone = normalize_phone(raw_phone)
#         if not phone:
#             return Response({"detail": "Phone number required"}, status=status.HTTP_400_BAD_REQUEST)
#
#         # create user if missing (but do NOT promote yet)
#         user, _ = User.objects.get_or_create(phone=phone, defaults={"is_center_manager": False})
#
#         # Get or create OTP record
#         otp_obj, created = ManagerOTP.objects.get_or_create(phone=phone, defaults={
#             "code": "000000",
#             "expires_at": timezone.now() + timedelta(seconds=self.OTP_TTL_SECONDS)
#         })
#
#         # simple rate-limit: check last_sent_at & send_count
#         now = timezone.now()
#         if otp_obj.last_sent_at and (now - otp_obj.last_sent_at).total_seconds() < 60:
#             if otp_obj.send_count >= self.MAX_SENDS_PER_MINUTE:
#                 return Response({"detail": "Too many OTP requests. Try again later."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
#         else:
#             # if last sent more than a minute ago, reset counter
#             otp_obj.send_count = 0
#             otp_obj.save(update_fields=["send_count"])
#
#         # create new code and update fields
#         otp_code = random.randint(100000, 999999)  # رندوم ۶ رقمی
#         otp_obj.touch_new_code(code=otp_code, ttl_seconds=self.OTP_TTL_SECONDS)
#
#         try:
#             resp = _send_otp_via_ghasedak(phone, otp_code)
#             return Response({"detail": resp}, status=200)  # فقط برای debug
#         except Exception as e:
#             return Response({"detail": str(e)}, status=500)


# MANAGER: verify
# class ManagerVerifyView(APIView):
#     permission_classes = [AllowAny]
#
#     MAX_VERIFY_ATTEMPTS = getattr(settings, "OTP_MAX_VERIFY_ATTEMPTS", 5)
#     ATTEMPT_WINDOW_SECONDS = getattr(settings, "OTP_ATTEMPT_WINDOW_SECONDS", 300)
#
#     def post(self, request):
#         raw_phone = request.data.get("phone")
#         phone = normalize_phone(raw_phone)
#         code = request.data.get("code")
#         if not phone or not code:
#             return Response({"detail": "Phone and code required."}, status=status.HTTP_400_BAD_REQUEST)
#
#         try:
#             otp_obj = ManagerOTP.objects.get(phone=phone)
#         except ManagerOTP.DoesNotExist:
#             return Response({"detail": "No OTP request found or expired."}, status=status.HTTP_400_BAD_REQUEST)
#
#         # expired?
#         if otp_obj.is_expired():
#             otp_obj.delete()
#             return Response({"detail": "OTP expired."}, status=status.HTTP_400_BAD_REQUEST)
#
#         # too many attempts?
#         if otp_obj.attempts >= self.MAX_VERIFY_ATTEMPTS:
#             otp_obj.delete()  # optional: remove record after lockout
#             return Response({"detail": "Too many attempts. Try later."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
#
#         # match?
#         if str(otp_obj.code) != str(code):
#             otp_obj.increment_attempts()
#             return Response({"detail": "Invalid code."}, status=status.HTTP_400_BAD_REQUEST)
#
#         # success: delete OTP, promote user to manager (persist), issue tokens
#         otp_obj.delete()
#
#         user, created = User.objects.get_or_create(phone=phone)
#         user.is_center_manager = True
#         user.save(update_fields=["is_center_manager"])
#
#         tokens = _issue_tokens_for_user(user)
#         return Response({"is_center_manager": True, **tokens}, status=status.HTTP_200_OK)



class ManagerLoginTestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = request.data.get("phone")
        if not phone:
            return Response({"detail": "Phone number required."}, status=status.HTTP_400_BAD_REQUEST)

        user, created = User.objects.get_or_create(phone=phone)
        user.is_center_manager = True
        user.save(update_fields=["is_center_manager"])

        refresh = RefreshToken.for_user(user)
        return Response({
            "created": created,
            "is_center_manager": True,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }, status=status.HTTP_200_OK)


