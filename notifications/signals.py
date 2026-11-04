"""
notifications/signals.py
------------------------
Auto-create in-app notifications on key events.

Events handled:
    1. Booking saved       → session_booked, session_cancelled, credits_received
    2. Review saved        → review_received
    3. Message saved       → message_received
    4. UserProfile saved   → (profile update hook if needed)

Reschedule notifications are created directly from views
since they don't map cleanly to a single model save event.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# ==============================================================================
# Signal 1 — Booking saved
# ==============================================================================

@receiver(post_save, sender='session.Booking')
def on_booking_saved(sender, instance, created, **kwargs):
    try:
        from notifications.models import Notification
        from session.models import Booking

        booking = instance
        session = booking.session
        tutor   = session.tutor
        learner = booking.learner

        # ── New booking created → notify tutor ────────────────────────
        if created and booking.status == 'confirmed':
            Notification.create(
                recipient=tutor,
                notification_type='session_booked',
                title='New Session Booking',
                message=f'{learner.get_full_name()} booked your session "{session.title}" on {session.date.strftime("%b %d, %Y")} at {session.start_time.strftime("%I:%M %p")}.',
                link=f'/my-sessions/',
            )

        # ── Booking cancelled → notify tutor and learner ───────────────
        if not created and booking.status == 'cancelled':
            update_fields = kwargs.get('update_fields')

            # Notify tutor
            Notification.create(
                recipient=tutor,
                notification_type='session_cancelled',
                title='Booking Cancelled',
                message=f'{learner.get_full_name()} cancelled their booking for "{session.title}" on {session.date.strftime("%b %d, %Y")}.',
                link=f'/my-sessions/',
            )

        # ── Booking completed → credits received → notify tutor ────────
        if not created and booking.status == 'completed':
            Notification.create(
                recipient=tutor,
                notification_type='credits_received',
                title='Credits Received',
                message=f'You received {booking.credits_paid} credits for completing "{session.title}" with {learner.get_full_name()}.',
                link=f'/wallet/',
            )

    except Exception as e:
        logger.error(f"[Notifications] Booking signal error: {e}")


# ==============================================================================
# Signal 2 — Review saved
# ==============================================================================

@receiver(post_save, sender='reviews.Review')
def on_review_saved(sender, instance, created, **kwargs):
    if not created:
        return

    try:
        from notifications.models import Notification

        review  = instance
        tutor   = review.tutor
        reviewer = review.reviewer
        stars   = '⭐' * review.rating

        Notification.create(
            recipient=tutor,
            notification_type='review_received',
            title='New Review Received',
            message=f'{reviewer.get_full_name()} left you a {review.rating}-star review {stars} for "{review.session.title}".',
            link=f'/profile/{tutor.pk}/',
        )

    except Exception as e:
        logger.error(f"[Notifications] Review signal error: {e}")


# ==============================================================================
# Signal 3 — Message saved
# ==============================================================================
# DISABLED: Message notifications removed in favor of dedicated message counter
# on navbar. Messages are tracked via the unread message badge on the message
# button, not in the general notification section.
#
# @receiver(post_save, sender='messaging.Message')
# def on_message_saved(sender, instance, created, **kwargs):
#     if not created:
#         return
#
#     try:
#         from notifications.models import Notification
#
#         message      = instance
#         sender_user  = message.sender
#         conversation = message.conversation
#
#         # Determine recipient (the other participant)
#         if conversation.participant_1 == sender_user:
#             recipient = conversation.participant_2
#         else:
#             recipient = conversation.participant_1
#
#         Notification.create(
#             recipient=recipient,
#             notification_type='message_received',
#             title='New Message',
#             message=f'{sender_user.get_full_name()} sent you a message.',
#             link=f'/messages/{conversation.pk}/',
#         )
#
#     except Exception as e:
#         logger.error(f"[Notifications] Message signal error: {e}")