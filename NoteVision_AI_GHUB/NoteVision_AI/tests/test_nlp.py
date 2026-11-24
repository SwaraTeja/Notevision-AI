import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from samples import SAMPLE
from modules import keyword_extractor as ke, question_answering as qa, summarizer, text_preprocessing as tp


class NLPTests(unittest.TestCase):
    def test_sentence_split_and_clean(self):
        self.assertGreaterEqual(len(tp.split_sentences(SAMPLE)), 9)
        self.assertEqual(tp.clean_text("learn-\ning   is  fun"), "learning is fun")

    def test_pipeline_outputs(self):
        r = tp.preprocess(SAMPLE)
        self.assertGreater(r["stats"]["words"], 50)
        self.assertNotIn("the", r["no_stopwords"])
        self.assertTrue(r["stems"] and r["lemmas"])
        self.assertIn(r["pos"]["engine"], {"NLTK", "none"})

    def test_keywords_and_definitions(self):
        terms = [k["term"] for k in ke.extract_keywords(SAMPLE, 15)]
        self.assertIn("supervised learning", terms)
        defs = {d["term"] for d in ke.extract_definitions(tp.split_sentences(SAMPLE))}
        self.assertIn("Clustering", defs)

    def test_summaries_use_only_source_sentences(self):
        sents = set(tp.content_sentences(SAMPLE))
        body = summarizer.summarize(SAMPLE, "quick").split("\n\n")[1]
        self.assertTrue(any(s in body for s in sents))
        for mode in ("detailed", "exam"):
            self.assertGreater(len(summarizer.summarize(SAMPLE, mode)), 200)

    def test_summary_rejects_tiny_text(self):
        with self.assertRaises(ValueError):
            summarizer.summarize("Too short.", "quick")

    def test_retrieval_answers_and_refuses(self):
        idx = qa.NotesIndex([{"id": 1, "title": "N", "pages": [{"page_no": 2, "text": SAMPLE}]}])
        hit = qa.answer(idx, "What is clustering?")
        self.assertTrue(hit["found"])
        self.assertIn("unsupervised", hit["answer"].lower())
        self.assertEqual(hit["sources"][0]["page"], 2)
        self.assertFalse(qa.answer(idx, "What is the capital of France?")["found"])


if __name__ == "__main__":
    unittest.main()
