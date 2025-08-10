import os

# def print_tree(start_path, prefix=''):
#     for item in os.listdir(start_path):
#         path = os.path.join(start_path, item)
#         print(prefix + "|-- " + item)
#         if os.path.isdir(path):
#             print_tree(path, prefix + "|   ")

# print_tree('.')

# import os

# EXCLUDED = {'.git', '.gitignore', 'my_venv'}
# MAX_DEPTH = 3  # Change this to control depth

# def print_tree(start_path, prefix='', current_depth=0):
#     if current_depth > MAX_DEPTH:
#         return

#     try:
#         entries = sorted(os.listdir(start_path))
#     except PermissionError:
#         return

#     for item in entries:
#         if item in EXCLUDED:
#             continue

#         path = os.path.join(start_path, item)
#         print(prefix + "|-- " + item)

#         if os.path.isdir(path):
#             print_tree(path, prefix + "|   ", current_depth + 1)

# print_tree('.')

# import os
# import argparse

# def print_tree(start_path, prefix='', current_depth=0, max_depth=2, excluded=None):
#     if current_depth > max_depth:
#         return

#     try:
#         entries = sorted(os.listdir(start_path))
#     except PermissionError:
#         return

#     for item in entries:
#         if item in excluded:
#             continue

#         path = os.path.join(start_path, item)
#         print(prefix + "|-- " + item)

#         if os.path.isdir(path):
#             print_tree(path, prefix + "|   ", current_depth + 1, max_depth, excluded)

# def main():
#     parser = argparse.ArgumentParser(description="Generate a file/folder tree.")
#     parser.add_argument(
#         "--exclude",
#         "-e",
#         nargs="*",
#         default=[],
#         help="List of files/folders to exclude"
#     )
#     parser.add_argument(
#         "--depth",
#         "-d",
#         type=int,
#         default=2,
#         help="Max depth of tree"
#     )
#     parser.add_argument(
#         "--path",
#         "-p",
#         default=".",
#         help="Starting path (default: current directory)"
#     )
#     args = parser.parse_args()

#     excluded = set(args.exclude)
#     print_tree(args.path, max_depth=args.depth, excluded=excluded)

# if __name__ == "__main__":
#     main()

# type like this on the shell
# python print-tree.py --exclude .git .gitignore my_venv yml.txt tree.txt --depth 3 --path . > tree.txt

# import os
# import argparse

# def generate_tree(start_path, prefix='', current_depth=0, max_depth=2, excluded=None, markdown=False):
#     if current_depth > max_depth:
#         return []

#     lines = []
#     try:
#         entries = sorted(os.listdir(start_path))
#     except PermissionError:
#         return []

#     for item in entries:
#         if item in excluded:
#             continue

#         path = os.path.join(start_path, item)
        
#         if markdown:
#             indent_level = prefix.count('|')
#             indent = '  ' * indent_level
#             line = f"{indent}- {item}"
#         else:
#             line = prefix + "|-- " + item

#         lines.append(line)

#         if os.path.isdir(path):
#             sub_lines = generate_tree(
#                 path,
#                 prefix + "|   ",
#                 current_depth + 1,
#                 max_depth,
#                 excluded,
#                 markdown
#             )
#             lines.extend(sub_lines)

#     return lines

# def main():
#     parser = argparse.ArgumentParser(description="Generate a file/folder tree.")
#     parser.add_argument(
#         "--exclude", "-e", nargs="*", default=[],
#         help="List of files/folders to exclude"
#     )
#     parser.add_argument(
#         "--depth", "-d", type=int, default=2,
#         help="Max depth of tree"
#     )
#     parser.add_argument(
#         "--path", "-p", default=".",
#         help="Starting path (default: current directory)"
#     )
#     parser.add_argument(
#         "--output", "-o", default=None,
#         help="Output file (optional)"
#     )
#     parser.add_argument(
#         "--markdown", "-m", action="store_true",
#         help="Format output as Markdown"
#     )
#     args = parser.parse_args()

#     excluded = set(args.exclude)
#     tree_lines = generate_tree(
#         args.path,
#         max_depth=args.depth,
#         excluded=excluded,
#         markdown=args.markdown
#     )

#     if args.markdown:
#         tree_lines.insert(0, "```markdown")
#         tree_lines.append("```")

