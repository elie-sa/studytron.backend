from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication
from collections import defaultdict
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Booking, EmailConfirmationToken, Pending, Tutor, Course, User, TutorPending
from .serializers import BookingSerializer, CourseSerializer, CreateBookingSerializer, PendingSerializer, ProfileSerializer, UserSerializer, TutorSerializer
from django.shortcuts import get_object_or_404, render
from .models import Tutor, EmailConfirmationToken
from .serializers import UserSerializer
from django.core.mail import send_mail
from django.template.loader import get_template


@api_view(['GET'])
def test_success_view(request):
    return Response({"message": "GET success endpoint called"}, status=status.HTTP_200_OK)

@api_view(['GET'])
def test_failure_view(request):
    return Response({"message": "GET failure endpoint called"}, status=status.HTTP_400_BAD_REQUEST)