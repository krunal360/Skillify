"""
trust/nlp.py
------------
Pure NLP utility functions — no Django imports.
Used by trust/calculator.py to compute NLP-based sub-scores.

Functions:
    analyse_sentiment(reviews)      → VADER sentiment scores
    bio_skill_match(bio, skills)    → spaCy bio-skill consistency
    detect_duplicates(reviews)      → sklearn TF-IDF duplicate penalty
"""

import statistics
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


# ── Load spaCy model once at module level (not on every call) ──────────────────
try:
    import spacy
    nlp_model = spacy.load("en_core_web_sm")
    SPACY_AVAILABLE = True
except Exception:
    nlp_model = None
    SPACY_AVAILABLE = False


# ── Load sklearn TF-IDF once at module level ───────────────────────────────────
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False


# ── VADER analyser instance ────────────────────────────────────────────────────
analyser = SentimentIntensityAnalyzer()


# ==============================================================================
# 1. VADER Sentiment Analysis
# ==============================================================================

def analyse_sentiment(review_comments: list[str]) -> dict:
    """
    Analyse sentiment of review comments using VADER.

    Args:
        review_comments: list of review comment strings

    Returns:
        {
            'avg_compound':   float,   # average compound score (-1 to 1)
            'std_dev':        float,   # standard deviation (0 = very consistent)
            'avg_score':      float,   # mapped 0–6 pts
            'consistency_score': float # mapped 0–4 pts
        }
    """
    if not review_comments:
        return {
            'avg_compound': 0.0,
            'std_dev': 0.0,
            'avg_score': 0.0,
            'consistency_score': 0.0,
        }

    # Filter out empty/whitespace comments
    clean_comments = [c.strip() for c in review_comments if c and c.strip()]

    if not clean_comments:
        return {
            'avg_compound': 0.0,
            'std_dev': 0.0,
            'avg_score': 0.0,
            'consistency_score': 0.0,
        }

    # Get compound score for each comment (-1 to +1)
    compounds = []
    for comment in clean_comments:
        scores = analyser.polarity_scores(comment)
        compounds.append(scores['compound'])

    avg_compound = statistics.mean(compounds)

    # Standard deviation — lower = more consistent sentiment
    if len(compounds) > 1:
        std_dev = statistics.stdev(compounds)
    else:
        std_dev = 0.0

    # ── Map avg_compound to 0–6 pts ──────────────────────────────────────────
    # compound range: -1 to +1
    # We treat 0.0 as neutral (3 pts), +1 as perfect (6 pts), -1 as 0 pts
    avg_score = round(((avg_compound + 1) / 2) * 6, 2)
    avg_score = max(0.0, min(6.0, avg_score))

    # ── Map std_dev to 0–4 pts ───────────────────────────────────────────────
    # Low std_dev (< 0.1) = very consistent = 4 pts
    # High std_dev (> 0.6) = very inconsistent = 0 pts
    if std_dev <= 0.1:
        consistency_score = 4.0
    elif std_dev >= 0.6:
        consistency_score = 0.0
    else:
        # Linear interpolation between 0.1 and 0.6
        consistency_score = round(4.0 * (1 - (std_dev - 0.1) / 0.5), 2)
        consistency_score = max(0.0, min(4.0, consistency_score))

    return {
        'avg_compound': round(avg_compound, 4),
        'std_dev': round(std_dev, 4),
        'avg_score': avg_score,
        'consistency_score': consistency_score,
    }


# ==============================================================================
# 2. spaCy Bio-Skill Match
# ==============================================================================

