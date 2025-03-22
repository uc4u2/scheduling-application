from datetime import datetime, timedelta
import random, string, uuid
from zoneinfo import ZoneInfo
import requests
from flask import Blueprint, request, jsonify, current_app, make_response, redirect
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from flask_mail import Message
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, mail
from app.models import Recruiter, Availability, Booking, Invitation
from googleapiclient.discovery import build
from google.oauth2 import service_account
from flask import make_response
from flask_cors import cross_origin

main = Blueprint('main', __name__)

def send_email(to, subject, body):
    msg = Message(subject=subject, recipients=[to], body=body)
    mail.send(msg)

def generate_meeting_link():
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return "https://meet.google.com/" + random_str

# New: Create a Jitsi Meet meeting link
def create_jitsi_meeting():
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"https://meet.jit.si/{random_str}"

# Optional: Google Calendar Integration (if desired)
def sync_to_google_calendar(email, availability_date, start_time, end_time):
    service_account_file = current_app.config.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not service_account_file:
        current_app.logger.error("Service account credentials file not provided")
        return
    try:
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=["https://www.googleapis.com/auth/calendar"]
        )
    except Exception as e:
        current_app.logger.error(f"Error loading service account credentials: {str(e)}")
        return
    try:
        service = build("calendar", "v3", credentials=credentials)
        event = {
            "summary": "Available Slot",
            "start": {
                "dateTime": f"{availability_date}T{start_time}:00",
                "timeZone": "America/New_York",
            },
            "end": {
                "dateTime": f"{availability_date}T{end_time}:00",
                "timeZone": "America/New_York",
            },
        }
        service.events().insert(
            calendarId=current_app.config.get("GOOGLE_CALENDAR_ID", "primary"),
            body=event
        ).execute()
    except Exception as e:
        current_app.logger.error(f"Error syncing to Google Calendar: {str(e)}")

# -----------------------
# Recruiter Endpoints
# -----------------------

@main.route("/register", methods=["POST"])
def register_recruiter():
    data = request.get_json()
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    timezone = data.get("timezone", "UTC")
    
    if not name or not email or not password:
        return jsonify({"error": "All fields are required"}), 400
    
    existing_user = Recruiter.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"error": "Email already registered"}), 409
    
    hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
    new_recruiter = Recruiter(
        name=name, 
        email=email, 
        password=hashed_password,
        timezone=timezone
    )
    db.session.add(new_recruiter)
    
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error("Error during registration: %s", str(e))
        db.session.rollback()
        return jsonify({"error": "Server error during registration."}), 500
    
    return jsonify({
        "message": "Recruiter registered successfully!",
        "recruiter_id": new_recruiter.id
    }), 201


@main.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    
    recruiter = Recruiter.query.filter_by(email=email).first()
    if not recruiter or not check_password_hash(recruiter.password, password):
        return jsonify({"error": "Invalid credentials"}), 401
    
    otp = ''.join(random.choices(string.digits, k=6))
    recruiter.otp = otp
    recruiter.otp_expiration = datetime.utcnow() + timedelta(minutes=5)
    db.session.commit()
    
    send_email(
        recruiter.email,
        "Your OTP for Login",
        f"Hello {recruiter.name},\n\nYour one-time password is: {otp}\nIt expires in 5 minutes."
    )
    
    return jsonify({"message": "OTP sent to your email. Please verify to complete login."}), 200

@main.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json()
    email = data.get("email")
    otp = data.get("otp")
    
    if not email or not otp:
        return jsonify({"error": "Email and OTP are required"}), 400
    
    recruiter = Recruiter.query.filter_by(email=email).first()
    if not recruiter:
        return jsonify({"error": "Recruiter not found"}), 404
    
    if recruiter.otp != otp or recruiter.otp_expiration < datetime.utcnow():
        return jsonify({"error": "Invalid or expired OTP"}), 401
    
    recruiter.otp = None
    recruiter.otp_expiration = None
    db.session.commit()
    
    token = create_access_token(identity=email)
    return jsonify({"access_token": token}), 200

