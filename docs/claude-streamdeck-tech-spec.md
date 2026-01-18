# Spécification technique : Claude Code Stream Deck MVP

## Metadata

| Champ | Valeur |
|-------|--------|
| **PRD associé** | claude-streamdeck-prd.md |
| **Version** | 1.0 |
| **Date** | 17 janvier 2026 |

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Structure du projet](#2-structure-du-projet)
3. [Composant 1 : Hook Script](#3-composant-1--hook-script)
4. [Composant 2 : Daemon](#4-composant-2--daemon)
5. [Composant 3 : Installation](#5-composant-3--installation)
6. [Assets graphiques](#6-assets-graphiques)
7. [Mapping User Stories → Implémentation](#7-mapping-user-stories--implémentation)
8. [Tests](#8-tests)

---

## 1. Vue d'ensemble

### 1.1 Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              CLAUDE CODE                                  │
│                                                                          │
│  ~/.claude/settings.json                                                 │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ hooks.SessionStart  ──►  streamdeck-notify.sh SessionStart         │ │
│  │ hooks.SessionEnd    ──►  streamdeck-notify.sh SessionEnd           │ │
│  │ hooks.UserPromptSubmit ► streamdeck-notify.sh UserPromptSubmit     │ │
│  │ hooks.PreToolUse    ──►  streamdeck-notify.sh PreToolUse           │ │
│  │ hooks.PostToolUse   ──►  streamdeck-notify.sh PostToolUse          │ │
│  │ hooks.Stop          ──►  streamdeck-notify.sh Stop                 │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ stdin: JSON
                                      ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         HOOK SCRIPT (bash)                                │
│                                                                          │
│  ~/.claude/hooks/streamdeck-notify.sh                                    │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ 1. Lire JSON depuis stdin                                          │ │
│  │ 2. Extraire event_type et tool_name                                │ │
│  │ 3. Envoyer message au socket Unix                                  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ socket: ~/.claude/streamdeck.sock
                                      ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                            DAEMON (Python)                                │
│                                                                          │
│  claude-streamdeck-daemon                                                │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ SocketServer         │ StateMachine        │ StreamDeckController  │ │
│  │ - listen()           │ - current_state     │ - connect()           │ │
│  │ - handle_message()   │ - transition()      │ - set_key_image()     │ │
│  │                      │ - get_display()     │ - on_key_press()      │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ USB HID
                                      ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                           STREAM DECK                                     │
│                                                                          │
│  ┌─────────┬─────────┬─────────┬─────────┬─────────┐                    │
│  │ Key 0   │ Key 1   │ Key 2   │ Key 3   │ Key 4   │                    │
│  │ STATUS  │ NEW     │ RESUME  │ STOP    │ (vide)  │                    │
│  └─────────┴─────────┴─────────┴─────────┴─────────┘                    │
└──────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Flux de données

| Événement | Source | Flux |
|-----------|--------|------|
| Changement d'état | Claude Code hook | Hook → Script → Socket → Daemon → Stream Deck |
| Appui touche | Stream Deck | Stream Deck → Daemon → Terminal (subprocess) |

---

## 2. Structure du projet

```
claude-streamdeck/
│
├── README.md                           # Documentation utilisateur
├── LICENSE                             # MIT
│
├── install.sh                          # Script d'installation principal
├── uninstall.sh                        # Script de désinstallation
│
├── hooks/
│   └── streamdeck-notify.sh            # Script hook pour Claude Code
│
├── daemon/
│   ├── requirements.txt                # Dépendances Python
│   ├── setup.py                        # Package Python (optionnel)
│   │
│   └── claude_streamdeck/
│       ├── __init__.py
│       ├── __main__.py                 # Entry point: python -m claude_streamdeck
│       ├── daemon.py                   # Classe principale
│       ├── socket_server.py            # Serveur socket Unix
│       ├── state_machine.py            # Machine à états
│       ├── streamdeck_controller.py    # Interface Stream Deck
│       ├── actions.py                  # Actions (new, resume, stop)
│       └── config.py                   # Configuration
│
├── assets/
│   └── icons/
│       ├── status-inactive.png         # 144x144 (@2x), gris
│       ├── status-idle.png             # 144x144 (@2x), vert
│       ├── status-thinking.png         # 144x144 (@2x), bleu
│       ├── status-tool.png             # 144x144 (@2x), orange
│       ├── action-new.png              # 144x144 (@2x)
│       ├── action-resume.png           # 144x144 (@2x)
│       └── action-stop.png             # 144x144 (@2x)
│
├── services/
│   ├── macos/
│   │   └── com.claude.streamdeck.plist # LaunchAgent macOS
│   └── linux/
│       └── claude-streamdeck.service   # systemd user service
│
└── tests/
    ├── test_state_machine.py
    ├── test_socket_server.py
    └── test_integration.py
```

---

## 3. Composant 1 : Hook Script

### 3.1 Spécification

| Attribut | Valeur |
|----------|--------|
| **Fichier** | `~/.claude/hooks/streamdeck-notify.sh` |
| **Langage** | Bash |
| **Input** | Argument $1 = event type, stdin = JSON |
| **Output** | Message envoyé au socket Unix |
| **Dépendances** | `jq`, `nc` (netcat) |

### 3.2 Implémentation

```bash
#!/bin/bash
# streamdeck-notify.sh
# Hook script pour envoyer les événements Claude Code au daemon Stream Deck

set -euo pipefail

# Configuration
SOCKET_PATH="${CLAUDE_STREAMDECK_SOCKET:-$HOME/.claude/streamdeck.sock}"
EVENT_TYPE="${1:-unknown}"

# Lire le JSON depuis stdin (avec timeout pour éviter de bloquer)
INPUT_JSON=$(timeout 1 cat 2>/dev/null || echo '{}')

# Extraire le nom de l'outil si présent
TOOL_NAME=""
if command -v jq &> /dev/null; then
    TOOL_NAME=$(echo "$INPUT_JSON" | jq -r '.tool_name // empty' 2>/dev/null || echo "")
fi

# Construire le message
TIMESTAMP=$(date +%s%3N 2>/dev/null || date +%s)
MESSAGE=$(cat <<EOF
{"event":"${EVENT_TYPE}","tool":"${TOOL_NAME}","timestamp":${TIMESTAMP}}
EOF
)

# Envoyer au daemon via socket Unix
if [[ -S "$SOCKET_PATH" ]]; then
    echo "$MESSAGE" | nc -U -w1 "$SOCKET_PATH" 2>/dev/null || true
fi

# Toujours exit 0 pour ne pas bloquer Claude Code
exit 0
```

### 3.3 Configuration hooks Claude Code

**Fichier** : `~/.claude/settings.json`

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.claude/hooks/streamdeck-notify.sh SessionStart"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.claude/hooks/streamdeck-notify.sh SessionEnd"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.claude/hooks/streamdeck-notify.sh UserPromptSubmit"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.claude/hooks/streamdeck-notify.sh PreToolUse"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.claude/hooks/streamdeck-notify.sh PostToolUse"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.claude/hooks/streamdeck-notify.sh Stop"
          }
        ]
      }
    ]
  }
}
```

### 3.4 Correspondance User Stories

| User Story | Critère d'acceptation | Implémentation |
|------------|----------------------|----------------|
| US-1 | AC-1.1 à AC-1.6 | Le script transmet tous les événements nécessaires pour les transitions d'état |
| US-1 | AC-1.7 | `timeout 1` + `nc -w1` garantissent une exécution < 500ms |

---

## 4. Composant 2 : Daemon

### 4.1 Module : config.py

```python
"""Configuration du daemon."""

from pathlib import Path
from dataclasses import dataclass


@dataclass
class Config:
    """Configuration globale du daemon."""
    
    # Chemins
    socket_path: Path = Path.home() / ".claude" / "streamdeck.sock"
    assets_path: Path = Path(__file__).parent.parent.parent / "assets" / "icons"
    
    # Stream Deck
    brightness: int = 70
    
    # Layout des touches (Stream Deck 15 touches)
    # Format: key_index -> (type, config)
    key_layout: dict = None
    
    def __post_init__(self):
        self.key_layout = {
            0: {"type": "status"},
            1: {"type": "action", "action": "new_session", "icon": "action-new.png"},
            2: {"type": "action", "action": "resume", "icon": "action-resume.png"},
            3: {"type": "action", "action": "stop", "icon": "action-stop.png"},
        }
    
    # États → Affichage
    state_display: dict = None
    
    def __post_init__(self):
        if self.key_layout is None:
            self.key_layout = {
                0: {"type": "status"},
                1: {"type": "action", "action": "new_session", "icon": "action-new.png"},
                2: {"type": "action", "action": "resume", "icon": "action-resume.png"},
                3: {"type": "action", "action": "stop", "icon": "action-stop.png"},
            }
        
        self.state_display = {
            "inactive": {"icon": "status-inactive.png", "title": "Offline"},
            "idle": {"icon": "status-idle.png", "title": "Ready"},
            "thinking": {"icon": "status-thinking.png", "title": "Thinking..."},
            "tool_running": {"icon": "status-tool.png", "title": "{tool}"},
        }
```

### 4.2 Module : state_machine.py

```python
"""Machine à états pour Claude Code."""

from enum import Enum
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class State(Enum):
    """États possibles de Claude Code."""
    INACTIVE = "inactive"
    IDLE = "idle"
    THINKING = "thinking"
    TOOL_RUNNING = "tool_running"


@dataclass
class StateContext:
    """Contexte associé à l'état courant."""
    state: State = State.INACTIVE
    tool_name: Optional[str] = None
    session_id: Optional[str] = None


class StateMachine:
    """
    Machine à états pour suivre l'état de Claude Code.
    
    Transitions:
        INACTIVE --[SessionStart]--> IDLE
        IDLE --[UserPromptSubmit]--> THINKING
        THINKING --[PreToolUse]--> TOOL_RUNNING
        TOOL_RUNNING --[PostToolUse]--> THINKING
        THINKING --[Stop]--> IDLE
        * --[SessionEnd]--> INACTIVE
    """
    
    def __init__(self):
        self._context = StateContext()
        self._listeners = []
    
    @property
    def state(self) -> State:
        return self._context.state
    
    @property
    def context(self) -> StateContext:
        return self._context
    
    def add_listener(self, callback):
        """Ajoute un listener appelé à chaque transition."""
        self._listeners.append(callback)
    
    def process_event(self, event: str, tool_name: Optional[str] = None):
        """
        Traite un événement et effectue la transition d'état appropriée.
        
        Args:
            event: Type d'événement (SessionStart, PreToolUse, etc.)
            tool_name: Nom de l'outil (pour PreToolUse)
        """
        old_state = self._context.state
        
        if event == "SessionStart":
            self._context.state = State.IDLE
            self._context.tool_name = None
            
        elif event == "SessionEnd":
            self._context.state = State.INACTIVE
            self._context.tool_name = None
            self._context.session_id = None
            
        elif event == "UserPromptSubmit":
            if self._context.state in (State.IDLE, State.INACTIVE):
                self._context.state = State.THINKING
                
        elif event == "PreToolUse":
            self._context.state = State.TOOL_RUNNING
            self._context.tool_name = tool_name
            
        elif event == "PostToolUse":
            self._context.state = State.THINKING
            self._context.tool_name = None
            
        elif event == "Stop":
            if self._context.state != State.INACTIVE:
                self._context.state = State.IDLE
                self._context.tool_name = None
        
        # Notifier les listeners si l'état a changé
        if old_state != self._context.state:
            logger.info(f"State transition: {old_state.value} -> {self._context.state.value}")
            for listener in self._listeners:
                listener(self._context)
    
    def get_display_info(self) -> dict:
        """
        Retourne les informations d'affichage pour l'état courant.
        
        Returns:
            dict avec 'icon' et 'title'
        """
        state = self._context.state.value
        
        display = {
            "inactive": {"icon": "status-inactive.png", "title": "Offline"},
            "idle": {"icon": "status-idle.png", "title": "Ready"},
            "thinking": {"icon": "status-thinking.png", "title": "Thinking..."},
            "tool_running": {"icon": "status-tool.png", "title": self._context.tool_name or "Tool"},
        }
        
        return display.get(state, display["inactive"])
```

### 4.3 Module : socket_server.py

```python
"""Serveur socket Unix pour recevoir les événements."""

import asyncio
import json
import os
from pathlib import Path
import logging
from typing import Callable

logger = logging.getLogger(__name__)


class SocketServer:
    """
    Serveur socket Unix asynchrone.
    
    Reçoit les messages JSON du hook script et les transmet au callback.
    """
    
    def __init__(self, socket_path: Path, message_callback: Callable[[dict], None]):
        self.socket_path = socket_path
        self.message_callback = message_callback
        self._server = None
    
    async def start(self):
        """Démarre le serveur socket."""
        # Supprimer le socket existant
        if self.socket_path.exists():
            self.socket_path.unlink()
        
        # Créer le répertoire parent si nécessaire
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Démarrer le serveur
        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=str(self.socket_path)
        )
        
        # Permissions restrictives
        os.chmod(self.socket_path, 0o600)
        
        logger.info(f"Socket server listening on {self.socket_path}")
        
        async with self._server:
            await self._server.serve_forever()
    
    async def stop(self):
        """Arrête le serveur."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        if self.socket_path.exists():
            self.socket_path.unlink()
    
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Traite une connexion client."""
        try:
            data = await asyncio.wait_for(reader.read(4096), timeout=5.0)
            
            if data:
                message = json.loads(data.decode('utf-8'))
                logger.debug(f"Received: {message}")
                
                # Appeler le callback de manière synchrone
                self.message_callback(message)
                
        except asyncio.TimeoutError:
            logger.warning("Client timeout")
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
```

### 4.4 Module : streamdeck_controller.py

```python
"""Contrôleur Stream Deck."""

