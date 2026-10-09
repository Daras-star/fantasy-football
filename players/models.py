from django.db import models


class Team(models.Model):
    """A real-life club."""

    fpl_id = models.PositiveIntegerField(unique=True)  # the club's id in the data feed
    name = models.CharField(max_length=60)
    short_name = models.CharField(max_length=5)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Position(models.Model):
    """Goalkeeper, Defender, Midfielder or Forward."""

    fpl_id = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=30)
    short_name = models.CharField(max_length=3)  # GKP, DEF, MID, FWD

    class Meta:
        ordering = ["fpl_id"]

    def __str__(self):
        return self.short_name


class Gameweek(models.Model):
    """One round of Premier League matches. A season has 38."""

    number = models.PositiveSmallIntegerField(unique=True)
    name = models.CharField(max_length=30)
    deadline = models.DateTimeField()  # the last moment to change your team
    finished = models.BooleanField(default=False)
    is_current = models.BooleanField(default=False)
    is_next = models.BooleanField(default=False)

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return self.name


class Player(models.Model):
    STATUS_CHOICES = [
        ("a", "Available"),
        ("d", "Doubtful"),
        ("i", "Injured"),
        ("s", "Suspended"),
        ("u", "Unavailable"),
        ("n", "Not in squad"),
    ]

    fpl_id = models.PositiveIntegerField(unique=True)
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    web_name = models.CharField(max_length=60)  # the short name used in lists
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="players")
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="players")
    price = models.DecimalField(max_digits=4, decimal_places=1)  # in millions, e.g. 6.5
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default="a")
    news = models.TextField(blank=True)  # injury or availability news
    total_points = models.IntegerField(default=0)  # points so far this season, from the feed

    class Meta:
        ordering = ["-total_points", "web_name"]

    def __str__(self):
        return self.web_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Fixture(models.Model):
    """A real-life match."""

    fpl_id = models.PositiveIntegerField(unique=True)
    gameweek = models.ForeignKey(
        Gameweek, null=True, blank=True, on_delete=models.SET_NULL, related_name="fixtures"
    )
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="home_fixtures")
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="away_fixtures")
    kickoff = models.DateTimeField(null=True, blank=True)  # empty until the match is scheduled
    home_score = models.PositiveSmallIntegerField(null=True, blank=True)
    away_score = models.PositiveSmallIntegerField(null=True, blank=True)
    started = models.BooleanField(default=False)
    finished = models.BooleanField(default=False)

    class Meta:
        ordering = ["kickoff", "fpl_id"]

    def __str__(self):
        return f"{self.home_team.short_name} v {self.away_team.short_name}"


class PlayerFixtureStats(models.Model):
    """What one player did in one match. Fantasy points are worked out from these."""

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="match_stats")
    fixture = models.ForeignKey(Fixture, on_delete=models.CASCADE, related_name="player_stats")
    minutes = models.PositiveSmallIntegerField(default=0)
    goals_scored = models.PositiveSmallIntegerField(default=0)
    assists = models.PositiveSmallIntegerField(default=0)
    clean_sheets = models.PositiveSmallIntegerField(default=0)
    goals_conceded = models.PositiveSmallIntegerField(default=0)
    own_goals = models.PositiveSmallIntegerField(default=0)
    penalties_saved = models.PositiveSmallIntegerField(default=0)
    penalties_missed = models.PositiveSmallIntegerField(default=0)
    yellow_cards = models.PositiveSmallIntegerField(default=0)
    red_cards = models.PositiveSmallIntegerField(default=0)
    saves = models.PositiveSmallIntegerField(default=0)
    bonus = models.PositiveSmallIntegerField(default=0)
    defensive_contribution = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name_plural = "player fixture stats"
        constraints = [
            models.UniqueConstraint(
                fields=["player", "fixture"], name="one_stats_row_per_player_per_fixture"
            ),
        ]

    def __str__(self):
        return f"{self.player} in {self.fixture}"