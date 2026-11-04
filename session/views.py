from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.db import models
from core.models import Transaction, Wallet
from session.forms import SessionForm, RescheduleForm
from session.models import Booking, Session
from session.zoom_utils import create_zoom_meeting
from skills.models import Skill


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def _transfer_credits(booking):
    try:
        learner_wallet = booking.learner.wallet
        tutor_wallet   = booking.session.tutor.wallet
    except Exception:
        return
    learner_wallet.unfreeze_and_transfer(booking.credits_paid, tutor_wallet)
    Transaction.objects.create(
        wallet=learner_wallet,
        transaction_type='session_payment',
        amount=booking.credits_paid,
        description=f'Payment for completed session: {booking.session.title}',
        balance_after=learner_wallet.balance,
    )
    Transaction.objects.create(
        wallet=tutor_wallet,
        transaction_type='tutor_earning',
        amount=booking.credits_paid,
        description=f'Earned from session: {booking.session.title}',
        balance_after=tutor_wallet.balance,
    )


def _refund_credits(booking):
    """Refund frozen credits back to learner."""
    try:
        learner_wallet = booking.learner.wallet
    except Exception:
        return
    learner_wallet.unfreeze_and_refund(booking.credits_paid)
    Transaction.objects.create(
        wallet=learner_wallet,
        transaction_type='refund',
        amount=booking.credits_paid,
        description=f'Refund — session cancelled: {booking.session.title}',
        balance_after=learner_wallet.balance,
    )


def _check_auto_complete():
    now   = timezone.now()
    today = now.date()

    # 1. Auto-complete overdue in_progress
    overdue_bookings = Booking.objects.filter(
        status='in_progress',
        tutor_confirmed=True,
        learner_confirmed=False,
        auto_complete_at__lte=now,
    ).select_related('session', 'learner', 'session__tutor')

    for booking in overdue_bookings:
        try:
            _transfer_credits(booking)
            booking.learner_confirmed = True
            booking.status            = 'pending_review'
            booking.save()
            if not booking.session.bookings.filter(status='in_progress').exists():
                booking.session.status = 'completed'
                booking.session.save()
        except Exception:
            continue

    # 2. Auto-cancel confirmed bookings where session is cancelled or time passed
    past_confirmed = Booking.objects.filter(
        status='confirmed',
        reschedule_status='none',
    ).select_related('session', 'learner')

    for booking in past_confirmed:
        try:
            should_cancel = False

            # Case 1: Session was directly cancelled
            if booking.session.status == 'cancelled':
                should_cancel = True

            # Case 2: Session time has passed
            else:
                session_end = timezone.make_aware(
                    datetime.combine(booking.session.date, booking.session.end_time)
                )
                if now > session_end:
                    should_cancel = True

            if should_cancel:
                _refund_credits(booking)
                booking.status = 'cancelled'
                booking.save()
                # Notify learner
                try:
                    from notifications.models import Notification
                    Notification.create(
                        recipient=booking.learner,
                        notification_type='session_cancelled',
                        title='Session Auto-Cancelled',
                        message=f'Your session "{booking.session.title}" was automatically cancelled. {booking.credits_paid} credits have been refunded.',
                        link='/my-sessions/',
                    )
                except Exception:
                    pass

        except Exception:
            continue

   # 3. Auto-process reschedule deadline (1 hour before session start)
    # Find ALL sessions with pending reschedule bookings (including future dates)
    pending_reschedule_bookings = Booking.objects.filter(
        status='confirmed',
        reschedule_status='pending',
    ).select_related('session', 'learner', 'session__tutor')

    processed_sessions = set()

    for booking in pending_reschedule_bookings:
        try:
            session = booking.session
            if session.pk in processed_sessions:
                continue

            session_start = timezone.make_aware(
                datetime.combine(session.date, session.start_time)
            )
            deadline = session_start - timedelta(hours=1)

            if now >= deadline:
                processed_sessions.add(session.pk)

                # Get all bookings for this session with reschedule pending/accepted
                all_reschedule_bookings = Booking.objects.filter(
                    session=session,
                    status='confirmed',
                    reschedule_status__in=['pending', 'accepted'],
                ).select_related('learner')

                # Get proposed times from session directly
                proposed_date       = session.proposed_date
                proposed_start_time = session.proposed_start_time
                proposed_end_time   = session.proposed_end_time
                accepted_bookings = all_reschedule_bookings.filter(reschedule_status='accepted')
                pending_bookings  = all_reschedule_bookings.filter(reschedule_status='pending')

                if accepted_bookings.exists() and proposed_date:
                    # At least one accepted → reschedule session
                    session.date       = proposed_date
                    session.start_time = proposed_start_time
                    session.end_time   = proposed_end_time
                    session.proposed_date       = None
                    session.proposed_start_time = None
                    session.proposed_end_time   = None
                    session.save()

                    # Reset accepted bookings
                    accepted_bookings.update(reschedule_status='none')

                    # Cancel pending (no-response) bookings
                    for b in pending_bookings:
                        try:
                            _refund_credits(b)
                            b.reschedule_status = 'declined'
                            b.status            = 'cancelled'
                            b.save()
                        except Exception:
                            continue

                    # Notify tutor
                    _send_reschedule_processed_email(session, accepted=True)

                else:
                    # Nobody accepted → cancel only pending bookings
                    # accepted bookings stay confirmed (they already accepted)
                    for b in pending_bookings:
                        try:
                            _refund_credits(b)
                            b.reschedule_status = 'declined'
                            b.status            = 'cancelled'
                            b.save()
                        except Exception:
                            continue

                    # Check if any accepted bookings remain
                    still_accepted = Booking.objects.filter(
                        session=session,
                        reschedule_status='accepted',
                        status='confirmed',
                    )

                    if still_accepted.exists() and proposed_date:
                        # Some accepted → reschedule session for them
                        session.date            = proposed_date
                        session.start_time      = proposed_start_time
                        session.end_time        = proposed_end_time
                        session.proposed_date       = None
                        session.proposed_start_time = None
                        session.proposed_end_time   = None
                        session.save()
                        still_accepted.update(reschedule_status='none')
                        _send_reschedule_processed_email(session, accepted=True)
                    else:
                        # Nobody accepted at all → cancel session entirely
                        remaining = Booking.objects.filter(
                            session=session,
                            status='confirmed',
                        )
                        for b in remaining:
                            try:
                                _refund_credits(b)
                                b.reschedule_status = 'declined'
                                b.status            = 'cancelled'
                                b.save()
                            except Exception:
                                continue

                        session.status              = 'cancelled'
                        session.proposed_date       = None
                        session.proposed_start_time = None
                        session.proposed_end_time   = None
                        session.save()
                        _send_reschedule_processed_email(session, accepted=False)
                        
        except Exception:
            continue

    # 4. Auto-cancel empty sessions where start time passed
    past_empty_sessions = Session.objects.filter(
        status='upcoming',
    ).exclude(date__gt=today)

    for session in past_empty_sessions:
        try:
            session_start = timezone.make_aware(
                datetime.combine(session.date, session.start_time)
            )
            if now > session_start:
                has_active = session.bookings.filter(
                    status__in=['confirmed', 'in_progress']
                ).exists()
                if not has_active:
                    session.status = 'cancelled'
                    session.save()
        except Exception:
            continue


