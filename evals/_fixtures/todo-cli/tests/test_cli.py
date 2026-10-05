import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from todo import cli


class CliTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp()
        os.close(fd)
        os.remove(self.path)
        os.environ["TODO_FILE"] = self.path

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(list(argv))
        return code, out.getvalue()

    def test_add_list_done(self):
        self.run_cli("add", "buy milk")
        self.run_cli("done", "1")
        code, out = self.run_cli("list")
        self.assertEqual(code, 0)
        self.assertIn("[x]  buy milk", out)

    def test_done_unknown_id(self):
        self.assertEqual(self.run_cli("done", "9")[0], 1)


if __name__ == "__main__":
    unittest.main()