def bio_skill_match(bio: str, skill_names: list[str]) -> dict:
    """
    Extract keywords from bio using spaCy and compare with listed skills.

    Args:
        bio:         tutor's bio text
        skill_names: list of skill name strings (e.g. ['Python', 'Django'])

    Returns:
        {
            'match_score':      float,  # 0–6 pts  (how well bio matches skills)
            'detail_score':     float,  # 0–4 pts  (how detailed the bio is)
            'matched_skills':   list,   # skills found in bio
            'bio_word_count':   int,
        }
    """
    # Fallback if spaCy not available
    if not SPACY_AVAILABLE or not nlp_model:
        detail_score = _bio_detail_fallback(bio)
        return {
            'match_score': 3.0,
            'detail_score': detail_score,
            'matched_skills': [],
            'bio_word_count': len(bio.split()) if bio else 0,
        }

    if not bio or not bio.strip():
        return {
            'match_score': 0.0,
            'detail_score': 0.0,
            'matched_skills': [],
            'bio_word_count': 0,
        }

    if not skill_names:
        # No skills listed — only score on bio detail
        detail_score = _bio_detail_score(bio)
        return {
            'match_score': 3.0,  # neutral — can't penalise for no skills
            'detail_score': detail_score,
            'matched_skills': [],
            'bio_word_count': len(bio.split()),
        }

    # Process bio with spaCy
    doc = nlp_model(bio.lower())

    # Extract tokens: nouns, proper nouns, and noun chunks
    bio_tokens = set()
    for token in doc:
        if not token.is_stop and not token.is_punct and len(token.text) > 2:
            bio_tokens.add(token.lemma_.lower())
    for chunk in doc.noun_chunks:
        bio_tokens.add(chunk.text.lower().strip())

    # Check which skills appear in bio
    matched_skills = []
    for skill in skill_names:
        skill_lower = skill.lower().strip()
        skill_words = set(skill_lower.split())
        # Direct match or all words of the skill appear in bio tokens
        if skill_lower in bio.lower() or skill_words.issubset(bio_tokens):
            matched_skills.append(skill)

    # ── Map match ratio to 0–6 pts ───────────────────────────────────────────
    if skill_names:
        match_ratio = len(matched_skills) / len(skill_names)
    else:
        match_ratio = 0.5

    match_score = round(match_ratio * 6, 2)
    match_score = max(0.0, min(6.0, match_score))

    # ── Bio detail score (0–4 pts) ───────────────────────────────────────────
    detail_score = _bio_detail_score(bio)

    return {
        'match_score': match_score,
        'detail_score': detail_score,
        'matched_skills': matched_skills,
        'bio_word_count': len(bio.split()),
    }


def _bio_detail_score(bio: str) -> float:
    """Score bio richness based on word count. Returns 0–4 pts."""
    if not bio:
        return 0.0
    word_count = len(bio.split())
    if word_count >= 80:
        return 4.0
    elif word_count >= 50:
        return 3.0
    elif word_count >= 30:
        return 2.0
    elif word_count >= 15:
        return 1.0
    else:
        return 0.5


def _bio_detail_fallback(bio: str) -> float:
    """Fallback when spaCy unavailable — score by word count only."""
    return _bio_detail_score(bio)


# ==============================================================================
# 3. Duplicate Review Detection (sklearn TF-IDF)
# ==============================================================================

def detect_duplicates(review_comments: list[str]) -> dict:
    """
    Detect suspiciously similar reviews using TF-IDF cosine similarity.

    Args:
        review_comments: list of review comment strings

    Returns:
        {
            'penalty':          float,  # 0 to -5 pts
            'duplicate_pairs':  int,    # number of near-duplicate pairs found
            'max_similarity':   float,  # highest similarity score found
        }
    """
    # Need at least 2 reviews to compare
    if not SKLEARN_AVAILABLE or len(review_comments) < 2:
        return {
            'penalty': 0.0,
            'duplicate_pairs': 0,
            'max_similarity': 0.0,
        }

    # Filter out empty comments
    clean = [c.strip() for c in review_comments if c and len(c.strip()) > 5]

    if len(clean) < 2:
        return {
            'penalty': 0.0,
            'duplicate_pairs': 0,
            'max_similarity': 0.0,
        }

    try:
        # Build TF-IDF matrix
        vectorizer = TfidfVectorizer(stop_words='english', min_df=1)
        tfidf_matrix = vectorizer.fit_transform(clean)

        # Compute pairwise cosine similarity
        sim_matrix = cosine_similarity(tfidf_matrix)

        # Count pairs with similarity > 0.85 (near-duplicates)
        duplicate_pairs = 0
        max_similarity = 0.0
        n = len(clean)

        for i in range(n):
            for j in range(i + 1, n):
                sim = sim_matrix[i][j]
                if sim > max_similarity:
                    max_similarity = sim
                if sim >= 0.85:
                    duplicate_pairs += 1

        # ── Map duplicate pairs to penalty 0 to -5 ──────────────────────────
        # 0 pairs  → 0 penalty
        # 1 pair   → -2 penalty
        # 2 pairs  → -3.5 penalty
        # 3+ pairs → -5 penalty (max)
        if duplicate_pairs == 0:
            penalty = 0.0
        elif duplicate_pairs == 1:
            penalty = -2.0
        elif duplicate_pairs == 2:
            penalty = -3.5
        else:
            penalty = -5.0

        return {
            'penalty': penalty,
            'duplicate_pairs': duplicate_pairs,
            'max_similarity': round(max_similarity, 4),
        }

    except Exception:
        return {
            'penalty': 0.0,
            'duplicate_pairs': 0,
            'max_similarity': 0.0,
        }