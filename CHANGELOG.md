# Changelog

All notable changes to the Invader Tracker integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.8.1] - 2026-10-26

### Fixed

- **Invaders manquants dans `New & Reactivated` et `Invaders To Flash`** — `news.php` écrit les identifiants tels qu'ils ont été saisis (`PA_08`) alors qu'awazleon les renvoie dépaddés (`PA_8`). Le rapprochement se faisait sur les chaînes brutes : un ajout ou une réactivation annoncé avec un ID paddé ne retrouvait jamais l'invader correspondant et disparaissait silencieusement des deux capteurs, ainsi que de `binary_sensor.has_new`. Les deux côtés passent désormais par `normalize_invader_id()`, comme les compteurs flashés/non flashés depuis la 2.8.0.
- `Invaders To Flash` liste maintenant les IDs dans l'ordre de la ville. Le rapprochement itérait un `set`, donc l'état du capteur pouvait changer d'une mise à jour à l'autre sans qu'aucune donnée n'ait bougé, polluant l'historique.

## [2.8.0] - 2026-10-26

### Fixed

- **Flashed + Unflashed + Gone dépassait le Total** — les identifiants d'awazleon sont normalisés (`PA_01` → `PA_1`), pas ceux de l'API Flash Invader. Un invader flashé renvoyé en `NA_01` ne correspondait donc pas au `NA_1` d'awazleon : il était compté comme flashé **et** comme « Unflashed (Available) » ou « Unflashed (Gone) ». Les deux sources sont maintenant comparées via `normalize_invader_id()` (majuscules + suppression du zero-padding), côté `CityStats`. Relevés avant correctif, au format *total → flashed + available + gone* : Nantes 3 → 2 + 1 + 2, Orléans 12 → 12 + 9 + 0, Versailles 42 → 27 + 6 + 17, Fontainebleau 46 → 8 + 27 + 14, Paris 1598 → 1310 + 99 + 195.
- Le regroupement des invaders flashés par ville est désormais insensible à la casse de l'identifiant renvoyé par l'API.

### Added

- **Attribut `invaders` sur `Unflashed (Available)` et `Unflashed (Gone)`** (devices ville) — la liste triée des IDs restant à flasher / définitivement perdus, pour les afficher dans une carte ou une automatisation. La liste est plafonnée à 500 IDs (`invaders_truncated: true` au-delà) : le recorder de Home Assistant jette l'intégralité des attributs d'une entité dès qu'ils dépassent 16 Kio, ce qu'une grosse ville atteint sur une installation neuve.

## [2.7.0] - 2026-06-06

### Added

- **UID modifiable depuis le menu Options** de l'intégration, sans avoir à la supprimer puis la recréer.

## [2.6.0] - 2026-05-26

### Added

- **Awazleon API key support** — awazleon.space now requires authentication. A new optional setup step prompts for your API key during initial configuration and in the options flow. The key is sent as the `X-API-Key` header on all requests.
- **Graceful degradation without API key** — leaving the key blank disables the Awazleon data source entirely (no error, no blocked startup). Only your personal Flash Invader data and the invader-spotter.art news feed remain active.