@main.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json()
    email = data.get("email")
    
    if not email:
        return jsonify({"error": "Email is required"}), 400
    
    recruiter = Recruiter.query.filter_by(email=email).first()
    if not recruiter:
        return jsonify({"error": "Email not found"}), 404
    
    reset_token = str(uuid.uuid4())
    reset_link = f"{current_app.config.get('FRONTEND_URL')}/reset-password/{reset_token}"
    recruiter.reset_token = reset_token
    db.session.commit()
    
    send_email(
        recruiter.email,
        "Password Reset Request",
        f"Hello {recruiter.name},\n\nClick the link below to reset your password:\n{reset_link}"
    )
    
    return jsonify({"message": "Password reset email sent successfully!"}), 200

@main.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()
    token = data.get("token")
    new_password = data.get("new_password")
    
    if not token or not new_password:
        return jsonify({"error": "Token and new password are required"}), 400
    
    recruiter = Recruiter.query.filter_by(reset_token=token).first()
    if not recruiter:
        return jsonify({"error": "Invalid token"}), 400
    
    hashed_password = generate_password_hash(new_password, method="pbkdf2:sha256")
    recruiter.password = hashed_password
    recruiter.reset_token = None
    db.session.commit()
    
    return jsonify({"message": "Password reset successfully!"}), 200

# -----------------------
# Availability Endpoints (Recruiter Protected)
# -----------------------

@main.route("/set-availability", methods=["POST"])
@jwt_required()
def set_availability():
    data = request.get_json()
    email = get_jwt_identity()
    recruiter = Recruiter.query.filter_by(email=email).first()
    
    if not recruiter:
        return jsonify({"error": "Recruiter not found"}), 404

    date_str = data.get("date")           # Expected "YYYY-MM-DD"
    start_time_str = data.get("start_time") # Expected "HH:MM"
    end_time_str = data.get("end_time")     # Expected "HH:MM"
    
    if not date_str or not start_time_str or not end_time_str:
        return jsonify({"error": "All fields are required"}), 400
    
    try:
        local_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        local_start_time = datetime.strptime(start_time_str, "%H:%M").time()
        local_end_time = datetime.strptime(end_time_str, "%H:%M").time()
    except ValueError:
        return jsonify({"error": "Invalid date or time format"}), 400
    
    recruiter_timezone = recruiter.timezone if recruiter.timezone else "UTC"
    local_start_dt = datetime.combine(local_date, local_start_time).replace(tzinfo=ZoneInfo(recruiter_timezone))
    local_end_dt = datetime.combine(local_date, local_end_time).replace(tzinfo=ZoneInfo(recruiter_timezone))
    
    utc_start_dt = local_start_dt.astimezone(ZoneInfo("UTC"))
    utc_end_dt = local_end_dt.astimezone(ZoneInfo("UTC"))
    
    new_availability = Availability(
        recruiter_id=recruiter.id,
        date=utc_start_dt.date(),
        start_time=utc_start_dt.time(),
        end_time=utc_end_dt.time(),
        booked=False
    )
    db.session.add(new_availability)
    db.session.commit()
    
    sync_to_google_calendar(recruiter.email, local_date, start_time_str, end_time_str)
    return jsonify({"message": "Availability set successfully!"}), 201

