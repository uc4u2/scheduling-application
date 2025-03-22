from celery import shared_task
from app import mail, db
from flask_mail import Message
from app.models import Booking, Recruiter
from datetime import datetime, timedelta

@shared_task
def send_reminder_emails():
    """
    This task checks for bookings starting approximately 2 hours from now (±5 minutes)
    and sends reminder emails to both the candidate and the recruiter.
    """
    target_time = datetime.utcnow() + timedelta(hours=2)
    window_start = target_time - timedelta(minutes=5)
    window_end = target_time + timedelta(minutes=5)
    
    # Retrieve all bookings (in production, filter to only upcoming bookings)
    bookings = Booking.query.all()
    
    for booking in bookings:
        # Combine booking.date and booking.start_time (assuming they are stored in UTC)
        appointment_dt = datetime.combine(booking.date, booking.start_time)
        
        if window_start <= appointment_dt <= window_end:
            # Prepare candidate reminder email
            candidate_msg = Message(
                subject="Reminder: Your Upcoming Interview",
                recipients=[booking.candidate_email],
                body=(
                    f"Hello {booking.candidate_name},\n\n"
                    f"This is a reminder that your interview is scheduled on {booking.date} at {booking.start_time}.\n"
                    "Please ensure you're available to join the meeting on time.\n\n"
                    "Best regards,\nYour Recruitment Team"
                )
            )
            # Prepare recruiter reminder email
            recruiter = Recruiter.query.filter_by(id=booking.recruiter_id).first()
            recruiter_email = recruiter.email if recruiter else ""
            recruiter_msg = Message(
                subject="Reminder: Upcoming Interview",
                recipients=[recruiter_email] if recruiter_email else [],
                body=(
                    f"Hello {recruiter.name if recruiter else 'Recruiter'},\n\n"
                    f"This is a reminder that your interview with {booking.candidate_name} is scheduled on {booking.date} at {booking.start_time}.\n\n"
                    "Best regards,\nYour Scheduler App"
                )
            )
            try:
                mail.send(candidate_msg)
                if recruiter_email:
                    mail.send(recruiter_msg)
            except Exception as e:
                print(f"Error sending reminder for booking {booking.id}: {e}")
    
    db.session.commit()
