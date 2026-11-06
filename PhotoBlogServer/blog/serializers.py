from rest_framework import serializers
from .models import Post

def validate_image(image):
    if image.size > 8 * 1024 * 1024:
        raise serializers.ValidationError('이미지는 8MB 이하여야 합니다.')
    if getattr(image, 'image', None) is not None and image.image.format not in ('JPEG', 'PNG', 'WEBP'):
        raise serializers.ValidationError('JPEG, PNG, WEBP 이미지를 사용해주세요.')
    return image

class PostSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = Post
        fields = ['id', 'title', 'text', 'image', 'created_date', 'published_date', 'author', 'acknowledged']
        read_only_fields = ['id', 'author', 'acknowledged']

    def validate_image(self, image):
        return validate_image(image)
