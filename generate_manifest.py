#!/usr/bin/env python3
"""
generate_manifest.py

Purpose:
    This script generates two files for use in a MicroPython-based OTA (Over-The-Air) update system:
    1. manifest.json → contains file hashes and sizes needed for validating OTA updates
    2. version.txt   → holds the semantic version string of the current firmware

Functionality:
    - Recursively scans the project directory for eligible files
    - Excludes predefined directories and script files not meant for OTA
    - Normalizes line endings in text files to ensure consistent hashing
    - Calculates a SHA-256 hash and file size for each tracked file
    - Writes a versioned manifest with all collected data
    - Bumps version based on the given semantic versioning flag: patch, minor, or major

Usage:
    python generate_manifest.py --bump [patch|minor|major]

Example:
    python generate_manifest.py --bump patch
"""

import os
import json
import argparse
import hashlib

# ------------------------------------------------------------------------------
# Exclude specific files and folders from the manifest
# ------------------------------------------------------------------------------
# These files are not relevant for deployment:
# - This script itself (generate_manifest.py)
# - Git internals (.git/)
# - Python bytecode cache (__pycache__/)
# 
# Note: We no longer exclude version.txt or manifest.json, so that they are
# included in the OTA update and rollback lifecycle.
EXCLUDE = {
    "generate_manifest.py",
    ".git",
    "__pycache__"
}

# ------------------------------------------------------------------------------
# File extensions we treat as plain text.
# This enables line-ending normalization for consistent hashing.
# ------------------------------------------------------------------------------
TEXT_EXTENSIONS = (".py", ".txt", ".json", ".md")

def sha256sum(path):
    """
    Computes the SHA-256 hash of a file.

    For text-based files (e.g., .py, .txt), this function normalizes line endings
    from Windows-style \r\n to Unix-style \n — which is essential to ensure that
    identical content across platforms produces the same hash.

    Args:
        path (str): Absolute or relative path to the file.

    Returns:
        str: Lowercase hexadecimal SHA-256 hash string.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        content = f.read()
        if path.endswith(TEXT_EXTENSIONS):
            content = content.replace(b"\r\n", b"\n")
        h.update(content)
    return h.hexdigest()

def collect_files(root):
    """
    Recursively collect all valid files in the given root directory,
    excluding hidden and explicitly ignored files and folders.
    
    Also excludes 'manifest.json' itself from being included in the hash
    list to prevent circular references during OTA verification.

    Returns:
        dict: { relative_path: { "sha256": ..., "size": ... } }
    """
    result = {}
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if fname == "manifest.json":
                continue  # 🚫 Avoid including manifest.json inside itself
            if fname in EXCLUDE or fname.startswith("_") or fname.startswith("."):
                continue
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, root).replace("\\", "/")
            result[rel] = {
                "sha256": sha256sum(full),
                "size": os.path.getsize(full)
            }
    return result

def bump_version(current, level):
    """
    Increments a semantic version string (e.g. 1.2.3) based on the requested bump level.

    Args:
        current (str): Existing version string, e.g. "0.3.2"
        level (str): One of "patch", "minor", or "major"

    Returns:
        str: New version string after increment
    """
    major, minor, patch = map(int, current.strip().split("."))
    return {
        "major": f"{major+1}.0.0",
        "minor": f"{major}.{minor+1}.0",
        "patch": f"{major}.{minor}.{patch+1}"
    }[level]

def main():
    # ------------------------------------------------------------------------------
    # Parse command-line argument: --bump patch|minor|major
    # Default bump level is "patch" if no flag is provided.
    # ------------------------------------------------------------------------------
    parser = argparse.ArgumentParser(description="Generate manifest.json and version.txt for OTA firmware deployment.")
    parser.add_argument("--bump", choices=["major", "minor", "patch"], default="patch",
                        help="Specify which part of the version to increment (default: patch)")
    args = parser.parse_args()

    # ------------------------------------------------------------------------------
    # Load the current firmware version from version.txt (or default to 0.0.0)
    # ------------------------------------------------------------------------------
    current = "0.0.0"
    if os.path.exists("version.txt"):
        with open("version.txt") as f:
            current = f.read().strip()

    new_version = bump_version(current, args.bump)
    print(f"🔄 Bumping version: {current} → {new_version}")

    # ------------------------------------------------------------------------------
    # Write the updated version to version.txt BEFORE scanning files
    # This ensures it's included in the manifest and checksummed.
    # ------------------------------------------------------------------------------
    with open("version.txt", "w") as f:
        f.write(new_version)

    # ------------------------------------------------------------------------------
    # Collect all valid files in the current directory for inclusion in manifest
    # This will now include version.txt and manifest.json itself, ensuring these are
    # tracked and rollback-safe.
    # ------------------------------------------------------------------------------
    files = collect_files(".")
    if not files:
        print("⚠️ No valid files found to include in manifest.")
        return

    # ------------------------------------------------------------------------------
    # Construct manifest dictionary and write it to manifest.json (formatted)
    # ------------------------------------------------------------------------------
    manifest_data = {
        "version": new_version,
        "files": files
    }

    with open("manifest.json", "w") as f:
        json.dump(manifest_data, f, indent=2)

    print(f"📦 Wrote manifest.json with {len(files)} files.")
    print(f"✅ Updated version.txt to {new_version}")

    # ------------------------------------------------------------------------------
    # Output a summary of included files for verification and debugging
    # ------------------------------------------------------------------------------
    print("\n📋 Included files:")
    for fpath in sorted(files):
        print(f"   • {fpath} ({files[fpath]['size']} bytes)")

if __name__ == "__main__":
    main()