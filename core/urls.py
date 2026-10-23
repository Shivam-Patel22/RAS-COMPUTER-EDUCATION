from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('about/live-sync/', views.about_live_sync, name='about_live_sync'),
    path('contact/', views.contact, name='contact'),
]
