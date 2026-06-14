#!/bin/sh
set -e

VERSION="0.2.0"
REPO="Satyam12singh/repolens"
BIN_DIR="${HOME}/.local/bin"

OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case "$OS" in
  darwin)
    case "$ARCH" in
      arm64)   BINARY="repolens-macos-arm64" ;;
      x86_64)  BINARY="repolens-macos-x64" ;;
      *) echo "Unsupported architecture: $ARCH" && exit 1 ;;
    esac
    ;;
  linux)
    case "$ARCH" in
      x86_64)  BINARY="repolens-linux-x64" ;;
      *) echo "Unsupported architecture: $ARCH" && exit 1 ;;
    esac
    ;;
  *)
    echo "Unsupported OS. On Windows download from:"
    echo "https://github.com/$REPO/releases/latest"
    exit 1
    ;;
esac

URL="https://github.com/$REPO/releases/download/v$VERSION/$BINARY"

mkdir -p "$BIN_DIR"
echo "Downloading repolens v$VERSION..."
curl -fsSL "$URL" -o "$BIN_DIR/repolens"
chmod +x "$BIN_DIR/repolens"

echo ""
echo "Installed to $BIN_DIR/repolens"

if ! echo "$PATH" | grep -q "$BIN_DIR"; then
  echo ""
  echo "Add this to your shell profile (~/.zshrc or ~/.bashrc):"
  echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
