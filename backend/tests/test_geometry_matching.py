import math
import unittest

import numpy as np

from normalize import contour_distance, normalize_contour


class TestContourGeometry(unittest.TestCase):
    def test_translation_scale_rotation_invariance(self):
        base = np.array(
            [
                [0.0, 0.0],
                [1.0, 0.5],
                [1.6, 1.0],
                [1.0, 1.8],
                [0.2, 1.4],
                [-0.4, 0.8],
            ],
            dtype=np.float32,
        )

        shifted = base + np.array([60.0, -40.0], dtype=np.float32)
        scaled = base * 2.3
        theta = math.radians(27)
        rotated = np.column_stack([
            base[:, 0] * math.cos(theta) - base[:, 1] * math.sin(theta),
            base[:, 0] * math.sin(theta) + base[:, 1] * math.cos(theta),
        ])

        self.assertLess(contour_distance(base, shifted), 0.12)
        self.assertLess(contour_distance(base, scaled), 0.12)
        self.assertLess(contour_distance(base, rotated), 0.18)

    def test_reflection_is_supported_and_consistent(self):
        base = np.array(
            [
                [0.0, 0.0],
                [0.8, 0.2],
                [1.7, 0.7],
                [1.9, 1.6],
                [1.1, 2.3],
                [0.2, 1.9],
            ],
            dtype=np.float32,
        )
        reflected = np.column_stack([base[:, 0], -base[:, 1]])
        self.assertLess(contour_distance(base, reflected), 0.08)

    def test_normalization_uses_geometric_center_not_mean(self):
        shape = np.array(
            [
                [0.0, 0.0],
                [2.0, 0.0],
                [2.5, 1.0],
                [1.8, 3.0],
                [0.2, 2.4],
                [-0.5, 0.7],
            ],
            dtype=np.float32,
        )

        norm = normalize_contour(shape)
        self.assertEqual(norm.shape, (256, 1, 2))
        self.assertAlmostEqual(float(norm[:, 0, 0].mean()), 0.0, delta=0.02)
        self.assertAlmostEqual(float(norm[:, 0, 1].mean()), 0.0, delta=0.02)


if __name__ == "__main__":
    unittest.main()
