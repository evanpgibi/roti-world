import io
import unittest

from PIL import Image

from share import generate_share_card


class TestShareCard(unittest.TestCase):
    def test_share_card_renders_without_missing_glyph_boxes(self):
        png = generate_share_card(
            best_country="Italy",
            best_iso="ITA",
            best_score=94.8,
            leaderboard=[
                {"country": "Italy", "score": 94.8},
                {"country": "Greece", "score": 82.1},
                {"country": "France", "score": 76.9},
            ],
            chapati_outline=[[0.0, 0.0], [0.5, 0.2], [0.8, 0.7], [0.1, 1.0]],
            country_outline=[[0.0, 0.0], [0.2, 0.6], [0.7, 0.8], [0.9, 0.2]],
            playful_copy="Your chapati is giving Italy.",
        )

        image = Image.open(io.BytesIO(png))
        self.assertEqual(image.size, (900, 520))
        total = sum(sum(pixel) for pixel in image.getdata())
        self.assertGreater(total, 0)


if __name__ == "__main__":
    unittest.main()