> **Obtaining an API key:** Request it directly at [www.awazleon.space](https://www.awazleon.space/) or via the **Space Invaders Discord server**.

### Removed

- Dead code cleanup: `async_force_refresh_city`, `StateSnapshot.was_previously_destroyed`, `ChangeSet.newly_destroyed` (unused internally, never called externally)

### Fixed

- `Invaders To Flash` text sensors returned the hardcoded string `"Aucun"` when empty — now correctly returns `None` (unavailable state), which is the proper HA convention

## [2.5.3] - 2026-04-16

### Fixed

- **New & Reactivated incomplets** — le parser de `news.php` traitait chaque ligne séparément. Les listes d'ajouts longues s'étendent sur plusieurs lignes (ex: `PA_1562, PA_1563,\nPA_1564, PA_1565,\nPA_1566, PA_1567 et PA_1568`) et seule la première était lue. Les lignes de continuation sont maintenant fusionnées avant parsing.

## [2.5.2] - 2026-04-15

### Fixed

- **"Platform not found" au démarrage** — mauvais chemin d'import pour `SelectSelector` (`homeassistant.components.selector` → `homeassistant.helpers.selector`)

## [2.5.1] - 2026-04-15

### Fixed

- **Total invaders toujours à ~3** — la structure de réponse awazleon était mal lue : les invaders sont sous `data["invaders"]`, pas à la racine
- **Compteurs Flashed / Unflashed / Gone incorrects** — awazleon padde les IDs avec des zéros (`PA_01`) contrairement à Flash Invader (`PA_1`) ; les IDs sont maintenant normalisés pour que le matching inter-sources fonctionne
- **Pas de liste de villes dans le config/options flow** — `/cities/info` imbrique les villes sous `data["cities"]["details"]`, pas `data["cities"]` directement
- **Dropdowns intervalle et options affichant des clés brutes ou des radio buttons** — remplacement de `vol.In` par `SelectSelector` (mode DROPDOWN) pour un rendu correct dans l'UI HA
- **Traductions** — noms de champs mis à jour (`update_interval`, `new_city_days`), ajout de l'étape `custom_interval`, correction des références awazleon.space

## [2.5.0] - 2026-04-15

### Added

- **Device "World"** — device agrégé visible dans HA regroupant toutes les stats sur l'ensemble des villes trackées : Total Invaders, Flashed, Unflashed (Available), Unflashed (Gone), New & Reactivated, Invaders To Flash, Has New Invaders.
- **Capteur "New City Invaded"** (device World) — affiche le nom de la dernière ville nouvellement envahie par Space Invader dans la fenêtre configurable (défaut 7 jours), sinon `None`. Attributs : `detected_at` (datetime de première détection), `also_new` (autres villes détectées en même temps). Persisté dans le StateStore via `city_first_seen`.
- Option **"New city detection window"** dans les réglages de l'intégration (3 jours, 1 semaine, 2 semaines, 1 mois).

### Changed

- **Intervalle de refresh unifié** — `CONF_SCRAPE_INTERVAL` et `CONF_API_INTERVAL` (en heures) sont remplacés par `CONF_UPDATE_INTERVAL` (en minutes) commun à toutes les sources. Les entrées existantes sont migrées automatiquement. Valeurs prédéfinies : 15 min, 30 min, 1h, 2h, 6h, 12h, 1j, 1 semaine, 1 mois — plus option "Custom…" avec saisie libre (min. 15 min).
- Imports locaux (`json`, `re`, `timedelta`) déplacés au niveau module dans tous les fichiers.
- Suppression de `sw_version="1.0"` hardcodé dans les `DeviceInfo`.
- `api/__init__.py` exporte maintenant `AwazleonClient`.
- Nettoyage des fixtures de test obsolètes dans `conftest.py`.

## [2.4.0] - 2026-04-15

### Changed

- **Remplacement du scraping invader-spotter par l'API awazleon.space** — les données invaders (statut, points, date d'installation) sont désormais récupérées via l'API REST de [awazleon.space](https://www.awazleon.space) au lieu de scraper le HTML d'invader-spotter.art. Un appel HTTP par ville, pas de BeautifulSoup, plus fiable.
- **Invader-spotter.art conservé uniquement pour `news.php`** — la détection des nouveaux invaders et réactivations reste assurée par l'API news d'invader-spotter (seule source disponible pour les événements new/reactivated).
- Nouveau client `AwazleonClient` (`api/awazleon.py`) avec mapping des codes d'état : `A` → OK, `DG` → DAMAGED, `D`/`DD` → DESTROYED, `H` → NOT_VISIBLE.
- `InvaderSpotterCoordinator` utilise désormais `AwazleonClient` pour les invaders et `InvaderSpotterScraper` uniquement pour les news.
- **Intervalle de refresh unifié** — `CONF_SCRAPE_INTERVAL` et `CONF_API_INTERVAL` (en heures) sont remplacés par `CONF_UPDATE_INTERVAL` (en minutes) commun à toutes les sources. Les entrées existantes sont migrées automatiquement (min des deux valeurs legacy converti en minutes).
- Choix de l'intervalle avec valeurs prédéfinies (15 min, 30 min, 1h, 2h, 6h, 12h, 1j, 1 semaine, 1 mois) + option "Custom…" avec saisie libre (minimum 15 min).

