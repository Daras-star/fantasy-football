from django.conf import settings
from django.db import models

from players.models import Gameweek, Player

from .chips import CHIPS


class FantasyTeam(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='fantasy_team'
    )
    name = models.CharField(max_length=50)
    total_points = models.IntegerField(default=0)
    free_transfers = models.PositiveSmallIntegerField(default=1)
    bank = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-total_points', 'name']

    def __str__(self):
        return self.name


class SquadPlayer(models.Model):
    """A player in the team's CURRENT squad (the one the manager edits)."""
    fantasy_team = models.ForeignKey(FantasyTeam, on_delete=models.CASCADE, related_name='squad')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='squad_entries')
    is_starter = models.BooleanField(default=False)
    is_captain = models.BooleanField(default=False)
    is_vice_captain = models.BooleanField(default=False)
    bought_price = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['fantasy_team', 'player'], name='unique_player_per_team'),
        ]

    def __str__(self):
        return f"{self.fantasy_team} - {self.player}"


class GameweekScore(models.Model):
    """A team's frozen lineup for one gameweek, and the points it earned."""
    fantasy_team = models.ForeignKey(FantasyTeam, on_delete=models.CASCADE, related_name='scores')
    gameweek = models.ForeignKey(Gameweek, on_delete=models.CASCADE, related_name='team_scores')
    points = models.IntegerField(default=0)
    transfer_cost = models.IntegerField(default=0)
    bank = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)

    class Meta:
        ordering = ['gameweek__number']
        constraints = [
            models.UniqueConstraint(fields=['fantasy_team', 'gameweek'], name='unique_team_gameweek'),
        ]

    def __str__(self):
        return f"{self.fantasy_team} - GW{self.gameweek.number}: {self.points}"


class GameweekPick(models.Model):
    """One player's role in a frozen lineup (copied from the squad at the deadline)."""
    score = models.ForeignKey(GameweekScore, on_delete=models.CASCADE, related_name='picks')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='gameweek_picks')
    is_starter = models.BooleanField(default=False)
    is_captain = models.BooleanField(default=False)
    is_vice_captain = models.BooleanField(default=False)
    bought_price = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['score', 'player'], name='unique_player_per_frozen_lineup'),
        ]

    def __str__(self):
        return f"{self.score} - {self.player}"


class ChipPlay(models.Model):
    """A chip a team has switched on for one gameweek."""
    fantasy_team = models.ForeignKey(FantasyTeam, on_delete=models.CASCADE, related_name='chip_plays')
    gameweek = models.ForeignKey(Gameweek, on_delete=models.CASCADE, related_name='chip_plays')
    chip = models.CharField(
        max_length=2, choices=[(code, info['name']) for code, info in CHIPS.items()]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['gameweek__number']
        constraints = [
            models.UniqueConstraint(
                fields=['fantasy_team', 'gameweek'], name='one_chip_per_team_per_gameweek'
            ),
        ]

    def __str__(self):
        return f"{self.fantasy_team} - {self.get_chip_display()} in GW{self.gameweek.number}"