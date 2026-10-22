"""Constants for the CapsPlan integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "capsplan"

# CapsPlan's iCloud container and the zone its sync writes to.
CONTAINER: Final = "iCloud.com.dxdotm-coding.capsplan"
ENVIRONMENT: Final = "production"
SYNC_ZONE: Final = "CapsPlanSync"

# Public CloudKit Web Services API token of the container. It identifies the
# container only; every request still needs the user's own sign-in.
API_TOKEN: Final = "4de0d60a392fc8c2393c611db2606dc53af5d51ce008b214434d423127380ffa"

# Page that runs Apple's sign-in and shows the token to paste into the setup.
SIGN_IN_URL: Final = "https://dxdotm.github.io/capsplan-home-assistant/"

CONF_WEB_AUTH_TOKEN: Final = "web_auth_token"
CONF_USER_RECORD: Final = "user_record_name"
# Whose CapsPlan this is ("Anna"); empty for a single person.
CONF_PERSON: Final = "person"
# Show "Medication 1" instead of the real names (shared dashboards).
CONF_HIDE_NAMES: Final = "hide_names"
MEDICATION_WORD: Final = {
    "de": "Medikament",
    "en": "Medication",
    "es": "Medicamento",
    "it": "Farmaco",
    "tr": "İlaç",
}

UPDATE_INTERVAL: Final = timedelta(minutes=5)
RECOMPUTE_INTERVAL: Final = timedelta(minutes=1)

STORAGE_VERSION: Final = 1

APP_STORE_URL: Final = "https://apps.apple.com/app/id6779642344"

# Dosage forms as the app names them (device model).
MEDICATION_TYPES: Final = {
    "de": {
        "tablet": "Tablette",
        "liquid": "Flüssig",
        "drops": "Tropfen",
        "capsule": "Kapsel",
        "injection": "Injektion",
        "patch": "Pflaster",
        "inhaler": "Inhalator",
        "powder": "Pulver",
        "spray": "Spray"
    },
    "en": {
        "tablet": "Tablet",
        "liquid": "Liquid",
        "drops": "Drops",
        "capsule": "Capsule",
        "injection": "Injection",
        "patch": "Patch",
        "inhaler": "Inhaler",
        "powder": "Powder",
        "spray": "Spray"
    },
    "es": {
        "tablet": "Comprimido",
        "liquid": "Líquido",
        "drops": "Gotas",
        "capsule": "Cápsula",
        "injection": "Inyección",
        "patch": "Parche",
        "inhaler": "Inhalador",
        "powder": "Polvo",
        "spray": "Espray"
    },
    "it": {
        "tablet": "Compressa",
        "liquid": "Liquido",
        "drops": "Gocce",
        "capsule": "Capsula",
        "injection": "Iniezione",
        "patch": "Cerotto",
        "inhaler": "Inalatore",
        "powder": "Polvere",
        "spray": "Spray"
    },
    "tr": {
        "tablet": "Tablet",
        "liquid": "Sıvı",
        "drops": "Damla",
        "capsule": "Kapsül",
        "injection": "Enjeksiyon",
        "patch": "Bant",
        "inhaler": "İnhaler",
        "powder": "Toz",
        "spray": "Sprey"
    }
}

# The account device's model, as the app calls the feature.
SYNC_WORD: Final = {
    "de": "iCloud-Synchronisation",
    "en": "iCloud sync",
    "es": "Sincronización con iCloud",
    "it": "Sincronizzazione iCloud",
    "tr": "iCloud eşitlemesi",
}
