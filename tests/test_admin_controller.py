import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from fastapi.testclient import TestClient
from app import app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.database import Base, UserDB
from models.role_model import Role
from controllers.admin_controller import (
    get_total_users_count,
    get_daily_signups,
    get_points_summary,
    get_top_users,
    change_user_role,
    _parse_timestamp,
)
from datetime import datetime, timezone, timedelta
import base64
import os as os_module

# Setup the database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_admin.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables in the test database
Base.metadata.create_all(bind=engine)


@pytest.fixture(scope="module")
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    client = TestClient(app)
    yield client


@pytest.fixture(scope="module")
def create_test_users(db):
    """Create test users with various roles and transaction history."""
    users = []
    
    # Create admin user
    admin_user = UserDB(
        unique_id="admin_test_1",
        first_name="Admin",
        last_name="User",
        email="admin@test.com",
        phone_number="1111111111",
        role=Role.ADMIN,
        credits=1000,
        transaction_history=[
            {
                "type": "ALLOCATE",
                "points": 100,
                "timestamp": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
                "balance": 1000,
                "action_user": "admin_test_1",
            }
        ],
    )
    db.add(admin_user)
    users.append(admin_user)
    
    # Create regular user
    regular_user = UserDB(
        unique_id="user_test_1",
        first_name="Regular",
        last_name="User",
        email="user@test.com",
        phone_number="2222222222",
        role=Role.USER,
        credits=500,
        transaction_history=[
            {
                "type": "ALLOCATE",
                "points": 200,
                "timestamp": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                "balance": 500,
                "action_user": "admin_test_1",
            },
            {
                "type": "REDEEM",
                "points": -50,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "balance": 450,
                "action_user": "user_test_1",
            }
        ],
    )
    db.add(regular_user)
    users.append(regular_user)
    
    # Create another user with older transactions
    old_user = UserDB(
        unique_id="user_test_2",
        first_name="Old",
        last_name="User",
        email="old@test.com",
        phone_number="3333333333",
        role=Role.USER,
        credits=300,
        transaction_history=[
            {
                "type": "ALLOCATE",
                "points": 300,
                "timestamp": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
                "balance": 300,
                "action_user": "admin_test_1",
            }
        ],
    )
    db.add(old_user)
    users.append(old_user)
    
    db.commit()
    for user in users:
        db.refresh(user)
    return users


@pytest.fixture(scope="module")
def admin_token():
    """Generate admin token for testing."""
    admin_password = os_module.getenv('ADMIN_PASSWORD', 'test_admin_password')
    return base64.b64encode(admin_password.encode()).decode()


def test_get_total_users_count(db, create_test_users):
    """Test getting total users count."""
    count = get_total_users_count(db)
    assert count >= 3  # At least our test users


def test_get_daily_signups(db, create_test_users):
    """Test getting daily signups."""
    result = get_daily_signups(db, days=7)
    assert "labels" in result
    assert "values" in result
    assert len(result["labels"]) == 7
    assert len(result["values"]) == 7
    assert all(isinstance(v, int) for v in result["values"])


def test_get_points_summary(db, create_test_users):
    """Test getting points summary."""
    result = get_points_summary(db, days=7)
    assert "minted_total" in result
    assert "redeemed_total" in result
    assert "minted_series" in result
    assert "redeemed_series" in result
    assert "labels" in result["minted_series"]
    assert "values" in result["minted_series"]
    assert result["minted_total"] >= 0
    assert result["redeemed_total"] >= 0


def test_get_top_users(db, create_test_users):
    """Test getting top users."""
    users = get_top_users(limit=5, db=db)
    assert isinstance(users, list)
    assert len(users) <= 5
    if len(users) > 0:
        assert "unique_id" in users[0]
        assert "name" in users[0]
        assert "credits" in users[0]
        assert "role" in users[0]
        # Should be sorted by credits descending
        if len(users) > 1:
            assert users[0]["credits"] >= users[1]["credits"]


