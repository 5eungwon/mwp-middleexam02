from rest_framework import serializers
import math
from .models import Post, DetectionSettings

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
        fields = ['id', 'title', 'text', 'image', 'created_date', 'published_date', 'author', 'acknowledged', 'zone_name']
        read_only_fields = ['id', 'author', 'acknowledged']

    def validate_image(self, image):
        return validate_image(image)


class DetectionSettingsSerializer(serializers.ModelSerializer):
    preview_image = serializers.SerializerMethodField()

    class Meta:
        model = DetectionSettings
        fields = ['zone_enabled', 'zone_name', 'left', 'top', 'right', 'bottom', 'notifications_enabled', 'updated_at', 'preview_image']
        read_only_fields = ['updated_at', 'preview_image']

    def get_preview_image(self, instance):
        post = Post.objects.filter(author=instance.owner).first()
        return self.context['request'].build_absolute_uri(post.image.url) if post else None

    def validate(self, attrs):
        coordinates = {}
        for key in ['left', 'top', 'right', 'bottom']:
            value = attrs.get(key, getattr(self.instance, key, {'left': 0, 'top': 0, 'right': 1, 'bottom': 1}[key]))
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise serializers.ValidationError({key: '좌표는 0~1 사이의 유한한 값이어야 합니다.'})
            coordinates[key] = value
        if coordinates['right'] - coordinates['left'] < .02 or coordinates['bottom'] - coordinates['top'] < .02:
            raise serializers.ValidationError('너비와 높이가 각각 2% 이상인 영역을 지정해주세요.')
        return attrs


class PushDeviceSerializer(serializers.Serializer):
    installation_id = serializers.UUIDField()
    binding_id = serializers.UUIDField()
    token = serializers.CharField(min_length=20, max_length=4096, trim_whitespace=True)
