from django.db.models import Q
from messaging.models import Conversation


def messaging_context(request):
    """Add messaging data to template context."""
    if request.user.is_authenticated:
        try:
            # Get total unread messages count for current user
            total_unread = 0
            conversations = Conversation.objects.filter(
                Q(participant_1=request.user) | Q(participant_2=request.user)
            )
            
            for conversation in conversations:
                total_unread += conversation.get_unread_count(request.user)
            
            return {'total_unread_messages': total_unread}
        except Exception:
            return {'total_unread_messages': 0}
    
    return {'total_unread_messages': 0}