import asyncio
from pathlib import Path
from typing import Callable, Optional
import logging

from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class StreamDeckController:
    """
    Interface avec le Stream Deck hardware.
    
    Gère la connexion, l'affichage et les événements de touches.
    """
    
    def __init__(self, assets_path: Path, key_callback: Optional[Callable[[int], None]] = None):
        self.assets_path = assets_path
        self.key_callback = key_callback
        self.deck = None
        self._icon_cache = {}
    
    def connect(self) -> bool:
        """
        Connecte au Stream Deck.
        
        Returns:
            True si la connexion réussit, False sinon.
        """
        try:
            devices = DeviceManager().enumerate()
            
            if not devices:
                logger.warning("No Stream Deck found")
                return False
            
            self.deck = devices[0]
            self.deck.open()
            self.deck.reset()
            self.deck.set_brightness(70)
            
            # Enregistrer le callback
            if self.key_callback:
                self.deck.set_key_callback(self._on_key_event)
            
            logger.info(f"Connected to {self.deck.deck_type()}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Déconnecte du Stream Deck."""
        if self.deck:
            try:
                self.deck.reset()
                self.deck.close()
            except Exception as e:
                logger.warning(f"Error disconnecting: {e}")
            finally:
                self.deck = None
    
    def set_key(self, key_index: int, icon_name: str, title: str = ""):
        """
        Configure l'affichage d'une touche.
        
        Args:
            key_index: Index de la touche (0-14 pour SD 15 touches)
            icon_name: Nom du fichier icône dans assets_path
            title: Texte à afficher sous l'icône
        """
        if not self.deck:
            return
        
        try:
            # Créer l'image
            image = self._create_key_image(icon_name, title)
            
            # Convertir au format natif et afficher
            native = PILHelper.to_native_format(self.deck, image)
            self.deck.set_key_image(key_index, native)
            
        except Exception as e:
            logger.error(f"Failed to set key {key_index}: {e}")
    
    def flash_key(self, key_index: int, duration: float = 0.1):
        """
        Flash une touche pour feedback visuel.
        
        Args:
            key_index: Index de la touche
            duration: Durée du flash en secondes
        """
        if not self.deck:
            return
        
        # Créer une image blanche
        image = PILHelper.create_image(self.deck)
        draw = ImageDraw.Draw(image)
        draw.rectangle([0, 0, image.width, image.height], fill="white")
        
        native = PILHelper.to_native_format(self.deck, image)
        self.deck.set_key_image(key_index, native)
        
        # Note: Le restauration sera faite par le caller
    
    def clear_key(self, key_index: int):
        """Efface une touche (noir)."""
        if not self.deck:
            return
        
        image = PILHelper.create_image(self.deck)
        native = PILHelper.to_native_format(self.deck, image)
        self.deck.set_key_image(key_index, native)
    
    def _create_key_image(self, icon_name: str, title: str) -> Image.Image:
        """Crée l'image pour une touche."""
        # Créer l'image de base
        image = PILHelper.create_image(self.deck)
        draw = ImageDraw.Draw(image)
        
        # Fond noir
        draw.rectangle([0, 0, image.width, image.height], fill="black")
        
        # Charger l'icône
        icon_path = self.assets_path / icon_name
        if icon_path.exists():
            icon = Image.open(icon_path).convert("RGBA")
            
            # Redimensionner l'icône (48x48 pour laisser place au titre)
            icon_size = 48 if title else 72
            icon = icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
            
            # Centrer l'icône
            x = (image.width - icon_size) // 2
            y = 5 if title else (image.height - icon_size) // 2
            
            image.paste(icon, (x, y), icon)
        
        # Ajouter le titre
        if title:
            # Tronquer si trop long
            if len(title) > 10:
                title = title[:9] + "…"
            
            # Police (utiliser une police système)
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
            except:
                font = ImageFont.load_default()
            
            # Centrer le texte en bas
            bbox = draw.textbbox((0, 0), title, font=font)
            text_width = bbox[2] - bbox[0]
            x = (image.width - text_width) // 2
            y = image.height - 18
            
            draw.text((x, y), title, font=font, fill="white")
        
        return image
    
    def _on_key_event(self, deck, key: int, state: bool):
        """Callback interne pour les événements de touche."""
        if state and self.key_callback:  # Key down only
            self.key_callback(key)
```

### 4.5 Module : actions.py

```python
"""Actions déclenchées par les touches."""

import subprocess
import sys
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class Actions:
    """
    Actions disponibles sur le Stream Deck.
    
    Chaque action est une méthode qui peut être appelée lors d'un appui de touche.
    """
    
    @staticmethod
    def new_session(project_dir: Optional[str] = None):
        """
        Lance une nouvelle session Claude Code.
        
        Ouvre un nouveau terminal et exécute 'claude'.
        
        Args:
            project_dir: Répertoire du projet (optionnel)
        """
        logger.info("Action: new_session")
        
        cmd = "claude"
        if project_dir:
            cmd = f"cd {project_dir} && claude"
        
        if sys.platform == "darwin":
            # macOS: utiliser osascript pour ouvrir Terminal
            script = f'tell app "Terminal" to do script "{cmd}"'
            subprocess.Popen(["osascript", "-e", script])
            
        else:
            # Linux: essayer plusieurs terminaux
            terminals = [
                ["gnome-terminal", "--", "bash", "-c", f"{cmd}; exec bash"],
                ["konsole", "-e", "bash", "-c", f"{cmd}; exec bash"],
                ["xterm", "-e", f"{cmd}; exec bash"],
            ]
            
            for terminal_cmd in terminals:
                try:
                    subprocess.Popen(terminal_cmd)
                    return
                except FileNotFoundError:
                    continue
            
            logger.error("No terminal emulator found")
    
    @staticmethod
    def resume():
        """
        Reprend la dernière session Claude Code.
        
        Ouvre un nouveau terminal et exécute 'claude --resume'.
        """
        logger.info("Action: resume")
        
        cmd = "claude --resume"
        
        if sys.platform == "darwin":
            script = f'tell app "Terminal" to do script "{cmd}"'
            subprocess.Popen(["osascript", "-e", script])
            
        else:
            terminals = [
                ["gnome-terminal", "--", "bash", "-c", f"{cmd}; exec bash"],
                ["konsole", "-e", "bash", "-c", f"{cmd}; exec bash"],
                ["xterm", "-e", f"{cmd}; exec bash"],
            ]
            
            for terminal_cmd in terminals:
                try:
                    subprocess.Popen(terminal_cmd)
                    return
                except FileNotFoundError:
                    continue
    
    @staticmethod
    def stop():
        """
        Interrompt Claude Code.
        
        Envoie la touche Escape au terminal actif.
        """
        logger.info("Action: stop")
        
        if sys.platform == "darwin":
            # macOS: envoyer Escape via System Events
            script = '''
            tell application "System Events"
                key code 53
            end tell
            '''
            subprocess.Popen(["osascript", "-e", script])
            
        else:
            # Linux: utiliser xdotool
            try:
                subprocess.Popen(["xdotool", "key", "Escape"])
            except FileNotFoundError:
                logger.error("xdotool not found - install with: sudo apt install xdotool")
```

### 4.6 Module : daemon.py (principal)

```python
"""Daemon principal."""

import asyncio
import signal
import logging
from pathlib import Path

from .config import Config
from .state_machine import StateMachine
from .socket_server import SocketServer
from .streamdeck_controller import StreamDeckController
from .actions import Actions

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ClaudeStreamDeckDaemon:
    """
    Daemon principal orchestrant tous les composants.
    """
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.state_machine = StateMachine()
        self.streamdeck = StreamDeckController(
            assets_path=self.config.assets_path,
            key_callback=self._on_key_press
        )
        self.socket_server = None
        self._running = False
    
    async def start(self):
        """Démarre le daemon."""
        logger.info("Starting Claude Stream Deck daemon")
        self._running = True
        
        # Connecter au Stream Deck
        if not self.streamdeck.connect():
            logger.error("Failed to connect to Stream Deck")
            return
        
        # Enregistrer le listener de changement d'état
        self.state_machine.add_listener(self._on_state_change)
        
        # Affichage initial
        self._update_display()
        
        # Démarrer le serveur socket
        self.socket_server = SocketServer(
            socket_path=self.config.socket_path,
            message_callback=self._on_message
        )
        
        try:
            await self.socket_server.start()
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()
    
    async def stop(self):
        """Arrête le daemon."""
        logger.info("Stopping daemon")
        self._running = False
        
        if self.socket_server:
            await self.socket_server.stop()
        
        self.streamdeck.disconnect()
    
    def _on_message(self, message: dict):
        """Callback pour les messages du socket."""
        event = message.get("event")
        tool = message.get("tool")
        
        if event:
            self.state_machine.process_event(event, tool_name=tool)
    
    def _on_state_change(self, context):
        """Callback pour les changements d'état."""
        self._update_display()
    
    def _on_key_press(self, key_index: int):
        """Callback pour les appuis de touche."""
        config = self.config.key_layout.get(key_index)
        
        if not config:
            return
        
        # Flash pour feedback
        asyncio.create_task(self._flash_key(key_index))
        
        if config["type"] == "action":
            action = config["action"]
            
            if action == "new_session":
                Actions.new_session()
            elif action == "resume":
                Actions.resume()
            elif action == "stop":
                Actions.stop()
    
    async def _flash_key(self, key_index: int):
        """Flash une touche et restaure l'affichage."""
        self.streamdeck.flash_key(key_index)
        await asyncio.sleep(0.1)
        self._update_display()
    
    def _update_display(self):
        """Met à jour l'affichage complet du Stream Deck."""
        for key_index, config in self.config.key_layout.items():
            if config["type"] == "status":
                display = self.state_machine.get_display_info()
                self.streamdeck.set_key(key_index, display["icon"], display["title"])
                
            elif config["type"] == "action":
                self.streamdeck.set_key(
                    key_index,
                    config["icon"],
                    config.get("label", "")
                )


def main():
    """Point d'entrée du daemon."""
    daemon = ClaudeStreamDeckDaemon()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Gestion des signaux
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(daemon.stop())
        )
    
    try:
        loop.run_until_complete(daemon.start())
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == "__main__":
    main()
