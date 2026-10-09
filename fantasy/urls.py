from django.urls import path

from . import chip_views, views

urlpatterns = [
    path('', views.my_team, name='my_team'),
    path('squad/', views.pick_squad, name='pick_squad'),
    path('lineup/', views.pick_lineup, name='pick_lineup'),
    path('chips/', chip_views.chip_list, name='chips'),
    path('chips/play/', chip_views.play_chip, name='play_chip'),
    path('chips/cancel/', chip_views.cancel_chip, name='cancel_chip'),
]