@main.route("/set-recurring-availability", methods=["POST"])
@jwt_required()
def set_recurring_availability():
    data = request.get_json()
    email = get_jwt_identity()
    recruiter = Recruiter.query.filter_by(email=email).first()
    
    if not recruiter:
        return jsonify({"error": "Recruiter not found"}), 404
    
    start_date_str = data.get("start_date")  # Expected "YYYY-MM-DD"
    end_date_str = data.get("end_date")      # Expected "YYYY-MM-DD"
    start_time_str = data.get("start_time")  # Expected "HH:MM"
    end_time_str = data.get("end_time")      # Expected "HH:MM"
    
    if not start_date_str or not end_date_str or not start_time_str or not end_time_str:
        return jsonify({"error": "All fields (start_date, end_date, start_time, end_time) are required"}), 400
    
    try:
        local_start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        local_end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        local_start_time = datetime.strptime(start_time_str, "%H:%M").time()
        local_end_time = datetime.strptime(end_time_str, "%H:%M").time()
    except ValueError:
        return jsonify({"error": "Invalid date or time format. Use YYYY-MM-DD for dates and HH:MM for times."}), 400
    
    recruiter_timezone = recruiter.timezone if recruiter.timezone else "UTC"
    
    current_date = local_start_date
    while current_date <= local_end_date:
        local_start_dt = datetime.combine(current_date, local_start_time).replace(tzinfo=ZoneInfo(recruiter_timezone))
        local_end_dt = datetime.combine(current_date, local_end_time).replace(tzinfo=ZoneInfo(recruiter_timezone))
        
        utc_start_dt = local_start_dt.astimezone(ZoneInfo("UTC"))
        utc_end_dt = local_end_dt.astimezone(ZoneInfo("UTC"))
        
        new_availability = Availability(
            recruiter_id=recruiter.id,
            date=utc_start_dt.date(),
            start_time=utc_start_dt.time(),
            end_time=utc_end_dt.time(),
            booked=False
        )
        db.session.add(new_availability)
        current_date += timedelta(days=7)  # Weekly recurrence
    
    db.session.commit()
    return jsonify({"message": "Recurring availability set successfully!"}), 201

@main.route("/set-daily-availability", methods=["POST"])
@jwt_required()
def set_daily_availability():
    data = request.get_json()
    email = get_jwt_identity()
    recruiter = Recruiter.query.filter_by(email=email).first()
    
    if not recruiter:
        return jsonify({"error": "Recruiter not found"}), 404

    date_str = data.get("date")
    start_time_str = data.get("start_time")
    end_time_str = data.get("end_time")
    duration_str = data.get("duration")
    
    if not date_str or not start_time_str or not end_time_str or not duration_str:
        return jsonify({"error": "All fields (date, start_time, end_time, duration) are required"}), 400
    
    try:
        availability_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        local_start_time = datetime.strptime(start_time_str, "%H:%M").time()
        local_end_time = datetime.strptime(end_time_str, "%H:%M").time()
        duration = int(duration_str)
    except Exception:
        return jsonify({"error": "Invalid date, time, or duration format"}), 400

    recruiter_timezone = recruiter.timezone if recruiter.timezone else "UTC"
    # Construct the starting and ending datetime objects in local time
    local_start_dt = datetime.combine(availability_date, local_start_time)
    local_end_dt = datetime.combine(availability_date, local_end_time)
    
    slots_created = []
    current_start = local_start_dt

    # Fetch existing slots for this recruiter on the given date
    existing_slots = Availability.query.filter_by(
        recruiter_id=recruiter.id,
        date=availability_date
    ).all()

    # Helper function to check if two time intervals overlap
    def overlaps(new_start, new_end, existing_start, existing_end):
        return new_start < existing_end and new_end > existing_start

    while current_start + timedelta(minutes=duration) <= local_end_dt:
        current_end = current_start + timedelta(minutes=duration)
        
        # Check for overlap with existing slots
        overlap_found = False
        for slot in existing_slots:
            # Combine the existing slot's date and times into datetime objects (assuming they represent local time)
            existing_start = datetime.combine(availability_date, slot.start_time)
            existing_end = datetime.combine(availability_date, slot.end_time)
            if overlaps(current_start, current_end, existing_start, existing_end):
                overlap_found = True
                break
        
        # If no overlap is found, create the new slot.
        if not overlap_found:
            local_start_dt_tz = current_start.replace(tzinfo=ZoneInfo(recruiter_timezone))
            local_end_dt_tz = current_end.replace(tzinfo=ZoneInfo(recruiter_timezone))
            utc_start = local_start_dt_tz.astimezone(ZoneInfo("UTC"))
            utc_end = local_end_dt_tz.astimezone(ZoneInfo("UTC"))
            
            new_slot = Availability(
                recruiter_id=recruiter.id,
                date=utc_start.date(),
                start_time=utc_start.time(),
                end_time=utc_end.time(),
                booked=False
            )
            db.session.add(new_slot)
            slots_created.append(new_slot)
            # Add the new slot to the list of existing slots so subsequent iterations avoid overlaps.
            existing_slots.append(new_slot)
        
        current_start = current_end

    db.session.commit()
    return jsonify({"message": f"Daily availability set successfully! {len(slots_created)} slots created."}), 201


