from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..financial.emi_calculator import EMICalculator, EMIRequest, EMIResponse
from ..financial.loan_analytics import LoanAnalytics

router = APIRouter(prefix="/financial", tags=["Financial Calculations"])

@router.post("/calculate-emi", response_model=EMIResponse)
def calculate_emi(request: EMIRequest):
    """Calculate EMI for loan"""
    try:
        result = EMICalculator.calculate_emi(
            request.principal, request.rate, request.tenure_months
        )
        
        # Generate monthly breakdown for first 12 months
        schedule = EMICalculator.generate_amortization_schedule(
            request.principal, request.rate, request.tenure_months
        )
        
        return EMIResponse(
            principal=request.principal,
            rate=request.rate,
            tenure_months=request.tenure_months,
            emi=result["emi"],
            total_amount=result["total_amount"],
            total_interest=result["total_interest"],
            monthly_breakdown=schedule
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"EMI calculation failed: {str(e)}")

@router.get("/loan-schedule/{loan_id}")
def get_loan_schedule(loan_id: int, db: Session = Depends(get_db)):
    """Get complete amortization schedule for a loan"""
    from ..models import Loan
    
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    
    schedule = EMICalculator.generate_amortization_schedule(
        loan.amount, loan.interest_rate, loan.term_months
    )
    
    return {
        "loan_id": loan_id,
        "loan_amount": loan.amount,
        "interest_rate": loan.interest_rate,
        "tenure_months": loan.term_months,
        "schedule": schedule
    }

@router.get("/analytics/overview")
def get_loan_analytics(db: Session = Depends(get_db)):
    """Get comprehensive loan analytics"""
    return LoanAnalytics.get_loan_statistics(db)

@router.get("/analytics/user/{user_id}")
def get_user_analytics(user_id: int, db: Session = Depends(get_db)):
    """Get user-specific loan analytics"""
    return LoanAnalytics.get_user_loan_summary(user_id, db)

@router.post("/calculate-tenure")
def calculate_tenure(principal: float, emi: float, rate: float):
    """Calculate loan tenure based on EMI"""
    try:
        tenure = EMICalculator.calculate_tenure(principal, emi, rate)
        return {
            "principal": principal,
            "emi": emi,
            "rate": rate,
            "tenure_months": int(tenure),
            "tenure_years": round(tenure / 12, 1)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Tenure calculation failed: {str(e)}")

@router.post("/calculate-principal")
def calculate_principal(emi: float, tenure_months: int, rate: float):
    """Calculate maximum loan principal based on EMI capacity"""
    import numpy_financial as npf
    
    try:
        monthly_rate = rate / (12 * 100)
        principal = npf.pv(monthly_rate, tenure_months, -emi)
        
        return {
            "emi": emi,
            "tenure_months": tenure_months,
            "rate": rate,
            "max_principal": round(float(principal), 2)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Principal calculation failed: {str(e)}")
