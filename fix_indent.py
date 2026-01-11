#!/usr/bin/env python3
import sys

def fix_file(filename):
    with open(filename, 'r') as f:
        content = f.read()
    fixed = content.replace('\t', '    ')
    with open(filename, 'w') as f:
        f.write(fixed)
    print(f"✅ Fixed: {filename}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        fix_file(sys.argv[1])
