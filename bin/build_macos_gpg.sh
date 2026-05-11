#!/usr/bin/env bash

set -euo pipefail


VER_GPG_ERROR="1.50"
VER_GCRYPT="1.11.0"
VER_ASSUAN="3.0.1"
VER_KSBA="1.6.7"
VER_NPTH="1.8"
VER_PINENTRY="1.3.1"
VER_GNUPG="2.4.7"


SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$REPO_ROOT/build/macos_gpg"
OUT_DIR="$REPO_ROOT/src/partizan_gpg/cipherlib/bundled/macos"

PREFIX="/tmp/gnupg_shim"

ARCH_ARM="arm64"
ARCH_X86="x86_64"
BUILD_ARM="$BUILD_DIR/arm64"
BUILD_X86="$BUILD_DIR/x86_64"
BUILD_UNI="$BUILD_DIR/universal"

mkdir -p "$BUILD_ARM" "$BUILD_X86" "$BUILD_UNI" "$OUT_DIR"

BOLD='\033[1m'
GREEN='\033[0;32m'
RESET='\033[0m'

log()  { echo -e "${BOLD}==> $*${RESET}"; }
ok()   { echo -e "${GREEN}     ✔ $*${RESET}"; }

download() {
    local url="$1" dest="$2"
    if [[ ! -f "$dest" ]]; then
        log "Downloading $(basename "$dest")"
        curl -fsSL "$url" -o "$dest"
    else
        ok "Already downloaded $(basename "$dest")"
    fi
}
verify_sha256() {
    local file="$1" expected="$2"
    local actual
    actual=$(shasum -a 256 "$file" | awk '{print $1}')
    if [[ "$actual" != "$expected" ]]; then
        echo "SHA256 mismatch for $file"
        echo "  expected: $expected"
        echo "  actual:   $actual"
        exit 1
    fi
    ok "SHA256 verified: $(basename "$file")"
}

build_arch() {
    local srcdir="$1" arch="$2" prefix="$3"
    shift 3
    local extra_args=("$@")

    local sdk
    sdk=$(xcrun --sdk macosx --show-sdk-path)

    local host
    if [[ "$arch" == "arm64" ]]; then
        host="aarch64-apple-darwin"
    else
        host="x86_64-apple-darwin"
    fi

    local cflags="-arch $arch -isysroot $sdk -mmacosx-version-min=12.0 -O2"
    local ldflags="-arch $arch -isysroot $sdk"

    mkdir -p "$prefix"

    ( 
        cd "$srcdir"
        ./configure \
            --prefix="$prefix" \
            --host="$host" \
            --enable-static \
            --disable-shared \
            --disable-doc \
            --disable-nls \
            CFLAGS="$cflags" \
            LDFLAGS="$ldflags" \
            PKG_CONFIG_PATH="$prefix/lib/pkgconfig" \
            "${extra_args[@]}"
        make -j"$(sysctl -n hw.logicalcpu)"
        make install
    )
}

lipo_merge() {
    local name="$1"
    local arm_file="$BUILD_ARM/$PREFIX/$name"
    local x86_file="$BUILD_X86/$PREFIX/$name"
    local out_file="$BUILD_UNI/$name"

    mkdir -p "$(dirname "$out_file}")"
    lipo -create "$arm_file" "$x86_file" -output "$out_file"
    ok "lipo → $name"
}

log "Installing build tools"
brew install autoconf automake libtool pkg-config gettext || true
export PATH="$(brew --prefix gettext)/bin:$PATH"

SOURCES="$BUILD_DIR/sources"
mkdir -p "$SOURCES"

BASE_FTP="https://gnupg.org/ftp/gcrypt"

download "$BASE_FTP/libgpg-error/libgpg-error-${VER_GPG_ERROR}.tar.bz2" \
    "$SOURCES/libgpg-error-${VER_GPG_ERROR}.tar.bz2"

download "$BASE_FTP/libgcrypt/libgcrypt-${VER_GCRYPT}.tar.bz2" \
    "$SOURCES/libgcrypt-${VER_GCRYPT}.tar.bz2"

download "$BASE_FTP/libassuan/libassuan-${VER_ASSUAN}.tar.bz2" \
    "$SOURCES/libassuan-${VER_ASSUAN}.tar.bz2"

download "$BASE_FTP/libksba/libksba-${VER_KSBA}.tar.bz2" \
    "$SOURCES/libksba-${VER_KSBA}.tar.bz2"

