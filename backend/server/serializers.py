import re
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Booking, Major, Course, Language, Pending, Profile, Rating, Tutor, FileUpload
from django.utils import timezone 
from datetime import datetime

class FileUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileUpload
        fields = ('file',)

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request else None

        if 'user' in validated_data:
            raise ValueError("User should not be included in validated_data")

        file_upload = FileUpload.objects.create(user=user, **validated_data)
        return file_upload

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['phone_number']

    def validate_phone_number(self, value):
        if Profile.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError(f"The phone number {value} is already in use.")
        return value

class PasswordChangeSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    new_password = serializers.CharField(write_only=True, required=True)

    def validate_new_password(self, value):
        user_serializer = UserSerializer()
        return user_serializer.validate_password(value)

class UserSerializer(serializers.ModelSerializer):
    is_tutor = serializers.SerializerMethodField()
    profile = ProfileSerializer(required=False)
    profile_picture = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'username', 'password', 'email', 'profile', 'is_tutor', 'profile_picture']
        extra_kwargs = {
            'password': {'write_only': True, 'required': True},
            'username': {'required': True},
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'is_tutor': {'required': True},
        }

    def validate(self, data):
        required_fields = ['username', 'email', 'first_name', 'last_name', 'password']

        for field in required_fields:
            if field not in data or not data[field].strip():
                raise serializers.ValidationError({field: f"{field.capitalize()} is required."})
        
        return data
    
    def validate_email(self, value):
        if not '@lau.edu' in value:
            raise serializers.ValidationError("Please use your Lebanese American University email address.")
        return value

    def validate_username(self, value):
        if ' ' in value:
            raise serializers.ValidationError("Username should not contain spaces.")
        return value
    
    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        if not any(char.isupper() for char in value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter.")
        if not any(char in re.escape('!@#$%^&*()_+-=[]{},.<>?;:/|') for char in value):
            raise serializers.ValidationError("Password must contain at least one special character.")
        return value

    def get_is_tutor(self, obj):
        return obj.groups.filter(name='tutors').exists()

    def create(self, validated_data):
        profile_data = validated_data.pop('profile', {})
        user = User.objects.create(**validated_data)
        user.set_password(validated_data['password'])
        user.save()
        
        Profile.objects.create(user=user, **profile_data)
        return user

    def get_profile_picture(self, obj):
        try:
            profile_picture = FileUpload.objects.filter(user=obj).last()
            if profile_picture:
                return profile_picture.file.url
            return None
        except FileUpload.DoesNotExist:
            return None


class MajorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Major
        fields = ['id', 'name', 'code']

class CourseSerializer(serializers.ModelSerializer):
    major = MajorSerializer()
    
    class Meta:
        model = Course
        fields = ['id', 'name', 'code', 'major']

class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = ['id', 'name']

class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = ['id', 'rating', 'num_of_ratings']

class TutorSerializer(serializers.ModelSerializer):
    taught_courses = CourseSerializer(many=True, read_only=True)
    languages = LanguageSerializer(many=True, read_only=True)
    user = UserSerializer(read_only=True)
    rating =serializers.SerializerMethodField()

    class Meta:
        model = Tutor
        fields = ['id', 'user', 'description', 'taught_courses', 'rate', 'languages', 'rating']

    def get_rating(self, obj):
        try:
            rating = Rating.objects.get(tutor=obj)
            return RatingSerializer(rating).data
        except Rating.DoesNotExist:
            return None
        

# Booking Serializers    
class BookingSerializer(serializers.ModelSerializer):
    hour = serializers.IntegerField(write_only=True)
    day = serializers.IntegerField(write_only=True)
    month = serializers.IntegerField(write_only=True)
    start_time = serializers.SerializerMethodField()
    user_details = serializers.SerializerMethodField()
    course_details = serializers.SerializerMethodField()


    class Meta:
        model = Booking
        fields = ['id', 'hour', 'user_details', 'course_details', 'day', 'month', 'start_time']

    def get_user_details(self, obj):
        include_user_details = self.context.get('include_user_details', False)
        if include_user_details and obj.user:
            return UserSerializer(obj.user).data
        return None
    
    def get_course_details(self, obj):
        if obj.course:
            return CourseSerializer(obj.course).data
        return None

    def get_start_time(self, obj):
        return obj.start_time

    def validate(self, data):
        current_year = timezone.now().year
        current_month = timezone.now().month
        hour = data.get('hour')
        day = data.get('day')
        month = data.get('month')

        if current_month == 12 and month == 1:
            current_year += 1

        # Create the start_time
        try:
            start_time = datetime(year=current_year, month=month, day=day, hour=hour)
        except ValueError as e:
            raise serializers.ValidationError(f"Invalid date or time: {e}")

        start_time = timezone.make_aware(start_time, timezone.get_current_timezone())


        # Check if start_time is in the past
        if start_time < timezone.now():
            raise serializers.ValidationError("Booking time cannot be in the past")

        tutor = self.context['request'].user.tutorInfo.first()

        if Booking.objects.filter(tutor=tutor, start_time=start_time).exists():
            raise serializers.ValidationError("This time slot is already created.")

        data['start_time'] = start_time
        return data

    def create(self, validated_data):
        hour = validated_data.pop('hour')
        day = validated_data.pop('day')
        month = validated_data.pop('month')

        tutor = self.context['request'].user.tutorInfo.first()
        start_time = validated_data['start_time']

        return Booking.objects.create(tutor=tutor, start_time=start_time)

    
class CreateBookingSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()
    course_id = serializers.IntegerField()

    def validate_booking_id(self, value):
        try:
            booking = Booking.objects.get(id=value)
        except Booking.DoesNotExist:
            raise serializers.ValidationError("Booking slot does not exist.")


        if booking.user is not None:
            raise serializers.ValidationError("Booking slot is already booked.")
        
        user = self.context['request'].user
        overlapping_bookings = Booking.objects.filter(user=user, start_time=booking.start_time)
        if overlapping_bookings.exists():
            raise serializers.ValidationError("You already have a booking at this time.")
        
        return booking
    
    def validate_course_id(self,value):
        try:
            course = Course.objects.get(id=value)
        except Course.DoesNotExist:
            raise serializers.ValidationError("Course id provided is not found")
        return course

# Settings Serializers
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    confirm_password = serializers.CharField(required=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("The new passwords do not match.")
        return data

class PendingSerializer(serializers.ModelSerializer):
    booking = BookingSerializer()
    course = CourseSerializer() 

    class Meta:
        model = Pending
        fields = ['id', 'booking', 'course']
