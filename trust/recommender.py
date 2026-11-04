"""
trust/recommender.py
--------------------
Recommendation engine for Skillify.

Two public functions:
    get_similar_tutors(tutor_user, n)
        → Used on tutor profile page.
        → Finds tutors with similar skills + bio.

    get_recommended_tutors(learner_user, n)
        → Used on learner dashboard.
        → Finds tutors based on:
            1. Progression logic (completed beginner → recommend intermediate)
            2. Learner's learning interests
            3. Past booking skill history
"""

import logging
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)

# Level progression map
NEXT_LEVEL = {
    'beginner':     'intermediate',
    'intermediate': 'advanced',
    'advanced':     'advanced',
}

LEVEL_DISPLAY = {
    'beginner':     '🟢 Beginner',
    'intermediate': '🟡 Intermediate',
    'advanced':     '🔴 Advanced',
}


# ==============================================================================
# Helper — build tutor text profile
# ==============================================================================

def _build_tutor_profile_text(user) -> str:
    try:
        from users.models import UserProfile
        profile = UserProfile.objects.get(user=user)
    except Exception:
        return ''

    parts = []

    if profile.skills.exists():
        skill_names = list(profile.skills.values_list('name', flat=True))
        skill_text  = ' '.join(skill_names)
        parts.append(skill_text)
        parts.append(skill_text)
        parts.append(skill_text)

    if profile.expertise and profile.expertise.strip():
        parts.append(profile.expertise.strip())

    if profile.bio and profile.bio.strip():
        parts.append(profile.bio.strip())

    return ' '.join(parts).lower()


def _build_learner_interest_text(user) -> str:
    try:
        from users.models import UserProfile
        profile = UserProfile.objects.get(user=user)
    except Exception:
        return ''

    parts = []

    if profile.learning_interests.exists():
        interest_names = list(profile.learning_interests.values_list('name', flat=True))
        interest_text  = ' '.join(interest_names)
        parts.append(interest_text)
        parts.append(interest_text)

    try:
        from session.models import Booking
        past_skills = (
            Booking.objects
            .filter(learner=user, status='completed')
            .values_list('session__skill__name', flat=True)
            .distinct()
        )
        if past_skills:
            parts.append(' '.join(s for s in past_skills if s))
    except Exception:
        pass

    if profile.skills.exists():
        skill_names = list(profile.skills.values_list('name', flat=True))
        parts.append(' '.join(skill_names))

    return ' '.join(parts).lower()


# ==============================================================================
# Progression logic
# ==============================================================================

def _get_progression_targets(learner_user) -> list:
    """
    Analyse learner's completed sessions and determine what level
    they should learn next for each skill.

    Returns list of (skill_name, next_level) tuples.
    Example: [('Python', 'intermediate'), ('UI Design', 'advanced')]
    """
    try:
        from session.models import Booking
        completed_bookings = (
            Booking.objects
            .filter(learner=learner_user, status='completed')
            .select_related('session', 'session__skill')
            .order_by('session__skill__name', 'session__date')
        )
    except Exception:
        return []

    if not completed_bookings.exists():
        return []

    level_order = {'beginner': 1, 'intermediate': 2, 'advanced': 3}
    skill_max_level = {}

    for booking in completed_bookings:
        skill_name    = booking.session.skill.name
        level         = booking.session.level or 'beginner'
        current_order = level_order.get(level, 1)

        if skill_name not in skill_max_level:
            skill_max_level[skill_name] = level
        else:
            existing_order = level_order.get(skill_max_level[skill_name], 1)
            if current_order > existing_order:
                skill_max_level[skill_name] = level

    targets = []
    for skill_name, highest_level in skill_max_level.items():
        next_level = NEXT_LEVEL.get(highest_level, 'advanced')
        targets.append((skill_name, next_level))

    return targets


def _get_progression_tutors(learner_user, exclude_ids: set, n: int) -> list:
    """
    Find tutors who teach the next level of skills the learner
    has already started learning.
    """
    targets = _get_progression_targets(learner_user)

    if not targets:
        return []

    from session.models import Session

    progression_tutors = {}

    for skill_name, next_level in targets:
        matching_sessions = (
            Session.objects
            .filter(
                skill__name=skill_name,
                level=next_level,
                status='upcoming',
            )
            .exclude(tutor__id__in=exclude_ids)
            .select_related('tutor', 'skill')
        )

        for session in matching_sessions:
            tutor_pk = session.tutor.pk
            if tutor_pk not in progression_tutors:
                progression_tutors[tutor_pk] = {
                    'user':       session.tutor,
                    'skill':      skill_name,
                    'next_level': next_level,
                }

    return list(progression_tutors.values())[:n]


# ==============================================================================
# Core TF-IDF engine
# ==============================================================================

def _get_all_tutors_with_profiles():
    from users.models import UserProfile

    tutor_profiles = (
        UserProfile.objects
        .filter(role='tutor')
        .select_related('user')
        .prefetch_related('skills')
    )

    result = []
    for profile in tutor_profiles:
        text = _build_tutor_profile_text(profile.user)
        if text.strip():
            result.append((profile.user, text))

    return result


