VERSION="填写你在 release 页看到的版本号"
ARCHIVE="uv-x86_64-unknown-linux-gnu.tar.gz"

curl -L -o "$ARCHIVE" "https://github.com/astral-sh/uv/releases/download/$VERSION/$ARCHIVE"
tar -xzf "$ARCHIVE"

mkdir -p "$HOME/.local/bin"
install -m 755 uv-x86_64-unknown-linux-gnu/uv "$HOME/.local/bin/uv"

export PATH="$HOME/.local/bin:$PATH"
uv --version
