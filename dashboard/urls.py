from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.admin_login, name='login'),
    path('logout/', views.admin_logout, name='logout'),
    path('dashboard/', views.index, name='index'),
    path('courses/', views.manage_courses, name='manage_courses'),
    path('courses/add/', views.add_course, name='add_course'),
    path('courses/<int:pk>/edit/', views.edit_course, name='edit_course'),
    path('courses/<int:pk>/delete/', views.delete_course, name='delete_course'),
    path('courses/<int:pk>/toggle-featured/', views.toggle_course_featured, name='toggle_course_featured'),
    path('certificates/', views.manage_certificates, name='manage_certificates'),
    path('certificates/add/', views.add_certificate, name='add_certificate'),
    path('certificates/<int:pk>/edit/', views.edit_certificate, name='edit_certificate'),
    path('certificates/<int:pk>/revoke/', views.revoke_certificate, name='revoke_certificate'),
    path('certificates/<int:pk>/verify/', views.verify_certificate, name='verify_certificate'),
    path('certificates/<int:pk>/print/', views.print_certificate, name='print_certificate'),
    path('certificates/download-zip/', views.download_certificates_zip, name='download_certificates_zip'),
    path('certificates/next-id/', views.get_next_certificate_id_api, name='get_next_certificate_id'),
    path('verify-certificate/', views.admin_verify_search, name='admin_verify_search'),



    path('inquiries/', views.manage_inquiries, name='manage_inquiries'),
    path('inquiries/<int:pk>/toggle-read/', views.toggle_inquiry_read, name='toggle_inquiry_read'),
    path('inquiries/<int:pk>/delete/', views.delete_inquiry, name='delete_inquiry'),
    path('inquiries/<int:pk>/followup/', views.add_inquiry_followup, name='add_inquiry_followup'),
    path('inquiries/<int:pk>/followups/', views.get_inquiry_followups, name='get_inquiry_followups'),
    path('offers/', views.manage_offers, name='manage_offers'),
    path('offers/add/', views.add_offer, name='add_offer'),
    path('offers/<int:pk>/edit/', views.edit_offer, name='edit_offer'),
    path('offers/<int:pk>/toggle-status/', views.toggle_offer_status, name='toggle_offer_status'),
    path('offers/<int:pk>/delete/', views.delete_offer, name='delete_offer'),
    path('students/', views.active_students, name='active_students'),
    path('students/add/', views.add_student, name='add_student'),
    path('students/<int:pk>/toggle-status/', views.toggle_student_status, name='toggle_student_status'),
    path('students/<int:pk>/delete/', views.delete_student, name='delete_student'),
    path('about/edit/', views.edit_about, name='edit_about'),
    path('contact/edit/', views.edit_contact, name='edit_contact'),
    path('settings/', views.account_settings, name='account_settings'),
    path('settings/change-username/', views.change_username, name='change_username'),
    path('settings/change-password/', views.change_password, name='change_password'),
]
