import os
import sys
from django.utils import timezone

# Add your Django project to the Python path
sys.path.append('/home/studytronadmin/studytron.backend/backend')  # Adjust the path to your username and project name
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.settings")  # Change to your actual settings module

import django
django.setup()

from server.models import Booking, Subscription  # Change 'your_app' to your actual app name

def delete_expired_bookings():
    now = timezone.now()
    expired_bookings = Booking.objects.filter(start_time__lt=now)
    expired_count = expired_bookings.count()
    expired_bookings.delete()
    print(f"Deleted {expired_count} expired bookings.")

def delete_expired_subscriptions():
    now = timezone.now()
    expired_subscriptions = Subscription.objects.filter(end_date__lt=now)
    expired_count = expired_subscriptions.count()
    expired_subscriptions.delete()
    print(f"Deleted {expired_count} expired subscriptions.")

def main():
    delete_expired_bookings()
    delete_expired_subscriptions()

if __name__ == "__main__":
    main()
