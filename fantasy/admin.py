from django.contrib import admin

from .models import ChipPlay, FantasyTeam, GameweekScore, SquadPlayer


class SquadPlayerInline(admin.TabularInline):
    model = SquadPlayer
    extra = 0


@admin.register(FantasyTeam)
class FantasyTeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'total_points')
    inlines = [SquadPlayerInline]


admin.site.register(GameweekScore)
admin.site.register(ChipPlay)