@main.route("/my-availability", methods=["GET"])
@jwt_required()
def my_availability():
    email = get_jwt_identity()
    recruiter = Recruiter.query.filter_by(email=email).first()
    
    if not recruiter:
        return jsonify({"error": "Recruiter not found"}), 404
    
    recruiter_timezone = recruiter.timezone if recruiter.timezone else "UTC"
    availabilities = Availability.query.filter_by(recruiter_id=recruiter.id).all()
    slots = []
    for slot in availabilities:
        utc_start_dt = datetime.combine(slot.date, slot.start_time).replace(tzinfo=ZoneInfo("UTC"))
        utc_end_dt = datetime.combine(slot.date, slot.end_time).replace(tzinfo=ZoneInfo("UTC"))
        local_start_dt = utc_start_dt.astimezone(ZoneInfo(recruiter_timezone))
        local_end_dt = utc_end_dt.astimezone(ZoneInfo(recruiter_timezone))
        
        slot_data = {
            "id": slot.id,
            "date": local_start_dt.strftime("%Y-%m-%d"),
            "start_time": local_start_dt.strftime("%H:%M"),
            "end_time": local_end_dt.strftime("%H:%M"),
            "booked": slot.booked
        }
        if slot.booked:
            booking = Booking.query.filter_by(availability_id=slot.id).first()
            if booking:
                slot_data["candidate_name"] = booking.candidate_name
                slot_data["candidate_email"] = booking.candidate_email
                slot_data["candidate_position"] = booking.candidate_position
                slot_data["booking_id"] = booking.id
        slots.append(slot_data)
    
    return jsonify({"available_slots": slots}), 200

@main.route("/update-availability/<int:slot_id>", methods=["PUT"])
@jwt_required()
def update_availability(slot_id):
    data = request.get_json()
    email = get_jwt_identity()
    recruiter = Recruiter.query.filter_by(email=email).first()
    if not recruiter:
        return jsonify({"error": "Recruiter not found"}), 404

    slot = Availability.query.filter_by(id=slot_id, recruiter_id=recruiter.id).first()
    if not slot:
        return jsonify({"error": "Availability slot not found"}), 404

    date_str = data.get("date")
    start_time_str = data.get("start_time")
    end_time_str = data.get("end_time")
    if not date_str or not start_time_str or not end_time_str:
        return jsonify({"error": "All fields (date, start_time, end_time) are required"}), 400

    try:
        local_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        local_start_time = datetime.strptime(start_time_str, "%H:%M").time()
        local_end_time = datetime.strptime(end_time_str, "%H:%M").time()
    except ValueError:
        return jsonify({"error": "Invalid date or time format"}), 400

    recruiter_timezone = recruiter.timezone if recruiter.timezone else "UTC"
    local_start_dt = datetime.combine(local_date, local_start_time).replace(tzinfo=ZoneInfo(recruiter_timezone))
    local_end_dt = datetime.combine(local_date, local_end_time).replace(tzinfo=ZoneInfo(recruiter_timezone))
    utc_start_dt = local_start_dt.astimezone(ZoneInfo("UTC"))
    utc_end_dt = local_end_dt.astimezone(ZoneInfo("UTC"))

    slot.date = utc_start_dt.date()
    slot.start_time = utc_start_dt.time()
    slot.end_time = utc_end_dt.time()
    db.session.commit()

    # If the slot is booked, send an update email to the candidate.
    if slot.booked:
        from app.models import Booking  # Ensure Booking is imported if not already
        booking = Booking.query.filter_by(availability_id=slot.id).first()
        if booking:
            # Construct a message with the updated meeting time.
            email_body = (
                f"Hello {booking.candidate_name},\n\n"
                f"Your interview meeting time has been updated. The new schedule is:\n\n"
                f"Date: {slot.date}\n"
                f"Start Time: {slot.start_time}\n"
                f"End Time: {slot.end_time}\n\n"
                "Please update your calendar accordingly.\n\n"
                "Best regards,\nYour Recruitment Team"
            )
            try:
                send_email(booking.candidate_email, "Meeting Time Updated", email_body)
            except Exception as e:
                current_app.logger.error("Error sending update email to candidate: %s", str(e))
                # Optionally, you could return a warning in your response if needed.

    return jsonify({"message": "Availability slot updated successfully! Candidate notified if slot was booked."}), 200


