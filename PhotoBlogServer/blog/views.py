from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.db import connection
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
from .models import Post
from .serializers import PostSerializer

class LoginThrottle(AnonRateThrottle):
    scope = 'login'

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def obtain_token(request):
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
        serializer.save(author=self.request.user)

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
        messages.success(request, '사진이 등록되었습니다.')
        return redirect('detail', pk=post.pk)
    return render(request, 'blog/upload.html', {'form': form})