def _send_tutor_start_email(booking):
    tutor = booking.session.tutor
    send_mail(
        subject=f'⏰ Your session "{booking.session.title}" starts in 15 minutes!',
        message=f"""Hi {tutor.get_full_name()},

Your session is about to start!

📅 Date   : {booking.session.date.strftime('%A, %B %d, %Y')}
⏰ Time   : {booking.session.start_time.strftime('%I:%M %p')} – {booking.session.end_time.strftime('%I:%M %p')}
👤 Learner: {booking.learner.get_full_name()}
🎯 Skill  : {booking.session.skill.name}

Please log in to Skillify and go to My Sessions to start your session.

Best regards,
Skillify Team
""",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[tutor.email],
        fail_silently=True,
    )
    booking.tutor_email_sent = True
    booking.save(update_fields=['tutor_email_sent'])

    # ── In-app notification ──
    try:
        from notifications.models import Notification
        Notification.create(
            recipient=tutor,
            notification_type='session_starting',
            title='Session Starting Soon',
            message=f'Your session "{booking.session.title}" with {booking.learner.get_full_name()} starts at {booking.session.start_time.strftime("%I:%M %p")}. Go to My Sessions to start it.',
            link='/my-sessions/',
        )
    except Exception:
        pass


def _send_learner_join_email(booking):
    learner = booking.learner
    send_mail(
        subject=f'🚀 Your session "{booking.session.title}" is starting now!',
        message=f"""Hi {learner.get_full_name()},

Your tutor {booking.session.tutor.get_full_name()} has started your session!

📅 Date : {booking.session.date.strftime('%A, %B %d, %Y')}
⏰ Time : {booking.session.start_time.strftime('%I:%M %p')} – {booking.session.end_time.strftime('%I:%M %p')}
🎯 Skill: {booking.session.skill.name}

Click the link below to join the Zoom meeting:
{booking.zoom_join_url}

After the session, please log in to Skillify and mark the session as complete.

Best regards,
Skillify Team
""",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[learner.email],
        fail_silently=True,
    )


