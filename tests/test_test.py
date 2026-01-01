import unittest

from src.test import hello_world


class TestHelloWorld(unittest.TestCase):
    """Test cases for the hello_world function."""

    def test_hello_world_returns_correct_string(self):
        """Test that hello_world returns the expected greeting."""
        result = hello_world()
        self.assertEqual(result, "Hello, World!")

    def test_hello_world_is_callable(self):
        """Test that hello_world is a callable function."""
        self.assertTrue(callable(hello_world))


if __name__ == "__main__":
    unittest.main()
