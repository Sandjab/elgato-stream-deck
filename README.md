# Elgato Stream Deck

Mono-dépôt regroupant diverses ressources pour travailler avec les périphériques Elgato Stream Deck, avec un focus particulier sur l'intégration avec Claude Code CLI.

## Contenu

- **Documentation technique** des Stream Deck (protocole HID, SDK, formats de fichiers)
- **Spécifications d'intégration** avec Claude Code CLI
- **PRD et specs techniques** pour une application de démonstration

## Documentation

### Spécifications techniques Stream Deck

| Document | Description |
|----------|-------------|
| [streamdeck-specifications.md](docs/streamdeck-specifications.md) | Référence technique complète des périphériques Stream Deck : identifiants USB, protocole HID, format des profils `.streamDeckProfile`, SDK Plugin, et bibliothèques disponibles. |

### Intégration Claude Code ↔ Stream Deck

| Document | Description |
|----------|-------------|
| [claude-code-streamdeck-integration-spec.md](docs/claude-code-streamdeck-integration-spec.md) | Spécifications des interfaces et architectures possibles pour intégrer Claude Code CLI avec un Stream Deck : hooks, protocoles de communication, mapping des états. |

### Application de démonstration

| Document | Description |
|----------|-------------|
| [claude-streamdeck-prd.md](docs/claude-streamdeck-prd.md) | Product Requirements Document (PRD) pour un MVP d'intégration Claude Code / Stream Deck : vision, user stories, métriques de succès. |
| [claude-streamdeck-tech-spec.md](docs/claude-streamdeck-tech-spec.md) | Spécifications techniques détaillées pour l'implémentation du MVP : architecture, composants, scripts, assets graphiques. |

### Images des produits

Les images des différents modèles de Stream Deck sont stockées dans [`docs/images/`](docs/images/). Pour les télécharger ou générer des placeholders :

```bash
./scripts/download-streamdeck-images.sh
```

## Plugin Stream Deck XL

Le plugin MVP pour Stream Deck XL est implémenté dans `plugin/`. Il permet de visualiser l'état de Claude Code et d'interagir via les boutons physiques.

### Fonctionnalités testées (2026-01-18)

| Fonctionnalité | Status | Notes |
|----------------|--------|-------|
| Affichage des icônes | ✅ | 4 boutons : Status, New, Resume, Stop |
| Bouton New | ✅ | Ouvre Terminal avec `claude` |
| Bouton Resume | ✅ | Ouvre Terminal avec `claude --resume` |
| Bouton Stop | ✅ | Envoie Escape (nécessite permissions Accessibilité) |
| État idle (vert) | ✅ | Affiché au démarrage de session |
| État thinking (bleu) | ✅ | Affiché pendant le traitement |
| État tool_running (orange) | ✅ | Affiche le nom de l'outil |
| Transitions d'état | ✅ | idle → thinking → tool → thinking → idle |

### Limitations connues

- Les sessions Claude multiples partagent le même affichage d'état
- Le bouton Stop nécessite les permissions Accessibilité sur macOS
- Resume utilise `--resume` (liste) au lieu de `--continue` (dernière session)

### Installation rapide

```bash
cd plugin/daemon
pip3 install -r requirements.txt
brew install hidapi  # macOS
python3 -m claude_streamdeck --debug
```

Voir [.claude/CLAUDE.md](.claude/CLAUDE.md) pour plus de détails.

## Structure du projet

```
elgato-stream-deck/
├── README.md
├── .claude/
│   └── CLAUDE.md                         # Contexte projet pour Claude Code
├── docs/
│   ├── streamdeck-specifications.md      # Specs techniques Stream Deck
│   ├── claude-code-streamdeck-integration-spec.md  # Intégration Claude Code
│   ├── claude-streamdeck-prd.md          # PRD appli démo
│   ├── claude-streamdeck-tech-spec.md    # Specs techniques appli démo
│   └── images/                           # Images des produits
├── plugin/                               # Plugin MVP Stream Deck XL
│   ├── daemon/                           # Daemon Python
│   │   └── claude_streamdeck/            # Package principal
│   ├── hooks/                            # Scripts hook pour Claude Code
│   ├── assets/icons/96x96/               # Icônes 96x96 pour XL
│   ├── services/                         # Fichiers service macOS/Linux
│   ├── tests/                            # Tests unitaires
│   ├── install.sh                        # Script d'installation
│   └── uninstall.sh                      # Script de désinstallation
└── scripts/
    └── download-streamdeck-images.sh     # Script téléchargement images
```

## Modèles de Stream Deck supportés

| Modèle | Touches | Taille icône | DeviceType |
|--------|---------|--------------|------------|
| Stream Deck Original | 15 (5×3) | 72×72 / 144×144 @2x | 0 |
| Stream Deck Mini | 6 (3×2) | 80×80 / 160×160 @2x | 1 |
| Stream Deck XL | 32 (8×4) | 96×96 / 144×144 @2x | 2 |
| Stream Deck + | 8 + 4 molettes | 120×120 / 240×240 @2x | 7 |
| Stream Deck Neo | 8 (4×2) | 72×72 / 144×144 @2x | 9 |

## Ressources externes

- [Documentation officielle Stream Deck SDK](https://docs.elgato.com/streamdeck/sdk/)
- [Protocole HID Stream Deck](https://docs.elgato.com/streamdeck/hid/)
- [python-elgato-streamdeck](https://github.com/abcminiuser/python-elgato-streamdeck) - Bibliothèque Python
- [@elgato-stream-deck/node](https://github.com/Julusian/node-elgato-stream-deck) - Bibliothèque Node.js

## Licence

MIT
