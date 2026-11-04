"""
skillify_admin/views.py
-----------------------
Admin panel views.
All pages protected by @admin_required decorator.
"""

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
import json

from disputes.models import Dispute
from skillify_admin.decorators import admin_required


# ==============================================================================
# Admin Login / Logout
# ==============================================================================

def admin_login_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        if not username or not password:
            messages.error(request, 'Please enter both username and password.')
            return render(request, 'skillify_admin/login.html')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_staff:
                login(request, user)
                return redirect('admin_dashboard')
            else:
                messages.error(request, 'Access denied. You do not have admin privileges.')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'skillify_admin/login.html')


def admin_logout_view(request):
    logout(request)
    return redirect('admin_login')


# ==============================================================================
# Dashboard
# ==============================================================================

@admin_required
def admin_dashboard_view(request):
    from users.models import UserProfile
    from skills.models import Skill
    from session.models import Session, Booking
    from reviews.models import Review
    from messaging.models import Message
    from core.models import Wallet, Transaction

    today     = timezone.now().date()
    now       = timezone.now()
    week_ago  = now - timezone.timedelta(days=7)
    month_ago = now - timezone.timedelta(days=30)

    total_users     = User.objects.filter(is_active=True).count()
    total_tutors    = UserProfile.objects.filter(role='tutor').count()
    total_learners  = UserProfile.objects.filter(role='learner').count()
    total_skills    = Skill.objects.count()
    total_sessions  = Session.objects.count()
    total_bookings  = Booking.objects.count()
    total_reviews   = Review.objects.count()
    total_messages  = Message.objects.count()
    new_this_week   = User.objects.filter(date_joined__gte=week_ago).count()
    new_this_month  = User.objects.filter(date_joined__gte=month_ago).count()
    active_today    = Session.objects.filter(date=today, status='upcoming').count()
    credits_in_system = Wallet.objects.aggregate(total=Sum('balance'))['total'] or 0

    from disputes.models import Dispute
    open_disputes = Dispute.objects.filter(status__in=['open', 'under_review']).count()
    recent_activities = []

    for b in Booking.objects.select_related('learner', 'session', 'session__tutor').order_by('-booked_at')[:5]:
        recent_activities.append({
            'icon': 'bi-calendar-check-fill', 'color': '#3B82F6',
            'text': f'{b.learner.get_full_name()} booked "{b.session.title}" with {b.session.tutor.get_full_name()}',
            'time': b.booked_at,
        })

    for r in Review.objects.select_related('reviewer', 'tutor', 'session').order_by('-created_at')[:5]:
        recent_activities.append({
            'icon': 'bi-star-fill', 'color': '#F59E0B',
            'text': f'{r.reviewer.get_full_name()} rated {r.tutor.get_full_name()} {r.rating}★',
            'time': r.created_at,
        })

    for u in User.objects.order_by('-date_joined')[:5]:
        recent_activities.append({
            'icon': 'bi-person-fill', 'color': '#4ECDC4',
            'text': f'New user registered: {u.get_full_name() or u.username}',
            'time': u.date_joined,
        })

    for s in Session.objects.filter(status='completed').select_related('tutor').order_by('-created_at')[:5]:
        recent_activities.append({
            'icon': 'bi-check-circle-fill', 'color': '#10B981',
            'text': f'Session "{s.title}" by {s.tutor.get_full_name()} completed',
            'time': s.created_at,
        })

    recent_activities.sort(key=lambda x: x['time'], reverse=True)
    recent_activities = recent_activities[:15]

    context = {
        'total_users': total_users, 'total_tutors': total_tutors,
        'total_learners': total_learners, 'total_skills': total_skills,
        'total_sessions': total_sessions, 'total_bookings': total_bookings,
        'total_reviews': total_reviews, 'total_messages': total_messages,
        'new_this_week': new_this_week, 'new_this_month': new_this_month,
        'active_today': active_today, 'credits_in_system': credits_in_system,
        'recent_activities': recent_activities,
        'open_disputes': open_disputes,
    }
    return render(request, 'skillify_admin/dashboard.html', context)


# ==============================================================================
# Analytics
# ==============================================================================

