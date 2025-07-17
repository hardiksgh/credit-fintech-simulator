from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base

# Enhanced User model with security features
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    
    # Profile information
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone = Column(String(20))
    date_of_birth = Column(DateTime)
    
    # Security & Authentication
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    last_login = Column(DateTime)
    password_changed_at = Column(DateTime, default=func.now())
    
    # MFA settings
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255))
    backup_codes = Column(JSON)
    
    # Behavioral biometrics
    typing_pattern = Column(JSON)
    device_fingerprints = Column(JSON)
    
    # Credit profile
    base_credit_score = Column(Integer, default=650)
    risk_category = Column(String(20), default="medium")  # low, medium, high
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    roles = relationship("UserRole", back_populates="user")
    loans = relationship("Loan", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    security_events = relationship("SecurityEvent", back_populates="user")

# Role-based access control
class Role(Base):
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True)  # individual, advisor, loan_officer, admin
    description = Column(Text)
    permissions = Column(JSON)  # List of permissions
    created_at = Column(DateTime, default=func.now())

class UserRole(Base):
    __tablename__ = "user_roles"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    role_id = Column(Integer, ForeignKey("roles.id"))
    granted_by = Column(Integer, ForeignKey("users.id"))
    granted_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    user = relationship("User", back_populates="roles")
    role = relationship("Role")

# Enhanced Loan model
class Loan(Base):
    __tablename__ = "loans"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    interest_rate = Column(Float, nullable=False)
    term_months = Column(Integer, nullable=False)
    purpose = Column(String(100))
    status = Column(String(20), default="pending")  # pending, approved, rejected, active, closed
    
    # Risk assessment
    risk_score = Column(Float)
    approval_confidence = Column(Float)
    fraud_score = Column(Float, default=0.0)
    
    # Approval workflow
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    rejection_reason = Column(Text)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    user = relationship("User", back_populates="loans", foreign_keys=[user_id])
    payments = relationship("Payment", back_populates="loan")

# Enhanced Payment model
class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    loan_id = Column(Integer, ForeignKey("loans.id"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(50))  # bank_transfer, card, wallet
    status = Column(String(20), default="pending")  # pending, completed, failed
    
    # Risk indicators
    risk_score = Column(Float, default=0.0)
    fraud_indicators = Column(JSON)
    
    # Authentication context
    auth_method = Column(String(50))  # password, mfa, biometric
    device_fingerprint = Column(String(255))
    ip_address = Column(String(45))
    location = Column(String(100))
    
    scheduled_date = Column(DateTime)
    processed_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    
    user = relationship("User", back_populates="payments")
    loan = relationship("Loan", back_populates="payments")

# Security and audit models
class SecurityEvent(Base):
    __tablename__ = "security_events"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_type = Column(String(50))  # login, failed_login, mfa_challenge, suspicious_activity
    severity = Column(String(20))  # low, medium, high, critical
    description = Column(Text)
    
    # Context data
    ip_address = Column(String(45))
    user_agent = Column(Text)
    device_fingerprint = Column(String(255))
    location = Column(String(100))
    
    # Risk impact
    risk_impact = Column(Float, default=0.0)
    credit_score_impact = Column(Float, default=0.0)
    
    resolved = Column(Boolean, default=False)
    resolved_by = Column(Integer, ForeignKey("users.id"))
    resolved_at = Column(DateTime)
    
    created_at = Column(DateTime, default=func.now())
    
    user = relationship("User", back_populates="security_events")

class APIKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True)
    key_hash = Column(String(255), unique=True)
    name = Column(String(100))
    user_id = Column(Integer, ForeignKey("users.id"))
    permissions = Column(JSON)
    rate_limit = Column(Integer, default=1000)
    
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())

class DelegationToken(Base):
    __tablename__ = "delegation_tokens"
    
    id = Column(Integer, primary_key=True)
    token_hash = Column(String(255), unique=True)
    delegator_id = Column(Integer, ForeignKey("users.id"))
    delegate_id = Column(Integer, ForeignKey("users.id"))
    permissions = Column(JSON)
    
    usage_count = Column(Integer, default=0)
    max_usage = Column(Integer, default=1)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())

# Credit scoring and risk models
class CreditScenario(Base):
    __tablename__ = "credit_scenarios"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    scenario_name = Column(String(255))
    scenario_type = Column(String(50))  # what_if, stress_test, optimization
    parameters = Column(JSON)
    projected_score = Column(Integer)
    confidence_level = Column(Float)
    
    access_level = Column(String(20), default="private")  # private, shared, public
    created_by_role = Column(String(50))
    
    created_at = Column(DateTime, default=func.now())

class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    assessment_type = Column(String(50))  # login, transaction, application
    
    # Risk factors
    behavioral_score = Column(Float)
    device_risk = Column(Float)
    location_risk = Column(Float)
    velocity_risk = Column(Float)
    overall_risk = Column(Float)
    
    # Context
    context_data = Column(JSON)
    mitigation_actions = Column(JSON)
    
    created_at = Column(DateTime, default=func.now())
