import io
import tempfile
from datetime import timedelta
import jwt
from PIL import Image
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from .authentication import create_token
from .models import Post

def photo(name='capture.jpg'):
    buffer = io.BytesIO()
    Image.new('RGB', (64, 48), '#486e80').save(buffer, format='JPEG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/jpeg')

class ServerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('camera', password='Test-Password-42!')
        cls.other = get_user_model().objects.create_user('other', password='Different-Test-42!')

    def setUp(self):
        cache.clear()
        self.media = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media.cleanup)
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION='JWT ' + create_token(self.owner))

    def make_post(self, **kwargs):
        values = {'author': self.owner, 'title': 'person', 'text': 'person newly appeared', 'image': photo()}
        values.update(kwargs)
        return Post.objects.create(**values)

    def test_login_returns_jwt_and_invalid_password_is_rejected(self):
        client = APIClient()
        response = client.post('/api-token-auth/', {'username': 'camera', 'password': 'Test-Password-42!'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], 'camera')
        claims = jwt.decode(response.data['token'], settings.SECRET_KEY, algorithms=['HS256'])
        self.assertEqual(claims['sub'], str(self.owner.pk))
        response = client.post('/api-token-auth/', {'username': 'camera', 'password': 'wrong'})
        self.assertEqual(response.status_code, 401)
        self.assertNotIn('token', response.data)

    def test_api_requires_authentication(self):
        client = APIClient()
        self.assertEqual(client.get('/api_root/Post/').status_code, 401)
        self.assertEqual(client.post('/api_root/Post/', {'title': 'forbidden'}).status_code, 401)

    def test_expired_and_tampered_jwt_rejected(self):
        expired = jwt.encode({'sub': str(self.owner.pk), 'iat': timezone.now()-timedelta(days=1), 'exp': timezone.now()-timedelta(hours=1)}, settings.SECRET_KEY, algorithm='HS256')
        for token in (expired, create_token(self.owner) + 'tampered'):
            self.api.credentials(HTTP_AUTHORIZATION='JWT ' + token)
            self.assertEqual(self.api.get('/api_root/Post/').status_code, 401)

    def test_bearer_header_accepted(self):
        self.api.credentials(HTTP_AUTHORIZATION='Bearer ' + create_token(self.owner))
        self.assertEqual(self.api.get('/api_root/Post/').status_code, 200)

    def test_multipart_upload_and_json_contract(self):
        response = self.api.post('/api_root/Post/', {'title': 'person', 'text': 'person, bicycle', 'image': photo(), 'author': self.other.pk, 'acknowledged': True}, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(set(response.data), {'id', 'title', 'text', 'image', 'created_date', 'published_date', 'author', 'acknowledged'})
        self.assertEqual(response.data['author'], 'camera')
        self.assertFalse(response.data['acknowledged'])
        self.assertTrue(response.data['image'].startswith('http://testserver/media/detections/'))
        self.assertNotIn('capture.jpg', response.data['image'])
        self.assertEqual(self.api.get('/api_root/Post/').data[0]['title'], 'person')

    def test_invalid_missing_and_oversize_images_rejected(self):
        bad = SimpleUploadedFile('fake.jpg', b'not an image', content_type='image/jpeg')
        for values in ({'title': 'missing'}, {'title': 'invalid', 'image': bad}):
            self.assertEqual(self.api.post('/api_root/Post/', values, format='multipart').status_code, 400)
        huge = photo()
        huge.size = 8 * 1024 * 1024 + 1
        from .serializers import validate_image
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_image(huge)

    def test_another_user_cannot_list_read_edit_delete_or_acknowledge(self):
        other_post = self.make_post(author=self.other)
        own = self.make_post()
        self.assertEqual([p['id'] for p in self.api.get('/api_root/Post/').data], [own.pk])
        url = f'/api_root/Post/{other_post.pk}/'
        self.assertEqual(self.api.get(url).status_code, 404)
        self.assertEqual(self.api.patch(url, {'title': 'stolen'}).status_code, 404)
        self.assertEqual(self.api.delete(url).status_code, 404)
        self.assertEqual(self.api.post(url + 'acknowledge/').status_code, 404)

    def test_search_and_unread_filters(self):
        match = self.make_post(title='person', text='front door')
        self.make_post(title='bicycle', acknowledged=True)
        self.assertEqual([p['id'] for p in self.api.get('/api_root/Post/?search=front&unread=1').data], [match.pk])
        self.assertEqual(len(self.api.get('/api_root/Post/?unread=1').data), 1)
        self.assertEqual(len(self.api.get('/api_root/Post/?search=unknown').data), 0)

    def test_acknowledge_is_idempotent(self):
        post = self.make_post()
        url = f'/api_root/Post/{post.pk}/acknowledge/'
        for _ in range(2):
            self.assertEqual(self.api.post(url).status_code, 200)
        post.refresh_from_db()
        self.assertTrue(post.acknowledged)
        self.assertEqual(self.api.get('/api_root/Post/?unread=1').data, [])

    def test_web_login_feed_detail_and_acknowledge(self):
        post = self.make_post()
        self.assertRedirects(self.client.get('/'), '/accounts/login/?next=/')
        self.assertTrue(self.client.login(username='camera', password='Test-Password-42!'))
        self.assertContains(self.client.get('/'), 'person')
        self.assertContains(self.client.get(reverse('detail', args=[post.pk])), 'person newly appeared')
        response = self.client.post(reverse('acknowledge', args=[post.pk]))
        self.assertRedirects(response, reverse('detail', args=[post.pk]))
        post.refresh_from_db()
        self.assertTrue(post.acknowledged)
        other = self.make_post(author=self.other)
        self.assertEqual(self.client.get(reverse('detail', args=[other.pk])).status_code, 404)

    def test_web_upload_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.login(username='camera', password='Test-Password-42!')
        response = client.post('/posts/new/', {'title': 'unsafe', 'image': photo()}, format='multipart')
        self.assertEqual(response.status_code, 403)

    def test_inactive_user_token_is_rejected(self):
        token = create_token(self.owner)
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        self.api.credentials(HTTP_AUTHORIZATION='JWT ' + token)
        self.assertEqual(self.api.get('/api_root/Post/').status_code, 401)

    def test_health_has_no_private_data(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'service': 'PhotoBlogServer'})

    def test_api_login_rate_limit(self):
        client = APIClient()
        for _ in range(10):
            self.assertEqual(client.post('/api-token-auth/', {'username': 'camera', 'password': 'wrong'}).status_code, 401)
        self.assertEqual(client.post('/api-token-auth/', {'username': 'camera', 'password': 'wrong'}).status_code, 429)
