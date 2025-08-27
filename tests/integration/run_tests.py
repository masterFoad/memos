#!/usr/bin/env python3
"""
OnMemOS v3 Test Runner
Run tests by category: unit, integration, e2e, performance, security, bucket
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

def run_tests(category=None, verbose=False):
    """Run tests by category"""
    test_dir = Path(__file__).parent / "tests"
    
    if category:
        # Run specific category
        category_dir = test_dir / category
        if not category_dir.exists():
            print(f"❌ Category '{category}' not found")
            return False
        
        cmd = ["python", "-m", "pytest", str(category_dir)]
        if verbose:
            cmd.append("-v")
        
        print(f"🧪 Running {category} tests...")
        result = subprocess.run(cmd)
        return result.returncode == 0
    else:
        # Run all tests
        print("🧪 Running all tests...")
        cmd = ["python", "-m", "pytest", str(test_dir)]
        if verbose:
            cmd.append("-v")
        
        result = subprocess.run(cmd)
        return result.returncode == 0

def list_categories():
    """List available test categories"""
    test_dir = Path(__file__).parent / "tests"
    categories = [d.name for d in test_dir.iterdir() if d.is_dir() and d.name != "__pycache__"]
    print("📁 Available test categories:")
    for cat in sorted(categories):
        print(f"  - {cat}")

def main():
    parser = argparse.ArgumentParser(description="OnMemOS v3 Test Runner")
    parser.add_argument("category", nargs="?", help="Test category to run")
    parser.add_argument("--list", action="store_true", help="List available categories")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.list:
        list_categories()
        return
    
    success = run_tests(args.category, args.verbose)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
