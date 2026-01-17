# Spécifications d'intégration Claude Code ↔ Stream Deck

## Vue d'ensemble

Ce document spécifie les interfaces et architectures possibles pour intégrer Claude Code CLI avec un Elgato Stream Deck, permettant un affichage dynamique de l'état de Claude et des actions de contrôle.

---

## Table des matières

1. [Objectifs](#1-objectifs)
2. [Architecture générale](#2-architecture-générale)
3. [Interface Claude Code (source de données)](#3-interface-claude-code-source-de-données)
4. [Interface Stream Deck (affichage et contrôle)](#4-interface-stream-deck-affichage-et-contrôle)
5. [Architectures d'intégration](#5-architectures-dintégration)
6. [Spécification du protocole de communication](#6-spécification-du-protocole-de-communication)
7. [Implémentation recommandée](#7-implémentation-recommandée)
8. [Annexes](#annexes)

---

## 1. Objectifs

### 1.1 Fonctionnalités cibles

| Catégorie | Fonctionnalité | Priorité |
|-----------|----------------|----------|
| **Affichage d'état** | Session active/inactive | P0 |
| | État courant (idle, thinking, tool execution) | P0 |
| | Nom de l'outil en cours | P1 |
| | Fichier(s) en cours de modification | P2 |
| | Tokens consommés / coût estimé | P3 |
| **Actions** | Lancer une nouvelle session Claude | P0 |
| | Reprendre la dernière session | P0 |
| | Interrompre (Ctrl+C) | P1 |
| | Prompts prédéfinis | P2 |
| | Changer de projet | P3 |

### 1.2 Contraintes

- Latence d'affichage < 500ms
- Pas de dépendance à l'application Stream Deck (optionnel)
- Compatible macOS et Linux
- Pas de modification du code source de Claude Code

---

## 2. Architecture générale

### 2.1 Vue d'ensemble des composants

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLAUDE CODE                                 │
│  ┌─────────────┐                                                        │
│  │   CLI       │                                                        │
│  │  (claude)   │                                                        │
│  └──────┬──────┘                                                        │
│         │ hooks (settings.json)                                         │
│         ▼                                                               │
│  ┌─────────────┐     stdin (JSON)      ┌─────────────────────────────┐ │
│  │   Hooks     │◄─────────────────────►│  Scripts de notification    │ │
│  │  système    │                       │  (.claude/hooks/*.sh)       │ │
│  └─────────────┘                       └──────────────┬──────────────┘ │
└──────────────────────────────────────────────────────│──────────────────┘
                                                       │
                              ┌─────────────────────────┴─────────────────────────┐
                              │              COUCHE DE TRANSPORT                   │
                              │  ┌─────────┐  ┌─────────┐  ┌─────────────────┐   │
                              │  │ Fichier │  │  Socket │  │  HTTP/WebSocket │   │
                              │  │  JSON   │  │  Unix   │  │    localhost    │   │
                              │  └────┬────┘  └────┬────┘  └────────┬────────┘   │
                              └───────│────────────│────────────────│─────────────┘
                                      │            │                │
                              ┌───────┴────────────┴────────────────┴─────────────┐
                              │                    DAEMON                          │
                              │  ┌─────────────────────────────────────────────┐  │
                              │  │  - Écoute les événements Claude Code        │  │
                              │  │  - Maintient l'état courant                 │  │
                              │  │  - Communique avec Stream Deck              │  │
                              │  └─────────────────────────────────────────────┘  │
                              └───────────────────────┬───────────────────────────┘
                                                      │
                              ┌────────────────────────┴────────────────────────┐
                              │                                                 │
                      ┌───────▼───────┐                               ┌────────▼────────┐
                      │  OPTION A     │                               │   OPTION B      │
                      │  Plugin SDK   │                               │  Contrôle USB   │
                      │  (avec app)   │                               │  direct (sans   │
                      │               │                               │  app Elgato)    │
                      └───────┬───────┘                               └────────┬────────┘
                              │                                                │
                              │         WebSocket localhost                    │ HID USB
                              ▼                                                ▼
                      ┌───────────────┐                               ┌───────────────┐
                      │  Stream Deck  │                               │  Stream Deck  │
                      │  Application  │                               │   Hardware    │
                      └───────────────┘                               └───────────────┘
```

### 2.2 Flux de données

```
[Claude Code CLI]
       │
       │ (1) Hook déclenché (SessionStart, PreToolUse, etc.)
       ▼
[Script Hook] ──────► stdin: JSON avec contexte complet
       │
       │ (2) Transformation en état simplifié
       ▼
[Transport] ◄──────── {state, tool, files, timestamp}
       │
       │ (3) Notification au daemon
       ▼
[Daemon]
       │
       │ (4) Mise à jour de l'affichage
       ▼
[Stream Deck] ◄────── Image + titre mis à jour
```

---

## 3. Interface Claude Code (source de données)

### 3.1 Hooks disponibles

| Hook | Déclencheur | Données clés |
|------|-------------|--------------|
| `SessionStart` | Nouvelle session ou reprise | `session_id`, `source` (startup/resume/clear) |
| `SessionEnd` | Fin de session | `session_id`, `reason` (exit/logout/clear) |
| `UserPromptSubmit` | Utilisateur soumet un prompt | `prompt` (texte soumis) |
| `PreToolUse` | Avant exécution d'un outil | `tool_name`, `tool_input` |
| `PostToolUse` | Après exécution d'un outil | `tool_name`, `tool_result` |
| `Stop` | Fin de réponse de Claude | `session_id` |
| `SubagentStop` | Fin d'un sous-agent | `session_id` |
| `Notification` | Message système | `message` |
| `PreCompact` | Avant compaction du contexte | `session_id` |

### 3.2 Configuration des hooks

**Emplacement** : `~/.claude/settings.json` (global) ou `.claude/settings.json` (projet)

```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "$HOME/.claude/hooks/streamdeck-notify.sh SessionStart"
      }]
    }],
    "SessionEnd": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "$HOME/.claude/hooks/streamdeck-notify.sh SessionEnd"
      }]
    }],
    "UserPromptSubmit": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "$HOME/.claude/hooks/streamdeck-notify.sh UserPromptSubmit"
      }]
    }],
    "PreToolUse": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "$HOME/.claude/hooks/streamdeck-notify.sh PreToolUse"
      }]
    }],
    "PostToolUse": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "$HOME/.claude/hooks/streamdeck-notify.sh PostToolUse"
      }]
    }],
    "Stop": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "$HOME/.claude/hooks/streamdeck-notify.sh Stop"
      }]
    }],
    "Notification": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "$HOME/.claude/hooks/streamdeck-notify.sh Notification"
      }]
    }]
  }
}
```

### 3.3 Variables d'environnement disponibles

| Variable | Description | Disponibilité |
|----------|-------------|---------------|
| `CLAUDE_SESSION_ID` | UUID de la session | Tous les hooks |
| `CLAUDE_TOOL_NAME` | Nom de l'outil | PreToolUse, PostToolUse |
| `CLAUDE_TOOL_INPUT` | Input JSON de l'outil | PreToolUse |
| `CLAUDE_FILE_PATHS` | Fichiers concernés | PreToolUse, PostToolUse |
| `CLAUDE_PROJECT_DIR` | Répertoire du projet | Tous les hooks |
| `CLAUDE_ENV_FILE` | Fichier pour persister des vars | SessionStart uniquement |
| `CLAUDE_CODE_REMOTE` | "true" si environnement web | Tous les hooks |

### 3.4 Format JSON en stdin

Chaque hook reçoit un JSON complet via stdin :

**SessionStart** :
```json
{
  "session_id": "abc123-def456",
  "transcript_path": "~/.claude/projects/.../transcript.jsonl",
  "permission_mode": "default",
  "hook_event_name": "SessionStart",
  "source": "startup"
}
```

**PreToolUse** :
```json
{
  "session_id": "abc123-def456",
  "tool_name": "Edit",
  "tool_input": {
    "file_path": "/path/to/file.py",
    "old_string": "...",
    "new_string": "..."
  },
  "hook_event_name": "PreToolUse"
}
```

**PostToolUse** :
```json
{
  "session_id": "abc123-def456",
  "tool_name": "Edit",
  "tool_result": "success",
  "hook_event_name": "PostToolUse"
}
```

**Stop** :
```json
{
  "session_id": "abc123-def456",
  "hook_event_name": "Stop",
  "stop_reason": "end_turn"
}
```

---

## 4. Interface Stream Deck (affichage et contrôle)

### 4.1 Option A : Plugin SDK (avec application Elgato)

#### 4.1.1 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Stream Deck Application                   │
│  ┌─────────────────┐       WebSocket        ┌─────────────┐ │
│  │   Interface     │◄──────────────────────►│   Plugin    │ │
│  │   utilisateur   │      localhost:port    │  Node.js    │ │
│  └─────────────────┘                        └──────┬──────┘ │
└─────────────────────────────────────────────────────────────┘
                                                     │
                                          WebSocket ou polling
                                                     │
                                                     ▼
                                              ┌─────────────┐
                                              │   Daemon    │
                                              │   Claude    │
                                              └─────────────┘
```

#### 4.1.2 Structure du plugin

```
com.user.claude-code.sdPlugin/
├── manifest.json
├── bin/
│   └── plugin.js           # Point d'entrée Node.js
├── imgs/
│   ├── plugin/
│   │   ├── marketplace.png
│   │   └── category-icon.png
│   └── actions/
│       └── status/
│           ├── icon.png
│           ├── active.png
│           ├── idle.png
│           ├── working.png
│           └── inactive.png
├── ui/
│   └── settings.html       # Property Inspector
└── package.json
```

#### 4.1.3 Manifest du plugin

```json
{
  "$schema": "https://schemas.elgato.com/streamdeck/plugins/manifest.json",
  "UUID": "com.user.claude-code",
  "Name": "Claude Code",
  "Version": "1.0.0.0",
  "Author": "User",
  "Description": "Intégration Claude Code CLI",
  "Icon": "imgs/plugin/marketplace",
  "CategoryIcon": "imgs/plugin/category-icon",
  "Category": "Claude Code",
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
    "Version": "20"
  },
  "Actions": [
    {
      "UUID": "com.user.claude-code.status",
      "Name": "État Claude",
      "Icon": "imgs/actions/status/icon",
      "Tooltip": "Affiche l'état de Claude Code",
      "Controllers": ["Keypad"],
      "States": [
        {
          "Image": "imgs/actions/status/inactive",
          "Name": "Inactif",
          "TitleAlignment": "bottom"
        },
        {
          "Image": "imgs/actions/status/active",
          "Name": "Actif",
          "TitleAlignment": "bottom"
        }
      ]
    },
    {
      "UUID": "com.user.claude-code.new-session",
      "Name": "Nouvelle session",
      "Icon": "imgs/actions/new-session/icon",
      "Tooltip": "Lance une nouvelle session Claude Code",
      "Controllers": ["Keypad"],
      "States": [{ "Image": "imgs/actions/new-session/key" }]
    },
    {
      "UUID": "com.user.claude-code.resume",
      "Name": "Reprendre",
      "Icon": "imgs/actions/resume/icon",
      "Tooltip": "Reprend la dernière session",
      "Controllers": ["Keypad"],
      "States": [{ "Image": "imgs/actions/resume/key" }]
    },
    {
      "UUID": "com.user.claude-code.interrupt",
      "Name": "Interrompre",
      "Icon": "imgs/actions/interrupt/icon",
      "Tooltip": "Interrompt Claude (Escape)",
      "Controllers": ["Keypad"],
      "States": [{ "Image": "imgs/actions/interrupt/key" }]
    }
  ]
}
```

#### 4.1.4 API du plugin (événements SDK)

| Événement | Direction | Usage |
|-----------|-----------|-------|
| `keyDown` | SD → Plugin | Touche pressée |
| `keyUp` | SD → Plugin | Touche relâchée |
| `willAppear` | SD → Plugin | Action ajoutée/visible |
| `willDisappear` | SD → Plugin | Action retirée/masquée |
| `setImage` | Plugin → SD | Changer l'image d'une touche |
| `setTitle` | Plugin → SD | Changer le titre |
| `setState` | Plugin → SD | Changer l'état (0/1) |
| `showAlert` | Plugin → SD | Afficher une alerte |

### 4.2 Option B : Contrôle USB direct (sans application Elgato)

#### 4.2.1 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Daemon                               │
│  ┌─────────────────┐                    ┌─────────────────┐ │
│  │  Réception des  │                    │   Contrôle USB  │ │
│  │  événements     │───────────────────►│   Stream Deck   │ │
│  │  Claude Code    │                    │   (HID)         │ │
│  └─────────────────┘                    └────────┬────────┘ │
└──────────────────────────────────────────────────│──────────┘
                                                   │
                                              USB HID
                                                   │
                                                   ▼
                                           ┌─────────────┐
                                           │ Stream Deck │
                                           │  Hardware   │
                                           └─────────────┘
```

#### 4.2.2 Bibliothèques recommandées

| Langage | Bibliothèque | Installation |
|---------|--------------|--------------|
| Python | `streamdeck` | `pip install streamdeck` |
| Node.js | `@elgato-stream-deck/node` | `npm install @elgato-stream-deck/node` |

#### 4.2.3 API de contrôle direct

**Python (python-elgato-streamdeck)** :

```python
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper
from PIL import Image

# Connexion
deck = DeviceManager().enumerate()[0]
deck.open()
deck.reset()

# Callbacks
def on_key_press(deck, key, state):
    if state:  # pressed
        handle_action(key)

deck.set_key_callback(on_key_press)

# Affichage
def set_key_image(key_index, image_path):
    image = Image.open(image_path)
    native = PILHelper.to_native_format(deck, image)
    deck.set_key_image(key_index, native)

# Luminosité
deck.set_brightness(70)
```

**Node.js (@elgato-stream-deck/node)** :

```javascript
import { openStreamDeck } from '@elgato-stream-deck/node';
import sharp from 'sharp';

const deck = await openStreamDeck();

// Callbacks
deck.on('down', (keyIndex) => handleAction(keyIndex));
deck.on('up', (keyIndex) => { /* released */ });

// Affichage
async function setKeyImage(keyIndex, imagePath) {
  const buffer = await sharp(imagePath)
    .resize(deck.ICON_SIZE, deck.ICON_SIZE)
    .raw()
    .toBuffer();
  deck.fillKeyBuffer(keyIndex, buffer);
}

// Luminosité
deck.setBrightness(70);
```

---

## 5. Architectures d'intégration

### 5.1 Architecture A : Fichier JSON + Polling

**Complexité** : ⭐ (Simple)
**Latence** : ~500ms (dépend de l'intervalle de polling)

```
┌─────────────┐     hooks      ┌─────────────┐     write      ┌─────────────┐
│ Claude Code │───────────────►│   Script    │───────────────►│  Fichier    │
│     CLI     │                │   notify    │                │   JSON      │
└─────────────┘                └─────────────┘                └──────┬──────┘
                                                                     │
                                                              polling (500ms)
                                                                     │
                                                               ┌─────▼──────┐
                                                               │  Daemon /  │
                                                               │  Plugin    │
                                                               └─────┬──────┘
                                                                     │
                                                               ┌─────▼──────┐
                                                               │ Stream Deck│
                                                               └────────────┘
```

**Fichier d'état** : `~/.claude/streamdeck-state.json`

```json
{
  "state": "working",
  "tool": "Edit",
  "files": ["/path/to/file.py"],
  "session_id": "abc123",
  "timestamp": 1705500000
}
```

**Avantages** :
- Implémentation triviale
- Debugging facile (fichier lisible)
- Pas de dépendances réseau

**Inconvénients** :
- Latence variable
- Consommation CPU (polling)

### 5.2 Architecture B : Socket Unix

**Complexité** : ⭐⭐ (Moyenne)
**Latence** : ~10ms

```
┌─────────────┐     hooks      ┌─────────────┐     write      ┌─────────────┐
│ Claude Code │───────────────►│   Script    │───────────────►│   Socket    │
│     CLI     │                │   notify    │                │    Unix     │
└─────────────┘                └─────────────┘                └──────┬──────┘
                                                                     │
                                                               listen (async)
                                                                     │
                                                               ┌─────▼──────┐
                                                               │  Daemon    │
                                                               └─────┬──────┘
                                                                     │
                                                               ┌─────▼──────┐
                                                               │ Stream Deck│
                                                               └────────────┘
```

**Socket** : `~/.claude/streamdeck.sock`

**Avantages** :
- Très faible latence
- Événements push (pas de polling)
- Efficace en ressources

**Inconvénients** :
- Plus complexe à implémenter
- macOS/Linux uniquement

### 5.3 Architecture C : HTTP/WebSocket localhost

**Complexité** : ⭐⭐⭐ (Élevée)
**Latence** : ~20ms

```
┌─────────────┐     hooks      ┌─────────────┐      POST      ┌─────────────┐
│ Claude Code │───────────────►│   Script    │───────────────►│   Serveur   │
│     CLI     │                │   notify    │  localhost:X   │    HTTP     │
└─────────────┘                └─────────────┘                └──────┬──────┘
                                                                     │
                                                               WebSocket
                                                                     │
                                                               ┌─────▼──────┐
                                                               │  Plugin    │
                                                               │ Stream Deck│
                                                               └─────┬──────┘
                                                                     │
                                                               ┌─────▼──────┐
                                                               │ Stream Deck│
                                                               └────────────┘
```

**Avantages** :
- Architecture standard
- Facile à debugger (curl, browser)
- Extensible (UI web, multi-clients)

**Inconvénients** :
- Overhead HTTP
- Port à gérer
- Plus de dépendances

### 5.4 Tableau comparatif

| Critère | Fichier JSON | Socket Unix | HTTP/WebSocket |
|---------|--------------|-------------|----------------|
| Complexité | ⭐ | ⭐⭐ | ⭐⭐⭐ |
| Latence | ~500ms | ~10ms | ~20ms |
| Fiabilité | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| Cross-platform | ✅ | ❌ (Unix) | ✅ |
| Debugging | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ |
| Ressources | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| Multi-clients | ❌ | ⭐⭐ | ⭐⭐⭐ |

---

## 6. Spécification du protocole de communication

### 6.1 Format des messages

#### 6.1.1 Message d'état (Claude → Daemon)

```typescript
interface ClaudeStateMessage {
  type: "state_update";
  timestamp: number;          // Unix timestamp ms
  session: {
    id: string;               // UUID de session
    active: boolean;          // Session en cours
    project_dir: string;      // Répertoire du projet
  };
  state: "inactive" | "idle" | "thinking" | "tool_running" | "waiting_input";
  tool?: {
    name: string;             // Bash, Edit, Write, Read, etc.
    input?: object;           // Input de l'outil
    files?: string[];         // Fichiers concernés
  };
  notification?: {
    message: string;
    level: "info" | "warning" | "error";
  };
}
```

#### 6.1.2 Message de commande (Daemon → Claude)

```typescript
interface CommandMessage {
  type: "command";
  action: "new_session" | "resume" | "interrupt" | "prompt";
  payload?: {
    prompt?: string;          // Pour action "prompt"
    project_dir?: string;     // Pour action "new_session"
  };
}
```

### 6.2 États de Claude Code

```
                    ┌─────────────┐
                    │  INACTIVE   │ ◄─── Pas de session
                    └──────┬──────┘
                           │ SessionStart
                           ▼
                    ┌─────────────┐
        ┌──────────►│    IDLE     │ ◄─── En attente d'input
        │           └──────┬──────┘
        │                  │ UserPromptSubmit
        │                  ▼
        │           ┌─────────────┐
        │           │  THINKING   │ ◄─── Claude réfléchit
        │           └──────┬──────┘
        │                  │ PreToolUse
        │                  ▼
        │           ┌─────────────┐
        │           │TOOL_RUNNING │ ◄─── Outil en exécution
        │           └──────┬──────┘
        │                  │ PostToolUse
        │                  │
        │    Stop ─────────┤
        │                  │
        └──────────────────┘
                           │ SessionEnd
                           ▼
                    ┌─────────────┐
                    │  INACTIVE   │
                    └─────────────┘
```

### 6.3 Mapping États → Affichage Stream Deck

| État | Couleur | Icône | Titre |
|------|---------|-------|-------|
| `inactive` | Gris | ⭘ | "Offline" |
| `idle` | Vert | ✓ | "Ready" |
| `thinking` | Bleu pulsant | 🧠 | "Thinking..." |
| `tool_running` | Orange | ⚙️ | Nom de l'outil |
| `waiting_input` | Jaune | ⏳ | "Waiting..." |

---

## 7. Implémentation recommandée

### 7.1 Stack technologique recommandé

| Composant | Technologie | Justification |
|-----------|-------------|---------------|
| Script hook | Bash | Simplicité, pas de dépendances |
| Transport | Socket Unix | Meilleur compromis latence/complexité |
| Daemon | Python | Écosystème `streamdeck` mature |
| Affichage | Contrôle USB direct | Indépendant de l'app Elgato |

### 7.2 Structure du projet

```
claude-streamdeck/
├── README.md
├── install.sh                    # Script d'installation
├── uninstall.sh
│
├── hooks/                        # Scripts pour Claude Code
│   ├── streamdeck-notify.sh      # Script principal
│   └── install-hooks.sh          # Installe la config dans settings.json
│
├── daemon/                       # Daemon Python
│   ├── requirements.txt
│   ├── claude_streamdeck/
│   │   ├── __init__.py
│   │   ├── daemon.py             # Point d'entrée
│   │   ├── state.py              # Machine à états
│   │   ├── transport.py          # Socket Unix
│   │   └── streamdeck.py         # Interface Stream Deck
│   └── assets/
│       ├── icons/
│       │   ├── inactive.png
│       │   ├── idle.png
│       │   ├── thinking.png
│       │   ├── tool-bash.png
│       │   ├── tool-edit.png
│       │   └── ...
│       └── fonts/
│
├── config/
│   ├── config.example.yaml       # Configuration exemple
│   └── buttons.yaml              # Mapping des boutons
│
└── systemd/                      # Service Linux
    └── claude-streamdeck.service
```

### 7.3 Script hook principal

**`hooks/streamdeck-notify.sh`** :

```bash
#!/bin/bash
set -euo pipefail

SOCKET_PATH="${CLAUDE_STREAMDECK_SOCKET:-$HOME/.claude/streamdeck.sock}"
EVENT_TYPE="$1"

# Lire le JSON depuis stdin
INPUT_JSON=$(cat)

# Construire le message
MESSAGE=$(jq -n \
  --arg type "state_update" \
  --arg event "$EVENT_TYPE" \
  --argjson timestamp "$(date +%s%3N)" \
  --argjson input "$INPUT_JSON" \
  '{
    type: $type,
    event: $event,
    timestamp: $timestamp,
    data: $input
  }'
)

# Envoyer au daemon via socket Unix
if [[ -S "$SOCKET_PATH" ]]; then
  echo "$MESSAGE" | nc -U "$SOCKET_PATH" -q0 2>/dev/null || true
fi

# Fallback : écrire dans un fichier
STATE_FILE="$HOME/.claude/streamdeck-state.json"
echo "$MESSAGE" > "$STATE_FILE"

exit 0
```

### 7.4 Daemon Python

**`daemon/claude_streamdeck/daemon.py`** :

```python
#!/usr/bin/env python3
"""
Daemon Claude Code <-> Stream Deck
"""

import asyncio
import json
import os
import signal
from pathlib import Path

from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper
from PIL import Image, ImageDraw, ImageFont


class ClaudeStreamDeckDaemon:
    def __init__(self, config_path: str = None):
        self.socket_path = Path.home() / ".claude" / "streamdeck.sock"
        self.state = {
            "status": "inactive",
            "tool": None,
            "session_id": None
        }
        self.deck = None
        self.running = False
        
        # Configuration des boutons
        self.button_config = {
            0: {"type": "status"},
            1: {"type": "action", "action": "new_session"},
            2: {"type": "action", "action": "resume"},
            3: {"type": "action", "action": "interrupt"},
        }
        
        # Assets
        self.assets_dir = Path(__file__).parent.parent / "assets"
        
    async def start(self):
        """Démarre le daemon"""
        self.running = True
        
        # Connexion Stream Deck
        await self._connect_streamdeck()
        
        # Démarrer le serveur socket
        await self._start_socket_server()
        
    async def _connect_streamdeck(self):
        """Connexion au Stream Deck"""
        devices = DeviceManager().enumerate()
        if not devices:
            raise RuntimeError("Aucun Stream Deck trouvé")
        
        self.deck = devices[0]
        self.deck.open()
        self.deck.reset()
        self.deck.set_brightness(70)
        
        # Callback pour les touches
        self.deck.set_key_callback(self._on_key_press)
        
        # Affichage initial
        await self._update_display()
        
    async def _start_socket_server(self):
        """Démarre le serveur socket Unix"""
        # Supprimer le socket existant
        if self.socket_path.exists():
            self.socket_path.unlink()
        
        server = await asyncio.start_unix_server(
            self._handle_client,
            path=str(self.socket_path)
        )
        
        # Permissions
        os.chmod(self.socket_path, 0o600)
        
        async with server:
            await server.serve_forever()
            
    async def _handle_client(self, reader, writer):
        """Traite un message entrant"""
        try:
            data = await reader.read(4096)
            if data:
                message = json.loads(data.decode())
                await self._process_message(message)
        except Exception as e:
            print(f"Erreur: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            
    async def _process_message(self, message: dict):
        """Traite un message de Claude Code"""
        event = message.get("event")
        data = message.get("data", {})
        
        if event == "SessionStart":
            self.state["status"] = "idle"
            self.state["session_id"] = data.get("session_id")
            
        elif event == "SessionEnd":
            self.state["status"] = "inactive"
            self.state["session_id"] = None
            self.state["tool"] = None
            
        elif event == "UserPromptSubmit":
            self.state["status"] = "thinking"
            
        elif event == "PreToolUse":
            self.state["status"] = "tool_running"
            self.state["tool"] = data.get("tool_name")
            
        elif event == "PostToolUse":
            self.state["status"] = "thinking"
            self.state["tool"] = None
            
        elif event == "Stop":
            self.state["status"] = "idle"
            self.state["tool"] = None
            
        await self._update_display()
        
    async def _update_display(self):
        """Met à jour l'affichage du Stream Deck"""
        if not self.deck:
            return
            
        for key_index, config in self.button_config.items():
            if config["type"] == "status":
                await self._render_status_button(key_index)
            elif config["type"] == "action":
                await self._render_action_button(key_index, config["action"])
                
    async def _render_status_button(self, key_index: int):
        """Render le bouton de statut"""
        status = self.state["status"]
        tool = self.state.get("tool")
        
        # Sélection de l'icône
        icon_map = {
            "inactive": "inactive.png",
            "idle": "idle.png",
            "thinking": "thinking.png",
            "tool_running": f"tool-{tool.lower()}.png" if tool else "tool-generic.png"
        }
        
        icon_name = icon_map.get(status, "inactive.png")
        icon_path = self.assets_dir / "icons" / icon_name
        
        if not icon_path.exists():
            icon_path = self.assets_dir / "icons" / "inactive.png"
            
        # Créer l'image
        image = PILHelper.create_image(self.deck)
        icon = Image.open(icon_path).resize((72, 72))
        
        # Titre
        title = tool if tool else status.replace("_", " ").title()
        
        draw = ImageDraw.Draw(image)
        # Centrer l'icône et ajouter le titre en bas
        # ... (code de rendu)
        
        native = PILHelper.to_native_format(self.deck, image)
        self.deck.set_key_image(key_index, native)
        
    def _on_key_press(self, deck, key, state):
        """Callback pour les appuis de touches"""
        if not state:  # Release
            return
            
        config = self.button_config.get(key)
        if not config:
            return
            
        if config["type"] == "action":
            action = config["action"]
            asyncio.create_task(self._execute_action(action))
            
    async def _execute_action(self, action: str):
        """Exécute une action"""
        import subprocess
        
        if action == "new_session":
            # Ouvrir un nouveau terminal avec claude
            subprocess.Popen([
                "osascript", "-e",
                'tell app "Terminal" to do script "claude"'
            ])
            
        elif action == "resume":
            subprocess.Popen([
                "osascript", "-e",
                'tell app "Terminal" to do script "claude --resume"'
            ])
            
        elif action == "interrupt":
            # Envoyer Escape au terminal actif
            subprocess.Popen([
                "osascript", "-e",
                'tell app "System Events" to keystroke escape'
            ])


def main():
    daemon = ClaudeStreamDeckDaemon()
    
    # Gestion des signaux
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))
    
    try:
        loop.run_until_complete(daemon.start())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
```

### 7.5 Configuration YAML

**`config/buttons.yaml`** :

```yaml
# Configuration des boutons Stream Deck pour Claude Code

layout:
  # Disposition pour Stream Deck 15 touches (5x3)
  # Ligne 0
  - position: [0, 0]
    type: status
    
  - position: [1, 0]
    type: action
    action: new_session
    label: "New"
    icon: new-session.png
    
  - position: [2, 0]
    type: action
    action: resume
    label: "Resume"
    icon: resume.png
    
  - position: [3, 0]
    type: action
    action: interrupt
    label: "Stop"
    icon: interrupt.png
    
  - position: [4, 0]
    type: action
    action: prompt
    label: "Review"
    prompt: "Please review the code I just wrote for any issues."
    icon: review.png

  # Ligne 1 - Prompts prédéfinis
  - position: [0, 1]
    type: action
    action: prompt
    label: "Explain"
    prompt: "Explain the current file."
    
  - position: [1, 1]
    type: action
    action: prompt
    label: "Test"
    prompt: "Write tests for the current file."
    
  - position: [2, 1]
    type: action
    action: prompt
    label: "Refactor"
    prompt: "Refactor this code for better readability."
    
  - position: [3, 1]
    type: action
    action: prompt
    label: "Docs"
    prompt: "Add documentation to this code."
    
  - position: [4, 1]
    type: folder
    label: "More..."
    folder: prompts_page2

# États visuels
states:
  inactive:
    background: "#333333"
    icon: inactive.png
    title: "Offline"
    
  idle:
    background: "#1a472a"
    icon: idle.png
    title: "Ready"
    
  thinking:
    background: "#1a3a5c"
    icon: thinking.png
    title: "Thinking..."
    animation: pulse
    
  tool_running:
    background: "#5c3a1a"
    icon: tool-generic.png
    title: "{tool_name}"
    
# Icônes spécifiques par outil
tool_icons:
  Bash: tool-bash.png
  Edit: tool-edit.png
  Write: tool-write.png
  Read: tool-read.png
  Grep: tool-grep.png
  WebFetch: tool-web.png
  Task: tool-task.png
```

### 7.6 Service systemd

**`systemd/claude-streamdeck.service`** :

```ini
[Unit]
Description=Claude Code Stream Deck Integration
After=network.target

[Service]
Type=simple
User=%i
ExecStart=/usr/local/bin/claude-streamdeck-daemon
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
```

---

## Annexes

### A. Codes de sortie des hooks

| Code | Signification | Comportement |
|------|---------------|--------------|
| 0 | Succès | Continue normalement |
| 1 | Erreur | Log l'erreur, continue |
| 2 | Blocage | Bloque l'action, feedback à Claude |

### B. Outils Claude Code

| Outil | Description | Fichiers concernés |
|-------|-------------|-------------------|
| `Bash` | Exécution de commandes | — |
| `Edit` | Modification de fichier | ✅ |
| `Write` | Création de fichier | ✅ |
| `Read` | Lecture de fichier | ✅ |
| `Grep` | Recherche dans fichiers | ✅ |
| `WebFetch` | Requête HTTP | — |
| `Task` | Sous-agent | — |
| `MultiEdit` | Éditions multiples | ✅ |

### C. Spécifications matérielles Stream Deck

| Modèle | Touches | Taille image (standard) | Taille image (@2x) | DeviceType |
|--------|---------|-------------------------|--------------------| -----------|
| Original | 15 (5×3) | 72×72 | 144×144 | 0 |
| Mini | 6 (3×2) | 80×80 | 160×160 | 1 |
| XL | 32 (8×4) | 96×96 | 144×144 | 2 |
| + | 8 + 4 dials | 120×120 | 240×240 | 7 |
| Neo | 8 (4×2) | 72×72 | 144×144 | 9 |

### D. Dépendances

**Python** :
```
streamdeck>=0.9.5
pillow>=10.0.0
pyyaml>=6.0
```

**Système (Debian/Ubuntu)** :
```bash
sudo apt install libusb-1.0-0-dev libhidapi-libusb0
```

**Système (macOS)** :
```bash
brew install hidapi
```

### E. Références

- [Documentation officielle des hooks Claude Code](https://docs.claude.com/en/docs/claude-code/hooks)
- [Stream Deck SDK](https://docs.elgato.com/streamdeck/sdk/)
- [python-elgato-streamdeck](https://github.com/abcminiuser/python-elgato-streamdeck)
- [Stream Deck HID Protocol](https://docs.elgato.com/streamdeck/hid/)

---

*Document généré le 17 janvier 2026.*
*Version 1.0*