@main.route("/delete-availability/<int:slot_id>", methods=["DELETE"])
@jwt_required()
def delete_availability(slot_id):
    email = get_jwt_identity()
    recruiter = Recruiter.query.filter_by(email=email).first()
    if not recruiter:
        return jsonify({"error": "Recruiter not found"}), 404

    slot = Availability.query.filter_by(id=slot_id, recruiter_id=recruiter.id).first()
    if not slot:
        return jsonify({"error": "Availability slot not found"}), 404

    if slot.booked:
        return jsonify({"error": "Cannot delete a booked slot"}), 400

    db.session.delete(slot)
    db.session.commit()
    return jsonify({"message": "Availability slot deleted successfully!"}), 200

# Cancel Booking Endpoint – only for booked slots
@main.route("/cancel-booking/<int:booking_id>", methods=["DELETE"])
@jwt_required()
def cancel_booking(booking_id):
    email = get_jwt_identity()
    recruiter = Recruiter.query.filter_by(email=email).first()
    if not recruiter:
        return jsonify({"error": "Recruiter not found"}), 404

    booking = Booking.query.filter_by(id=booking_id, recruiter_id=recruiter.id).first()
    if not booking:
        return jsonify({"error": "Booking not found"}), 404

    slot = Availability.query.filter_by(id=booking.availability_id, recruiter_id=recruiter.id).first()
    if not slot:
        return jsonify({"error": "Associated availability slot not found"}), 404

    try:
        db.session.delete(booking)
        slot.booked = False
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to cancel booking"}), 500

    try:
        send_email(
            booking.candidate_email,
            "Your Interview Booking Has Been Cancelled",
            f"Hello {booking.candidate_name},\n\nYour interview booking scheduled for {slot.date} at {slot.start_time} has been cancelled.\nPlease contact the recruiter for further details."
        )
    except Exception as e:
        current_app.logger.error("Error sending cancellation email: %s", str(e))
    
    return jsonify({"message": "Booking cancelled successfully!"}), 200

@main.route("/analytics", methods=["GET"])
@jwt_required()
def analytics():
    email = get_jwt_identity()
    recruiter = Recruiter.query.filter_by(email=email).first()
    if not recruiter:
        return jsonify({"error": "Recruiter not found"}), 404

    total_bookings = Booking.query.filter_by(recruiter_id=recruiter.id).count()
    upcoming_bookings = Booking.query.filter(
        Booking.recruiter_id == recruiter.id,
        Booking.date >= datetime.utcnow().date()
    ).count()

    return jsonify({
        "total_bookings": total_bookings,
        "upcoming_bookings": upcoming_bookings,
    }), 200

# -----------------------
# Public Endpoints (For Candidates)
# -----------------------

@main.route("/public/availability/<int:recruiter_id>", methods=["GET"])
def view_public_availability(recruiter_id):
    availabilities = Availability.query.filter_by(recruiter_id=recruiter_id, booked=False).all()
    slots = [{
        "id": slot.id,
        "date": slot.date.strftime("%Y-%m-%d"),
        "start_time": slot.start_time.strftime("%H:%M"),
        "end_time": slot.end_time.strftime("%H:%M")
    } for slot in availabilities]
    return jsonify({"available_slots": slots}), 200

