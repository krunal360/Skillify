import json
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.core.mail import send_mail
from django.conf import settings

from users.models import UserProfile
from users.forms import RegisterForm, LoginForm, OTPForm
from users.utils import generate_otp



def index(request):
    from skills.models import Skill
    from session.models import Session
    skills = Skill.objects.all()
    tutor_count = UserProfile.objects.filter(role='tutor', is_verified=True).count()
    session_count = Session.objects.filter(status='completed').count()
    skill_count = Skill.objects.count()
    context = {
        'skills': skills,
        'tutor_count': tutor_count,
        'session_count': session_count,
        'skill_count': skill_count,
    }
    return render(request, 'users/index.html', context)


def register_view(request):
    if request.method == 'POST':
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
    return render(request, 'users/register.html')


def verify_otp_view(request):
    email = request.session.get('verify_email')
    if not email:
        messages.error(request, 'No email to verify.')
        return redirect('register')
    if request.method == 'POST':
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
    return render(request, 'users/verify_otp.html', {'email': email})


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
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            role = form.cleaned_data.get('role', 'learner')
            try:
                user_obj = User.objects.get(email=email)
            except User.DoesNotExist:
                messages.error(request, 'No account found with this email.')
                return render(request, 'users/login.html')
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
    return render(request, 'users/login.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'Logged out successfully.')
    return redirect('index')


def forgot_password_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        if not email:
            messages.error(request, 'Please enter your email address.')
            return render(request, 'users/forgot_password.html')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, 'No account found with this email.')
            return render(request, 'users/forgot_password.html')
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
    return render(request, 'users/forgot_password.html')


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
            return render(request, 'users/reset_password.html', {'email': email})
        if len(new_password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
            return render(request, 'users/reset_password.html', {'email': email})
        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'users/reset_password.html', {'email': email})
        try:
            user = User.objects.get(email=email)
            profile = user.profile
            if profile.otp != otp:
                messages.error(request, 'Invalid OTP. Please try again.')
                return render(request, 'users/reset_password.html', {'email': email})
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
            messages.success(request, 'Password changed successfully! You can now login.')
            return redirect('login')
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
            return redirect('forgot_password')
    return render(request, 'users/reset_password.html', {'email': email})


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


@login_required
def switch_role(request):
    profile = request.user.profile
    profile.role = 'tutor' if profile.role == 'learner' else 'learner'
    profile.save()
    messages.success(request, f'Switched to {profile.get_role_display()} mode.')
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


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
                'fullName': request.POST.get('fullName', ''),
                'email': request.POST.get('email', ''),
                'password': request.POST.get('password', ''),
                'confirmPassword': request.POST.get('confirmPassword', ''),
                'role': request.POST.get('role', 'learner'),
            }
        full_name = data.get('fullName', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        confirm_password = data.get('confirmPassword', '')
        role = data.get('role', 'learner')
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
        names = full_name.split(' ', 1)
        first_name = names[0]
        last_name = names[1] if len(names) > 1 else ''
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
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