@admin_required
def admin_analytics_view(request):
    from session.models import Session, Booking
    from core.models import Transaction
    from trust.models import TrustScore

    now = timezone.now()

    # 1. User Growth
    user_growth_labels, user_growth_data = [], []
    for i in range(7, -1, -1):
        ws = now - timezone.timedelta(weeks=i+1)
        we = now - timezone.timedelta(weeks=i)
        user_growth_labels.append(ws.strftime('%b %d'))
        user_growth_data.append(User.objects.filter(date_joined__gte=ws, date_joined__lt=we).count())

    # 2. Booking Trend
    booking_trend_labels, booking_trend_data = [], []
    for i in range(7, -1, -1):
        ws = now - timezone.timedelta(weeks=i+1)
        we = now - timezone.timedelta(weeks=i)
        booking_trend_labels.append(ws.strftime('%b %d'))
        booking_trend_data.append(Booking.objects.filter(booked_at__gte=ws, booked_at__lt=we).count())

    # 3. Skill Popularity — sessions per skill
    skill_pop = Session.objects.values('skill__name').annotate(
        count=Count('id')
    ).order_by('-count')[:8]
    skill_pop_labels = [s['skill__name'] for s in skill_pop]
    skill_pop_data   = [s['count'] for s in skill_pop]

    # 4. Top Tutors by Earnings
    top_tutors_qs = Transaction.objects.filter(
        transaction_type='tutor_earning'
    ).values('wallet__user').annotate(
        total_earned=Sum('amount')
    ).order_by('-total_earned')[:5]

    top_tutors_list = []
    for t in top_tutors_qs:
        try:
            u = User.objects.get(pk=t['wallet__user'])
            sessions = Session.objects.filter(tutor=u, status='completed').count()
            try:
                trust = round(u.trust_score.score)
            except Exception:
                trust = 0
            top_tutors_list.append({
                'user': u, 'sessions': sessions,
                'trust': trust, 'total_earned': t['total_earned'],
            })
        except Exception:
            continue

    # 5. Trust Score Distribution by label
    trust_labels = ['New', 'Beginner', 'Developing', 'Established', 'Expert', 'Master']
    trust_keys   = ['new', 'beginner', 'developing', 'established', 'expert', 'master']
    trust_data   = [TrustScore.objects.filter(label=k).count() for k in trust_keys]

    # 6. Session Completion Rate
    completed = Session.objects.filter(status='completed').count()
    cancelled = Session.objects.filter(status='cancelled').count()
    upcoming  = Session.objects.filter(status='upcoming').count()

    # 7. Credit Flow
    credit_labels, credits_earned, credits_spent = [], [], []
    for i in range(7, -1, -1):
        ws = now - timezone.timedelta(weeks=i+1)
        we = now - timezone.timedelta(weeks=i)
        credit_labels.append(ws.strftime('%b %d'))
        credits_earned.append(
            Transaction.objects.filter(
                transaction_type__in=['tutor_earning', 'signup_bonus', 'credit', 'refund'],
                created_at__gte=ws, created_at__lt=we
            ).aggregate(total=Sum('amount'))['total'] or 0
        )
        credits_spent.append(
            Transaction.objects.filter(
                transaction_type__in=['session_payment', 'booking_payment'],
                created_at__gte=ws, created_at__lt=we
            ).aggregate(total=Sum('amount'))['total'] or 0
        )

    context = {
        'user_growth_labels':   json.dumps(user_growth_labels),
        'user_growth_data':     json.dumps(user_growth_data),
        'booking_trend_labels': json.dumps(booking_trend_labels),
        'booking_trend_data':   json.dumps(booking_trend_data),
        'skill_pop_labels':     json.dumps(skill_pop_labels),
        'skill_pop_data':       json.dumps(skill_pop_data),
        'top_tutors':           top_tutors_list,
        'trust_labels':         json.dumps(trust_labels),
        'trust_data':           json.dumps(trust_data),
        'completed':            completed,
        'cancelled':            cancelled,
        'upcoming':             upcoming,
        'credit_labels':        json.dumps(credit_labels),
        'credits_earned':       json.dumps(credits_earned),
        'credits_spent':        json.dumps(credits_spent),
    }
    return render(request, 'skillify_admin/analytics.html', context)


# ==============================================================================
# User Management
# ==============================================================================