#     output = "\n".join(tree_lines)

#     if args.output:
#         with open(args.output, "w", encoding="utf-8") as f:
#             f.write(output + "\n")
#         print(f"Tree saved to {args.output}")
#     else:
#         print(output)

# if __name__ == "__main__":
#     main()

# # type like this in shell
# # python print-tree.py --exclude .git .gitignore my_venv yml.txt tree.txt --depth 3 --path . -o tree.md -m

# import os
# import argparse
# import json

# def generate_tree(start_path, prefix='', current_depth=0, max_depth=2, excluded=None, markdown=False, comments=None, root_path=None):
#     if current_depth > max_depth:
#         return []

#     lines = []
#     try:
#         entries = sorted(os.listdir(start_path))
#     except PermissionError:
#         return []

#     for item in entries:
#         if item in excluded:
#             continue

#         path = os.path.join(start_path, item)
#         rel_path = os.path.relpath(path, root_path or start_path).replace("\\", "/")  # Normalize to forward slashes

#         indent_level = prefix.count('|')
#         indent = '  ' * indent_level
#         display_name = item

#         # Apply markdown styling if requested
#         if markdown:
#             display_name = f"{item}"

#         # Match comment by full relative path
#         comment = comments.get(rel_path, "")
#         if markdown and comment:
#             comment_str = f"  # {comment} "
#         elif comment:
#             comment_str = f"  <!--  {comment} -->"
#         else:
#             comment_str = ""

#         # Fixed-width alignment
#         name_column = f"{indent}- {display_name:<30}"
#         line = f"{name_column}{comment_str}"
#         lines.append(line)

#         if os.path.isdir(path):
#             sub_lines = generate_tree(
#                 path,
#                 prefix + "|   ",
#                 current_depth + 1,
#                 max_depth,
#                 excluded,
#                 markdown,
#                 comments,
#                 root_path or start_path
#             )
#             lines.extend(sub_lines)

#     return lines


# def main():
#     parser = argparse.ArgumentParser(description="Generate a file/folder tree with optional comments.")
#     parser.add_argument("--exclude", "-e", nargs="*", default=[], help="List of files/folders to exclude")
#     parser.add_argument("--depth", "-d", type=int, default=2, help="Max depth of tree")
#     parser.add_argument("--path", "-p", default=".", help="Starting path (default: current directory)")
#     parser.add_argument("--output", "-o", default=None, help="Output file (optional)")
#     parser.add_argument("--markdown", "-m", action="store_true", help="Format output as Markdown")
#     parser.add_argument("--comments", "-c", default=None, help="Path to comments.json")

#     args = parser.parse_args()

#     excluded = set(args.exclude)

#     # Load comments if provided
#     comments = {}
#     if args.comments:
#         try:
#             with open(args.comments, "r", encoding="utf-8") as f:
#                 comments = json.load(f)
#         except Exception as e:
#             print(f"⚠️ Failed to load comments file: {e}")

#     # Generate tree lines
#     tree_lines = generate_tree(
#         args.path,
#         max_depth=args.depth,
#         excluded=excluded,
#         markdown=args.markdown,
#         comments=comments,
#         root_path=args.path
#     )

#     # Wrap in markdown block if needed
#     if args.markdown:
#         tree_lines.insert(0, "```markdown")
#         tree_lines.append("```")

#     output = "\n".join(tree_lines)

#     if args.output:
#         with open(args.output, "w", encoding="utf-8") as f:
#             f.write(output + "\n")
#         print(f"✅ Tree saved to {args.output}")
#     else:
#         print(output)

# if __name__ == "__main__":
#     main()
# # type like this in the shell
# # python print-tree.py --exclude .git .gitignore my_venv yml.txt tree.txt --depth 3 --path . -o tree.md -m -c comments.json

import os
import argparse
import json
import sys

try:
    import yaml
except ImportError:
    yaml = None