def _send_reschedule_request_email(booking):
    learner  = booking.learner
    session  = booking.session
    deadline = session.start_time  # 1 hour before session start

    send_mail(
        subject=f'📅 Reschedule Request for "{session.title}"',
        message=f"""Hi {learner.get_full_name()},

Your tutor {session.tutor.get_full_name()} has requested to reschedule your session.

Original Date/Time:
📅 {session.date.strftime('%A, %B %d, %Y')}
⏰ {session.start_time.strftime('%I:%M %p')} – {session.end_time.strftime('%I:%M %p')}

Proposed New Date/Time:
📅 {booking.proposed_date.strftime('%A, %B %d, %Y')}
⏰ {booking.proposed_start_time.strftime('%I:%M %p')} – {booking.proposed_end_time.strftime('%I:%M %p')}

⚠️ You must respond before 1 hour of the original session start time.
If you do not respond, your booking will be automatically cancelled and credits refunded.

Please log in to Skillify and go to My Sessions → Upcoming tab to Accept or Decline.

Best regards,
Skillify Team
""",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[learner.email],
        fail_silently=True,
    )


def _send_reschedule_processed_email(session, accepted):
    tutor = session.tutor
    if accepted:
        subject = f'✅ Session "{session.title}" has been rescheduled!'
        message = f"""Hi {tutor.get_full_name()},

Your session has been successfully rescheduled!

📅 New Date : {session.date.strftime('%A, %B %d, %Y')}
⏰ New Time : {session.start_time.strftime('%I:%M %p')} – {session.end_time.strftime('%I:%M %p')}

Learners who did not respond have been automatically cancelled and refunded.

Best regards,
Skillify Team
"""
    else:
        subject = f'❌ Session "{session.title}" reschedule was rejected'
        message = f"""Hi {tutor.get_full_name()},

Unfortunately, no learners accepted your reschedule request for "{session.title}".
The session has been cancelled and all learners have been refunded.

Best regards,
Skillify Team
"""
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[tutor.email],
        fail_silently=True,
    )


