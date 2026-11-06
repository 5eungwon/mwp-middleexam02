import uuid
from pathlib import Path
from django.conf import settings
from django.db import models
from django.utils import timezone

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

    class Meta:
        ordering = ['-created_date', '-id']
        verbose_name = '감지 기록'
        verbose_name_plural = '감지 기록'

    def __str__(self):
        return self.title
