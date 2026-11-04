from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Avg
from django.utils import timezone

from users.models import UserProfile
from skills.models import Skill
from profiles.models import Certificate
from reviews.models import Review
from session.models import Booking, Session


@login_required
def edit_tutor_profile_view(request):
    profile = request.user.profile
    skills = Skill.objects.all()
    certificates = Certificate.objects.filter(tutor=request.user).order_by('-uploaded_at')

    if request.method == 'POST':

        # ── Full name
        full_name = request.POST.get('fullName', '').strip()
        if full_name:
            parts = full_name.split(' ', 1)
            request.user.first_name = parts[0]
            request.user.last_name = parts[1] if len(parts) > 1 else ''
            request.user.save()
     # ── Profile fields — role-separated ───────────────────────
        if profile.role == 'tutor':
            profile.expertise = request.POST.get('headline', '')
            profile.bio       = request.POST.get('bio', '')        # tutor bio
        else:
            profile.learner_bio = request.POST.get('learner_bio', '')  # learner bio

        profile.demo_video = request.POST.get('demo_video', '')
        profile.linkedin   = request.POST.get('linkedin', '')
        profile.github     = request.POST.get('github', '')

        # ── Skills — role-separated ────────────────────────────────
        skill_ids = request.POST.getlist('skills')
        if profile.role == 'tutor':
            profile.skills.set(skill_ids)              # skills I teach
        else:
            profile.learning_interests.set(skill_ids)

        profile.save()

        # ── Certificate UPLOAD
        # HTML form must use:  name="cert_file"  and  name="cert_title"
        if 'cert_file' in request.FILES:
            cert_title = request.POST.get('cert_title', '').strip()
            cert_file  = request.FILES['cert_file']
            if cert_title:
                Certificate.objects.create(
                    tutor=request.user,
                    title=cert_title,
                    file=cert_file
                )
                messages.success(request, f'Certificate "{cert_title}" uploaded successfully!')
            else:
                messages.warning(request, 'Please enter a title for the certificate.')
            return redirect('edit_tutor_profile')

        # ── Certificate DELETE
        # HTML form must use:  name="delete_cert_id"  value="{{ cert.pk }}"
        delete_cert_id = request.POST.get('delete_cert_id')
        if delete_cert_id:
            try:
                cert = Certificate.objects.get(pk=delete_cert_id, tutor=request.user)
                cert.file.delete(save=False)
                cert.delete()
                messages.success(request, 'Certificate deleted.')
            except Certificate.DoesNotExist:
                pass
            return redirect('edit_tutor_profile')

        # ── Regular profile save
        messages.success(request, 'Profile updated successfully!')
        return redirect('edit_tutor_profile')

    # ── GET: build calendar
    from session.models import Session
    today     = timezone.now().date()
    two_weeks = today + timezone.timedelta(days=14)
    now = timezone.now()
    upcoming_sessions = Session.objects.filter(
        tutor=request.user,
        date__lte=two_weeks,
        status='upcoming'
    ).exclude(
        date__lt=today
    ).exclude(
        date=today,
        start_time__lt=now.time()
    ).select_related('skill').order_by('date', 'start_time')

    calendar_data = build_calendar(
        today, upcoming_sessions, request.user, is_tutor_view=True
    )

    context = {
        'profile':       profile,
        'user':          request.user,
        'skills':        skills,
        'certificates':  certificates,
        'calendar_data': calendar_data,
        'sessions':      upcoming_sessions,
        'today':         today,
    }
    return render(request, 'profiles/edit_tutor_profile.html', context)


@login_required
def tutor_profile_view(request, pk):
    tutor_user = get_object_or_404(User, pk=pk)
    profile    = get_object_or_404(UserProfile, user=tutor_user)

    from collections import Counter

    reviews      = Review.objects.filter(tutor=tutor_user).select_related('reviewer', 'reviewer__profile').order_by('-created_at')
    review_count = reviews.count()
    avg_rating   = round(reviews.aggregate(avg=Avg('rating'))['avg'] or 0, 1)

    # Rating distribution
    rating_distribution = {str(i): 0 for i in range(1, 6)}
    for r in reviews:
        rating_distribution[str(r.rating)] += 1

    # Recommend percent
    recommend_count   = reviews.filter(recommended=True).count()
    recommend_percent = round((recommend_count / review_count * 100)) if review_count > 0 else 0

    # Top tags
    all_tags  = []
    for r in reviews:
        all_tags.extend(r.tags)
    tag_label_map = dict(Review.TAG_CHOICES)
    tag_counts    = Counter(all_tags)
    top_tags      = [(tag_label_map.get(tag, tag), count) for tag, count in tag_counts.most_common(4)]

    certificates    = Certificate.objects.filter(tutor=tutor_user).order_by('-uploaded_at')
    embed_video_url = profile.get_embed_video_url() if profile.demo_video else None

    today     = timezone.now().date()
    two_weeks = today + timezone.timedelta(days=14)
    now       = timezone.now()

    upcoming_sessions = Session.objects.filter(
    tutor=tutor_user,
    date__lte=two_weeks,
    status='upcoming'
    ).exclude(
        date__lt=today
    ).exclude(
        date=today,
        start_time__lt=now.time()
    ).select_related('skill').order_by('date', 'start_time')

    booked_session_ids = []
    if request.user.is_authenticated and request.user != tutor_user:
        try:
            booked_session_ids = list(Booking.objects.filter(
                learner=request.user,
                session__tutor=tutor_user,
                session__date__gte=today,
                status__in=['confirmed', 'in_progress']
            ).values_list('session_id', flat=True))
        except Exception:
            pass

    calendar_data = build_calendar(
        today, upcoming_sessions, request.user,
        is_tutor_view=(request.user == tutor_user),
        booked_session_ids=booked_session_ids
    )
