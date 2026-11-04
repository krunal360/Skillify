from django.contrib import admin
from .models import  Wallet, Transaction
from session.models import Session,Booking


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('title', 'tutor', 'skill', 'date', 'status', 'credits_required')
    list_filter = ('status', 'skill')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('learner', 'session', 'status', 'credits_paid', 'booked_at')
    list_filter = ('status',)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'transaction_type', 'amount', 'balance_after', 'created_at')
    list_filter = ('transaction_type',)