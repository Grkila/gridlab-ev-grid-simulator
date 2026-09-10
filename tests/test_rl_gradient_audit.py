"""Independent numerical likelihood-gradient checks for the practical RL update."""
import unittest

import numpy as np

from mvgrid.novi_sad.playground.rl import BinaryPolicy, FEATURES


class RLGradientAuditTests(unittest.TestCase):
    def policy(self, bias=0.):
        p = BinaryPolicy(4)
        p.weights['b2'][0] = bias
        return p

    def check_gradient(self, p, xs, actions, rewards, gamma):
        trajectory = [dict(x=x, actions=np.asarray(a), probabilities=p.probabilities(x), reward=r)
                      for x, a, r in zip(xs, actions, rewards)]
        returns = np.zeros(len(rewards))
        for t in range(len(rewards) - 1, -1, -1):
            returns[t] = rewards[t] + (gamma * returns[t + 1] if t + 1 < len(rewards) else 0.)
        # All cases keep the heuristic scale at 1 and norm below the clipping
        # threshold, isolating the episode-start likelihood-ratio gradient.
        self.assertLess(np.std(returns), 1.)

        def surrogate():
            result = 0.
            for t, item in enumerate(trajectory):
                probability = p.probabilities(item['x'])
                score = np.where(item['actions'], np.log(probability), np.log1p(-probability))
                result += gamma**t * returns[t] * score.sum()
            return result / len(trajectory)

        numerical = {}
        delta = 1e-5
        for key, value in p.weights.items():
            numerical[key] = np.zeros_like(value)
            for index in np.ndindex(value.shape):
                original = value[index]
                value[index] = original + delta
                above = surrogate()
                value[index] = original - delta
                below = surrogate()
                value[index] = original
                numerical[key][index] = (above - below) / (2 * delta)
        before = {key: value.copy() for key, value in p.weights.items()}
        norm = p.update(trajectory, learning_rate=.01, gamma=gamma)
        self.assertLess(norm, 10.)
        for key in before:
            np.testing.assert_allclose((p.weights[key] - before[key]) / .01,
                                       numerical[key], atol=2e-7, rtol=2e-5, err_msg=key)

    def test_multistep_discounted_joint_score_finite_difference(self):
        rng = np.random.default_rng(9)
        self.check_gradient(self.policy(), [rng.normal(0, .2, (2, len(FEATURES))) for _ in range(3)],
                            [[1, 0], [0, 1], [1, 1]], [.1, -.2, .3], .6)

    def test_empty_initial_slot_still_counts_in_discount(self):
        self.check_gradient(self.policy(), [np.empty((0, len(FEATURES))), np.zeros((1, len(FEATURES)))],
                            [[], [1]], [0., 1.], .1)

    def test_saturated_logits_have_zero_numerical_score_derivative(self):
        for bias, action in ((30., 0), (-30., 1)):
            with self.subTest(bias=bias):
                self.check_gradient(self.policy(bias), [np.ones((1, len(FEATURES)))], [[action]], [1.], .99)

    def test_discount_one_retains_undiscounted_objective(self):
        self.check_gradient(self.policy(), [np.zeros((1, len(FEATURES)))] * 2,
                            [[1], [0]], [.2, .4], 1.)

    def test_inference_roundtrip_unchanged_for_saturated_weights(self):
        p = self.policy(30.)
        loaded = BinaryPolicy.from_dict(p.to_dict())
        x = np.zeros((2, len(FEATURES)))
        np.testing.assert_array_equal(p.probabilities(x), loaded.probabilities(x))
        np.testing.assert_array_equal(loaded.predict(x)[0], [1, 1])


if __name__ == '__main__':
    unittest.main()
