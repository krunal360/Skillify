"""
trust/calculator.py
-------------------
Main trust score calculation engine.
Queries the DB, computes every sub-score, calls nlp.py, saves TrustScore.

Public API:
    recalculate_trust_score(user) → TrustScore
"""

import math
from django.contrib.auth.models import User
from django.db.models import Avg, Count, Q

from trust.models import TrustScore
from trust.nlp import analyse_sentiment, bio_skill_match, detect_duplicates


# ==============================================================================
# Public entry point
# ==============================================================================

def recalculate_trust_score(user: User) -> TrustScore:
    """
    Recalculate and save the trust score for a tutor.
    Creates the TrustScore record if it doesn't exist yet.

    Args:
        user: the tutor User instance

    Returns:
        saved TrustScore instance
    """
    # Lazy imports to avoid circular imports at module load time
    from reviews.models import Review
    from session.models import Booking, Session
    from users.models import UserProfile
    from profiles.models import Certificate

    # ── Fetch raw data ─────────────────────────────────────────────────────────
    profile         = _get_profile(user)
    all_sessions    = Session.objects.filter(tutor=user)
    all_bookings    = Booking.objects.filter(session__tutor=user)
    completed_bookings = all_bookings.filter(status='completed')
    cancelled_bookings = all_bookings.filter(status='cancelled')
    all_reviews     = Review.objects.filter(tutor=user)
    certificates    = Certificate.objects.filter(tutor=user)

    # ── Compute each section ───────────────────────────────────────────────────
    session_data    = _session_performance(all_bookings, completed_bookings, cancelled_bookings)
    review_data     = _review_metrics(all_reviews, all_bookings, completed_bookings)
    nlp_data        = _nlp_scores(all_reviews, profile)
    genuineness     = _profile_genuineness(profile, certificates)
    completion      = _profile_completion(profile, certificates)
    duplicate_data  = _duplicate_penalty(all_reviews)

    # ── Sum up ─────────────────────────────────────────────────────────────────
    session_perf_score  = session_data['total']
    review_metrics_score = review_data['total']
    nlp_score           = (
        nlp_data['vader_avg_score']
        + nlp_data['vader_consistency_score']
        + nlp_data['bio_skill_match_score']
        + nlp_data['bio_detail_score']
        + genuineness['score']
    )
    profile_completion_score = completion['score']
    duplicate_penalty        = duplicate_data['penalty']

    raw_score = (
        session_perf_score
        + review_metrics_score
        + nlp_score
        + profile_completion_score
        + duplicate_penalty
    )

    final_score = round(max(0.0, min(100.0, raw_score)), 2)
    label       = TrustScore.get_label_for_score(final_score)

    # ── Save (upsert) ──────────────────────────────────────────────────────────
    ts, _ = TrustScore.objects.get_or_create(tutor=user)

    # Session performance sub-scores
    ts.session_performance_score = session_perf_score
    ts.completion_rate_score     = session_data['completion_rate_score']
    ts.sessions_taught_score     = session_data['sessions_taught_score']
    ts.students_taught_score     = session_data['students_taught_score']
    ts.cancellation_rate_score   = session_data['cancellation_rate_score']

    # Review metric sub-scores
    ts.review_metrics_score  = review_metrics_score
    ts.bayesian_rating_score = review_data['bayesian_rating_score']
    ts.review_count_score    = review_data['review_count_score']
    ts.recommend_pct_score   = review_data['recommend_pct_score']
    ts.repeat_booking_score  = review_data['repeat_booking_score']

    # NLP sub-scores
    ts.nlp_score                 = nlp_score
    ts.vader_avg_score           = nlp_data['vader_avg_score']
    ts.vader_consistency_score   = nlp_data['vader_consistency_score']
    ts.bio_skill_match_score     = nlp_data['bio_skill_match_score']
    ts.bio_detail_score          = nlp_data['bio_detail_score']
    ts.profile_genuineness_score = genuineness['score']

    # Profile completion
    ts.profile_completion_score = profile_completion_score

    # Penalty
    ts.duplicate_review_penalty = duplicate_penalty

    # Raw data snapshots
    ts.total_sessions_taught  = session_data['sessions_taught']
    ts.total_students_taught  = session_data['students_taught']
    ts.completion_rate_pct    = session_data['completion_rate_pct']
    ts.cancellation_rate_pct  = session_data['cancellation_rate_pct']
    ts.avg_rating             = review_data['avg_rating']
    ts.total_reviews          = review_data['review_count']
    ts.recommend_pct          = review_data['recommend_pct']
    ts.repeat_booking_count   = review_data['repeat_booking_count']
    ts.vader_avg_compound     = nlp_data['vader_avg_compound']
    ts.vader_std_dev          = nlp_data['vader_std_dev']

    # Final score
    ts.score = final_score
    ts.label = label

    ts.save()

    # Also update trust_score on UserProfile for easy access
    if profile:
        profile.trust_score = final_score
        profile.save(update_fields=['trust_score'])

    return ts


