"""The calculator: exact arithmetic for question answers. No model, no floats, two engines agree on every result."""
import unittest
from decimal import Decimal
from fractions import Fraction

import calculator as calc
from calculator import CalculatorError


class WholeNumberTests(unittest.TestCase):
    def test_add_subtract_multiply(self):
        self.assertEqual(calc.add(3134, 2493).value, 5627)
        self.assertEqual(calc.subtract(480, 130).value, 350)
        self.assertEqual(calc.multiply(12, 7).value, 84)

    def test_every_result_records_its_method_and_two_agreeing_engines(self):
        result = calc.add(2, 3)
        self.assertEqual(result.engines, ("python", "sympy"))
        self.assertIn("add", result.method)
        self.assertEqual(result.display, "5")

    def test_a_float_is_never_accepted(self):
        for call in (lambda: calc.add(0.1, 0.2), lambda: calc.multiply(1.5, 2), lambda: calc.parse_decimal(0.5)):
            with self.assertRaises(CalculatorError):
                call()

    def test_booleans_are_not_numbers(self):
        with self.assertRaises(CalculatorError):
            calc.add(True, 1)

    def test_a_negative_whole_number_result_is_reported_not_hidden(self):
        self.assertEqual(calc.subtract(3, 5).value, -2)


class DivisionTests(unittest.TestCase):
    def test_divmod_gives_quotient_and_remainder(self):
        result = calc.divide_with_remainder(17, 5)
        self.assertEqual((result.value["quotient"], result.value["remainder"]), (3, 2))
        self.assertEqual(result.display, "3 remainder 2")
        self.assertEqual(result.engines, ("python", "sympy"))

    def test_exact_division_has_remainder_zero(self):
        result = calc.divide_with_remainder(42, 6)
        self.assertEqual((result.value["quotient"], result.value["remainder"]), (7, 0))
        self.assertEqual(result.display, "7")

    def test_quotient_times_divisor_plus_remainder_gives_the_dividend_back(self):
        for dividend, divisor in ((17, 5), (42, 6), (0, 9), (99, 100), (1000, 7)):
            r = calc.divide_with_remainder(dividend, divisor).value
            self.assertEqual(r["quotient"] * divisor + r["remainder"], dividend)
            self.assertTrue(0 <= r["remainder"] < divisor)

    def test_divide_exact_refuses_a_remainder(self):
        self.assertEqual(calc.divide_exact(42, 6).value, 7)
        with self.assertRaises(CalculatorError):
            calc.divide_exact(17, 5)

    def test_zero_divisor_and_negative_inputs_are_refused(self):
        for args in ((5, 0), (-5, 2), (5, -2)):
            with self.assertRaises(CalculatorError):
                calc.divide_with_remainder(*args)


class FractionTests(unittest.TestCase):
    def test_parse_fraction_forms(self):
        self.assertEqual(calc.parse_fraction("3/4"), Fraction(3, 4))
        self.assertEqual(calc.parse_fraction("1 3/4"), Fraction(7, 4))
        self.assertEqual(calc.parse_fraction(5), Fraction(5))
        for bad in ("3/0", "x/2", "1/2/3", "", "0.5"):
            with self.assertRaises(CalculatorError):
                calc.parse_fraction(bad)

    def test_fraction_arithmetic_is_exact_and_simplified(self):
        self.assertEqual(calc.fraction_op("add", "1/2", "1/3").value, Fraction(5, 6))
        self.assertEqual(calc.fraction_op("add", "1/4", "3/4").value, Fraction(1))
        self.assertEqual(calc.fraction_op("subtract", "5/6", "1/3").value, Fraction(1, 2))
        self.assertEqual(calc.fraction_op("multiply", "2/3", "3/4").value, Fraction(1, 2))
        self.assertEqual(calc.fraction_op("divide", "1/2", "1/4").value, Fraction(2))

    def test_fraction_results_agree_with_sympy(self):
        self.assertEqual(calc.fraction_op("add", "7/9", "5/6").engines, ("python", "sympy"))

    def test_display_improper_and_mixed(self):
        value = calc.fraction_op("add", "3/4", "5/8").value  # 11/8
        self.assertEqual(calc.format_fraction(value), "11/8")
        self.assertEqual(calc.format_mixed(value), "1 3/8")
        self.assertEqual(calc.format_mixed(Fraction(3)), "3")
        self.assertEqual(calc.format_mixed(Fraction(1, 2)), "1/2")

    def test_fraction_answer_forms_include_improper_mixed_and_unsimplified_free(self):
        forms = calc.fraction_answer_forms(Fraction(11, 8))
        self.assertIn("11/8", forms)
        self.assertIn("1 3/8", forms)
        self.assertNotIn("22/16", forms)

    def test_division_by_zero_fraction_is_refused(self):
        with self.assertRaises(CalculatorError):
            calc.fraction_op("divide", "1/2", "0")


