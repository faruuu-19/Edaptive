"""The arithmetic of every calculation is done by sympy; the shape rules around it are unchanged."""
import random
import unittest
from unittest import mock

import question_generator as qg


def python_reference(node):
    """An independent oracle written with plain Python operators, used only here."""
    if isinstance(node, int):
        return node
    left, right = (python_reference(x) for x in node['operands'])
    return {'add': left + right, 'subtract': left - right, 'multiply': left * right}[node['operation']]


def random_tree(rng, depth=0):
    if depth >= 3 or rng.random() < 0.3:
        return rng.randint(0, 999)
    return {'operation': rng.choice(['add', 'subtract', 'multiply']),
            'operands': [random_tree(rng, depth + 1), random_tree(rng, depth + 1)]}


class SympyEvaluatorTests(unittest.TestCase):
    def test_values_match_an_independent_python_oracle_on_random_expressions(self):
        rng = random.Random(20261008)
        for _ in range(500):
            tree = random_tree(rng)
            value, inputs, operations = qg._evaluate_expression(tree)
            self.assertEqual(value, python_reference(tree), tree)
            self.assertIs(type(value), int)  # callers serialise and hash these; a sympy Integer would break json.dumps

    def test_the_arithmetic_really_goes_through_sympy(self):
        with mock.patch.object(qg.sympy, 'Add', side_effect=RuntimeError('sympy was used')):
            with self.assertRaisesRegex(RuntimeError, 'sympy was used'):
                qg._evaluate_expression({'operation': 'add', 'operands': [2, 3]})
        with mock.patch.object(qg.sympy, 'Mul', side_effect=RuntimeError('sympy was used')):
            with self.assertRaisesRegex(RuntimeError, 'sympy was used'):
                qg._evaluate_expression({'operation': 'multiply', 'operands': [2, 3]})

    def test_subtraction_can_go_negative_and_refs_are_still_resolved(self):
        self.assertEqual(qg._evaluate_expression({'operation': 'subtract', 'operands': [3, 10]})[0], -7)
        ref = {'operation': 'add', 'operands': [{'ref': 'a'}, 5]}
        self.assertEqual(qg._evaluate_expression(ref, {'a': 10})[0], 15)

    def test_big_numbers_stay_exact_python_ints(self):
        big = 10 ** 30
        value = qg._evaluate_expression({'operation': 'multiply', 'operands': [big, big]})[0]
        self.assertEqual(value, 10 ** 60)
        self.assertIs(type(value), int)

    def test_negative_control_the_shape_rules_around_the_arithmetic_are_unchanged(self):
        for bad in ({'operation': 'power', 'operands': [4, 2]}, {'operation': 'add', 'operands': [1]},
                    {'operation': 'add', 'operands': [1, 2, 3]}, 2.5, {'ref': 'nope'}, 'x'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                qg._evaluate_expression(bad)

    def test_inputs_and_operation_counts_are_still_reported(self):
        tree = {'operation': 'add', 'operands': [{'operation': 'add', 'operands': [370, 200]}, 50]}
        self.assertEqual(qg._evaluate_expression(tree), (620, [370, 200, 50], 2))


if __name__ == '__main__':
    unittest.main()
