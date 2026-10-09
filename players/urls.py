from django.urls import path

from . import views
from .fixture_views import fixtures
from .table_views import league_table

app_name = "players"

urlpatterns = [
    path('', views.player_list, name='player_list'),
    path('<int:pk>/', views.player_detail, name='player_detail'),
    path("fixtures/", fixtures, name="fixtures"),
    path("table/", league_table, name="table"),
]