import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.db.models import Base, User, LeaveRequest, CompanyPolicy
from backend.shared.ai.gemini import process_unified_ai_assistant_query
from backend.modules.hr.leave_management.service import (
    submit_leave_request,
    update_leave_approval_status,
    get_user_remaining_leave_days
)
from backend.modules.hr.leave_management.schemas import CreateLeaveRequestSchema

@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    
    # Create test worker and HR user
    worker = User(id=1, email="worker_test@buildora.com", full_name="Field Worker", role="WORKER", password_hash="dummy_hash")
    hr_user = User(id=2, email="hr_test@buildora.com", full_name="HR Manager", role="HR_MANAGER", password_hash="dummy_hash")
    db.add_all([worker, hr_user])

    # Seed sample policy
    policy = CompanyPolicy(
        id=1,
        title="Safety & Site Guidelines 2026",
        category="Safety & Site",
        content="Standard working hours are 8:00 AM to 5:00 PM. Hard hats and safety vests are mandatory at all times. Reimbursements for field expenses up to $150 require valid receipt submission within 7 days.",
        original_filename="safety_guidelines.txt"
    )
    db.add(policy)
    db.commit()

    yield db
    db.close()


def test_leave_intent_routing_and_auto_approval_2_days(test_db):
    worker = test_db.query(User).filter(User.id == 1).first()
    
    # 1. Check Initial Balance
    res_bal = process_unified_ai_assistant_query("How many leave days do I have left?", test_db, current_user=worker)
    assert res_bal["intent"] == "leave_balance"
    assert "15 days" in res_bal["answer"]

    # 2. Request 2 Days Leave ("I want to take a leave for 2 days")
    res_req = process_unified_ai_assistant_query("I want to take a leave for 2 days", test_db, current_user=worker)
    assert res_req["intent"] == "leave_request"
    assert res_req["auto_approved_leave"] is True
    assert "automatically approved" in res_req["answer"].lower()

    # 3. Verify Balance reduced to 13
    assert get_user_remaining_leave_days(test_db, 1) == 13
    res_bal2 = process_unified_ai_assistant_query("Check my leave balance", test_db, current_user=worker)
    assert "13 days" in res_bal2["answer"]


def test_leave_auto_approval_3_days(test_db):
    worker = test_db.query(User).filter(User.id == 1).first()
    
    # Request 3 Days Leave ("I want to request 3 days leave")
    res_req = process_unified_ai_assistant_query("I want to request 3 days leave", test_db, current_user=worker)
    assert res_req["intent"] == "leave_request"
    assert res_req["auto_approved_leave"] is True
    assert get_user_remaining_leave_days(test_db, 1) == 12


def test_cumulative_approved_leaves(test_db):
    worker = test_db.query(User).filter(User.id == 1).first()
    
    # Approve 3 days twice -> remaining 9
    process_unified_ai_assistant_query("I want to request 3 days leave", test_db, current_user=worker)
    process_unified_ai_assistant_query("I need 3 days leave", test_db, current_user=worker)
    assert get_user_remaining_leave_days(test_db, 1) == 9


def test_insufficient_leave_balance_rejection(test_db):
    worker = test_db.query(User).filter(User.id == 1).first()
    
    # Consume 14 days (submitted as PENDING, approved by HR)
    today = datetime.date.today()
    req = CreateLeaveRequestSchema(start_date=today, end_date=today + datetime.timedelta(days=13), reason="Long vacation")
    leave_rec = submit_leave_request(test_db, worker, req)
    update_leave_approval_status(test_db, hr_id=2, leave_id=leave_rec.id, new_status="APPROVED")
    assert get_user_remaining_leave_days(test_db, 1) == 1

    # Attempt 3-day request -> Rejection due to insufficient balance
    res = process_unified_ai_assistant_query("I want to take leave for 3 days", test_db, current_user=worker)
    assert "Insufficient Leave Balance" in res["answer"]
    assert get_user_remaining_leave_days(test_db, 1) == 1  # Unchanged


