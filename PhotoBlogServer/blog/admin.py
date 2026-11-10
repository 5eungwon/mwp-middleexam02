from django.contrib import admin
from .models import Post, DetectionSettings, PushDevice, PushDelivery

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'created_date', 'zone_name', 'acknowledged']
    list_filter = ['acknowledged', 'created_date']
    search_fields = ['title', 'text', 'author__username']

admin.site.register(DetectionSettings)

@admin.register(PushDevice)
class PushDeviceAdmin(admin.ModelAdmin):
    list_display = ['installation_id', 'owner', 'active', 'updated_at']
    exclude = ['token']
    readonly_fields = ['installation_id', 'binding_id', 'owner', 'updated_at']
    def has_add_permission(self, request):
        return False

@admin.register(PushDelivery)
class PushDeliveryAdmin(admin.ModelAdmin):
    list_display = ['post', 'device', 'state', 'attempts', 'error_code', 'updated_at']
    readonly_fields = ['post', 'device', 'attempts', 'updated_at']
