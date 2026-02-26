import unittest
from unittest.mock import patch, MagicMock
from .api import generate_flashcards, _parse_flashcards


class TestParseFlashcards(unittest.TestCase):
    def test_parse_valid_format(self):
        raw = """- Pergunta 1 | Resposta 1
- Pergunta 2 | Resposta 2
- Pergunta 3 | Resposta 3
- Pergunta 4 | Resposta 4"""
        result = _parse_flashcards(raw)
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], {'title': 'Pergunta 1', 'content': 'Resposta 1'})

    def test_parse_missing_separator(self):
        raw = """- Apenas um lado
- Outro sem separação"""
        result = _parse_flashcards(raw)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['title'], 'Flashcard')

    def test_parse_limits_to_4(self):
        raw = "\n".join([f"- P{i} | R{i}" for i in range(10)])
        result = _parse_flashcards(raw)
        self.assertEqual(len(result), 4)


class TestGenerateFlashcards(unittest.TestCase):
    @patch("ai.api.client")
    def test_generate_success(self, mock_client):
        mock_response = MagicMock()
        mock_response.text = "- O que é X? | É Y\n- Defina Z | Z é W"
        mock_client.models.generate_content.return_value = mock_response

        result = generate_flashcards("Texto de exemplo")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['title'], 'O que é X?')

    @patch("ai.api.client")
    def test_generate_api_error(self, mock_client):
        mock_client.models.generate_content.side_effect = Exception("API down")
        with self.assertRaises(Exception) as ctx:
            generate_flashcards("Texto")
        self.assertIn("Erro ao gerar flashcards", str(ctx.exception))

    def test_generate_empty_text(self):
        with self.assertRaises(ValueError):
            generate_flashcards("")


if __name__ == "__main__":
    unittest.main()
