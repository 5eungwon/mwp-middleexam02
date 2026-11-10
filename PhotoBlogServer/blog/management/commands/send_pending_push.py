from django.core.management.base import BaseCommand
from blog.models import PushDelivery
from blog.push import send_delivery


class Command(BaseCommand):
    help = 'Retry pending FCM notifications without printing tokens or credentials.'

    def handle(self, *args, **options):
        deliveries = PushDelivery.objects.exclude(state__in=['sent', 'disabled']).filter(attempts__lt=3).select_related('post__author', 'device')[:100]
        count = 0
        for delivery in deliveries:
            send_delivery(delivery)
            count += 1
        self.stdout.write(f'Processed {count} notification deliveries.')