```

### 4.7 Module : \_\_main\_\_.py

```python
"""Entry point pour python -m claude_streamdeck."""

from .daemon import main

if __name__ == "__main__":
    main()
```

### 4.8 requirements.txt

```
streamdeck>=0.9.5
pillow>=10.0.0
```

### 4.9 Correspondance User Stories

| User Story | Critère | Module | Fonction/Méthode |
|------------|---------|--------|------------------|
| US-1 | AC-1.1 | state_machine.py | `State.INACTIVE`, `get_display_info()` |
| US-1 | AC-1.2 | state_machine.py | `State.IDLE`, transition sur `SessionStart` |
| US-1 | AC-1.3 | state_machine.py | `State.THINKING`, transition sur `UserPromptSubmit` |
| US-1 | AC-1.4 | state_machine.py | `State.TOOL_RUNNING`, `tool_name` dans context |
| US-1 | AC-1.5 | state_machine.py | Transition `Stop` → `IDLE` |
| US-1 | AC-1.6 | state_machine.py | Transition `SessionEnd` → `INACTIVE` |
| US-1 | AC-1.7 | socket_server.py | Traitement asynchrone, pas de polling |
| US-2 | AC-2.1 | config.py | `key_layout[1]` = new_session |
| US-2 | AC-2.2 | actions.py | `Actions.new_session()` |
| US-2 | AC-2.3 | state_machine.py | Hook `SessionStart` → state change |
| US-2 | AC-2.4 | daemon.py | `_flash_key()` |
| US-3 | AC-3.1 | config.py | `key_layout[2]` = resume |
| US-3 | AC-3.2 | actions.py | `Actions.resume()` |
| US-3 | AC-3.3 | actions.py | (Terminal affichera l'erreur Claude) |
| US-3 | AC-3.4 | state_machine.py | Hook `SessionStart` → state change |
| US-4 | AC-4.1 | config.py | `key_layout[3]` = stop |
| US-4 | AC-4.2 | actions.py | `Actions.stop()` |
| US-4 | AC-4.3 | state_machine.py | Hook `Stop` → state change |
| US-4 | AC-4.4 | daemon.py | `_on_key_press()` vérifie le type |

---

## 5. Composant 3 : Installation

### 5.1 Script install.sh

```bash
#!/bin/bash
# install.sh - Installation du daemon Claude Stream Deck
set -euo pipefail