def test_long_leave_requires_reason_and_hr_approval(test_db):
    worker = test_db.query(User).filter(User.id == 1).first()
    hr_user = test_db.query(User).filter(User.id == 2).first()

    # Step 1: Request 5 days -> Prompt for reason
    res1 = process_unified_ai_assistant_query("I need 5 days leave", test_db, current_user=worker, session_id="test_sess_5")
    assert "reason" in res1["answer"].lower()
    assert res1["auto_approved_leave"] is False
    assert get_user_remaining_leave_days(test_db, 1) == 15  # Pending request does not reduce balance

    # Step 2: Provide reason -> Submits PENDING
    res2 = process_unified_ai_assistant_query("Family event in another state", test_db, current_user=worker, session_id="test_sess_5")
    assert "submitted to hr" in res2["answer"].lower()
    assert get_user_remaining_leave_days(test_db, 1) == 15  # Still 15 while pending

    # Verify DB record is PENDING
    pending_leave = test_db.query(LeaveRequest).filter(LeaveRequest.user_id == 1, LeaveRequest.status == "PENDING").first()
    assert pending_leave is not None
    assert pending_leave.days == 5

    # Step 3: HR Approves -> Balance reduces to 10
    update_leave_approval_status(test_db, hr_id=2, leave_id=pending_leave.id, new_status="APPROVED")
    assert get_user_remaining_leave_days(test_db, 1) == 10


def test_hr_rejection_preserves_balance(test_db):
    worker = test_db.query(User).filter(User.id == 1).first()
    
    # Create 4-day pending leave
    process_unified_ai_assistant_query("I need 4 days leave", test_db, current_user=worker, session_id="test_sess_rej")
    process_unified_ai_assistant_query("Personal business", test_db, current_user=worker, session_id="test_sess_rej")

    pending_leave = test_db.query(LeaveRequest).filter(LeaveRequest.user_id == 1, LeaveRequest.status == "PENDING").first()
    assert pending_leave is not None

    # HR Rejects
    update_leave_approval_status(test_db, hr_id=2, leave_id=pending_leave.id, new_status="REJECTED")
    assert pending_leave.status == "REJECTED"
    assert get_user_remaining_leave_days(test_db, 1) == 15  # Balance untouched


def test_hr_approval_balance_recheck_blocks_if_exhausted(test_db):
    worker = test_db.query(User).filter(User.id == 1).first()

    # Step 1: Create a 5-day pending leave when balance = 15
    process_unified_ai_assistant_query("I need 5 days leave", test_db, current_user=worker, session_id="test_sess_check")
    process_unified_ai_assistant_query("Travel", test_db, current_user=worker, session_id="test_sess_check")
    pending_leave = test_db.query(LeaveRequest).filter(LeaveRequest.user_id == 1, LeaveRequest.status == "PENDING").first()

    # Step 2: Another leave of 12 days gets approved in the meantime
    today = datetime.date.today()
    req = CreateLeaveRequestSchema(start_date=today, end_date=today + datetime.timedelta(days=11), reason="Medical")
    leave_rec2 = submit_leave_request(test_db, worker, req)  # Submitted as PENDING
    update_leave_approval_status(test_db, hr_id=2, leave_id=leave_rec2.id, new_status="APPROVED")  # Consumes 12 days -> remaining = 3

    assert get_user_remaining_leave_days(test_db, 1) == 3

    # Step 3: HR attempts to approve the 5-day pending request -> MUST FAIL because only 3 days remain
    with pytest.raises(Exception) as exc_info:
        update_leave_approval_status(test_db, hr_id=2, leave_id=pending_leave.id, new_status="APPROVED")
    assert "only 3 remaining" in str(exc_info.value).lower()


def test_policy_queries(test_db):
    worker = test_db.query(User).filter(User.id == 1).first()

    # Working hours query
    res_hours = process_unified_ai_assistant_query("What are the working hours?", test_db, current_user=worker)
    assert res_hours["intent"] == "policy"
    assert "policy" in res_hours["answer"].lower() or "guidelines" in res_hours["answer"].lower()

    # Leave policy query
    res_lpol = process_unified_ai_assistant_query("What is the leave policy?", test_db, current_user=worker)
    assert res_lpol["intent"] == "policy"
    assert "15 days" in res_lpol["answer"] or "leave" in res_lpol["answer"].lower()

    # Multi-topic query (safety and expenses)
    res_multi = process_unified_ai_assistant_query("What are the company policies for safety and expenses?", test_db, current_user=worker)
    assert res_multi["intent"] == "policy"
    assert "policy" in res_multi["answer"].lower() or "safety" in res_multi["answer"].lower() or "expense" in res_multi["answer"].lower()
