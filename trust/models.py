from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User


class TrustScore(models.Model):
    """
    Stores the computed trust score for a tutor.
    One record per tutor — created on first calculation, updated on recalculation.
    """

    LABEL_CHOICES = [
        ('new',         'New Tutor'),
        ('beginner',    'Beginner'),
        ('developing',  'Developing'),
        ('established', 'Established'),
        ('expert',      'Expert'),
        ('master',      'Master Tutor'),
    ]

    tutor = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='trust_score',
    )

    # ── Final Score ──────────────────────────────────────────────
    score       = models.FloatField(default=0.0)   # 0–100
    label       = models.CharField(
        max_length=20,
        choices=LABEL_CHOICES,
        default='new',
    )

    # ── Sub-scores (for profile breakdown display) ────────────────
    # Session Performance  (max 30)
    session_performance_score = models.FloatField(default=0.0)
    completion_rate_score     = models.FloatField(default=0.0)   # max 10
    sessions_taught_score     = models.FloatField(default=0.0)   # max  8
    students_taught_score     = models.FloatField(default=0.0)   # max  8
    cancellation_rate_score   = models.FloatField(default=0.0)   # max  4

    # Review Metrics  (max 28)
    review_metrics_score      = models.FloatField(default=0.0)
    bayesian_rating_score     = models.FloatField(default=0.0)   # max 12
    review_count_score        = models.FloatField(default=0.0)   # max  7
    recommend_pct_score       = models.FloatField(default=0.0)   # max  6
    repeat_booking_score      = models.FloatField(default=0.0)   # max  3

    # NLP / AI Quality  (max 25)
    nlp_score                 = models.FloatField(default=0.0)
    vader_avg_score           = models.FloatField(default=0.0)   # max  6
    vader_consistency_score   = models.FloatField(default=0.0)   # max  4
    bio_skill_match_score     = models.FloatField(default=0.0)   # max  6
    bio_detail_score          = models.FloatField(default=0.0)   # max  4
    profile_genuineness_score = models.FloatField(default=0.0)   # max  5

    # Profile Completion  (max 17)
    profile_completion_score  = models.FloatField(default=0.0)

    # Penalty
    duplicate_review_penalty  = models.FloatField(default=0.0)   # max -5

    # ── Raw Data Snapshots (informational / debugging) ────────────
    total_sessions_taught  = models.IntegerField(default=0)
    total_students_taught  = models.IntegerField(default=0)
    completion_rate_pct    = models.FloatField(default=0.0)    # 0–100
    cancellation_rate_pct  = models.FloatField(default=0.0)    # 0–100
    avg_rating             = models.FloatField(default=0.0)    # 1–5
    total_reviews          = models.IntegerField(default=0)
    recommend_pct          = models.FloatField(default=0.0)    # 0–100
    repeat_booking_count   = models.IntegerField(default=0)
    vader_avg_compound     = models.FloatField(default=0.0)    # -1 to 1
    vader_std_dev          = models.FloatField(default=0.0)

    # ── Timestamps ────────────────────────────────────────────────
    calculated_at  = models.DateTimeField(auto_now=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name       = 'Trust Score'
        verbose_name_plural = 'Trust Scores'

    def __str__(self):
        return f"{self.tutor.username} — {self.score:.1f} ({self.get_label_display()})"

    # ── Helpers ───────────────────────────────────────────────────
    @property
    def label_emoji(self):
        emoji_map = {
            'new':         '🆕',
            'beginner':    '⭐',
            'developing':  '⭐⭐',
            'established': '⭐⭐⭐',
            'expert':      '⭐⭐⭐⭐',
            'master':      '🏆',
        }
        return emoji_map.get(self.label, '')

    @property
    def label_display_full(self):
        return f"{self.get_label_display()} {self.label_emoji}"

    @property
    def score_int(self):
        """Rounded integer score — for display."""
        return round(self.score)

    @property
    def score_percentage(self):
        """For progress-bar width in templates."""
        return min(self.score, 100)

    @staticmethod
    def get_label_for_score(score: float) -> str:
        """Map a numeric score to its label key."""
        if score <= 20:
            return 'new'
        elif score <= 40:
            return 'beginner'
        elif score <= 60:
            return 'developing'
        elif score <= 75:
            return 'established'
        elif score <= 90:
            return 'expert'
        else:
            return 'master'