echo "=== Claude Stream Deck Installation ==="
echo ""

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Détection de l'OS
OS="$(uname -s)"
case "$OS" in
    Darwin) OS_TYPE="macos" ;;
    Linux)  OS_TYPE="linux" ;;
    *)      echo -e "${RED}OS non supporté: $OS${NC}"; exit 1 ;;
esac

echo "OS détecté: $OS_TYPE"

# Répertoire d'installation
INSTALL_DIR="$HOME/.local/share/claude-streamdeck"
HOOKS_DIR="$HOME/.claude/hooks"
CLAUDE_SETTINGS="$HOME/.claude/settings.json"

# 1. Vérifier les prérequis
echo ""
echo "=== Vérification des prérequis ==="

# Python 3.10+
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 non trouvé. Installez Python 3.10+${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $PYTHON_VERSION"

# pip
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}pip3 non trouvé${NC}"
    exit 1
fi

# jq (pour les hooks)
if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}jq non trouvé, installation...${NC}"
    if [[ "$OS_TYPE" == "macos" ]]; then
        brew install jq
    else
        sudo apt-get install -y jq
    fi
fi

# netcat
if ! command -v nc &> /dev/null; then
    echo -e "${YELLOW}netcat non trouvé, installation...${NC}"
    if [[ "$OS_TYPE" == "linux" ]]; then
        sudo apt-get install -y netcat-openbsd
    fi
