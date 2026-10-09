import secrets

from django.conf import settings
from django.db import models

from fantasy.models import FantasyTeam

# No 0, O, 1 or I, which are easy to mix up when typing a code
JOIN_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
JOIN_CODE_LENGTH = 6


def unique_join_code():
    """A random join code that no existing league uses."""
    while True:
        code = ''.join(secrets.choice(JOIN_CODE_ALPHABET) for _ in range(JOIN_CODE_LENGTH))
        if not League.objects.filter(join_code=code).exists():
            return code


class League(models.Model):
    name = models.CharField(max_length=50)
    join_code = models.CharField(
        max_length=JOIN_CODE_LENGTH, unique=True, default=unique_join_code, editable=False
    )
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_leagues'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class LeagueMember(models.Model):
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='members')
    team = models.ForeignKey(FantasyTeam, on_delete=models.CASCADE, related_name='league_memberships')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['joined_at']
        constraints = [
            models.UniqueConstraint(fields=['league', 'team'], name='unique_team_per_league'),
        ]

    def __str__(self):
        return f"{self.team} in {self.league}"