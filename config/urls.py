from django.contrib import admin
from django.urls import include, path

from fantasy.leaderboard_views import leaderboard
from players.home_views import home

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('my-team/', include('fantasy.urls')),
    path('players/', include('players.urls')),
    path('leagues/', include('leagues.urls')),
    path('leaderboard/', leaderboard, name='leaderboard'),
    path('', home, name='home'),
]