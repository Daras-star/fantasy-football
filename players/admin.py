from django.contrib import admin

from .models import Fixture, Gameweek, Player, PlayerFixtureStats, Position, Team


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name")
    search_fields = ("name", "short_name")


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name")


@admin.register(Gameweek)
class GameweekAdmin(admin.ModelAdmin):
    list_display = ("name", "deadline", "finished", "is_current", "is_next")


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("web_name", "team", "position", "price", "total_points", "status")
    list_filter = ("position", "team", "status")
    search_fields = ("web_name", "first_name", "last_name")
    list_select_related = ("team", "position")


@admin.register(Fixture)
class FixtureAdmin(admin.ModelAdmin):
    list_display = ("__str__", "gameweek", "kickoff", "home_score", "away_score", "finished")
    list_filter = ("gameweek", "finished")
    list_select_related = ("home_team", "away_team", "gameweek")


@admin.register(PlayerFixtureStats)
class PlayerFixtureStatsAdmin(admin.ModelAdmin):
    list_display = ("player", "fixture", "minutes", "goals_scored", "assists", "bonus")
    list_filter = ("fixture__gameweek",)
    search_fields = ("player__web_name",)
    list_select_related = ("player", "fixture__home_team", "fixture__away_team")