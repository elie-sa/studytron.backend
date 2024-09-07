from django.contrib import admin
from .models import Course, Major, Tutor, Language, Rating, SpecificRating, Booking, Profile, EmailConfirmationToken, TutorPending, Pending

class BookingAdmin(admin.ModelAdmin):
    list_display = ['tutor', 'start_time', 'user']
    search_fields = ['tutor__user__username', 'user__username']

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