from django.contrib import admin
from .models import User, Course, Major, Tutor, Language, Rating, SpecificRating, Booking, Profile, EmailConfirmationToken, TutorPending, Pending, FileUpload, Subscription
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

class BookingAdmin(admin.ModelAdmin):
    list_display = ['tutor', 'start_time', 'user']
    search_fields = ['tutor__user__username', 'user__username']

class UserAdmin(BaseUserAdmin):
    list_display = ('id', 'username', 'email', 'first_name', 'last_name', 'is_staff')

admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(Course)
admin.site.register(Major)
admin.site.register(Tutor)
admin.site.register(Language)
admin.site.register(Rating)
admin.site.register(SpecificRating)
admin.site.register(Booking, BookingAdmin)
admin.site.register(Profile)
admin.site.register(EmailConfirmationToken)
admin.site.register(TutorPending)
admin.site.register(Pending)
admin.site.register(FileUpload)
admin.site.register(Subscription)