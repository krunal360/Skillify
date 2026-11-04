import random
import string
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Avg, Count
from django.core.mail import send_mail
from django.conf import settings
from django.views.decorators.http import require_GET

from users.models import UserProfile
from session.models import Session
from reviews.models import Review
from session.models import Booking
from core.models import Wallet, Transaction


def generate_otp():
    return ''.join(random.choices(string.digits, k=6))


# ==================== AUTH ====================

def register_view(request):
    if request.method == 'POST':
        from .forms import RegisterForm
        form = RegisterForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            names = data['fullName'].split(' ', 1)
            first_name = names[0]
            last_name = names[1] if len(names) > 1 else ''

            user = User.objects.create_user(
                username=data['email'],
                email=data['email'],
                password=data['password'],
                first_name=first_name,
                last_name=last_name,
                is_active=False,
            )
            profile = user.profile
            profile.role = data['role']
            otp = generate_otp()
            profile.otp = otp
            profile.otp_created_at = timezone.now()
            profile.save()

            try:
                send_mail(
                    'Skillify - Verify Your Email',
                    f'Your OTP verification code is: {otp}\n\nThis code expires in 5 minutes.',
                    settings.DEFAULT_FROM_EMAIL,
                    [data['email']],
                    fail_silently=False,
                )
            except Exception:
                pass

            request.session['verify_email'] = data['email']
            messages.success(request, f'OTP sent to {data["email"]}. Please verify.')
            return redirect('verify_otp')
        else:
            for error in form.errors.values():
                messages.error(request, error[0] if isinstance(error, list) else error)
    return render(request, 'core/register.html')


def verify_otp_view(request):
    email = request.session.get('verify_email')
    if not email:
        messages.error(request, 'No email to verify.')
        return redirect('register')

    if request.method == 'POST':
        from .forms import OTPForm
        form = OTPForm(request.POST)
        if form.is_valid():
            otp = form.cleaned_data['otp']
            try:
                user = User.objects.get(email=email)
                profile = user.profile
                if profile.otp == otp:
                    if profile.otp_created_at and (timezone.now() - profile.otp_created_at).seconds <= 300:
                        user.is_active = True
                        user.save()
                        profile.is_verified = True
                        profile.otp = ''
                        profile.save()
                        del request.session['verify_email']
                        messages.success(request, 'Email verified! You can now login.')
                        return redirect('login')
                    else:
                        messages.error(request, 'OTP has expired. Please request a new one.')
                else:
                    messages.error(request, 'Invalid OTP. Please try again.')
            except User.DoesNotExist:
                messages.error(request, 'User not found.')
    return render(request, 'core/verify_otp.html', {'email': email})