## [2.3.0] - 2026-04-14

### Added

- **Capteur "Total Invaders Worldwide"** — nombre total d'invaders dans le monde, directement depuis l'API Flash Invader (`total_si_count`). Apparaît sur le device profil.

## [2.2.1] - 2026-04-13

### Added

- **Détection automatique des nouveaux joueurs suivis** — l'intégration se recharge automatiquement quand un nouveau joueur est suivi dans l'app Flash Invader, créant le nouvel appareil et ses entités sans intervention manuelle.

### Fixed

- Corrections CI : mypy (`ConfigFlowResult`, types `CoordinatorEntity`, `_attr_state_class`), ruff (imports inutilisés), listener async via `hass.async_create_task`
- Tests mis à jour pour correspondre aux attributs simplifiés des capteurs

## [2.2.0] - 2026-04-13

### Added

- **Option "Track followed players"** — nouvelle option dans les réglages de l'intégration pour activer ou désactiver le suivi des joueurs suivis. Désactivé = aucun appel API supplémentaire, aucune entité créée. Activé par défaut (comportement inchangé pour les installations existantes).

## [2.1.1] - 2026-04-13

### Added

- **Registration Date** — nouvelle entité sur le profil principal
- **Device par joueur suivi** — chaque joueur suivi a maintenant son propre appareil "Invader Tracker - {NOM}" avec 3 entités : `Score`, `Rank` (attribut `rank_str`), `Invaders Found`

### Fixed

- `New & Reactivated` excluait incorrectement les invaders déjà flashés — utilise désormais `unflashed_new_count` pour être cohérent avec `Invaders To Flash`

### Changed

- Le device profil principal s'appelle désormais **"Invader Tracker - {pseudo}"** (ex: "Invader Tracker - TROPLENT") au lieu de "Invader Tracker - Profil"
- `sensor.score` n'a plus `rank`/`rank_str` en attributs — ces infos sont sur `sensor.rank`
- `sensor.rank` a `rank_str` en attribut (cohérent avec les joueurs suivis)

## [2.1.0] - 2026-04-12

### Added

- **Player Profile device** — nouveau device "Invader Tracker - Profil" créé automatiquement dès qu'un UID est configuré :
  - `sensor.score` — score total (attributs : `rank`, `rank_str`)
  - `sensor.rank` — classement global
  - `sensor.invaders_found` — total d'invaders flashés toutes villes confondues
  - `sensor.cities_found` — nombre de villes distinctes avec au moins un flash
- **Joueurs suivis** — une entité par joueur suivi (valeur = score, attributs = `rank`, `rank_str`, `invaders_count`)
- **Retry sur timeout scraper** — les timeouts sur invader-spotter.art déclenchent jusqu'à 3 tentatives avec backoff exponentiel (2s, 4s), réduisant les mises à jour partielles
- Nouveaux endpoints API : `get_player_profile()` et `get_followed_players()` dans `FlashInvaderAPI`
- Nouveau coordinator : `FlashInvaderProfileCoordinator`
- Nouveaux modèles : `PlayerProfile`, `FollowedPlayer`

### Changed

- Attributs des entités ville simplifiés — suppression des listes verboses, seuls les compteurs essentiels sont conservés :
  - `Total Invaders` : supprimé `invader_ids`, conservé `flashable_count`
  - `Flashed`, `Unflashed (Available)`, `Unflashed (Gone)` : aucun attribut
  - `New & Reactivated` : valeur = total (new + reactivated), attributs = `new_count` + `reactivated_count`
  - `Invaders To Flash` : valeur = liste CSV des IDs, aucun attribut
  - `Has New Invaders` : binaire pur, aucun attribut

