import os
import tempfile
import unittest

from auth import hash_password, verify_password
from database import (
    create_session,
    create_user,
    get_all_leads,
    get_all_sessions,
    get_session_leads,
    init_db,
    reset_engine_cache,
    save_leads,
)


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_leads.db")
        os.environ.pop("DATABASE_URL", None)
        os.environ["LEADS_DB_PATH"] = self.db_path
        reset_engine_cache()
        init_db()

    def tearDown(self):
        reset_engine_cache()
        os.environ.pop("LEADS_DB_PATH", None)
        self.temp_dir.cleanup()

    def test_password_hash_round_trip(self):
        password = "correct horse battery staple"
        password_hash = hash_password(password)

        self.assertTrue(verify_password(password, password_hash))
        self.assertFalse(verify_password("wrong-password", password_hash))

    def test_round_trip_save_and_fetch_for_signed_in_user(self):
        user = create_user("alice", hash_password("password123"))
        self.assertIsNotNone(user)

        session_id = create_session("photographers", "Bangalore", user["id"])
        saved = save_leads(
            [
                {
                    "name": "Acme Photos",
                    "sector": "photographers",
                    "city": "Bangalore",
                    "instagram_url": "https://www.instagram.com/acmephotos/",
                    "website": "https://acmephotos.in",
                    "phone": "+919999999999",
                    "email": "hello@acmephotos.in",
                    "bio": "Wedding photography studio",
                    "source_url": "https://acmephotos.in",
                    "source": "duckduckgo",
                    "snippet": "Wedding photography studio in Bangalore",
                    "digital_presence_score": 3,
                    "digital_presence_notes": "Own website found",
                    "lead_quality_score": 8.5,
                    "all_phones": ["+919999999999"],
                    "all_emails": ["hello@acmephotos.in"],
                    "all_instagram_urls": ["https://www.instagram.com/acmephotos/"],
                }
            ],
            session_id,
        )

        rows = get_session_leads(session_id, user["id"])

        self.assertEqual(saved, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Acme Photos")
        self.assertEqual(rows[0]["digital_presence_notes"], "Own website found")

    def test_users_only_see_their_own_sessions_and_leads(self):
        alice = create_user("alice", hash_password("password123"))
        bob = create_user("bob", hash_password("password456"))
        self.assertIsNotNone(alice)
        self.assertIsNotNone(bob)

        alice_session = create_session("photographers", "Bangalore", alice["id"])
        bob_session = create_session("makeup artists", "Mumbai", bob["id"])

        save_leads(
            [
                {
                    "name": "Alice Lead",
                    "sector": "photographers",
                    "city": "Bangalore",
                    "source_url": "https://example.com/alice",
                    "digital_presence_score": 7,
                    "lead_quality_score": 4.0,
                }
            ],
            alice_session,
        )
        save_leads(
            [
                {
                    "name": "Bob Lead",
                    "sector": "makeup artists",
                    "city": "Mumbai",
                    "source_url": "https://example.com/bob",
                    "digital_presence_score": 5,
                    "lead_quality_score": 6.0,
                }
            ],
            bob_session,
        )

        alice_sessions = get_all_sessions(alice["id"])
        alice_leads = get_all_leads(user_id=alice["id"])
        bob_leads_from_alice_view = get_session_leads(bob_session, alice["id"])

        self.assertEqual(len(alice_sessions), 1)
        self.assertEqual(alice_sessions[0]["id"], alice_session)
        self.assertEqual(len(alice_leads), 1)
        self.assertEqual(alice_leads[0]["name"], "Alice Lead")
        self.assertEqual(bob_leads_from_alice_view, [])


if __name__ == "__main__":
    unittest.main()