def _send_cancellation_email_to_tutor(booking):
    tutor = booking.session.tutor
    send_mail(
        subject=f'❌ Booking Cancelled for "{booking.session.title}"',
        message=f"""Hi {tutor.get_full_name()},

A learner has cancelled their booking for your session.

📅 Date   : {booking.session.date.strftime('%A, %B %d, %Y')}
⏰ Time   : {booking.session.start_time.strftime('%I:%M %p')} – {booking.session.end_time.strftime('%I:%M %p')}
👤 Learner: {booking.learner.get_full_name()}
🎯 Skill  : {booking.session.skill.name}

The slot is now available for other learners to book.

Best regards,
Skillify Team
""",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[tutor.email],
        fail_silently=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN VIEWS
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def my_sessions_view(request):
    profile = request.user.profile
    wallet  = request.user.wallet
    today   = timezone.now().date()
    now     = timezone.now()

    _check_auto_complete()

    if profile.role == 'tutor':
        from django.db.models import Count, Q

        all_sessions = Session.objects.filter(
            tutor=request.user
        ).select_related('skill').order_by('-date', '-start_time')

        all_bookings = Booking.objects.filter(
            session__tutor=request.user
        ).select_related('learner', 'session', 'session__skill').order_by('-booked_at')

        inprogress_bookings = all_bookings.filter(status='in_progress')

        # Build set of booking pks where session end time has passed
        ended_booking_pks = set()
        for b in inprogress_bookings:
            session_end = timezone.make_aware(
                datetime.combine(b.session.date, b.session.end_time)
            )
            if now > session_end:
                ended_booking_pks.add(b.pk)

        inprogress_session_ids = inprogress_bookings.values_list('session_id', flat=True)

        booked_session_ids_any = Booking.objects.filter(
            session__tutor=request.user,
            status__in=['confirmed', 'in_progress']
        ).values_list('session_id', flat=True)

        upcoming_sessions = all_sessions.filter(
            status='upcoming'
        ).exclude(
            date__lt=today
        ).exclude(
            date=today,
            start_time__lt=now.time(),
            id__in=Session.objects.exclude(id__in=booked_session_ids_any).values_list('id', flat=True)
        ).exclude(
            date=today,
            end_time__lt=now.time(),
            id__in=booked_session_ids_any
        ).exclude(
            id__in=inprogress_session_ids
        ).annotate(
            active_bookings_count=Count(
                'bookings',
                filter=Q(bookings__status__in=['confirmed', 'in_progress'])
            )
        )

        completed_sessions = all_sessions.filter(
            status__in=['completed', 'cancelled']
        ).order_by('-date')

        confirmed_bookings = Booking.objects.filter(
            session__tutor=request.user,
            status='confirmed',
            tutor_email_sent=False,
        ).select_related('session', 'learner', 'session__skill')

        for booking in confirmed_bookings:
            if booking.can_start():
                _send_tutor_start_email(booking)

        startable = {}
        for booking in Booking.objects.filter(
            session__tutor=request.user,
            status='confirmed',
        ).select_related('session'):
            if booking.can_start():
                startable[booking.session_id] = booking.pk
        
        # Build set of session IDs where less than 12 hours to start
        no_reschedule_ids = set()
        for session in upcoming_sessions:
            session_start = timezone.make_aware(
                datetime.combine(session.date, session.start_time)
            )
            hours_until = (session_start - now).total_seconds() / 3600
            if hours_until < 12:
                no_reschedule_ids.add(session.pk)

        from disputes.models import Dispute

# All disputes involving current user
        all_disputes = Dispute.objects.filter(
            filed_by=request.user
        ) | Dispute.objects.filter(
            against=request.user
        )
        all_disputes = all_disputes.select_related('booking').distinct()

# Build lookup: booking_pk → dispute info
        dispute_info = {}
        for d in all_disputes:
            booking_pk_str = str(d.booking.pk)
            dispute_info[booking_pk_str] = {
                'pk':     d.pk,
                'status': d.status,
                'role':   'filed' if d.filed_by == request.user else 'against',
            }

        # Build dispute maps
        # Booking PKs where current user already filed a dispute
        filed_dispute_map = {}  # booking_pk → dispute_pk
        for d in Dispute.objects.filter(filed_by=request.user).select_related('booking'):
            filed_dispute_map[d.booking.pk] = d.pk

        # Booking PKs where dispute was filed against current user
        against_dispute_map = {}  # booking_pk → dispute_pk
        for d in Dispute.objects.filter(against=request.user).select_related('booking'):
            against_dispute_map[d.booking.pk] = d.pk

        context = {
            'profile':             profile,
            'wallet':              wallet,
            'upcoming_sessions':   upcoming_sessions,
            'completed_sessions':  completed_sessions,
            'bookings':            all_bookings,
            'inprogress_bookings': inprogress_bookings,
            'startable':           startable,
            'ended_booking_pks':   ended_booking_pks,
            'now':                 now,
            'no_reschedule_ids': no_reschedule_ids,
            'filed_dispute_map':   filed_dispute_map,
            'against_dispute_map': against_dispute_map,
            'dispute_info': dispute_info,
        }

    else:  # learner
        all_bookings = Booking.objects.filter(
            learner=request.user
        ).select_related('session', 'session__tutor', 'session__skill')

        upcoming_bookings = all_bookings.filter(
            status='confirmed',
        ).exclude(
            session__date__lt=today
        ).exclude(
            session__date=today,
            session__start_time__lt=now.time()
        ).order_by('session__date', 'session__start_time')

        inprogress_bookings = all_bookings.filter(
            status='in_progress',
        ).order_by('session__date')

        ended_booking_pks = set()
        for b in inprogress_bookings:
            session_end = timezone.make_aware(
                datetime.combine(b.session.date, b.session.end_time)
            )
            if now > session_end:
                ended_booking_pks.add(b.pk)

        completed_bookings = all_bookings.filter(
            status__in=['completed', 'pending_review']
        ).order_by('-session__date')

        cancelled_bookings = all_bookings.filter(
            status='cancelled'
        ).order_by('-session__date')

        # Build dispute maps
        from disputes.models import Dispute

        # Booking PKs where current user already filed a dispute
        filed_dispute_map = {}  # booking_pk → dispute_pk
        for d in Dispute.objects.filter(filed_by=request.user).select_related('booking'):
            filed_dispute_map[d.booking.pk] = d.pk

        # Booking PKs where dispute was filed against current user
        against_dispute_map = {}  # booking_pk → dispute_pk
        for d in Dispute.objects.filter(against=request.user).select_related('booking'):
            against_dispute_map[d.booking.pk] = d.pk

        # Build lookup: booking_pk → dispute info
        all_disputes = Dispute.objects.filter(
            filed_by=request.user
        ) | Dispute.objects.filter(
            against=request.user
        )
        all_disputes = all_disputes.select_related('booking').distinct()

        dispute_info = {}
        for d in all_disputes:
            booking_pk_str = str(d.booking.pk)
            dispute_info[booking_pk_str] = {
                'pk':     d.pk,
                'status': d.status,
                'role':   'filed' if d.filed_by == request.user else 'against',
            }

        context = {
            'profile':             profile,
            'wallet':              wallet,
            'upcoming_bookings':   upcoming_bookings,
            'inprogress_bookings': inprogress_bookings,
            'completed_bookings':  completed_bookings,
            'cancelled_bookings':  cancelled_bookings,
            'ended_booking_pks':   ended_booking_pks,
            'now':                 now,
            'filed_dispute_map':   filed_dispute_map,
            'against_dispute_map': against_dispute_map,
            'dispute_info':        dispute_info,
        }

    return render(request, 'session/my_session.html', context)


# ─────────────────────────────────────────────────────────────────────────────
@login_required
def start_session_view(request, booking_id):
    booking = get_object_or_404(
        Booking,
        pk=booking_id,
        session__tutor=request.user,
        status='confirmed',
    )

    if not booking.can_start():
        messages.error(request, 'You can only start the session within 15 minutes of the scheduled time.')
        return redirect('my_sessions')

    zoom_data = create_zoom_meeting(booking.session)
    if zoom_data:
        booking.zoom_meeting_id = zoom_data['meeting_id']
        booking.zoom_host_url   = zoom_data['host_url']
        booking.zoom_join_url   = zoom_data['join_url']
        messages.success(request, 'Session started! Zoom meeting created and learner notified.')
    else:
        messages.warning(request, 'Session started, but Zoom meeting could not be created. Please share a meeting link manually.')

    booking.status             = 'in_progress'
    booking.session_started_at = timezone.now()
    booking.save()

    if booking.zoom_join_url:
        _send_learner_join_email(booking)

    # ── In-app notification to learner ──
    try:
        from notifications.models import Notification
        Notification.create(
            recipient=booking.learner,
            notification_type='session_starting',
            title='Session Starting Now',
            message=f'Your session "{booking.session.title}" with {request.user.get_full_name()} has started. Join now!',
            link=booking.zoom_join_url if booking.zoom_join_url else '/my-sessions/',
        )
    except Exception:
        pass

    return redirect('my_sessions')


# ─────────────────────────────────────────────────────────────────────────────
@login_required
def mark_complete_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id, status='in_progress')

    is_tutor   = request.user == booking.session.tutor
    is_learner = request.user == booking.learner

    if not is_tutor and not is_learner:
        messages.error(request, 'You are not part of this session.')
        return redirect('my_sessions')

    if booking.session_started_at:
        elapsed_minutes   = (timezone.now() - booking.session_started_at).total_seconds() / 60
        scheduled_minutes = booking.session.duration_minutes()
        minimum_minutes   = scheduled_minutes * 0.8

        if elapsed_minutes < minimum_minutes:
            remaining = int(minimum_minutes - elapsed_minutes)
            messages.error(
                request,
                f'Session is too short! Minimum {int(minimum_minutes)} minutes required. '
                f'Please wait {remaining} more minutes before marking complete.'
            )
            return redirect('my_sessions')

    if is_tutor and not booking.tutor_confirmed:
        booking.tutor_confirmed  = True
        booking.auto_complete_at = timezone.now() + timedelta(hours=24)
        booking.save()
        messages.info(request, 'You marked the session complete. Credits will transfer when learner confirms or automatically after 24 hours.')

    elif is_learner and not booking.learner_confirmed:
        booking.learner_confirmed = True
        booking.save()
        messages.info(request, 'You marked the session complete.')

    booking.refresh_from_db()
    if booking.tutor_confirmed and booking.learner_confirmed:
        _transfer_credits(booking)
        booking.status = 'pending_review'
        booking.save()
        if not booking.session.bookings.filter(status='in_progress').exists():
            booking.session.status = 'completed'
            booking.session.save()
        messages.success(request, f'Session completed! {booking.credits_paid} credits transferred successfully.')

    return redirect('my_sessions')


