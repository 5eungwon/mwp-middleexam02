import uuid
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .authentication import create_token
from .models import DetectionSettings, Post, PushDevice, PushDelivery
from .push import dispatch_post, send_delivery


@override_settings(FCM_SERVICE_ACCOUNT_FILE='')
class DetectionFeatureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('feature-camera', password='Testing-Features-42!')
        cls.other = get_user_model().objects.create_user('feature-other', password='Testing-Other-42!')

    def setUp(self):
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION='JWT ' + create_token(self.user))

    def register(self):
        self.device_values = {'installation_id': str(uuid.uuid4()), 'binding_id': str(uuid.uuid4()), 'token': 'fcm-registration-token-for-unit-testing'}
        return self.api.post('/api/push/devices/', self.device_values, format='json')

    def test_settings_requires_auth_and_defaults_to_full_frame(self):
        self.assertEqual(APIClient().get('/api/settings/').status_code, 401)
        response = self.api.get('/api/settings/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['zone_enabled'])
        self.assertTrue(response.data['monitoring_enabled'])
        self.assertEqual([response.data[k] for k in ['left', 'top', 'right', 'bottom']], [0, 0, 1, 1])
        self.assertFalse(response.data['push']['configured'])

    def test_region_persists_and_is_private_to_each_account(self):
        response = self.api.patch('/api/settings/', {'zone_enabled': True, 'zone_name': '현관', 'left': .2, 'top': .1, 'right': .8, 'bottom': .9}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.api.get('/api/settings/').data['left'], .2)
        self.api.credentials(HTTP_AUTHORIZATION='JWT ' + create_token(self.other))
        self.assertFalse(self.api.get('/api/settings/').data['zone_enabled'])

    def test_region_rejects_inverted_tiny_nonfinite_and_out_of_range(self):
        for changes in [{'left': .9, 'right': .1}, {'right': .01}, {'bottom': 1.2}, {'top': 'nan'}]:
            with self.subTest(changes=changes):
                self.assertEqual(self.api.patch('/api/settings/', changes, format='json').status_code, 400)

    def test_settings_web_requires_login_and_renders_configuration_state(self):
        self.assertEqual(self.client.get('/settings/').status_code, 302)
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/settings/'), '원격 감시 ON/OFF')

    def test_monitoring_toggle_is_persistent_and_account_scoped(self):
        self.assertEqual(self.api.patch('/api/settings/', {'monitoring_enabled': False}, format='json').status_code, 200)
        self.assertFalse(self.api.get('/api/settings/').data['monitoring_enabled'])
        self.api.credentials(HTTP_AUTHORIZATION='JWT '+create_token(self.other))
        self.assertTrue(self.api.get('/api/settings/').data['monitoring_enabled'])

    def test_paused_server_blocks_new_records_but_preserves_reads_and_resume(self):
        from .tests import photo
        import tempfile
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            existing=Post.objects.create(author=self.user,title='existing',image='test.jpg')
            self.api.patch('/api/settings/', {'monitoring_enabled': False}, format='json')
            blocked=self.api.post('/api_root/Post/', {'title':'person','image':photo()}, format='multipart')
            self.assertEqual(blocked.status_code,423)
            self.assertEqual(blocked.data['code'],'monitoring_paused')
            self.assertEqual(Post.objects.count(),1)
            self.assertEqual(self.api.get(f'/api_root/Post/{existing.pk}/').status_code,200)
            self.api.patch('/api/settings/', {'monitoring_enabled': True}, format='json')
            accepted=self.api.post('/api_root/Post/', {'title':'person','image':photo()}, format='multipart')
            self.assertEqual(accepted.status_code,201)

    def test_monitoring_patch_does_not_change_saved_region(self):
        self.api.patch('/api/settings/', {'zone_enabled':True,'left':.2,'right':.8}, format='json')
        response=self.api.patch('/api/settings/', {'monitoring_enabled':False}, format='json')
        self.assertEqual((response.data['left'],response.data['right'],response.data['zone_enabled']),(.2,.8,True))

    def test_device_binding_is_registered_without_exposing_token(self):
        response = self.register()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.device_values['token'], str(response.data))
        self.assertEqual(PushDevice.objects.get().owner, self.user)

    def test_another_user_cannot_unregister_or_claim_an_unknown_device_token(self):
        self.register()
        self.api.credentials(HTTP_AUTHORIZATION='JWT ' + create_token(self.other))
        self.api.delete('/api/push/devices/' + self.device_values['installation_id'] + '/')
        self.assertEqual(PushDevice.objects.count(), 1)
        values = dict(self.device_values, token='different-token-for-test-only')
        self.assertEqual(self.api.post('/api/push/devices/', values, format='json').status_code, 403)

    def test_missing_firebase_config_is_recorded_instead_of_fake_success(self):
        self.register()
        post = Post.objects.create(author=self.user, title='person', image='test.jpg')
        dispatch_post(post.pk)
        self.assertEqual(PushDelivery.objects.get().state, 'configuration_required')

    def test_disabled_notifications_are_not_sent(self):
        self.register()
        DetectionSettings.objects.update_or_create(owner=self.user, defaults={'notifications_enabled': False})
        post = Post.objects.create(author=self.user, title='person', image='test.jpg')
        dispatch_post(post.pk)
        self.assertEqual(PushDelivery.objects.get().state, 'disabled')

    @patch('blog.push.configured', return_value=True)
    @patch('google.oauth2.service_account.Credentials.from_service_account_file')
    @patch('google.auth.transport.requests.AuthorizedSession')
    def test_fcm_payload_targets_current_binding_and_success_is_not_resent(self, session_type, credentials, configured):
        self.register()
        post = Post.objects.create(author=self.user, title='person', zone_name='현관', image='test.jpg')
        credentials.return_value = SimpleNamespace(project_id='unit-project')
        session = session_type.return_value.__enter__.return_value
        session.post.return_value.status_code = 200
        dispatch_post(post.pk)
        delivery = PushDelivery.objects.get()
        self.assertEqual(delivery.state, 'sent')
        payload = session.post.call_args.kwargs['json']['message']
        self.assertEqual(payload['data']['binding_id'], self.device_values['binding_id'])
        self.assertEqual(payload['data']['post_id'], str(post.pk))
        send_delivery(delivery)
        self.assertEqual(session.post.call_count, 1)

    @patch('blog.push.configured', return_value=True)
    @patch('google.oauth2.service_account.Credentials.from_service_account_file', side_effect=ValueError('invalid key'))
    def test_provider_failure_preserves_post_and_retry_state(self, credentials, configured):
        self.register()
        post = Post.objects.create(author=self.user, title='person', image='test.jpg')
        dispatch_post(post.pk)
        self.assertTrue(Post.objects.filter(pk=post.pk).exists())
        delivery = PushDelivery.objects.get()
        self.assertEqual((delivery.state, delivery.attempts), ('failed', 1))

    def test_invalid_login_json_array_returns_400(self):
        self.assertEqual(APIClient().post('/api-token-auth/', [], format='json').status_code, 400)