class DecimalAndMoneyTests(unittest.TestCase):
    def test_decimals_do_not_suffer_float_error(self):
        self.assertEqual(calc.decimal_op("add", "0.1", "0.2").value, Decimal("0.3"))
        self.assertEqual(calc.decimal_op("subtract", "5.00", "1.25").value, Decimal("3.75"))
        self.assertEqual(calc.decimal_op("multiply", "1.5", "0.4").value, Decimal("0.6"))

    def test_decimal_results_agree_with_sympy(self):
        self.assertEqual(calc.decimal_op("add", "12.375", "0.625").engines, ("python", "sympy"))

    def test_decimal_display_drops_trailing_zeros_but_keeps_a_point_free_integer(self):
        self.assertEqual(calc.format_decimal(Decimal("3.50")), "3.5")
        self.assertEqual(calc.format_decimal(Decimal("4.00")), "4")

    def test_money_is_two_places_and_formatted_with_a_dollar_sign(self):
        total = calc.money_op("add", "$12.50", "3.75")
        self.assertEqual(total.value, Decimal("16.25"))
        self.assertEqual(total.display, "$16.25")
        self.assertEqual(calc.money_op("subtract", "$20", "$4.55").display, "$15.45")

    def test_money_with_more_than_two_places_is_refused(self):
        with self.assertRaises(CalculatorError):
            calc.parse_money("1.005")

    def test_money_answer_forms(self):
        forms = calc.money_answer_forms(Decimal("16.50"))
        self.assertEqual(forms[:3], ["$16.50", "16.50", "16.5"])

    def test_money_multiplied_by_a_whole_number(self):
        self.assertEqual(calc.money_op("multiply", "$2.35", "4").display, "$9.40")


class RoundingTests(unittest.TestCase):
    def test_whole_number_rounding_is_half_up(self):
        self.assertEqual(calc.round_to_place(3941, 1000).value, 4000)
        self.assertEqual(calc.round_to_place(3941, 100).value, 3900)
        self.assertEqual(calc.round_to_place(74621, 10000).value, 70000)
        self.assertEqual(calc.round_to_place(681904, 100000).value, 700000)
        self.assertEqual(calc.round_to_place(35, 10).value, 40)  # the half goes up
        self.assertEqual(calc.round_to_place(34, 10).value, 30)

    def test_place_must_be_a_power_of_ten(self):
        for place in (0, 7, 25, -10):
            with self.assertRaises(CalculatorError):
                calc.round_to_place(100, place)

    def test_decimal_rounding(self):
        self.assertEqual(calc.round_decimal("3.456", 2).value, Decimal("3.46"))
        self.assertEqual(calc.round_decimal("3.455", 2).value, Decimal("3.46"))
        self.assertEqual(calc.round_decimal("2.5", 0).value, Decimal("3"))


