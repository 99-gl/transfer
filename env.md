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

cd $HOME

wget https://www.python.org/ftp/python/3.12.13/Python-3.12.13.tar.xz
tar -xf Python-3.12.13.tar.xz
cd Python-3.12.13

./configure --prefix=$HOME/.local/python-3.12
make -j$(nproc)
make install

export PATH="$HOME/.local/python-3.12/bin:$PATH"

python3.12 --version
python3.12 -m pip --version

cd /path/to/verl
python3.12 -m venv .venv
source .venv/bin/activate
pip install -U pip uv