@admin_required
def admin_users_view(request):
    search      = request.GET.get('search', '').strip()
    role_filter = request.GET.get('role', 'all')

    if request.method == 'POST':
        action  = request.POST.get('action')
        user_id = request.POST.get('user_id')
        try:
            target_user = User.objects.get(pk=user_id)
            if action == 'suspend':
                target_user.is_active = False
                target_user.save()
                messages.success(request, f'{target_user.get_full_name()} suspended.')
            elif action == 'unsuspend':
                target_user.is_active = True
                target_user.save()
                messages.success(request, f'{target_user.get_full_name()} reactivated.')
            elif action == 'delete':
                name = target_user.get_full_name()
                target_user.delete()
                messages.success(request, f'{name} deleted.')
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
        return redirect('admin_users')

    if request.GET.get('export') == 'csv':
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="users.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Email', 'Role', 'Trust Score', 'Balance', 'Status', 'Joined'])
        for u in User.objects.select_related('profile').order_by('-date_joined'):
            try:
                role    = u.profile.role
                balance = u.wallet.balance
                trust   = round(u.trust_score.score)
            except Exception:
                role = '-'; balance = 0; trust = 0
            writer.writerow([
                u.get_full_name(), u.email, role, trust, balance,
                'Active' if u.is_active else 'Suspended',
                u.date_joined.strftime('%Y-%m-%d'),
            ])
        return response

    users = User.objects.select_related('profile').order_by('-date_joined')

    if search:
        users = users.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search)
        )

    if role_filter == 'tutor':
        users = users.filter(profile__role='tutor')
    elif role_filter == 'learner':
        users = users.filter(profile__role='learner')

    user_data = []
    for u in users:
        try:
            role    = u.profile.role
            balance = u.wallet.balance
        except Exception:
            role = '-'; balance = 0
        try:
            trust_val = round(u.trust_score.score)
        except Exception:
            trust_val = 0
        user_data.append({
            'user': u, 'role': role,
            'trust': trust_val, 'balance': balance,
            'is_active': u.is_active,
        })

    context = {
        'user_data': user_data, 'search': search,
        'role_filter': role_filter, 'total': len(user_data),
    }
    return render(request, 'skillify_admin/users.html', context)


# ==============================================================================
# Placeholder views — replaced one by one
# ==============================================================================

@admin_required
def admin_tutors_view(request):
    from users.models import UserProfile

    search = request.GET.get('search', '').strip()

    if request.method == 'POST':
        action  = request.POST.get('action')
        user_id = request.POST.get('user_id')
        try:
            target_user = User.objects.get(pk=user_id)
            if action == 'suspend':
                target_user.is_active = False
                target_user.save()
                messages.success(request, f'{target_user.get_full_name()} suspended.')
            elif action == 'unsuspend':
                target_user.is_active = True
                target_user.save()
                messages.success(request, f'{target_user.get_full_name()} reactivated.')
            elif action == 'recalculate':
                from trust.calculator import recalculate_trust_score
                recalculate_trust_score(target_user)
                messages.success(request, f'Trust score recalculated for {target_user.get_full_name()}.')
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
        return redirect('admin_tutors')

    if request.GET.get('export') == 'csv':
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="tutors.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Email', 'Trust Score', 'Trust Label', 'Avg Rating', 'Sessions', 'Balance', 'Status'])
        for p in UserProfile.objects.filter(role='tutor').select_related('user'):
            try:
                ts      = p.user.trust_score
                score   = round(ts.score)
                label   = ts.label
            except Exception:
                score = 0; label = 'new'
            from reviews.models import Review
            from django.db.models import Avg
            avg_rating = Review.objects.filter(tutor=p.user).aggregate(avg=Avg('rating'))['avg'] or 0
            from session.models import Session
            sessions = Session.objects.filter(tutor=p.user).count()
            try:
                balance = p.user.wallet.balance
            except Exception:
                balance = 0
            writer.writerow([
                p.user.get_full_name(), p.user.email,
                score, label, round(avg_rating, 1),
                sessions, balance,
                'Active' if p.user.is_active else 'Suspended',
            ])
        return response

    tutors = UserProfile.objects.filter(role='tutor').select_related('user').order_by('user__first_name')

    if search:
        tutors = tutors.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search)
        )

    from reviews.models import Review
    from session.models import Session
    from django.db.models import Avg

    tutor_data = []
    for p in tutors:
        try:
            ts    = p.user.trust_score
            score = round(ts.score)
            label = ts.label_display_full
        except Exception:
            score = 0
            label = 'New Tutor 🆕'

        avg_rating = Review.objects.filter(
            tutor=p.user
        ).aggregate(avg=Avg('rating'))['avg'] or 0

        sessions = Session.objects.filter(tutor=p.user).count()

        try:
            balance = p.user.wallet.balance
        except Exception:
            balance = 0

        # Trust score color
        if score <= 40:
            color = '#EF4444'
        elif score <= 60:
            color = '#F59E0B'
        elif score <= 75:
            color = '#EAB308'
        elif score <= 90:
            color = '#10B981'
        else:
            color = '#0D9488'

        tutor_data.append({
            'user':       p.user,
            'score':      score,
            'label':      label,
            'avg_rating': round(avg_rating, 1),
            'sessions':   sessions,
            'balance':    balance,
            'is_active':  p.user.is_active,
            'color':      color,
        })

    context = {
        'tutor_data': tutor_data,
        'search':     search,
        'total':      len(tutor_data),
    }
    return render(request, 'skillify_admin/tutors.html', context)

