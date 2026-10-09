from django.urls import path

from . import views

app_name = 'leagues'

urlpatterns = [
    path('', views.league_list, name='list'),
    path('create/', views.create_league, name='create'),
    path('join/', views.join_league, name='join'),
    path('<int:pk>/', views.league_detail, name='detail'),
    path('<int:pk>/leave/', views.leave_league, name='leave'),
    path('<int:pk>/delete/', views.delete_league, name='delete'),
]