import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.db_manager import Database


def _doc(db):
    i = db.add_document("Notes", "Physics", "n.png", "x", "png", 1)
    db.add_pages(i, [{"page_no": 1, "text": "Newton's laws describe motion."}])
    return i


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "t.db"
        self.db = Database(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_crud_and_search(self):
        db, i = self.db, _doc(self.db)
        self.assertTrue(db.get_full_text(i).startswith("Newton"))
        self.assertEqual(db.list_documents("motion")[0]["id"], i)
        self.assertEqual(db.list_documents("zzz"), [])
        self.assertEqual(db.list_documents(subject="Chemistry"), [])
        db.update_page_text(db.get_pages(i)[0]["id"], "edited")
        self.assertEqual(db.get_full_text(i), "edited")

    def test_persistence_across_restart(self):
        i = _doc(self.db)
        self.db.save_summary(i, "quick", "S")
        d2 = Database(self.path)                       # simulates restarting the app
        self.assertEqual(d2.get_document(i)["title"], "Notes")
        self.assertEqual(d2.latest_summary(i, "quick")["content"], "S")

    def test_cascade_delete(self):
        db, i = self.db, _doc(self.db)
        qid = db.save_quiz(i, [{"question": "Q", "options": list("abcd"), "answer_index": 1}])
        db.save_attempt(qid, i, 1, 1, {"1": 1})
        db.replace_flashcards(i, [{"front": "f", "back": "b"}])
        db.log_activity("upload", i)
        db.delete_document(i)
        self.assertEqual(db.get_pages(i), [])
        self.assertIsNone(db.get_quiz(qid))
        self.assertEqual(db.get_flashcards(i), [])
        self.assertEqual(db.list_attempts(), [])
        self.assertIsNone(db.recent_activity()[0]["doc_id"])   # activity kept, link cleared

    def test_flashcard_status(self):
        db, i = self.db, _doc(self.db)
        db.replace_flashcards(i, [{"front": "f", "back": "b"}])
        db.set_flashcard_status(db.get_flashcards(i)[0]["id"], "known")
        c = db.get_flashcards(i)[0]
        self.assertEqual((c["status"], c["reviews"]), ("known", 1))


if __name__ == "__main__":
    unittest.main()
