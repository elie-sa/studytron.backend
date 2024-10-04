from django.contrib import admin
from django.urls import path, re_path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from . import views, views_scheduling, views_rating, views_payment, views_testing

urlpatterns = [
    # authentication apis
    path('admin/', admin.site.urls),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', views.CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('login', views.login, name="login"),
    path('signup', views.signup, name="signup"),
    path('logout', views.logout, name="logout"),
    path('test_token', views.test_token),
    path('user/sendConfirmationEmail', views.create_email_token, name = "send_confirmation_email"),
    path('user/confirmEmail', views.confirm_email_view, name="confirm_email_view"),
    path('user/forgotPassword', views.check_email, name="check_email"),
    path('user/verifyOtp', views.verify_otp, name="verify_otp"),
    path('user/changeForgottenPassword', views.change_forgotten_password, name="change_forgotten_password"),

    # main get APIs
    path('user/getInfo', views.get_user_info, name="get_user_info"),
    path('getMajors/', views.list_majors, name="list_majors"),
    path('getCourses/', views.list_courses, name="list_courses"),
    path('getAllCourses/', views.list_all_courses, name="list_all_courses"),
    path('getTutors/', views.list_tutors, name="list_tutors"),
    path('getLanguages/', views.list_languages, name="list_languages"),
    path('getLanguage/<int:language_id>', views.get_language, name="get_language"),
    path('getCourse/<int:course_id>', views.get_course, name="get_course"),
    path('getMajor/<int:major_id>', views.get_major, name="get_major"),
    
    # for changing the user and tutor attributes
    path('user/changeName', views.change_user_name, name="change_user_name"),
    path('user/changePassword', views.change_password, name="change_password"),
    path('user/changePhoneNumber', views.change_phone_number, name="change_phone_number"),
    path('tutor/changeDescription', views.tutor_change_description, name="tutor_change_description"),
    path('tutor/changeCourses', views.tutor_change_courses, name="tutor_change_courses"),
    path('tutor/changeLanguages', views.tutor_change_languages, name="tutor_change_languages"),
    path('tutor/changeRate', views.tutor_change_rate, name="tutor_change_rate"),

    # rating
    path('user/rateTutor', views_rating.rate_tutor, name="rate_tutor"),
    path('user/deleteRating', views_rating.delete_rating, name="delete_rating"),
    path('getTutorRating', views_rating.get_tutor_rating, name="get_tutor_rating"),
    path('user/getRating', views_rating.get_user_rating, name="get_user_rating"),

    # scheduling

    #POST requests
    path('tutor/createSlot', views_scheduling.create_booking, name="create_booking"),
    path('user/bookSlot', views_scheduling.book_session, name="book_session"),
    path('tutor/confirmBooking', views_scheduling.confirm_booking, name="confirm_booking"),

    #GET requests
    path('user/getHours', views_scheduling.get_hours, name="get_hours"),
    path('user/getBookings', views_scheduling.get_my_bookings, name="get_my_bookings"),
    path('user/getBookedDays', views_scheduling.user_get_days, name="user_get_days"),
    path('tutor/getSlottedDays', views_scheduling.tutor_get_slotted_days, name="tutor_get_slotted_days"),
    path('user/getMyBookedDays', views_scheduling.user_get_booked_days, name="user_get_booked_days"),
    path('user/getPendingRequests', views_scheduling.user_get_pending_bookings, name="user_get_pending_bookings"),
    path('tutor/getHours', views_scheduling.tutor_get_hours, name="tutor_get_hours"),
    path('user/getPendingDays', views_scheduling.user_get_pending_days, name="user_get_pending_days"),
    path('tutor/getPendingDays', views_scheduling.tutor_get_pending_days, name="tutor_get_pending_days"),
    path('tutor/getBookedDays', views_scheduling.tutor_get_days, name="tutor_get_days"),
    path('tutor/getFullyBookedDays', views_scheduling.tutor_get_full_days, name="tutor_get_full_days"),
    path('tutor/getPendingRequests', views_scheduling.tutor_get_pending_bookings, name="tutor_get_pending_bookings"),
    path('tutor/checkBookingStatus', views_scheduling.tutor_check_booking_condition, name="tutor_check_booking_condition"),

    #PUT
    path('user/cancelBooking', views_scheduling.cancel_my_booking, name="cancel_my_booking"),
    path('tutor/cancelBooking', views_scheduling.tutor_cancel_booking, name="tutor_cancel_booking"),
    path('tutor/deleteSlot', views_scheduling.tutor_delete_slot, name="tutor_delete_slot"),

    #Contact Us
    path('user/contactUs', views.contact_us, name="contact_us"),

    #Banning
    path('tutor/banUser', views.tutor_ban_user, name="tutor_ban_user"),
    path('tutor/unbanUser', views.tutor_unban_user, name="tutor_unban_user"),
    path('tutor/getBannedUsers', views.tutor_get_banned_users, name="tutor_get_banned_users"),

    #Payment and Activation
    path('activateAccount', views_payment.activate_tutor_account, name="activate_tutor_account"),
    path('activateFreeTrial', views_payment.activate_tutor_free_trial, name="activate_tutor_free_trial"),
    path('tutor/getDaysLeft', views_payment.tutor_get_subscription_days, name="tutor_get_subscription_days"),
    path('tutor/getActivationStatus', views_payment.get_tutor_activation_status, name="get_tutor_activation_status"),

    #Profile Pictures
    path('user/uploadProfilePicture', views.upload_profile_picture, name="upload_profile_picture"),
    path('user/getProfilePicture', views.get_profile_picture, name='get_profile_picture'),
    path('user/deleteProfilePicture', views.delete_profile_picture, name="delete_profile_picture"),

    #Testing Apis
    path('testSuccess', views_testing.test_success_view),
    path('testFailure', views_testing.test_failure_view),
]