@main.route("/public/book-slot", methods=["POST"])
def public_book_slot():
    data = request.get_json()
    candidate_name = data.get("candidate_name")
    candidate_email = data.get("candidate_email")
    candidate_position = data.get("candidate_position")  # New field
    availability_id = data.get("availability_id")
    invitation_token = data.get("invitation_token")  # New field

    if not candidate_name or not candidate_email or not availability_id or not invitation_token:
        return jsonify({"error": "Candidate name, email, availability ID, and invitation token are required"}), 400

    # Validate invitation token
    invitation = Invitation.query.filter_by(token=invitation_token).first()
    if not invitation:
        return jsonify({"error": "Invalid invitation token."}), 400
    if invitation.used:
        return jsonify({"error": "This invitation link has already been used."}), 400
    if invitation.expiration < datetime.utcnow():
        return jsonify({"error": "This invitation link has expired."}), 400

    # Check if the slot is available
    slot = Availability.query.filter_by(id=availability_id, booked=False).first()
    if not slot:
        return jsonify({"error": "Slot not available"}), 404

    slot.booked = True
    recruiter = Recruiter.query.filter_by(id=slot.recruiter_id).first()
    # Generate a meeting link using Jitsi Meet
    meeting_link = create_jitsi_meeting()
    
    new_booking = Booking(
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        candidate_position=candidate_position,  # Save the candidate's position
        availability_id=slot.id,
        recruiter_id=slot.recruiter_id,
        date=slot.date,
        start_time=slot.start_time,
        end_time=slot.end_time,
        meeting_link=meeting_link
    )
    db.session.add(new_booking)
    # Mark the invitation as used so it cannot be reused
    invitation.used = True
    db.session.commit()
    
    # Build a cancellation link.
    cancellation_link = f"{current_app.config.get('FRONTEND_URL')}/cancel-booking?email={candidate_email}&token={invitation_token}"

    # Send confirmation email to candidate with meeting and cancellation links.
    send_email(
        candidate_email,
        "Your Interview Slot is Confirmed",
        f"Hello {candidate_name},\n\nYour interview is scheduled for {slot.date} at {slot.start_time}.\n"
        f"Position: {candidate_position}\n"
        f"Please join the meeting using this link: {meeting_link}\n\n"
        f"If you need to cancel your booking, please use the following link:\n{cancellation_link}\n\n"
        "Good luck!"
    )
    
    # Send email to recruiter
    send_email(
        recruiter.email,
        "New Booking Received",
        f"Hello {recruiter.name},\n\nA new booking has been made for the slot on {slot.date} from {slot.start_time} to {slot.end_time}.\n"
        f"Candidate: {candidate_name} ({candidate_email})\n"
        f"Position: {candidate_position}\n"
        f"Meeting Link: {meeting_link}"
    )
    
    return jsonify({"message": "Slot booked successfully!"}), 201





# -----------------------
# Send Invitation Endpoint (For Recruiters)
# -----------------------
@main.route("/send-invitation", methods=["POST"])
@jwt_required()
def send_invitation():
    data = request.get_json()
    candidate_name = data.get("candidate_name")
    candidate_email = data.get("candidate_email")
    
    if not candidate_name or not candidate_email:
        return jsonify({"error": "Candidate name and email are required"}), 400

    recruiter_email = get_jwt_identity()
    recruiter = Recruiter.query.filter_by(email=recruiter_email).first()
    if not recruiter:
        return jsonify({"error": "Recruiter not found"}), 404

    # Generate a random invitation token and store it in the Invitation model
    invitation_token = uuid.uuid4().hex
    expiration_time = datetime.utcnow() + timedelta(hours=48)
    invitation = Invitation(
        recruiter_id=recruiter.id,
        token=invitation_token,
        used=False,
        expiration=expiration_time
    )
    db.session.add(invitation)
    db.session.commit()

    booking_link = f"{current_app.config.get('FRONTEND_URL')}/book-slot/{recruiter.id}/{invitation_token}"
    expiration_str = expiration_time.strftime("%Y-%m-%d %H:%M UTC")
    
    message_body = (
        f"Hello {candidate_name},\n\n"
        "You have been invited to book an interview slot. Please use the following link to schedule your interview:\n\n"
        f"{booking_link}\n\n"
        "For your reference, your invitation token is: " + invitation_token + "\n"
        f"This token (and the link) will expire on {expiration_str}.\n\n"
        "Best regards,\nYour Recruitment Team"
    )
    
    try:
        send_email(candidate_email, "Interview Invitation", message_body)
        return jsonify({"message": "Invitation sent successfully!"}), 200
    except Exception as e:
        current_app.logger.error("Error sending invitation: %s", str(e))
        return jsonify({"error": "Failed to send invitation"}), 500
