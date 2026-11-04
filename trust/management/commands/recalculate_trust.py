"""
trust/management/commands/recalculate_trust.py
----------------------------------------------
Bulk recalculate trust scores for all tutors.

Usage:
    python manage.py recalculate_trust
    python manage.py recalculate_trust --username john
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Recalculate trust scores for all tutors (or a specific user)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Recalculate for a specific username only',
        )

    def handle(self, *args, **options):
        from trust.calculator import recalculate_trust_score
        from users.models import UserProfile

        username = options.get('username')

        if username:
            # Single user
            try:
                user = User.objects.get(username=username)
                ts = recalculate_trust_score(user)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ {user.username} → {ts.score} ({ts.label_display_full})"
                    )
                )
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"User '{username}' not found"))
            return

        # All tutors — users whose role is tutor
        tutor_profiles = UserProfile.objects.filter(role='tutor').select_related('user')

        if not tutor_profiles.exists():
            self.stdout.write(self.style.WARNING('No tutors found.'))
            return

        total   = tutor_profiles.count()
        success = 0
        failed  = 0

        self.stdout.write(f"Recalculating trust scores for {total} tutors...\n")

        for profile in tutor_profiles:
            try:
                ts = recalculate_trust_score(profile.user)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ {profile.user.username:<20} "
                        f"score: {ts.score:>6.1f}  "
                        f"label: {ts.label_display_full}"
                    )
                )
                success += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ {profile.user.username} — {e}")
                )
                failed += 1

        self.stdout.write(
            f"\nDone. {success} succeeded, {failed} failed out of {total} tutors."
        )