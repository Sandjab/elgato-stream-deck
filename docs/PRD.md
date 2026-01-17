# PRD : Claude Code Stream Deck Integration MVP

## Metadata

| Champ | Valeur |
|-------|--------|
| **Titre** | Claude Code Stream Deck Integration |
| **Version** | 1.0 |
| **Date** | 17 janvier 2026 |
| **Auteur** | — |
| **Statut** | Draft |

---

## 1. Résumé exécutif

### 1.1 Vision

Permettre aux utilisateurs de Claude Code CLI de visualiser l'état de leur session en temps réel sur un Stream Deck et d'exécuter des actions courantes d'un simple appui de touche.

### 1.2 Problème

Lorsqu'on utilise Claude Code en CLI, il n'existe aucun moyen visuel externe de connaître l'état de la session (actif, en réflexion, exécution d'outil, inactif). L'utilisateur doit constamment regarder son terminal pour savoir ce que fait Claude.

### 1.3 Solution

Un daemon qui :
- Écoute les événements de Claude Code via le système de hooks natif
- Affiche l'état en temps réel sur un Stream Deck
- Permet de lancer des actions (nouvelle session, reprise, interruption) via les touches

### 1.4 Scope MVP

| In Scope | Out of Scope |
|----------|--------------|
| Affichage de l'état (4 états) | Interface de configuration graphique |
| 4 actions de base | Prompts prédéfinis personnalisables |
| Support Stream Deck 15 touches | Support Stream Deck +, Mini, XL |
| macOS et Linux | Windows |
| Contrôle USB direct | Plugin SDK Elgato |

---

## 2. Objectifs et métriques

### 2.1 Objectifs

| ID | Objectif | Priorité |
|----|----------|----------|
| O1 | L'utilisateur voit l'état de Claude Code sans regarder le terminal | P0 |
| O2 | L'utilisateur peut démarrer/reprendre une session d'un appui | P0 |
| O3 | L'utilisateur peut interrompre Claude d'un appui | P1 |
| O4 | Le système fonctionne de manière fiable sans intervention | P0 |

### 2.2 Métriques de succès

| Métrique | Cible |
|----------|-------|
| Latence affichage état | < 500ms |
| Disponibilité daemon | > 99% (pas de crash) |
| Temps d'installation | < 5 minutes |

---

## 3. User Stories

### 3.1 Persona

**Alex**, développeur, utilise Claude Code quotidiennement pour coder. Il a un Stream Deck sur son bureau qu'il utilise pour d'autres raccourcis. Il veut intégrer Claude Code à son setup.

### 3.2 User Stories MVP

#### US-1 : Voir l'état de Claude Code
**En tant qu'** utilisateur de Claude Code  
**Je veux** voir sur mon Stream Deck si Claude est actif, en réflexion, ou inactif  
**Afin de** savoir quand je peux interagir sans regarder mon terminal  

**Critères d'acceptation :**
- [ ] AC-1.1 : Quand aucune session n'est active, la touche affiche "Offline" avec une icône grise
- [ ] AC-1.2 : Quand une session démarre, la touche passe à "Ready" avec une icône verte
- [ ] AC-1.3 : Quand j'envoie un prompt, la touche passe à "Thinking" avec une icône bleue
- [ ] AC-1.4 : Quand Claude exécute un outil, la touche affiche le nom de l'outil avec une icône orange
- [ ] AC-1.5 : Quand Claude termine sa réponse, la touche revient à "Ready"
- [ ] AC-1.6 : Quand je quitte la session, la touche revient à "Offline"
- [ ] AC-1.7 : La transition d'état se fait en moins de 500ms

#### US-2 : Démarrer une nouvelle session
**En tant qu'** utilisateur  
**Je veux** appuyer sur une touche pour lancer une nouvelle session Claude Code  
**Afin de** démarrer rapidement sans taper de commande  

**Critères d'acceptation :**
- [ ] AC-2.1 : Une touche est dédiée à l'action "Nouvelle session"
- [ ] AC-2.2 : L'appui ouvre un nouveau terminal avec `claude` lancé
- [ ] AC-2.3 : L'état passe à "Ready" quand la session démarre
- [ ] AC-2.4 : Un feedback visuel confirme l'appui (flash de la touche)

