from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import update_session_auth_hash
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import User, Address
from .serializers import (
    RegisterSerializer, LoginSerializer, TokenSerializer, UserSerializer,
    ChangePasswordSerializer, UpdateProfileSerializer, RiderLocationSerializer,
    RiderStatusSerializer, AddressSerializer
)
from .permissions import IsOwnerOrAdmin, IsDeliveryRider, IsAdminUser


class RegisterView(generics.CreateAPIView):
    """
    User registration endpoint
    """
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="ثبت نام کاربر جدید",
        description="ثبت نام با نام کاربری، ایمیل، شماره تلفن و رمز عبور",
        responses={201: UserSerializer, 400: "Invalid data"}
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_201_CREATED)


class LoginView(generics.GenericAPIView):
    """
    User login endpoint
    """
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="ورود کاربر",
        description="ورود با نام کاربری/ایمیل/شماره تلفن و رمز عبور",
        responses={200: TokenSerializer, 401: "Invalid credentials"}
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
        }, status=status.HTTP_200_OK)


class LogoutView(generics.GenericAPIView):
    """
    User logout endpoint - blacklists the refresh token
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="خروج کاربر",
        description="باطل کردن توکن رفرش",
        responses={205: "Logged out", 400: "Invalid token"}
    )
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class ProfileView(generics.RetrieveUpdateAPIView):
    """
    View and update user profile
    """
    serializer_class = UpdateProfileSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    
    def get_object(self):
        return self.request.user
    
    @extend_schema(
        summary="دریافت پروفایل کاربر",
        responses={200: UserSerializer}
    )
    def get(self, request, *args, **kwargs):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    
    @extend_schema(
        summary="بروزرسانی پروفایل کاربر",
        responses={200: UserSerializer}
    )
    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)
    
    @extend_schema(
        summary="بروزرسانی جزئی پروفایل کاربر",
        responses={200: UserSerializer}
    )
    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


class ChangePasswordView(generics.GenericAPIView):
    """
    Change user password
    """
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="تغییر رمز عبور",
        responses={200: "Password changed", 400: "Invalid data"}
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response({"old_password": "رمز عبور فعلی اشتباه است."}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        update_session_auth_hash(request, user)
        
        return Response({"message": "رمز عبور با موفقیت تغییر کرد."}, 
                       status=status.HTTP_200_OK)


class RiderLocationView(generics.GenericAPIView):
    """
    Update delivery rider's current location
    """
    serializer_class = RiderLocationSerializer
    permission_classes = [IsAuthenticated, IsDeliveryRider]
    
    @extend_schema(
        summary="بروزرسانی موقعیت راننده",
        description="راننده موقعیت لحظه‌ای خود را ارسال می‌کند",
        responses={200: "Location updated", 400: "Invalid location"}
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        user.update_location(
            serializer.validated_data['latitude'],
            serializer.validated_data['longitude']
        )
        
        return Response({"message": "موقعیت با موفقیت بروزرسانی شد."}, 
                       status=status.HTTP_200_OK)


class RiderStatusView(generics.UpdateAPIView):
    """
    Update rider's availability status
    """
    serializer_class = RiderStatusSerializer
    permission_classes = [IsAuthenticated, IsDeliveryRider]
    
    def get_object(self):
        return self.request.user
    
    @extend_schema(
        summary="تغییر وضعیت راننده",
        description="available, busy, offline",
        responses={200: RiderStatusSerializer}
    )
    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


class UserListView(generics.ListAPIView):
    """
    Admin only - List all users
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    @extend_schema(
        summary="لیست تمام کاربران (فقط ادمین)",
        responses={200: UserSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Admin only - Manage any user
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    @extend_schema(
        summary="جزییات کاربر (فقط ادمین)",
        responses={200: UserSerializer}
    )
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="بروزرسانی کاربر (فقط ادمین)",
        responses={200: UserSerializer}
    )
    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)
    
    @extend_schema(
        summary="حذف کاربر (فقط ادمین)",
        responses={204: "Deleted"}
    )
    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)


class AddressViewSet(viewsets.ModelViewSet):
    """
    Manage user addresses
    """
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        is_first = not Address.objects.filter(user=self.request.user).exists()
        serializer.save(user=self.request.user, is_default=is_first, is_active=is_first)

    @extend_schema(
        summary="لیست آدرس‌های کاربر",
        responses={200: AddressSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="افزودن آدرس جدید",
        responses={201: AddressSerializer}
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="فعال‌سازی آدرس",
        description="تنظیم یک آدرس به عنوان آدرس فعال فعلی برای فیلترینگ رستوران‌ها",
        responses={200: AddressSerializer}
    )
    @action(detail=True, methods=['post'], url_path='set-active')
    def set_active(self, request, pk=None):
        address = self.get_object()
        Address.objects.filter(user=request.user).update(is_active=False)
        address.is_active = True
        address.save()
        return Response(AddressSerializer(address).data)