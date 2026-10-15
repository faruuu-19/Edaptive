"""Regression checks for factual values in natural spoken rewrites."""
import unittest
from script_agent.checks import check_rewrite, number_values


def segment(source):
    return {'type':'worked_example','phase':'main','content':source,'metaphor':'detectives','rewrite':True}


class RewriteFactTests(unittest.TestCase):
    def test_swapped_area_and_perimeter_are_rejected(self):
        source='The rectangle is 4 units wide and 7 units long. Its perimeter is 22 units. Its area is 28 square units.'
        changed='You see a rectangle 4 units wide and 7 units long. Its perimeter is 28 units. Its area is 22 square units.'
        self.assertIn('rewrite_changed_quantity',check_rewrite(segment(source),changed,4))

    def test_swapped_width_and_length_are_rejected(self):
        source='The rectangle is 4 units wide and 7 units long.'
        changed='You see a rectangle 7 units wide and 4 units long.'
        self.assertIn('rewrite_changed_quantity',check_rewrite(segment(source),changed,4))

    def test_spoken_one_in_equation_is_valid(self):
        self.assertEqual([],check_rewrite(segment('9 plus 1 equals 10.'),'You can see nine plus one equals ten.',4))

    def test_numeric_one_cannot_be_dropped(self):
        self.assertIn('rewrite_dropped_number',check_rewrite(segment('There is one empty spot.'),'You see an empty spot.',4))

    def test_a_changed_hundreds_value_is_not_hidden_by_number_words(self):
        self.assertEqual({'124'},number_values('one hundred and twenty-four'))
        self.assertEqual({'125'},number_values('one hundred and twenty-five'))

    def test_selection_one_can_still_be_rephrased_as_a(self):
        self.assertEqual(number_values('Pick one side. 3 plus 4 equals 7.'),number_values('Pick a side. 3 plus 4 equals 7.'))
    def test_decimal_operation_cannot_be_changed(self):
        source='1.5 plus 0.5 equals 2.'
        self.assertIn('rewrite_changed_equation',check_rewrite(segment(source),'You see 1.5 minus 0.5 equals 2.',4))

    def test_signed_operation_cannot_be_changed(self):
        source='3 plus negative 2 equals 1.'
        self.assertIn('rewrite_changed_equation',check_rewrite(segment(source),'You see 3 minus negative 2 equals 1.',4))
    def test_factor_pairs_cannot_be_rearranged_using_the_same_values(self):
        source='The rectangles have area 24. They are 1 by 24, 2 by 12, 3 by 8 and 4 by 6.'
        changed='You see rectangles with area 24. They are 1 by 12, 2 by 24, 3 by 8 and 4 by 6.'
        self.assertIn('rewrite_changed_pairing',check_rewrite(segment(source),changed,4))

    def test_reversing_a_rectangle_pair_is_equivalent(self):
        source='The rectangle is 3 by 9.'
        self.assertNotIn('rewrite_changed_pairing',check_rewrite(segment(source),'You see a rectangle 9 by 3.',4))

    def test_row_counts_cannot_be_swapped_with_square_counts(self):
        source='There are 9 rows of 3 squares.'
        self.assertIn('rewrite_changed_quantity',check_rewrite(segment(source),'You see 3 rows of 9 squares.',4))
        self.assertIn('rewrite_changed_quantity',check_rewrite(segment(source),'You see 3 rows of 3 squares. You can think about 9.',4))

    def test_place_value_shorthand_can_name_its_ones(self):
        source='Say 2 tens 8 is 28.'
        self.assertNotIn('rewrite_changed_quantity',check_rewrite(segment(source),'You can say 2 tens and 8 ones make 28.',4))

    def test_unchanged_value_relationships_can_be_rephrased(self):
        source='The rectangle is 4 units wide and 7 units long. Its perimeter is 22 units. Its area is 28 square units.'
        spoken='You have a rectangle 4 units wide and 7 units long. Your perimeter is 22 units. Your area is 28 square units.'
        self.assertNotIn('rewrite_changed_quantity',check_rewrite(segment(source),spoken,4))

if __name__=='__main__':unittest.main()
