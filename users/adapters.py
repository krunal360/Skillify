from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from django.contrib.auth.models import User
from django.shortcuts import redirect


class SkillifyAccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter to handle standard allauth account operations.
    """

    def get_login_redirect_url(self, request):
        return '/dashboard/'

    def get_logout_redirect_url(self, request):
        return '/login/'


class SkilifySocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapter for Google OAuth.
    - Links Google login to existing email-matched accounts
    - Auto-creates UserProfile on first Google login
    - Sets default role to 'learner'
    """

    def pre_social_login(self, request, sociallogin):
        """
        Called after OAuth but before login is finalized.
        Links Google account to existing user if email matches.
        """
        # If user is already logged in, skip
        if request.user.is_authenticated:
            return

        # Get email from Google
        if not sociallogin.is_existing:
            email = sociallogin.account.extra_data.get('email', '').lower()

            if email:
                try:
                    # Check if user with this email already exists
                    existing_user = User.objects.get(email__iexact=email)
                    # Connect Google account to existing user
                    sociallogin.connect(request, existing_user)
                except User.DoesNotExist:
                    # New user — will be created automatically
                    pass

    def save_user(self, request, sociallogin, form=None):
        """
        Called when a new user is created via Google OAuth.
        Creates UserProfile with default role 'learner'.
        """
        user = super().save_user(request, sociallogin, form)

        # Set username from email if not set
        if not user.username:
            base_username = user.email.split('@')[0]
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            user.username = username
            user.save()

        # Set first and last name from Google data
        extra_data = sociallogin.account.extra_data
        if not user.first_name:
            user.first_name = extra_data.get('given_name', '')
        if not user.last_name:
            user.last_name = extra_data.get('family_name', '')
        user.save()

        # Create UserProfile if it doesn't exist
        try:
            from users.models import UserProfile
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'role': 'learner',       # Default role
                    'is_verified': True,     # Google accounts are pre-verified
                }
            )

            # If profile already exists, just mark as verified
            if not created:
                profile.is_verified = True
                profile.save()

        except Exception as e:
            # Log error but don't break login
            print(f"Error creating UserProfile for Google user: {e}")

        # Create Wallet if it doesn't exist
        try:
            from core.models import Wallet, Transaction
            wallet, wallet_created = Wallet.objects.get_or_create(
                user=user,
                defaults={'balance': 100}
            )

            # Give signup bonus if new wallet
            if wallet_created:
                Transaction.objects.create(
                    wallet=wallet,
                    transaction_type='signup_bonus',
                    amount=100,
                    description='Welcome bonus — Google signup',
                    balance_after=100
                )

        except Exception as e:
            print(f"Error creating Wallet for Google user: {e}")

        return user

    def is_open_for_signup(self, request, sociallogin):
        """
        Allow signup via Google OAuth.
        """
        return True