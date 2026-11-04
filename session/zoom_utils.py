import requests
from django.conf import settings


def get_zoom_token():
    """
    Get Zoom OAuth access token using Server-to-Server OAuth.
    Returns access_token string or None on failure.
    """
    url    = 'https://zoom.us/oauth/token'
    params = {'grant_type': 'account_credentials', 'account_id': settings.ZOOM_ACCOUNT_ID}

    response = requests.post(
        url,
        params=params,
        auth=(settings.ZOOM_CLIENT_ID, settings.ZOOM_CLIENT_SECRET),
    )

    if response.status_code == 200:
        return response.json().get('access_token')
    return None


def create_zoom_meeting(session):
    """
    Create a Zoom meeting for a given session.

    Returns dict:
        {
            'meeting_id': str,
            'host_url':   str,   ← tutor opens this
            'join_url':   str,   ← learner opens this
        }
    Returns None on failure.
    """
    token = get_zoom_token()
    if not token:
        return None

    import pytz
    from datetime import datetime

    # Build ISO start time in IST timezone
    ist      = pytz.timezone('Asia/Kolkata')
    naive_dt = datetime.combine(session.date, session.start_time)
    aware_dt = ist.localize(naive_dt)
    start_time_iso = aware_dt.strftime('%Y-%m-%dT%H:%M:%S')

    url     = 'https://api.zoom.us/v2/users/me/meetings'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type':  'application/json',
    }
    payload = {
        'topic':      session.title,
        'type':       2,               # 2 = scheduled meeting
        'start_time': start_time_iso,
        'duration':   session.duration_minutes(),
        'timezone':   'Asia/Kolkata',
        'settings': {
            'host_video':        True,
            'participant_video': True,
            'join_before_host':  False,
            'waiting_room':      True,
            'auto_recording':    'none',
        },
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 201:
        data = response.json()
        return {
            'meeting_id': str(data['id']),
            'host_url':   data['start_url'],
            'join_url':   data['join_url'],
        }
    return None