fi

# Dépendances USB pour Linux
if [[ "$OS_TYPE" == "linux" ]]; then
    echo "Installation des dépendances USB..."
    sudo apt-get install -y libusb-1.0-0-dev libhidapi-libusb0
    
    # udev rules
    echo "Configuration des règles udev..."
    sudo tee /etc/udev/rules.d/50-streamdeck.rules > /dev/null << 'EOF'
SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", MODE="0660", GROUP="plugdev"
EOF
    sudo udevadm control --reload-rules
    sudo usermod -aG plugdev "$USER" 2>/dev/null || true
fi

echo -e "${GREEN}Prérequis OK${NC}"

# 2. Créer les répertoires
echo ""
echo "=== Installation des fichiers ==="

mkdir -p "$INSTALL_DIR"
mkdir -p "$HOOKS_DIR"
mkdir -p "$HOME/.claude"

# 3. Copier les fichiers
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp -r "$SCRIPT_DIR/daemon" "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/assets" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/hooks/streamdeck-notify.sh" "$HOOKS_DIR/"
chmod +x "$HOOKS_DIR/streamdeck-notify.sh"

echo "Fichiers installés dans $INSTALL_DIR"

# 4. Installer les dépendances Python
echo ""
echo "=== Installation des dépendances Python ==="

