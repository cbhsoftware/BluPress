#!/usr/bin/env bash
set -euo pipefail

NAME="BluPress"
APP_DIR="${NAME}.AppDir"

echo "==> Building PyInstaller binary..."
pyinstaller BluPress.spec

echo "==> Creating AppDir structure..."
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/usr/bin"

cp "dist/${NAME}" "$APP_DIR/usr/bin/${NAME}"
cp favicon.png "$APP_DIR/${NAME}.png"
cp favicon.ico "$APP_DIR/"

cat > "$APP_DIR/${NAME}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=${NAME}
Comment=Blu-ray & DVD Compressor
Exec=${NAME}
Icon=${NAME}
Categories=AudioVideo;Video;
Terminal=false
EOF

ln -sf "${NAME}.png" "$APP_DIR/.DirIcon"

cat > "$APP_DIR/AppRun" <<'APPRUN'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"
export PATH="${HERE}/usr/bin:${PATH}"
export BLUPRESS_RESOURCES="${HERE}"
exec "${HERE}/usr/bin/BluPress" "$@"
APPRUN
chmod +x "$APP_DIR/AppRun"

echo "==> AppDir ready at: ${APP_DIR}/"
echo "==> To create AppImage, install appimagetool and run:"
echo "    appimagetool ${APP_DIR}"
echo ""
echo "    Or download from: https://github.com/AppImage/AppImageKit/releases"