# ─────────────────────────────────────────────────────────────────────────────
@login_required
def reschedule_session_view(request, session_id):
    session = get_object_or_404(Session, pk=session_id, tutor=request.user, status='upcoming')

    # Block reschedule if less than 12 hours to session start
    now           = timezone.now()
    session_start = timezone.make_aware(
        datetime.combine(session.date, session.start_time)
    )
    hours_until_start = (session_start - now).total_seconds() / 3600

    # Block if reschedule already pending
    already_pending = Booking.objects.filter(
        session=session,
        status='confirmed',
        reschedule_status='pending',
    ).exists()
    if already_pending:
        messages.error(request, 'A reschedule request is already pending. Please wait for learners to respond before rescheduling again.')
        return redirect('my_sessions')

    if request.method == 'POST':
        form = RescheduleForm(request.POST)
        if form.is_valid():
            new_date       = form.cleaned_data['date']
            new_start_time = form.cleaned_data['start_time']
            new_end_time   = form.cleaned_data['end_time']

            bookings = Booking.objects.filter(
                session=session,
                status='confirmed',
                reschedule_status='none',
            )

            if not bookings.exists():
                # No bookings — reschedule directly
                session.date       = new_date
                session.start_time = new_start_time
                session.end_time   = new_end_time
                session.save()
                messages.success(request, f'Session rescheduled to {new_date} at {new_start_time.strftime("%I:%M %p")}.')
                return redirect('my_sessions')
            else:
                # Set reschedule deadline = 1 hour before original session start
                reschedule_deadline = session_start - timedelta(hours=1)

                for booking in bookings:
                    booking.proposed_date       = new_date
                    booking.proposed_start_time = new_start_time
                    booking.proposed_end_time   = new_end_time
                    booking.reschedule_status   = 'pending'
                    booking.reschedule_deadline = reschedule_deadline
                    booking.save()
                    _send_reschedule_request_email(booking)
                    # ── In-app notification ──
                    try:
                        from notifications.models import Notification
                        Notification.create(
                            recipient=booking.learner,
                            notification_type='reschedule_requested',
                            title='Session Reschedule Requested',
                            message=f'Tutor {request.user.get_full_name()} requested to reschedule "{session.title}" to {new_date.strftime("%b %d, %Y")} at {new_start_time.strftime("%I:%M %p")}.',
                            link='/my-sessions/',
                        )
                    except Exception:
                        pass

                # Save proposed times on session for deadline processing
                session.proposed_date       = new_date
                session.proposed_start_time = new_start_time
                session.proposed_end_time   = new_end_time
                session.save()

                messages.success(
                    request,
                    f'Reschedule request sent to {bookings.count()} learner(s). '
                    f'They must respond before {reschedule_deadline.strftime("%I:%M %p on %B %d")}.'
                )
                return redirect('my_sessions')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = RescheduleForm(initial={
            'date':       session.date,
            'start_time': session.start_time,
            'end_time':   session.end_time,
        })

    return render(request, 'session/reschedule_session.html', {
        'form':    form,
        'session': session,
        'today':   timezone.now().date(),
    })