#### US-3 : Reprendre la dernière session
**En tant qu'** utilisateur  
**Je veux** appuyer sur une touche pour reprendre ma dernière session  
**Afin de** continuer mon travail rapidement  

**Critères d'acceptation :**
- [ ] AC-3.1 : Une touche est dédiée à l'action "Reprendre"
- [ ] AC-3.2 : L'appui ouvre un terminal avec `claude --resume`
- [ ] AC-3.3 : Si aucune session précédente n'existe, un feedback d'erreur s'affiche
- [ ] AC-3.4 : L'état passe à "Ready" quand la session reprend

#### US-4 : Interrompre Claude
**En tant qu'** utilisateur  
**Je veux** appuyer sur une touche pour interrompre Claude  
**Afin de** stopper une action en cours sans chercher mon terminal  

**Critères d'acceptation :**
- [ ] AC-4.1 : Une touche est dédiée à l'action "Interrompre"
- [ ] AC-4.2 : L'appui envoie l'équivalent de Escape au terminal Claude actif
- [ ] AC-4.3 : L'état passe à "Ready" après l'interruption
- [ ] AC-4.4 : Si aucune session n'est active, l'appui est ignoré (pas d'erreur)

#### US-5 : Installation simple
**En tant qu'** utilisateur  
**Je veux** installer l'intégration avec une seule commande  
**Afin de** ne pas perdre de temps en configuration manuelle  

**Critères d'acceptation :**
- [ ] AC-5.1 : Un script `install.sh` installe toutes les dépendances
- [ ] AC-5.2 : Le script configure automatiquement les hooks Claude Code
- [ ] AC-5.3 : Le script démarre le daemon
- [ ] AC-5.4 : Le script affiche un message de succès avec les instructions d'usage
- [ ] AC-5.5 : L'installation prend moins de 5 minutes

#### US-6 : Démarrage automatique
**En tant qu'** utilisateur  
**Je veux** que le daemon démarre automatiquement au login  
**Afin de** ne pas avoir à le lancer manuellement  

**Critères d'acceptation :**
- [ ] AC-6.1 : Sur macOS, un LaunchAgent est installé
- [ ] AC-6.2 : Sur Linux, un service systemd user est installé
- [ ] AC-6.3 : Le daemon se reconnecte automatiquement si le Stream Deck est débranché/rebranché
- [ ] AC-6.4 : Le daemon redémarre automatiquement en cas de crash

---

## 4. Exigences fonctionnelles

### 4.1 Affichage d'état

| ID | Exigence | User Story |
|----|----------|------------|
| F-1.1 | Le système affiche 4 états distincts : inactive, idle, thinking, tool_running | US-1 |
| F-1.2 | Chaque état a une icône et couleur distinctes | US-1 |
| F-1.3 | L'état "tool_running" affiche le nom de l'outil en titre | US-1 |
| F-1.4 | Les transitions d'état sont instantanées (< 500ms) | US-1 |

### 4.2 Actions

| ID | Exigence | User Story |
|----|----------|------------|
| F-2.1 | Touche "New" : lance `claude` dans un nouveau terminal | US-2 |
| F-2.2 | Touche "Resume" : lance `claude --resume` dans un nouveau terminal | US-3 |
| F-2.3 | Touche "Stop" : envoie Escape au terminal actif | US-4 |
| F-2.4 | Chaque appui produit un feedback visuel | US-2, US-3, US-4 |

### 4.3 Installation

| ID | Exigence | User Story |
|----|----------|------------|
| F-3.1 | Script d'installation one-liner | US-5 |
| F-3.2 | Détection automatique de l'OS | US-5 |
| F-3.3 | Installation des dépendances Python | US-5 |
| F-3.4 | Configuration automatique des hooks Claude Code | US-5 |
| F-3.5 | Création du service de démarrage automatique | US-6 |

---

## 5. Exigences non fonctionnelles

### 5.1 Performance

| ID | Exigence | Cible |
|----|----------|-------|
| NF-1.1 | Latence hook → affichage | < 500ms |
| NF-1.2 | Utilisation CPU daemon idle | < 1% |
| NF-1.3 | Utilisation mémoire daemon | < 50 MB |

### 5.2 Fiabilité

| ID | Exigence |
|----|----------|
| NF-2.1 | Le daemon ne crashe pas si Claude Code n'est pas installé |
| NF-2.2 | Le daemon gère la déconnexion/reconnexion du Stream Deck |
| NF-2.3 | Le daemon gère les messages malformés sans crash |
| NF-2.4 | Les hooks n'impactent pas les performances de Claude Code |

### 5.3 Compatibilité

| ID | Exigence |
|----|----------|
| NF-3.1 | Support macOS 13+ (Ventura et ultérieur) |
| NF-3.2 | Support Linux (Ubuntu 22.04+, Debian 12+) |
| NF-3.3 | Support Stream Deck Original (15 touches) V1 et V2 |
| NF-3.4 | Python 3.10+ |

### 5.4 Sécurité

| ID | Exigence |
|----|----------|
| NF-4.1 | Le socket Unix est accessible uniquement par l'utilisateur (mode 600) |
| NF-4.2 | Aucune donnée sensible n'est loggée |
| NF-4.3 | Les hooks n'exécutent pas de code arbitraire |

---

## 6. Architecture technique

### 6.1 Composants

```
┌─────────────────┐
│   Claude Code   │
│      CLI        │
└────────┬────────┘
         │ hooks
         ▼
┌─────────────────┐
│  Hook Script    │
│  (bash)         │
└────────┬────────┘
         │ socket unix
         ▼
┌─────────────────┐
│     Daemon      │
│    (Python)     │
└────────┬────────┘
         │ USB HID
         ▼
┌─────────────────┐
│  Stream Deck    │
└─────────────────┘
```

### 6.2 Stack technique

| Composant | Technologie |
|-----------|-------------|
| Hook script | Bash |
| Transport | Socket Unix |
| Daemon | Python 3.10+ |
| Lib Stream Deck | python-elgato-streamdeck |
| Images | Pillow |
| Service macOS | launchd (plist) |
| Service Linux | systemd user service |

---

## 7. Layout Stream Deck

```
┌─────────┬─────────┬─────────┬─────────┬─────────┐
│ STATUS  │   NEW   │ RESUME  │  STOP   │  (vide) │
│  [état] │   [+]   │   [▶]   │   [■]   │         │
├─────────┼─────────┼─────────┼─────────┼─────────┤
│ (vide)  │ (vide)  │ (vide)  │ (vide)  │ (vide)  │
│         │         │         │         │         │
├─────────┼─────────┼─────────┼─────────┼─────────┤
│ (vide)  │ (vide)  │ (vide)  │ (vide)  │ (vide)  │
│         │         │         │         │         │
└─────────┴─────────┴─────────┴─────────┴─────────┘
  Key 0     Key 1     Key 2     Key 3     Key 4
```

---

## 8. Hors scope (futures versions)

| Fonctionnalité | Version cible |
|----------------|---------------|
| Prompts prédéfinis personnalisables | v1.1 |
| Support Stream Deck Mini, XL, + | v1.1 |
| Support Windows | v1.2 |
| Interface de configuration | v1.2 |
| Affichage tokens/coût | v1.3 |
| Plugin SDK Elgato (alternative) | v2.0 |
| Multi-session | v2.0 |

---

## 9. Risques

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| API hooks Claude Code change | Moyenne | Élevé | Versioning strict, tests d'intégration |
| Problèmes permissions USB Linux | Moyenne | Moyen | Documentation udev rules, script d'install |
| Stream Deck non détecté | Faible | Élevé | Retry avec backoff, logs clairs |
| Latence excessive | Faible | Moyen | Socket Unix (pas de polling) |

---

## 10. Timeline

| Milestone | Contenu | Durée estimée |
|-----------|---------|---------------|
| M1 | Hook script + daemon minimal (état seulement) | 2h |
| M2 | Actions (new, resume, stop) | 1h |
| M3 | Installation automatisée | 1h |
| M4 | Service démarrage auto + polish | 1h |
| **Total** | **MVP complet** | **5h** |

---

## 11. Critères de validation MVP

Le MVP est considéré comme terminé quand :

- [ ] Le daemon démarre et se connecte au Stream Deck
- [ ] Les 4 états s'affichent correctement lors d'une session Claude Code
- [ ] Les 3 actions fonctionnent (new, resume, stop)
- [ ] Le script d'installation fonctionne sur macOS
- [ ] Le daemon redémarre automatiquement au login
- [ ] La documentation d'installation existe
