from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Count

from session.models import Booking
from reviews.models import Review


@login_required
def leave_review_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id, learner=request.user)

    # Must be pending_review
    if booking.status != 'pending_review':
        messages.error(request, 'This session is not eligible for review.')
        return redirect('my_sessions')

    # Already reviewed
    if hasattr(booking, 'review'):
        messages.info(request, 'You have already reviewed this session.')
        return redirect('my_sessions')

    if request.method == 'POST':
        rating      = int(request.POST.get('rating', 5))
        comment     = request.POST.get('comment', '').strip()
        recommended = request.POST.get('recommended') == 'on'
        tags        = request.POST.getlist('tags')

        Review.objects.create(
            booking     = booking,
            session     = booking.session,
            reviewer    = request.user,
            tutor       = booking.session.tutor,
            rating      = rating,
            comment     = comment,
            recommended = recommended,
            tags        = tags,
        )

        # Mark booking as completed
        booking.status = 'completed'
        booking.save()

        # Check if all bookings for this session are completed
        session = booking.session
        pending = session.bookings.filter(status='pending_review').count()
        if pending == 0:
            session.status = 'completed'
            session.save()

        messages.success(request, f'Thank you for your review! Your feedback helps the community.')
        return redirect('my_sessions')

    context = {
        'booking':     booking,
        'tag_choices': Review.TAG_CHOICES,
    }
    return render(request, 'reviews/leave_review.html', context)