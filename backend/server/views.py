import re
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils import timezone
from django.http import Http404
from rest_framework.response import Response
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User, Group
from django.shortcuts import render
from . import views_scheduling
from .models import Booking, Course, FileUpload, Language, Major, Rating, Tutor, EmailConfirmationToken, TutorPending
from django.db.models import Q, Count
from .serializers import ChangePasswordSerializer, FileUploadSerializer, LanguageSerializer, MajorSerializer, PasswordChangeSerializer, UserSerializer, TutorSerializer
from django.core.mail import send_mail
from django.template.loader import get_template
import pyotp
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.paginator import Paginator
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.response import Response
from .serializers import CookieTokenRefreshSerializer

# authentication apis

@api_view(['POST'])
def signup(request):
    serializer = UserSerializer(data=request.data)
    email = request.data.get('email')
    username = request.data.get('username')

    if username and User.objects.filter(username=username).exists():
        return Response({'username': 'Username already exists.'}, status=status.HTTP_400_BAD_REQUEST)
    
    if email and User.objects.filter(email=email).exists():
        return Response({'email': 'The email address is already in use.'}, status=status.HTTP_400_BAD_REQUEST)

    if serializer.is_valid():
        user = serializer.save()
        password = request.data.get('password')
        if password:
            user.set_password(password)
        user.save()

        if request.data.get('is_tutor', False):
            tutorGroup = Group.objects.get(name='tutors')
            user.groups.add(tutorGroup)

            description = request.data.get('description', '')
            taught_courses = request.data.get('taughtCourses', [])
            rate = request.data.get('rate', 0)
            languages = request.data.get('languages', [])

            try:
                create_tutor(user, description, rate, taught_courses, languages)
            except ValueError as e:
                user.delete()
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        email_token = EmailConfirmationToken.objects.create(user=user)
        send_confirmation_email(email=user.email, token_id=email_token.pk, user_id=user.pk, access_token=access_token)

        response = Response({
            'access': access_token,
            'user': serializer.data
        }, status=status.HTTP_201_CREATED)

        cookie_max_age = 3600 * 24 * 7  # 7
        response.set_cookie(
            'refresh_token',
            str(refresh),
            max_age=cookie_max_age,
            httponly=True,
            secure=True 
        )

        return response

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def login(request):
    login_credential = request.data["login_credential"].strip()

    email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

    if re.match(email_pattern, login_credential):
        login_kind = "email"
        try:
            user = User.objects.get(email__iexact=login_credential)
        except:
            return Response(f"Invalid {login_kind} or password.", status=status.HTTP_400_BAD_REQUEST)
    else:
        login_kind = "email"
        try:
            user = User.objects.get(username=login_credential)
        except:
            return Response(f"Invalid {login_kind} or password.", status=status.HTTP_400_BAD_REQUEST)
        
    if not user.profile.is_confirmed:
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        return Response({
            "message": "Invalid login credentials. Email Verification is needed.",
            'access': access_token,
            'refresh': str(refresh),
            }, status=status.HTTP_403_FORBIDDEN)
    

    if not user.check_password(request.data['password']):
        return Response(f"Invalid {login_kind} or password.", status=status.HTTP_400_BAD_REQUEST)
    
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)

    serializer = UserSerializer(user)

    response = Response({
        'access': access_token,
        'user': serializer.data
    })

    cookie_max_age = 3600 * 24 * 7  # 7 days
    response.set_cookie(
        'refresh_token',
        str(refresh),
        max_age=cookie_max_age,
        httponly=True,
        secure=True
    )

    return response

@api_view(['POST'])
def logout(request):
    response = Response({"message": "Logout successful"}, status=status.HTTP_200_OK)
    response.delete_cookie('refresh_token')
    return response

