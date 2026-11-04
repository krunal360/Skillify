"""
notifications/views.py
----------------------
Views for the notification system.

URLs:
    /notifications/                  → full notifications page
    /notifications/unread-count/     → JSON unread count (for navbar poll)
    /notifications/mark-read/<pk>/   → mark single notification as read
    /notifications/mark-all-read/    → mark all as read
"""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from notifications.models import Notification


@login_required
def notifications_page(request):
    """Full notifications page."""
    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')[:50]

    unread_count = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()

    context = {
        'notifications': notifications,
        'unread_count':  unread_count,
    }
    return render(request, 'notifications/notifications.html', context)


@login_required
def unread_count_api(request):
    """JSON endpoint — returns unread notification count for navbar polling."""
    count = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()
    return JsonResponse({'count': count})


@login_required
def mark_read(request, pk):
    """Mark a single notification as read and redirect to its link."""
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = True
    notification.save(update_fields=['is_read'])

    if notification.link:
        return redirect(notification.link)
    return redirect('notifications_page')


@login_required
@require_POST
def mark_all_read(request):
    """Mark all notifications as read."""
    Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).update(is_read=True)
    return redirect('notifications_page')


@login_required
def recent_notifications_api(request):
    """
    JSON endpoint — returns 5 most recent notifications for navbar dropdown.
    """
    notifications = Notification.objects.filter(
        recipient=request.user,
    ).order_by('-created_at')[:5]

    data = []
    for n in notifications:
        data.append({
            'id':       n.pk,
            'type':     n.notification_type,
            'title':    n.title,
            'message':  n.message,
            'link':     f'/notifications/mark-read/{n.pk}/',
            'is_read':  n.is_read,
            'icon':     n.icon,
            'color':    n.color,
            'time':     n.created_at.strftime('%b %d, %I:%M %p'),
        })

    return JsonResponse({
        'notifications': data,
        'unread_count':  Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count(),
    })