download "$BASE_FTP/npth/npth-${VER_NPTH}.tar.bz2" \
    "$SOURCES/npth-${VER_NPTH}.tar.bz2"

download "$BASE_FTP/pinentry/pinentry-${VER_PINENTRY}.tar.bz2" \
    "$SOURCES/pinentry-${VER_PINENTRY}.tar.bz2"

download "$BASE_FTP/gnupg/gnupg-${VER_GNUPG}.tar.bz2" \
    "$SOURCES/gnupg-${VER_GNUPG}.tar.bz2"


build_component() {
    local name="$1" tarball="$2"
    shift 2
    local extra_args=("$@")

    log "Building $name"

    for arch in "$ARCH_ARM" "$ARCH_X86"; do
        local arch_build
        if [[ "$arch" == "arm64" ]]; then
            arch_build="$BUILD_ARM"
        else
            arch_build="$BUILD_X86"
        fi

        local srcdir="$arch_build/src/$name"
        local prefix="$arch_build/$PREFIX"

        if [[ -f "$prefix/lib/${name}.a" ]] || \
           [[ -f "$prefix/bin/gpg" && "$name" == "gnupg" ]]; then
           ok "$name ($arch) already built - skipping"
           continue
        fi

        mkdir -p "$srcdir"
        tar -xjf "$tarball" -C "$srcdir" --strip-components=1

        build_arch "$srcdir" "$arch" "$prefix" "${extra_args[@]}"
        ok "$name built for $arch"
    done
}

build_component "libgpg-error" \
    "$SOURCES/libgpg-error-${VER_GPG_ERROR}.tar.bz2" \
    --disable-languages \
    --disable-tests

build_component "libgcrypt" \
    "$SOURCES/libgcrypt-${VER_GCRYPT}.tar.bz2" \
    --disable-tests \
    --with-libgpg-error-prefix="\$prefix"   # resolved per-arch in build_arch

build_component "libassuan" \
    "$SOURCES/libassuan-${VER_ASSUAN}.tar.bz2"

build_component "libksba" \
    "$SOURCES/libksba-${VER_KSBA}.tar.bz2"

build_component "npth" \
    "$SOURCES/npth-${VER_NPTH}.tar.bz2"

build_component "pinentry" \
    "$SOURCES/pinentry-${VER_PINENTRY}.tar.bz2" \
    --enable-pinentry-tty \
    --disable-pinentry-curses \
    --disable-pinentry-gtk2 \
    --disable-pinentry-gnome3 \
    --disable-pinentry-qt

build_component "gnupg" \
    "$SOURCES/gnupg-${VER_GNUPG}.tar.bz2" \
    --disable-scdaemon \
    --disable-dirmngr \
    --enable-gpg \
    --enable-gpgv \
    --enable-agent \
    --with-pinentry-pgm="$PREFIX/bin/pinentry"

# -----------------------------------------------------------------------------
# lipo everything into universal binaries
# -----------------------------------------------------------------------------
log "Creating universal binaries"

BINARIES=(
    "bin/gpg"
    "bin/gpg-agent"
    "bin/gpgconf"
    "bin/gpg-connect-agent"
    "bin/gpgv"
    "bin/pinentry"
)

for bin in "${BINARIES[@]}"; do
    lipo_merge "$bin"
done

log "Copying to output: $OUT_DIR"

mkdir -p "$OUT_DIR/bin"

for bin in "${BINARIES[@]}";do
    dest_name=$(basename "$bin")
    cp "$BUILD_UNI/$bin" "$OUT_DIR/bin/$dest_name"
    chmod +x "$OUT_DIR/bin/$dest_name"
    ok "→ $OUT_DIR/bin/$dest_name"
done

cat > "$OUT_DIR/versions.txt" <<EOF
libgpg-error    $VER_GPG_ERROR
libgcrypt       $VER_GCRYPT
libassuan       $VER_ASSUAN
libksba         $VER_KSBA
npth            $VER_NPTH
pinentry        $VER_PINENTRY
gnupg           $VER_GNUPG
built:          $(date -u +"%Y-%m-%dT%H:%M:%SZ")
arch:           universal (arm64 + x86_64)
EOF

log "Build complete"
echo ""
echo "  Output dir: $OUT_DIR"
echo "  GPG version: $("$OUT_DIR/bin/gpg" --version | head -1)"
echo ""