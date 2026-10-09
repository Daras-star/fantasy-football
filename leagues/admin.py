from django.contrib import admin

from .models import League, LeagueMember


class LeagueMemberInline(admin.TabularInline):
    model = LeagueMember
    extra = 0


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    list_display = ('name', 'join_code', 'admin', 'created_at')
    readonly_fields = ('join_code',)
    inlines = [LeagueMemberInline]