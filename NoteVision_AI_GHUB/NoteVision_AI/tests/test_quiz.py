import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from samples import SAMPLE
from modules import flashcard_generator as fg, quiz_generator as qg, text_preprocessing as tp


class QuizTests(unittest.TestCase):
    def test_quiz_structure_and_grounding(self):
        qs = qg.generate_quiz(SAMPLE, 8, seed=7)
        self.assertTrue(4 <= len(qs) <= 8)
        for q in qs:
            self.assertEqual(len(q["options"]), 4)
            self.assertEqual(len(set(q["options"])), 4)
            self.assertTrue(0 <= q["answer_index"] < 4)
            correct = q["options"][q["answer_index"]]
            self.assertIn(correct.lower().rstrip("."), SAMPLE.lower())   # answer comes from the notes
            self.assertTrue(q["explanation"].startswith("From your notes"))

    def test_blank_hides_the_answer(self):
        for q in qg.generate_quiz(SAMPLE, 10, seed=3):
            if q["qtype"] == "fill_blank":
                self.assertIn("_____", q["question"])

    def test_quiz_varies_with_seed(self):
        a = [q["question"] for q in qg.generate_quiz(SAMPLE, 6, seed=1)]
        b = [q["question"] for q in qg.generate_quiz(SAMPLE, 6, seed=2)]
        self.assertNotEqual(a, b)

    def test_tiny_notes_give_no_questions(self):
        self.assertEqual(qg.generate_quiz("Short note here about nothing much at all today.", 5, seed=1), [])

    def test_flashcards_from_notes(self):
        cards = fg.generate_flashcards(SAMPLE)
        self.assertGreaterEqual(len(cards), 5)
        sents = tp.split_sentences(SAMPLE)
        self.assertTrue(all(c["back"] in sents for c in cards))


if __name__ == "__main__":
    unittest.main()