@admin_required
def admin_skills_view(request):
    from skills.models import Skill
    from session.models import Session, Booking
    from users.models import UserProfile
    from reviews.models import Review
    from django.db.models import Avg

    if request.method == 'POST':
        action   = request.POST.get('action')
        skill_id = request.POST.get('skill_id')

        if action == 'add':
            name = request.POST.get('name', '').strip()
            icon = request.POST.get('icon', 'bi-lightbulb').strip()
            if name:
                if Skill.objects.filter(name__iexact=name).exists():
                    messages.error(request, f'Skill "{name}" already exists.')
                else:
                    Skill.objects.create(name=name, icon=icon)
                    messages.success(request, f'Skill "{name}" added.')
            else:
                messages.error(request, 'Skill name is required.')

        elif action == 'edit':
            name = request.POST.get('name', '').strip()
            icon = request.POST.get('icon', '').strip()
            try:
                skill = Skill.objects.get(pk=skill_id)
                skill.name = name
                if icon:
                    skill.icon = icon
                skill.save()
                messages.success(request, f'Skill "{name}" updated.')
            except Skill.DoesNotExist:
                messages.error(request, 'Skill not found.')

        elif action == 'delete':
            try:
                skill = Skill.objects.get(pk=skill_id)
                name  = skill.name
                skill.delete()
                messages.success(request, f'Skill "{name}" deleted.')
            except Skill.DoesNotExist:
                messages.error(request, 'Skill not found.')

        return redirect('admin_skills')

    skills = Skill.objects.all().order_by('name')

    skill_data = []
    for skill in skills:
        sessions  = Session.objects.filter(skill=skill).count()
        bookings  = Booking.objects.filter(session__skill=skill).count()
        tutors    = UserProfile.objects.filter(skills=skill).count()
        learners  = UserProfile.objects.filter(learning_interests=skill).count()
        avg_rating = Review.objects.filter(
            session__skill=skill
        ).aggregate(avg=Avg('rating'))['avg'] or 0

        skill_data.append({
            'skill':      skill,
            'sessions':   sessions,
            'bookings':   bookings,
            'tutors':     tutors,
            'learners':   learners,
            'avg_rating': round(avg_rating, 1),
        })

    context = {
        'skill_data': skill_data,
        'total':      len(skill_data),
    }
    return render(request, 'skillify_admin/skills.html', context)

@admin_required
def admin_sessions_view(request):
    from session.models import Session, Booking

    status_filter = request.GET.get('status', 'all')
    level_filter  = request.GET.get('level', 'all')
    type_filter   = request.GET.get('type', 'all')

    if request.GET.get('export') == 'csv':
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="sessions.csv"'
        writer = csv.writer(response)
        writer.writerow(['Title', 'Tutor', 'Skill', 'Level', 'Type', 'Date',
                         'Start Time', 'End Time', 'Credits', 'Status', 'Total Bookings'])
        for s in Session.objects.select_related('tutor', 'skill').order_by('-date'):
            writer.writerow([
                s.title, s.tutor.get_full_name(), s.skill.name,
                s.level, s.session_type, s.date,
                s.start_time, s.end_time, s.credits_required,
                s.status, s.bookings.count(),
            ])
        return response

    sessions = Session.objects.select_related(
        'tutor', 'skill'
    ).order_by('-date', '-start_time')

    if status_filter != 'all':
        sessions = sessions.filter(status=status_filter)
    if level_filter != 'all':
        sessions = sessions.filter(level=level_filter)
    if type_filter != 'all':
        sessions = sessions.filter(session_type=type_filter)

    session_data = []
    for s in sessions:
        bookings = Booking.objects.filter(session=s)
        session_data.append({
            'session':  s,
            'bookings': bookings,
            'booking_count': bookings.count(),
        })

    context = {
        'session_data':   session_data,
        'status_filter':  status_filter,
        'level_filter':   level_filter,
        'type_filter':    type_filter,
        'total':          len(session_data),
    }
    return render(request, 'skillify_admin/sessions.html', context)

    
