#!/usr/bin/env python3
"""Fix blog flickering: update build-version + add reload guard to version check script."""
import os
import re
import glob

BLOG_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_VERSION = "2026-06-21T08:00"

# Old version check script (the buggy one)
OLD_SCRIPT = """(function(){
  var bv = document.querySelector('meta[name="build-version"]');
  var cur = bv ? bv.content : '';
  fetch('/version.json', {cache:'no-store'})
    .then(function(r){ return r.json(); })
    .then(function(d){
      if(d.version && d.version !== cur){
        location.replace(location.href.split('?')[0] + '?v=' + d.version);
      }
    })
    .catch(function(){});
})();"""

# New version check script with reload guard
NEW_SCRIPT = """(function(){
  // Reload guard: if URL already has ?v= param, skip to prevent infinite loop
  var urlParams = new URLSearchParams(window.location.search);
  if(urlParams.get('v')) return;
  var bv = document.querySelector('meta[name="build-version"]');
  var cur = bv ? bv.content : '';
  fetch('/version.json', {cache:'no-store'})
    .then(function(r){ return r.json(); })
    .then(function(d){
      if(d.version && d.version !== cur){
        location.replace(location.href.split('?')[0] + '?v=' + d.version);
      }
    })
    .catch(function(){});
})();"""

# Find all HTML files
html_files = []
for pattern in ['*.html', 'posts/*.html', 'blog_posts/*.html']:
    html_files.extend(glob.glob(os.path.join(BLOG_DIR, pattern)))

html_files = list(set(html_files))  # dedupe

updated_version = 0
updated_script = 0

for filepath in sorted(html_files):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    changed = False

    # 1. Update build-version meta tag to match version.json
    content = re.sub(
        r'<meta name="build-version" content="[^"]*">',
        f'<meta name="build-version" content="{TARGET_VERSION}">',
        content
    )

    # 2. Replace the buggy version check script with the fixed one
    if OLD_SCRIPT in content:
        content = content.replace(OLD_SCRIPT, NEW_SCRIPT)
        updated_script += 1
        changed = True

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        changed = True

    if changed:
        updated_version += 1
        print(f"  Fixed: {os.path.relpath(filepath, BLOG_DIR)}")

print(f"\nTotal files updated: {updated_version}")
print(f"Scripts fixed: {updated_script}")
