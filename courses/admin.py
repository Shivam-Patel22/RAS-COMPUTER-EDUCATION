from django.contrib import admin
from django.db import models
from django.db.models import Q
from .models import Course, CourseOffer, CourseCategory

@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon', 'display_order', 'is_active', 'subcourses_count_display', 'created_at')
    list_editable = ('display_order', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    fields = ('name', 'slug', 'icon', 'description', 'duration', 'display_order', 'is_active')

    def subcourses_count_display(self, obj):
        all_cat_names = set(CourseCategory.objects.values_list('name', flat=True))
        count = Course.objects.filter(
            Q(category_ref=obj) | Q(category=obj.slug)
        ).exclude(name__in=all_cat_names).count()
        return f"{count} sub-courses"
    subcourses_count_display.short_description = 'Sub-Courses'


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'category_ref', 'duration', 'fee', 'is_featured', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('category_ref', 'is_featured', 'created_at')
    list_editable = ('category_ref', 'is_featured')
    fields = ('name', 'category_ref', 'description', 'duration', 'fee', 'image', 'is_featured', 'slug')


@admin.register(CourseOffer)
class CourseOfferAdmin(admin.ModelAdmin):
    list_display = ('title', 'badge', 'course', 'discount', 'status', 'computed_status', 'priority', 'start_date', 'end_date', 'created_at')
    list_filter = ('status', 'course', 'created_at')
    search_fields = ('title', 'description', 'discount', 'badge')
    list_editable = ('status', 'priority')
