# documents_manager.py
"""Manages local document storage: list / create / read / save / delete HTML docs."""
import logging
import os
import re

logger = logging.getLogger("SpeechEditor")

SUPPORTED_EXTS = [".md", ".html", ".txt"]
DEFAULT_DOCS_FOLDER = "documents"


def ensure_folder(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def _slug(name: str) -> str:
    base = re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")
    return base or "untitled"


def list_documents(folder: str) -> list:
    """Returns document paths, most recently modified first."""
    if not os.path.isdir(folder):
        return []
    files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.splitext(f.lower())[1] in SUPPORTED_EXTS
    ]
    return sorted(files, key=os.path.getmtime, reverse=True)


def create_document(folder: str, name: str, ext: str = ".md") -> str:
    """Creates an empty document with the chosen extension (filename made unique).
    If the name itself ends in a supported extension (e.g. 'notes.txt'),
    that extension wins over the default."""
    ensure_folder(folder)
    # Honour an extension typed as part of the name
    given_base, given_ext = os.path.splitext(name.strip())
    if given_ext.lower() in SUPPORTED_EXTS:
        name, ext = given_base, given_ext.lower()
    if ext not in SUPPORTED_EXTS:
        ext = ".txt"  # default format
    base = _slug(name)
    path = os.path.join(folder, base + ext)
    n = 2
    while os.path.exists(path):
        path = os.path.join(folder, f"{base}_{n}{ext}")
        n += 1
    save_document(path, "")
    logger.info(f"Created document: {path}")
    return path


def import_document(source_path: str, dest_folder: str) -> str:
    """Copies an external file into the documents folder (unique name)."""
    ensure_folder(dest_folder)
    base = os.path.basename(source_path)
    dest = os.path.join(dest_folder, base)
    stem, ext = os.path.splitext(base)
    n = 2
    while os.path.exists(dest):
        dest = os.path.join(dest_folder, f"{stem}_{n}{ext}")
        n += 1
    with open(source_path, "rb") as src, open(dest, "wb") as dst:
        dst.write(src.read())
    logger.info(f"Imported {source_path} -> {dest}")
    return dest


def create_folder(parent: str, name: str) -> str:
    """Creates a folder (name made unique), returns its path."""
    ensure_folder(parent)
    base = _slug(name)
    path = os.path.join(parent, base)
    n = 2
    while os.path.exists(path):
        path = os.path.join(parent, f"{base}_{n}")
        n += 1
    os.makedirs(path)
    logger.info(f"Created folder: {path}")
    return path


def read_document(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def save_document(path: str, html: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def delete_document(path: str):
    if os.path.exists(path):
        os.remove(path)
        logger.info(f"Deleted document: {path}")


def rename_document(old_path: str, new_name: str) -> str:
    """Renames a file (keeps extension) or folder. Returns the new path."""
    directory = os.path.dirname(old_path)
    _, ext = os.path.splitext(old_path)
    base = _slug(new_name)
    new_path = os.path.join(directory, base + ext)
    if os.path.abspath(new_path) == os.path.abspath(old_path):
        return old_path
    n = 2
    while os.path.exists(new_path):
        new_path = os.path.join(directory, f"{base}_{n}{ext}")
        n += 1
    os.rename(old_path, new_path)
    logger.info(f"Renamed {old_path} -> {new_path}")
    return new_path


def duplicate_document(path: str) -> str:
    """Creates a 'name_copy.ext' copy next to the original. Returns the copy path."""
    directory = os.path.dirname(path)
    stem, ext = os.path.splitext(os.path.basename(path))
    new_path = os.path.join(directory, f"{stem}_copy{ext}")
    n = 2
    while os.path.exists(new_path):
        new_path = os.path.join(directory, f"{stem}_copy{n}{ext}")
        n += 1
    with open(path, "r", encoding="utf-8") as src, \
            open(new_path, "w", encoding="utf-8") as dst:
        dst.write(src.read())
    logger.info(f"Duplicated {path} -> {new_path}")
    return new_path


def display_name(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0].replace("_", " ")