## [2.0.0] - 2026-01-27

### Added

- Comprehensive test suite: 101 tests across 7 test files (processor, coordinator, sensor, flash_invader, invader_spotter, models, device_removal)
- CI pipeline via GitHub Actions (ruff lint, mypy type-check, pytest with coverage)
- HACS validation workflow
- Comprehensive documentation suite: CHANGELOG.md, CONTRIBUTING.md, DOCUMENTATION.md, INSTALL.md, QUICK_REFERENCE.md
- Expanded README.md with entity docs, automation examples, troubleshooting
- Brand submission assets (`brands_submission/`)
- `pyproject.toml` now tracked in git (test/lint/type-check config)

### Fixed

- Critical bug: `flash_date.isoformat()` crash when `flash_date` is `None` in flashed sensor attributes
- Type annotation: `_extract_date` return type corrected from `datetime | None` to `date | None`

### Changed

- Replaced empty `pass` in `TYPE_CHECKING` blocks with actual type imports
- Removed redundant `TYPE_CHECKING` imports in `__init__.py`, `flash_invader.py`, `invader_spotter.py`
- Fixed `TimeoutError` to `asyncio.TimeoutError` in both API clients
- Removed unused loop variable in coordinator
- Renamed `old_status` to `previous_inv_status` to avoid variable shadowing
- Made `install_date` and `flash_date` optional in `FlashedInvader` model (prevents crashes on malformed data)
- Improved date parsing: returns `None` instead of silently falling back to `datetime.now()`
- Fixed test mock paths to patch correct import locations
- Added `config_entry` fixture in conftest.py
- Trailing whitespace cleanup across all files
- Updated architecture document to v2.0.0 (aligned with actual codebase)

### Removed

- Deleted BUGFIX_CITY_REMOVAL.md (fix already shipped in v1.3.2)
- Removed `pyproject.toml` from `.gitignore`

## [1.3.2] - 2026-01-25

### Fixed

- Suppress city devices on removal from config (device registry cleanup)

### Changed

- Bumped version to 1.3.2

## [1.3.0] - 2026-01-25

### Added

- Text sensor `to_flash` showing invader IDs to flash as a comma-separated list
- Fixed binary sensor display for `has_new`

## [1.2.0] - 2026-01-24

### Added

- News scraper (`news.php`) for detecting new and reactivated invaders
- Smart caching with per-city cache and 6-hour news TTL
- Fallback to expired cache during API failures
- New/reactivated invader detection via news events + state snapshot comparison
- Icon added to repo root for HACS display

### Fixed

- Options flow: read current values from options first, then data
- Entity creation: read cities from options first
- City parsing: use `javascript:envoi` pattern for city discovery
- Invader-spotter scraping: POST method, pagination support, status mapping
- Flash Invader API: use `api.space-invaders.com` with UID as query parameter

## [1.0.0] - 2026-01-23

### Added

- Initial release
- Integration with invader-spotter.art (HTML scraping for city invaders)
- Flash Invader API support via personal UID
- Config flow with UID validation and city selection
- Options flow for reconfiguring cities and intervals
- Reauth flow on credential failure
- 5 sensor entities per city: total, flashed, unflashed, unflashed_gone, new
- 1 binary sensor per city: has_new
- Device per tracked city in HA device registry
- State persistence via `StateStore` for change detection
- Custom exception hierarchy
- English and French translations
- Rate limiting (2s between city scrapes)

## [0.1.1] - 2026-01-22

### Added

- Release workflow (GitHub Actions)

## [0.1.0] - 2026-01-22

### Added

- Initial commit with basic integration scaffold

---

## Version Policy

- **MAJOR** version for incompatible changes (config format, entity structure)
- **MINOR** version for new features (new sensors, API support)
- **PATCH** version for bug fixes and improvements
