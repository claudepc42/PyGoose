#!/bin/bash
DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
xattr -cr "$DIR/PyGoose" 2>/dev/null || true
nohup "$DIR/PyGoose" > /dev/null 2>&1 &
disown $!