# ==============================================================================
# Section 1 — Session Performance (max 30 pts)
# ==============================================================================

def _session_performance(all_bookings, completed_bookings, cancelled_bookings) -> dict:
    """
    Compute session performance sub-scores.

    Completion rate    → 0–10 pts
    Sessions taught    → 0–8 pts
    Students taught    → 0–8 pts
    Cancellation rate  → 0–4 pts
    """
    total_bookings     = all_bookings.count()
    completed_count    = completed_bookings.count()
    cancelled_count    = cancelled_bookings.count()

    # Unique students (learners who completed at least one session)
    students_taught = (
        completed_bookings
        .values('learner')
        .distinct()
        .count()
    )

    # ── Completion rate (0–10 pts) ─────────────────────────────────────────────
    if total_bookings > 0:
        completion_rate_pct = (completed_count / total_bookings) * 100
    else:
        completion_rate_pct = 0.0

    if completion_rate_pct >= 90:
        completion_rate_score = 10.0
    elif completion_rate_pct >= 75:
        completion_rate_score = 7.5
    elif completion_rate_pct >= 60:
        completion_rate_score = 5.0
    elif completion_rate_pct >= 40:
        completion_rate_score = 3.0
    elif completion_rate_pct > 0:
        completion_rate_score = 1.0
    else:
        completion_rate_score = 0.0

    # ── Sessions taught (0–8 pts) ──────────────────────────────────────────────
    if completed_count >= 50:
        sessions_taught_score = 8.0
    elif completed_count >= 20:
        sessions_taught_score = 6.0
    elif completed_count >= 10:
        sessions_taught_score = 4.5
    elif completed_count >= 5:
        sessions_taught_score = 3.0
    elif completed_count >= 2:
        sessions_taught_score = 1.5
    elif completed_count == 1:
        sessions_taught_score = 0.5
    else:
        sessions_taught_score = 0.0

    # ── Students taught (0–8 pts) ──────────────────────────────────────────────
    if students_taught >= 30:
        students_taught_score = 8.0
    elif students_taught >= 15:
        students_taught_score = 6.0
    elif students_taught >= 8:
        students_taught_score = 4.0
    elif students_taught >= 4:
        students_taught_score = 2.5
    elif students_taught >= 1:
        students_taught_score = 1.0
    else:
        students_taught_score = 0.0

    # ── Cancellation rate (0–4 pts) ────────────────────────────────────────────
    # Lower cancellation = higher score
    if total_bookings > 0:
        cancellation_rate_pct = (cancelled_count / total_bookings) * 100
    else:
        cancellation_rate_pct = 0.0

    if cancellation_rate_pct == 0:
        cancellation_rate_score = 4.0
    elif cancellation_rate_pct <= 10:
        cancellation_rate_score = 3.0
    elif cancellation_rate_pct <= 25:
        cancellation_rate_score = 2.0
    elif cancellation_rate_pct <= 40:
        cancellation_rate_score = 1.0
    else:
        cancellation_rate_score = 0.0

    total = round(
        completion_rate_score
        + sessions_taught_score
        + students_taught_score
        + cancellation_rate_score,
        2
    )

    return {
        'total':                  total,
        'completion_rate_score':  completion_rate_score,
        'sessions_taught_score':  sessions_taught_score,
        'students_taught_score':  students_taught_score,
        'cancellation_rate_score': cancellation_rate_score,
        'completion_rate_pct':    round(completion_rate_pct, 2),
        'cancellation_rate_pct':  round(cancellation_rate_pct, 2),
        'sessions_taught':        completed_count,
        'students_taught':        students_taught,
    }


