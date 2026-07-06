from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, UserOTP, Address

class AddressSerializer(serializers.ModelSerializer):
    """
    Serializer for Address model
    """
    class Meta:
        model = Address
        fields = [
            'id', 'title', 'city', 'address_text', 'latitude', 'longitude',
            'is_default', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model - used for profile views
    """
    full_name = serializers.SerializerMethodField()
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone_number', 'first_name', 'last_name',
            'full_name', 'role', 'role_display', 'avatar', 'is_verified',
            'date_joined', 'rider_status', 'current_latitude', 'current_longitude'
        ]
        read_only_fields = ['id', 'date_joined', 'is_verified']
    
    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration
    """
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    role = serializers.ChoiceField(choices=User.Role.choices, default=User.Role.CUSTOMER)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'phone_number', 'password', 'password2', 
                  'first_name', 'last_name', 'role']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "رمزهای عبور مطابقت ندارند."})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login
    """
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        
        # Try to find user by username or email or phone
        user = None
        if '@' in username:
            try:
                user_obj = User.objects.get(email=username)
                user = authenticate(username=user_obj.username, password=password)
            except User.DoesNotExist:
                pass
        
        if not user:
            user = authenticate(username=username, password=password)
        
        if not user:
            raise serializers.ValidationError("نام کاربری یا رمز عبور اشتباه است.")
        
        if not user.is_active:
            raise serializers.ValidationError("این کاربر غیرفعال شده است.")
        
        attrs['user'] = user
        return attrs


class TokenSerializer(serializers.Serializer):
    """
    Serializer for returning JWT tokens
    """
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for password change
    """
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "رمزهای عبور جدید مطابقت ندارند."})
        return attrs


class UpdateProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user profile
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'avatar']
    
    def validate_email(self, value):
        user = self.context['request'].user
        if User.objects.exclude(pk=user.pk).filter(email=value).exists():
            raise serializers.ValidationError("این ایمیل قبلاً ثبت شده است.")
        return value
    
    def validate_phone_number(self, value):
        user = self.context['request'].user
        if value and User.objects.exclude(pk=user.pk).filter(phone_number=value).exists():
            raise serializers.ValidationError("این شماره تلفن قبلاً ثبت شده است.")
        return value


class RiderLocationSerializer(serializers.Serializer):
    """
    Serializer for updating rider's location
    """
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    
    def validate(self, attrs):
        # Basic validation for Iran coordinates (optional)
        lat = float(attrs['latitude'])
        lng = float(attrs['longitude'])
        if lat < 25 or lat > 40:
            raise serializers.ValidationError("عرض جغرافیایی نامعتبر است.")
        if lng < 44 or lng > 64:
            raise serializers.ValidationError("طول جغرافیایی نامعتبر است.")
        return attrs


class RiderStatusSerializer(serializers.ModelSerializer):
    """
    Serializer for updating rider's availability status
    """
    class Meta:
        model = User
        fields = ['rider_status']
    
    def validate_rider_status(self, value):
        user = self.context['request'].user
        if not user.is_delivery_rider():
            raise serializers.ValidationError("فقط راننده‌ها می‌توانند وضعیت خود را تغییر دهند.")
        return value


class OTPRequestSerializer(serializers.Serializer):
    """
    Serializer for requesting OTP
    """
    phone_number = serializers.CharField(max_length=15, required=True)


class OTPVerifySerializer(serializers.Serializer):
    """
    Serializer for verifying OTP
    """
    phone_number = serializers.CharField(max_length=15, required=True)
    code = serializers.CharField(max_length=6, required=True)
    