import os
import tempfile
import unittest

from database import (
    create_session,
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

    def test_round_trip_save_and_fetch(self):
        session_id = create_session("photographers", "Bangalore")
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

        rows = get_session_leads(session_id)

        self.assertEqual(saved, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Acme Photos")
        self.assertEqual(rows[0]["digital_presence_notes"], "Own website found")


if __name__ == "__main__":
    unittest.main()
