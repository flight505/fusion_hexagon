#!/bin/bash
# deploy.sh — Helper for registering Hexagon in Fusion 360.

cat <<'EOF'
Hexagon does not use a deploy step.

To install (first time only):
  1. Open Fusion 360
  2. Shift+S → Scripts and Add-Ins
  3. Click the "+" button
  4. Navigate to /Users/jesper/Projects/3Dprint/Hexagon
  5. Select the folder and click Open

After that, just edit HexagonGenerator.py in this folder. Toggle Run off/on
in the Scripts and Add-Ins dialog to reload after changes.
EOF
