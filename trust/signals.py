"""
trust/signals.py
----------------
Auto-recalculate trust score whenever:
    1. A review is submitted
    2. A booking is marked completed
    3. A tutor's UserProfile is updated
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# ==============================================================================
# Signal 1 — Recalculate after a review is saved
# ==============================================================================

@receiver(post_save, sender='reviews.Review')
def on_review_saved(sender, instance, created, **kwargs):
    """
    Fires whenever a Review is created or updated.
    Recalculates trust score for the tutor being reviewed.
    """
    try:
        from trust.calculator import recalculate_trust_score
        recalculate_trust_score(instance.tutor)
        logger.info(f"[TrustScore] Recalculated after review — tutor: {instance.tutor.username}")
    except Exception as e:
        logger.error(f"[TrustScore] Failed after review save — {e}")


# ==============================================================================
# Signal 2 — Recalculate after a booking is completed
# ==============================================================================

@receiver(post_save, sender='session.Booking')
def on_booking_saved(sender, instance, created, **kwargs):
    """
    Fires whenever a Booking is saved.
    Only recalculates when status is 'completed'.
    """
    if instance.status != 'completed':
        return

    try:
        from trust.calculator import recalculate_trust_score
        tutor = instance.session.tutor
        recalculate_trust_score(tutor)
        logger.info(f"[TrustScore] Recalculated after booking completed — tutor: {tutor.username}")
    except Exception as e:
        logger.error(f"[TrustScore] Failed after booking save — {e}")


# ==============================================================================
# Signal 3 — Recalculate after UserProfile is updated
# ==============================================================================

@receiver(post_save, sender='users.UserProfile')
def on_profile_saved(sender, instance, created, **kwargs):
    """
    Fires whenever a UserProfile is saved.
    Recalculates trust score so profile completion stays up to date.
    Skips if we're only updating trust_score itself (prevents infinite loop).
    """
    # Prevent infinite loop — calculator calls profile.save(update_fields=['trust_score'])
    # If only trust_score was updated, skip recalculation
    update_fields = kwargs.get('update_fields')
    if update_fields and set(update_fields) == {'trust_score'}:
        return

    try:
        from trust.calculator import recalculate_trust_score
        recalculate_trust_score(instance.user)
        logger.info(f"[TrustScore] Recalculated after profile update — user: {instance.user.username}")
    except Exception as e:
        logger.error(f"[TrustScore] Failed after profile save — {e}")