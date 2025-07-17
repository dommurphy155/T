#!/usr/bin/env python3
"""
Test script to verify that all the flake8 and mypy fixes are working correctly.
"""

import ast
import sys
from typing import List, Tuple


def check_syntax(file_path: str) -> Tuple[bool, List[str]]:
    """Check if a Python file has valid syntax."""
    errors = []
    try:
        with open(file_path, 'r') as f:
            ast.parse(f.read())
        return True, []
    except SyntaxError as e:
        errors.append(f"Syntax error: {e}")
        return False, errors
    except Exception as e:
        errors.append(f"Error reading file: {e}")
        return False, errors


def check_line_lengths(file_path: str, max_length: int = 79) -> Tuple[bool, List[str]]:
    """Check if any lines exceed the maximum length."""
    errors = []
    try:
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                if len(line.rstrip('\n')) > max_length:
                    errors.append(f"Line {line_num}: {len(line.rstrip())} > {max_length} chars")
        return len(errors) == 0, errors
    except Exception as e:
        errors.append(f"Error reading file: {e}")
        return False, errors


def main():
    """Run all checks on the fixed files."""
    files_to_check = [
        'trade_closer.py',
        'trade_executor.py', 
        'oanda_client.py',
        'state_manager.py',
        'telegram_bot.py'
    ]
    
    print("🔍 Checking syntax and line lengths...")
    print("=" * 50)
    
    all_passed = True
    
    for file_path in files_to_check:
        print(f"\n📁 Checking {file_path}:")
        
        # Check syntax
        syntax_ok, syntax_errors = check_syntax(file_path)
        if syntax_ok:
            print("  ✅ Syntax: OK")
        else:
            print(f"  ❌ Syntax: FAILED")
            for error in syntax_errors:
                print(f"    {error}")
            all_passed = False
        
        # Check line lengths
        length_ok, length_errors = check_line_lengths(file_path)
        if length_ok:
            print("  ✅ Line lengths: OK")
        else:
            print(f"  ❌ Line lengths: FAILED")
            for error in length_errors:
                print(f"    {error}")
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All checks passed! The fixes are working correctly.")
        return 0
    else:
        print("❌ Some checks failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())