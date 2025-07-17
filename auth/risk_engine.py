import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from ..models import User, SecurityEvent, RiskAssessment
from ..schemas import RiskContext

class RiskEngine:
    def __init__(self):
        self.risk_thresholds = {
            "low": 0.3,
            "medium": 0.6,
            "high": 0.8
        }
    
    def assess_login_risk(self, user: User, context: RiskContext, db: Session) -> float:
        """Assess risk for login attempts"""
        risk_factors = {}
        
        # Check for unusual location
        risk_factors["location"] = self._assess_location_risk(user, context.location, db)
        
        # Check device fingerprint
        risk_factors["device"] = self._assess_device_risk(user, context.device_fingerprint)
        
        # Check login velocity
        risk_factors["velocity"] = self._assess_velocity_risk(user, db)
        
        # Check time-based patterns
        risk_factors["timing"] = self._assess_timing_risk(user, db)
        
        # Calculate overall risk
        overall_risk = sum(risk_factors.values()) / len(risk_factors)
        
        # Store risk assessment
        self._store_risk_assessment(user.id, "login", risk_factors, overall_risk, db)
        
        return overall_risk
    
    def assess_transaction_risk(self, user: User, transaction_data: Dict[str, Any], db: Session) -> float:
        """Assess risk for financial transactions"""
        risk_factors = {}
        
        # Amount-based risk
        risk_factors["amount"] = self._assess_amount_risk(user, transaction_data["amount"], db)
        
        # Frequency-based risk
        risk_factors["frequency"] = self._assess_frequency_risk(user, db)
        
        # Behavioral risk
        risk_factors["behavioral"] = self._assess_behavioral_risk(user, transaction_data)
        
        overall_risk = sum(risk_factors.values()) / len(risk_factors)
        
        self._store_risk_assessment(user.id, "transaction", risk_factors, overall_risk, db)
        
        return overall_risk
    
    def _assess_location_risk(self, user: User, current_location: Optional[str], db: Session) -> float:
        if not current_location:
            return 0.2
        
        # Get recent login locations
        recent_events = db.query(SecurityEvent).filter(
            SecurityEvent.user_id == user.id,
            SecurityEvent.event_type == "login",
            SecurityEvent.created_at > datetime.utcnow() - timedelta(days=30)
        ).all()
        
        known_locations = [event.location for event in recent_events if event.location]
        
        if not known_locations:
            return 0.3  # New user, moderate risk
        
        if current_location in known_locations:
            return 0.1  # Known location, low risk
        else:
            return 0.7  # New location, high risk
    
    def _assess_device_risk(self, user: User, device_fingerprint: str) -> float:
        if not user.device_fingerprints:
            return 0.3
        
        known_devices = user.device_fingerprints.get("devices", [])
        
        if device_fingerprint in known_devices:
            return 0.1
        else:
            return 0.6
    
    def _assess_velocity_risk(self, user: User, db: Session) -> float:
        # Check login attempts in last hour
        recent_attempts = db.query(SecurityEvent).filter(
            SecurityEvent.user_id == user.id,
            SecurityEvent.event_type.in_(["login", "failed_login"]),
            SecurityEvent.created_at > datetime.utcnow() - timedelta(hours=1)
        ).count()
        
        if recent_attempts > 5:
            return 0.8
        elif recent_attempts > 2:
            return 0.4
        else:
            return 0.1
    
    def _assess_timing_risk(self, user: User, db: Session) -> float:
        current_hour = datetime.utcnow().hour
        
        # Get user's typical login hours
        recent_logins = db.query(SecurityEvent).filter(
            SecurityEvent.user_id == user.id,
            SecurityEvent.event_type == "login",
            SecurityEvent.created_at > datetime.utcnow() - timedelta(days=30)
        ).all()
        
        if not recent_logins:
            return 0.2
        
        typical_hours = [login.created_at.hour for login in recent_logins]
        hour_frequency = {}
        for hour in typical_hours:
            hour_frequency[hour] = hour_frequency.get(hour, 0) + 1
        
        # If current hour is unusual, increase risk
        if current_hour not in hour_frequency:
            return 0.5
        elif hour_frequency[current_hour] < len(recent_logins) * 0.1:
            return 0.3
        else:
            return 0.1
    
    def _assess_amount_risk(self, user: User, amount: float, db: Session) -> float:
        # Get user's transaction history
        from ..models import Payment
        recent_payments = db.query(Payment).filter(
            Payment.user_id == user.id,
            Payment.created_at > datetime.utcnow() - timedelta(days=30)
        ).all()
        
        if not recent_payments:
            # New user, assess based on amount
            if amount > 10000:
                return 0.8
            elif amount > 5000:
                return 0.5
            else:
                return 0.2
        
        avg_amount = sum(p.amount for p in recent_payments) / len(recent_payments)
        
        if amount > avg_amount * 3:
            return 0.8
        elif amount > avg_amount * 2:
            return 0.5
        else:
            return 0.2
    
    def _assess_frequency_risk(self, user: User, db: Session) -> float:
        from ..models import Payment
        today_payments = db.query(Payment).filter(
            Payment.user_id == user.id,
            Payment.created_at > datetime.utcnow() - timedelta(hours=24)
        ).count()
        
        if today_payments > 10:
            return 0.9
        elif today_payments > 5:
            return 0.6
        else:
            return 0.2
    
    def _assess_behavioral_risk(self, user: User, transaction_data: Dict[str, Any]) -> float:
        # Analyze behavioral patterns
        risk_score = 0.0
        
        # Check for unusual payment methods
        if transaction_data.get("payment_method") not in ["bank_transfer", "card"]:
            risk_score += 0.3
        
        # Check for off-hours transactions
        if datetime.utcnow().hour < 6 or datetime.utcnow().hour > 22:
            risk_score += 0.2
        
        return min(risk_score, 1.0)
    
    def _store_risk_assessment(self, user_id: int, assessment_type: str, 
                              risk_factors: Dict[str, float], overall_risk: float, db: Session):
        assessment = RiskAssessment(
            user_id=user_id,
            assessment_type=assessment_type,
            behavioral_score=risk_factors.get("behavioral", 0.0),
            device_risk=risk_factors.get("device", 0.0),
            location_risk=risk_factors.get("location", 0.0),
            velocity_risk=risk_factors.get("velocity", 0.0),
            overall_risk=overall_risk,
            context_data=risk_factors
        )
        db.add(assessment)
        db.commit()
    
    def determine_auth_requirements(self, risk_score: float) -> Dict[str, Any]:
        """Determine authentication requirements based on risk score"""
        if risk_score >= self.risk_thresholds["high"]:
            return {
                "auth_level": "biometric_mfa",
                "requires_mfa": True,
                "requires_biometric": True,
                "additional_verification": True,
                "message": "High-risk activity detected. Enhanced verification required."
            }
        elif risk_score >= self.risk_thresholds["medium"]:
            return {
                "auth_level": "mfa",
                "requires_mfa": True,
                "requires_biometric": False,
                "additional_verification": False,
                "message": "Additional verification required for security."
            }
        else:
            return {
                "auth_level": "basic",
                "requires_mfa": False,
                "requires_biometric": False,
                "additional_verification": False,
                "message": "Standard authentication sufficient."
            }

risk_engine = RiskEngine()
