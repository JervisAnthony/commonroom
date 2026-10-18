# The Burrow Clock mobile privacy preview

An interactive, local-only React Native / Expo preview for iOS and Android. It uses
the existing Expo SDK 57, safe-area handling, system fonts and original clock
ornamentation. No additional dependencies or navigation framework are needed.

## Implemented experience

- A privacy overview with Commonroom branding, a permanent **Location sharing is
  off** message and **Demo preview — not connected** disclosure.
- Two unmistakably fictional contacts, Example Lantern and Example Fern. These
  local identifiers are not accounts, device contacts, real people or friendships.
- Explicit recipient, hypothetical scope (`PRESENCE`, `APPROXIMATE`, `PRECISE`) and
  duration choices. All selections start empty; no preview starts on launch.
- An additional warning for Precise, a recipient/direction/scope/duration review,
  and an explicitly labelled **Start simulated preview** action.
- One outgoing simulation at a time. Settings are locked during a run; the user
  can end it immediately or wait for its exact expiry. The UI says **Preview session
  running — no information is shared**, never that real sharing is enabled.
- Terminal ended/expired states and an explicit fresh-start action. Selections can
  then be changed. A new run never reactivates the old simulation.

Duration choices are 60, 900, 3600 and 86400 seconds, within the API's 60 to 86400
seconds, inclusive, contract. Matching that numeric range does not connect this
preview to the API or confer server authorization.

The interface scrolls within native safe areas, uses large touch targets, visible
selection/disabled/focus states, labelled radio controls and buttons, and scaling
system text. Status includes words rather than color alone. No animation or
external imagery/fonts are used.

## State and privacy boundaries

`src/preview-session.ts` is a narrow pure simulation model. Every transition takes
an explicit millisecond timestamp, validates fictional recipient, outgoing direction,
scope and finite duration, and computes an immutable deadline. Running means
`now < expiresAtMs`; a tick at the exact deadline transitions to expired. Ended and
expired states remain terminal even when a subsequent clock reading moves backwards.
A fresh run needs a new explicit start and receives a new local run number.

The UI uses a local presentation timer only while running and immediately rechecks
expiry when the app returns to the foreground. It makes no server polling calls
and schedules no background task. A paused app may update its visible countdown
only after resuming; the deadline is unchanged and expiry is checked on resume.

All state is in component memory. Closing/restarting the app discards sessions and
selections. Backgrounding alone can retain the in-memory screen, but cannot extend
its deadline. There is no storage, real-world disclosure capability or persisted
permission. The model is not an actual `ConsentGrant` or authentication mechanism.
The one-way preview never enables a reverse-direction choice for the example contact.

The app requests no location permission and never accesses GPS, sensors, contacts,
maps or device identity. It collects and transmits no coordinates, contact data or
presence observations. It contains no authentication, API client, network requests,
telemetry, analytics, geofencing, push notifications or WebSockets. Android's empty
permissions configuration is unchanged. Expo's development server is tooling, not a
product API integration. Real authentication, mutual friendship workflows and
production sharing integration remain deferred; the mobile preview is unconnected
to the existing Burrow Clock backend.

## Development and validation

Use Node **24.20.0** and **pnpm 11.21.0**, as pinned at the repository root. From the
root:

```sh
pnpm install --frozen-lockfile --ignore-scripts
pnpm --filter burrow-clock-mobile run dev
```

Open the app with a compatible Expo Go client or development environment on a device
or emulator. `pnpm --filter burrow-clock-mobile run android` and
`pnpm --filter burrow-clock-mobile run ios` start the corresponding platform; iOS
simulators require macOS. No real account or location permission is needed.

```sh
pnpm --filter burrow-clock-mobile run typecheck
pnpm --filter burrow-clock-mobile run lint
pnpm --filter burrow-clock-mobile run test
pnpm --filter burrow-clock-mobile run config:check
pnpm --filter burrow-clock-mobile run check:dependencies
pnpm --filter burrow-clock-mobile run bundle:check
python scripts/validate_repository.py
python scripts/validate_toolchain.py
python scripts/validate_contract_schemas.py
python -m unittest discover -s scripts/tests
```

Tests use Node's native test runner and synthetic fixtures, with no test dependency,
network, native runtime or backend. They cover default-off and explicit activation,
validation, direction/recipient isolation, finite expiry, immediate termination,
terminal-state nonreactivation, fresh starts and absence of network side effects.
The mobile GitHub Actions workflow makes these tests mandatory.

Set `EXPO_NO_TELEMETRY=1` for validation. For offline tooling checks also set
`EXPO_OFFLINE=1`, as CI does. `bundle:check` exports both iOS and Android JavaScript
into ignored `dist/`; it does not build/sign a native app or prove physical-device,
VoiceOver or TalkBack behavior. Those require a device/emulator review.
