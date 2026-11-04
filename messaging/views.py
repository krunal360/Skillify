from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone

from messaging.models import Conversation, Message
from session.models import Booking


def _can_message(user1, user2):
    """Check if user1 can message user2 — must have a booking together."""
    return Booking.objects.filter(
        Q(learner=user1, session__tutor=user2) |
        Q(learner=user2, session__tutor=user1),
        status__in=['confirmed', 'in_progress', 'pending_review', 'completed']
    ).exists()


def _get_or_create_conversation(user1, user2):
    """Get existing conversation or create new one."""
    # Always store with lower pk as participant_1
    if user1.pk < user2.pk:
        p1, p2 = user1, user2
    else:
        p1, p2 = user2, user1

    conversation, created = Conversation.objects.get_or_create(
        participant_1=p1,
        participant_2=p2,
    )
    return conversation


@login_required
def inbox_view(request):
    """Show all conversations for current user."""
    conversations = Conversation.objects.filter(
        Q(participant_1=request.user) | Q(participant_2=request.user)
    ).order_by('-updated_at')

    # Enrich with other participant and unread count
    enriched = []
    for conv in conversations:
        other      = conv.get_other_participant(request.user)
        unread     = conv.get_unread_count(request.user)
        last_msg   = conv.get_last_message()
        enriched.append({
            'conversation': conv,
            'other':        other,
            'unread':       unread,
            'last_message': last_msg,
        })

    context = {
        'conversations': enriched,
        'total_unread':  sum(c['unread'] for c in enriched),
    }
    return render(request, 'messaging/inbox.html', context)


@login_required
def conversation_view(request, conversation_id):
    """Open a specific conversation."""
    conversation = get_object_or_404(
        Conversation,
        pk=conversation_id,
    )

    # Security check
    if request.user not in [conversation.participant_1, conversation.participant_2]:
        messages.error(request, 'You do not have access to this conversation.')
        return redirect('inbox')

    # Mark all messages as read
    conversation.messages.filter(is_read=False).exclude(
        sender=request.user
    ).update(is_read=True)

    # Get all messages
    chat_messages = conversation.messages.select_related('sender').order_by('created_at')

    # Get all conversations for sidebar
    all_conversations = Conversation.objects.filter(
        Q(participant_1=request.user) | Q(participant_2=request.user)
    ).order_by('-updated_at')

    enriched_convs = []
    for conv in all_conversations:
        other    = conv.get_other_participant(request.user)
        unread   = conv.get_unread_count(request.user)
        last_msg = conv.get_last_message()
        enriched_convs.append({
            'conversation': conv,
            'other':        other,
            'unread':       unread,
            'last_message': last_msg,
        })

    other_participant = conversation.get_other_participant(request.user)

    context = {
        'conversation':     conversation,
        'chat_messages':    chat_messages,
        'other':            other_participant,
        'conversations':    enriched_convs,
        'last_message_id':  chat_messages.last().pk if chat_messages.exists() else 0,
    }
    return render(request, 'messaging/conversation.html', context)


@login_required
def start_conversation(request, user_id):
    """Start or open conversation with a user."""
    other_user = get_object_or_404(User, pk=user_id)

    if other_user == request.user:
        messages.error(request, 'You cannot message yourself.')
        return redirect('inbox')

    if not _can_message(request.user, other_user):
        messages.error(request, 'You can only message users you have a booking with.')
        return redirect('inbox')

    conversation = _get_or_create_conversation(request.user, other_user)
    return redirect('conversation', conversation_id=conversation.pk)


@login_required
def send_message(request):
    """Send a message."""
    if request.method != 'POST':
        return redirect('inbox')

    conversation_id = request.POST.get('conversation_id')
    content         = request.POST.get('content', '').strip()
    file            = request.FILES.get('file')

    # Validate
    if not content and not file:
        messages.error(request, 'Please type a message or attach a file.')
        return redirect('conversation', conversation_id=conversation_id)

    conversation = get_object_or_404(Conversation, pk=conversation_id)

    # Security check
    if request.user not in [conversation.participant_1, conversation.participant_2]:
        messages.error(request, 'You do not have access to this conversation.')
        return redirect('inbox')

    # Handle file
    file_type = 'none'
    file_name = ''
    if file:
        # Size check (5MB)
        if file.size > 5 * 1024 * 1024:
            messages.error(request, 'File too large. Maximum size is 5MB.')
            return redirect('conversation', conversation_id=conversation_id)

        # Type check
        allowed_images    = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        allowed_documents = ['application/pdf', 'application/msword',
                             'application/vnd.openxmlformats-officedocument.wordprocessingml.document']

        if file.content_type in allowed_images:
            file_type = 'image'
        elif file.content_type in allowed_documents:
            file_type = 'document'
        else:
            messages.error(request, 'File type not allowed. Please upload images or PDF/Word documents only.')
            return redirect('conversation', conversation_id=conversation_id)

        file_name = file.name

    # Create message
    Message.objects.create(
        conversation = conversation,
        sender       = request.user,
        content      = content,
        file         = file if file else None,
        file_type    = file_type,
        file_name    = file_name,
        is_read      = False,
    )

    # Update conversation timestamp
    conversation.save()

    return redirect('conversation', conversation_id=conversation_id)


@login_required
def mark_read(request, conversation_id):
    """Mark all messages in conversation as read."""
    conversation = get_object_or_404(Conversation, pk=conversation_id)

    if request.user not in [conversation.participant_1, conversation.participant_2]:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    conversation.messages.filter(
        is_read=False
    ).exclude(
        sender=request.user
    ).update(is_read=True)

    return JsonResponse({'status': 'ok'})


@login_required
def unread_count(request):
    """API endpoint for navbar unread count."""
    count = Message.objects.filter(
        conversation__in=Conversation.objects.filter(
            Q(participant_1=request.user) | Q(participant_2=request.user)
        ),
        is_read=False,
    ).exclude(sender=request.user).count()

    return JsonResponse({'count': count})


@login_required
def poll_messages(request, conversation_id):
    """Poll for new messages after a given message id."""
    conversation = get_object_or_404(Conversation, pk=conversation_id)

    if request.user not in [conversation.participant_1, conversation.participant_2]:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        last_id = int(request.GET.get('last_id', 0))
    except (TypeError, ValueError):
        last_id = 0

    new_messages = conversation.messages.filter(
        pk__gt=last_id
    ).select_related('sender', 'sender__profile').order_by('created_at')

    # Mark new messages as read
    new_messages.filter(is_read=False).exclude(
        sender=request.user
    ).update(is_read=True)

    data = []
    for msg in new_messages:
        if msg.sender != request.user:
            msg.is_read = True
        data.append({
            'id':         msg.pk,
            'sender_id':  msg.sender.pk,
            'sender':     msg.sender.get_full_name(),
            'avatar':     msg.sender.profile.avatar_url(),
            'content':    msg.content,
            'file_url':   msg.file.url if msg.file else None,
            'file_type':  msg.file_type,
            'file_name':  msg.file_name,
            'is_read':    msg.is_read,
            'created_at': timezone.localtime(msg.created_at).strftime('%I:%M %p'),
            'is_mine':    msg.sender == request.user,
        })

    return JsonResponse({'messages': data})