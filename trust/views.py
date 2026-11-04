"""
trust/views.py
--------------
API endpoint that returns a tutor's full trust score breakdown as JSON.
Used by the tutor profile page to render the score card.
"""

from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def trust_score_api(request, pk):
    """
    GET /trust/score/<pk>/
    Returns the full trust score breakdown for a tutor.
    No authentication required — scores are public.
    """
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

    # Get or trigger calculation
    try:
        ts = user.trust_score
    except Exception:
        # TrustScore doesn't exist yet — calculate it now
        from trust.calculator import recalculate_trust_score
        ts = recalculate_trust_score(user)

    data = {
        'tutor_id':    user.pk,
        'username':    user.username,

        # Final score
        'score':       ts.score,
        'score_int':   ts.score_int,
        'label':       ts.label,
        'label_display': ts.label_display_full,

        # Sub-scores
        'breakdown': {
            'session_performance': {
                'total':              ts.session_performance_score,
                'max':                30,
                'completion_rate':    ts.completion_rate_score,
                'sessions_taught':    ts.sessions_taught_score,
                'students_taught':    ts.students_taught_score,
                'cancellation_rate':  ts.cancellation_rate_score,
            },
            'review_metrics': {
                'total':           ts.review_metrics_score,
                'max':             28,
                'bayesian_rating': ts.bayesian_rating_score,
                'review_count':    ts.review_count_score,
                'recommend_pct':   ts.recommend_pct_score,
                'repeat_bookings': ts.repeat_booking_score,
            },
            'nlp_quality': {
                'total':              ts.nlp_score,
                'max':                25,
                'vader_avg':          ts.vader_avg_score,
                'vader_consistency':  ts.vader_consistency_score,
                'bio_skill_match':    ts.bio_skill_match_score,
                'bio_detail':         ts.bio_detail_score,
                'genuineness':        ts.profile_genuineness_score,
            },
            'profile_completion': {
                'total': ts.profile_completion_score,
                'max':   17,
            },
            'penalty': ts.duplicate_review_penalty,
        },

        # Raw stats
        'stats': {
            'total_sessions':     ts.total_sessions_taught,
            'total_students':     ts.total_students_taught,
            'completion_rate_pct': ts.completion_rate_pct,
            'cancellation_rate_pct': ts.cancellation_rate_pct,
            'avg_rating':         ts.avg_rating,
            'total_reviews':      ts.total_reviews,
            'recommend_pct':      ts.recommend_pct,
            'repeat_bookings':    ts.repeat_booking_count,
        },

        'calculated_at': ts.calculated_at.isoformat(),
    }

    return JsonResponse(data)