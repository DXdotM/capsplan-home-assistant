<p align="center">
  <img src="custom_components/capsplan/brand/icon@2x.png" width="112" alt="CapsPlan">
</p>

<h1 align="center">CapsPlan für Home Assistant</h1>

<p align="center">
  Deine Medikamente aus <a href="https://apps.apple.com/app/id6779642344"><b>CapsPlan</b></a> in Home Assistant:<br>
  nächste Einnahme, offene Einnahmen, Vorrat, Reichweite und Ausschleich-Dosis – direkt aus deiner eigenen iCloud.
</p>

<p align="center"><a href="README.md">🇬🇧 English</a></p>

---

**CapsPlan** ist eine Medikamenten-Erinnerung für iPhone, iPad und Apple Watch (und Android): Einnahmen mit Erinnerungen, Einnahmeverlauf, Vorrat pro Tablettenstärke, Ein- und Ausschleichpläne, Live-Aktivitäten und Widgets. Seit Version 1.15 kann CapsPlan deine Daten über iCloud zwischen deinen Apple-Geräten synchronisieren. Diese Integration liest genau diese Daten – Home Assistant weiß damit immer, was CapsPlan weiß.

- ✅ **Kostenlos und Open Source** (MIT). Kein Konto bei uns, kein Server von uns, kein Tracking.
- 🔒 **Deine Daten bleiben deine**: Home Assistant liest sie direkt aus *deiner* iCloud. Nichts läuft über Dritte.
- 👀 **Nur lesend**: Die Integration verändert nie etwas an deinen Daten in CapsPlan.

## Was du bekommst

Jedes Medikament wird ein eigenes Gerät in Home Assistant (Entitäts-IDs mit deutscher Sprache):

| Entität | Beispiel | Hinweise |
|---|---|---|
| `sensor.<medikament>_nachste_einnahme` | heute 19:00 | Zeitpunkt; Attribute `dose`, `unit` |
| `sensor.<medikament>_heute_eingenommen` | `1` | Attribute `planned`, `open`, `skipped` und die Liste `doses` von heute |
| `binary_sensor.<medikament>_einnahme_offen` | an | Eine Einnahme ist fällig und weder bestätigt noch übersprungen |
| `sensor.<medikament>_zuletzt_eingenommen` | heute 07:05 | Zeitpunkt der letzten Bestätigung |
| `sensor.<medikament>_aktuelle_dosis` | `8 mg` | Dosis von heute, folgt Ausschleichplänen |
| `sensor.<medikament>_vorrat` | `1200 mg` | Vorrat in der Dosiseinheit; Attribut `tablets_by_strength` |
| `sensor.<medikament>_reichweite` | `29 d` | Wie viele Tage der Vorrat mit den geplanten Einnahmen reicht, Ausschleichen eingerechnet (max. 365) |
| `binary_sensor.<medikament>_vorrat_niedrig` | aus | Deine Vorratswarnung aus CapsPlan |

Dazu ein Gerät **CapsPlan** für alles zusammen:

| Entität | Hinweise |
|---|---|
| `sensor.capsplan_als_nachstes` | **Welche** Einnahmen als Nächstes kommen, z. B. `16:00 · Metformin 500 mg` (alle Medikamente zu dieser Zeit) |
| `sensor.capsplan_offen` | **Welche** Einnahmen offen sind, z. B. `Metformin 08:00, Ramipril 12:00` (`–`, wenn keine) |
| `calendar.capsplan_einnahmen` | Alle geplanten Einnahmen als Kalendertermine: ✓ genommen, ✗ übersprungen, ⏰ offen |
| `sensor.capsplan_nachste_einnahme` | Zeitpunkt der nächsten Einnahme; Attribute `medications` (alle zu dieser Zeit), `medication`, `dose`, `unit` |
| `sensor.capsplan_offene_einnahmen` | Anzahl fälliger, unbestätigter Einnahmen (für Automationen); Attribut `doses` |
| `binary_sensor.capsplan_einnahme_offen` | An, solange irgendeine Einnahme offen ist |
| `sensor.capsplan_einnahmetreue_7_tage` | Anteil der geplanten Einnahmen der letzten 7 Tage, die genommen wurden |
| `sensor.capsplan_letzte_synchronisation` | Diagnose: letzter erfolgreicher Abgleich mit iCloud |

Mit englischer Home-Assistant-Sprache heißen Namen und IDs englisch (z. B. `sensor.metformin_supply`). Bedarfsmedikamente bekommen nur die Entitäten, die für sie sinnvoll sind.

## Voraussetzungen