# ─────────────────────────────────────────────────────────────────────────────
@login_required
def reschedule_accept_view(request, booking_id):
    booking = get_object_or_404(
        Booking,
        pk=booking_id,
        learner=request.user,
        reschedule_status='pending',
    )

    session = booking.session

    # Check if deadline has passed
    now = timezone.now()
    if booking.reschedule_deadline and now >= booking.reschedule_deadline:
        messages.error(request, 'The response deadline for this reschedule has passed.')
        return redirect('my_sessions')

    # Save proposed times before clearing
    new_date       = booking.proposed_date
    new_start_time = booking.proposed_start_time
    new_end_time   = booking.proposed_end_time

    # Mark this booking as accepted
    booking.reschedule_status   = 'accepted'
    booking.proposed_date       = None
    booking.proposed_start_time = None
    booking.proposed_end_time   = None
    booking.tutor_email_sent    = False
    booking.save()

    # Check if ALL pending bookings have now responded
    pending_count = Booking.objects.filter(
        session=session,
        reschedule_status='pending',
    ).count()

    if pending_count == 0:
        # All responded — update session time now
        session.date       = new_date
        session.start_time = new_start_time
        session.end_time   = new_end_time
        session.save()

        # Reset all accepted bookings reschedule status
        Booking.objects.filter(
            session=session,
            reschedule_status='accepted'
        ).update(reschedule_status='none')

        messages.success(request, f'All learners responded! Session rescheduled to {new_date} at {new_start_time.strftime("%I:%M %p")}.')
    else:
        messages.success(request, f'You accepted the reschedule. Waiting for {pending_count} other learner(s) to respond.')

    # ── In-app notification to tutor ──
    try:
        from notifications.models import Notification
        Notification.create(
            recipient=session.tutor,
            notification_type='reschedule_accepted',
            title='Reschedule Accepted',
            message=f'{request.user.get_full_name()} accepted the reschedule for "{session.title}".',
            link='/my-sessions/',
        )
    except Exception:
        pass

    return redirect('my_sessions')


