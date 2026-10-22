<p align="center">
  <img src="custom_components/capsplan/brand/icon@2x.png" width="112" alt="CapsPlan">
</p>

<h1 align="center">CapsPlan for Home Assistant</h1>

<p align="center">
  Your medications from <a href="https://apps.apple.com/app/id6779642344"><b>CapsPlan</b></a> in Home Assistant:<br>
  next dose, open doses, stock, supply and tapering dose — read from your own iCloud.
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Custom"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/price-free-brightgreen.svg" alt="Free">
</p>

<p align="center"><a href="README.de.md">🇩🇪 Deutsche Anleitung</a></p>

---

**CapsPlan** is a medication reminder for iPhone, iPad and Apple Watch (and Android): doses with reminders, intake history, stock per tablet strength, tapering plans, Live Activities and widgets. Since version 1.15 it can sync your data between your Apple devices through iCloud. This integration reads that synced data, so Home Assistant always knows what CapsPlan knows.

- ✅ **Free and open source** (MIT). No account with us, no server of ours, no tracking.
- 🔒 **Your data stays yours**: Home Assistant reads it directly from *your* iCloud. Nothing passes through any third party.
- 👀 **Read-only**: the integration never changes your data in CapsPlan.

## What you get

Every medication becomes its own device in Home Assistant:

| Entity | Example | Notes |
|---|---|---|
| `sensor.<medication>_next_dose` | today 19:00 | Timestamp; attributes `dose`, `unit` |
| `sensor.<medication>_taken_today` | `1` | Attributes `planned`, `open`, `skipped` and the full list `doses` of today |
| `binary_sensor.<medication>_dose_open` | on | A dose is due and neither confirmed nor skipped |
| `sensor.<medication>_last_taken` | today 07:05 | When the last dose was confirmed |
| `sensor.<medication>_current_dose` | `8 mg` | Today's dose, follows tapering plans |
| `sensor.<medication>_stock` | `94 × 75 mg, ½ × 50 mg` | Tablets per strength; attributes `tablets_by_strength`, `total` (in the dose unit) |
| `sensor.<medication>_supply` | `29 d` | Days the stock lasts with the planned doses, tapering included (max. 365) |
| `binary_sensor.<medication>_stock_low` | off | Your low-stock warning from CapsPlan |

Plus a **CapsPlan** device for everything together:

| Entity | Notes |
|---|---|
| `sensor.capsplan_up_next` | **Which** doses come next, e.g. `16:00 · Metformin 500 mg` (all medications due at that time) |
| `sensor.capsplan_open` | **Which** doses are open, e.g. `Metformin 08:00, Ramipril 12:00` (`–` when none) |
| `calendar.capsplan_doses` | Every planned dose as a calendar event: ✓ taken, ✗ skipped, ⏰ open |
| `sensor.capsplan_next_dose` | Time of the next dose; attributes `medications` (all at that time), `medication`, `dose`, `unit` |
| `sensor.capsplan_open_doses` | Number of due, unconfirmed doses (for automations); attribute `doses` |
| `binary_sensor.capsplan_dose_open` | On while any dose is open |
| `sensor.capsplan_adherence_7_days` | Share of planned doses of the last 7 days that were taken |
| `sensor.capsplan_last_sync` | Diagnostic: last successful sync with iCloud |

Entity names follow your Home Assistant language (English and German included), and so do the entity ids: with German, `sensor.metformin_supply` is `sensor.metformin_reichweite`. Medications for use as needed only get the entities that make sense for them.

## Requirements

- **CapsPlan 1.15 or newer** on iPhone or iPad with **iCloud sync** switched on: CapsPlan → Settings → Backups → *iCloud sync*.
- **Home Assistant 2026.3** or newer.
- An Apple ID **without Advanced Data Protection**, see [Limitations](#limitations).

> CapsPlan's iCloud sync is currently available on iPhone and iPad. For Android an equivalent is in the works.

## Installation

### With HACS (recommended)

1. Open HACS → ⋮ (top right) → **Custom repositories**.
2. Repository: `https://github.com/DXdotM/capsplan-home-assistant`, type **Integration** → **Add**.
3. Search for **CapsPlan** in HACS, open it and click **Download**.
4. Restart Home Assistant.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=DXdotM&repository=capsplan-home-assistant&category=integration)

### Manually

Copy the folder `custom_components/capsplan` from the [latest release](https://github.com/DXdotM/capsplan-home-assistant/releases) into the `custom_components` folder of your Home Assistant configuration and restart Home Assistant.

## Setup

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=capsplan)

