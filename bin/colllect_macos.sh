#!/bin/bash
set -e

GPG_BIN=$(which gpg)
OUT_DIR="src/partizan_gpg/cipherlib/bundled/macos"
LIB_DIR="$OUT_DIR/lib"

mkdir -p "$OUT_DIR" "$LIB_DIR"

cp "$GPG_BIN" "$OUT_DIR/gpg"
chmod +x "$OUT_DIR/gpg"

collect_libs() {
    local binary="$1"
    otool -L "$binary" | awk `NR>1 {print $1}` | while read -r lib; do
        [[ "$lib" == /usr/lib/* ]] && continue
        [[ "$lib" == /System/* ]] && continue
        [[ ! -f "$lib" ]] && continue

        filename=$(basename "$lib")
        dest="$LIB_DIR/$filename"

        if [[ ! -f "$dest" ]]; then
            echo " copying $lib"
            cp "$lib" "$dest"
            chmod +w "$dest"
            collect_libs "$dest"
        fi
    done
}

echo "Collecting dylibs for: $GPG_BIN"
collect_libs "$GPG_BIN"

echo "Rewriting install names..."

for lib in "$LIB_DIR"/*.dylib; do
    filename=$(basename "$lib") 
    install_name_tool -change \
        "$(otool -L "$OUT_DIR/gpg" | grep "$filename" | awk `{print $1}`)" \
        "@executable_path/lib/$filename" \
        "$OUT_DIR/gpg" 2>/dev/null || true

    for dep in "$LIB_DIR"/*.dylib; do
        depname=$(basename "$dep")
        install_name_tool -change \
            "$(otool -L "$lib" | grep "$depname" | awk `{print $1}`)" \
            "@loader_path/$depname" \
            "$lib" 2>/dev/null || true
    done
done

echo "Done. Contents of $OUT_DIR:"
ls -lh "$OUT_DIR"
echo ""
echo "Libs:"
ls -lh "$LIB_DIR"