@admin_required
def admin_reviews_view(request):
    from reviews.models import Review
    from django.db.models import Q

    # Get all filter parameters
    rating_filter = request.GET.get('rating', 'all')
    session_type_filter = request.GET.get('session_type', 'all')
    recommendation_filter = request.GET.get('recommendation', 'all')
    tags_filter_list = request.GET.getlist('tags')  # Get multiple tags
    tutor_filter = request.GET.get('tutor', 'all')

    # Build base queryset
    reviews = Review.objects.select_related(
        'reviewer', 'tutor', 'session', 'session__skill'
    ).order_by('-created_at')

    # Apply filters
    if rating_filter != 'all':
        reviews = reviews.filter(rating=int(rating_filter))

    if session_type_filter != 'all':
        reviews = reviews.filter(session__session_type=session_type_filter)

    if recommendation_filter != 'all':
        recommended = recommendation_filter == 'yes'
        reviews = reviews.filter(recommended=recommended)

    # Filter by multiple tags (OR logic - show reviews that have ANY of the selected tags)
    if tags_filter_list:
        tag_query = Q()
        for tag in tags_filter_list:
            tag_query |= Q(tags__contains=tag)
        reviews = reviews.filter(tag_query)

    if tutor_filter != 'all':
        reviews = reviews.filter(tutor__id=int(tutor_filter))

    # Handle CSV export
    if request.GET.get('export') == 'csv':
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="reviews.csv"'
        writer = csv.writer(response)
        writer.writerow(['Reviewer', 'Tutor', 'Session', 'Session Type', 'Rating', 'Recommended', 'Tags', 'Comment', 'Date'])
        for r in reviews:
            writer.writerow([
                r.reviewer.get_full_name(), r.tutor.get_full_name(),
                r.session.title, r.session.session_type, r.rating,
                'Yes' if r.recommended else 'No',
                ', '.join(r.tags), r.comment,
                r.created_at.strftime('%Y-%m-%d'),
            ])
        return response

    # Get distinct values for filter dropdowns
    all_session_types = Review.objects.filter(
        session__session_type__isnull=False
    ).values_list('session__session_type', flat=True).distinct().order_by('session__session_type')

    all_tags = set()
    for review in Review.objects.values_list('tags', flat=True):
        if review:
            all_tags.update(review)
    all_tags = sorted(list(all_tags))

    all_tutors = Review.objects.values_list(
        'tutor__id', 'tutor__first_name', 'tutor__last_name'
    ).distinct().order_by('tutor__first_name', 'tutor__last_name')

    context = {
        'reviews':                reviews,
        'rating_filter':          rating_filter,
        'session_type_filter':    session_type_filter,
        'recommendation_filter':  recommendation_filter,
        'tags_filter_list':       tags_filter_list,
        'tutor_filter':           tutor_filter,
        'all_session_types':      all_session_types,
        'all_tags':               all_tags,
        'all_tutors':             all_tutors,
        'total':                  reviews.count(),
    }
    return render(request, 'skillify_admin/reviews.html', context)


