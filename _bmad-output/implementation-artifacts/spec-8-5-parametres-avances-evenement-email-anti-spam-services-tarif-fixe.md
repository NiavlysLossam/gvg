---
title: 'Story 8.5 - Paramètres Avancés Événement : E-mail Anti-Spam, Services sur Place & Recalcul Tarif au Mètre'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_commit: 3f9a3c556065c8fa548d2df094e87be71984ce27
route: 'dispatch'
review_loop_iteration: 1
context:
  - _bmad-output/implementation-artifacts/epic-8-context.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:**
1. L'adresse e-mail de contact de l'événement (`organizer_email`) était affichée en clair dans le code HTML de la vitrine publique (`EventShowcasePage.tsx`), l'exposant aux robots aspirateurs de spam, et les e-mails envoyés par la plateforme aux exposants ne définissaient pas d'en-tête `Reply-To` vers l'adresse dédiée de l'événement.
2. Les 5 services et commodités affichés sur la page vitrine publique (`buvette`, `restauration`, `sanitaires`, `parking`, `pmr`) étaient codés en dur pour tous les événements, sans possibilité pour l'organisateur de cocher ceux réellement présents sur place.
3. Lorsqu'un organisateur modifiait le tarif au mètre linéaire (`price_per_meter`) dans les paramètres de l'événement, ce nouveau tarif n'était pas automatiquement répercuté sur les stands existants non réservés.

