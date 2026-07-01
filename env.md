## uv
VERSION="0.11.25"
ARCHIVE="uv-x86_64-unknown-linux-gnu.tar.gz"

wget -O "$ARCHIVE" "https://github.com/astral-sh/uv/releases/download/$VERSION/$ARCHIVE"
tar -xzf "$ARCHIVE"

mkdir -p "$HOME/.local/bin"
install -m 755 uv-x86_64-unknown-linux-gnu/uv "$HOME/.local/bin/uv"

export PATH="$HOME/.local/bin:$PATH"
uv --version

## python

wget https://github.com/astral-sh/python-build-standalone/releases/download/20241016/cpython-3.11.10+20241016-x86_64-unknown-linux-gnu-install_only.tar.gz

tar -xzf cpython-3.11.10+20241016-x86_64-unknown-linux-gnu-install_only.tar.gz -C ~/python3.11

uv venv --python ~/python3.11/python/bin/python3.11
source .venv/bin/activate