class ComparisonTests(unittest.TestCase):
    def test_symbols(self):
        self.assertEqual(calc.compare(3, 5).value, "<")
        self.assertEqual(calc.compare(7, 5).value, ">")
        self.assertEqual(calc.compare(5, 5).value, "=")

    def test_mixed_kinds_compare_exactly(self):
        self.assertEqual(calc.compare("1/2", "0.5").value, "=")
        self.assertEqual(calc.compare("3/4", "2/3").value, ">")
        self.assertEqual(calc.compare("0.30", "0.3").value, "=")
        self.assertEqual(calc.compare("$4.10", "$4.01").value, ">")

    def test_comparison_agrees_with_sympy(self):
        self.assertEqual(calc.compare("5/8", "3/5").engines, ("python", "sympy"))

    def test_symbol_answer_forms(self):
        self.assertEqual(calc.symbol_answer_forms("<"), ["<", "less than"])
        self.assertEqual(calc.symbol_answer_forms(">"), [">", "greater than", "more than"])
        self.assertEqual(calc.symbol_answer_forms("="), ["=", "equal to", "equals", "the same"])


class PlaceValueTests(unittest.TestCase):
    def test_digit_and_value_at_a_place(self):
        self.assertEqual(calc.digit_at(3941, 1000).value, 3)
        self.assertEqual(calc.digit_value(3941, 1000).value, 3000)
        self.assertEqual(calc.digit_value(3941, 10).value, 40)
        self.assertEqual(calc.digit_value(3941, 100000).value, 0)

    def test_expanded_form(self):
        self.assertEqual(calc.expanded_form(40762).value, [40000, 700, 60, 2])
        self.assertEqual(calc.expanded_form(0).value, [0])

    def test_place_names(self):
        self.assertEqual(calc.place_name(1), "ones")
        self.assertEqual(calc.place_name(10000), "ten thousands")
        self.assertEqual(calc.place_value_of_name("hundreds"), 100)
        with self.assertRaises(CalculatorError):
            calc.place_name(70)


class VerifyAnswerTests(unittest.TestCase):
    def test_a_claim_that_matches_is_recorded_with_method_and_value(self):
        record = calc.verify_claim(calc.add(2, 3), 5)
        self.assertTrue(record["matches"])
        self.assertEqual(record["computed"], "5")
        self.assertIn("add", record["method"])
        self.assertEqual(record["engines"], ["python", "sympy"])

    def test_a_wrong_claim_is_recorded_as_a_mismatch_never_accepted(self):
        record = calc.verify_claim(calc.add(2, 3), 6)
        self.assertFalse(record["matches"])
        self.assertEqual(record["computed"], "5")

    def test_claims_in_other_shapes_are_normalised_before_comparing(self):
        self.assertTrue(calc.verify_claim(calc.fraction_op("add", "1/4", "1/4"), "1/2")["matches"])
        self.assertTrue(calc.verify_claim(calc.fraction_op("add", "1/4", "1/4"), "2/4")["matches"])
        self.assertTrue(calc.verify_claim(calc.money_op("add", "1", "1.5"), "$2.50")["matches"])
        self.assertTrue(calc.verify_claim(calc.decimal_op("add", "1.0", "1.5"), "2.5")["matches"])
        self.assertTrue(calc.verify_claim(calc.compare(1, 2), "less than")["matches"])
        self.assertTrue(calc.verify_claim(calc.divide_with_remainder(17, 5), "3 r 2")["matches"])
        self.assertTrue(calc.verify_claim(calc.divide_with_remainder(17, 5), "3 remainder 2")["matches"])
        self.assertFalse(calc.verify_claim(calc.divide_with_remainder(17, 5), "3")["matches"])
        self.assertFalse(calc.verify_claim(calc.divide_with_remainder(17, 5), "3 r 4")["matches"])   # the remainder is checked too
        self.assertFalse(calc.verify_claim(calc.divide_with_remainder(17, 5), "4 remainder 2")["matches"])
        self.assertFalse(calc.verify_claim(calc.add(2, 3), "five")["matches"])  # words are not parsed as claims


if __name__ == "__main__":
    unittest.main()
