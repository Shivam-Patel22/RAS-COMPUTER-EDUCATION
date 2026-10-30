from django.contrib import admin
from .models import Course, CourseOffer

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'duration', 'fee', 'is_featured', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('category', 'is_featured', 'created_at')
    list_editable = ('category', 'is_featured')


@admin.register(CourseOffer)
class CourseOfferAdmin(admin.ModelAdmin):
    list_display = ('title', 'badge', 'course', 'discount', 'status', 'computed_status', 'priority', 'start_date', 'end_date', 'created_at')
    list_filter = ('status', 'course', 'created_at')
    search_fields = ('title', 'description', 'discount', 'badge')
    list_editable = ('status', 'priority')
