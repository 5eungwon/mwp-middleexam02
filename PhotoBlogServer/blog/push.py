"""FCM HTTP v1 delivery. Credentials and registration tokens never enter logs."""
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import close_old_connections
from .models import DetectionSettings, PushDevice, PushDelivery

LOG = logging.getLogger(__name__)
WORKERS = ThreadPoolExecutor(max_workers=2, thread_name_prefix='detection-push')


def configured():
    return bool(settings.FCM_SERVICE_ACCOUNT_FILE and Path(settings.FCM_SERVICE_ACCOUNT_FILE).is_file())


def transport_status(user):
    prefs, _ = DetectionSettings.objects.get_or_create(owner=user)
    return {'configured': configured(), 'enabled': prefs.notifications_enabled,
            'registered_devices': PushDevice.objects.filter(owner=user, active=True).count()}


def send_delivery(delivery):
    if delivery.state == 'sent' or not delivery.device.active:
        return
    prefs, _ = DetectionSettings.objects.get_or_create(owner=delivery.post.author)
    if not prefs.notifications_enabled or delivery.device.owner_id != delivery.post.author_id:
        delivery.state = 'disabled'
        delivery.save(update_fields=['state', 'updated_at'])
        return
    if not configured():
        delivery.state = 'configuration_required'
        delivery.save(update_fields=['state', 'updated_at'])
        return
    delivery.attempts += 1
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
        credentials = service_account.Credentials.from_service_account_file(
            settings.FCM_SERVICE_ACCOUNT_FILE,
            scopes=['https://www.googleapis.com/auth/firebase.messaging'])
        post = delivery.post
        payload = {'message': {
            'token': delivery.device.token,
            'data': {'post_id': str(post.pk), 'title': '새 감지 기록',
                     'body': f'{post.zone_name or "감시 카메라"}: {post.title}'[:160],
                     'binding_id': str(delivery.device.binding_id)},
            'android': {'priority': 'high', 'ttl': '3600s'},
        }}
        with AuthorizedSession(credentials, refresh_timeout=5, max_refresh_attempts=1) as session:
            response = session.post(f'https://fcm.googleapis.com/v1/projects/{credentials.project_id}/messages:send',
                                    json=payload, timeout=8)
        if response.status_code == 200:
            delivery.state, delivery.error_code = 'sent', ''
        else:
            try:
                error = response.json().get('error', {})
                codes = [detail.get('errorCode', '') for detail in error.get('details', [])]
            except (ValueError, AttributeError, TypeError):
                codes = []
            delivery.state = 'failed'
            delivery.error_code = 'UNREGISTERED' if 'UNREGISTERED' in codes else f'FCM_HTTP_{response.status_code}'
            if delivery.error_code == 'UNREGISTERED':
                PushDevice.objects.filter(pk=delivery.device_id).update(active=False)
    except Exception as error:
        delivery.state, delivery.error_code = 'failed', type(error).__name__[:80]
        LOG.warning('Push delivery failed id=%s type=%s', delivery.pk, type(error).__name__)
    delivery.save(update_fields=['state', 'attempts', 'error_code', 'updated_at'])


def dispatch_post(post_id):
    from .models import Post
    try:
        post = Post.objects.select_related('author').get(pk=post_id)
        devices = PushDevice.objects.filter(owner=post.author, active=True)[:10]
        for device in devices:
            delivery, _ = PushDelivery.objects.get_or_create(post=post, device=device)
            send_delivery(delivery)
    except Exception as error:
        # A notification failure must not turn a committed photo into HTTP 500.
        LOG.warning('Push dispatch failed post=%s type=%s', post_id, type(error).__name__)


def enqueue_post(post_id):
    """Persist work before best-effort background sending; photo responses stay fast."""
    from .models import Post
    try:
        post = Post.objects.get(pk=post_id)
        devices = PushDevice.objects.filter(owner=post.author, active=True)[:10]
        for device in devices:
            PushDelivery.objects.get_or_create(post=post, device=device,
                defaults={'state': 'pending' if configured() else 'configuration_required'})
        if configured() and devices.exists():
            def work():
                close_old_connections()
                try:
                    dispatch_post(post_id)
                finally:
                    close_old_connections()
            WORKERS.submit(work)
    except Exception as error:
        LOG.warning('Push enqueue failed post=%s type=%s', post_id, type(error).__name__)
