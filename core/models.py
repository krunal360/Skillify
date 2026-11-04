from django.db import models
from django.contrib.auth.models import User


class Wallet(models.Model):
    user           = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance        = models.IntegerField(default=100)
    frozen_balance = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username}'s Wallet: {self.balance} credits"

    def freeze_credits(self, amount):
        """Move credits from available balance into frozen balance"""
        self.balance        -= amount
        self.frozen_balance += amount
        self.save()

    def unfreeze_and_transfer(self, amount, tutor_wallet):
        """Transfer frozen credits to tutor on session completion"""
        self.frozen_balance -= amount
        self.save()
        tutor_wallet.balance += amount
        tutor_wallet.save()

    def unfreeze_and_refund(self, amount):
        """Return frozen credits back to learner on cancellation"""
        self.frozen_balance -= amount
        self.balance        += amount
        self.save()


class Transaction(models.Model):
    TYPE_CHOICES = [
        ('credit',            'Credit'),
        ('debit',             'Debit'),
        ('signup_bonus',      'Signup Bonus'),
        ('booking_payment',   'Booking Payment'),
        ('tutor_earning',     'Tutor Earning'),
        ('credits_frozen',    'Credits Frozen'),
        ('credits_unfrozen',  'Credits Unfrozen'),
        ('session_payment',   'Session Payment'),
        ('refund',            'Refund'),        # ← new
    ]

    wallet           = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    amount           = models.IntegerField()
    description      = models.CharField(max_length=255)
    balance_after    = models.IntegerField()
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.transaction_type}: {self.amount} credits"