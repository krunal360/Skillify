from django.core.management.base import BaseCommand
from session.views import _check_auto_complete

class Command(BaseCommand):
    help = 'Auto-complete and auto-cancel overdue sessions'

    def handle(self, *args, **kwargs):
        try:
            _check_auto_complete()
            self.stdout.write(
                self.style.SUCCESS('Successfully processed sessions')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {e}')
            )