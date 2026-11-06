from datetime import timedelta
import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

def create_token(user):
    now = timezone.now()
    return jwt.encode({'sub': str(user.pk), 'iat': now, 'exp': now + timedelta(hours=8)}, settings.SECRET_KEY, algorithm='HS256')

class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() not in (b'jwt', b'bearer'):
            return None
        if len(parts) != 2:
            raise AuthenticationFailed('인증 헤더 형식을 확인해주세요.')
        try:
            payload = jwt.decode(parts[1], settings.SECRET_KEY, algorithms=['HS256'], options={'require': ['sub', 'exp', 'iat']})
            user = get_user_model().objects.get(pk=payload['sub'], is_active=True)
        except (jwt.InvalidTokenError, get_user_model().DoesNotExist, ValueError, TypeError):
            raise AuthenticationFailed('토큰이 만료되었거나 유효하지 않습니다.')
        return (user, parts[1])

    def authenticate_header(self, request):
        return 'JWT'