# Sidebar: only show sessions that are not fully booked
    from django.db.models import Count
    available_sessions = []
    for s in upcoming_sessions:
        active_bookings = Booking.objects.filter(
            session=s,
            status__in=['confirmed', 'in_progress']
        ).count()
        if active_bookings < s.max_participants:
            available_sessions.append(s)


    # Trust score + similar tutors
    from trust.recommender import get_similar_tutors
    try:
        trust_score = tutor_user.trust_score
    except Exception:
        from trust.calculator import recalculate_trust_score
        trust_score = recalculate_trust_score(tutor_user)

    similar_tutors = get_similar_tutors(tutor_user, n=4)

    context = {
        'tutor_user':           tutor_user,
        'profile':              profile,
        'reviews':              reviews[:10],
        'review_count':         review_count,
        'avg_rating':           avg_rating,
        'rating_distribution':  rating_distribution,
        'recommend_percent':    recommend_percent,
        'top_tags':             top_tags,
        'certificates':         certificates,
        'embed_video_url':      embed_video_url,
        'calendar_data':        calendar_data,
        'sessions':             available_sessions,
        'trust_score':    trust_score,
        'similar_tutors': similar_tutors,
        'wallet':               request.user.wallet if request.user.is_authenticated else None,
    }    
    return render(request, 'profiles/tutor_profile.html', context)

def build_calendar(today, sessions, current_user,
                   is_tutor_view=False, booked_session_ids=None):
    """
    Build 2-week calendar.
    Time format: 12-hour AM/PM  e.g. "9:30 AM"
    Colors: green=available, red=full, blue=booked by this learner
    """
    if booked_session_ids is None:
        booked_session_ids = []

    weeks = []
    for week_num in range(2):
        week_start = today + timezone.timedelta(days=week_num * 7)
        days = []
        for day_offset in range(7):
            day_date     = week_start + timezone.timedelta(days=day_offset)
            day_sessions = []

            for session in sessions:
                if session.date != day_date:
                    continue

                try:
                    from session.models import Booking
                    booked_count = Booking.objects.filter(
                        session=session,
                        status__in=['confirmed', 'in_progress']
                    ).count()
                except Exception:
                    booked_count = 0

                spots_left = max(session.max_participants - booked_count, 0)

                if session.pk in booked_session_ids:
                    color = 'blue'
                elif spots_left <= 0:
                    color = 'red'
                else:
                    color = 'green'

                # 12-hour AM/PM  (%-I removes leading zero on Linux)
                try:
                    start_fmt = session.start_time.strftime('%-I:%M %p')
                    end_fmt   = session.end_time.strftime('%-I:%M %p')
                except ValueError:
                    # Windows fallback
                    start_fmt = session.start_time.strftime('%I:%M %p').lstrip('0')
                    end_fmt   = session.end_time.strftime('%I:%M %p').lstrip('0')

                day_sessions.append({
                    'id':               session.pk,
                    'title':            session.title,
                    'skill':            session.skill.name,
                    'start_time':       start_fmt,
                    'end_time':         end_fmt,
                    'credits':          session.credits_required,
                    'type':             session.session_type,
                    'max_participants': session.max_participants,
                    'spots_left':       spots_left,
                    'color':            color,
                })

            days.append({
                'date':     day_date,
                'day_name': day_date.strftime('%a'),
                'day_num':  day_date.day,
                'is_today': day_date == today,
                'sessions': day_sessions,
            })

        weeks.append({
            'week_num': week_num + 1,
            'label':    'This Week' if week_num == 0 else 'Next Week',
            'days':     days,
        })

    return weeks