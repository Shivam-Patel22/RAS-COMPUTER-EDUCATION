from django.contrib import admin
from .models import Inquiry, InquiryFollowUp, ContactContent, AboutContent, JustdialReview

@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'subject', 'course', 'created_at', 'is_read')
    list_filter = ('is_read', 'created_at', 'course')
    search_fields = ('name', 'phone', 'email', 'message', 'subject')
    list_editable = ('is_read',)
    readonly_fields = ('created_at',)

@admin.register(InquiryFollowUp)
class InquiryFollowUpAdmin(admin.ModelAdmin):
    list_display = ('inquiry', 'admin_user', 'status', 'callback_at', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('inquiry__name', 'message', 'admin_user__username')
    readonly_fields = ('created_at',)

@admin.register(ContactContent)
class ContactContentAdmin(admin.ModelAdmin):
    list_display = ('phone', 'whatsapp_number', 'email', 'instagram_username', 'facebook_name', 'updated_at')
    fieldsets = (
        ('Contact Information', {
            'fields': ('phone', 'whatsapp_number', 'email', 'address', 'working_hours')
        }),
        ('Social Media Links', {
            'fields': ('instagram_username', 'instagram_url', 'facebook_name', 'facebook_url'),
            'description': 'Configure official Instagram and Facebook handles and URLs. Leave blank to hide on public pages.'
        }),
        ('Location Map', {
            'fields': ('map_embed_url',)
        }),
    )


@admin.register(AboutContent)
class AboutContentAdmin(admin.ModelAdmin):
    list_display = ('heading', 'updated_at')


@admin.register(JustdialReview)
class JustdialReviewAdmin(admin.ModelAdmin):
    list_display = ('reviewer_name', 'rating', 'review_date', 'display_order', 'is_active')
    list_editable = ('display_order', 'is_active')
    list_filter = ('is_active', 'rating')
    search_fields = ('reviewer_name', 'review_text')