class CookieTokenRefreshView(TokenRefreshView):
    serializer_class = CookieTokenRefreshSerializer

    def finalize_response(self, request, response, *args, **kwargs):
        if response.data.get('refresh'):
            cookie_max_age = 3600 * 24 * 7  # 14 days
            response.set_cookie('refresh_token', response.data['refresh'], max_age=cookie_max_age, httponly=True)
            del response.data['refresh']
        
        return super().finalize_response(request, response, *args, **kwargs)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def test_token(request):
    return Response("passed for {}".format(request.user.email))

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_user_info(request):
    user = request.user
    if is_tutor(user):
        tutor = Tutor.objects.get(user = user)
        serializer = TutorSerializer(tutor)
    else:
        serializer = UserSerializer(user)
    return Response(serializer.data)

@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def create_email_token(request):
    user = request.user
    token = EmailConfirmationToken.objects.create(user=user)

    access_token = request.headers.get('Authorization').split(' ')[1] if request.headers.get('Authorization') else None
    send_confirmation_email(email=user.email, token_id=token.pk, user_id=user.pk, access_token=access_token)
    return Response(data=None, status=status.HTTP_201_CREATED)

def send_confirmation_email(email, token_id, user_id, access_token):
    data = {
        'token_id': str(token_id),
        'user_id': str(user_id),
        'auth_token': access_token
    }
    message = get_template('users/confirmation_email.txt').render(data)
    send_mail(
        subject='Please confirm your email',
        message=message,
        recipient_list=[email],
        from_email="studytron@trial-0r83ql3dvxpgzw1j.mlsender.net",
        fail_silently=True
    )
    
def confirm_email_view(request):
    token_id = request.GET.get('token_id', None)
    auth_token = request.GET.get('auth_token', None) 

    try:
        token = EmailConfirmationToken.objects.get(pk=token_id)
        user = token.user
        user.save()
        profile = user.profile
        profile.is_confirmed = True
        profile.save()
        token.delete()
        
        data = {'is_email_confirmed': True, 'token': auth_token}
        return render(request, template_name='users/confirm_email_view.html', context=data)    
    except EmailConfirmationToken.DoesNotExist:
        data = {'is_email_confirmed': False, 'token': auth_token}
        return render(request, template_name='users/confirm_email_view.html', context=data)

@api_view(['POST'])
def check_email(request):
    try:
        email = request.data['email']
    except: 
        return Response("Error in JSON body, please include an email.", status=status.HTTP_400_BAD_REQUEST)
    
    user = User.objects.filter(email=email).first()
    if user:
        send_otp(user)
        return Response("Success! The email address you provided has been found.", status=status.HTTP_200_OK)
    else:
        return Response("Error: The email address you entered could not be found.", status=status.HTTP_400_BAD_REQUEST)


def send_otp(user):
    user.profile.generate_secret_key()
    totp = pyotp.TOTP(user.profile.secret_key, interval=60)
    otp = totp.now()
    
    # Send the OTP via email
    send_mail(
        'Your OTP Code',
        f'Your OTP code is {otp}. It is valid for the next minute.',
        "studytron@trial-0r83ql3dvxpgzw1j.mlsender.net",
        [user.email],
        fail_silently=False,
    )

@api_view(['POST'])
def verify_otp(request):
    try:
        email = request.data['email']
        otp = request.data['otp']
    except KeyError:
        return Response("Error in JSON body, please include both email and otp.", status=status.HTTP_400_BAD_REQUEST)
    
    user = User.objects.filter(email=email).first()
    if user and user.profile.secret_key:
        if verify_otp_service(user.profile.secret_key, otp):
            return Response("OTP is valid.", status=status.HTTP_200_OK)
        else:
            return Response("Invalid OTP or OTP expired.", status=status.HTTP_400_BAD_REQUEST)
    else:
        return Response("User not found or secret key missing.", status=status.HTTP_400_BAD_REQUEST)

def verify_otp_service(user_secret_key, otp):
    totp = pyotp.TOTP(user_secret_key, interval=60)
    return totp.verify(otp)

