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

@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def create_booking(request):
    serializer = BookingSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def book_session(request):
    serializer = CreateBookingSerializer(data=request.data, context={'request': request})

    try:
        booking = Booking.objects.get(id=request.data['booking_id'])
    except Booking.DoesNotExist:
        return Response("Error: The booking ID provided does not exist.", status=status.HTTP_400_BAD_REQUEST)

    try:
        course = Course.objects.get(id=request.data['course_id'])
    except Course.DoesNotExist:
        return Response("Error: The course ID provided does not exist.", status=status.HTTP_400_BAD_REQUEST)
    
    try:
        tutor = booking.tutor
    except Tutor.DoesNotExist:
        return Response("Error: There has been an error querying this booking's tutor.")

    if tutor.bannedProfiles.filter(id=request.user.id).exists():
        return Response(f"You are unable to book sessions with {tutor.user.first_name} {tutor.user.last_name} as you have been banned", status=status.HTTP_400_BAD_REQUEST)

    if serializer.is_valid():
        profile = request.user.profile

        if Pending.objects.filter(booking=booking, pending_profiles=profile).exists():
            return Response({'detail': 'This booking is already pending confirmation.'}, status=status.HTTP_400_BAD_REQUEST)
    
        pending = Pending.objects.create(booking=booking, course=course)
        tutor_pending, _ = TutorPending.objects.get_or_create(tutor=tutor)
        tutor_pending.pending_bookings.add(pending)
        profile.pending_bookings.add(pending)
        course_serializer = CourseSerializer(course)
        create_email_token(request.user, booking.tutor, course_serializer.data, booking.id, course.id)
        return Response({'detail': 'Request sent to the tutor. Please await an email confirmation for your booking.'}, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def create_email_token(user, tutor, course_data, booking_id, course_id):
    token = EmailConfirmationToken.objects.create(user=tutor.user)
    
    try: 
        booking = Booking.objects.get(id=booking_id)
    except:
        return Response(status = status.HTTP_400_BAD_REQUEST)

    start_time = booking.start_time
    formatted_time = f"{start_time.strftime('%B')} {start_time.day} at {start_time.strftime('%I').lstrip('0')} {start_time.strftime('%p')}"

    
    if user.profile.phone_number:
        phone_number = user.profile.phone_number
    else:
        phone_number = None

    send_confirmation_email(
        user_id = user.id,
        student_name=user.get_full_name(),
        student_email=user.email,
        tutor_email=tutor.user.email,
        course_data=course_data,
        token_id=token.pk,
        tutor_name=tutor.user.first_name + " " + tutor.user.last_name,
        booking_id = booking_id,
        course_id = course_id,
        session_time = formatted_time,
        phone_number = phone_number
    )

    return Response(data=None, status=status.HTTP_201_CREATED)

def send_confirmation_email(user_id, student_name, student_email, tutor_email, course_data, token_id, tutor_name, booking_id, course_id, session_time, phone_number):

    data = {
        'user_id': user_id,
        'token_id': str(token_id),
        'tutor_name': str(tutor_name),
        'student_name': student_name,
        'student_email': student_email,
        'course_name': course_data['name'],
        'booking_id': booking_id,
        'course_id': course_id,
        'session_time': session_time,
        'student_phone': phone_number
    }
    message = get_template('users/tutor_confirmation_email.txt').render(data)
    
    send_mail(
        subject='Booking Confirmation Request',
        message=message,
        recipient_list=[tutor_email],
        from_email="studytron@trial-0r83ql3dvxpgzw1j.mlsender.net",
        fail_silently=True
    )

@api_view(['GET'])
def confirm_booking(request):
    booking_id = request.query_params.get("booking_id")
    user_id = request.query_params.get("user_id")
    course_id = request.query_params.get("course_id")

    auth_header = request.headers.get('Authorization')
    
    if not auth_header:
        try:
            token_id = request.query_params.get("token_id")
            token = EmailConfirmationToken.objects.get(pk=token_id)
            tutor = token.user.tutorInfo.first()
        except: 
            return Response("No authentication or email token were provided.", status = status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)
    else:
        tutor = request.user.tutorInfo.first()

    try:
        booking = Booking.objects.get(id=booking_id)
        user = User.objects.get(id=user_id)
        course = Course.objects.get(id=course_id)
    except Booking.DoesNotExist:
        return Response("Booking not found.", status=status.HTTP_404_NOT_FOUND)
    except User.DoesNotExist:
        return Response("User not found.", status=status.HTTP_404_NOT_FOUND)
    except Course.DoesNotExist:
        return Response("Course not found", status = status.HTTP_404_NOT_FOUND)

    if booking.tutor != tutor:
        return Response("The provided token did not match the booking's tutor.",status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)

    user_pending = user.profile.pending_bookings.filter(booking=booking)
    if not user_pending.exists():
        return render(request, template_name='users/error_confirming_booking.html')    
    
    booking.user = user
    booking.course = course
    booking.save()

    pending_instances = Pending.objects.filter(booking=booking).exclude(id=user_pending.first().id)
    send_pending_cancellation_emails(request, pending_bookings=pending_instances, booking=booking)
    all_pending_instances = Pending.objects.filter(booking=booking)
    all_pending_instances.delete()

    start_time = booking.start_time.astimezone(timezone.get_current_timezone())
    formatted_time = f"{start_time.strftime('%B')} {start_time.day} at {start_time.strftime('%I').lstrip('0')} {start_time.strftime('%p')}"

    username = f"{user.first_name} {user.last_name}"
    tutor_name = f"{tutor.user.first_name} {tutor.user.last_name}"
    tutor_email = tutor.user.email
    tutor_phone_number = tutor.user.profile.phone_number

    data = {
        'tutor_name': tutor_name,
        'user_name': username,
        'session_time': formatted_time,
        'course': course.name,
        'tutor_email': tutor_email,
        'tutor_phone_number': tutor_phone_number
    }

    message = get_template('users/user_booking_confirmation_email.txt').render(data)

    send_mail(
        subject='Booking Confirmation',
        message=message,
        from_email="studytron@trial-0r83ql3dvxpgzw1j.mlsender.net",
        recipient_list=[user.email],
        fail_silently=True
    )

    context = {
        'user_name': username,
        'session_time': formatted_time
    }

    if auth_header:
        return Response({"success": "Booking confirmed successfully."})
    
    return render(request, template_name='users/confirm_booking.html', context=context)

#get functions
@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_hours(request):
    booked_only = request.query_params.get("booked_only", None)
    tutor_id = request.query_params.get("tutor_id")
    try:
        tutor = Tutor.objects.get(id=tutor_id)
    except Tutor.DoesNotExist:
        return Response({'detail': 'Tutor not found'}, status=status.HTTP_404_NOT_FOUND)

    now = timezone.now()
    one_month_later = now + timezone.timedelta(days=30)

    if booked_only is not None:
        if booked_only.lower() == 'true':
            bookings = Booking.objects.filter(tutor=tutor, start_time__range=(now, one_month_later), user__isnull=False)
        elif booked_only.lower() == 'false':
            bookings = Booking.objects.filter(tutor=tutor, start_time__range=(now, one_month_later), user__isnull=True)
        else:
            return Response("Invalid value for 'booked_only'. Expected 'true' or 'false'.", status=status.HTTP_400_BAD_REQUEST)
    else:
        bookings = Booking.objects.filter(tutor=tutor, start_time__range=(now, one_month_later))


    grouped_bookings = defaultdict(lambda: defaultdict(list))
    for booking in bookings:
        month = booking.start_time.month
        day = booking.start_time.day
        grouped_bookings[month][day].append(booking)

    # Serialize the grouped bookings
    response_data = []
    for month, days in grouped_bookings.items():
        month_data = {'month': month, 'days': {}}
        for day, bookings in days.items():
            month_data['days'][day] = BookingSerializer(bookings, many=True).data
        response_data.append(month_data)

    return Response(response_data, status=status.HTTP_200_OK)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def tutor_get_hours(request):
    booked_only = request.query_params.get('booked_only', None)
    include_user_details = True

    try:
        tutor = Tutor.objects.get(user = request.user)
    except:
        return Response("Error! This api was called by a user and not a tutor", status=status.HTTP_403_FORBIDDEN)
    
    now = timezone.now().date()
    next_30_days = now + timezone.timedelta(days=30)

    if booked_only is not None:
        if booked_only.lower() == 'true':
            bookings = Booking.objects.filter(tutor=tutor, user__isnull=False, start_time__range=[now, next_30_days])
        elif booked_only.lower() == 'false':
            bookings = Booking.objects.filter(tutor=tutor, user__isnull=True, start_time__range=[now, next_30_days])
        else:
            return Response("Invalid value for 'booked_only'. Expected 'true' or 'false'.", status=status.HTTP_400_BAD_REQUEST)
    else:
        bookings = Booking.objects.filter(tutor=tutor, start_time__range=[now, next_30_days])
    
    grouped_bookings = defaultdict(lambda: defaultdict(list))
    for booking in bookings:
        month = booking.start_time.month
        day = booking.start_time.day
        grouped_bookings[month][day].append(booking)

    # Serialize the grouped bookings
    response_data = []
    for month, days in grouped_bookings.items():
        month_data = {'month': month, 'days': {}}
        for day, bookings in days.items():
            month_data['days'][day] = BookingSerializer(bookings, many=True, context={'include_user_details': include_user_details}).data
        response_data.append(month_data)

    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_my_bookings(request):
    now = timezone.now()
    one_month_later = now + timezone.timedelta(days=30)
    bookings = Booking.objects.filter(user=request.user, start_time__range=(now, one_month_later))
    grouped_bookings = defaultdict(lambda: defaultdict(list))
    for booking in bookings:
        month = booking.start_time.month
        day = booking.start_time.day
        booking_data = BookingSerializer(booking).data
        tutor_data = UserSerializer(booking.tutor.user).data
        tutor_data['rate'] = booking.tutor.rate
        booking_data['tutor_details'] = tutor_data
        grouped_bookings[month][day].append(booking_data)

    response_data = []
    for month, days in grouped_bookings.items():
        month_data = {'month': month, 'days': {}}
        for day, bookings in days.items():
            month_data['days'][day] = bookings
        response_data.append(month_data)

    return Response(response_data, status=status.HTTP_200_OK)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def tutor_get_full_days(request):
    include_user_details = True
    try:
        tutor = request.user.tutorInfo.first()
    except:
        return Response("Forbidden! The user is not a tutor.", status= status.HTTP_403_FORBIDDEN)

    now = timezone.now()
    one_month_later = now + timezone.timedelta(days=30)

    bookings = Booking.objects.filter(tutor=tutor, start_time__range=(now, one_month_later))

    grouped_bookings = defaultdict(list)
    for booking in bookings:
        day = booking.start_time.date()
        grouped_bookings[day].append(booking)

    fully_booked_days = []
    for day, day_bookings in grouped_bookings.items():
        if all(booking.user is not None for booking in day_bookings):
            fully_booked_days.append({
                'day': day,
                'bookings': BookingSerializer(day_bookings, many=True, context={"include_user_details": include_user_details}).data
            })

    fully_booked_days.sort(key=lambda x: x['day'])

    return Response(fully_booked_days, status=status.HTTP_200_OK)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def tutor_get_days(request):
    try:
        tutor = request.user.tutorInfo.first()
    except Tutor.DoesNotExist:
        return Response({'detail': 'Forbidden Access. The user is not a tutor.'}, status=status.HTTP_403_FORBIDDEN)

    now = timezone.now()
    one_month_later = now + timezone.timedelta(days=30)

    bookings = Booking.objects.filter(tutor=tutor, start_time__range=(now, one_month_later))

    grouped_bookings = defaultdict(list)
    for booking in bookings:
        day = booking.start_time.date()
        grouped_bookings[day].append(booking)

    days_availability = []
    for day, day_bookings in grouped_bookings.items():
        any_booked = any(booking.user is not None for booking in day_bookings)
        all_booked = all(booking.user is not None for booking in day_bookings)
        
        if any_booked:
            fully_booked = all_booked
            days_availability.append({
                'date': day,
                'fully_booked': fully_booked
            })

    days_availability.sort(key=lambda x: x['date'])

    return Response(days_availability, status=status.HTTP_200_OK)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def user_get_days(request):
    try:
        tutor = Tutor.objects.get(id=request.query_params.get("tutor_id"))
    except Tutor.DoesNotExist:
        return Response({'detail': 'Tutor not found'}, status=status.HTTP_404_NOT_FOUND)

    now = timezone.now()
    one_month_later = now + timezone.timedelta(days=30)

    bookings = Booking.objects.filter(tutor=tutor, start_time__range=(now, one_month_later))

    grouped_bookings = defaultdict(list)
    for booking in bookings:
        day = booking.start_time.date()
        grouped_bookings[day].append(booking)

    days_availability = []
    for day, day_bookings in grouped_bookings.items():
        all_booked = all(booking.user is not None for booking in day_bookings)
        days_availability.append({
            'date': day,
            'fully_booked': all_booked
        })

    days_availability.sort(key=lambda x: x['date'], reverse=True)

    return Response(days_availability, status=status.HTTP_200_OK)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def user_get_booked_days(request):
    bookings = Booking.objects.filter(user = request.user)

    grouped_bookings = defaultdict(list)
    for booking in bookings:
        day = booking.start_time.date()
        grouped_bookings[day].append(booking)

    booking_days = list(grouped_bookings.keys())
    booking_days.sort(reverse=True)

    return Response(booking_days, status=status.HTTP_200_OK)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def user_get_pending_bookings(request):
    try:

        now = timezone.now()
        one_month_later = now + timezone.timedelta(days=30)

        pending_requests = request.user.profile.pending_bookings.order_by('booking__start_time')
        pending_requests.filter(booking__start_time__range=(now, one_month_later))

        if not pending_requests.exists():
            return Response("You don't have any current pending requests.", status=status.HTTP_204_NO_CONTENT)

        response_data = []

        for pending in pending_requests:
            pending_data = PendingSerializer(pending).data

            tutor = pending.booking.tutor
            tutor_data = UserSerializer(tutor.user).data
            tutor_data['rate'] = tutor.rate

            pending_data.update({
                'tutor_details': tutor_data
            })

            response_data.append(pending_data)

        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def user_get_pending_days(request):
    pendings = request.user.profile.pending_bookings.all()

    grouped_bookings = defaultdict(list)
    for pending in pendings:
        day = pending.booking.start_time.date()
        grouped_bookings[day].append(pending)

    booking_days = list(grouped_bookings.keys())
    booking_days.sort(reverse=True)

    return Response(booking_days, status=status.HTTP_200_OK)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def tutor_get_pending_days(request):
    tutor_pending = TutorPending.objects.get(tutor = request.user.tutorInfo.first())
    pendings = tutor_pending.pending_bookings.all()

    grouped_bookings = defaultdict(list)
    for pending in pendings:
        day = pending.booking.start_time.date()
        grouped_bookings[day].append(pending)

    booking_days = list(grouped_bookings.keys())
    booking_days.sort(reverse=True)

    return Response(booking_days, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def tutor_get_pending_bookings(request):
    try:
        tutor = request.user.tutorInfo.first()
        if not tutor:
            return Response({'detail': 'Tutor not found.'}, status=status.HTTP_404_NOT_FOUND)
    except Tutor.DoesNotExist:
        return Response({'detail': 'Tutor information not found.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        tutor_pending = TutorPending.objects.get(tutor=tutor)
    except TutorPending.DoesNotExist:
        return Response({'detail': 'No pending bookings found for this tutor.'}, status=status.HTTP_404_NOT_FOUND)


    now = timezone.now()
    one_month_later = now + timezone.timedelta(days=30)

    tutor_pending_bookings = tutor_pending.pending_bookings.all().order_by('booking__start_time')
    tutor_pending_bookings.filter(booking__start_time__range=(now, one_month_later))

    response_data = []

    for pending in tutor_pending_bookings:
        pending_data = PendingSerializer(pending).data

        for profile in pending.pending_profiles.all():
            user = profile.user
            user_data = UserSerializer(user).data

            pending_data.update({
                'user_details': user_data
            })

        response_data.append(pending_data)

    return Response(response_data, status=status.HTTP_200_OK)

#deletion functions:

@api_view(['DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def cancel_my_booking(request):
    given_id = request.query_params.get("booking_id")

    try:
        general_booking = Booking.objects.get(pk=given_id)
    except Booking.DoesNotExist:
        return Response("This booking slot does not exist.", status=status.HTTP_400_BAD_REQUEST)

    profile = request.user.profile

    pending_request = profile.pending_bookings.filter(booking=general_booking).first()
    if pending_request:
        pending_request.delete()
        return Response("Your pending request for this booking has been successfully cancelled.", status=status.HTTP_204_NO_CONTENT)

    if general_booking.user:
        if general_booking.user != request.user:
            return Response("This slot has already been cancelled or the booking wasn't accepted initially.", status=status.HTTP_400_BAD_REQUEST)
        
        user_name = f"{general_booking.user.first_name} {general_booking.user.last_name}"
        course_name = general_booking.course.name
        general_booking.user = None
        general_booking.course = None
        general_booking.save()

        # sending email to tutor
        tutor = general_booking.tutor
        tutor_name = f"{tutor.user.first_name} {tutor.user.last_name}"
        tutor_email = tutor.user.email
        start_time = general_booking.start_time.astimezone(timezone.get_current_timezone())
        formatted_time = f"{start_time.strftime('%B')} {start_time.day} at {start_time.strftime('%I').lstrip('0')} {start_time.strftime('%p')}"


        data = {
            'tutor_name': tutor_name,
            'user_name': user_name,
            'session_time': formatted_time,
            'course_name': course_name,
            'tutor_email': tutor_email,
        }

        message = get_template('users/user_cancelled_booking.txt').render(data)

        send_mail(
            subject='Booking Cancellation Notification',
            message=message,
            from_email="studytron@trial-0r83ql3dvxpgzw1j.mlsender.net",
            recipient_list=[tutor_email],
            fail_silently=True
        )

        return Response("Your booking has been cancelled successfully.", status=status.HTTP_204_NO_CONTENT)

    return Response("Error: Can't cancel this booking. Not pending nor confirmed by the user.", status=status.HTTP_400_BAD_REQUEST)

#this method is for the user to cancel the booking

@api_view(['DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def tutor_cancel_booking(request):
    given_id = request.query_params.get("booking_id")

    try:
        booking = Booking.objects.get(tutor=request.user.tutorInfo.first(), pk=given_id)
    except Booking.DoesNotExist:
        return Response("This slot has already been deleted or wasn't created initially.", status=status.HTTP_400_BAD_REQUEST)

    if booking.user is None:
        pending_requests = Pending.objects.filter(booking=booking)
        if pending_requests.exists():
            send_pending_cancellation_emails(request, pending_bookings=pending_requests, booking=booking)
            pending_requests.delete()
            return Response("The pending request for this slot has been deleted.", status=status.HTTP_204_NO_CONTENT)
        return Response("Booking is already cancelled or was never booked.", status=status.HTTP_400_BAD_REQUEST)
    
    # If the booking has a user, cancel the booking and remove the user
    name = f"{booking.user.first_name} {booking.user.last_name}"
    # sending cancellation email
    send_booking_cancellation_email(request, booking)
    booking.user = None
    booking.course = None
    booking.save()

    return Response(f"Your booking with user {name} has been cancelled successfully.", status=status.HTTP_204_NO_CONTENT)

@api_view(['DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def tutor_delete_slot(request):
    given_id = request.query_params.get("booking_id")
    
    try: 
        booking = Booking.objects.get(id=given_id)
    except Booking.DoesNotExist:
        return Response("This slot has already been deleted or wasn't created initially.", status=status.HTTP_400_BAD_REQUEST)

    pending_bookings = Pending.objects.filter(booking=booking)
    
    start_time = booking.start_time
    formatted_time = f"{start_time.strftime('%B')} {start_time.day} at {start_time.strftime('%I').lstrip('0')} {start_time.strftime('%p')}"


    if pending_bookings.exists():
        send_pending_cancellation_emails(request, pending_bookings, booking)
        cancellation_message = f"Your pending requests scheduled for {booking.start_time.strftime('%Y-%m-%d %H')} have been cancelled, and the booking slot has been removed."
        pending_bookings.delete()

    

    elif booking.user:
        send_booking_cancellation_email(request, booking)
        cancellation_message = f"Your reserved booking at {formatted_time} with {booking.user.first_name} {booking.user.last_name} has been cancelled, and the booking slot has been removed."
    else:
        cancellation_message = f"Your booking slot at {formatted_time} has been deleted."

    booking.delete()

    return Response(cancellation_message, status=status.HTTP_204_NO_CONTENT)

#send cancellation emails to confirmed booking users
def send_booking_cancellation_email(request, booking):
    tutor = booking.tutor
    user = booking.user

    user_name = f"{user.first_name} {user.last_name}"
    tutor_name = f"{tutor.user.first_name} {tutor.user.last_name}"
    tutor_email = tutor.user.email
    start_time = booking.start_time.astimezone(timezone.get_current_timezone())
    formatted_time = f"{start_time.strftime('%B')} {start_time.day} at {start_time.strftime('%I').lstrip('0')} {start_time.strftime('%p')}"

    course_name = booking.course.name

    data = {
        'tutor_name': tutor_name,
        'user_name': user_name,
        'session_time': formatted_time,
        'course_name': course_name,
    }

    message = get_template('users/tutor_cancelled_booking.txt').render(data)

    send_mail(
        subject='Booking Cancellation Notification',
        message=message,
        from_email="studytron@trial-0r83ql3dvxpgzw1j.mlsender.net",
        recipient_list=[tutor_email],
        fail_silently=True
    )

    return Response(status=status.HTTP_204_NO_CONTENT)

#sending cancellation emails for pending users
def send_pending_cancellation_emails(request, pending_bookings, booking):
    tutor = booking.tutor
    tutor_name = f"{tutor.user.first_name} {tutor.user.last_name}"
    start_time = booking.start_time.astimezone(timezone.get_current_timezone())
    formatted_time = f"{start_time.strftime('%B')} {start_time.day} at {start_time.strftime('%I').lstrip('0')} {start_time.strftime('%p')}"


    for pending in pending_bookings:
        user = pending.pending_profiles.first().user
        user_name = f"{user.first_name} {user.last_name}"
        course_name = pending.course.name

        data = {
            'tutor_name': tutor_name,
            'user_name': user_name,
            'session_time': formatted_time,
            'course_name': course_name,
        }

        message = get_template('users/tutor_cancelled_pending.txt').render(data)

        send_mail(
            subject='Cancellation of Your Pending Booking Request',
            message=message,
            from_email="studytron@trial-0r83ql3dvxpgzw1j.mlsender.net",
            recipient_list=[user.email],
            fail_silently=True
        )

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def tutor_check_booking_condition(request):
    booking_id = request.query_params.get("booking_id")
    
    try:
        booking = Booking.objects.get(pk=booking_id)
    except Booking.DoesNotExist:
        return Response("The booking ID provided is invalid or the booking does not exist.", status=status.HTTP_400_BAD_REQUEST)

    if booking.user:
        return Response({"booking":f"You have a confirmed booking with {booking.user.first_name} {booking.user.last_name}."}, status=status.HTTP_200_OK)
    
    pending_bookings = Pending.objects.filter(booking=booking)
    if pending_bookings.exists():
        return Response({"pending":"You have pending requests for this booking slot."}, status=status.HTTP_200_OK)
    
    return Response({"available":"This booking slot is available for new requests."}, status=status.HTTP_200_OK)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def tutor_get_slotted_days(request):
    try:
        tutor = request.user.tutorInfo.first()
    except:
        return Response("Unauthorized access, the user is not a tutor.", status=status.HTTP_403_FORBIDDEN)

    now = timezone.now()
    one_month_later = now + timezone.timedelta(days=30)

    slots = Booking.objects.filter(tutor=tutor).order_by('start_time')
    slots.filter(start_time__range=(now, one_month_later))

    grouped_slots = defaultdict(list)
    for slot in slots:
        day = slot.start_time.date()
        grouped_slots[day].append(slot)

    slotted_days = list(grouped_slots.keys())

    return Response(slotted_days, status=status.HTTP_200_OK)