1. Settings → Devices & services → **Add integration** → **CapsPlan**.
2. Open the **[CapsPlan sign-in page](https://dxdotm.github.io/capsplan-home-assistant/)** and click *Sign in with Apple ID*.
3. Sign in with the Apple ID that CapsPlan syncs with. (If Apple offers *Keep me signed in*, tick it.)
4. Apple sends you back to the page, which now shows your **sign-in token**. Copy it.
5. Paste it into the setup dialog in Home Assistant right away and submit.

That's it — your medications appear as devices within a few seconds.

**Why a token?** Apple only lets apps read your iCloud data after you signed in on Apple's own page. The sign-in page is a small static page in this repository (see [`docs/index.html`](docs/index.html)): it talks to Apple only and shows the token in your browser; nothing is sent anywhere else. The token grants access to CapsPlan's data in your iCloud, not to your photos, mail or anything else.

## Examples

### Turn a light red while a dose is open

```yaml
automation:
  - alias: "Medication: light shows open dose"
    triggers:
      - trigger: state
        entity_id: binary_sensor.capsplan_dose_open
    actions:
      - choose:
          - conditions: "{{ trigger.to_state.state == 'on' }}"
            sequence:
              - action: light.turn_on
                target: { entity_id: light.kitchen }
                data: { color_name: red, brightness_pct: 60 }
        default:
          - action: light.turn_off
            target: { entity_id: light.kitchen }
```

### Remind the family when a dose is 30 minutes overdue

```yaml
automation:
  - alias: "Medication: overdue reminder"
    triggers:
      - trigger: state
        entity_id: binary_sensor.capsplan_dose_open
        to: "on"
        for: "00:30:00"
    actions:
      - action: notify.family
        data:
          title: "Medication"
          message: >
            Still open:
            {% for d in state_attr('sensor.capsplan_open_doses', 'doses') %}
            {{ d.medication }} ({{ as_datetime(d.time).strftime('%H:%M') }}){{ ', ' if not loop.last }}
            {% endfor %}
```

### Order in time: supply below 10 days

```yaml
automation:
  - alias: "Medication: reorder"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.metformin_supply
        below: 10
    actions:
      - action: todo.add_item
        target: { entity_id: todo.shopping_list }
        data: { item: "Prescription Metformin" }
```

More examples: [`examples/`](examples/).

### Dashboard cards

```yaml
type: entities
title: Medications
entities:
  - entity: sensor.capsplan_up_next
  - entity: sensor.capsplan_open
  - entity: sensor.prednisolon_current_dose
  - entity: sensor.metformin_supply
  - entity: sensor.capsplan_adherence_7_days
```

The day at a glance — every dose with ✓ / ✗ / ⏰:

```yaml
type: calendar
entities:
  - calendar.capsplan_doses
initial_view: listWeek
```

## How it works

- CapsPlan stores each medication, intake, strength and tapering phase as a record in a private iCloud zone of your Apple ID. Home Assistant fetches the changes every **5 minutes** (only what changed since the last time) and keeps a local copy, so a restart doesn't download everything again.
- Planned doses are **calculated**, exactly like the app does it: times per day, weekdays, every-n-days intervals, individual times per weekday and tapering plans with doses per time of day. States like *open* or *next dose* are refreshed every minute.
- The token is renewed with every request and stored in Home Assistant. As long as Home Assistant runs, the sign-in normally stays valid. If it expires, Home Assistant shows a **repair notice**: sign in once more on the sign-in page and paste the new token.

## Limitations

- **Advanced Data Protection**: Apple does not hand out web sign-ins for apps' iCloud data to accounts with Advanced Data Protection turned on. With it on, the sign-in on the sign-in page fails. CapsPlan's own sync between your devices is not affected.
- **Read-only**: confirming a dose from Home Assistant is not possible (yet).
- **Delay**: changes show up in Home Assistant after CapsPlan synced them to iCloud and the next poll ran — usually within a few minutes.
- **Doses are calculated, not copied**: if a medication's schedule is unusual and the integration shows something different from the app, please [open an issue](https://github.com/DXdotM/capsplan-home-assistant/issues).

## Privacy

- Medication data is health data. This integration reads it only from your iCloud into your Home Assistant. There is no server in between, no analytics, no telemetry.
- The local copy lives in `.storage/capsplan.<entry>` in your Home Assistant configuration and is deleted when you remove the integration.
- Diagnostics downloads contain counts and statuses only — no medication names, no doses, no token.
- Remove the access at any time: delete the integration in Home Assistant. The stored token is deleted with it and is never used again.

## Troubleshooting

| Problem | Solution |
|---|---|
| Setup says *token not valid* | Tokens are single-use and short-lived until first used. Sign in again on the sign-in page and paste the new token immediately. |
| Sign-in page shows no token | Allow pop-ups and cookies for the page, or try another browser. With Advanced Data Protection the sign-in fails (see above). |
| No medications appear | Check that iCloud sync is on in CapsPlan (Settings → Backups) and that you signed in with the same Apple ID. |
| A dose stays *open* although I took it | Open CapsPlan once so it syncs, wait for the next poll (≤ 5 minutes). |
| Repair notice *sign in again* | The Apple sign-in expired. Follow the notice. |

Debug logging:

```yaml
logger:
  logs:
    custom_components.capsplan: debug
```

## Disclaimer

This integration is a convenience feature, **not a medical device**. Always rely on CapsPlan itself and on your doctor's instructions for your medication. Automations can fail (network, iCloud, Home Assistant).

## About CapsPlan

CapsPlan is made by DXdotM Coding.

- App Store: <https://apps.apple.com/app/id6779642344>
- Google Play: <https://play.google.com/store/apps/details?id=com.dxdotm_coding.capsplan>
- Website: <https://dxdotm-coding.com/capsplan>
- Support: <https://dxdotm-coding.com/capsplan_support/>

## License

[MIT](LICENSE) — free to use, modify and share.
