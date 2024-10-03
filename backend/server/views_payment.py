from datetime import timedelta
from .models import Tutor, Subscription
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone

@api_view(['POST'])
def activate_tutor_account(request):
    tutor_id = request.query_params.get('tutor_id')
    subscription_period = request.query_params.get('duration')

    try:
        subscription_period = int(subscription_period)
    except (TypeError, ValueError):
        return Response({"error": "Duration must be a valid integer."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        tutor = Tutor.objects.get(id=tutor_id)
    except Tutor.DoesNotExist:
        return Response({"error": "Tutor id is invalid."}, status=status.HTTP_400_BAD_REQUEST)

    start_date = timezone.now()

    end_year = start_date.year + (start_date.month + subscription_period - 1) // 12
    end_month = (start_date.month + subscription_period - 1) % 12 + 1
    end_day = min(start_date.day, (timezone.datetime(end_year, end_month, 1) + timedelta(days=31)).replace(day=1).day - 1)

    try:
        end_date = start_date.replace(year=end_year, month=end_month, day=end_day)
    except ValueError:
        end_date = start_date.replace(year=end_year, month=end_month, day=1) + timedelta(days=-1)

    Subscription.objects.create(
        tutor=tutor,
        start_date=start_date,
        end_date=end_date
    )

    return Response({"message": "Tutor account activated successfully."}, status=status.HTTP_200_OK)

@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def tutor_get_subscription_days(request):
    try:
        tutor = request.user.tutorInfo.first()
    except:
        return Response({"error": "The user is not a tutor."}, status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)
    
    subscription = tutor.subscription
    time_left = subscription.days_left()

    return Response({"days_left": f"{time_left}"}, status=status.HTTP_200_OK)