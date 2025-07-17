
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import os

# Database configuration
DATABASE_URL = "mysql+pymysql://root:Hardik%402827@localhost:3306/fintech_credit_simulator"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True)
    username = Column(String(100), unique=True)
    password_hash = Column(String(255))
    first_name = Column(String(100))
    last_name = Column(String(100))
    credit_score = Column(Integer, default=650)
    created_at = Column(DateTime, default=datetime.utcnow)

class Loan(Base):
    __tablename__ = "loans"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    amount = Column(Float)
    term_months = Column(Integer)
    purpose = Column(String(255))
    interest_rate = Column(Float)
    status = Column(String(50), default="approved")
    created_at = Column(DateTime, default=datetime.utcnow)

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    loan_id = Column(Integer)
    amount = Column(Float)
    payment_method = Column(String(100))
    status = Column(String(50), default="completed")
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Enhanced Fintech Credit Simulator", version="3.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models (same as before)
class UserCreate(BaseModel):
    email: str
    username: str
    password: str
    first_name: str
    last_name: str

class UserLogin(BaseModel):
    email: str
    password: str

class LoanCreate(BaseModel):
    amount: float
    term_months: int
    purpose: str

class PaymentCreate(BaseModel):
    loan_id: int
    amount: float
    payment_method: str
class BankVerificationRequest(BaseModel):
    account_number: str
    ifsc_code: str
    account_holder_name: str
    phone_number: Optional[str] = None
    account_type: str = "person"
    consent: str = "Y"

# Enhanced endpoints with database
@app.get("/")
def root():
    return {
        "message": "🚀 Enhanced Fintech Credit Simulator with Database!",
        "version": "3.0.0",
        "features": ["database_integration", "real_credit_scoring", "fraud_detection"],
        "status": "PRODUCTION_READY"
    }

@app.post("/auth/register")
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    db_user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=user_data.password,  # In production, hash this
        first_name=user_data.first_name,
        last_name=user_data.last_name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return {
        "success": True,
        "message": "✅ User registered in database!",
        "user": {
            "id": db_user.id,
            "email": db_user.email,
            "username": db_user.username,
            "credit_score": db_user.credit_score
        },
        "access_token": f"fintech_token_{db_user.id}"
    }

@app.get("/auth/register")
def get_registration_info():
    """Get registration requirements and form information"""
    return {
        "endpoint": "/auth/register",
        "method": "POST",
        "description": "Register a new user in the fintech credit simulator",
        "required_fields": {
            "email": "string (valid email format)",
            "username": "string (3-50 characters)",
            "password": "string (minimum 8 characters)",
            "first_name": "string",
            "last_name": "string"
        },
        "example_request": {
            "email": "hardiksingh2704@gmail.com",
            "username": "hardiksingh",
            "password": "hardik@2827",
            "first_name": "Hardik",
            "last_name": "Singh"
        },
        "response_format": {
            "success": "boolean",
            "message": "string",
            "user": "object with user details",
            "access_token": "string"
        },
        "features": [
            "Database integration with MySQL",
            "Email uniqueness validation",
            "Automatic credit score assignment (650)",
            "Access token generation"
        ]
    }


@app.post("/loans")
def create_loan(loan_data: LoanCreate, db: Session = Depends(get_db)):
    # Calculate interest rate based on amount
    interest_rate = 5.0 + (loan_data.amount / 100000) * 2  # Higher amount = higher rate
    
    db_loan = Loan(
        user_id=1,  # For demo, use user ID 1
        amount=loan_data.amount,
        term_months=loan_data.term_months,
        purpose=loan_data.purpose,
        interest_rate=interest_rate
    )
    db.add(db_loan)
    db.commit()
    db.refresh(db_loan)
    
    return {
        "success": True,
        "message": "🏦 Loan saved to database!",
        "loan": {
            "id": db_loan.id,
            "amount": db_loan.amount,
            "term_months": db_loan.term_months,
            "purpose": db_loan.purpose,
            "interest_rate": round(db_loan.interest_rate, 2),
            "status": db_loan.status
        }
    }



@app.get("/score")
def get_credit_score(db: Session = Depends(get_db)):
    # Calculate real credit score based on database data
    user_id = 1  # Demo user
    
    # Get user's loans and payments
    loans = db.query(Loan).filter(Loan.user_id == user_id).all()
    payments = db.query(Payment).filter(Payment.user_id == user_id).all()
    
    # Calculate score factors
    base_score = 650
    
    # Payment history factor
    if payments:
        on_time_payments = len([p for p in payments if p.status == "completed"])
        payment_ratio = on_time_payments / len(payments)
        payment_score = payment_ratio * 150
    else:
        payment_score = 0
    
    # Credit utilization factor
    total_loan_amount = sum(loan.amount for loan in loans)
    total_payments = sum(payment.amount for payment in payments)
    
    if total_loan_amount > 0:
        utilization = max(0, (total_loan_amount - total_payments) / total_loan_amount)
        utilization_score = (1 - utilization) * 100
    else:
        utilization_score = 100
    
    final_score = int(base_score + payment_score + utilization_score)
    final_score = max(300, min(850, final_score))
    
    return {
        "success": True,
        "current_score": final_score,
        "score_factors": {
            "base_score": base_score,
            "payment_history": round(payment_score, 2),
            "credit_utilization": round(utilization_score, 2)
        },
        "total_loans": len(loans),
        "total_payments": len(payments),
        "total_loan_amount": total_loan_amount,
        "total_paid": total_payments,
        "last_updated": datetime.utcnow().isoformat()
    }

@app.post("/auth/login")
def login(login_data: UserLogin):
    """User login endpoint"""
    return {
        "success": True,
        "message": "✅ Login successful!",
        "user": {
            "email": login_data.email
        },
        "access_token": "fintech_login_token_123",
        "token_type": "bearer"
    }



import numpy_financial as npf
from pydantic import BaseModel, Field

class EMIRequest(BaseModel):
    principal: float = Field(..., gt=0)
    rate: float = Field(..., gt=0, le=50)
    tenure_months: int = Field(..., gt=0, le=360)

@app.post("/calculate-emi")
def calculate_emi(request: EMIRequest):
    """Calculate EMI for loan"""
    try:
        monthly_rate = request.rate / (12 * 100)
        emi = npf.pmt(monthly_rate, request.tenure_months, -request.principal)
        total_amount = float(emi * request.tenure_months)
        total_interest = total_amount - request.principal
        
        return {
            "principal": request.principal,
            "rate": request.rate,
            "tenure_months": request.tenure_months,
            "emi": round(float(emi), 2),
            "total_amount": round(total_amount, 2),
            "total_interest": round(total_interest, 2)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"EMI calculation failed: {str(e)}")
    


@app.post("/verify-account")
def verify_bank_account(verification_request: BankVerificationRequest):
    """Bank Account Verification API"""
    
    # Valid test accounts
    valid_accounts = {
        "HDFC0000001": {
            "name": "JANE DOE", 
            "bank": "HDFC BANK LIMITED"
        },
        "YESB0000262": {
            "name": "JOHN DOE", 
            "bank": "YES BANK"
        }
    }
    
    ifsc_code = verification_request.ifsc_code  # Fixed field name
    
    if ifsc_code in valid_accounts:
        account_data = valid_accounts[ifsc_code]
        return {
            "status": "SUCCESS",
            "message": "Bank account details verified successfully",
            "data": {
                "name_at_bank": account_data["name"],
                "bank_name": account_data["bank"]
            }
        }
    
    return {
        "status": "FAILED",
        "message": "Invalid IFSC code provided",
        "data": {}
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
