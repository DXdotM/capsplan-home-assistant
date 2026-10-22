# Security policy

CapsPlan for Home Assistant handles health data and an iCloud sign-in token,
so security reports are very welcome.

## Reporting a vulnerability

Please **do not open a public issue**. Report it privately instead:

- GitHub: **Security** tab → **Report a vulnerability**
  (<https://github.com/DXdotM/capsplan-home-assistant/security/advisories/new>)

Include what you found, how to reproduce it and which version you use.
You will get an answer as soon as possible; fixes are released as a new
version and mentioned in the release notes.

## Supported versions

Only the latest release receives fixes. Update through HACS.

## Scope

- The integration in `custom_components/capsplan`
- The sign-in page in `docs/` (served at <https://dxdotm.github.io/capsplan-home-assistant/>)

The CapsPlan app itself and Apple's iCloud are out of scope here; for the app,
contact <https://dxdotm-coding.com/capsplan_support/>.

See also [Privacy and security](README.md#privacy-and-security) for how data
and tokens are handled.
