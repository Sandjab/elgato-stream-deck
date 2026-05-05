# Spec — Stream Deck Core Daemon (extensible, multi-modèles)

**Date** : 2026-05-06
**Statut** : Design validé en brainstorming, prêt pour planification d'implémentation
**Contexte** : Refonte du POC `claude-streamdeck` en daemon générique réutilisable

## 1. Objectif

Construire un **daemon Python monoprocess** qui :

1. Pilote un ou plusieurs Stream Deck Elgato (XL d'abord, puis autres modèles).
2. Expose un **protocole JSON sur socket Unix** offrant des **primitives atomiques** (afficher une image sur un bouton, animer, marquer un bouton actif, capturer les pressions).
3. Est **extensible in-process** : des modules Python (« extensions ») chargés par configuration peuvent enrichir le daemon avec de la logique métier (machines à états, scènes, claim/release, intégration Claude Code…) en appelant l'API du core directement et en enregistrant leurs propres commandes JSON.

Le POC actuel (intégration Claude Code avec états codés en dur, actions new/resume/stop) sera réimplémenté plus tard comme **une extension** au-dessus de ce core, hors du scope de ce spec.

## 2. Non-objectifs

- **Pas de logique métier dans le core** : pas de machine à états Claude, pas d'ownership, pas de scènes, pas d'actions à exécuter.
- **Pas de support multi-transport** : seul le socket Unix est exposé (TCP/WebSocket peuvent venir plus tard).
- **Pas de plugin discovery automatique** (entry points, packages pip-installables) : les extensions sont importées par nom depuis la config.
- **Pas de persistence** des assets uploadés ni de l'état d'affichage : un redémarrage repart vide.
- **Pas d'authentification réseau** : le socket est protégé par les permissions filesystem (`0o600`).

## 3. Architecture globale

```
┌─────────────────────────────────────────────────────────────┐
│  PROCESS daemon                                             │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Extensions (in-process, optionnelles, par config)    │  │
│  │  → utilisent l'API Python du core                    │  │
│  │  → enregistrent leurs commandes JSON au socket       │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↕ API Python                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Core (toujours actif)                                │  │
│  │  DeviceManager / AssetRegistry / DisplayEngine /     │  │
│  │  InputDispatcher / EventBus / CommandRegistry        │  │
│  │  SocketServer (JSONL persistant, multi-clients)      │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↕ USB HID (lib `streamdeck`)       │
└─────────────────────────────────────────────────────────────┘
                          ↕ socket Unix (JSONL)
                  Producteurs externes
              (bash, scripts, hooks Claude Code)
```

Un seul process. Le socket Unix sert exclusivement aux clients **non-Python** ou aux clients qui doivent vivre dans un autre process. Les extensions Python ne passent pas par le socket : elles ont l'`CoreAPI` injecté.

## 4. Composants du core

### 4.1 DeviceManager

- Énumère les Stream Decks connectés au démarrage et à la reconnexion HID.
- Détecte le modèle via le product ID, instancie un `Device` adapté, lui attribue un `device_id` stable de la forme `<model>-<serial>` (ex. `xl-CL12345678`).
- Gère reconnexion automatique (boucle existante du POC).
- Émet `device.connected` / `device.disconnected` sur l'`EventBus`.

### 4.2 Device (abstraction)

```python
class Device:
    id: str
    model: DeviceModel        # XL, MK2, MINI, PLUS, NEO, PEDAL, ORIGINAL...
    key_count: int
    image_size: tuple[int, int]
    image_format: ImageFormat # JPEG | BMP
    has_screen: bool          # LCD du Plus
    has_dial: bool            # dials du Plus

    def set_key_image(button: int, image: PIL.Image) -> None: ...
    def clear_key(button: int) -> None: ...
    def set_brightness(value: int) -> None: ...
    def set_key_callback(cb: Callable[[int, bool], None]) -> None: ...
```

MVP : seul le modèle XL est implémenté concrètement. Les autres sont prêts à brancher en complétant la fabrique de `Device` (la lib `streamdeck` expose nativement leurs caractéristiques).

### 4.3 AssetRegistry

Stocke les images par nom et fournit des bitmaps prêts à pousser au device.

- **Sources d'assets** :
  - **Statiques** : chargés au démarrage depuis un dossier configuré (ex. `~/.config/claude-streamdeck/assets/`). Les noms = noms de fichier sans extension. Formats acceptés : PNG, JPEG, GIF.
  - **Dynamiques** : uploadés via la commande `asset.upload` (bytes en base64). Vivent en RAM.
- **Cache de redimensionnement** : pour chaque couple `(asset_name, target_size)`, l'image redimensionnée (Lanczos) est mise en cache.
- **Détection animations** : un GIF multi-frames est stocké comme un asset animé (frames + délais extraits par PIL). Le format est auto-détecté à l'upload via les magic bytes (PIL).
- **Limite de taille configurable** par asset (défaut : 5 MB de bytes uploadés).
- **Refcount optionnel** : assets dynamiques évincés via `asset.remove` explicite (pas d'éviction automatique au MVP).

### 4.4 DisplayEngine

- Maintient un **état d'affichage par bouton** : `(asset_ref | None, animation_state | None)`.
- `set_image(device_id, button, asset_name)` : si une animation tournait sur ce bouton, elle est arrêtée puis l'image statique est affichée.
- `animate(device_id, button, frames, loop)` : démarre une **tâche asyncio** par bouton animé qui boucle sur les frames avec leurs délais. Si `loop=false`, s'arrête après une passe.
- `stop_animation(device_id, button, mode)` : `mode="freeze"` garde la dernière frame, `mode="clear"` éteint le bouton.
- À la déconnexion d'un device, toutes ses animations sont arrêtées et l'état purgé.

### 4.5 InputDispatcher

- État par bouton : **actif** ou **inactif** (défaut : inactif).
- Reçoit les callbacks HID du `Device` (thread `streamdeck`) et les **bridge thread-safe** vers la boucle asyncio (cf. POC actuel : `run_coroutine_threadsafe`).
- Si bouton actif → publie `button.pressed` / `button.released` sur l'`EventBus`. Si inactif → ignore silencieusement.

### 4.6 EventBus

- Pub/sub interne asynchrone, thread-safe.
- Topics : `button.pressed`, `button.released`, `device.connected`, `device.disconnected`, `error`.
- Consommateurs : `SocketServer` (broadcast vers clients abonnés), extensions.

### 4.7 CommandRegistry

- Mapping `{cmd_name: handler}`.
- Le core enregistre les commandes du protocole standard (`device.*`, `asset.*`, `display.*`, `input.*`, `system.*`).
- Les extensions enregistrent leurs propres namespaces via `CoreAPI.register_command(name, handler)`.
- Conflit : un nom déjà enregistré lève une exception au chargement de l'extension (fail-fast).

### 4.8 SocketServer (transport)

- `asyncio.start_unix_server` sur le chemin configuré (défaut : `~/.config/claude-streamdeck/daemon.sock`), permissions `0o600`.
- **Connexions persistantes** : le serveur garde la connexion ouverte tant que le client ne ferme pas.
- Format : **JSONL** — un objet JSON par ligne (terminée par `\n`).
- Chaque connexion = un objet `Connection` qui :
  - parse les lignes entrantes et dispatche au `CommandRegistry`,
  - garde la liste des subscriptions actives (`input`, plus tard `device`),
  - reçoit les événements pushed par l'`EventBus` et les sérialise sur la connexion.
- Multi-clients en parallèle ; broadcast à tous les abonnés.

### 4.9 CoreAPI (façade pour extensions)

Une extension reçoit un objet `CoreAPI` qui expose :

```python
class CoreAPI:
    devices: DeviceManager           # (lecture seule pour énumération)
    assets: AssetRegistry            # upload/get/remove
    display: DisplayEngine           # set_image, animate, ...
    input: InputDispatcher           # set_active
    events: EventBus                 # subscribe à des topics
    commands: CommandRegistry        # register_command(name, handler)
    config: dict                     # config spécifique à l'extension
```

L'extension implémente :

```python
class Extension:
    def init(self, api: CoreAPI) -> None: ...
    def shutdown(self) -> None: ...
```

## 5. Protocole JSON

### 5.1 Transport

- Socket Unix, JSONL.
- Connexion persistante, bidirectionnelle.
- Encodage UTF-8.
- Taille max d'une ligne : configurable (défaut : 8 MB pour absorber les uploads d'assets).

### 5.2 Enveloppe

**Commandes (client → daemon)** :
```json
{"cmd": "<namespace>.<action>", "request_id": "<opt>", ...params}
```

**Réponses (daemon → client, en réaction à une commande)** :
```json
{"ok": true,  "request_id": "<echo>", "result": {...}}
{"ok": false, "request_id": "<echo>", "error": "<code>", "message": "<human>"}
```

`request_id` est purement applicatif — le daemon le fait suivre s'il est fourni, ne le génère jamais lui-même.

**Événements (daemon → client, push asynchrone)** :
```json
{"event": "<name>", "ts": <epoch_ms>, ...payload}
```

### 5.3 Commandes du core

| Commande | Paramètres | Résultat |
|---|---|---|
| `device.list` | — | `[{id, model, key_count, image_size, has_screen, has_dial}]` |
| `device.capabilities` | `device_id?` | objet capacités d'un device |
| `asset.upload` | `name`, `data` (base64) | `{name, animated: bool, frame_count: int}` |
| `asset.remove` | `name` | `{}` |
| `asset.list` | — | `[{name, animated, size_bytes}]` |
| `display.set` | `device_id?`, `button`, `asset` | `{}` |
| `display.clear` | `device_id?`, `button` | `{}` |
| `display.animate` | `device_id?`, `button`, (`asset` | `frames[]`), `loop?` | `{}` |
| `display.stop_animation` | `device_id?`, `button`, `mode: "freeze"\|"clear"` | `{}` |
| `display.brightness` | `device_id?`, `value: 0..100` | `{}` |
| `input.set_active` | `device_id?`, `button`, `active: bool` | `{}` |
| `input.subscribe` | — | `{}` (active la réception d'events `button.*` sur cette connexion) |
| `input.unsubscribe` | — | `{}` |
| `system.ping` | — | `{pong: true}` |
| `system.version` | — | `{version, extensions: [...]}` |

`device_id` est optionnel : par défaut, premier device connecté. Si plusieurs devices et `device_id` absent, le comportement est documenté comme « premier device » (pas d'erreur).

### 5.4 Événements

| Événement | Payload |
|---|---|
| `button.pressed` | `device_id`, `button` |
| `button.released` | `device_id`, `button` |
| `device.connected` | `device_id`, `model` |
| `device.disconnected` | `device_id` |
| `error` | `code`, `message`, `context?` |

Les events `button.*` sont émis uniquement aux connexions ayant fait `input.subscribe`, et uniquement pour les boutons marqués `active=true`.

### 5.5 Codes d'erreur

| Code | Sens |
|---|---|
| `invalid_json` | ligne reçue non-parseable |
| `unknown_command` | `cmd` non enregistré |
| `invalid_params` | paramètres manquants ou typés incorrectement |
| `asset_not_found` | référencé mais inconnu du registry |
| `asset_too_large` | upload > limite configurée |
| `invalid_asset_data` | base64 invalide ou décodage image impossible |
| `button_out_of_range` | hors `[0, key_count)` |
| `no_device` | aucun device connecté |
| `device_not_found` | `device_id` inconnu |
| `extension_error` | erreur remontée par un handler d'extension |

## 6. Mécanisme d'extension

### 6.1 Configuration

Le daemon lit une config **TOML** (parser `tomllib` de la bibliothèque standard Python 3.11+) qui inclut :
```toml
[daemon]
socket_path = "~/.config/claude-streamdeck/daemon.sock"
assets_dir  = "~/.config/claude-streamdeck/assets"

[[extensions]]
module = "claude_streamdeck.extensions.echo"
config = { log_level = "debug" }

[[extensions]]
module = "my_package.my_extension"
config = { ... }
```

### 6.2 Chargement

Au démarrage :
1. Le core est instancié.
2. Pour chaque entrée `extensions[]`, `importlib.import_module(module)` puis instanciation d'un objet `Extension` exporté par le module.
3. `extension.init(core_api)` est appelé. Une exception est attrapée, loggée, et l'extension est ignorée — le daemon continue.
4. À l'arrêt, `extension.shutdown()` est appelé pour chaque extension chargée.

### 6.3 Interface

Une extension peut :
- Appeler n'importe quelle méthode de `CoreAPI` (display, input, assets, devices).
- S'abonner à des topics de l'`EventBus` (typiquement `button.pressed`).
- Enregistrer ses propres commandes via `core_api.commands.register_command("scene.set", handler)`.

Une extension **ne peut pas** :
- Remplacer une commande du core (registry fail-fast en cas de collision).
- Accéder directement au socket ou aux connexions clients (passe par les events).

### 6.4 Extension de démo : `echo`

Pour valider le mécanisme, le MVP inclut une extension `echo` :
- Marque tous les boutons comme `active=true` au démarrage.
- S'abonne aux events `button.pressed` et logge `button N pressed`.
- Pas de commandes additionnelles enregistrées.

## 7. Arborescence du code

```
plugin/daemon/claude_streamdeck/
├── __main__.py
├── config.py
├── daemon.py
│
├── core/
│   ├── __init__.py
│   ├── core_api.py
│   ├── device_manager.py
│   ├── device.py
│   ├── asset_registry.py
│   ├── display_engine.py
│   ├── input_dispatcher.py
│   ├── command_registry.py
│   └── event_bus.py
│
├── transport/
│   ├── __init__.py
│   ├── socket_server.py
│   └── connection.py
│
├── handlers/
│   ├── __init__.py
│   ├── device_handlers.py
│   ├── asset_handlers.py
│   ├── display_handlers.py
│   ├── input_handlers.py
│   └── system_handlers.py
│
└── extensions/
    ├── __init__.py        # loader (importlib)
    └── echo/
        └── __init__.py
```

```
plugin/tests/
├── test_asset_registry.py
├── test_display_engine.py
├── test_command_registry.py
├── test_event_bus.py
├── test_socket_server.py
├── test_device_mock.py
├── test_protocol.py            # E2E sur socket avec device mocké
└── test_extension_loading.py
```

Le code existant du POC (`actions.py`, `state_machine.py`, `streamdeck_controller.py` actuel) sera **remplacé** par cette architecture. La logique métier Claude Code (machine à états, hooks) sera réintroduite plus tard sous forme d'extension `claude` (hors scope de ce spec).

## 8. Gestion d'erreurs

| Cas | Comportement |
|---|---|
| `asset` inexistant dans `display.set` | `error: "asset_not_found"`, état du bouton inchangé |
| Bouton hors bornes | `error: "button_out_of_range"` |
| JSON invalide sur une ligne | `error: "invalid_json"` envoyé, connexion **non fermée** |
| Commande inconnue | `error: "unknown_command"` |
| Aucun device connecté | Commandes d'affichage : `error: "no_device"` ; daemon continue de tourner et tente reconnexion |
| Device déconnecté pendant exécution | event `device.disconnected`, animations arrêtées, état d'affichage purgé |
| Extension qui crash à l'init | warning loggé, extension ignorée, daemon continue |
| Extension qui crash dans un handler | `error: "extension_error"` au client, daemon continue |
| Asset > limite | `error: "asset_too_large"` |
| Upload base64 invalide | `error: "invalid_asset_data"` |
| Connexion client cassée | nettoyage des subscriptions, animations conservées (pas d'ownership au core) |

Pas de retries automatiques côté daemon — le client redemande s'il en a besoin.

## 9. Tests

| Niveau | Cible | Outils |
|---|---|---|
| Unit | `AssetRegistry` : load, cache, redim, GIF multi-frames, limite de taille | `pytest`, fixtures PIL |
| Unit | `CommandRegistry` : register, dispatch, conflit | `pytest` |
| Unit | `EventBus` : pub/sub, multi-subscriber, thread safety | `pytest`, `pytest-asyncio` |
| Unit | `DisplayEngine` : avec `Device` mocké, animation timing | `pytest-asyncio` |
| Unit | `InputDispatcher` : actif/inactif, bridge thread-safe | `pytest-asyncio` |
| Intégration | `SocketServer` + `CommandRegistry` + handlers : envoyer JSONL, vérifier réponses, vérifier broadcast d'events | `pytest-asyncio` |
| Intégration | Chargement d'une extension fictive : enregistrement de commande, abonnement aux events, dispatch correct | `pytest` |
| E2E (manuel) | Stream Deck XL réel : afficher, animer, presser, recevoir event sur socket | script de smoke test |

Aucun test ne touche le HID réel automatiquement. Le `Device` est remplacé par un mock qui implémente la même interface.

## 10. MVP livrable

Le MVP couvre :

1. Core complet : tous les composants de la section 4.
2. Protocole complet pour le **modèle XL uniquement** (autres modèles : structure prête, fabrique `Device` non implémentée).
3. Extension de démo `echo`.
4. Suite de tests unitaires + intégration (sans HID réel).
5. Smoke test manuel documenté avec un Stream Deck XL.
6. Documentation : ce spec, plus un `README` du daemon listant les commandes JSON exposées.

Ce qui **reste hors scope** et fera l'objet de specs séparés :
- Extension `claude` (machine à états + actions new/resume/stop).
- Extensions `scenes` (claim/release, gestion de scènes).
- Support des modèles MK2, Mini, Plus, Neo, Pedal.
- Persistence des assets et de l'état.
- Authentification ou transport TCP/WebSocket.
