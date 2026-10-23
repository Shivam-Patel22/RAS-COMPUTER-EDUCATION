from django.urls import path
from . import views

app_name = 'certificates'

urlpatterns = [
    path('verify-certificate/', views.verify, name='verify'),
    path('verify/', views.verify, name='verify_alt'),
    path('verify-certificate/download/<path:certificate_id>/', views.download_certificate_pdf, name='download_certificate_pdf'),
    path('verify-certificate/<path:certificate_id>/', views.verify, name='verify_direct'),
    path('verify/<path:certificate_id>/', views.verify, name='verify_alt_direct'),
]
