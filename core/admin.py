from django.contrib import admin
from .models import Center, Visitor, Queue

@admin.register(Center)
class CenterAdmin(admin.ModelAdmin):
    list_display = ('user','name', 'phone', 'latitude', 'longitude')
    search_fields = ('name', 'phone')


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone')
    search_fields = ('name', 'phone')


@admin.register(Queue)
class QueueAdmin(admin.ModelAdmin):
    list_display = ('visitor', 'center', 'position', 'status', 'created_at')
    list_filter = ('center', 'status')
    search_fields = ('visitor__name', 'center__name')