def test_change_user_role(db, create_test_users, admin_token):
    """Test changing user role."""
    admin_id = "admin_test_1"
    target_user_id = "user_test_1"
    new_role = "SALES"
    
    result = change_user_role(admin_id, target_user_id, new_role, db)
    assert "message" in result
    assert "user" in result
    assert result["user"]["id"] == target_user_id
    assert result["user"]["role"] == Role.SALES.value
    
    # Verify in database
    updated_user = db.query(UserDB).filter(UserDB.unique_id == target_user_id).first()
    assert updated_user.role == Role.SALES


def test_change_user_role_unauthorized(db, create_test_users):
    """Test that non-admin cannot change roles."""
    non_admin_id = "user_test_1"
    target_user_id = "user_test_2"
    new_role = "ADMIN"
    
    with pytest.raises(Exception):  # Should raise HTTPException
        change_user_role(non_admin_id, target_user_id, new_role, db)


def test_change_user_role_invalid_role(db, create_test_users):
    """Test changing to invalid role."""
    admin_id = "admin_test_1"
    target_user_id = "user_test_1"
    new_role = "INVALID_ROLE"
    
    with pytest.raises(Exception):  # Should raise HTTPException
        change_user_role(admin_id, target_user_id, new_role, db)


def test_parse_timestamp_iso_format():
    """Test parsing ISO format timestamps."""
    iso_str = "2024-01-15T10:30:00Z"
    result = _parse_timestamp(iso_str)
    assert result is not None
    assert isinstance(result, datetime)
    assert result.tzinfo is not None


def test_parse_timestamp_with_timezone():
    """Test parsing timestamps with timezone."""
    tz_str = "2024-01-15T10:30:00+05:30"
    result = _parse_timestamp(tz_str)
    assert result is not None
    assert isinstance(result, datetime)
    assert result.tzinfo is not None


def test_parse_timestamp_datetime_object():
    """Test parsing datetime object."""
    dt = datetime.now(timezone.utc)
    result = _parse_timestamp(dt)
    assert result is not None
    assert result.tzinfo is not None


def test_parse_timestamp_unix_timestamp():
    """Test parsing Unix timestamp."""
    unix_ts = 1705312200  # Example timestamp
    result = _parse_timestamp(unix_ts)
    assert result is not None
    assert isinstance(result, datetime)
    assert result.tzinfo is not None


def test_parse_timestamp_none():
    """Test parsing None value."""
    result = _parse_timestamp(None)
    assert result is None


def test_admin_metrics_endpoints(client, create_test_users, admin_token):
    """Test admin metrics endpoints with authentication."""
    headers = {"TOKEN": admin_token}
    
    # Test total users
    response = client.get("/admin/metrics/total_users", headers=headers)
    assert response.status_code == 200
    assert "total_users" in response.json()
    
    # Test daily signups
    response = client.get("/admin/metrics/daily_signups?days=7", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "labels" in data
    assert "values" in data
    
    # Test points minted
    response = client.get("/admin/metrics/points_minted?days=7", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "series" in data
    
    # Test points redeemed
    response = client.get("/admin/metrics/points_redeemed?days=7", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "series" in data
    
    # Test top users
    response = client.get("/admin/metrics/top_users?limit=10", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "users" in data


def test_admin_metrics_unauthorized(client):
    """Test that metrics endpoints require authentication."""
    # Test without token
    response = client.get("/admin/metrics/total_users")
    assert response.status_code == 401
    
    # Test with invalid token
    headers = {"TOKEN": "invalid_token"}
    response = client.get("/admin/metrics/total_users", headers=headers)
    assert response.status_code == 401


def test_csv_export(client, create_test_users, admin_token):
    """Test CSV export endpoint."""
    headers = {"TOKEN": admin_token}
    response = client.get("/admin/transactions/export.csv", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]
    
    # Check CSV content
    content = response.text
    assert "user_id" in content
    assert "type" in content
    assert "amount" in content

