import time
import jwt
import requests
from datetime import datetime, timedelta
import random, string
from flask import current_app
from app import db

def generate_random_meeting_link():
    """Generate a random meeting link as a fallback."""
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return "https://meet.google.com/" + random_str

def refresh_zoom_token(recruiter):
    """
    Refresh the Zoom access token using the stored refresh token.
    Returns True if refresh is successful; False otherwise.
    """
    token_url = "https://zoom.us/oauth/token"
    params = {
        "grant_type": "refresh_token",
        "refresh_token": recruiter.zoom_refresh_token
    }
    auth = (
        current_app.config.get("ZOOM_CLIENT_ID"),
        current_app.config.get("ZOOM_CLIENT_SECRET")
    )
    response = requests.post(token_url, params=params, auth=auth)
    if response.status_code == 200:
        token_info = response.json()
        recruiter.zoom_access_token = token_info.get("access_token")
        recruiter.zoom_refresh_token = token_info.get("refresh_token")
        # Optionally, store token expiry if desired
        db.session.commit()
        return True
    else:
        current_app.logger.error("Zoom token refresh failed: %s", response.text)
        return False

def create_zoom_meeting(recruiter, slot):
    """
    Create a Zoom meeting using the recruiter's stored access token and slot information.
    Returns the join_url if meeting is created successfully; otherwise returns a fallback meeting link.
    """
    access_token = getattr(recruiter, "zoom_access_token", None)
    if not access_token:
        current_app.logger.error("Recruiter has not connected Zoom. Using fallback meeting link.")
        return generate_random_meeting_link()

    url = "https://api.zoom.us/v2/users/me/meetings"
    # Combine slot.date and slot.start_time into a datetime object (assuming stored in UTC)
    slot_start_dt = datetime.combine(slot.date, slot.start_time)
    meeting_details = {
        "topic": "Interview Meeting",
        "type": 2,  # Scheduled meeting
        "start_time": slot_start_dt.isoformat() + "Z",  # ISO 8601 format in UTC
        "duration": 30,  # Meeting duration in minutes; adjust as needed
        "timezone": "UTC",
        "agenda": "Interview scheduled via Scheduler App",
        "settings": {
            "host_video": True,
            "participant_video": True,
            "join_before_host": False,
            "mute_upon_entry": True
        }
    }
    headers = {
        "authorization": f"Bearer {access_token}",
        "content-type": "application/json"
    }
    response = requests.post(url, headers=headers, json=meeting_details)
    if response.status_code == 201:
        meeting_info = response.json()
        join_url = meeting_info.get("join_url")
        if join_url:
            return join_url
        else:
            current_app.logger.error("Zoom meeting created but join_url missing; using fallback.")
            return generate_random_meeting_link()
    elif response.status_code == 401:
        # Possibly token expired: try refreshing token and retry once.
        if refresh_zoom_token(recruiter):
            headers["authorization"] = f"Bearer {recruiter.zoom_access_token}"
            response = requests.post(url, headers=headers, json=meeting_details)
            if response.status_code == 201:
                meeting_info = response.json()
                join_url = meeting_info.get("join_url")
                if join_url:
                    return join_url
        current_app.logger.error("Zoom meeting creation failed after token refresh: %s", response.text)
        return generate_random_meeting_link()
    else:
        current_app.logger.error("Zoom meeting creation failed: %s", response.text)
        return generate_random_meeting_link()