**Approach:**
1. **E-mail de contact & Anti-Spam** : Clarifier dans `EventForm.tsx` et `EventSettingsPage.tsx` que `organizer_email` est une adresse publique dédiée à l'événement (distincte du compte admin). Masquer par défaut l'adresse sur `EventShowcasePage.tsx` derrière un bouton « Afficher l'e-mail » avant de révéler l'adresse complète et le lien `mailto:`. Ajouter l'en-tête `Reply-To: <event.organizer_email>` sur tous les e-mails transactionnels, rappels J-7/J-2 et diffusions groupées.
2. **Services configurables (liste fermée de 5 services)** : Ajouter une colonne JSON `services` sur le modèle `Event` (migration Alembic `011_add_services_to_events.py`), exposée dans les schémas `EventBase`, `EventUpdate`, `EventResponse`, `PublicEventResponse` et `PublicEventListItem`, ainsi que lors de la duplication d'événement. Ajouter 5 cases à cocher (`buvette`, `restauration`, `sanitaires`, `parking`, `pmr`) dans `EventForm.tsx` et `EventSettingsPage.tsx`, et filtrer l'affichage sur `EventShowcasePage.tsx` (masquer la section si aucun service n'est coché).
3. **Recalcul automatique du prix des stands lors de la modification du tarif au mètre (`price_per_meter`)** : Lors de l'appel à `PATCH /api/v1/events/{id_or_slug}` modifiant `price_per_meter`, recalculer automatiquement `spot.price_cents = int(round(spot.linear_meters * new_price_per_meter_cents))` sur chaque stand de l'événement qui n'est **ni** en statut `reserved`, **ni** en cours de réservation dans un panier actif (`spot.status == "locked"` avec `locked_until > now`), **ni** lié à une commande active (`confirmed`, `pending`, `pending_approval`, `cancellation_requested`). Afficher un message d'alerte et une demande de confirmation dans `EventSettingsPage.tsx` lorsque `pricePerMeter` est modifié.

## Boundaries & Constraints

**Always:**
- Limiter strictement les services aux 5 clés autorisées : `buvette`, `restauration`, `sanitaires`, `parking`, `pmr` (aucun champ texte libre).
- Protéger strictement les stands réservés (`spot.status == "reserved"`), en cours de réservation (`spot.status == "locked"` actif) ou liés à une commande active (`Order.status in ["confirmed", "pending", "pending_approval", "cancellation_requested"]`) lors de la modification de `price_per_meter`.
- Obfusquer `organizer_email` dans le rendu initial de `EventShowcasePage.tsx` (aucune adresse en clair ni lien `mailto:` dans le DOM tant que l'utilisateur n'a pas cliqué sur « Afficher l'e-mail »).
- Renseigner l'en-tête `Reply-To` dans `send_raw_email` lorsque `event.organizer_email` est défini et valide (contient `@`).
- Conserver `services` lors de la duplication d'un événement (`POST /api/v1/events/{id_or_slug}/duplicate`).

**Never:**
- Ne jamais modifier le prix d'un stand déjà réservé, en cours de réservation ou rattaché à une commande active lors d'un changement de `price_per_meter`.
- Ne jamais afficher la section « Services & commodités sur place » sur `EventShowcasePage.tsx` si la liste `event.services` est vide ou nulle.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Affichage initial de l'e-mail public | Visiteur charge `EventShowcasePage` avec `organizer_email="contact@asso.fr"` | L'e-mail est masqué (`co***@as***.fr`) avec un bouton « Afficher l'e-mail » ; aucun `mailto:` dans le DOM | Si `organizer_email` est null/vide, le bloc contact n'est pas affiché |
| Révélation de l'e-mail public | Visiteur clique sur « Afficher l'e-mail » | L'adresse complète `contact@asso.fr` et le bouton `mailto:` « Écrire » s'affichent | Réinitialisé à masqué si changement de `slug` |
| Envoi d'e-mail aux exposants | `organizer_email` configuré sur l'événement | Le message MIME contient l'en-tête `Reply-To: <organizer_email>` | Ignoré proprement si `organizer_email` est null ou invalide |
| Sélection des services | Admin coche `buvette` et `parking` et enregistre | `event.services = ["buvette", "parking"]` persisté en base et retourné par l'API publique ; seules ces 2 cartes s'affichent sur la vitrine | Si aucun service coché (`[]`), la section est masquée sur la vitrine |
| Modification du tarif au mètre (`price_per_meter`) | Admin modifie `price_per_meter` (ex: `7.50` € / m) et confirme l'alerte à l'enregistrement | Tous les stands disponibles voient leur `price_cents` recalculé selon leur `linear_meters` ; les stands réservés, verrouillés en panier actif ou en commande active restent intacts | HTTP 422 si `price_per_meter < 0.01`, HTTP 403 si non propriétaire |

</frozen-after-approval>

## Code Map

- `backend/alembic/versions/011_add_services_to_events.py` -- Migration Alembic ajoutant la colonne `services` (JSON) à `events` et initialisant les événements existants avec les 5 services.
- `backend/app/models/event.py` -- Ajout de `services = Column(JSON, nullable=True, default=list)`.
- `backend/app/schemas/event.py` -- Ajout de `ServiceType = Literal["buvette", "restauration", "sanitaires", "parking", "pmr"]` et déduplication/validation de `services` dans `EventBase` et `EventUpdate`.
- `backend/app/schemas/public.py` -- Ajout de `services` dans `PublicEventResponse` et `PublicEventListItem`.
- `backend/app/api/v1/endpoints/events.py` -- Recalcul automatique du prix des stands non réservés/non verrouillés lorsque `price_per_meter` change dans `update_event`, et copie de `services` dans `duplicate_event`.
- `backend/app/api/v1/endpoints/public.py` -- Exposition de `services` dans `list_public_events` et `get_public_event`.
- `backend/app/services/email_service.py`, `reminder_service.py`, `broadcast_service.py` -- Support et nettoyage anti-CRLF de `reply_to=event.organizer_email`.
- `frontend/src/types/event.ts` & `frontend/src/types/public.ts` -- Types `services`, `EventServiceKey`, `EVENT_SERVICES_OPTIONS`.
- `frontend/src/components/EventForm.tsx` -- Aide anti-spam et cases à cocher des 5 services.
- `frontend/src/pages/EventSettingsPage.tsx` -- Aide anti-spam, cases à cocher des 5 services, bandeau d'alerte et confirmation lors de la modification de `pricePerMeter`.
- `frontend/src/pages/EventShowcasePage.tsx` -- Filtrage et affichage conditionnel des 5 services et obfuscation anti-spam de `organizer_email`.

## Tasks & Acceptance

**Execution:**
- [x] `backend/alembic/versions/011_add_services_to_events.py` & `backend/app/models/event.py` -- Ajouter la colonne JSON `services` avec backfill des événements existants.
- [x] `backend/app/schemas/event.py`, `backend/app/schemas/public.py`, `backend/app/api/v1/endpoints/events.py`, `backend/app/api/v1/endpoints/public.py` -- Exposer, valider (`ServiceType`) et dupliquer `services`, et recalculer les prix des stands disponibles lors d'un changement de `price_per_meter`.
- [x] `backend/app/services/email_service.py`, `reminder_service.py`, `broadcast_service.py` -- Ajouter l'en-tête `Reply-To`.
- [x] `frontend/src/components/EventForm.tsx`, `frontend/src/pages/EventSettingsPage.tsx`, `frontend/src/pages/EventShowcasePage.tsx` -- Implémenter l'UI admin et publique pour les 3 fonctionnalités.
- [x] `backend/tests/test_migrations.py`, `backend/tests/test_events_api.py`, `backend/tests/test_spots_api.py`, `backend/tests/test_email_service.py` -- Ajouter les tests unitaires et d'intégration complets.

**Acceptance Criteria:**
- Given un événement avec `organizer_email`, when un visiteur consulte `EventShowcasePage`, then l'adresse e-mail est masquée par défaut et ne révèle l'adresse complète et le lien `mailto:` qu'après clic sur « Afficher l'e-mail ».
- Given un événement avec `organizer_email`, when un e-mail est envoyé à un exposant, then l'en-tête `Reply-To` vaut `event.organizer_email`.
- Given les 5 services prédéfinis, when l'organisateur coche un sous-ensemble dans `EventSettingsPage` ou `EventForm`, then seuls les services cochés apparaissent sur `EventShowcasePage` (et la section disparaît si aucun n'est coché).
- Given un événement contenant des stands disponibles et des stands réservés/en commande active/verrouillés, when l'organisateur modifie `price_per_meter` dans `EventSettingsPage`, then un message d'alerte s'affiche et seuls les stands disponibles voient leur prix recalculé (`linear_meters * nouveau tarif`).

## Verification

**Commands:**
- `/home/sylvain/projets/gvg/gvg/.venv/bin/pytest` -- expected: 100% pass.
- `PATH="/home/sylvain/projets/gvg/gvg/.tools/node/bin:$PATH" npm run build --prefix frontend` -- expected: 0 erreur TypeScript ou Vite.

### Review Findings

- [x] **F1 (Acceptance Auditor / Blind Hunter / Edge Case Hunter)** : `EventBase.services` et `EventUpdate.services` acceptaient `list[str]` au lieu de restreindre strictement aux 5 clés autorisées (`Literal["buvette", "restauration", "sanitaires", "parking", "pmr"]`) et de dédupliquer les entrées.
- [x] **F2 (Acceptance Auditor / Edge Case Hunter)** : Lors de la mise à jour du tarif de l'événement, rejeter tout montant `< 0.01` € (422) et protéger les stands activement verrouillés dans un panier (`spot.status == "locked"` avec `locked_until > now`) en plus des stands réservés et des commandes actives.
- [x] **F3 (Blind Hunter / Edge Case Hunter)** : La migration `011_add_services_to_events.py` laissait `services = NULL` sur les événements déjà existants en base de données, ce qui aurait masqué les 5 services sur leurs pages vitrines après déploiement.
- [x] **F4 (Blind Hunter / Edge Case Hunter)** : `send_raw_email` dans `email_service.py` n'épurait pas les caractères CR/LF (`\r`, `\n`) de `reply_to` avant de construire l'en-tête MIME `Reply-To`.
- [x] **F5 (Acceptance Auditor / Edge Case Hunter)** : Dans `EventShowcasePage.tsx`, `event.services` n'était pas filtré contre les 5 clés connues avant de décider d'afficher la section, la carte `pmr` conservait une classe `col-span-2 sm:col-span-1` orpheline lorsque moins de 5 cartes étaient affichées, et `maskEmail` gérait mal les sous-domaines multiples (`co***@mail.asso.fr`).
- [x] **F6 (Verification Gap)** : `test_migrations.py` ne vérifiait pas la présence de la colonne `services` (ni `wms_url`/`wms_layer`), et il manquait des tests pour `ServiceType` invalide (422), stand verrouillé (`locked`), montant `< 0.01` € (422), et `Reply-To` sur e-mail avec pièces jointes (`multipart/mixed`).

## Spec Change Log

- **Iteration 1** : Application des correctifs issus des 4 sous-agents de revue BMAD (`Acceptance Auditor`, `Blind Hunter`, `Edge Case Hunter`, `Verification Gap`) et enrichissement de la suite de tests.
- **Renégociation utilisateur (Point 3)** : Remplacement de la modification de tarif par montant fixe par le recalcul automatique du prix des stands non réservés / non en cours de réservation lors de la modification du tarif au mètre (`price_per_meter`) dans les paramètres de l'événement, avec conservation du message d'alerte.

## Review Triage Log

### Iteration 1
| Finding | Decision | Rationale |
|---------|----------|-----------|
| F1: Restriction `ServiceType` Literal & déduplication | **Fix** | Garantit au niveau API la contrainte stricte des 5 services sans texte libre ni doublons. |
| F2: `fixed_price` `ge=0.01, le=100000.0` + protection stands `locked` + rollback | **Fix** | Empêche un tarif à 0 centime ou un dépassement d'entier SQL et protège les paniers exposants en cours de paiement. |
| F3: Backfill `services` dans la migration `011` | **Fix** | Préserve le comportement des événements existants lors de la mise à jour en production. |
| F4: Sanitization CR/LF sur `reply_to` | **Fix** | Défense en profondeur contre l'injection d'en-têtes SMTP. |
| F5: Filtrage `activeServices`, grille CSS `pmr` et `maskEmail` multi-points | **Fix** | Évite une section vide sur clés inconnues, améliore l'alignement responsive et renforce le masquage d'e-mail. |
| F6: Couverture de tests additionnelle (`test_migrations`, `test_events_api`, `test_spots_api`, `test_email_service`) | **Fix** | Couvre toutes les branches et cas limites identifiés par `Verification Gap`. |