pip3 install --user streamdeck pillow

# 5. Configurer les hooks Claude Code
echo ""
echo "=== Configuration des hooks Claude Code ==="

# Créer ou mettre à jour settings.json
if [[ -f "$CLAUDE_SETTINGS" ]]; then
    # Backup
    cp "$CLAUDE_SETTINGS" "$CLAUDE_SETTINGS.backup"
    
    # Merger les hooks (simplifié - en prod utiliser jq)
    echo -e "${YELLOW}settings.json existant détecté${NC}"
    echo "Ajoutez manuellement les hooks depuis: $SCRIPT_DIR/hooks/claude-settings.json"
else
    # Créer le fichier
    cat > "$CLAUDE_SETTINGS" << 'EOF'
{
  "hooks": {
    "SessionStart": [{"matcher": "", "hooks": [{"type": "command", "command": "$HOME/.claude/hooks/streamdeck-notify.sh SessionStart"}]}],
    "SessionEnd": [{"matcher": "", "hooks": [{"type": "command", "command": "$HOME/.claude/hooks/streamdeck-notify.sh SessionEnd"}]}],
    "UserPromptSubmit": [{"matcher": "", "hooks": [{"type": "command", "command": "$HOME/.claude/hooks/streamdeck-notify.sh UserPromptSubmit"}]}],
    "PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "$HOME/.claude/hooks/streamdeck-notify.sh PreToolUse"}]}],
    "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "$HOME/.claude/hooks/streamdeck-notify.sh PostToolUse"}]}],
    "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "$HOME/.claude/hooks/streamdeck-notify.sh Stop"}]}]
  }
}
EOF
    echo -e "${GREEN}Hooks configurés${NC}"
