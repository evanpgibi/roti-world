import math
import pickle
import unittest
from pathlib import Path

import numpy as np

from config import load_settings
from matcher import match_chapati


def make_square():
    return np.array([
        [1.0, 1.0],
        [1.0, -1.0],
        [-1.0, -1.0],
        [-1.0, 1.0],
    ], dtype=np.float32)


def make_star():
    pts = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5.0
        radius = 1.0 if i % 2 == 0 else 0.42
        pts.append([math.cos(angle) * radius, math.sin(angle) * radius])
    return np.array(pts, dtype=np.float32)


def make_blob(seed):
    rng = np.random.default_rng(seed)
    angles = np.linspace(0, 2 * math.pi, 32, endpoint=False)
    radii = 0.65 + 0.35 * rng.random(32)
    pts = np.column_stack([np.cos(angles) * radii, np.sin(angles) * radii])
    pts += rng.normal(0.0, 0.1, size=pts.shape)
    return pts


class TestMatchingRegression(unittest.TestCase):
    def setUp(self):
        self.settings = load_settings()
        with open(Path(__file__).resolve().parents[1] / "cache" / "country_cache.pkl", "rb") as f:
            payload = pickle.load(f)
        self.countries = payload["countries"]

    def test_country_matches_itself(self):
        italy = next(c for c in self.countries if c["name"] == "Italy")
        res = match_chapati(italy["contour_points"], self.settings)
        self.assertEqual(res.best_match.country, "Italy")
        self.assertGreater(res.best_match.score, 80.0)

    def test_square_and_star_are_not_false_positives(self):
        shapes = {"square": make_square(), "star": make_star()}
        for name, shape in shapes.items():
            res = match_chapati(shape.tolist(), self.settings)
            self.assertLess(res.best_match.score, 50.0, f"{name} matched too strongly: {res.best_match}")

    def test_random_blobs_do_not_all_collapse_to_same_country(self):
        winners = []
        for seed in range(6):
            res = match_chapati(make_blob(seed).tolist(), self.settings)
            winners.append(res.best_match.country)
        self.assertGreater(len(set(winners)), 1)


if __name__ == "__main__":
    unittest.main()
