#!/bin/bash

set -euo pipefail

APP_NAME="Partizan Guard GPG"
BINARY_NAME="partizan-gpg"
BUNDLE_ID="com.partizan.gpg"
VERSION="${1:-$(poetry version -s 2>/dev/null || echo '0.0.0')}"
# ICON_PATH=

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$REPO_ROOT/dist"
APP_DIR="$DIST_DIR/${APP_NAME}.app"
DMG_OUT="$DIST_DIR/${BINARY_NAME}-${VERSION}.dmg"
DMG_STAGING="$DIST_DIR/dmg-staging"

echo "==> Building PYInstaller binary..."
cd "$REPO_ROOT"
poetry run pyinstaller partizan_gpg.spec

echo "==> Creating .app bundle at: $APP_DIR"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

cp "$DIST_DIR/$BINARY_NAME" "$APP_DIR/Contents/Resources/$BINARY_NAME"
chmod +x "$APP_DIR/Contents/Resources/$BINARY_NAME"

cat > "$APP_DIR/Contents/MacOS/launcher" << 'LAUNCHER'
#!/bin/bash

BINARY="$(dirname "$0")/../Resources/partizan-gpg"
BINARY="$(cd "$(dirname "$BINARY")" && pwd)/$(basename "$BINARY")"

osascript - "$BINARY" << 'APPLESCRIPT'
on run argv
    set binaryPath to item 1 of argv
    tell application "Terminal"
        activate
        do script quoted form of binaryPath
    end tell
end run
APPLESCRIPT
LAUNCHER

chmod +x "$APP_DIR/Contents/MacOS/launcher"

cat > "$APP_DIR/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plit PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>

    <key>CFBundleDisplayName</key>
    <string>${APP_NAME}</string>

    <key>CFBundleIdentifier</key>
    <string>${BUNDLE_ID}</string>

    <key>CFBundleVersion</key>
    <string>${VERSION}</string>

    <key>CFBundleShortVersionString</key>
    <string>${VERSION}</string>

    <key>CFBundleExecutable</key>
    <string>launcher</string>

    <key>CFBundlePackageType</key>
    <string>APPL</string>

    <key>CFBundleSignature</key>
    <string>????</string>

    <key>NSHighResolutionCapable</key>
    <true/>

    <key>LSUIElement</key>
    <true/>

    <key>NSHumanReadableCopyright</key>
    <string>Copyright © 2026 Dylan Garrett. MIT License</string>
</dict>
</plist>
PLIST


echo "==> Building DMG: $DMG_OUT"
rm -f "$DMG_OUT"
rm -rf "$DMG_STAGING"
mkdir -p "$DMG_STAGING"
cp -r "$APP_DIR" "$DMG_STAGING/"

create-dmg \
    --volname "${APP_NAME}" \
    --window-pos 200 120 \
    --window-size 640 400 \
    --icon-size 128 \
    --hide-extension "${APP_NAME}.app" \
    --app-drop-link 480 185 \
    --no-internet-enable \
    "$DMG_OUT" \
    "$DMG_STAGING/"

rm -rf "$DMG_STAGING"

echo ""
echo "✅ Done!"
echo "      App bundle : $APP_DIR"
echo "      DMG        : $DMG_OUT"
echo ""
echo "NOTE: This build is unsigned. macOS Gatekeeper will quarantine it for"
echo "      users who downloaded it from the internet. They can unlock it with:"
echo "      xattr -d com.apple.quarantine '${APP_NAME}.app'"
echo "      OR: System Settings -> Privacy & Security -> Open Anyway"
