#!/bin/bash
# Pack icons are the same models rendered from a single view, so an icon can
# never drift from what is inside. Resource pack, the white ball, behavior
# pack, the enraged monster: both are told apart at a glance in world settings.
set -euo pipefail
cd "$(dirname "$0")/.."

CALM="eyes_closed,eyes_worried,brows,mouth_open"
HURT="eyes_open,eyes_closed,mouth_line"

python3 art/render_geo.py --views "three-quarter" --tile 256 --hide "$CALM" \
  --out bedrock/resource_pack/pack_icon.png
python3 art/render_geo.py --views "three-quarter" --tile 256 --hide "$HURT" \
  --identifier geometry.friend_night --texture friend_angry \
  --out bedrock/behavior_pack/pack_icon.png

echo "icons: ball (RP) and monster (BP), 256x256"
