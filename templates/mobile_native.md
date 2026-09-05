# Product type: mobile_native

DEC-010: native mobile is an ASF factory product type. Keep v1 **simple** — one platform-first binary, not a multi-tenant Super App.

## Typical MVP

- One primary platform first (Android **or** iOS), second store only if TZ requires it
- One happy-path job (list + detail, booking, or form — not all three plus chat)
- Local persistence for that job; accounts only if TZ says so
- Push / camera / location **only** when listed as must-have
- Store listing can be “internal build” in v1 (TestFlight / APK)

## Discovery checklist

- [ ] Audience and the one job the app does
- [ ] Platforms in v1 (Android, iOS, both — both raises estimate)
- [ ] Current process / why not a site or Telegram bot
- [ ] Public identity (name on the home screen and store)
- [ ] Auth: none / phone / existing account
- [ ] Offline needs (none vs last-view cache vs real offline writes)
- [ ] Device capabilities (push, camera, files, location) — must vs later
- [ ] Distribution (internal, TestFlight/Play internal, public stores)
- [ ] Brand assets and design references (what to reuse)
- [ ] Design direction (system-native vs custom chrome — impacts estimate)
- [ ] Legal: 152-FZ / personal data, store privacy nutrition labels
- [ ] Backend: none, existing API, or a small companion `rest_service` (escalate if a second product)
- [ ] Timeline and budget
- [ ] Contact details and preferred channel
- [ ] Acceptance: how the owner will check the build

## Out of scope for this template

Cross-platform rewrite in two languages “because we can”, in-app payments, Super App navigation, background geofencing fleets, Wear/TV/Car companions. React Native / Flutter / native Kotlin/Swift are implementation choices — lock one in TZ, do not dual-track.

Map “мы хотели приложение, но достаточно бота” back to `telegram_bot` or `website` instead of forcing native.
