import pathlib
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern
import logging
import aiofiles
from typing import List
from datetime import datetime
import uuid
import os
import re

from app.models.schemas import (
    ConcatenationStats,
    FileConcatenationError,
    TreeNode
)

logger = logging.getLogger(__name__)

class FileConcatenator:
    def __init__(self, base_dir: str = ".", additional_ignores: List[str] = None):
        try:
            logger.info(f"Initializing concatenator for directory: {base_dir}")
            self.base_dir = pathlib.Path(base_dir).resolve()
            if not self.base_dir.exists():
                raise FileConcatenationError(f"Directory does not exist: {base_dir}")
            
            self.additional_ignores = additional_ignores or []
            logger.info(f"Additional ignore patterns: {self.additional_ignores}")
            
            # Initialize statistics
            self.stats = ConcatenationStats()
            
            # Load gitignore patterns and combine with additional ignores
            self.gitignore_patterns = self._load_gitignore()
            all_patterns = self.gitignore_patterns + self.additional_ignores
            self.gitignore_spec = PathSpec.from_lines(GitWildMatchPattern, all_patterns)
            
            # Create output directory if it doesn't exist
            self.output_dir = pathlib.Path(__file__).parent.parent.parent / "output"
            self.output_dir.mkdir(exist_ok=True)
            logger.info(f"Output directory ready at: {self.output_dir}")
            
        except Exception as e:
            logger.error(f"Initialization failed: {str(e)}")
            raise FileConcatenationError(f"Initialization error: {str(e)}")

    def _load_gitignore(self) -> List[str]:
        """Load .gitignore patterns if the file exists."""
        gitignore_path = self.base_dir / ".gitignore"
        patterns = []
        try:
            logger.info(f"Loading gitignore from: {gitignore_path}")
            if gitignore_path.exists():
                with open(gitignore_path, "r") as f:
                    patterns = [line.strip() for line in f if line.strip() 
                              and not line.startswith("#")]
                logger.info(f"Successfully loaded {len(patterns)} gitignore patterns")
            else:
                logger.warning("No gitignore file found")
        except Exception as e:
            logger.error(f"Failed to read gitignore: {e}")
            logger.warning("Proceeding with empty gitignore patterns")
        
        return patterns

    def _is_comment_line(self, line: str) -> bool:
        """Check if a line is a comment based on common comment markers."""
        comment_markers = ['#', '//', '/*', '*', '<!--', '-->', '"""', "'''"]
        stripped = line.strip()
        return any(stripped.startswith(marker) for marker in comment_markers)

    def _update_file_stats(self, file_path: pathlib.Path, content: str):
        """Update file statistics for a processed file."""
        # Update file type stats
        file_type = file_path.suffix.lower() or 'no extension'
        if file_type.startswith('.'):
            file_type = file_type[1:]  # Remove the leading dot
        self.stats.file_stats.file_types[file_type] = \
            self.stats.file_stats.file_types.get(file_type, 0) + 1

        # Update size stats
        file_size = file_path.stat().st_size
        self.stats.file_stats.total_size += file_size
        if file_size > self.stats.file_stats.largest_file["size"]:
            self.stats.file_stats.largest_file = {
                'path': str(file_path.relative_to(self.base_dir)),
                'size': file_size
            }

        # Update line stats
        lines = content.splitlines()
        self.stats.file_stats.total_lines += len(lines)
        self.stats.file_stats.empty_lines += sum(1 for line in lines if not line.strip())
        self.stats.file_stats.comment_lines += sum(1 for line in lines if self._is_comment_line(line))

    def _update_dir_stats(self, current_path: pathlib.Path, files_count: int):
        """Update directory statistics."""
        self.stats.dir_stats.total_dirs += 1
        
        # Update depth stats
        relative_path = current_path.relative_to(self.base_dir)
        depth = len(relative_path.parts)
        self.stats.dir_stats.max_depth = max(self.stats.dir_stats.max_depth, depth)
        
        # Update directory with most files
        if files_count > self.stats.dir_stats.dirs_with_most_files["count"]:
            self.stats.dir_stats.dirs_with_most_files = {
                'path': str(relative_path),
                'count': files_count
            }
        
        # Update empty directory count
        if files_count == 0:
            self.stats.dir_stats.empty_dirs += 1

    def _update_filter_stats(self, file_path: pathlib.Path, is_gitignore: bool):
        """Update filter statistics when a file is ignored."""
        rel_path = str(file_path.relative_to(self.base_dir))
        
        if is_gitignore:
            self.stats.filter_stats.gitignore_filtered += 1
            # Check which gitignore pattern matched
            for pattern in self.gitignore_patterns:
                if PathSpec.from_lines(GitWildMatchPattern, [pattern]).match_file(rel_path):
                    self.stats.filter_stats.pattern_matches[pattern] = \
                        self.stats.filter_stats.pattern_matches.get(pattern, 0) + 1
        else:
            self.stats.filter_stats.custom_filtered += 1
            # Check which custom pattern matched
            for pattern in self.additional_ignores:
                if PathSpec.from_lines(GitWildMatchPattern, [pattern]).match_file(rel_path):
                    self.stats.filter_stats.pattern_matches[pattern] = \
                        self.stats.filter_stats.pattern_matches.get(pattern, 0) + 1

    def _is_ignored(self, path: pathlib.Path) -> bool:
        """Check if path should be ignored based on .gitignore rules."""
        try:
            rel_path = str(path.relative_to(self.base_dir))
            
            # Check gitignore patterns first
            for pattern in self.gitignore_patterns:
                if PathSpec.from_lines(GitWildMatchPattern, [pattern]).match_file(rel_path):
                    self._update_filter_stats(path, True)
                    return True
            
            # Then check additional patterns
            for pattern in self.additional_ignores:
                if PathSpec.from_lines(GitWildMatchPattern, [pattern]).match_file(rel_path):
                    self._update_filter_stats(path, False)
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking ignore status for {path}: {e}")
            return True

    def _build_directory_tree(self) -> TreeNode:
        """Build a directory tree structure."""
        root = TreeNode(
            name=self.base_dir.name or self.base_dir.absolute(),
            path=str(self.base_dir),
            type='directory',
            children=[]
        )

        def add_to_tree(current_path: pathlib.Path, node: TreeNode):
            """Recursively add files and directories to the tree."""
            try:
                # Sort entries for consistent display
                entries = sorted(current_path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
                
                for entry in entries:
                    if self._is_ignored(entry):
                        continue
                        
                    is_file = entry.is_file()
                    child = TreeNode(
                        name=entry.name,
                        path=str(entry.relative_to(self.base_dir)),
                        type='file' if is_file else 'directory',
                        children=[],
                        metadata={
                            'size': entry.stat().st_size if is_file else None,
                            'extension': entry.suffix.lower() if is_file else None
                        }
                    )
                    
                    if not is_file:
                        add_to_tree(entry, child)
                    
                    node.children.append(child)
            except Exception as e:
                logger.error(f"Error building tree for {current_path}: {e}")

        add_to_tree(self.base_dir, root)
        return root

    def _get_repo_name(self) -> str:
        """Extract repository name from the base directory."""
        try:
            # Get the full path components
            parts = self.base_dir.parts
            
            # Look for repository name in path (format: repo-name_timestamp_pid_hash)
            for part in reversed(parts):
                if '_' in part and any(c.isdigit() for c in part):
                    repo_name = part.split('_')[0]
                    # If we're in a subdirectory, append it to make the name more specific
                    subdir_path = self.base_dir.relative_to(self.base_dir.parent)
                    if str(subdir_path) != repo_name:
                        clean_subdir = re.sub(r'[^\w\-]', '_', str(subdir_path))
                        return f"{repo_name}_{clean_subdir}"
                    return repo_name
            
            # Fallback: use the last directory name
            return re.sub(r'[^\w\-]', '_', self.base_dir.name)
        except Exception as e:
            logger.warning(f"Error extracting repo name: {e}, using fallback")
            return re.sub(r'[^\w\-]', '_', self.base_dir.name)

    def _generate_unique_filename(self, repo_name: str) -> str:
        """Generate a unique filename for output."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")  # Include microseconds
        unique_id = uuid.uuid4().hex[:8]  # 8 characters from UUID
        pid = os.getpid()  # Process ID
        
        # Clean up repo_name to ensure it's filesystem-safe
        clean_name = re.sub(r'[^\w\-]', '_', repo_name)
        return f"output_{clean_name}_{timestamp}_pid{pid}_{unique_id}.txt"

    async def concatenate_files(self) -> str:
        """Concatenate all files in the directory respecting .gitignore rules."""
        try:
            repo_name = self._get_repo_name()
            output_filename = self._generate_unique_filename(repo_name)
            output_file = self.output_dir / output_filename
            
            files = self._walk_directory()
            self.stats.file_stats.total_files = len(files)
            
            # Build directory tree starting from the current base_dir
            self.stats.dir_stats.tree = self._build_directory_tree()
            
            async with aiofiles.open(output_file, 'w', encoding='utf-8') as outfile:
                # Write directory information
                await outfile.write(f"Directory: {self.base_dir}\n")
                await outfile.write("=" * (len(str(self.base_dir)) + 11) + "\n\n")
                
                # Write directory tree visualization
                await outfile.write("Directory Structure:\n")
                await outfile.write("===================\n\n")
                await self._write_tree_visualization(outfile, self.stats.dir_stats.tree)
                await outfile.write("\n\nFile Contents:\n")
                await outfile.write("=============\n\n")
                
                for file_path in files:
                    try:
                        if self._is_ignored(file_path):
                            self.stats.file_stats.skipped_files += 1
                            continue
                        
                        logger.info(f"Processing file: {file_path}")
                        async with aiofiles.open(file_path, 'r', encoding='utf-8') as infile:
                            content = await infile.read()
                            
                            # Write file header with relative path from base_dir
                            await outfile.write(f"\n{'='*80}\n")
                            await outfile.write(f"File: {file_path.relative_to(self.base_dir)}\n")
                            await outfile.write(f"{'='*80}\n\n")
                            
                            # Write file content
                            await outfile.write(content)
                            await outfile.write("\n")
                            
                            self._update_file_stats(file_path, content)
                            self.stats.file_stats.processed_files += 1
                            
                    except Exception as e:
                        logger.error(f"Error processing file {file_path}: {e}")
                        continue
            
            logger.info(f"Concatenation complete. Output saved to: {output_file}")
            return str(output_file)
            
        except Exception as e:
            logger.error(f"Concatenation failed: {e}")
            raise FileConcatenationError(f"Concatenation error: {str(e)}")

    async def _write_tree_visualization(self, outfile, node: TreeNode, prefix: str = "", is_last: bool = True):
        """Write ASCII tree visualization to the output file."""
        if not node:
            return

        # Calculate the current line prefix
        current_prefix = prefix + ("└── " if is_last else "├── ")
        next_prefix = prefix + ("    " if is_last else "│   ")

        # Add size information for files
        size_info = ""
        if node.type == 'file' and node.metadata.get('size') is not None:
            size = node.metadata['size']
            if size < 1024:
                size_info = f" ({size} B)"
            elif size < 1024 * 1024:
                size_info = f" ({size/1024:.1f} KB)"
            else:
                size_info = f" ({size/(1024*1024):.1f} MB)"

        # Write the current node
        await outfile.write(f"{current_prefix}{node.name}{size_info}\n")

        # Process children
        if node.children:
            for i, child in enumerate(node.children):
                is_last_child = i == len(node.children) - 1
                await self._write_tree_visualization(outfile, child, next_prefix, is_last_child)

    def _walk_directory(self) -> List[pathlib.Path]:
        """Walk through directory and collect all files."""
        files = []
        try:
            # Only walk through the specified base directory
            for current_path in self.base_dir.rglob("*"):
                if current_path.is_file():
                    files.append(current_path)
                elif current_path.is_dir():
                    # Count files in this directory for stats
                    dir_files = list(current_path.glob("*"))
                    self._update_dir_stats(current_path, len([f for f in dir_files if f.is_file()]))
            
            return sorted(files)
        except Exception as e:
            logger.error(f"Error walking directory: {e}")
            return [] 