@api_view(['POST'])
def change_forgotten_password(request):
    serializer = PasswordChangeSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        new_password = serializer.validated_data['new_password']
        
        user = User.objects.filter(email=email).first()
        if user:
            user.set_password(new_password)
            user.save()
            return Response("Password has been successfully changed.", status=status.HTTP_200_OK)
        else:
            return Response("User not found.", status=status.HTTP_400_BAD_REQUEST)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def is_tutor(user):
    return user.groups.filter(name='tutors').exists()


def create_tutor(provided_user: User, description='', rate=0, taught_course_ids=None, language_ids=None):
    
        if taught_course_ids is None:
            taught_course_ids = []
        if language_ids is None:
            language_ids = []

        if not language_ids:
            raise ValueError("Error: At least one language must be provided.")

        tutor = Tutor.objects.create(
            user=provided_user,
            description=description,
            rate=rate
        )

        TutorPending.objects.create(tutor = tutor)
        Rating.objects.create(tutor=tutor)

        if taught_course_ids:
            taught_courses = Course.objects.filter(id__in=taught_course_ids)
            tutor.taught_courses.add(*taught_courses)

        languages = Language.objects.filter(id__in=language_ids)
        tutor.languages.add(*languages)

        return tutor


# main pages get apis
# no authentication required

@api_view(['GET'])
def list_majors(request):
    if request.method == 'GET':
        majors = Major.objects.all().order_by('name')
        major_data = []
        for major in majors:
            num_courses = major.courses.count()
            serializer = MajorSerializer(major)
            major_info = serializer.data
            major_info['num_courses'] = num_courses
            major_data.append(major_info)
        return Response(major_data)
    
@api_view(['GET'])
def list_courses(request):
    major_id = request.query_params.get('major_id', None)
    search_entry = request.query_params.get('search_entry', None)
    page_number = request.query_params.get('page', 1)
    items_per_page = 9 

    query = Q()
    if major_id:
        query &= Q(major_id=major_id)
    if search_entry:
        query &= Q(name__icontains=search_entry)
    
    courses = Course.objects.filter(query).annotate(num_tutors=Count('courseTutors')).filter(num_tutors__gt=0).order_by('name')

    paginator = Paginator(courses, items_per_page)
    page_obj = paginator.get_page(page_number)

    course_data = []
    for course in page_obj:
        major_name = course.major.name
        course_code = f"{course.major.code}{course.code}"
        num_tutors = Tutor.objects.filter(taught_courses=course).count()

        course_info = {
            "id": course.id,
            "name": course.name,
            "major": major_name,
            "code": course_code,
            "num_tutors": num_tutors
        }
        course_data.append(course_info)

    pagination_info = {
        "hasNext": page_obj.has_next(),
        "hasPrev": page_obj.has_previous(),
        "totalPages": paginator.num_pages,
        "currentPage": page_obj.number
    }

    return Response({
        "courses": course_data,
        "pagination": pagination_info
    })

@api_view(['GET'])
def list_all_courses(request):
    major_id = request.query_params.get('major_id', None)
    search_entry = request.query_params.get('search_entry', None)

    query = Q()
    if major_id:
        query &= Q(major_id=major_id)
    if search_entry:
        query &= Q(name__icontains=search_entry)
    
    courses = Course.objects.filter(query).order_by('name')

    course_data = []
    for course in courses:
        major_name = course.major.name
        course_code = f"{course.major.code}{course.code}"
        num_tutors = Tutor.objects.filter(taught_courses=course).count()

        course_info = {
            "id": course.id,
            "name": course.name,
            "major": major_name,
            "code": course_code,
            "num_tutors": num_tutors
        }
        course_data.append(course_info)

    return Response(course_data)
    