fi

# 6. Installer le service de démarrage automatique
echo ""
echo "=== Configuration du démarrage automatique ==="

if [[ "$OS_TYPE" == "macos" ]]; then
    PLIST_DIR="$HOME/Library/LaunchAgents"
    PLIST_FILE="$PLIST_DIR/com.claude.streamdeck.plist"
    
    mkdir -p "$PLIST_DIR"
    
    cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.claude.streamdeck</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(which python3)</string>
        <string>-m</string>
        <string>claude_streamdeck</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR/daemon</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>$INSTALL_DIR/daemon</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$HOME/.claude/streamdeck.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.claude/streamdeck.error.log</string>
</dict>
</plist>
EOF
    
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
    launchctl load "$PLIST_FILE"
    
    echo -e "${GREEN}LaunchAgent installé${NC}"

else
    # Linux systemd
    SERVICE_DIR="$HOME/.config/systemd/user"
    SERVICE_FILE="$SERVICE_DIR/claude-streamdeck.service"
    
    mkdir -p "$SERVICE_DIR"
    
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Claude Code Stream Deck Integration
After=default.target

[Service]
Type=simple
ExecStart=$(which python3) -m claude_streamdeck
WorkingDirectory=$INSTALL_DIR/daemon
Environment=PYTHONPATH=$INSTALL_DIR/daemon
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
    
    systemctl --user daemon-reload
    systemctl --user enable claude-streamdeck
    systemctl --user start claude-streamdeck
    
    echo -e "${GREEN}Service systemd installé${NC}"
fi

# 7. Terminé
echo ""
echo "=== Installation terminée ==="
echo ""
echo -e "${GREEN}✓ Daemon installé${NC}"
echo -e "${GREEN}✓ Hooks configurés${NC}"
echo -e "${GREEN}✓ Démarrage automatique activé${NC}"
echo ""
echo "Le daemon est maintenant actif."
echo "Logs: ~/.claude/streamdeck.log"
echo ""

if [[ "$OS_TYPE" == "linux" ]]; then
    echo -e "${YELLOW}NOTE: Vous devrez peut-être vous déconnecter/reconnecter"
    echo -e "pour que les permissions USB prennent effet.${NC}"
fi
```

### 5.2 Script uninstall.sh

```bash
#!/bin/bash
# uninstall.sh - Désinstallation du daemon Claude Stream Deck
set -euo pipefail

echo "=== Désinstallation Claude Stream Deck ==="

OS="$(uname -s)"
INSTALL_DIR="$HOME/.local/share/claude-streamdeck"

# Arrêter le service
if [[ "$OS" == "Darwin" ]]; then
    PLIST="$HOME/Library/LaunchAgents/com.claude.streamdeck.plist"
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
else
    systemctl --user stop claude-streamdeck 2>/dev/null || true
    systemctl --user disable claude-streamdeck 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/claude-streamdeck.service"
    systemctl --user daemon-reload
fi

# Supprimer les fichiers
rm -rf "$INSTALL_DIR"
rm -f "$HOME/.claude/hooks/streamdeck-notify.sh"
rm -f "$HOME/.claude/streamdeck.sock"