# ==============================================================================
# Section 2 — Review Metrics (max 28 pts)
# ==============================================================================

def _review_metrics(all_reviews, all_bookings, completed_bookings) -> dict:
    """
    Compute review metric sub-scores.

    Bayesian avg rating  → 0–12 pts
    Review count         → 0–7 pts
    Recommend %          → 0–6 pts
    Repeat bookings      → 0–3 pts
    """
    review_count = all_reviews.count()

    # ── Bayesian average rating (0–12 pts) ────────────────────────────────────
    # Bayesian avg = (C * m + sum_ratings) / (C + n)
    # C = confidence weight (5 reviews), m = prior mean (3.0)
    C = 5
    m = 3.0
    if review_count > 0:
        sum_ratings = sum(r.rating for r in all_reviews)
        bayesian_avg = (C * m + sum_ratings) / (C + review_count)
        avg_rating   = sum_ratings / review_count
    else:
        bayesian_avg = m
        avg_rating   = 0.0

    # Map 1–5 bayesian avg to 0–12 pts
    # 3.0 (prior) → 6 pts, 5.0 → 12 pts, 1.0 → 0 pts
    bayesian_rating_score = round(((bayesian_avg - 1) / 4) * 12, 2)
    bayesian_rating_score = max(0.0, min(12.0, bayesian_rating_score))

    # ── Review count (0–7 pts) ────────────────────────────────────────────────
    if review_count >= 30:
        review_count_score = 7.0
    elif review_count >= 15:
        review_count_score = 5.5
    elif review_count >= 8:
        review_count_score = 4.0
    elif review_count >= 4:
        review_count_score = 2.5
    elif review_count >= 2:
        review_count_score = 1.5
    elif review_count == 1:
        review_count_score = 0.5
    else:
        review_count_score = 0.0

    # ── Recommend % (0–6 pts) ─────────────────────────────────────────────────
    if review_count > 0:
        recommended_count = all_reviews.filter(recommended=True).count()
        recommend_pct     = (recommended_count / review_count) * 100
    else:
        recommended_count = 0
        recommend_pct     = 0.0

    recommend_pct_score = round((recommend_pct / 100) * 6, 2)
    recommend_pct_score = max(0.0, min(6.0, recommend_pct_score))

    # ── Repeat bookings (0–3 pts) ─────────────────────────────────────────────
    # Learners who booked more than once with this tutor
    learner_booking_counts = (
        completed_bookings
        .values('learner')
        .annotate(booking_count=Count('id'))
    )
    repeat_booking_count = sum(
        1 for lb in learner_booking_counts if lb['booking_count'] > 1
    )

    if repeat_booking_count >= 10:
        repeat_booking_score = 3.0
    elif repeat_booking_count >= 5:
        repeat_booking_score = 2.0
    elif repeat_booking_count >= 2:
        repeat_booking_score = 1.0
    elif repeat_booking_count == 1:
        repeat_booking_score = 0.5
    else:
        repeat_booking_score = 0.0

    total = round(
        bayesian_rating_score
        + review_count_score
        + recommend_pct_score
        + repeat_booking_score,
        2
    )

    return {
        'total':                 total,
        'bayesian_rating_score': bayesian_rating_score,
        'review_count_score':    review_count_score,
        'recommend_pct_score':   recommend_pct_score,
        'repeat_booking_score':  repeat_booking_score,
        'avg_rating':            round(avg_rating, 2),
        'review_count':          review_count,
        'recommend_pct':         round(recommend_pct, 2),
        'repeat_booking_count':  repeat_booking_count,
    }