# ─────────────────────────────────────────────────────────────────────────────
@login_required
def reschedule_decline_view(request, booking_id):
    booking = get_object_or_404(
        Booking,
        pk=booking_id,
        learner=request.user,
        reschedule_status='pending',
    )

    session = booking.session

    # Check if deadline has passed
    now = timezone.now()
    if booking.reschedule_deadline and now >= booking.reschedule_deadline:
        messages.error(request, 'The response deadline for this reschedule has passed.')
        return redirect('my_sessions')

    # Save proposed times before cancelling (needed if others accepted)
    new_date       = booking.proposed_date
    new_start_time = booking.proposed_start_time
    new_end_time   = booking.proposed_end_time

    # Cancel only this learner's booking
    _refund_credits(booking)
    booking.reschedule_status = 'declined'
    booking.status            = 'cancelled'
    booking.save()

    # Check remaining bookings
    remaining_pending  = Booking.objects.filter(session=session, reschedule_status='pending').count()
    remaining_accepted = Booking.objects.filter(session=session, reschedule_status='accepted').count()

    if remaining_pending == 0:
        # All have responded
        if remaining_accepted > 0 and new_date:
            # Some accepted → reschedule session now
            session.date       = new_date
            session.start_time = new_start_time
            session.end_time   = new_end_time
            session.save()

            # Reset accepted bookings
            Booking.objects.filter(
                session=session,
                reschedule_status='accepted'
            ).update(reschedule_status='none')

            messages.info(request, f'You declined the reschedule. {booking.credits_paid} credits refunded. Session has been rescheduled for other learners.')
        else:
            # Nobody accepted → cancel session entirely
            remaining_confirmed = Booking.objects.filter(
                session=session,
                status='confirmed',
            )
            for b in remaining_confirmed:
                try:
                    _refund_credits(b)
                    b.reschedule_status = 'declined'
                    b.status            = 'cancelled'
                    b.save()
                except Exception:
                    continue

            session.status = 'cancelled'
            session.save()

            messages.info(request, f'You declined the reschedule. {booking.credits_paid} credits refunded. Session has been cancelled.')
    else:
        messages.info(request, f'You declined the reschedule. {booking.credits_paid} credits refunded. Session continues for other learners.')

    # ── In-app notification to tutor ──
    try:
        from notifications.models import Notification
        Notification.create(
            recipient=session.tutor,
            notification_type='reschedule_declined',
            title='Reschedule Declined',
            message=f'{request.user.get_full_name()} declined the reschedule for "{session.title}". Their booking has been cancelled and credits refunded.',
            link='/my-sessions/',
        )
    except Exception:
        pass

    return redirect('my_sessions')


# ─────────────────────────────────────────────────────────────────────────────
@login_required
def create_session_view(request):
    today = timezone.now().date()

    if request.method == 'POST':
        form = SessionForm(request.POST)
        if form.is_valid():
            session_date = form.cleaned_data['date']
            if session_date < today:
                messages.error(request, 'You cannot create a session for a past date.')
                return render(request, 'session/create_session.html', {
                    'form': form, 'skills': Skill.objects.all(), 'today': today
                })
            session        = form.save(commit=False)
            session.tutor  = request.user
            session.status = 'upcoming'

            # Check for overlapping sessions
            overlapping = Session.objects.filter(
                tutor=request.user,
                date=session.date,
                status='upcoming',
            ).exclude(
                end_time__lte=session.start_time
            ).exclude(
                start_time__gte=session.end_time
            )
            if overlapping.exists():
                messages.error(request, 'You cannot create another session for the same time slot. Please choose a different date or time.')
                return render(request, 'session/create_session.html', {
                    'form': form, 'skills': Skill.objects.all(), 'today': today
                })

            session.save()
            messages.success(request, f'Session "{session.title}" created successfully!')
            return redirect('my_sessions')
        else:
            messages.error(request, 'Could not create session. Please check the time slot!')
    else:
        form = SessionForm()

    return render(request, 'session/create_session.html', {
        'form': form, 'skills': Skill.objects.all(), 'today': today
    })


