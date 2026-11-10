from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.db import connection, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from .authentication import create_token
from .forms import PostForm
from .models import Post, DetectionSettings, PushDevice
from .serializers import PostSerializer, DetectionSettingsSerializer, PushDeviceSerializer
from .push import enqueue_post, transport_status

class LoginThrottle(AnonRateThrottle):
    scope = 'login'

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def obtain_token(request):
    if not isinstance(request.data, dict):
        return Response({'detail': '아이디와 비밀번호를 객체로 전송해주세요.'}, status=400)
    user = authenticate(request, username=request.data.get('username', ''), password=request.data.get('password', ''))
    if not user:
        return Response({'detail': '아이디 또는 비밀번호를 확인해주세요.'}, status=status.HTTP_401_UNAUTHORIZED)
    return Response({'token': create_token(user), 'username': user.username})

def filter_posts(queryset, params):
    search = params.get('search', '').strip()
    if search:
        queryset = queryset.filter(Q(title__icontains=search) | Q(text__icontains=search))
    if params.get('unread') == '1':
        queryset = queryset.filter(acknowledged=False)
    return queryset

class PostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return filter_posts(Post.objects.filter(author=self.request.user).select_related('author'), self.request.query_params)

    def perform_create(self, serializer):
        post = serializer.save(author=self.request.user)
        transaction.on_commit(lambda: enqueue_post(post.pk))

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        post = self.get_object()
        post.acknowledged = True
        post.save(update_fields=['acknowledged'])
        return Response(self.get_serializer(post).data)

def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except Exception:
        return JsonResponse({'status': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ok', 'service': 'PhotoBlogServer'})

@login_required
def dashboard(request):
    all_posts = Post.objects.filter(author=request.user)
    context = {
        'posts': filter_posts(all_posts, request.GET),
        'total': all_posts.count(), 'unread': all_posts.filter(acknowledged=False).count(),
        'today': all_posts.filter(created_date__date=timezone.localdate()).count(),
        'search': request.GET.get('search', ''), 'unread_only': request.GET.get('unread') == '1',
    }
    return render(request, 'blog/dashboard.html', context)

@login_required
def detail(request, pk):
    post = get_object_or_404(Post, pk=pk, author=request.user)
    return render(request, 'blog/detail.html', {'post': post})

@login_required
@require_POST
def acknowledge(request, pk):
    post = get_object_or_404(Post, pk=pk, author=request.user)
    post.acknowledged = True
    post.save(update_fields=['acknowledged'])
    messages.success(request, '감지 기록을 확인 완료로 표시했습니다.')
    return redirect('detail', pk=pk)

@login_required
def upload(request):
    form = PostForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        transaction.on_commit(lambda: enqueue_post(post.pk))
        messages.success(request, '사진이 등록되었습니다.')
        return redirect('detail', pk=post.pk)
    return render(request, 'blog/upload.html', {'form': form})


@api_view(['GET', 'PATCH'])
def detection_settings(request):
    prefs, _ = DetectionSettings.objects.get_or_create(owner=request.user)
    kwargs = {'partial': True, 'context': {'request': request}}
    if request.method == 'PATCH':
        kwargs['data'] = request.data
    serializer = DetectionSettingsSerializer(prefs, **kwargs)
    if request.method == 'PATCH':
        serializer.is_valid(raise_exception=True)
        serializer.save()
    data = dict(serializer.data)
    data['push'] = transport_status(request.user)
    return Response(data)


@api_view(['POST'])
def register_push_device(request):
    serializer = PushDeviceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    device = PushDevice.objects.filter(installation_id=values['installation_id']).first()
    if device and device.owner_id != request.user.pk and device.token != values['token']:
        return Response({'detail': '다른 계정에 연결된 기기입니다.'}, status=403)
    token_device = PushDevice.objects.filter(token=values['token']).first()
    if token_device and token_device.installation_id != values['installation_id']:
        return Response({'detail': '기기 등록 정보를 새로 확인해주세요.'}, status=409)
    if not device and PushDevice.objects.filter(owner=request.user, active=True).count() >= 10:
        return Response({'detail': '등록 가능한 기기 수를 초과했습니다.'}, status=400)
    PushDevice.objects.update_or_create(installation_id=values['installation_id'],
        defaults={**values, 'owner': request.user, 'active': True})
    return Response({'registered': True, 'push': transport_status(request.user)}, status=200)


@api_view(['DELETE'])
def unregister_push_device(request, installation_id):
    PushDevice.objects.filter(owner=request.user, installation_id=installation_id).delete()
    return Response(status=204)


@login_required
def settings_page(request):
    prefs, _ = DetectionSettings.objects.get_or_create(owner=request.user)
    preview = Post.objects.filter(author=request.user).first()
    values = {key: getattr(prefs, key) for key in ['zone_enabled', 'zone_name', 'left', 'top', 'right', 'bottom', 'notifications_enabled']}
    return render(request, 'blog/settings.html', {'prefs': prefs, 'preview': preview, 'zone_values': values, 'push': transport_status(request.user)})
