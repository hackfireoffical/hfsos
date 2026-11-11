import unittest

from app.rubika.handlers import WELCOME, _extract_message


class HandlerTests(unittest.TestCase):
    def test_extracts_official_new_message_update_shape(self):
        update = {
            "type": "NewMessage",
            "chat_id": "chat-guid",
            "new_message": {"text": "  /help  ", "message_id": "message-guid"},
        }
        self.assertEqual(_extract_message(update), ("chat-guid", "/help"))

    def test_ignores_non_message_updates(self):
        self.assertIsNone(_extract_message({"type": "RemovedMessage", "chat_id": "x"}))

    def test_ignores_empty_messages(self):
        self.assertIsNone(_extract_message({
            "type": "NewMessage", "chat_id": "x", "new_message": {"text": "  "}
        }))

    def test_help_includes_download_and_file_lookup(self):
        self.assertIn("/download github", WELCOME)
        self.assertIn("/files <project-id>", WELCOME)


if __name__ == "__main__":
    unittest.main()