@api_view(['GET'])
def list_tutors(request):
    user = None
    tutor_to_exclude = None
    auth_header = request.headers.get('Authorization')
    
    if auth_header:
        jwt_auth = JWTAuthentication()
        try:
            user, _ = jwt_auth.authenticate(request)
            tutor_to_exclude = user.tutorInfo.first() if hasattr(user, 'tutorInfo') else None
        except Exception:
            user = None

    course_id = request.query_params.get('course_id')
    language = request.query_params.get('language_id')
    search_entry = request.query_params.get('search_entry')
    rate = request.query_params.get('rate')
    rating = request.query_params.get('rating')
    page_number = request.query_params.get('page', 1) 
    items_per_page = 10

    query = Q()
    if course_id:
        query &= Q(taught_courses__id=course_id)
    if search_entry:
        search_entry = search_entry.strip()
        search_terms = search_entry.split()
        
        if len(search_terms) >= 2:
            first_name_part = search_terms[0]
            last_name_part = " ".join(search_terms[1:]) 
            query &= (Q(user__first_name__icontains=first_name_part) & Q(user__last_name__icontains=last_name_part)) | \
                     (Q(user__first_name__icontains=last_name_part) & Q(user__last_name__icontains=first_name_part))
        else:
            query &= Q(user__first_name__icontains=search_entry) | Q(user__last_name__icontains=search_entry)
    if language:
        query &= Q(languages__id=language)
    if rate:
        query &= Q(rate__lt=float(rate) + 1)
    if rating:
        query &= Q(rating__rating__gte=float(rating))
    if tutor_to_exclude:
        query &= ~Q(id=tutor_to_exclude.id)

    tutors = Tutor.objects.filter(query).annotate(
        num_courses=Count("taught_courses")
    ).filter(num_courses__gt=0).order_by('user__first_name', 'user__last_name')

    paginator = Paginator(tutors, items_per_page)
    page_obj = paginator.get_page(page_number)

    serializer = TutorSerializer(page_obj, many=True)

    pagination_info = {
        "hasNext": page_obj.has_next(),
        "hasPrev": page_obj.has_previous(),
        "totalPages": paginator.num_pages,
        "currentPage": page_obj.number
    }

    return Response({
        "tutors": serializer.data,
        "pagination": pagination_info
    })
    
@api_view(['GET'])
def list_languages(request):
    search_entry = request.query_params.get('search_entry')

    if search_entry:
        languages = Language.objects.filter(name__icontains=search_entry).order_by('name')
    else:
        languages = Language.objects.all().order_by('name')
    serializer = LanguageSerializer(languages, many = True)
    return Response(serializer.data)
    
@api_view(['GET'])
def get_major(request, major_id):
    try:
        major = Major.objects.get(pk = major_id)
    except:
        raise Http404("Major does not exist")
    serializer = MajorSerializer(major)
    return Response(serializer.data)

@api_view(['GET'])
def get_course(request, course_id):
    try:
        course = Course.objects.get(pk = course_id)
    except:
        raise Http404("Course does not exist")
    num_tutors = Tutor.objects.filter(taught_courses=course).count()
    course_code = f"{course.major.code}{course.code}"
    return Response({"name": course.name, "major": course.major.name, "code": course_code, "num_tutors": num_tutors})


@api_view(['GET'])
def get_language(request, language_id):
    try:
        language = Language.objects.get(pk = language_id)
    except:
        raise Http404("Language not found")
    serializer = LanguageSerializer(language)
    return Response(serializer.data)

# settings page

