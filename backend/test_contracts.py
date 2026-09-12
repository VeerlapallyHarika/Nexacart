import sys
import os
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(__file__))

from main import app
from database import SessionLocal, Base, engine
from models.contract import CommerceContract


class TestCommerceContractValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.session_id = "test_contract_session_123"
        self.db = SessionLocal()
        self.db.query(CommerceContract).filter(CommerceContract.session_id == self.session_id).delete()
        self.db.commit()

    def tearDown(self):
        self.db.query(CommerceContract).filter(CommerceContract.session_id == self.session_id).delete()
        self.db.commit()
        self.db.close()

    def test_create_contract_battery_zero(self):
        """Test contract creation with minimum_battery_hours=0 (and battery_hours_min=0)."""
        # Test with minimum_battery_hours=0
        response = self.client.post(
            f"/api/contracts/{self.session_id}",
            json={
                "goal": "Buy budget earphones",
                "minimum_battery_hours": 0,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["minimum_battery_hours"], 0)

        # Test activation echoes back 0
        act_res = self.client.post(f"/api/contracts/{self.session_id}/activate")
        self.assertEqual(act_res.status_code, 200)
        self.assertEqual(act_res.json()["minimum_battery_hours"], 0)

    def test_create_contract_battery_hours_min_alias_zero(self):
        """Test contract creation with battery_hours_min=0."""
        response = self.client.post(
            f"/api/contracts/{self.session_id}",
            json={
                "goal": "Buy budget earphones",
                "battery_hours_min": 0,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["minimum_battery_hours"], 0)

    def test_create_contract_battery_thirty(self):
        """Test contract creation with minimum_battery_hours=30 and battery_hours_min=30."""
        # Test with minimum_battery_hours=30
        response = self.client.post(
            f"/api/contracts/{self.session_id}",
            json={
                "goal": "Buy ANC headphones",
                "minimum_battery_hours": 30,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["minimum_battery_hours"], 30)

        # Test activation echoes back 30
        act_res = self.client.post(f"/api/contracts/{self.session_id}/activate")
        self.assertEqual(act_res.status_code, 200)
        self.assertEqual(act_res.json()["minimum_battery_hours"], 30)

    def test_create_contract_battery_hours_min_alias_thirty(self):
        """Test contract creation with battery_hours_min=30."""
        response = self.client.post(
            f"/api/contracts/{self.session_id}",
            json={
                "goal": "Buy ANC headphones",
                "battery_hours_min": 30,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["minimum_battery_hours"], 30)

    def test_negative_battery_rejected(self):
        """Test that negative battery hours are rejected with 400 and clear error message."""
        # Test with minimum_battery_hours=-11
        response = self.client.post(
            f"/api/contracts/{self.session_id}",
            json={
                "goal": "Buy headphones",
                "minimum_battery_hours": -11,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Battery life must be 0 or greater", response.text)

        # Test with battery_hours_min=-5
        response2 = self.client.post(
            f"/api/contracts/{self.session_id}",
            json={
                "goal": "Buy headphones",
                "battery_hours_min": -5,
            },
        )
        self.assertEqual(response2.status_code, 400)
        self.assertIn("Battery life must be 0 or greater", response2.text)


if __name__ == "__main__":
    unittest.main()
