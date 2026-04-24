import unittest
from unittest.mock import patch

from extractor import extract_lead
from scoring import (
    compute_digital_presence_notes,
    compute_digital_presence_score,
    compute_lead_quality_score,
)


class ScoringTests(unittest.TestCase):
    def test_social_only_presence_scores_as_weak(self):
        lead = {
            "name": "Pixel Weddings",
            "instagram_url": "https://www.instagram.com/pixelweddings/",
            "website": "",
            "phone": "+919999999999",
            "email": "",
            "bio": "Wedding photographer in Bangalore.",
            "snippet": "DM for bookings",
            "source_url": "https://www.instagram.com/pixelweddings/",
        }

        score = compute_digital_presence_score(lead)
        notes = compute_digital_presence_notes(lead)

        self.assertGreaterEqual(score, 8)
        self.assertIn("No owned website found", notes)

    def test_professional_site_scores_as_strong(self):
        lead = {
            "name": "Northlight Studio",
            "instagram_url": "https://www.instagram.com/northlightstudio/",
            "website": "https://northlightstudio.in",
            "phone": "+918888888888",
            "email": "hello@northlightstudio.in",
            "bio": (
                "Northlight Studio is a Bangalore wedding photography team with "
                "portfolio, pricing, testimonials, booking, and contact details."
            ),
            "snippet": "Portfolio and packages available online.",
            "source_url": "https://northlightstudio.in",
            "all_phones": ["+918888888888", "+917777777777"],
            "all_emails": ["hello@northlightstudio.in", "bookings@northlightstudio.in"],
        }

        score = compute_digital_presence_score(lead)
        quality = compute_lead_quality_score(lead)

        self.assertLessEqual(score, 3)
        self.assertGreaterEqual(quality, 8.5)


class ExtractorTests(unittest.TestCase):
    @patch("extractor.rate_limit", return_value=None)
    @patch(
        "extractor._fetch_html",
        return_value="""
        <html>
            <head>
                <title>Acme Photography | Justdial</title>
                <meta name="description" content="Photography services in Bangalore" />
            </head>
            <body>
                <a href="https://acmephotos.in">Website</a>
                <a href="https://www.instagram.com/acmephotos/">Instagram</a>
                <a href="mailto:hello@acmephotos.in">Email</a>
            </body>
        </html>
        """,
    )
    def test_directory_source_prefers_extracted_official_site(self, *_mocks):
        lead = extract_lead(
            {
                "url": "https://www.justdial.com/Bangalore/Acme-Photography",
                "title": "Acme Photography",
                "snippet": "Call now for wedding photography",
                "source": "duckduckgo",
            },
            sector="wedding photographers",
            city="Bangalore",
        )

        self.assertEqual(lead["website"], "https://acmephotos.in")
        self.assertEqual(lead["email"], "hello@acmephotos.in")


if __name__ == "__main__":
    unittest.main()