# changing user attributes
@api_view(['PUT'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def change_user_name(request):
    user = request.user
    first_name = request.query_params.get('first_name', None)
    last_name = request.query_params.get('last_name', None)

    if first_name:
        user.first_name = first_name
    if last_name:
        user.last_name = last_name
    user.save() 
    
    response_data = {
        "message": "User name updated successfully",
        "user": {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "email": user.email,
        }
    }
    
    return Response(response_data, status=status.HTTP_200_OK)

# changing password
@api_view(['PUT'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def change_password(request):
    user = request.user
    serializer = ChangePasswordSerializer(data=request.data)

    if serializer.is_valid():
        old_password = serializer.validated_data['old_password']
        if not user.check_password(old_password):
            return Response({"old_password": "Old password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)
        
        new_password = serializer.validated_data['new_password']
        user.set_password(new_password)
        user.save()

        return Response({"message": "Password updated successfully"}, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# changing tutor description
@api_view(['PUT'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def tutor_change_description(request):
    user = request.user
    if is_tutor(user):
        tutor = Tutor.objects.get(user = user)
        description = request.data['description']
        tutor.description = description
        tutor.save()
    else:
        return Response({"message": "Forbidden access, the user should be a tutor"}, status=status.HTTP_403_FORBIDDEN)
    
    return Response({'message': "Description updated successfully"}, status=status.HTTP_200_OK)

# changing tutor courses
@api_view(['PUT'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def tutor_change_courses(request):
    user = request.user
    if is_tutor(user):
        tutor = Tutor.objects.get(user = user)
        courses = request.data['courses']
        tutor.taught_courses.set(courses)
        tutor.save()
    else:
        return Response({"message": "Forbidden access, the user should be a tutor"}, status=status.HTTP_403_FORBIDDEN)
    
    return Response({'message': "Your taught courses have been updated successfully"}, status=status.HTTP_200_OK)

# changing tutor languages
@api_view(['PUT'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def tutor_change_languages(request):
    user = request.user
    if is_tutor(user):
        tutor = Tutor.objects.get(user = user)
        languages = request.data['languages']
        tutor.languages.set(languages)
        tutor.save()
    else:
        return Response({"message": "Forbidden access, the user should be a tutor"}, status=status.HTTP_403_FORBIDDEN)
    
    return Response({'message': "Your languages have been updated successfully"}, status=status.HTTP_200_OK)

# changing tutor rate
@api_view(['PUT'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def tutor_change_rate(request):
    user = request.user
    if is_tutor(user):
        tutor = Tutor.objects.get(user = user)
        rate = request.data['rate']
        tutor.rate = rate
        tutor.save()
    else:
        return Response({"message": "Forbidden access, the user should be a tutor"}, status=status.HTTP_403_FORBIDDEN)
    
    return Response({'message': "Your rate has been updated successfully"}, status=status.HTTP_200_OK)
 
@api_view(['PUT'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def change_phone_number(request):
    user = request.user
    try:
        new_phone_number = request.data["phone_number"]
    except:
        return Response("JSON Error. phone_number field not provided.")
    user.profile.phone_number = new_phone_number
    user.profile.save()
    
    return Response({'message': "Your phone number has been updated successfully"}, status=status.HTTP_200_OK)

@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def contact_us(request):
    user = request.user
    user_name = f"{user.first_name} {user.last_name}"
    user_email = user.email
    subject = request.data.get('subject')
    message_content = request.data.get('message')

    if not subject or not message_content:
        return Response("Please fill in all the fields.", status=400)

    data = {
        'user_name': user_name,
        'user_email': user_email,
        'message_content': message_content,
    }

    message = get_template('users/contact_us_template.txt').render(data)

    send_mail(
        subject=f"Contact Us Form Submission: {subject}",
        message=message,
        from_email="studytron@trial-0r83ql3dvxpgzw1j.mlsender.net",
        recipient_list=["studytron01@gmail.com"],
        fail_silently=False,
    )

    return Response("Your message has been sent successfully. We will get back to you soon.", status=200)

@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def tutor_ban_user(request):
    user_id = request.data['user_id']
    try:
        tutor = request.user.tutorInfo.first()
    except:
        return Response("This user is not a tutor.", status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)
    
    try:
        user = User.objects.get(id=user_id)
    except:
        return Response("The provided user id is invalid.", status=status.HTTP_400_BAD_REQUEST)
    
    user_name = f"{user.first_name} {user.last_name}"
    if tutor.bannedProfiles.filter(id=user_id).exists():
        return Response(f"{user_name} is already banned.", status=status.HTTP_400_BAD_REQUEST)

    bookings = Booking.objects.filter(user=user, tutor=tutor)
    
    pending_list = user.profile.pending_bookings.all()
    if pending_list.exists():
        tutor_name = f"{tutor.user.first_name} {tutor.user.last_name}"
        send_pending_cancellation_emails(request, pending_list, tutor_name)
        pending_list.delete()

    for booking in bookings:
        views_scheduling.send_booking_cancellation_email(request, booking)
        booking.user = None
        booking.save()

    tutor.bannedProfiles.add(user)
    return Response(f"{user_name} was successfully banned.", status=status.HTTP_200_OK)


def send_pending_cancellation_emails(request, pending_bookings, tutor_name):
    for pending in pending_bookings:
        start_time = pending.booking.start_time.astimezone(timezone.get_current_timezone())
        formatted_time = f"{start_time.strftime('%B')} {start_time.day} at {start_time.strftime('%I').lstrip('0')} {start_time.strftime('%p')}"
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



@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def tutor_unban_user(request):
    user_id = request.data['user_id']
    try:
        tutor = request.user.tutorInfo.first()
    except:
        return Response("This user is not a tutor.", status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)
    
    try:
        user = User.objects.get(id=user_id)
    except:
        return Response("The provided user id is invalid.", status=status.HTTP_400_BAD_REQUEST)
    
    if not tutor.bannedProfiles.filter(id=user_id).exists():
        return Response(f"{user.first_name} {user.last_name} is already unbanned or wasn't banned initially.", status=status.HTTP_400_BAD_REQUEST)
    
    tutor.bannedProfiles.remove(user)
    return Response(f"{user.first_name} {user.last_name} was successfully unbanned.", status=status.HTTP_200_OK)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def tutor_get_banned_users(request):
    try:
        tutor = request.user.tutorInfo.first()
    except:
        return Response("This user is not a tutor.", status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)
    
    bannedProfiles = tutor.bannedProfiles.all()

    serializer = UserSerializer(bannedProfiles, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def upload_profile_picture(request):
    serializer = FileUploadSerializer(data=request.data, context={'request': request, 'user': request.user})
    
    if serializer.is_valid():
        delete_old_profile_picture(request.user)

        file_upload = serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_profile_picture(request):
    file_upload = FileUpload.objects.filter(user=request.user).last()

    if file_upload:
        file_url = file_upload.file.url
    else:
        file_url = None 

    return Response({'file_url': file_url}, status=status.HTTP_200_OK)

from azure.storage.blob import BlobServiceClient
from django.conf import settings

def delete_old_profile_picture(user):
    file_upload = FileUpload.objects.filter(user=user).last()

    if file_upload:
        old_file_path = file_upload.file.name
        
        connection_string = f"DefaultEndpointsProtocol=https;AccountName={settings.AZURE_ACCOUNT_NAME};AccountKey={settings.AZURE_ACCOUNT_KEY};EndpointSuffix=core.windows.net"
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        
        container_client = blob_service_client.get_container_client(settings.AZURE_CONTAINER)
        
        blob_client = container_client.get_blob_client(old_file_path)

        try:
            blob_client.delete_blob()
            print(f"Successfully deleted old profile picture: '{old_file_path}'")
        except Exception as e:
            print(f"Failed to delete old profile picture: {e}")

        file_upload.delete()
    else:
        print("No file upload found for the user.")

@api_view(['DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def delete_profile_picture(request):
    delete_old_profile_picture(request.user)
    try:
        return Response("Profile picture successfully removed.", status=status.HTTP_200_OK)
    except:
        return Response("Profile picture already removed", status=status.HTTP_400_BAD_REQUEST)