@admin_required
def admin_disputes_view(request):
    from disputes.models import Dispute
    from session.views import _refund_credits

    if request.method == 'POST':
        action     = request.POST.get('action')
        dispute_id = request.POST.get('dispute_id')
        note       = request.POST.get('resolution_note', '').strip()

        try:
            dispute = Dispute.objects.get(pk=dispute_id)

            if action == 'under_review':
                dispute.status = 'under_review'
                dispute.save()
                # Notify both parties
                try:
                    from notifications.models import Notification
                    for user in [dispute.filed_by, dispute.against]:
                        Notification.create(
                            recipient=user,
                            notification_type='dispute_resolved',
                            title='Dispute Under Review',
                            message=f'Your dispute for "{dispute.booking.session.title}" is now being reviewed by admin.',
                            link=f'/disputes/{dispute.pk}/',
                        )
                except Exception:
                    pass
                messages.success(request, 'Dispute marked as under review.')

            elif action == 'resolve':
                dispute.status          = 'resolved'
                dispute.resolution_note = note
                dispute.resolved_by     = request.user
                dispute.resolved_at     = timezone.now()
                dispute.save()
                # Notify both parties
                try:
                    from notifications.models import Notification
                    for user in [dispute.filed_by, dispute.against]:
                        Notification.create(
                            recipient=user,
                            notification_type='dispute_resolved',
                            title='Dispute Resolved',
                            message=f'Your dispute for "{dispute.booking.session.title}" has been resolved. Note: {note}',
                            link=f'/disputes/{dispute.pk}/',
                        )
                except Exception:
                    pass
                messages.success(request, 'Dispute resolved.')

            elif action == 'resolve_refund':
                # Resolve + refund credits to learner
                dispute.status           = 'resolved'
                dispute.resolution_note  = note
                dispute.resolved_by      = request.user
                dispute.resolved_at      = timezone.now()
                dispute.credits_refunded = True
                dispute.save()
                # Refund credits
                try:
                    booking = dispute.booking
                    if booking.status in ['completed', 'pending_review']:
                        from core.models import Transaction
                        learner_wallet = booking.learner.wallet
                        tutor_wallet   = booking.session.tutor.wallet
                        # Deduct from tutor and refund to learner
                        tutor_wallet.balance   -= booking.credits_paid
                        learner_wallet.balance += booking.credits_paid
                        tutor_wallet.save()
                        learner_wallet.save()
                        Transaction.objects.create(
                            wallet=learner_wallet,
                            transaction_type='refund',
                            amount=booking.credits_paid,
                            description=f'Dispute refund for session: {booking.session.title}',
                            balance_after=learner_wallet.balance,
                        )
                        Transaction.objects.create(
                            wallet=tutor_wallet,
                            transaction_type='debit',
                            amount=booking.credits_paid,
                            description=f'Dispute refund deducted: {booking.session.title}',
                            balance_after=tutor_wallet.balance,
                        )
                except Exception as e:
                    messages.warning(request, f'Dispute resolved but credit refund failed: {e}')

                try:
                    from notifications.models import Notification
                    for user in [dispute.filed_by, dispute.against]:
                        Notification.create(
                            recipient=user,
                            notification_type='dispute_resolved',
                            title='Dispute Resolved — Credits Refunded',
                            message=f'Your dispute for "{dispute.booking.session.title}" has been resolved with a credit refund.',
                            link=f'/disputes/{dispute.pk}/',
                        )
                except Exception:
                    pass
                messages.success(request, 'Dispute resolved and credits refunded.')

            elif action == 'reject':
                dispute.status          = 'rejected'
                dispute.resolution_note = note
                dispute.resolved_by     = request.user
                dispute.resolved_at     = timezone.now()
                dispute.save()
                try:
                    from notifications.models import Notification
                    for user in [dispute.filed_by, dispute.against]:
                        Notification.create(
                            recipient=user,
                            notification_type='dispute_resolved',
                            title='Dispute Rejected',
                            message=f'Your dispute for "{dispute.booking.session.title}" has been rejected. Note: {note}',
                            link=f'/disputes/{dispute.pk}/',
                        )
                except Exception:
                    pass
                messages.success(request, 'Dispute rejected.')

        except Dispute.DoesNotExist:
            messages.error(request, 'Dispute not found.')

        return redirect('admin_disputes')

    status_filter = request.GET.get('status', 'all')
    disputes = Dispute.objects.select_related(
        'booking', 'booking__session', 'booking__session__skill',
        'filed_by', 'against', 'resolved_by'
    ).order_by('-created_at')

    if status_filter != 'all':
        disputes = disputes.filter(status=status_filter)

    open_count = Dispute.objects.filter(status__in=['open', 'under_review']).count()

    context = {
        'disputes':      disputes,
        'status_filter': status_filter,
        'open_count':    open_count,
        'total':         disputes.count(),
    }
    return render(request, 'skillify_admin/disputes.html', context)

