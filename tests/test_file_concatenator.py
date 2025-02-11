# tests/test_file_concatenator.py
import unittest
import tempfile
import shutil
from pathlib import Path
from app.core.file_concatenator import FileConcatenator
from app.config.pattern_manager import PatternManager, SYSTEM_IGNORES

class TestFileConcatenator(unittest.TestCase):
    def setUp(self):
        # Use tempfile.mkdtemp() for safer temporary directory creation
        self.temp_dir = tempfile.mkdtemp()
        self.test_repo_path = Path(self.temp_dir) / "test_repo"
        self.test_repo_path.mkdir(parents=True, exist_ok=True)

        # Create some test files and directories
        (self.test_repo_path / "file1.txt").write_text("Content of file1")
        (self.test_repo_path / "file2.log").write_text("Content of file2")
        (self.test_repo_path / "dir1").mkdir(exist_ok=True)
        (self.test_repo_path / "dir1/file3.tmp").write_text("Content of file3")
        (self.test_repo_path / ".hidden.txt").write_text("Content of hidden") # For system ignore test

        # Create a .gitignore file
        (self.test_repo_path / ".gitignore").write_text("*.log\n*.tmp\n")

    def tearDown(self):
        # Use shutil.rmtree() for safer temporary directory removal
        shutil.rmtree(self.temp_dir)

    def test_concatenation_with_gitignore(self):
        # Test concatenation with a .gitignore file
        concatenator = FileConcatenator(repo_path=self.test_repo_path)
        output_file = concatenator.concatenate()

        # Check that the output file exists
        output_path = Path("output") / output_file
        self.assertTrue(output_path.exists())

        # Check that ignored files are NOT included (using file paths)
        with open(output_path, 'r') as f:
            content = f.read()
            self.assertNotIn("File: file2.log", content)  # Check for file path
            self.assertNotIn("File: dir1/file3.tmp", content) # Check for file path
            self.assertIn("File: file1.txt", content) # Check that the non-ignored file IS present

    def test_concatenation_without_gitignore(self):
        # Remove the .gitignore file
        (self.test_repo_path / ".gitignore").unlink()

        # Test concatenation without a .gitignore file (system ignores should still apply)
        concatenator = FileConcatenator(repo_path=self.test_repo_path)
        output_file = concatenator.concatenate()

        # Check that the output file exists
        output_path = Path("output") / output_file
        self.assertTrue(output_path.exists())

        # Check that system-ignored files are NOT included, but other files ARE
        with open(output_path, 'r') as f:
            content = f.read()
            self.assertIn("File: file1.txt", content)
            self.assertIn("File: file2.log", content)  # Should be included now
            self.assertIn("File: dir1/file3.tmp", content) # Should be included now
            self.assertNotIn("File: .hidden.txt", content) # Test a system ignore

    def test_concatenation_with_additional_ignores(self):
        # Test concatenation with additional ignore patterns
        additional_ignores = ["file1.txt"]
        concatenator = FileConcatenator(repo_path=self.test_repo_path, additional_ignores=additional_ignores)
        output_file = concatenator.concatenate()

        # Check that the output file exists
        output_path = Path("output") / output_file
        self.assertTrue(output_path.exists())

        # Check that additionally ignored files are NOT included
        with open(output_path, 'r') as f:
            content = f.read()
            self.assertNotIn("File: file1.txt", content)  # Check additional ignore
            self.assertNotIn("File: file2.log", content)  # Check .gitignore
            self.assertNotIn("File: dir1/file3.tmp", content)  # Check .gitignore

    def test_system_ignores(self):
        # Create a file that matches a system ignore pattern
        (self.test_repo_path / ".hidden.txt").write_text("This should be ignored")

        concatenator = FileConcatenator(repo_path=self.test_repo_path)
        output_file = concatenator.concatenate()

        output_path = Path("output") / output_file
        with open(output_path, 'r') as f:
            content = f.read()
            self.assertNotIn("File: .hidden.txt", content)

class TestPatternManager(unittest.TestCase):
    def test_combine_patterns(self):
        manager = PatternManager(repo_ignores=["*.log", "temp/"], user_ignores=["*.tmp", "temp/"])
        expected = sorted(SYSTEM_IGNORES + ["*.log", "*.tmp", "temp/"])  # Combine and sort
        self.assertEqual(manager.all_ignores, expected)

    def test_should_ignore(self):
        manager = PatternManager(repo_ignores=["*.log"], user_ignores=["*.tmp"])
        self.assertTrue(manager.should_ignore("test.log"))      # Repo ignore
        self.assertTrue(manager.should_ignore("test.tmp"))      # User ignore
        self.assertTrue(manager.should_ignore(".git/config"))  # System ignore
        self.assertFalse(manager.should_ignore("test.txt"))     # Not ignored

    def test_from_repo_path(self):
        # Create a temporary directory and .gitignore
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "test_repo"
            repo_path.mkdir()
            (repo_path / ".gitignore").write_text("*.log\n# Comment\n*.tmp\n")

            manager = PatternManager.from_repo_path(repo_path)
            self.assertIn("*.log", manager.repo_ignores)
            self.assertIn("*.tmp", manager.repo_ignores)
            self.assertNotIn("# Comment", manager.repo_ignores) # Check comment removal

            # Test should_ignore with files in the temp dir
            (repo_path / "test.txt").write_text("test")
            (repo_path / "test.log").write_text("test")

            self.assertTrue(manager.should_ignore(str(repo_path / "test.log")))
            self.assertFalse(manager.should_ignore(str(repo_path / "test.txt")))

if __name__ == '__main__':
    unittest.main()