echo ""
echo "Désinstallation terminée."
echo ""
echo "NOTE: Les hooks dans ~/.claude/settings.json n'ont pas été supprimés."
echo "Vous pouvez les retirer manuellement si nécessaire."
```

### 5.3 Correspondance User Stories

| User Story | Critère | Fichier | Section |
|------------|---------|---------|---------|
| US-5 | AC-5.1 | install.sh | Entier |
| US-5 | AC-5.2 | install.sh | Détection OS |
| US-5 | AC-5.3 | install.sh | `pip3 install` |
| US-5 | AC-5.4 | install.sh | Section hooks |
| US-5 | AC-5.5 | install.sh | ~2min d'exécution |
| US-6 | AC-6.1 | install.sh | Section LaunchAgent |
| US-6 | AC-6.2 | install.sh | Section systemd |
| US-6 | AC-6.3 | daemon.py | (À implémenter: retry connect) |
| US-6 | AC-6.4 | install.sh | `KeepAlive`/`Restart=on-failure` |

---

## 6. Assets graphiques

### 6.1 Spécifications des icônes

> **Note** : Les tailles varient selon le modèle de Stream Deck. Pour une compatibilité maximale,
> fournir les icônes en haute résolution (@2x) et laisser la bibliothèque redimensionner.
>
> | Modèle | Taille standard | Taille @2x (recommandée) |
> |--------|-----------------|--------------------------|
> | Original | 72×72 | 144×144 |
> | Mini | 80×80 | 160×160 |
> | XL | 96×96 | 144×144 |
> | + | 120×120 | 240×240 |
> | Neo | 72×72 | 144×144 |

| Fichier | Taille recommandée | Couleur dominante | Description |
|---------|-------------------|-------------------|-------------|
| status-inactive.png | 144×144 | Gris (#666666) | Cercle vide ou power off |
| status-idle.png | 144×144 | Vert (#00AA00) | Checkmark ou cercle plein |
| status-thinking.png | 144×144 | Bleu (#0066CC) | Cerveau ou points de suspension |
| status-tool.png | 144×144 | Orange (#FF8800) | Engrenage ou outil |
| action-new.png | 144×144 | Blanc | Plus (+) |
| action-resume.png | 144×144 | Blanc | Play (▶) |
| action-stop.png | 144×144 | Rouge (#CC0000) | Stop (■) ou X |

### 6.2 Format

- PNG avec transparence (RGBA)
- Fond transparent ou noir (#000000)
- Icône centrée
- Marge de 8px minimum (ajustée pour haute résolution)

---

## 7. Mapping User Stories → Implémentation

| User Story | Composant | Fichier(s) | Fonction(s) clé(s) |
|------------|-----------|------------|-------------------|
| **US-1** | Daemon | state_machine.py, streamdeck_controller.py | `StateMachine`, `set_key()` |
| **US-2** | Daemon | actions.py, daemon.py | `Actions.new_session()`, `_on_key_press()` |
| **US-3** | Daemon | actions.py | `Actions.resume()` |
| **US-4** | Daemon | actions.py | `Actions.stop()` |
| **US-5** | Installation | install.sh | Script entier |
| **US-6** | Installation | install.sh, services/*.plist/*.service | LaunchAgent/systemd |

---

## 8. Tests

### 8.1 Tests unitaires

**test_state_machine.py** :

```python
import pytest
from claude_streamdeck.state_machine import StateMachine, State


class TestStateMachine:
    def test_initial_state_is_inactive(self):
        sm = StateMachine()
        assert sm.state == State.INACTIVE
    
    def test_session_start_transitions_to_idle(self):
        sm = StateMachine()
        sm.process_event("SessionStart")
        assert sm.state == State.IDLE
    
    def test_user_prompt_transitions_to_thinking(self):
        sm = StateMachine()
        sm.process_event("SessionStart")
        sm.process_event("UserPromptSubmit")
        assert sm.state == State.THINKING
    
    def test_pre_tool_use_transitions_to_tool_running(self):
        sm = StateMachine()
        sm.process_event("SessionStart")
        sm.process_event("UserPromptSubmit")
        sm.process_event("PreToolUse", tool_name="Edit")
        assert sm.state == State.TOOL_RUNNING
        assert sm.context.tool_name == "Edit"
    
    def test_post_tool_use_transitions_to_thinking(self):
        sm = StateMachine()
        sm.process_event("SessionStart")
        sm.process_event("UserPromptSubmit")
        sm.process_event("PreToolUse", tool_name="Edit")
        sm.process_event("PostToolUse")
        assert sm.state == State.THINKING
        assert sm.context.tool_name is None
    
    def test_stop_transitions_to_idle(self):
        sm = StateMachine()
        sm.process_event("SessionStart")
        sm.process_event("UserPromptSubmit")
        sm.process_event("Stop")
        assert sm.state == State.IDLE
    
    def test_session_end_transitions_to_inactive(self):
        sm = StateMachine()
        sm.process_event("SessionStart")
        sm.process_event("SessionEnd")
        assert sm.state == State.INACTIVE
    
    def test_listener_is_called_on_transition(self):
        sm = StateMachine()
        called = []
        sm.add_listener(lambda ctx: called.append(ctx.state))
        
        sm.process_event("SessionStart")
        
        assert len(called) == 1
        assert called[0] == State.IDLE
```

### 8.2 Test d'intégration manuel

```bash
# 1. Démarrer le daemon manuellement
cd ~/.local/share/claude-streamdeck/daemon
python3 -m claude_streamdeck

# 2. Dans un autre terminal, simuler des événements
echo '{"event":"SessionStart","tool":"","timestamp":1234567890}' | nc -U ~/.claude/streamdeck.sock

echo '{"event":"UserPromptSubmit","tool":"","timestamp":1234567890}' | nc -U ~/.claude/streamdeck.sock

echo '{"event":"PreToolUse","tool":"Edit","timestamp":1234567890}' | nc -U ~/.claude/streamdeck.sock

echo '{"event":"PostToolUse","tool":"","timestamp":1234567890}' | nc -U ~/.claude/streamdeck.sock

echo '{"event":"Stop","tool":"","timestamp":1234567890}' | nc -U ~/.claude/streamdeck.sock

echo '{"event":"SessionEnd","tool":"","timestamp":1234567890}' | nc -U ~/.claude/streamdeck.sock
```

---

*Fin de la spécification technique.*