@admin_required
def admin_reports_view(request):
    report_type = request.GET.get('type')

    if report_type:
        import csv
        from django.http import HttpResponse
        from core.models import Transaction

        if report_type == 'users':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="users_report.csv"'
            writer = csv.writer(response)
            writer.writerow(['Name', 'Email', 'Role', 'Trust Score', 'Balance', 'Status', 'Joined'])
            for u in User.objects.select_related('profile').order_by('-date_joined'):
                try:
                    role    = u.profile.role
                    balance = u.wallet.balance
                    trust   = round(u.trust_score.score)
                except Exception:
                    role = '-'; balance = 0; trust = 0
                writer.writerow([
                    u.get_full_name(), u.email, role, trust, balance,
                    'Active' if u.is_active else 'Suspended',
                    u.date_joined.strftime('%Y-%m-%d'),
                ])
            return response

        elif report_type == 'sessions':
            from session.models import Session
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="sessions_report.csv"'
            writer = csv.writer(response)
            writer.writerow(['Title', 'Tutor', 'Skill', 'Level', 'Type', 'Date', 'Start', 'End', 'Credits', 'Status', 'Bookings'])
            for s in Session.objects.select_related('tutor', 'skill').order_by('-date'):
                writer.writerow([
                    s.title, s.tutor.get_full_name(), s.skill.name,
                    s.get_level_display(), s.session_type, s.date,
                    s.start_time, s.end_time, s.credits_required,
                    s.status, s.bookings.count(),
                ])
            return response

        elif report_type == 'bookings':
            from session.models import Booking
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="bookings_report.csv"'
            writer = csv.writer(response)
            writer.writerow(['Learner', 'Session', 'Tutor', 'Skill', 'Date', 'Credits Paid', 'Status', 'Booked At'])
            for b in Booking.objects.select_related('learner', 'session', 'session__tutor', 'session__skill').order_by('-booked_at'):
                writer.writerow([
                    b.learner.get_full_name(), b.session.title,
                    b.session.tutor.get_full_name(), b.session.skill.name,
                    b.session.date, b.credits_paid, b.status,
                    b.booked_at.strftime('%Y-%m-%d %H:%M'),
                ])
            return response

        elif report_type == 'transactions':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="transactions_report.csv"'
            writer = csv.writer(response)
            writer.writerow(['User', 'Type', 'Amount', 'Description', 'Balance After', 'Date'])
            for t in Transaction.objects.select_related('wallet__user').order_by('-created_at'):
                writer.writerow([
                    t.wallet.user.get_full_name(),
                    t.get_transaction_type_display(),
                    t.amount, t.description, t.balance_after,
                    t.created_at.strftime('%Y-%m-%d %H:%M'),
                ])
            return response

        elif report_type == 'reviews':
            from reviews.models import Review
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="reviews_report.csv"'
            writer = csv.writer(response)
            writer.writerow(['Reviewer', 'Tutor', 'Session', 'Rating', 'Recommended', 'Tags', 'Comment', 'Date'])
            for r in Review.objects.select_related('reviewer', 'tutor', 'session').order_by('-created_at'):
                writer.writerow([
                    r.reviewer.get_full_name(), r.tutor.get_full_name(),
                    r.session.title, r.rating,
                    'Yes' if r.recommended else 'No',
                    ', '.join(r.tags), r.comment,
                    r.created_at.strftime('%Y-%m-%d'),
                ])
            return response

        elif report_type == 'trust':
            from trust.models import TrustScore
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="trust_scores_report.csv"'
            writer = csv.writer(response)
            writer.writerow([
                'Tutor', 'Email', 'Score', 'Label',
                'Session Performance', 'Review Metrics',
                'NLP Score', 'Profile Completion',
                'Penalty', 'Total Reviews', 'Avg Rating', 'Last Calculated'
            ])
            for ts in TrustScore.objects.select_related('tutor').order_by('-score'):
                writer.writerow([
                    ts.tutor.get_full_name(), ts.tutor.email,
                    ts.score, ts.label,
                    ts.session_performance_score,
                    ts.review_metrics_score,
                    ts.nlp_score,
                    ts.profile_completion_score,
                    ts.duplicate_review_penalty,
                    ts.total_reviews, ts.avg_rating,
                    ts.calculated_at.strftime('%Y-%m-%d %H:%M'),
                ])
            return response

        elif report_type == 'disputes':
            from disputes.models import Dispute
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="disputes_report.csv"'
            writer = csv.writer(response)
            writer.writerow(['#', 'Session', 'Filed By', 'Against', 'Reason', 'Status', 'Credits', 'Resolved By', 'Date'])
            for d in Dispute.objects.select_related('booking__session', 'filed_by', 'against', 'resolved_by').order_by('-created_at'):
                writer.writerow([
                    d.pk, d.booking.session.title,
                    d.filed_by.get_full_name(), d.against.get_full_name(),
                    d.get_reason_display(), d.status,
                    d.booking.credits_paid,
                    d.resolved_by.get_full_name() if d.resolved_by else '—',
                    d.created_at.strftime('%Y-%m-%d'),
                ])
            return response

    # Stats for the page
    from session.models import Session, Booking
    from reviews.models import Review
    from trust.models import TrustScore
    from disputes.models import Dispute
    from core.models import Transaction

    stats = {
        'users':        User.objects.count(),
        'sessions':     Session.objects.count(),
        'bookings':     Booking.objects.count(),
        'transactions': Transaction.objects.count(),
        'reviews':      Review.objects.count(),
        'trust_scores': TrustScore.objects.count(),
        'disputes':     Dispute.objects.count(),
    }

    return render(request, 'skillify_admin/reports.html', {'stats': stats})

