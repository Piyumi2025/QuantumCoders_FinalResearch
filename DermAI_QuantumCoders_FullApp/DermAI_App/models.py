"""SQLAlchemy 2.0 models — the SQL schema for DermAI."""
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    slmc_no = db.Column(db.String(40))
    specialization = db.Column(db.String(80), default="Dermatologist")
    role = db.Column(db.String(20), default="doctor")          # doctor | admin
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    verify_token = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    patients = db.relationship("Patient", backref="doctor", lazy=True)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "email": self.email,
            "slmc_no": self.slmc_no, "specialization": self.specialization,
            "role": self.role, "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at.strftime("%Y-%m-%d") if self.created_at else None,
        }


class Patient(db.Model):
    __tablename__ = "patients"
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    patient_code = db.Column(db.String(30))
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(20))
    nic = db.Column(db.String(40))
    contact = db.Column(db.String(40))
    address = db.Column(db.String(255))
    fitzpatrick = db.Column(db.String(10))
    lesion_location = db.Column(db.String(60))
    duration_weeks = db.Column(db.Integer)
    growth_speed = db.Column(db.String(20))
    sun_exposure = db.Column(db.String(40))
    immunosuppression = db.Column(db.String(60))
    family_history = db.Column(db.String(60))
    prev_history = db.Column(db.String(60))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assessments = db.relationship("Assessment", backref="patient", lazy=True)

    def to_dict(self):
        return {
            "id": self.id, "patient_code": self.patient_code,
            "first_name": self.first_name, "last_name": self.last_name,
            "age": self.age, "gender": self.gender, "fitzpatrick": self.fitzpatrick,
            "lesion_location": self.lesion_location,
        }


class ImageAsset(db.Model):
    __tablename__ = "images"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"))
    assessment_id = db.Column(db.Integer, db.ForeignKey("assessments.id"))
    filename = db.Column(db.String(255))
    stored_path = db.Column(db.String(300))
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    size_bytes = db.Column(db.Integer)
    blur_score = db.Column(db.Float)
    quality_pass = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Assessment(db.Model):
    __tablename__ = "assessments"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    symptom_json = db.Column(db.Text)                # stored symptom vector + flags
    predicted_type = db.Column(db.String(20))
    stage = db.Column(db.String(20))
    confidence = db.Column(db.Float)
    urgency = db.Column(db.String(20))
    uncertain = db.Column(db.Boolean, default=False)
    prob_mel = db.Column(db.Float)
    prob_bcc = db.Column(db.Float)
    prob_scc = db.Column(db.Float)
    prob_mcc = db.Column(db.Float)
    mode = db.Column(db.String(20))                  # trained | rule
    heatmap_path = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    images = db.relationship("ImageAsset", backref="assessment", lazy=True)

    def to_dict(self):
        return {
            "id": self.id, "patient_id": self.patient_id,
            "predicted_type": self.predicted_type, "stage": self.stage,
            "confidence": round(self.confidence or 0, 1), "urgency": self.urgency,
            "uncertain": self.uncertain, "mode": self.mode,
            "probs": {"Melanoma": self.prob_mel, "BCC": self.prob_bcc,
                      "SCC": self.prob_scc, "MCC": self.prob_mcc},
            "created_at": self.created_at.strftime("%d %b %Y") if self.created_at else None,
        }


class AuditLog(db.Model):
    __tablename__ = "audit_log"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(40))
    details = db.Column(db.String(255))
    ip = db.Column(db.String(60))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        u = User.query.get(self.user_id) if self.user_id else None
        return {
            "id": self.id, "user": u.name if u else "—", "action": self.action,
            "details": self.details, "ip": self.ip,
            "at": self.created_at.strftime("%d %b %H:%M") if self.created_at else "",
        }


def log(user_id, action, details, ip=""):
    db.session.add(AuditLog(user_id=user_id, action=action, details=details, ip=ip))
    db.session.commit()
