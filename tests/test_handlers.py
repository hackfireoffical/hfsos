import unittest

from app.rubika.handlers import WELCOME, _button_id, _extract_message, main_keypad


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

    def test_help_mentions_interactive_menu(self):
        self.assertIn("Choose a service", WELCOME)

    def test_main_menu_has_all_four_search_providers(self):
        keyboard = main_keypad()
        button_ids = [
            button["id"]
            for row in keyboard["rows"]
            for button in row["buttons"]
        ]
        self.assertEqual(
            set(button_ids),
            {"menu:github", "menu:modrinth", "menu:curseforge", "menu:youtube", "menu:downloads", "menu:help"},
        )

    def test_extracts_inline_button_callback(self):
        update = {
            "type": "NewMessage",
            "chat_id": "chat-guid",
            "new_message": {
                "text": "GitHub",
                "aux_data": {"button_id": "menu:github"},
            },
        }
        self.assertEqual(_button_id(update), "menu:github")


if __name__ == "__main__":
    unittest.main()