@admin_required
def admin_announcements_view(request):
    from notifications.models import Notification
    from users.models import UserProfile

    # New model needed — check if AdminAnnouncement exists
    # For now store announcement history in session or simple approach

    if request.method == 'POST':
        audience      = request.POST.get('audience', 'all')
        title         = request.POST.get('title', '').strip()
        message_text  = request.POST.get('message', '').strip()
        specific_email = request.POST.get('specific_user', '').strip()

        if not title or not message_text:
            messages.error(request, 'Title and message are required.')
            return redirect('admin_announcements')

        recipients = []

        if specific_email:
            try:
                specific_user = User.objects.get(email=specific_email)
                recipients = [specific_user]
            except User.DoesNotExist:
                messages.error(request, f'User with email "{specific_email}" not found.')
                return redirect('admin_announcements')
        elif audience == 'all':
            recipients = list(User.objects.filter(is_active=True))
        elif audience == 'tutors':
            recipients = list(User.objects.filter(
                is_active=True, profile__role='tutor'
            ))
        elif audience == 'learners':
            recipients = list(User.objects.filter(
                is_active=True, profile__role='learner'
            ))

        # Create notification for each recipient
        count = 0
        for recipient in recipients:
            Notification.objects.create(
                recipient=recipient,
                notification_type='announcement',
                title=title,
                message=message_text,
                link='/dashboard/',
            )
            count += 1

        # Save to announcement history
        from skillify_admin.models import AdminAnnouncement
        AdminAnnouncement.objects.create(
            admin=request.user,
            title=title,
            message=message_text,
            audience=audience if not specific_email else 'specific',
            specific_user=specific_user if specific_email else None,
            sent_to_count=count,
        )

        messages.success(request, f'Announcement sent to {count} user(s).')
        return redirect('admin_announcements')

    from skillify_admin.models import AdminAnnouncement
    history = AdminAnnouncement.objects.select_related(
        'admin', 'specific_user'
    ).order_by('-created_at')[:20]

    context = {
        'history': history,
    }
    return render(request, 'skillify_admin/announcements.html', context)

@admin_required
def admin_manage_admins_view(request):
    if not request.user.is_superuser:
        messages.error(request, 'Only superusers can manage admins.')
        return redirect('admin_dashboard')

    if request.method == 'POST':
        action  = request.POST.get('action')
        user_id = request.POST.get('user_id')

        if action == 'add_admin':
            email = request.POST.get('email', '').strip()
            try:
                target = User.objects.get(email=email)
                if target.is_staff:
                    messages.error(request, f'{target.get_full_name()} is already an admin.')
                else:
                    target.is_staff = True
                    target.save()
                    messages.success(request, f'{target.get_full_name()} is now an admin.')
            except User.DoesNotExist:
                messages.error(request, f'No user found with email "{email}".')

        elif action == 'remove_admin':
            try:
                target = User.objects.get(pk=user_id)
                if target == request.user:
                    messages.error(request, 'You cannot remove yourself as admin.')
                elif target.is_superuser:
                    messages.error(request, 'Cannot remove superuser admin rights.')
                else:
                    target.is_staff = False
                    target.save()
                    messages.success(request, f'{target.get_full_name()} removed from admins.')
            except User.DoesNotExist:
                messages.error(request, 'User not found.')

        return redirect('admin_manage_admins')

    admins = User.objects.filter(is_staff=True).order_by('-is_superuser', 'first_name')

    context = {
        'admins': admins,
        'total':  admins.count(),
    }
    return render(request, 'skillify_admin/manage_admins.html', context)