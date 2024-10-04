from datetime import timedelta
from .models import Tutor, Subscription
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Tutor
from rest_framework.response import Response

@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def activate_tutor_free_trial(request):
    try:
        tutor = request.user.tutorInfo.first()
    except:
        return Response({"error": "This user is not registered as a tutor."}, status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)
    
    if tutor.freeTrialActivated:
        return Response({"error": "The free trial has already been claimed on this account."}, status=status.HTTP_400_BAD_REQUEST)

    start_date = timezone.now()
    end_date = start_date + timedelta(weeks=2)  # Set end date to 2 weeks from start date

    Subscription.objects.create(
        tutor=tutor,
        start_date=start_date,
        end_date=end_date
    )

    tutor.freeTrialActivated = True
    tutor.isActive = True
    tutor.save()

    return Response("Free trial successfully activated for two weeks.", status=status.HTTP_200_OK)

@api_view(['GET'])
def activate_tutor_account(request):
    tutor_id = request.query_params.get('tutor_id')
    subscription_period = request.query_params.get('duration')
    
    try:
        tutor = Tutor.objects.get(id=tutor_id)
    except Tutor.DoesNotExist:
        return Response({"error": "Tutor id is invalid."}, status=status.HTTP_400_BAD_REQUEST)

    start_date = timezone.now()
    days_to_extend = subscription_period * 30

    existing_subscription = Subscription.objects.filter(tutor=tutor).first()

    if existing_subscription:
        existing_subscription.end_date += timedelta(days=days_to_extend)
        existing_subscription.save()

        return Response(
            {"message": f"Tutor account renewed successfully for {days_to_extend} days."}, 
            status=status.HTTP_200_OK
        )
    else:
        end_date = start_date + timedelta(days=days_to_extend)

        Subscription.objects.create(
            tutor=tutor,
            start_date=start_date,
            end_date=end_date
        )

        return Response(
            {"message": f"Tutor account activated successfully for {days_to_extend} days."},
            status=status.HTTP_200_OK
        )

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def tutor_get_subscription_days(request):
    try:
        tutor = request.user.tutorInfo.first()
    except:
        return Response({"error": "The user is not a tutor."}, status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)
    
    subscription = tutor.subscription
    time_left = subscription.days_left()

    return Response({"days_left": f"{time_left}"}, status=status.HTTP_200_OK)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_tutor_activation_status(request):
    try:
        tutor = request.user.tutorInfo.first()
    except:
        return Response({"error": "The user is not a tutor."}, status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)
    
    return Response({"isAccountActivated": tutor.isActive, "isTrialActivated": tutor.freeTrialActivated}, status=status.HTTP_200_OK)
