from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import os
from datetime import datetime

from .database import engine, get_db, Base, test_database_connection
from .models import User, Loan, Payment, SecurityEvent, UserRole, Role
from .schemas import (
    UserCreate, UserLogin, LoanCreate, PaymentCreate, CreditScoreResponse,
    MFASetup, MFAVerification, BiometricData, RiskContext, PermissionCheck,
    DelegationRequest, SecurityEventCreate
)
from .auth.jwt_handler import jwt_handler
from .auth.risk_engine import risk_engine
from .crud import user_crud, loan_crud, payment_crud, security_crud

# Create database tables
Base.metadata.create_all(bind=engine)
test_database_connection()

app = FastAPI(
    title="Fintech Credit Score Simulator",
    version="2.0.0",
    description="Advanced credit scoring simulation with comprehensive security features"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# Dependency to get current user
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    payload = jwt_handler.verify_token(token)
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    user = user_crud.get_user(db, int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user

# Permission checking dependency
def require_permission(permission: str):
    def permission_checker(current_user: User = Depends(get_current_user)):
        if not user_crud.has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
        return current_user
    return permission_checker

# Risk-based authentication middleware
@app.middleware("http")
async def risk_assessment_middleware(request: Request, call_next):
    # Skip risk assessment for public endpoints
    if request.url.path in ["/", "/health", "/docs", "/openapi.json"]:
        return await call_next(request)
    
    # Extract risk context
    risk_context = RiskContext(
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent", ""),
        device_fingerprint=request.headers.get("x-device-fingerprint", ""),
        location=request.headers.get("x-location")
    )
    
    # Store in request state for use in endpoints
    request.state.risk_context = risk_context
    
    response = await call_next(request)
    return response

# Authentication endpoints
@app.post("/auth/register")
async def register(user_data: UserCreate, request: Request, db: Session = Depends(get_db)):
    """Register a new user with risk assessment"""
    
    # Check if user exists
    if user_crud.get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    user = user_crud.create_user(db, user_data)
    
    # Log security event
    security_crud.create_security_event(
        db, user.id, "registration", "low", 
        "User registration", request.state.risk_context.__dict__
    )
    
    # Generate tokens
    access_token = jwt_handler.create_access_token({"sub": str(user.id)})
    refresh_token = jwt_handler.create_refresh_token(user.id)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user_crud.get_user_profile(user)
    }

@app.post("/auth/login")
async def login(login_data: UserLogin, request: Request, db: Session = Depends(get_db)):
    """Login with risk-based authentication"""
    
    user = user_crud.authenticate_user(db, login_data.email, login_data.password)
    if not user:
        # Log failed login
        security_crud.create_security_event(
            db, None, "failed_login", "medium",
            f"Failed login attempt for {login_data.email}",
            request.state.risk_context.__dict__
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Assess login risk
    risk_score = risk_engine.assess_login_risk(user, request.state.risk_context, db)
    auth_requirements = risk_engine.determine_auth_requirements(risk_score)
    
    # Log successful login
    security_crud.create_security_event(
        db, user.id, "login", "low",
        "Successful login", 
        {**request.state.risk_context.__dict__, "risk_score": risk_score}
    )
    
    # If high risk, require additional authentication
    if auth_requirements["requires_mfa"] and not user.mfa_enabled:
        return {
            "requires_setup": True,
            "message": "MFA setup required for enhanced security",
            "risk_score": risk_score
        }
    
    if auth_requirements["requires_mfa"]:
        # Generate MFA challenge
        challenge_token = jwt_handler.create_access_token(
            {"sub": str(user.id), "challenge": "mfa", "risk_score": risk_score},
            expires_delta=timedelta(minutes=5)
        )
        return {
            "challenge_required": True,
            "challenge_type": "mfa",
            "challenge_token": challenge_token,
            "message": auth_requirements["message"]
        }
    
    # Generate tokens for successful login
    access_token = jwt_handler.create_access_token({"sub": str(user.id)})
    refresh_token = jwt_handler.create_refresh_token(user.id)
    
    # Update last login
    user_crud.update_last_login(db, user.id)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "risk_score": risk_score,
        "user": user_crud.get_user_profile(user)
    }

@app.post("/auth/mfa/setup")
async def setup_mfa(
    mfa_data: MFASetup,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set up multi-factor authentication"""
    success = user_crud.setup_mfa(db, current_user.id, mfa_data.secret, mfa_data.verification_code)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code"
        )
    
    return {"message": "MFA setup successful", "backup_codes": user_crud.generate_backup_codes(db, current_user.id)}

@app.post("/auth/mfa/verify")
async def verify_mfa(
    mfa_verification: MFAVerification,
    challenge_token: str,
    db: Session = Depends(get_db)
):
    """Verify MFA challenge"""
    payload = jwt_handler.verify_token(challenge_token)
    
    if payload.get("challenge") != "mfa":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid challenge token"
        )
    
    user_id = int(payload.get("sub"))
    user = user_crud.get_user(db, user_id)
    
    if not user_crud.verify_mfa(user, mfa_verification.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code"
        )
    
    # Generate final access token
    access_token = jwt_handler.create_access_token({"sub": str(user_id)})
    refresh_token = jwt_handler.create_refresh_token(user_id)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user_crud.get_user_profile(user)
    }

# Enhanced loan endpoints with authorization
@app.post("/loans", dependencies=[Depends(require_permission("create_loan"))])
async def create_loan(
    loan_data: LoanCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a loan with risk assessment"""
    
    # Assess transaction risk
    transaction_context = {
        "amount": loan_data.amount,
        "type": "loan_application",
        "user_id": current_user.id
    }
    
    risk_score = risk_engine.assess_transaction_risk(current_user, transaction_context, db)
    
    # High-risk loans require additional approval
    if risk_score > 0.7 and loan_data.amount > 50000:
        # Create pending loan for manual review
        loan = loan_crud.create_loan(db, current_user.id, loan_data, status="pending_review")
        
        # Log high-risk application
        security_crud.create_security_event(
            db, current_user.id, "high_risk_loan_application", "high",
            f"High-risk loan application: ${loan_data.amount}",
            {"risk_score": risk_score, "loan_id": loan.id}
        )
        
        return {
            "loan": loan,
            "status": "pending_review",
            "message": "Loan application submitted for manual review due to risk factors",
            "risk_score": risk_score
        }
    
    # Auto-approve low-risk loans
    loan = loan_crud.create_loan(db, current_user.id, loan_data, status="approved")
    
    return {
        "loan": loan,
        "status": "approved",
        "risk_score": risk_score
    }

@app.post("/payments", dependencies=[Depends(require_permission("make_payment"))])
async def make_payment(
    payment_data: PaymentCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Make a payment with fraud detection"""
    
    # Verify loan ownership
    loan = loan_crud.get_loan(db, payment_data.loan_id)
    if not loan or loan.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan not found"
        )
    
    # Assess payment risk
    payment_context = {
        "amount": payment_data.amount,
        "payment_method": payment_data.payment_method,
        "loan_id": payment_data.loan_id
    }
    
    risk_score = risk_engine.assess_transaction_risk(current_user, payment_context, db)
    auth_requirements = risk_engine.determine_auth_requirements(risk_score)
    
    # High-risk payments require additional verification
    if auth_requirements["requires_mfa"]:
        return {
            "requires_additional_auth": True,
            "auth_requirements": auth_requirements,
            "risk_score": risk_score,
            "message": "Additional verification required for this payment"
        }
    
    # Process payment
    payment = payment_crud.create_payment(
        db, current_user.id, payment_data, 
        risk_score=risk_score,
        auth_context=request.state.risk_context.__dict__
    )
    
    return {
        "payment": payment,
        "risk_score": risk_score,
        "message": "Payment processed successfully"
    }

@app.get("/score")
async def get_credit_score(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> CreditScoreResponse:
    """Get credit score with security impact analysis"""
    
    # Calculate base credit score
    base_score = loan_crud.calculate_credit_score(db, current_user.id)
    
    # Factor in security events
    security_impact = security_crud.calculate_security_impact(db, current_user.id)
    
    # Adjust score based on security behavior
    adjusted_score = max(300, min(850, base_score - (security_impact * 50)))
    
    # Get score factors
    score_factors = loan_crud.get_score_factors(db, current_user.id)
    score_factors["security_behavior"] = 1 - security_impact
    
    # Generate recommendations
    recommendations = loan_crud.generate_recommendations(db, current_user.id, adjusted_score)
    
    return CreditScoreResponse(
        current_score=int(adjusted_score),
        score_factors=score_factors,
        risk_category=current_user.risk_category,
        recommendations=recommendations,
        security_impact=security_impact,
        last_updated=datetime.utcnow()
    )

# Admin endpoints
@app.get("/admin/users", dependencies=[Depends(require_permission("view_all_users"))])
async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all users (admin only)"""
    users = user_crud.get_users(db, skip=skip, limit=limit)
    return {"users": users, "total": len(users)}

@app.get("/admin/security-events", dependencies=[Depends(require_permission("view_security_events"))])
async def get_security_events(
    user_id: Optional[int] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get security events with filtering"""
    events = security_crud.get_security_events(
        db, user_id=user_id, event_type=event_type, 
        severity=severity, skip=skip, limit=limit
    )
    return {"events": events, "total": len(events)}

# Delegation endpoints
@app.post("/auth/delegate")
async def create_delegation(
    delegation_request: DelegationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create delegation token for temporary access"""
    
    delegate = user_crud.get_user_by_email(db, delegation_request.delegate_email)
    if not delegate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delegate user not found"
        )
    
    # Create delegation token
    delegation_token = user_crud.create_delegation_token(
        db, current_user.id, delegate.id, 
        delegation_request.permissions,
        delegation_request.expires_in_hours,
        delegation_request.max_usage
    )
    
    return {
        "delegation_token": delegation_token,
        "expires_in_hours": delegation_request.expires_in_hours,
        "permissions": delegation_request.permissions
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