def generate_tree(start_path, prefix='', current_depth=0, max_depth=2, excluded=None,
                  markdown=False, comments=None, root_path=None):
    """Generate markdown tree lines with optional comments."""
    if current_depth > max_depth:
        return []

    lines = []
    try:
        entries = sorted(os.listdir(start_path))
    except PermissionError:
        return []

    for item in entries:
        if item in excluded:
            continue

        path = os.path.join(start_path, item)
        rel_path = os.path.relpath(path, root_path or start_path).replace("\\", "/")
        is_dir = os.path.isdir(path)
        comment = comments.get(rel_path, "")

        indent_level = prefix.count('|')
        indent = '  ' * indent_level
        display_name = item
        if markdown:
            display_name = f"{item}"

        if markdown and comment:
            comment_str = f"  # {comment} "
        elif comment:
            comment_str = f"  <!--  {comment} -->"
        else:
            comment_str = ""

        name_column = f"{indent}- {display_name:<30}"
        line = f"{name_column}{comment_str}"
        lines.append(line)

        if is_dir:
            sub_lines = generate_tree(
                path,
                prefix + "|   ",
                current_depth + 1,
                max_depth,
                excluded,
                markdown,
                comments,
                root_path or start_path
            )
            lines.extend(sub_lines)

    return lines


def generate_table(start_path, max_depth=2, excluded=None, comments=None, root_path=None, repo_url=None):
    """Generate GitHub markdown table lines with Path, Type, Comment."""
    lines = []

    def walk_dir(path, depth):
        if depth > max_depth:
            return
        for item in sorted(os.listdir(path)):
            if item in excluded:
                continue
            full_path = os.path.join(path, item)
            rel_path = os.path.relpath(full_path, root_path or start_path).replace("\\", "/")
            is_dir = os.path.isdir(full_path)
            comment = comments.get(rel_path, "")

            if repo_url:
                if is_dir:
                    link = f"{repo_url.rstrip('/')}/tree/main/{rel_path}"
                else:
                    link = f"{repo_url.rstrip('/')}/blob/main/{rel_path}"
                path_display = f"[`{rel_path}`]({link})"
            else:
                path_display = f"`{rel_path}`"

            lines.append(f"| {path_display} | {'Folder' if is_dir else 'File'} | {comment} |")

            if is_dir:
                walk_dir(full_path, depth + 1)

    walk_dir(start_path, 0)
    return lines


def load_comments(file_path):
    """Load comments from JSON or YAML file."""
    if not file_path:
        return {}
    try:
        if file_path.lower().endswith((".yaml", ".yml")):
            if yaml is None:
                sys.exit("❌ PyYAML not installed. Install with: pip install pyyaml")
            with open(file_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Failed to load comments file: {e}")
        return {}


def main():
    parser = argparse.ArgumentParser(description="Generate a file/folder tree and GitHub table with optional comments and links.")
    parser.add_argument("--exclude", "-e", nargs="*", default=[], help="List of files/folders to exclude")
    parser.add_argument("--depth", "-d", type=int, default=2, help="Max depth of tree")
    parser.add_argument("--path", "-p", default=".", help="Starting path (default: current directory)")
    parser.add_argument("--output", "-o", default=None, help="Output file (optional)")
    parser.add_argument("--markdown", "-m", action="store_true", help="Format output as Markdown")
    parser.add_argument("--comments", "-c", default=None, help="Path to comments.json or comments.yaml")
    parser.add_argument("--repo", "-r", default=None, help="GitHub repo base URL (for clickable links)")

    args = parser.parse_args()

    excluded = set(args.exclude)
    comments = load_comments(args.comments)

    # Generate tree
    tree_lines = generate_tree(
        args.path,
        max_depth=args.depth,
        excluded=excluded,
        markdown=True,
        comments=comments,
        root_path=args.path
    )

    # Generate table with links
    table_lines = generate_table(
        args.path,
        max_depth=args.depth,
        excluded=excluded,
        comments=comments,
        root_path=args.path,
        repo_url=args.repo
    )

    # Combine both sections
    output_parts = []
    output_parts.append("## 📂 Project Structure (Tree View)\n")
    output_parts.append("```markdown")
    output_parts.extend(tree_lines)
    output_parts.append("```\n")

    output_parts.append("## 📊 Project Structure (Table View)\n")
    output_parts.append("| Path | Type | Comment |")
    output_parts.append("|------|------|---------|")
    output_parts.extend(table_lines)

    output = "\n".join(output_parts)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output + "\n")
        print(f"✅ Output saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