# ==============================================================================
# Section 3 — NLP Scores (max 20 pts, genuineness handled separately)
# ==============================================================================

def _nlp_scores(all_reviews, profile) -> dict:
    """
    Compute VADER sentiment and spaCy bio-skill scores.

    VADER avg sentiment    → 0–6 pts
    VADER consistency      → 0–4 pts
    Bio-skill match        → 0–6 pts
    Bio detail             → 0–4 pts
    """
    # ── VADER sentiment ────────────────────────────────────────────────────────
    comments = list(all_reviews.values_list('comment', flat=True))
    sentiment_result = analyse_sentiment(comments)

    # ── spaCy bio-skill match ──────────────────────────────────────────────────
    bio = profile.bio if profile and profile.bio else ''
    if profile and profile.skills.exists():
        skill_names = list(profile.skills.values_list('name', flat=True))
    else:
        skill_names = []

    bio_result = bio_skill_match(bio, skill_names)

    return {
        'vader_avg_score':        sentiment_result['avg_score'],
        'vader_consistency_score': sentiment_result['consistency_score'],
        'vader_avg_compound':     sentiment_result['avg_compound'],
        'vader_std_dev':          sentiment_result['std_dev'],
        'bio_skill_match_score':  bio_result['match_score'],
        'bio_detail_score':       bio_result['detail_score'],
    }


# ==============================================================================
# Section 4 — Profile Genuineness (max 5 pts)
# ==============================================================================

def _profile_genuineness(profile, certificates) -> dict:
    """
    Certificate uploaded  → 3 pts
    Demo video present    → 2 pts
    """
    score = 0.0

    if certificates.exists():
        score += 3.0

    if profile and profile.demo_video and profile.demo_video.strip():
        score += 2.0

    return {'score': round(score, 2)}


# ==============================================================================
# Section 5 — Profile Completion (max 17 pts)
# ==============================================================================

def _profile_completion(profile, certificates) -> dict:
    """
    Profile picture   → 3 pts
    Bio filled        → 3 pts
    Expertise filled  → 2 pts
    Skill depth       → 4 pts  (1 skill=3, 2=3.5, 3+=4)
    Certificate       → 3 pts
    Demo video OR links → 2 pts
    """
    if not profile:
        return {'score': 0.0}

    score = 0.0

    # Profile picture (3 pts)
    if profile.profile_picture:
        score += 3.0

    # Bio filled (3 pts)
    if profile.bio and len(profile.bio.strip()) >= 20:
        score += 3.0

    # Expertise filled (2 pts)
    if profile.expertise and profile.expertise.strip():
        score += 2.0

    # Skill depth (0–4 pts)
    skill_count = profile.skills.count()
    if skill_count >= 3:
        score += 4.0
    elif skill_count == 2:
        score += 3.5
    elif skill_count == 1:
        score += 3.0
    else:
        score += 0.0

    # Certificate (3 pts)
    if certificates.exists():
        score += 3.0

    # Demo video OR social links (2 pts)
    has_demo    = bool(profile.demo_video and profile.demo_video.strip())
    has_linkedin = bool(profile.linkedin and profile.linkedin.strip())
    has_github  = bool(profile.github and profile.github.strip())

    if has_demo or has_linkedin or has_github:
        score += 2.0

    return {'score': round(min(score, 17.0), 2)}


# ==============================================================================
# Section 6 — Duplicate Review Penalty (max -5 pts)
# ==============================================================================

def _duplicate_penalty(all_reviews) -> dict:
    """Run TF-IDF duplicate detection on all review comments."""
    comments = list(all_reviews.values_list('comment', flat=True))
    result   = detect_duplicates(comments)
    return {'penalty': result['penalty']}


# ==============================================================================
# Helper
# ==============================================================================

def _get_profile(user):
    """Safely fetch UserProfile — returns None if not found."""
    try:
        from users.models import UserProfile
        return UserProfile.objects.get(user=user)
    except Exception:
        return None