# ─────────────────────────────────────────────────────────────────────────────
@login_required
def book_session_view(request, session_id):
    session = get_object_or_404(Session, pk=session_id)

    if session.tutor == request.user:
        messages.error(request, 'You cannot book your own session.')
        return redirect('tutor_profile', pk=session.tutor.pk)

    now           = timezone.now()
    session_start = timezone.make_aware(
        datetime.combine(session.date, session.start_time)
    )
    if now > session_start:
        messages.error(request, 'This session has already started or passed.')
        return redirect('tutor_profile', pk=session.tutor.pk)

    if session.status != 'upcoming':
        messages.error(request, 'This session is no longer available.')
        return redirect('tutor_profile', pk=session.tutor.pk)

    if Booking.objects.filter(
        learner=request.user,
        session=session,
        status__in=['confirmed', 'in_progress']
    ).exists():
        messages.warning(request, 'You have already booked this session.')
        return redirect('my_sessions')

    booked_count = Booking.objects.filter(
        session=session,
        status__in=['confirmed', 'in_progress']
    ).count()
    if booked_count >= session.max_participants:
        messages.error(request, 'Sorry, this session is fully booked.')
        return redirect('tutor_profile', pk=session.tutor.pk)

    wallet = request.user.wallet
    if wallet.balance < session.credits_required:
        messages.error(request, f'Insufficient credits. You need {session.credits_required} but have {wallet.balance}.')
        return redirect('tutor_profile', pk=session.tutor.pk)

    if request.method == 'POST':
        wallet.freeze_credits(session.credits_required)
        Transaction.objects.create(
            wallet=wallet,
            transaction_type='credits_frozen',
            amount=session.credits_required,
            description=f'Credits frozen for: {session.title}',
            balance_after=wallet.balance,
        )

        # Update existing cancelled booking or create new one
        existing = Booking.objects.filter(
            learner=request.user,
            session=session,
            status='cancelled'
        ).first()

        if existing:
            existing.status             = 'confirmed'
            existing.credits_paid       = session.credits_required
            existing.reschedule_status  = 'none'
            existing.proposed_date      = None
            existing.proposed_start_time = None
            existing.proposed_end_time  = None
            existing.reschedule_deadline = None
            existing.tutor_confirmed    = False
            existing.learner_confirmed  = False
            existing.zoom_meeting_id    = ''
            existing.zoom_host_url      = None
            existing.zoom_join_url      = None
            existing.session_started_at = None
            existing.auto_complete_at   = None
            existing.tutor_email_sent   = False
            existing.save()
        else:
            Booking.objects.create(
                learner=request.user,
                session=session,
                status='confirmed',
                credits_paid=session.credits_required,
            )

        messages.success(request, f'Session "{session.title}" booked! {session.credits_required} credits frozen.')
        return redirect('my_sessions')

    return redirect('tutor_profile', pk=session.tutor.pk)


# ─────────────────────────────────────────────────────────────────────────────
@login_required
def cancel_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id, learner=request.user)

    if booking.status != 'confirmed':
        messages.error(request, 'This booking cannot be cancelled.')
        return redirect('my_sessions')

    # 2-hour cancellation check
    now           = timezone.now()
    session_start = timezone.make_aware(
        datetime.combine(booking.session.date, booking.session.start_time)
    )
    hours_until_start = (session_start - now).total_seconds() / 3600
    if hours_until_start < 2:
        messages.error(request, 'Cancellation is only allowed up to 2 hours before the session starts.')
        return redirect('my_sessions')

    _refund_credits(booking)
    booking.status = 'cancelled'
    booking.save()
                # ── Notification ──
    try:
        from notifications.models import Notification
        Notification.create(
            recipient=booking.learner,
            notification_type='session_cancelled',
            title='Session Auto-Cancelled',
            message=f'Your session "{booking.session.title}" was automatically cancelled as it was not started. {booking.credits_paid} credits have been refunded.',
            link='/my-sessions/',
        )
        Notification.create(
            recipient=booking.session.tutor,
            notification_type='credits_received',
            title='Session Auto-Cancelled',
            message=f'Session "{booking.session.title}" was automatically cancelled. Learner credits have been refunded.',
            link='/my-sessions/',
        )
    except Exception:
        pass

    _send_cancellation_email_to_tutor(booking)

    messages.success(request, f'Booking cancelled. {booking.credits_paid} credits refunded.')
    return redirect('my_sessions')


# ─────────────────────────────────────────────────────────────────────────────
@login_required
def api_book_session(request, session_id):
    if request.method == 'POST':
        session = get_object_or_404(Session, pk=session_id, status='upcoming')
        wallet  = request.user.wallet

        if session.tutor == request.user:
            return JsonResponse({'error': "Can't book own session"}, status=400)
        if Booking.objects.filter(
            learner=request.user,
            session=session,
            status__in=['confirmed', 'in_progress']
        ).exists():
            return JsonResponse({'error': 'Already booked'}, status=400)
        if wallet.balance < session.credits_required:
            return JsonResponse({'error': 'Insufficient credits'}, status=400)

        wallet.freeze_credits(session.credits_required)
        Transaction.objects.create(
            wallet=wallet,
            transaction_type='credits_frozen',
            amount=session.credits_required,
            description=f'Credits frozen for: {session.title}',
            balance_after=wallet.balance,
        )

        existing = Booking.objects.filter(
            learner=request.user,
            session=session,
            status='cancelled'
        ).first()

        if existing:
            existing.status      = 'confirmed'
            existing.credits_paid = session.credits_required
            existing.reschedule_status = 'none'
            existing.save()
        else:
            Booking.objects.create(
                learner=request.user,
                session=session,
                status='confirmed',
                credits_paid=session.credits_required,
            )

        return JsonResponse({'status': 'ok', 'balance': wallet.balance})
    return JsonResponse({'error': 'POST required'}, status=400)