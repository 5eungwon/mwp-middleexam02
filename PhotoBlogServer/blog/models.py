import uuid
from pathlib import Path
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

def image_path(instance, filename):
    suffix = Path(filename).suffix.lower()
    if suffix not in ('.jpg', '.jpeg', '.png', '.webp'):
        suffix = '.jpg'
    return f"detections/{timezone.localdate():%Y/%m/%d}/{uuid.uuid4().hex}{suffix}"

class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='detections')
    title = models.CharField('제목', max_length=200)
    text = models.TextField('검출 내용', max_length=5000, blank=True)
    image = models.ImageField('검출 이미지', upload_to=image_path)
    created_date = models.DateTimeField('검출 시각', default=timezone.now)
    published_date = models.DateTimeField('등록 시각', default=timezone.now)
    acknowledged = models.BooleanField('확인 완료', default=False)
    zone_name = models.CharField('감시 영역', max_length=80, blank=True, default='')

    class Meta:
        ordering = ['-created_date', '-id']
        verbose_name = '감지 기록'
        verbose_name_plural = '감지 기록'

    def __str__(self):
        return self.title


class DetectionSettings(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='detection_settings')
    zone_enabled = models.BooleanField(default=False)
    monitoring_enabled = models.BooleanField('감시 작동', default=True)
    zone_name = models.CharField(max_length=80, default='현관')
    left = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(1)])
    top = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(1)])
    right = models.FloatField(default=1, validators=[MinValueValidator(0), MaxValueValidator(1)])
    bottom = models.FloatField(default=1, validators=[MinValueValidator(0), MaxValueValidator(1)])
    notifications_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)


class PushDevice(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    installation_id = models.UUIDField(unique=True)
    binding_id = models.UUIDField()
    token = models.CharField(max_length=4096, unique=True)
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)


class PushDelivery(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    device = models.ForeignKey(PushDevice, on_delete=models.CASCADE)
    state = models.CharField(max_length=32, default='pending')
    attempts = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=80, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['post', 'device'], name='unique_post_device_push')]
