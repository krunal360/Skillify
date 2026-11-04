from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone

from disputes.models import Dispute, DisputeResponse
from session.models import Booking


@login_required
def file_dispute_view(request, booking_id):
    booking = get_object_or_404(
        Booking,
        pk=booking_id,
        status__in=['confirmed', 'in_progress', 'completed', 'pending_review'],
    )

    is_learner = request.user == booking.learner
    is_tutor   = request.user == booking.session.tutor

    if not is_learner and not is_tutor:
        messages.error(request, 'You are not part of this booking.')
        return redirect('my_sessions')

    # Check if user already filed a dispute for this booking
    existing = Dispute.objects.filter(booking=booking, filed_by=request.user).first()
    if existing:
        messages.warning(request, 'You have already filed a dispute for this booking.')
        return redirect('view_dispute', pk=existing.pk)

    # Check if dispute already exists against this user — redirect to add response
    dispute_against_me = Dispute.objects.filter(booking=booking, against=request.user).first()
    if dispute_against_me:
        messages.info(request, 'A dispute has been filed against you for this booking. You can add your response below.')
        return redirect('add_dispute_response', pk=dispute_against_me.pk)

    if request.method == 'POST':
        reason        = request.POST.get('reason', '')
        description   = request.POST.get('description', '').strip()
        evidence_url  = request.POST.get('evidence_url', '').strip()
        evidence_file = request.FILES.get('evidence_file')

        if not reason or not description:
            messages.error(request, 'Please fill in all required fields.')
        else:
            against = booking.session.tutor if is_learner else booking.learner

            dispute = Dispute.objects.create(
                booking=booking,
                filed_by=request.user,
                against=against,
                reason=reason,
                description=description,
                evidence_url=evidence_url,
                evidence_file=evidence_file,
            )

            # Notify other party
            try:
                from notifications.models import Notification
                Notification.create(
                    recipient=against,
                    notification_type='dispute_filed',
                    title='Dispute Filed Against You',
                    message=f'{request.user.get_full_name()} filed a dispute for "{booking.session.title}". You can view and respond to it.',
                    link=f'/disputes/{dispute.pk}/',
                )
            except Exception:
                pass

            # Notify admins
            from django.contrib.auth.models import User
            for admin in User.objects.filter(is_staff=True):
                try:
                    from notifications.models import Notification
                    Notification.create(
                        recipient=admin,
                        notification_type='dispute_filed',
                        title='New Dispute Filed',
                        message=f'{request.user.get_full_name()} filed a dispute for "{booking.session.title}".',
                        link='/skillify-admin/disputes/',
                    )
                except Exception:
                    pass

            messages.success(request, 'Dispute filed successfully. The other party has been notified and can respond.')
            return redirect('view_dispute', pk=dispute.pk)

    context = {
        'booking':        booking,
        'reason_choices': Dispute.REASON_CHOICES,
        'is_learner':     is_learner,
        'is_tutor':       is_tutor,
    }
    return render(request, 'disputes/file_dispute.html', context)


@login_required
def add_dispute_response_view(request, pk):
    """
    The party against whom the dispute was filed adds their response/defence.
    """
    dispute = get_object_or_404(Dispute, pk=pk)

    # Only the 'against' party can respond
    if request.user != dispute.against:
        messages.error(request, 'Only the other party can add a response to this dispute.')
        return redirect('view_dispute', pk=pk)

    # Check if already responded
    existing_response = DisputeResponse.objects.filter(
        dispute=dispute,
        responded_by=request.user,
    ).first()

    if existing_response:
        messages.info(request, 'You have already added your response to this dispute.')
        return redirect('view_dispute', pk=pk)

    if request.method == 'POST':
        response_text = request.POST.get('response', '').strip()
        evidence_url  = request.POST.get('evidence_url', '').strip()
        evidence_file = request.FILES.get('evidence_file')

        if not response_text:
            messages.error(request, 'Please write your response.')
        else:
            DisputeResponse.objects.create(
                dispute=dispute,
                responded_by=request.user,
                response=response_text,
                evidence_url=evidence_url,
                evidence_file=evidence_file,
            )

            # Notify the person who filed the dispute
            try:
                from notifications.models import Notification
                Notification.create(
                    recipient=dispute.filed_by,
                    notification_type='dispute_filed',
                    title='Response Added to Your Dispute',
                    message=f'{request.user.get_full_name()} has responded to your dispute for "{dispute.booking.session.title}".',
                    link=f'/disputes/{dispute.pk}/',
                )
            except Exception:
                pass

            # Notify admins
            from django.contrib.auth.models import User
            for admin in User.objects.filter(is_staff=True):
                try:
                    from notifications.models import Notification
                    Notification.create(
                        recipient=admin,
                        notification_type='dispute_filed',
                        title='Dispute Response Added',
                        message=f'{request.user.get_full_name()} responded to dispute #{dispute.pk}.',
                        link='/skillify-admin/disputes/',
                    )
                except Exception:
                    pass

            messages.success(request, 'Your response has been submitted successfully.')
            return redirect('view_dispute', pk=pk)

    context = {
        'dispute': dispute,
    }
    return render(request, 'disputes/add_response.html', context)


@login_required
def view_dispute_view(request, pk):
    dispute   = get_object_or_404(Dispute, pk=pk)
    responses = dispute.responses.all()

    is_involved = (
        request.user == dispute.filed_by or
        request.user == dispute.against or
        request.user.is_staff
    )

    if not is_involved:
        messages.error(request, 'You do not have permission to view this dispute.')
        return redirect('my_sessions')

    can_respond = (
        request.user == dispute.against and
        not responses.filter(responded_by=request.user).exists() and
        dispute.is_open
    )

    context = {
        'dispute':     dispute,
        'responses':   responses,
        'can_respond': can_respond,
    }
    return render(request, 'disputes/view_dispute.html', context)


@login_required
def my_disputes_view(request):
    filed   = Dispute.objects.filter(filed_by=request.user).select_related('booking', 'booking__session', 'against')
    against = Dispute.objects.filter(against=request.user).select_related('booking', 'booking__session', 'filed_by')

    context = {
        'filed':   filed,
        'against': against,
    }
    return render(request, 'disputes/my_disputes.html', context)