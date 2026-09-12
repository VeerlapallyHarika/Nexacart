import sys
import os
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(__file__))

from main import app
from database import SessionLocal, Base, engine
from models.user import User
from models.order import Order
from services.auth_service import AuthService


class TestAuthAndSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.db = SessionLocal()
        # Clean up test users and orders
        self.db.query(User).filter(User.email.like("%@test.com")).delete()
        self.db.commit()

    def tearDown(self):
        self.db.query(User).filter(User.email.like("%@test.com")).delete()
        self.db.commit()
        self.db.close()

    def test_1_user_registration_success(self):
        """1. Register a new user successfully."""
        response = self.client.post("/api/auth/register", json={
            "name": "Alice Wonderland",
            "email": "alice@test.com",
            "password": "password123"
        })
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "bearer")
        self.assertEqual(data["user"]["email"], "alice@test.com")
        self.assertEqual(data["user"]["name"], "Alice Wonderland")
        self.assertNotIn("password", data["user"])
        self.assertNotIn("password_hash", data["user"])

    def test_2_duplicate_email_rejection(self):
        """2. Duplicate email registration should return 400 Bad Request."""
        # First registration
        self.client.post("/api/auth/register", json={
            "name": "Alice Wonderland",
            "email": "alice@test.com",
            "password": "password123"
        })
        # Second registration with same email
        response = self.client.post("/api/auth/register", json={
            "name": "Alice Duplicate",
            "email": "alice@test.com",
            "password": "differentpass"
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("already exists", response.json()["detail"].lower())

    def test_3_password_hashing_security(self):
        """3. Passwords must be hashed with bcrypt, never stored plaintext."""
        self.client.post("/api/auth/register", json={
            "name": "Security Test",
            "email": "security@test.com",
            "password": "mysecretpassword123"
        })
        user = self.db.query(User).filter(User.email == "security@test.com").first()
        self.assertIsNotNone(user)
        self.assertNotEqual(user.password_hash, "mysecretpassword123")
        self.assertTrue(user.password_hash.startswith("$2b$") or user.password_hash.startswith("$2a$"))
        self.assertTrue(AuthService.verify_password("mysecretpassword123", user.password_hash))
        self.assertFalse(AuthService.verify_password("wrongpassword", user.password_hash))

    def test_4_successful_login(self):
        """4. Successful login returns JWT token."""
        self.client.post("/api/auth/register", json={
            "name": "Bob Builder",
            "email": "bob@test.com",
            "password": "builditright123"
        })
        response = self.client.post("/api/auth/login", json={
            "email": "bob@test.com",
            "password": "builditright123"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["user"]["email"], "bob@test.com")

    def test_5_invalid_password_rejection(self):
        """5. Invalid password login attempt should return 401 Unauthorized."""
        self.client.post("/api/auth/register", json={
            "name": "Bob Builder",
            "email": "bob@test.com",
            "password": "builditright123"
        })
        response = self.client.post("/api/auth/login", json={
            "email": "bob@test.com",
            "password": "wrongpassword"
        })
        self.assertEqual(response.status_code, 401)
        self.assertIn("invalid", response.json()["detail"].lower())

    def test_6_invalid_email_rejection(self):
        """6. Non-existent email login attempt should return 401 Unauthorized."""
        response = self.client.post("/api/auth/login", json={
            "email": "nonexistent@test.com",
            "password": "somepassword"
        })
        self.assertEqual(response.status_code, 401)

    def test_7_get_me_authenticated(self):
        """7. GET /api/auth/me returns current user info when token provided."""
        reg = self.client.post("/api/auth/register", json={
            "name": "Carol Danvers",
            "email": "carol@test.com",
            "password": "higherfurtherfaster"
        }).json()
        token = reg["access_token"]

        response = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["email"], "carol@test.com")
        self.assertEqual(data["name"], "Carol Danvers")
        self.assertNotIn("password", data)

    def test_8_get_me_unauthenticated(self):
        """8. GET /api/auth/me returns 401 Unauthorized without token."""
        response = self.client.get("/api/auth/me")
        self.assertEqual(response.status_code, 401)

    def test_9_protected_orders_without_token(self):
        """9. Orders endpoint without session_id and without token returns 401."""
        response = self.client.get("/api/orders")
        self.assertEqual(response.status_code, 401)

    def test_10_protected_orders_with_valid_token(self):
        """10. Authenticated user can view their orders."""
        reg = self.client.post("/api/auth/register", json={
            "name": "David Miller",
            "email": "david@test.com",
            "password": "password123"
        }).json()
        token = reg["access_token"]

        response = self.client.get("/api/orders", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("orders", data)
        self.assertIn("count", data)

    def test_11_user_authorization_data_isolation(self):
        """11. User A cannot access User B's order."""
        # Create User A
        reg_a = self.client.post("/api/auth/register", json={
            "name": "User A",
            "email": "usera@test.com",
            "password": "password123"
        }).json()
        user_a_id = reg_a["user"]["id"]

        # Create User B
        reg_b = self.client.post("/api/auth/register", json={
            "name": "User B",
            "email": "userb@test.com",
            "password": "password123"
        }).json()
        token_b = reg_b["access_token"]

        # Create an order belonging to User A directly in DB
        order_a = Order(
            id=Order.generate_id(),
            session_id="session_usera_test",
            user_id=user_a_id,
            cart_id="cart_dummy_a",
            payment_id="pay_dummy_a",
            total_amount=9999.0,
            status="CONFIRMED"
        )
        self.db.add(order_a)
        self.db.commit()

        # User B attempts to access User A's order by ID
        response = self.client.get(
            f"/api/orders/{order_a.id}",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("permission", response.json()["detail"].lower())

        # Unauthenticated user attempts to access User A's order by session
        response_anon = self.client.get(f"/api/orders?session_id=session_usera_test")
        self.assertEqual(response_anon.status_code, 403)


if __name__ == "__main__":
    unittest.main()
