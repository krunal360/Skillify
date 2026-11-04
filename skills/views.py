from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Min, Q
from django.utils import timezone

from reviews.models import Review
from skills.models import Skill
from users.models import UserProfile


@login_required
def browse_skills_view(request):
    search = request.GET.get('search', '')
    skill_filter = request.GET.get('skill', '')
    max_credits = request.GET.get('max_credits', '')
    min_rating = request.GET.get('min_rating', '')
    session_type = request.GET.get('session_type', '')
    availability = request.GET.get('availability', '')
    sort_by = request.GET.get('sort_by', '')

    # Import here to avoid circular imports
    from session.models import Session
    from reviews.models import Review

    # Start with all tutors who have upcoming sessions
    # Show ALL tutors regardless of whether they have sessions
    tutors = UserProfile.objects.filter(
        role='tutor'
    ).select_related('user').prefetch_related('skills')

    # Search filter
    if search:
        search_terms = search.strip().split()
        
        if len(search_terms) == 1:
            # Single word — search everywhere
            term = search_terms[0]
            query = (
                Q(user__first_name__icontains=term) |
                Q(user__last_name__icontains=term) |
                Q(user__username__icontains=term) |
                Q(skills__name__icontains=term) |
                Q(expertise__icontains=term) |
                Q(bio__icontains=term)
            )
        else:
            # Multiple words — try full name + individual words
            # Start with first term
            first_term = search_terms[0]
            query = (
                Q(user__first_name__icontains=first_term) |
                Q(user__last_name__icontains=first_term) |
                Q(user__username__icontains=first_term) |
                Q(skills__name__icontains=first_term) |
                Q(expertise__icontains=first_term) |
                Q(bio__icontains=first_term)
            )
            # Add remaining terms
            for term in search_terms[1:]:
                query |= (
                    Q(user__first_name__icontains=term) |
                    Q(user__last_name__icontains=term) |
                    Q(user__username__icontains=term) |
                    Q(skills__name__icontains=term) |
                    Q(expertise__icontains=term) |
                    Q(bio__icontains=term)
                )
            # Also try first + last name combo
            query |= (
                Q(user__first_name__icontains=search_terms[0]) &
                Q(user__last_name__icontains=search_terms[1])
            )
            query |= (
                Q(user__first_name__icontains=search_terms[-1]) &
                Q(user__last_name__icontains=search_terms[0])
            )
        tutors = tutors.filter(query).distinct()

    # Skill filter
    if skill_filter:
        tutors = tutors.filter(skills__name=skill_filter)

    # Session type filter
    if session_type:
        tutor_ids_by_type = Session.objects.filter(
            status='upcoming',
            session_type=session_type
        ).values_list('tutor', flat=True).distinct()
        tutors = tutors.filter(user__id__in=tutor_ids_by_type)

    # Availability filter - active this week
    if availability == 'this_week':
        today = timezone.now().date()
        week_end = today + timezone.timedelta(days=7)
        tutor_ids_this_week = Session.objects.filter(
            status='upcoming',
            date__gte=today,
            date__lte=week_end
        ).values_list('tutor', flat=True).distinct()
        tutors = tutors.filter(user__id__in=tutor_ids_this_week)

    # Max credits filter
    if max_credits:
        tutor_ids_by_credits = Session.objects.filter(
            status='upcoming',
            credits_required__lte=int(max_credits)
        ).values_list('tutor', flat=True).distinct()
        tutors = tutors.filter(user__id__in=tutor_ids_by_credits)

    # Build enriched tutor list with extra data
    today = timezone.now().date()
    week_end = today + timezone.timedelta(days=7)

    enriched_tutors = []
    for tutor in tutors:
        # Average rating
        avg_rating = Review.objects.filter(
            tutor=tutor.user
        ).aggregate(avg=Avg('rating'))['avg'] or 0

        # Min rating filter
        if min_rating and avg_rating < float(min_rating):
            continue

        # Review count
        review_count = Review.objects.filter(tutor=tutor.user).count()

        # Total completed sessions
        total_sessions = Session.objects.filter(
            tutor=tutor.user,
            status='completed'
        ).count()

        # Total students taught
        from session.models import Booking  # ← new location
        total_students = Booking.objects.filter(
            session__tutor=tutor.user
        ).values('learner').distinct().count()

        # Min credits
        min_credits_val = Session.objects.filter(
            tutor=tutor.user,
            status='upcoming'
        ).aggregate(min=Min('credits_required'))['min'] or 0

        # Active this week
        is_active_this_week = Session.objects.filter(
            tutor=tutor.user,
            status='upcoming',
            date__gte=today,
            date__lte=week_end
        ).exists()

        # Session types available
        has_one_to_one = Session.objects.filter(
            tutor=tutor.user,
            status='upcoming',
            session_type='one-to-one'
        ).exists()

        has_group = Session.objects.filter(
            tutor=tutor.user,
            status='upcoming',
            session_type='group'
        ).exists()

        enriched_tutors.append({
            'user': tutor.user,
            'profile': tutor,
            'avg_rating': round(avg_rating, 1),
            'review_count': review_count,
            'total_sessions': total_sessions,
            'total_students': total_students,
            'min_credits': min_credits_val,
            'is_active_this_week': is_active_this_week,
            'has_one_to_one': has_one_to_one,
            'has_group': has_group,
        })

    # Sorting
    if sort_by == 'highest_rating':
        enriched_tutors.sort(key=lambda x: x['avg_rating'], reverse=True)
    elif sort_by == 'lowest_credits':
        enriched_tutors.sort(key=lambda x: x['min_credits'])
    elif sort_by == 'most_students':
        enriched_tutors.sort(key=lambda x: x['total_students'], reverse=True)

    skills = Skill.objects.all()
    wallet = request.user.wallet

    context = {
        'tutors': enriched_tutors,
        'skills': skills,
        'wallet': wallet,
        'search': search,
        'skill_filter': skill_filter,
        'max_credits': max_credits,
        'min_rating': min_rating,
        'session_type': session_type,
        'availability': availability,
        'sort_by': sort_by,
    }
    return render(request, 'skills/browse_skills.html', context)