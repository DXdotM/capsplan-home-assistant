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

UPDATE_INTERVAL: Final = timedelta(minutes=5)
RECOMPUTE_INTERVAL: Final = timedelta(minutes=1)

STORAGE_VERSION: Final = 1

APP_STORE_URL: Final = "https://apps.apple.com/app/id6779642344"
