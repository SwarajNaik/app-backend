"""
Manual smoke test for role-change flow.

This test simulates the role-change workflow and can be run manually
or as part of the test suite to verify the role-change functionality.

Usage:
    pytest tests/test_role_change_smoke.py -v
    OR
    python -m pytest tests/test_role_change_smoke.py::test_role_change_flow -v -s
"""

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
from controllers.admin_controller import change_user_role
import base64
import os as os_module

# Setup the database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_role_smoke.db"

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
def setup_role_change_test_data(db):
    """Setup test data for role-change smoke test."""
    # Create admin user
    admin = UserDB(
        unique_id="smoke_admin_1",
        first_name="Smoke",
        last_name="Admin",
        email="smoke_admin@test.com",
        phone_number="9999999999",
        role=Role.ADMIN,
        credits=1000,
    )
    db.add(admin)
    
    # Create regular user to be promoted
    regular_user = UserDB(
        unique_id="smoke_user_1",
        first_name="Smoke",
        last_name="User",
        email="smoke_user@test.com",
        phone_number="8888888888",
        role=Role.USER,
        credits=100,
    )
    db.add(regular_user)
    
    # Create sales user to be demoted
    sales_user = UserDB(
        unique_id="smoke_sales_1",
        first_name="Smoke",
        last_name="Sales",
        email="smoke_sales@test.com",
        phone_number="7777777777",
        role=Role.SALES,
        credits=200,
    )
    db.add(sales_user)
    
    db.commit()
    db.refresh(admin)
    db.refresh(regular_user)
    db.refresh(sales_user)
    
    return {
        "admin": admin,
        "regular_user": regular_user,
        "sales_user": sales_user,
    }


@pytest.fixture(scope="module")
def admin_token():
    """Generate admin token for testing."""
    admin_password = os_module.getenv('ADMIN_PASSWORD', 'test_admin_password')
    return base64.b64encode(admin_password.encode()).decode()


def test_role_change_flow(db, setup_role_change_test_data, client, admin_token):
    """
    Manual smoke test for role-change flow.
    
    This test verifies:
    1. Admin can change user roles
    2. Role changes are persisted in database
    3. API endpoint works correctly
    4. Authorization is enforced
    """
    test_data = setup_role_change_test_data
    admin = test_data["admin"]
    regular_user = test_data["regular_user"]
    sales_user = test_data["sales_user"]
    
    headers = {"TOKEN": admin_token}
    
    # Step 1: Verify initial roles
    assert regular_user.role == Role.USER
    assert sales_user.role == Role.SALES
    
    # Step 2: Promote regular user to SALES via controller
    result = change_user_role(
        admin_id=admin.unique_id,
        target_user_id=regular_user.unique_id,
        new_role="SALES",
        db=db
    )
    assert result["message"] == "User role updated to SALES successfully"
    assert result["user"]["role"] == Role.SALES.value
    
    # Verify in database
    db.refresh(regular_user)
    assert regular_user.role == Role.SALES
    
    # Step 3: Promote sales user to ADMIN via API
    response = client.put(
        "/admin/users/role",
        json={
            "admin_id": admin.unique_id,
            "user_id": sales_user.unique_id,
            "role": "ADMIN"
        },
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["user"]["role"] == Role.ADMIN.value
    
    # Verify in database
    db.refresh(sales_user)
    assert sales_user.role == Role.ADMIN
    
    # Step 4: Demote regular user back to USER via API
    response = client.put(
        "/admin/users/role",
        json={
            "admin_id": admin.unique_id,
            "user_id": regular_user.unique_id,
            "role": "USER"
        },
        headers=headers
    )
    assert response.status_code == 200
    
    # Verify in database
    db.refresh(regular_user)
    assert regular_user.role == Role.USER
    
    # Step 5: Test authorization - non-admin cannot change roles
    response = client.put(
        "/admin/users/role",
        json={
            "admin_id": regular_user.unique_id,  # Regular user trying to change role
            "user_id": sales_user.unique_id,
            "role": "USER"
        },
        headers=headers
    )
    assert response.status_code == 403  # Forbidden
    
    # Step 6: Test invalid role
    response = client.put(
        "/admin/users/role",
        json={
            "admin_id": admin.unique_id,
            "user_id": regular_user.unique_id,
            "role": "INVALID_ROLE"
        },
        headers=headers
    )
    assert response.status_code == 400  # Bad Request
    
    # Step 7: Test non-existent user
    response = client.put(
        "/admin/users/role",
        json={
            "admin_id": admin.unique_id,
            "user_id": "non_existent_user",
            "role": "ADMIN"
        },
        headers=headers
    )
    assert response.status_code == 404  # Not Found
    
    print("\n✅ Role-change smoke test passed!")
    print("   - Admin can change user roles")
    print("   - Role changes persist in database")
    print("   - API endpoint works correctly")
    print("   - Authorization is enforced")
    print("   - Invalid inputs are handled properly")


def test_role_change_without_auth(client, setup_role_change_test_data):
    """Test that role change requires authentication."""
    test_data = setup_role_change_test_data
    
    # Try to change role without token
    response = client.put(
        "/admin/users/role",
        json={
            "admin_id": test_data["admin"].unique_id,
            "user_id": test_data["regular_user"].unique_id,
            "role": "SALES"
        }
    )
    assert response.status_code == 401  # Unauthorized


if __name__ == "__main__":
    # Allow running as script for manual testing
    pytest.main([__file__, "-v", "-s"])