#############
@main.route("/profile", methods=["GET", "OPTIONS"])
@cross_origin()  # This decorator ensures the response includes CORS headers
@jwt_required(optional=True)
def profile():
    if request.method == "OPTIONS":
        response = make_response("")
        response.headers["Access-Control-Allow-Origin"] = current_app.config.get("FRONTEND_URL", "*")
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response, 200

    email = get_jwt_identity()
    recruiter = Recruiter.query.filter_by(email=email).first()
    if recruiter:
        return jsonify({
            "id": recruiter.id,
            "name": recruiter.name,
            "email": recruiter.email,
            "timezone": recruiter.timezone,
            "zoom_connected": False
        }), 200
    else:
        return jsonify({"error": "Recruiter not found"}), 404
#########
@main.route("/public/cancel-booking", methods=["POST"])
def public_cancel_booking():
    data = request.get_json()
    candidate_name = data.get("candidate_name")
    candidate_email = data.get("candidate_email")
    invitation_token = data.get("invitation_token")
    
    if not candidate_name or not candidate_email or not invitation_token:
        return jsonify({"error": "Candidate name, email, and invitation token are required"}), 400

    # Validate invitation token
    invitation = Invitation.query.filter_by(token=invitation_token).first()
    if not invitation:
        return jsonify({"error": "Invalid invitation token."}), 400
    if invitation.expiration < datetime.utcnow():
        return jsonify({"error": "This invitation link has expired."}), 400
    if invitation.cancel_count >= 2:
        return jsonify({"error": "Cancellation limit reached. You cannot cancel more than 2 times."}), 400

    # Find the booking using candidate email. 
    # (Assuming candidate_email uniquely identifies the booking for this invitation.)
    booking = Booking.query.filter_by(candidate_email=candidate_email).first()
    if not booking:
        return jsonify({"error": "Booking not found."}), 404

    # Get the associated slot.
    slot = Availability.query.filter_by(id=booking.availability_id).first()
    if slot:
        slot.booked = False  # Mark slot as available

    # Remove the booking record.
    db.session.delete(booking)
    
    # Update the invitation: increment cancellation count and mark as unused.
    invitation.cancel_count += 1
    invitation.used = False
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Cancellation commit error: %s", str(e))
        return jsonify({"error": "Failed to cancel booking due to a server error."}), 500

    # Send email to the candidate confirming cancellation.
    try:
        send_email(
            candidate_email,
            "Booking Cancelled",
            f"Hello {candidate_name},\n\nYour booking has been cancelled. You may rebook using your invitation token if needed (cancellations allowed: 2 times).\n\nBest regards,\nYour Recruitment Team"
        )
    except Exception as e:
        current_app.logger.error("Error sending cancellation email to candidate: %s", str(e))
    
    # Also, send email to the recruiter notifying them about the cancellation.
    try:
        recruiter = Recruiter.query.filter_by(id=slot.recruiter_id).first()
        if recruiter:
            send_email(
                recruiter.email,
                "Booking Cancelled",
                f"Hello {recruiter.name},\n\nThe booking for the slot on {slot.date} from {slot.start_time} to {slot.end_time} "
                f"has been cancelled by {candidate_name} ({candidate_email}).\n\nBest regards,\nYour Scheduler App"
            )
    except Exception as e:
        current_app.logger.error("Error sending cancellation email to recruiter: %s", str(e))
    
    return jsonify({"message": "Booking cancelled successfully. Both candidate and recruiter have been notified."}), 200
