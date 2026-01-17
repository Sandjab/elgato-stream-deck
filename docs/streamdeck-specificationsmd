# Spécifications Elgato Stream Deck

## Vue d'ensemble

Ce document compile les spécifications techniques pour travailler programmatiquement avec les périphériques Elgato Stream Deck. Il couvre trois aspects principaux :

1. **Format .streamDeckProfile** — fichiers de configuration exportables
2. **Protocole HID USB** — communication directe avec le hardware
3. **SDK Plugin** — développement de plugins pour l'application officielle

> **Note de version** : Informations à jour pour Stream Deck Software 7.x et SDK 2.0 (janvier 2026).

---

## Table des matières

1. [Modèles de périphériques](#1-modèles-de-périphériques)
2. [Format .streamDeckProfile](#2-format-streamdeckprofile)
3. [Structure interne des profils (ProfilesV2)](#3-structure-interne-des-profils-profilesv2)
4. [Protocole HID USB](#4-protocole-hid-usb)
5. [SDK Plugin - Manifest](#5-sdk-plugin---manifest)
6. [Bibliothèques et outils](#6-bibliothèques-et-outils)
7. [Chemins système](#7-chemins-système)

---

## 1. Modèles de périphériques

### Identifiants USB

| Modèle | DeviceType | Product ID (PID) | Touches | Disposition | Taille image |
|--------|------------|------------------|---------|-------------|--------------|
| Stream Deck Original (V1) | 0 | 0x0060 | 15 | 5×3 | 72×72 px |
| Stream Deck Original (V2) | 0 | 0x006D | 15 | 5×3 | 72×72 px |
| Stream Deck Mini | 1 | 0x0063 | 6 | 3×2 | 80×80 px |
| Stream Deck XL | 2 | 0x006C | 32 | 8×4 | 96×96 px |
| Stream Deck Mobile | 3 | — | Variable | — | — |
| Corsair GKeys | 4 | — | — | — | — |
| Stream Deck Pedal | 5 | 0x0086 | 3 | 3×1 | Pas d'écran |
| Corsair Voyager | 6 | — | — | — | — |
| Stream Deck + | 7 | 0x0084 | 8 + 4 dials | 4×2 + écran | 120×120 px |
| SCUF Controller | 8 | — | — | — | — |
| Stream Deck Neo | 9 | — | 8 | 4×2 | — |
| Stream Deck Studio | 10 | — | — | — | — |
| Virtual Stream Deck | 11 | — | Variable | — | — |

**Vendor ID (VID)** : `0x0FD9` (Elgato)

### Spécifications d'images par modèle

| Modèle | Format | Taille touche | Rotation | Mirroring |
|--------|--------|---------------|----------|-----------|
| Original V1 | BMP | 72×72 | Non | Non |
| Original V2 | JPEG | 72×72 | Non | Non |
| Mini | BMP | 80×80 | 90° CW | H+V |
| XL | JPEG | 96×96 | Non | Non |
| + (touches) | JPEG | 120×120 | Non | Non |
| + (écran) | JPEG | 800×100 | Non | Non |

---

## 2. Format .streamDeckProfile

### Description générale

Un fichier `.streamDeckProfile` est une **archive compressée** (similaire à ZIP) contenant la configuration complète d'un profil :

- Disposition des touches et pages
- Actions assignées à chaque touche
- Icônes et images personnalisées
- Métadonnées du profil

### Installation

- **Double-clic** sur le fichier → installation automatique via l'application Stream Deck
- **Import manuel** : Préférences → Profils → Import

### Nommage pour déploiement

Pour le déploiement à grande échelle, les fichiers doivent correspondre au modèle :

| Modèle | Nom de fichier requis |
|--------|----------------------|
| Stream Deck (15 touches) | `StreamDeck.streamDeckProfile` |
| Stream Deck Mini | `StreamDeckMini.streamDeckProfile` |
| Stream Deck XL | `StreamDeckXL.streamDeckProfile` |
| Stream Deck + | `StreamDeckPlus.streamDeckProfile` |
| Stream Deck Neo | `StreamDeckNeo.streamDeckProfile` |

---

## 3. Structure interne des profils (ProfilesV2)

### Emplacement sur disque

Les profils installés sont stockés dans le dossier `ProfilesV2` :

| OS | Chemin |
|----|--------|
| Windows | `%APPDATA%\Elgato\StreamDeck\ProfilesV2\` |
| macOS | `~/Library/Application Support/com.elgato.StreamDeck/ProfilesV2/` |

### Structure d'un profil

Chaque profil est un dossier nommé avec un UUID (format `XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX.sdProfile`) contenant :

```
XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX.sdProfile/
├── manifest.json           # Configuration principale
├── 0,0/                    # Dossier pour la touche en position (0,0)
│   └── [images]
├── 0,1/                    # Touche en position (0,1)
├── 1,0/
│   └── [images]
└── ...
```

### Format du manifest.json (profil)

```json
{
  "Version": "1.0",
  "Name": "Mon Profil",
  "DeviceUUID": "@(1)[SERIAL_NUMBER]",
  "DeviceModel": "20GAA9902",
  "AppIdentifier": "/Applications/MonApp.app",
  "Actions": {
    "0,0": {
      "Name": "Website",
      "UUID": "com.elgato.streamdeck.system.website",
      "State": 0,
      "States": [
        {
          "FFamily": "",
          "FSize": "",
          "FStyle": "",
          "FUnderline": "",
          "Image": "",
          "Title": "Mon Site",
          "TitleAlignment": "",
          "TitleColor": "",
          "TitleShow": ""
        }
      ],
      "Settings": {
        "openInBrowser": true,
        "path": "https://example.com"
      }
    },
    "0,1": {
      "Name": "Multi Action",
      "UUID": "com.elgato.streamdeck.multiactions.routine",
      "State": 0,
      "States": [...],
      "Settings": {
        "Routine": [...]
      }
    }
  }
}
```

### Indexation des touches

Les touches sont indexées par coordonnées `"colonne,ligne"` :

```
Stream Deck 15 touches (5×3) :
┌─────┬─────┬─────┬─────┬─────┐
│ 0,0 │ 1,0 │ 2,0 │ 3,0 │ 4,0 │  ← Ligne 0
├─────┼─────┼─────┼─────┼─────┤
│ 0,1 │ 1,1 │ 2,1 │ 3,1 │ 4,1 │  ← Ligne 1
├─────┼─────┼─────┼─────┼─────┤
│ 0,2 │ 1,2 │ 2,2 │ 3,2 │ 4,2 │  ← Ligne 2
└─────┴─────┴─────┴─────┴─────┘
  ↑     ↑     ↑     ↑     ↑
 Col0  Col1  Col2  Col3  Col4
```

### Actions système intégrées

| UUID | Description |
|------|-------------|
| `com.elgato.streamdeck.system.website` | Ouvrir URL |
| `com.elgato.streamdeck.system.open` | Ouvrir application/fichier |
| `com.elgato.streamdeck.system.hotkey` | Raccourci clavier |
| `com.elgato.streamdeck.system.text` | Saisie de texte |
| `com.elgato.streamdeck.multiactions.routine` | Multi-action |
| `com.elgato.streamdeck.profile.rotate` | Changer de profil |
| `com.elgato.streamdeck.page.next` | Page suivante |
| `com.elgato.streamdeck.page.previous` | Page précédente |

### Structure d'une action

```json
{
  "Name": "Nom affiché",
  "UUID": "com.vendor.plugin.action",
  "State": 0,
  "States": [
    {
      "FFamily": "Arial",
      "FSize": "12",
      "FStyle": "Bold",
      "FUnderline": "false",
      "Image": "chemin/vers/image",
      "Title": "Titre",
      "TitleAlignment": "middle",
      "TitleColor": "#FFFFFF",
      "TitleShow": "true"
    }
  ],
  "Settings": {
    // Paramètres spécifiques à l'action
  }
}
```

---

## 4. Protocole HID USB

### Concepts fondamentaux

Le Stream Deck communique via le protocole USB HID (Human Interface Device) :

| Direction | Type | Description |
|-----------|------|-------------|
| Device → Host | Input Report | Événements (appui touches) |
| Host → Device | Output Report | Commandes (images, config) |
| Bidirectionnel | Feature Report | Configuration, info firmware |

### Workflow de communication

1. **Détecter** le périphérique (VID: `0x0FD9`, PID selon modèle)
2. **Ouvrir** la connexion HID
3. **Initialiser/Configurer** (optionnel)
4. **Boucle** : Lire Input Reports / Envoyer Output Reports
5. **Fermer** la connexion

### Report IDs

| Report ID | Direction | Usage |
|-----------|-----------|-------|
| `0x01` | Input | État des touches |
| `0x02` | Output | Commandes (images, etc.) |
| `0x03` | Feature | Configuration |

### Input Report (état des touches)

Intervalle de polling recommandé : **50 ms**

Structure pour un appui de touche :
```
[0x01, 0x00, 0x20, 0x00, ...boutons...]
```

Le tableau de boutons contient `1` pour chaque touche pressée, `0` sinon.

### Output Report (envoi d'images)

Taille maximale : **1024 octets** (pour les modèles V2+)

Structure générale :
```
[Report ID, Command, Key Index, Is Last, Length (2 bytes), Page Number, ...Data...]
```

| Commande | Description |
|----------|-------------|
| `0x07` | Upload image pour une touche |
| `0x08` | Upload image plein écran (Stream Deck +) |

### Commandes Feature Report

| Commande | Description |
|----------|-------------|
| Reset | Réinitialiser l'affichage |
| Set Brightness | Régler la luminosité (0-100) |
| Get Serial | Récupérer le numéro de série |
| Get Firmware | Récupérer la version firmware |

### Format des images

| Modèle | Format | Encodage | Notes |
|--------|--------|----------|-------|
| Original V1 | BMP | Brut | Header BMP de 54 octets inclus |
| Original V2+ | JPEG | Compressé | Qualité ~80 recommandée |
| Mini | BMP | Brut | Rotation 90° CW requise |
| Modules 6/15/32 | BMP/JPEG | Selon modèle | Voir doc HID officielle |

---

## 5. SDK Plugin - Manifest

### Structure d'un plugin

```
com.vendor.plugin.sdPlugin/
├── manifest.json           # Métadonnées du plugin
├── bin/
│   └── plugin.js          # Point d'entrée (Node.js)
├── imgs/
│   ├── plugin/
│   │   ├── category-icon.png
│   │   └── marketplace.png
│   └── actions/
│       └── action-name/
│           ├── icon.png
│           └── key.png
├── ui/
│   └── settings.html      # Property Inspector
└── logs/
```

### Manifest.json (plugin)

```json
{
  "$schema": "https://schemas.elgato.com/streamdeck/plugins/manifest.json",
  "UUID": "com.vendor.plugin",
  "Name": "Mon Plugin",
  "Version": "1.0.0.0",
  "Author": "Auteur",
  "Description": "Description du plugin",
  "Icon": "imgs/plugin/marketplace",
  "CategoryIcon": "imgs/plugin/category-icon",
  "Category": "Mon Plugin",
  "CodePath": "bin/plugin.js",
  "SDKVersion": 2,
  "Software": {
    "MinimumVersion": "6.6"
  },
  "OS": [
    { "Platform": "mac", "MinimumVersion": "13" },
    { "Platform": "windows", "MinimumVersion": "10" }
  ],
  "Nodejs": {
    "Version": "20",
    "Debug": "enabled"
  },
  "Actions": [
    {
      "UUID": "com.vendor.plugin.action",
      "Name": "Mon Action",
      "Icon": "imgs/actions/action-name/icon",
      "Tooltip": "Description de l'action",
      "Controllers": ["Keypad"],
      "States": [
        {
          "Image": "imgs/actions/action-name/key",
          "TitleAlignment": "middle"
        }
      ],
      "PropertyInspectorPath": "ui/settings.html"
    }
  ],
  "Profiles": [
    {
      "Name": "profiles/my-profile",
      "DeviceType": 0,
      "AutoInstall": true,
      "Readonly": false,
      "DontAutoSwitchWhenInstalled": true
    }
  ]
}
```

### Propriétés clés du manifest

#### Actions

| Propriété | Type | Description |
|-----------|------|-------------|
| `UUID` | string | Identifiant unique (reverse-DNS) |
| `Name` | string | Nom affiché |
| `Icon` | string | Icône dans la liste d'actions (sans extension) |
| `Controllers` | array | `["Keypad"]`, `["Encoder"]`, ou les deux |
| `States` | array | États de l'action (1 ou 2 max) |
| `DisableAutomaticStates` | boolean | Désactiver le toggle automatique |
| `VisibleInActionsList` | boolean | Visible dans la liste (default: true) |
| `SupportedInMultiActions` | boolean | Utilisable en multi-action |
| `UserTitleEnabled` | boolean | Permettre titre personnalisé |

#### States

| Propriété | Type | Description |
|-----------|------|-------------|
| `Image` | string | Image de la touche (sans extension) |
| `Title` | string | Titre par défaut |
| `TitleAlignment` | string | `"top"`, `"middle"`, `"bottom"` |
| `TitleColor` | string | Couleur hex (`"#FFFFFF"`) |
| `ShowTitle` | boolean | Afficher le titre |
| `FontFamily` | string | Police |
| `FontSize` | number | Taille |
| `FontStyle` | string | `""`, `"Bold"`, `"Italic"`, `"Bold Italic"` |

#### Encoder (Stream Deck +)

```json
{
  "Controllers": ["Keypad", "Encoder"],
  "Encoder": {
    "layout": "$B1",
    "background": "imgs/encoder-bg",
    "Icon": "imgs/encoder-icon",
    "StackColor": "#0078D4",
    "TriggerDescription": {
      "Push": "Activer",
      "Rotate": "Ajuster",
      "Touch": "Activer",
      "LongTouch": "Options"
    }
  }
}
```

Layouts pré-définis : `$X1`, `$A0`, `$A1`, `$B1`, `$B2`, `$C1`

#### Profiles bundlés

| Propriété | Type | Description |
|-----------|------|-------------|
| `Name` | string | Chemin vers `.streamDeckProfile` (sans extension) |
| `DeviceType` | number | Type de périphérique (voir section 1) |
| `AutoInstall` | boolean | Installation automatique |
| `Readonly` | boolean | Profil en lecture seule |
| `DontAutoSwitchWhenInstalled` | boolean | Ne pas basculer automatiquement |

### Tailles d'images requises

| Type | Taille standard | Taille @2x |
|------|-----------------|------------|
| Plugin Icon (Marketplace) | 256×256 | 512×512 |
| Category Icon | 28×28 | 56×56 |
| Action Icon | 20×20 | 40×40 |
| Key Image | 72×72 | 144×144 |
| Encoder Icon | 72×72 | 144×144 |
| Touchscreen Background | 200×100 | 400×200 |

**Format** : PNG ou SVG (sauf Marketplace Icon : PNG uniquement)

**Convention de nommage** : `image.png` et `image@2x.png`

---

## 6. Bibliothèques et outils

### Contrôle direct USB (sans app Elgato)

| Langage | Bibliothèque | Stars | Notes |
|---------|--------------|-------|-------|
| Python | [python-elgato-streamdeck](https://github.com/abcminiuser/python-elgato-streamdeck) | ~1.1k | La plus mature, tous modèles |
| Node.js | [@elgato-stream-deck/node](https://github.com/Julusian/node-elgato-stream-deck) | ~183 | Monorepo avec packages WebHID/TCP |
| C#/.NET | [DeckSurf SDK](https://github.com/dend/decksurf-sdk) | ~50 | Windows, reverse-engineered |
| Deno | [deno_streamdeck](https://deno.land/x/deno_streamdeck) | — | Via Deno FFI |

### SDK Plugin officiel

| Langage | SDK | Notes |
|---------|-----|-------|
| TypeScript/Node.js | [@elgato/streamdeck](https://github.com/elgatosf/streamdeck) | Officiel, recommandé |
| C# | [streamdeck-tools](https://github.com/BarRaider/streamdeck-tools) | Communautaire, très populaire |

### Générateurs de profils

| Projet | Langage | Description |
|--------|---------|-------------|
| [streamdeck-profile-generator](https://github.com/data-enabler/streamdeck-profile-generator) | JavaScript | Génération programmatique de `.streamDeckProfile` |

### Alternatives Linux

| Projet | Description |
|--------|-------------|
| [StreamController](https://github.com/StreamController/StreamController) | App GTK4, plugin store, recommandé |
| [OpenDeck](https://github.com/nekename/OpenDeck) | Rust/Tauri, supporte plugins Elgato via Wine |

---

## 7. Chemins système

### Windows

| Élément | Chemin |
|---------|--------|
| Profils | `%APPDATA%\Elgato\StreamDeck\ProfilesV2\` |
| Plugins | `%APPDATA%\Elgato\StreamDeck\Plugins\` |
| Logs | `%APPDATA%\Elgato\StreamDeck\logs\` |
| Préférences | `%APPDATA%\Elgato\StreamDeck\preferences.json` |

### macOS

| Élément | Chemin |
|---------|--------|
| Profils | `~/Library/Application Support/com.elgato.StreamDeck/ProfilesV2/` |
| Plugins | `~/Library/Application Support/com.elgato.StreamDeck/Plugins/` |
| Logs | `~/Library/Logs/ElgatoStreamDeck/` |
| Préférences | `~/Library/Preferences/com.elgato.StreamDeck.plist` |

### Configuration de chemin personnalisé

**Windows** (Registry) :
```
HKEY_CURRENT_USER\Software\Elgato Systems GmbH\StreamDeck
Nom: custom_default_profiles
Type: REG_SZ
Valeur: C:\StreamDeck\DefaultProfiles
```

**macOS** (defaults) :
```bash
defaults write com.elgato.StreamDeck custom_default_profiles /path/to/profiles
```

---

## Références

### Documentation officielle

- [Stream Deck SDK](https://docs.elgato.com/streamdeck/sdk/introduction/getting-started)
- [Stream Deck HID API](https://docs.elgato.com/streamdeck/hid/)
- [Manifest Reference](https://docs.elgato.com/streamdeck/sdk/references/manifest/)
- [JSON Schema](https://schemas.elgato.com/streamdeck/plugins/manifest.json)

### Ressources communautaires

- [USB ID Repository - Elgato](http://www.linux-usb.org/usb.ids) (VID 0x0FD9)
- [Reverse Engineering Stream Deck](https://den.dev/blog/reverse-engineering-stream-deck/) par Den Delimarsky
- [Reverse Engineering Stream Deck Plus](https://den.dev/blog/reverse-engineer-stream-deck-plus/) par Den Delimarsky

---

*Document généré le 17 janvier 2026. Basé sur Stream Deck Software 7.x et SDK 2.0.*
