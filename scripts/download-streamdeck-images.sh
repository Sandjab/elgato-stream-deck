#!/bin/bash
# Script de téléchargement des images officielles des Stream Deck
#
# Usage: ./download-streamdeck-images.sh
#
# Ce script aide à télécharger les images des produits Stream Deck
# et les redimensionne à une taille uniforme (300x300) pour la documentation.
#
# Compatible avec bash 3.2+ (macOS par défaut)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGES_DIR="${SCRIPT_DIR}/../docs/images"
TARGET_SIZE="300x300"

# Couleurs pour les messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { printf "${GREEN}[INFO]${NC} %s\n" "$1"; }
log_warn() { printf "${YELLOW}[WARN]${NC} %s\n" "$1"; }
log_error() { printf "${RED}[ERROR]${NC} %s\n" "$1"; }

# Vérifier les dépendances
check_dependencies() {
    local has_error=0

    if ! command -v curl &> /dev/null; then
        log_error "curl n'est pas installé"
        has_error=1
    fi

    if ! command -v convert &> /dev/null; then
        log_warn "ImageMagick (convert) n'est pas installé - les placeholders ne pourront pas être créés"
    fi

    if [ $has_error -eq 1 ]; then
        echo ""
        echo "Installation:"
        echo "  macOS:   brew install curl imagemagick"
        echo "  Ubuntu:  sudo apt install curl imagemagick"
        exit 1
    fi
}

# Créer les répertoires
setup_directories() {
    mkdir -p "$IMAGES_DIR"
    log_info "Répertoire images: $IMAGES_DIR"
}

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
    local existing=0
    local missing=0

    echo ""
    log_info "Vérification des images existantes..."
    echo ""

    for model in original mini xl plus neo; do
        local file="${IMAGES_DIR}/streamdeck-${model}.png"
        if [ -f "$file" ]; then
            echo "  ✓ streamdeck-${model}.png"
            existing=$((existing + 1))
        else
            echo "  ✗ streamdeck-${model}.png (manquant)"
            missing=$((missing + 1))
        fi
    done

    echo ""
    log_info "Résumé: $existing images trouvées, $missing manquantes"

    return $missing
}

# Créer des placeholders si les images n'existent pas
create_placeholders() {
    if ! command -v convert &> /dev/null; then
        log_error "ImageMagick n'est pas installé. Impossible de créer les placeholders."
        echo "  Installation: brew install imagemagick"
        return 1
    fi

    log_info "Création des placeholders..."

    # Définir les modèles et descriptions
    create_single_placeholder "original" "ORIGINAL" "15 touches (5x3)"
    create_single_placeholder "mini" "MINI" "6 touches (3x2)"
    create_single_placeholder "xl" "XL" "32 touches (8x4)"
    create_single_placeholder "plus" "PLUS" "8 touches + 4 molettes"
    create_single_placeholder "neo" "NEO" "8 touches + Infobar"
}

create_single_placeholder() {
    local model="$1"
    local model_upper="$2"
    local desc="$3"
    local file="${IMAGES_DIR}/streamdeck-${model}.png"

    if [ -f "$file" ]; then
        return 0
    fi

    # Créer un placeholder avec ImageMagick
    if convert -size 300x300 xc:'#1a1a2e' \
        -fill '#16213e' -draw "roundrectangle 20,20 280,280 15,15" \
        -fill '#e94560' -font Helvetica -pointsize 20 \
        -gravity center -annotate +0-30 "Stream Deck" \
        -fill '#ffffff' -pointsize 16 \
        -annotate +0+10 "$model_upper" \
        -fill '#888888' -pointsize 12 \
        -annotate +0+40 "$desc" \
        "$file" 2>/dev/null; then
        log_info "  Placeholder créé: streamdeck-${model}.png"
    else
        # Fallback: créer une image simple si la première commande échoue
        if convert -size 300x300 xc:'#333333' \
            -fill white -gravity center \
            -annotate 0 "Stream Deck $model_upper" \
            "$file" 2>/dev/null; then
            log_info "  Placeholder créé (simple): streamdeck-${model}.png"
        else
            log_warn "  Échec de création: streamdeck-${model}.png"
        fi
    fi
}

# Redimensionner une image existante
resize_image() {
    local input="$1"
    local output="$2"

    if [ ! -f "$input" ]; then
        log_error "Fichier non trouvé: $input"
        return 1
    fi

    if ! command -v convert &> /dev/null; then
        log_error "ImageMagick n'est pas installé"
        return 1
    fi

    convert "$input" \
        -resize "${TARGET_SIZE}^" \
        -gravity center \
        -extent "$TARGET_SIZE" \
        -quality 90 \
        "$output"

    log_info "Image redimensionnée: $output"
}

# Redimensionner toutes les images existantes
resize_all_images() {
    log_info "Redimensionnement des images à ${TARGET_SIZE}..."

    for model in original mini xl plus neo; do
        local file="${IMAGES_DIR}/streamdeck-${model}.png"
        if [ -f "$file" ]; then
            local temp_file="${file}.tmp"
            if resize_image "$file" "$temp_file"; then
                mv "$temp_file" "$file"
                log_info "  ✓ streamdeck-${model}.png"
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
        printf "Voulez-vous créer des placeholders pour les images manquantes? [o/N] "
        read -r REPLY
        echo ""

        if [ "$REPLY" = "o" ] || [ "$REPLY" = "O" ]; then
            create_placeholders
        fi
    else
        log_info "Toutes les images sont présentes!"

        echo ""
        printf "Voulez-vous redimensionner les images à ${TARGET_SIZE}? [o/N] "
        read -r REPLY
        echo ""

        if [ "$REPLY" = "o" ] || [ "$REPLY" = "O" ]; then
            resize_all_images
        fi
    fi

    echo ""
    log_info "Terminé."
}

main "$@"
