from app import db
from datetime import datetime, timedelta

class Recruiter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    reset_token = db.Column(db.String(120), nullable=True)
    otp = db.Column(db.String(6), nullable=True)
    otp_expiration = db.Column(db.DateTime, nullable=True)
    timezone = db.Column(db.String(50), nullable=True)
    zoom_access_token = db.Column(db.String(500), nullable=True)
    zoom_refresh_token = db.Column(db.String(500), nullable=True)

    availabilities = db.relationship('Availability', backref='recruiter', lazy=True)
    bookings = db.relationship('Booking', backref='recruiter', lazy=True)
    invitations = db.relationship('Invitation', backref='recruiter', lazy=True)


class Availability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recruiter_id = db.Column(db.Integer, db.ForeignKey('recruiter.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    booked = db.Column(db.Boolean, default=False)
    
    booking = db.relationship('Booking', backref='availability', uselist=False)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    candidate_name = db.Column(db.String(100), nullable=False)
    candidate_email = db.Column(db.String(100), nullable=False)
    candidate_position = db.Column(db.String(100), nullable=True)  # New field for candidate's position
    availability_id = db.Column(db.Integer, db.ForeignKey('availability.id'), nullable=False)
    recruiter_id = db.Column(db.Integer, db.ForeignKey('recruiter.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    meeting_link = db.Column(db.String(200), nullable=True)


class Invitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recruiter_id = db.Column(db.Integer, db.ForeignKey('recruiter.id'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    used = db.Column(db.Boolean, default=False)
    cancel_count = db.Column(db.Integer, default=0)
    expiration = db.Column(db.DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(hours=48))
