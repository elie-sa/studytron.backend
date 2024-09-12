from server.models import Tutor, Subscription
from django.utils import timezone
for tutor in Tutor.objects.all():
    Subscription.objects.create(tutor=tutor, start_date=timezone.now(), end_date=timezone.now() + timezone.timedelta(days=30))
