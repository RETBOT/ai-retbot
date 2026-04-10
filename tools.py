import os
import subprocess

BASE_PATH = os.getcwd()


def read_file(path, offset=0, limit=200):
    try:
        if not os.path.isabs(path):
            path = os.path.join(BASE_PATH, path)
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return "".join(lines[offset:offset+limit])
    except Exception as e:
        return f"Error: {e}"


def write_file(path, content):
    try:
        if not os.path.isabs(path):
            path = os.path.join(BASE_PATH, path)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"OK: {path}"
    except Exception as e:
        return f"Error: {e}"


def glob(pattern, path=None):
    import glob as g
    try:
        search_path = os.path.join(path or BASE_PATH, pattern)
        matches = g.glob(search_path, recursive=True)
        return "\n".join(matches[:50]) or "No matches"
    except Exception as e:
        return f"Error: {e}"


def grep(pattern, path=None, include="*"):
    import fnmatch
    results = []
    search_path = path or BASE_PATH
    for root, dirs, files in os.walk(search_path):
        for f in files:
            if fnmatch.fnmatch(f, include):
                full_path = os.path.join(root, f)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as file:
                        for i, line in enumerate(file, 1):
                            if pattern.lower() in line.lower():
                                results.append(f"{full_path}:{i}: {line.rstrip()}")
                except:
                    pass
        if len(results) > 100:
            break
    return "\n".join(results[:50]) or "No matches"


def bash(command):
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=BASE_PATH
        )
        output = result.stdout or result.stderr or ""
        return f"[{result.returncode}] {output[:2000]}"
    except Exception as e:
        return f"Error: {e}"


def list_files(path=None):
    try:
        search_path = path or BASE_PATH
        items = []
        for item in os.listdir(search_path):
            full = os.path.join(search_path, item)
            items.append(item + ("/" if os.path.isdir(full) else ""))
        return "\n".join(items)
    except Exception as e:
        return f"Error: {e}"


TOOLS = {
    "read_file": read_file,
    "write_file": write_file,
    "glob": glob,
    "grep": grep,
    "bash": bash,
    "list_files": list_files,
}
