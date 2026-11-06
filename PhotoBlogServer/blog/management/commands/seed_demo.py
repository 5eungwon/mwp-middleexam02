import os
from pathlib import Path
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from blog.models import Post

class Command(BaseCommand):
    help = 'Create a local test user. DEMO_PASSWORD must be supplied through the environment.'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='guardian')
        parser.add_argument('--superuser', action='store_true')
        parser.add_argument('--image', type=Path)

    def handle(self, *args, **options):
        password = os.environ.get('DEMO_PASSWORD')
        if not password:
            raise CommandError('Set DEMO_PASSWORD in the environment (never commit it).')
        user, created = get_user_model().objects.get_or_create(username=options['username'])
        try:
            validate_password(password, user)
        except ValidationError as error:
            if created:
                user.delete()
            raise CommandError('; '.join(error.messages))
        user.set_password(password)
        user.is_staff = options['superuser']
        user.is_superuser = options['superuser']
        user.save()
        image = options['image']
        if image:
            with image.open('rb') as source:
                Post.objects.create(author=user, title='연결 테스트 이미지', text='데모 이미지 · 실제 YOLO 검출 결과 아님', image=File(source, name=image.name))
        self.stdout.write(self.style.SUCCESS(f'User {user.username} ready. Password not printed.'))
