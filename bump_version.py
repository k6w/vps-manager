#!/usr/bin/env python3
"""
Version Bumping Utility for VPS Manager

Usage:
    python bump_version.py [patch|minor|major]
    
Examples:
    python bump_version.py patch    # 1.2.0 -> 1.2.1
    python bump_version.py minor    # 1.2.0 -> 1.3.0
    python bump_version.py major    # 1.2.0 -> 2.0.0
"""

import sys
import re
from pathlib import Path

def get_current_version():
    """Extract current version from VERSION file"""
    version_file = Path(__file__).parent / "VERSION"
    with open(version_file, "r", encoding="utf-8") as f:
        return f.read().strip()

def bump_version(current_version, bump_type):
    """Calculate new version based on bump type"""
    major, minor, patch = map(int, current_version.split("."))
    
    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")
    
    return f"{major}.{minor}.{patch}"

def update_version_in_script(new_version):
    """No longer needed - version is read from VERSION file"""
    pass

def update_version_file(new_version):
    """Update VERSION file"""
    version_file = Path(__file__).parent / "VERSION"
    with open(version_file, "w") as f:
        f.write(new_version)

def main():
    if len(sys.argv) != 2:
        print("Usage: python bump_version.py [patch|minor|major]")
        print("\\nExamples:")
        print("  python bump_version.py patch    # 1.2.0 -> 1.2.1")
        print("  python bump_version.py minor    # 1.2.0 -> 1.3.0")
        print("  python bump_version.py major    # 1.2.0 -> 2.0.0")
        sys.exit(1)
    
    bump_type = sys.argv[1].lower()
    if bump_type not in ["patch", "minor", "major"]:
        print(f"Error: Invalid bump type \"{bump_type}\". Use patch, minor, or major.")
        sys.exit(1)
    
    try:
        # Get current version
        current_version = get_current_version()
        print(f"Current version: {current_version}")
        
        # Calculate new version
        new_version = bump_version(current_version, bump_type)
        print(f"New version: {new_version}")
        
        # Update files
        print("Updating VERSION file...")
        update_version_file(new_version)
        
        print(f"✅ Version successfully bumped from {current_version} to {new_version}")
        print("\\nNext steps:")
        print("1. Test the application")
        print("2. Commit changes: git add . && git commit -m \"Bump version to {}\"" .format(new_version))
        print("3. Create tag: git tag v{}".format(new_version))
        print("4. Push changes: git push && git push --tags")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