def _rank_by_similarity(query_text: str, tutor_texts: list, tutor_users: list, exclude_user=None) -> list:
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        logger.error("[Recommender] scikit-learn not available")
        return []

    if not tutor_texts:
        return []

    all_texts = [query_text] + tutor_texts

    try:
        vectorizer   = TfidfVectorizer(stop_words='english', min_df=1, ngram_range=(1, 2))
        tfidf_matrix = vectorizer.fit_transform(all_texts)
    except Exception as e:
        logger.error(f"[Recommender] TF-IDF error: {e}")
        return []

    query_vec    = tfidf_matrix[0]
    tutor_matrix = tfidf_matrix[1:]
    similarities = cosine_similarity(query_vec, tutor_matrix)[0]

    ranked = []
    for i, user in enumerate(tutor_users):
        if exclude_user and user.pk == exclude_user.pk:
            continue
        ranked.append((user, float(similarities[i])))

    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked


def _apply_trust_boost(ranked: list) -> list:
    boosted = []
    for user, sim_score in ranked:
        try:
            trust = user.trust_score.score / 100.0
        except Exception:
            trust = 0.0

        final = round((0.7 * sim_score) + (0.3 * trust), 6)
        boosted.append((user, sim_score, final))

    boosted.sort(key=lambda x: x[2], reverse=True)
    return boosted


# ==============================================================================
# Public API 1 — Similar Tutors (for tutor profile page)
# ==============================================================================

def get_similar_tutors(tutor_user: User, n: int = 4) -> list:
    all_tutors = _get_all_tutors_with_profiles()

    if len(all_tutors) < 2:
        return []

    tutor_users = [u for u, _ in all_tutors]
    tutor_texts = [t for _, t in all_tutors]
    query_text  = _build_tutor_profile_text(tutor_user)

    if not query_text.strip():
        return []

    ranked   = _rank_by_similarity(query_text, tutor_texts, tutor_users, exclude_user=tutor_user)
    boosted  = _apply_trust_boost(ranked)
    filtered = [(u, s, f) for u, s, f in boosted if s > 0.05]
    return _format_results(filtered[:n])


# ==============================================================================
# Public API 2 — Recommended Tutors (for learner dashboard)
# ==============================================================================

def get_recommended_tutors(learner_user: User, n: int = 6) -> list:
    """
    Find n tutors recommended for a learner based on:
    1. Progression logic — next level of skills already started
    2. TF-IDF interest matching — learning interests + booking history
    """
    already_booked_ids = _get_already_booked_tutor_ids(learner_user)
    exclude_ids        = already_booked_ids | {learner_user.pk}

    results  = []
    seen_pks = set()

    # ── Priority 1: Progression-based ─────────────────────────────────
    progression = _get_progression_tutors(learner_user, exclude_ids, n)

    for item in progression:
        user = item['user']
        if user.pk not in seen_pks:
            seen_pks.add(user.pk)
            results.append(_format_single(
                user=user,
                similarity=1.0,
                reason=f"Next step: {LEVEL_DISPLAY.get(item['next_level'])} {item['skill']}",
                is_progression=True,
            ))

    # ── Priority 2: Interest-based TF-IDF ─────────────────────────────
    if len(results) < n:
        remaining  = n - len(results)
        all_tutors = _get_all_tutors_with_profiles()
        all_tutors = [(u, t) for u, t in all_tutors
                      if u.pk not in seen_pks and u.pk not in exclude_ids]

        if all_tutors:
            tutor_users = [u for u, _ in all_tutors]
            tutor_texts = [t for _, t in all_tutors]
            query_text  = _build_learner_interest_text(learner_user)

            if query_text.strip():
                ranked   = _rank_by_similarity(query_text, tutor_texts, tutor_users)
                boosted  = _apply_trust_boost(ranked)
                filtered = [(u, s, f) for u, s, f in boosted if s > 0.05]

                for u, s, f in filtered[:remaining]:
                    if u.pk not in seen_pks:
                        seen_pks.add(u.pk)
                        results.append(_format_single(
                            user=u,
                            similarity=s,
                            reason='Matches your interests',
                            is_progression=False,
                        ))

    return results[:n]


# ==============================================================================
# Helpers
# ==============================================================================

def _get_already_booked_tutor_ids(learner_user) -> set:
    try:
        from session.models import Booking
        ids = (
            Booking.objects
            .filter(learner=learner_user, status='completed')
            .values_list('session__tutor__id', flat=True)
            .distinct()
        )
        return set(ids)
    except Exception:
        return set()


def _format_single(user, similarity: float, reason: str, is_progression: bool) -> dict:
    """Format a single tutor result dict."""
    try:
        ts    = user.trust_score
        score = ts.score
        label = ts.label_display_full
    except Exception:
        score = 0.0
        label = 'New Tutor 🆕'

    try:
        from users.models import UserProfile
        profile = UserProfile.objects.get(user=user)
        skills  = list(profile.skills.values_list('name', flat=True))
        pic     = profile.profile_picture.url if profile.profile_picture else None
    except Exception:
        skills = []
        pic    = None

    return {
        'user':           user,
        'similarity':     round(similarity, 4),
        'trust_score':    score,
        'label':          label,
        'skills':         skills,
        'profile_pic':    pic,
        'reason':         reason,
        'is_progression': is_progression,
    }


def _format_results(boosted: list) -> list:
    results = []
    for user, similarity, final_score in boosted:
        results.append(_format_single(
            user=user,
            similarity=similarity,
            reason='Matches your interests',
            is_progression=False,
        ))
    return results