- **CapsPlan 1.15 oder neuer** auf iPhone oder iPad mit eingeschalteter **iCloud-Synchronisation**: CapsPlan → Einstellungen → Backups → *iCloud-Synchronisation*.
- **Home Assistant 2026.3** oder neuer.
- Eine Apple-ID **ohne erweiterten Datenschutz für iCloud**, siehe [Einschränkungen](#einschränkungen).

> Die iCloud-Synchronisation von CapsPlan gibt es derzeit auf iPhone und iPad. Für Android ist ein Gegenstück in Arbeit.

## Installation

### Mit HACS (empfohlen)

1. HACS öffnen → ⋮ (oben rechts) → **Benutzerdefinierte Repositories**.
2. Repository: `https://github.com/DXdotM/capsplan-home-assistant`, Typ **Integration** → **Hinzufügen**.
3. In HACS nach **CapsPlan** suchen, öffnen und **Herunterladen**.
4. Home Assistant neu starten.

[![Repository in HACS öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=DXdotM&repository=capsplan-home-assistant&category=integration)

### Von Hand

Den Ordner `custom_components/capsplan` aus dem [neuesten Release](https://github.com/DXdotM/capsplan-home-assistant/releases) in den Ordner `custom_components` deiner Home-Assistant-Konfiguration kopieren und Home Assistant neu starten.

## Einrichtung

[![Integration in Home Assistant einrichten](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=capsplan)

1. Einstellungen → Geräte & Dienste → **Integration hinzufügen** → **CapsPlan**.
2. Die **[CapsPlan-Anmeldeseite](https://dxdotm.github.io/capsplan-home-assistant/)** öffnen und auf *Mit Apple-ID anmelden* klicken.
3. Mit der Apple-ID anmelden, mit der CapsPlan synchronisiert. (Bietet Apple *Angemeldet bleiben* an, den Haken setzen.)
4. Apple leitet zurück auf die Seite, die jetzt dein **Anmelde-Token** zeigt. Kopieren.
5. Gleich danach in den Einrichtungsdialog in Home Assistant einfügen und absenden.

Fertig – deine Medikamente erscheinen nach wenigen Sekunden als Geräte.

**Warum ein Token?** Apple lässt Apps nur dann an deine iCloud-Daten, wenn du dich auf Apples eigener Seite angemeldet hast. Die Anmeldeseite ist eine kleine statische Seite in diesem Repository (siehe [`docs/index.html`](docs/index.html)): Sie spricht nur mit Apple und zeigt das Token in deinem Browser an; es wird nirgendwohin sonst geschickt. Das Token gibt Zugriff auf die Daten von CapsPlan in deiner iCloud – nicht auf Fotos, Mails oder irgendetwas anderes.

## Beispiele

### Licht zeigt eine offene Einnahme

```yaml
automation:
  - alias: "Medikamente: Licht zeigt offene Einnahme"
    triggers:
      - trigger: state
        entity_id: binary_sensor.capsplan_einnahme_offen
    actions:
      - choose:
          - conditions: "{{ trigger.to_state.state == 'on' }}"
            sequence:
              - action: light.turn_on
                target: { entity_id: light.kueche }
                data: { color_name: red, brightness_pct: 60 }
        default:
          - action: light.turn_off
            target: { entity_id: light.kueche }
```

### Familie erinnern, wenn eine Einnahme 30 Minuten überfällig ist

```yaml
automation:
  - alias: "Medikamente: überfällig"
    triggers:
      - trigger: state
        entity_id: binary_sensor.capsplan_einnahme_offen
        to: "on"
        for: "00:30:00"
    actions:
      - action: notify.familie
        data:
          title: "Medikamente"
          message: >
            Noch offen:
            {% for d in state_attr('sensor.capsplan_offene_einnahmen', 'doses') %}
            {{ d.medication }} ({{ as_datetime(d.time).strftime('%H:%M') }}){{ ', ' if not loop.last }}
            {% endfor %}
```

### Rechtzeitig nachbestellen: Reichweite unter 10 Tagen

```yaml
automation:
  - alias: "Medikamente: nachbestellen"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.metformin_reichweite
        below: 10
    actions:
      - action: todo.add_item
        target: { entity_id: todo.einkaufsliste }
        data: { item: "Rezept Metformin" }
```

### Dashboard

```yaml
type: entities
title: Medikamente
entities:
  - entity: sensor.capsplan_als_nachstes
  - entity: sensor.capsplan_offen
  - entity: sensor.capsplan_einnahmetreue_7_tage
```

Der Tag auf einen Blick – jede Einnahme mit ✓ / ✗ / ⏰:

```yaml
type: calendar
entities:
  - calendar.capsplan_einnahmen
initial_view: listWeek
```

Weitere Beispiele (Durchsage vor der Einnahme, Vorratswarnung, Ausschleich-Dosis ändert sich): [`examples/automations.yaml`](examples/automations.yaml).

## So funktioniert es

- CapsPlan speichert jedes Medikament, jede Einnahme, Stärke und Ausschleich-Phase als Datensatz in einer privaten iCloud-Zone deiner Apple-ID. Home Assistant holt **alle 5 Minuten** die Änderungen (nur was sich seit dem letzten Mal geändert hat) und hält eine lokale Kopie, damit ein Neustart nicht alles neu lädt.
- Geplante Einnahmen werden **berechnet**, genau wie in der App: Uhrzeiten, Wochentage, Intervalle (alle n Tage), eigene Zeiten pro Wochentag und Ausschleichpläne mit Dosis pro Einnahmezeit. Zustände wie *offen* oder *nächste Einnahme* werden jede Minute aktualisiert.
- Das Token wird mit jeder Anfrage erneuert und in Home Assistant gespeichert. Solange Home Assistant läuft, bleibt die Anmeldung normalerweise gültig. Läuft sie doch ab, zeigt Home Assistant einen **Reparaturhinweis**: einmal auf der Anmeldeseite neu anmelden und das neue Token einfügen.

## Einschränkungen

- **Erweiterter Datenschutz für iCloud**: Apple gibt Accounts mit erweitertem Datenschutz keine Web-Anmeldung für App-Daten in iCloud. Ist er eingeschaltet, schlägt die Anmeldung auf der Anmeldeseite fehl. Die Synchronisation von CapsPlan zwischen deinen Geräten ist davon nicht betroffen.
- **Nur lesend**: Einnahmen aus Home Assistant bestätigen geht (noch) nicht.
- **Verzögerung**: Änderungen erscheinen, sobald CapsPlan sie mit iCloud abgeglichen hat und der nächste Abruf lief – meist innerhalb weniger Minuten.
- **Berechnet, nicht kopiert**: Zeigt die Integration bei einem ungewöhnlichen Einnahmeplan etwas anderes als die App, bitte ein [Issue öffnen](https://github.com/DXdotM/capsplan-home-assistant/issues).

## Datenschutz

- Medikamentendaten sind Gesundheitsdaten. Diese Integration liest sie nur aus deiner iCloud in dein Home Assistant. Es gibt keinen Server dazwischen, keine Analyse, keine Telemetrie.
- Die lokale Kopie liegt in `.storage/capsplan.<eintrag>` deiner Home-Assistant-Konfiguration und wird gelöscht, wenn du die Integration entfernst.
- Diagnose-Downloads enthalten nur Anzahlen und Zustände – keine Medikamentennamen, keine Dosen, kein Token.
- Zugriff jederzeit beenden: die Integration in Home Assistant löschen. Das gespeicherte Token wird dabei mit gelöscht und nie wieder verwendet.

## Fehlerbehebung

| Problem | Lösung |
|---|---|
| Einrichtung meldet *Token nicht gültig* | Tokens gelten nur einmal. Auf der Anmeldeseite neu anmelden und das neue Token sofort einfügen. |
| Anmeldeseite zeigt kein Token | Pop-ups und Cookies für die Seite erlauben oder einen anderen Browser versuchen. Mit erweitertem Datenschutz schlägt die Anmeldung fehl (siehe oben). |
| Keine Medikamente sichtbar | Prüfen, ob in CapsPlan die iCloud-Synchronisation an ist (Einstellungen → Backups) und ob du dich mit derselben Apple-ID angemeldet hast. |
| Einnahme bleibt *offen*, obwohl genommen | CapsPlan einmal öffnen, damit es synchronisiert; den nächsten Abruf abwarten (≤ 5 Minuten). |
| Reparaturhinweis *erneut anmelden* | Die Apple-Anmeldung ist abgelaufen. Dem Hinweis folgen. |

Debug-Protokoll:

```yaml
logger:
  logs:
    custom_components.capsplan: debug
```

## Haftungsausschluss

Diese Integration ist eine Komfortfunktion und **kein Medizinprodukt**. Verlass dich für deine Medikamente immer auf CapsPlan selbst und die Anweisungen deiner Ärztin oder deines Arztes. Automationen können ausfallen (Netzwerk, iCloud, Home Assistant).

## Über CapsPlan

CapsPlan wird von DXdotM Coding entwickelt.

- App Store: <https://apps.apple.com/app/id6779642344>
- Google Play: <https://play.google.com/store/apps/details?id=com.dxdotm_coding.capsplan>
- Website: <https://dxdotm-coding.com/capsplan>
- Support: <https://dxdotm-coding.com/capsplan_support/>

## Lizenz

[MIT](LICENSE) – frei nutzbar, veränderbar und weitergebbar.
