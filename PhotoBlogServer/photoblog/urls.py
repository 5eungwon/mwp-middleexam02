from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from blog import views

router = DefaultRouter()
router.register('Post', views.PostViewSet, basename='post')
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api-token-auth/', views.obtain_token, name='api-token-auth'),
    path('api_root/', include(router.urls)),
    path('health/', views.health, name='health'),
    path('accounts/login/', LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
    path('', views.dashboard, name='dashboard'),
    path('posts/new/', views.upload, name='upload'),
    path('posts/<int:pk>/', views.detail, name='detail'),
    path('posts/<int:pk>/acknowledge/', views.acknowledge, name='acknowledge'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
