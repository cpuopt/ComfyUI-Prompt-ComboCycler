import unittest

from prompt_matrix.matrix import (
    choose_count,
    mixed_radix_indices,
    permutation_count,
    select_from_source,
    shuffle_no_repeat_index,
    source_from_text,
    stable_random_index,
    unrank_combination,
    unrank_permutation,
)
from prompt_matrix.nodes import PromptMatrixController, PromptMatrixSource, _reset_controller_state


class MatrixMathTests(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(choose_count(5, 2), 10)
        self.assertEqual(permutation_count(5, 2), 20)
        self.assertEqual(choose_count(3, 4), 0)
        self.assertEqual(permutation_count(3, 4), 0)

    def test_unrank_combination_matches_lexicographic_order(self):
        combos = [unrank_combination(4, 2, i) for i in range(6)]
        self.assertEqual(combos, [[0, 1], [0, 2], [0, 3], [1, 2], [1, 3], [2, 3]])

    def test_unrank_permutation_matches_lexicographic_order(self):
        perms = [unrank_permutation(3, 2, i) for i in range(6)]
        self.assertEqual(perms, [[0, 1], [0, 2], [1, 0], [1, 2], [2, 0], [2, 1]])

    def test_select_from_source(self):
        source = source_from_text("a\nb\nc", "combination", 2, " + ")
        self.assertEqual(source.count, 3)
        self.assertEqual(select_from_source(source, 0), "a + b")
        self.assertEqual(select_from_source(source, 2), "b + c")

        source = source_from_text("a\nb\nc", "permutation", 2, ", ")
        self.assertEqual(source.count, 6)
        self.assertEqual(select_from_source(source, 3), "b, c")

    def test_mixed_radix(self):
        self.assertEqual(mixed_radix_indices(0, [2, 3, 4]), [0, 0, 0])
        self.assertEqual(mixed_radix_indices(1, [2, 3, 4]), [0, 0, 1])
        self.assertEqual(mixed_radix_indices(4, [2, 3, 4]), [0, 1, 0])
        self.assertEqual(mixed_radix_indices(23, [2, 3, 4]), [1, 2, 3])

    def test_random_with_repeat_is_seeded(self):
        sequence_a = [stable_random_index(100, 42, i) for i in range(10)]
        sequence_b = [stable_random_index(100, 42, i) for i in range(10)]
        self.assertEqual(sequence_a, sequence_b)

    def test_shuffle_no_repeat_cycle_has_no_duplicates(self):
        values = [shuffle_no_repeat_index(17, 42, i) for i in range(17)]
        self.assertEqual(len(set(values)), 17)
        self.assertTrue(all(0 <= value < 17 for value in values))

    def test_empty_or_disabled_source_counts_as_one(self):
        self.assertEqual(source_from_text("", "combination", 3, ", ").count, 1)
        self.assertEqual(source_from_text("a\nb", "combination", 1, ", ", enabled=False).count, 1)

    def test_choose_k_clamps_to_available_items(self):
        source = source_from_text("a\nb", "permutation", 9, ", ")
        self.assertEqual(source.count, 2)
        self.assertEqual(select_from_source(source, 0), "a, b")


class NodeBehaviorTests(unittest.TestCase):
    def setUp(self):
        _reset_controller_state()

    def test_source_node_outputs_payload_and_count(self):
        result = PromptMatrixSource().build("a\nb\nc", "combination", 2, " + ", True)
        payload, count = result["result"]
        self.assertEqual(count, 3)
        self.assertEqual(payload["items"], ["a", "b", "c"])
        self.assertEqual(result["ui"]["status"][0], "3 possible")

    def test_controller_sequential_steps_and_composes(self):
        source_a = PromptMatrixSource().build("a\nb", "combination", 1, ", ", True)["result"][0]
        source_b = PromptMatrixSource().build("x\ny", "combination", 1, ", ", True)["result"][0]
        controller = PromptMatrixController()

        first = controller.compose("sequential", 0, " | ", unique_id="node-a", source_1=source_a, source_2=source_b)
        second = controller.compose("sequential", 0, " | ", unique_id="node-a", source_1=source_a, source_2=source_b)
        third = controller.compose("sequential", 0, " | ", unique_id="node-a", source_1=source_a, source_2=source_b)

        self.assertEqual(first["result"], ("a | x", 1, 4))
        self.assertEqual(second["result"], ("a | y", 2, 4))
        self.assertEqual(third["result"], ("b | x", 3, 4))

    def test_controller_random_with_repeat_is_resettable(self):
        source = PromptMatrixSource().build("a\nb\nc\nd", "combination", 1, ", ", True)["result"][0]
        controller = PromptMatrixController()

        sequence_a = [
            controller.compose("random_with_repeat", 123, ", ", unique_id="node-r", source_1=source)["result"]
            for _ in range(5)
        ]
        _reset_controller_state("node-r")
        sequence_b = [
            controller.compose("random_with_repeat", 123, ", ", unique_id="node-r", source_1=source)["result"]
            for _ in range(5)
        ]

        self.assertEqual(sequence_a, sequence_b)


if __name__ == "__main__":
    unittest.main()