def resend_otp_view(request):
    email = request.session.get('verify_email')
    if not email:
        return redirect('register')
    try:
        user = User.objects.get(email=email)
        profile = user.profile
        otp = generate_otp()
        profile.otp = otp
        profile.otp_created_at = timezone.now()
        profile.save()
        try:
            send_mail(
                'Skillify - New OTP',
                f'Your new OTP verification code is: {otp}\n\nThis code expires in 5 minutes.',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
        except Exception:
            pass
        messages.success(request, 'New OTP sent!')
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
    return redirect('verify_otp')


def login_view(request):
    if request.method == 'POST':
        from .forms import LoginForm
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            role = form.cleaned_data.get('role', 'learner')

            try:
                user_obj = User.objects.get(email=email)
            except User.DoesNotExist:
                messages.error(request, 'No account found with this email.')
                return render(request, 'core/login.html')

            if not user_obj.is_active:
                profile = user_obj.profile
                if not profile.is_verified:
                    request.session['verify_email'] = email
                    messages.error(request, 'Please verify your email first.')
                    return redirect('verify_otp')

            user = authenticate(request, username=user_obj.username, password=password)
            if user is not None:
                login(request, user)
                profile = user.profile
                if role:
                    profile.role = role
                    profile.save()
                messages.success(request, f'Welcome back, {user.first_name}!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid email or password.')
    return render(request, 'core/login.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'Logged out successfully.')
    return redirect('index')


# ==================== FORGOT / RESET PASSWORD ====================

def forgot_password_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        if not email:
            messages.error(request, 'Please enter your email address.')
            return render(request, 'core/forgot_password.html')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, 'No account found with this email.')
            return render(request, 'core/forgot_password.html')

        profile = user.profile
        otp = generate_otp()
        profile.otp = otp
        profile.otp_created_at = timezone.now()
        profile.save()

        try:
            send_mail(
                'Skillify - Password Reset OTP',
                f'Your password reset OTP is: {otp}\n\nThis code expires in 5 minutes.\n\nIf you did not request this, please ignore this email.',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
        except Exception:
            pass

        request.session['reset_email'] = email
        messages.success(request, f'OTP sent to {email}.')
        return redirect('reset_password')

    return render(request, 'core/forgot_password.html')


def reset_password_view(request):
    email = request.session.get('reset_email')
    if not email:
        messages.error(request, 'Please request a password reset first.')
        return redirect('forgot_password')

    if request.method == 'POST':
        otp = request.POST.get('otp', '').strip()
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not otp or not new_password:
            messages.error(request, 'Please fill in all fields.')
            return render(request, 'core/reset_password.html', {'email': email})
        if len(new_password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
            return render(request, 'core/reset_password.html', {'email': email})
        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'core/reset_password.html', {'email': email})

        try:
            user = User.objects.get(email=email)
            profile = user.profile

            if profile.otp != otp:
                messages.error(request, 'Invalid OTP. Please try again.')
                return render(request, 'core/reset_password.html', {'email': email})
            if profile.otp_created_at and (timezone.now() - profile.otp_created_at).seconds > 300:
                messages.error(request, 'OTP has expired. Please request a new one.')
                return redirect('forgot_password')

            user.set_password(new_password)
            user.save()
            profile.otp = ''
            profile.otp_created_at = None
            profile.save()

            if 'reset_email' in request.session:
                del request.session['reset_email']

            messages.success(request, 'Password changed successfully!')
            return redirect('login')

        except User.DoesNotExist:
            messages.error(request, 'User not found.')
            return redirect('forgot_password')

    return render(request, 'core/reset_password.html', {'email': email})


def resend_reset_otp_view(request):
    email = request.session.get('reset_email')
    if not email:
        messages.error(request, 'Please start the password reset process first.')
        return redirect('forgot_password')

    try:
        user = User.objects.get(email=email)
        profile = user.profile
        otp = generate_otp()
        profile.otp = otp
        profile.otp_created_at = timezone.now()
        profile.save()

        try:
            send_mail(
                'Skillify - New Password Reset OTP',
                f'Your new password reset OTP is: {otp}\n\nThis code expires in 5 minutes.',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
        except Exception:
            pass

        messages.success(request, f'New OTP sent to {email}!')
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect('forgot_password')

    return redirect('reset_password')


# ==================== DASHBOARD ====================

@login_required
def dashboard_view(request):
    profile = request.user.profile
    wallet  = request.user.wallet
    today   = timezone.now().date()

    bookings = Booking.objects.filter(
        learner=request.user
    ).select_related('session', 'session__tutor', 'session__skill')

    upcoming_bookings = bookings.filter(
        status='confirmed',
        session__status='upcoming',
        session__date__gte=today
    ).order_by('session__date', 'session__start_time')[:5]

    completed_bookings = bookings.filter(
        status__in=['completed', 'pending_review']
    ).order_by('-session__date')[:5]

    tutor_upcoming_sessions = None
    tutor_stats = {}

    if profile.role == 'tutor':
        tutor_upcoming_sessions = Session.objects.filter(
            tutor=request.user,
            status='upcoming',
            date__gte=today
        ).select_related('skill').order_by('date', 'start_time')[:5]

        total_sessions  = Session.objects.filter(tutor=request.user).count()
        completed_count = Session.objects.filter(tutor=request.user, status='completed').count()
        avg_rating_val  = Review.objects.filter(tutor=request.user).aggregate(avg=Avg('rating'))['avg'] or 0
        total_students  = Booking.objects.filter(
            session__tutor=request.user
        ).values('learner').distinct().count()

        tutor_stats = {
            'total_sessions':     total_sessions,
            'completed_sessions': completed_count,
            'upcoming_count':     tutor_upcoming_sessions.count(),
            'avg_rating':         round(avg_rating_val, 1),
            'total_students':     total_students,
            'trust_score':        profile.trust_score,  # float — already there
            'trust_score_obj':    getattr(request.user, 'trust_score', None),  # ← add this
        }

    # ── Recommended tutors (for learner dashboard) ─────────────────
    from trust.recommender import get_recommended_tutors
    recommended_tutors = []
    if profile.role == 'learner':
        recommended_tutors = get_recommended_tutors(request.user, n=6)
    context = {
        'profile':                 profile,
        'wallet':                  wallet,
        'upcoming_bookings':       upcoming_bookings,
        'completed_bookings':      completed_bookings,
        'tutor_upcoming_sessions': tutor_upcoming_sessions,
        'tutor_stats':             tutor_stats,
        'today':                   today,
        'recommended_tutors': recommended_tutors,
    }
    return render(request, 'core/dashboard.html', context)


# ==================== ROLE SWITCHING ====================

@login_required
def switch_role(request):
    profile = request.user.profile
    profile.role = 'tutor' if profile.role == 'learner' else 'learner'
    profile.save()
    messages.success(request, f'Switched to {profile.get_role_display()} mode.')
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


# ==================== API ENDPOINTS ====================

@login_required
def api_switch_role(request):
    if request.method == 'POST':
        profile = request.user.profile
        profile.role = 'tutor' if profile.role == 'learner' else 'learner'
        profile.save()
        return JsonResponse({'status': 'ok', 'role': profile.role})
    return JsonResponse({'error': 'POST required'}, status=400)


@require_GET
def api_check_email(request):
    email = request.GET.get('email', '').strip().lower()
    if not email:
        return JsonResponse({'exists': False})
    exists = User.objects.filter(email=email).exists()
    return JsonResponse({'exists': exists, 'email': email})


def api_register(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=400)

    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = {
                'fullName':       request.POST.get('fullName', ''),
                'email':          request.POST.get('email', ''),
                'password':       request.POST.get('password', ''),
                'confirmPassword': request.POST.get('confirmPassword', ''),
                'role':           request.POST.get('role', 'learner'),
            }

        full_name        = data.get('fullName', '').strip()
        email            = data.get('email', '').strip().lower()
        password         = data.get('password', '')
        confirm_password = data.get('confirmPassword', '')
        role             = data.get('role', 'learner')

        errors = {}
        if not full_name or len(full_name) < 2:
            errors['fullName'] = 'Full name is required (min 2 characters).'
        if not email:
            errors['email'] = 'Email is required.'
        elif '@' not in email or '.' not in email.split('@')[-1]:
            errors['email'] = 'Please enter a valid email address.'
        elif User.objects.filter(email=email).exists():
            errors['email'] = 'An account with this email already exists.'
        if not password:
            errors['password'] = 'Password is required.'
        elif len(password) < 6:
            errors['password'] = 'Password must be at least 6 characters.'
        if password != confirm_password:
            errors['confirmPassword'] = 'Passwords do not match.'
        if role not in ('learner', 'tutor'):
            errors['role'] = 'Invalid role selected.'

        if errors:
            return JsonResponse({'success': False, 'errors': errors}, status=400)

        names      = full_name.split(' ', 1)
        first_name = names[0]
        last_name  = names[1] if len(names) > 1 else ''

        user = User.objects.create_user(
            username=email, email=email, password=password,
            first_name=first_name, last_name=last_name,
            is_active=False,
        )
        profile = user.profile
        profile.role = role
        otp = generate_otp()
        profile.otp = otp
        profile.otp_created_at = timezone.now()
        profile.save()

        try:
            send_mail(
                'Skillify - Verify Your Email',
                f'Your OTP verification code is: {otp}\n\nThis code expires in 5 minutes.',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
        except Exception:
            pass

        request.session['verify_email'] = email
        return JsonResponse({
            'success': True,
            'message': f'OTP sent to {email}. Redirecting to verification...',
            'redirect': '/verify-otp/',
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
@login_required
def wallet_view(request):
    from django.db.models import Sum
    wallet       = request.user.wallet
    transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at')
    profile      = request.user.profile

    
    
    earned_types = ['tutor_earning', 'signup_bonus', 'credit', 'refund' ]
    spent_types  = ['session_payment', 'debit', 'booking_payment']

    total_earned = transactions.filter(
        transaction_type__in=earned_types
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_spent = transactions.filter(
        transaction_type__in=spent_types
    ).aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'wallet':        wallet,
        'transactions':  transactions,
        'profile':       profile,
        'total_earned':  total_earned,
        'total_spent':   total_spent,
        'earned_types':  earned_types,
        'spent_types':   spent_types,
    }
    return render(request, 'core/wallet.html', context)

@login_required
def wallet_export_view(request):
    import csv
    from django.http import HttpResponse
    from django.db.models import Sum

    wallet       = request.user.wallet
    filter_type  = request.GET.get('filter', 'all')

    earned_types = ['tutor_earning', 'signup_bonus', 'credit', 'refund', 'credits_unfrozen']
    spent_types  = ['credits_frozen', 'session_payment', 'debit', 'booking_payment']

    transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at')

    if filter_type == 'earned':
        transactions = transactions.filter(transaction_type__in=earned_types)
        filename = 'earned_transactions'
    elif filter_type == 'spent':
        transactions = transactions.filter(transaction_type__in=spent_types)
        filename = 'spent_transactions'
    else:
        filename = 'all_transactions'

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date', 'Description', 'Type', 'Amount', 'Balance After'])

    for txn in transactions:
        writer.writerow([
            txn.created_at.strftime('%Y-%m-%d %H:%M'),
            txn.description,
            txn.get_transaction_type_display(),
            txn.amount,
            txn.balance_after,
        ])

    return response