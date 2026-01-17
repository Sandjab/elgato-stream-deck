#!/bin/bash
# Script de téléchargement des images officielles des Stream Deck
#
# Usage: ./download-streamdeck-images.sh
#
# Ce script télécharge les images des produits Stream Deck depuis les sources officielles
# et les redimensionne à une taille uniforme (300x300) pour la documentation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGES_DIR="${SCRIPT_DIR}/../docs/images"
TEMP_DIR="/tmp/streamdeck-images"
TARGET_SIZE="300x300"

# Couleurs pour les messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Vérifier les dépendances
check_dependencies() {
    local missing=()

    if ! command -v curl &> /dev/null; then
        missing+=("curl")
    fi

    if ! command -v convert &> /dev/null; then
        missing+=("imagemagick")
    fi

    if [ ${#missing[@]} -ne 0 ]; then
        log_error "Dépendances manquantes: ${missing[*]}"
        echo ""
        echo "Installation:"
        echo "  macOS:   brew install ${missing[*]}"
        echo "  Ubuntu:  sudo apt install ${missing[*]}"
        exit 1
    fi
}

# Créer les répertoires
setup_directories() {
    mkdir -p "$IMAGES_DIR"
    mkdir -p "$TEMP_DIR"
    log_info "Répertoires créés"
}

# Télécharger une image
download_image() {
    local url="$1"
    local output="$2"
    local name="$3"

    log_info "Téléchargement: $name"

    if curl -sL -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)" \
            --max-time 30 \
            -o "$output" \
            "$url"; then
        log_info "  ✓ Téléchargé: $name"
        return 0
    else
        log_warn "  ✗ Échec: $name"
        return 1
    fi
}

# Redimensionner une image
resize_image() {
    local input="$1"
    local output="$2"
    local size="$3"

    if [ -f "$input" ]; then
        convert "$input" \
            -resize "${size}^" \
            -gravity center \
            -extent "$size" \
            -quality 90 \
            "$output"
        return 0
    fi
    return 1
}

# Sources des images officielles Elgato
# Note: Ces URLs peuvent changer. Mettez à jour si nécessaire.
declare -A IMAGE_SOURCES=(
    # Les URLs ci-dessous sont des exemples.
    # Pour les images officielles, visitez:
    # - https://www.elgato.com/us/en/p/stream-deck (Original)
    # - https://www.elgato.com/us/en/p/stream-deck-mini (Mini)
    # - https://www.elgato.com/us/en/p/stream-deck-xl (XL)
    # - https://www.elgato.com/us/en/p/stream-deck-plus (Plus)
    # - https://www.elgato.com/us/en/p/stream-deck-neo (Neo)
)

# Téléchargement manuel recommandé
manual_download_instructions() {
    cat << 'EOF'

╔══════════════════════════════════════════════════════════════════════════════╗
║                    TÉLÉCHARGEMENT MANUEL DES IMAGES                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Les images officielles doivent être téléchargées manuellement depuis        ║
║  le site d'Elgato pour des raisons de droits d'auteur.                       ║
║                                                                              ║
║  1. Visitez les pages produits suivantes:                                    ║
║                                                                              ║
║     Stream Deck (Original):                                                  ║
║     → https://www.elgato.com/us/en/p/stream-deck                             ║
║                                                                              ║
║     Stream Deck Mini:                                                        ║
║     → https://www.elgato.com/us/en/p/stream-deck-mini                        ║
║                                                                              ║
║     Stream Deck XL:                                                          ║
║     → https://www.elgato.com/us/en/p/stream-deck-xl                          ║
║                                                                              ║
║     Stream Deck + (Plus):                                                    ║
║     → https://www.elgato.com/us/en/p/stream-deck-plus                        ║
║                                                                              ║
║     Stream Deck Neo:                                                         ║
║     → https://www.elgato.com/us/en/p/stream-deck-neo                         ║
║                                                                              ║
║  2. Faites un clic droit sur l'image du produit → "Enregistrer l'image"      ║
║                                                                              ║
║  3. Enregistrez les images dans: docs/images/                                ║
║     avec les noms suivants:                                                  ║
║       - streamdeck-original.png                                              ║
║       - streamdeck-mini.png                                                  ║
║       - streamdeck-xl.png                                                    ║
║       - streamdeck-plus.png                                                  ║
║       - streamdeck-neo.png                                                   ║
║                                                                              ║
║  4. Redimensionnez les images à 300x300 pixels (optionnel):                  ║
║     convert input.png -resize 300x300^ -gravity center \                     ║
║             -extent 300x300 output.png                                       ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

EOF
}

# Vérifier si les images existent déjà
check_existing_images() {
    local models=("original" "mini" "xl" "plus" "neo")
    local existing=0
    local missing=0

    echo ""
    log_info "Vérification des images existantes..."
    echo ""

    for model in "${models[@]}"; do
        local file="${IMAGES_DIR}/streamdeck-${model}.png"
        if [ -f "$file" ]; then
            echo "  ✓ streamdeck-${model}.png"
            ((existing++))
        else
            echo "  ✗ streamdeck-${model}.png (manquant)"
            ((missing++))
        fi
    done

    echo ""
    log_info "Résumé: $existing images trouvées, $missing manquantes"

    return $missing
}

# Créer des placeholders si les images n'existent pas
create_placeholders() {
    local models=("original:15 touches (5×3)" "mini:6 touches (3×2)" "xl:32 touches (8×4)" "plus:8 touches + 4 molettes" "neo:8 touches + Infobar")

    log_info "Création des placeholders..."

    for model_info in "${models[@]}"; do
        local model="${model_info%%:*}"
        local desc="${model_info#*:}"
        local file="${IMAGES_DIR}/streamdeck-${model}.png"

        if [ ! -f "$file" ]; then
            # Créer un placeholder avec ImageMagick
            convert -size 300x300 xc:'#1a1a2e' \
                -fill '#16213e' -draw "roundrectangle 20,20 280,280 15,15" \
                -fill '#e94560' -font Helvetica -pointsize 20 \
                -gravity center -annotate +0-30 "Stream Deck" \
                -fill '#ffffff' -pointsize 16 \
                -annotate +0+10 "${model^^}" \
                -fill '#888888' -pointsize 12 \
                -annotate +0+40 "$desc" \
                "$file" 2>/dev/null || {
                    # Fallback: créer une image simple si la première commande échoue
                    convert -size 300x300 xc:'#333333' \
                        -fill white -gravity center \
                        -annotate 0 "Stream Deck ${model^^}" \
                        "$file" 2>/dev/null || true
                }

            if [ -f "$file" ]; then
                log_info "  Placeholder créé: streamdeck-${model}.png"
            fi
        fi
    done
}

# Main
main() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║     Script de téléchargement des images Stream Deck          ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""

    check_dependencies
    setup_directories

    if ! check_existing_images; then
        manual_download_instructions

        echo ""
        read -p "Voulez-vous créer des placeholders pour les images manquantes? [o/N] " -n 1 -r
        echo ""

        if [[ $REPLY =~ ^[Oo]$ ]]; then
            create_placeholders
        fi
    else
        log_info "Toutes les images sont présentes!"
    fi

    echo ""
    log_info "Terminé."
}

main "$@"
