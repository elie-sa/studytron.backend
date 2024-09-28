from django.utils import timezone
from datetime import timedelta
import uuid
from django.db import models
from django.contrib.auth.models import User
from rest_framework.authentication import TokenAuthentication
from django.core.validators import MinValueValidator, MaxValueValidator
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.authtoken.models import Token
import pyotp

class ExpiringToken(Token):
    expires = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.expires = timezone.now() + timedelta(hours=4)
        super().save(*args, **kwargs)

class ExpiringTokenAuthentication(TokenAuthentication):

    def authenticate(self, request):
        auth = super().authenticate(request)
        if not auth:
            return None
        
        token = auth[1]
        if token.expires < timezone.now():
            token.delete()
            raise AuthenticationFailed('Token has expired.')

        return auth

class FileUpload(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="profile_picture")
    file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

class EmailConfirmationToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4,  editable = False )
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

class Major(models.Model):
    name = models.CharField(max_length = 64)
    code = models.CharField(max_length = 5)

    def __str__ (self):
            return f"{self.name}"

class Course(models.Model):
    name = models.CharField(max_length = 64)
    major = models.ForeignKey(Major, on_delete=models.CASCADE, related_name = "courses")
    code = models.CharField(max_length = 8)

    def __str__ (self):
        return f"{self.code} - {self.name}"    
       
class Language(models.Model):
     name = models.CharField(max_length = 64)

     def __str__(self):
          return f"{self.name}"

class Tutor(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank = False, related_name = "tutorInfo")
    description = models.CharField(max_length = 256, default = "")
    taught_courses = models.ManyToManyField(Course, blank = True, related_name = "courseTutors")
    rate = models.PositiveIntegerField(default = 0)
    languages = models.ManyToManyField(Language, blank = True, related_name = "languageTutors")
    bannedProfiles = models.ManyToManyField(User, blank=True, related_name="banningTutors")

    def __str__ (self):
        return f"{self.user.first_name} {self.user.last_name}"
    
class Subscription(models.Model):
    tutor = models.OneToOneField(Tutor, on_delete=models.CASCADE, related_name="subscription")
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    def is_active(self):
        return self.end_date > timezone.now()

    def days_left(self):
        time_left = self.end_date - timezone.now()
        days_left = time_left.days if time_left.days > 0 else 0
        
        return days_left

    def __str__(self):
        return f"Subscription for {self.tutor.user.first_name} {self.tutor.user.last_name}"


# rating models
class Rating(models.Model):
    tutor = models.ForeignKey(Tutor, related_name="rating", on_delete=models.CASCADE, blank = False)
    rating = models.FloatField(default=0)
    num_of_ratings = models.IntegerField(default = 0)

    def __str__(self):
        return f"Rating: {self.rating} with {self.num_of_ratings} ratings"
        
class SpecificRating(models.Model):
    rating = models.FloatField(blank = False, validators=[MinValueValidator(1), MaxValueValidator(5)])
    related_rating = models.ForeignKey(Rating, blank = False, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"Rating: {self.rating}"

# scheduling
class Booking(models.Model):
    tutor = models.ForeignKey(Tutor, on_delete=models.CASCADE, related_name='bookings')
    start_time = models.DateTimeField()
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, default=None)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f" "
    
class Pending(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="pending")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="pending_courses")

    def __str__(self):
        return f"Pending: {self.booking} for {self.course.name}"

class TutorPending(models.Model):
    tutor = models.ForeignKey(Tutor, on_delete=models.CASCADE)
    pending_bookings = models.ManyToManyField(Pending, related_name="pending_tutor_profiles", blank=True)

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    is_confirmed = models.BooleanField(default=False)
    secret_key = models.CharField(max_length=32, blank=True, null=True)
    pending_bookings = models.ManyToManyField(Pending, related_name="pending_profiles", blank=True)

    def generate_secret_key(self):
        self.secret_key = pyotp.random_base32()
        self.save()

    def __str__(self):
        return self.user.username
    
    def add_pending_booking(self, booking):
        pending, created = Pending.objects.get_or_create(booking=booking, profile=self)
        return pending
