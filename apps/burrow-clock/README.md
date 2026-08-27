# The Burrow Clock

**The Burrow Clock** is a mobile-first, privacy-fundamental consensual family and friend presence sharing application within the Commonroom ecosystem.

## Product Scope & Boundaries
- **Domain Responsibilities**: Friend/family relationships for location sharing, geofencing, presence state computation, per-friend permission scoping, location-sharing sessions, group clock UI, and optional map views.
- **Non-Responsibilities**: Wizarding lore retrieval, trivia authoring, or AI-generated lore reasoning.

## Privacy Invariants
- Location sharing is default-off, strictly opt-in, permission-scoped per friend, and immediately revocable.
- Raw GPS coordinates are never broadcast by default; ambient presence and geofence states are prioritized.
- Fantasy/roleplay statuses (e.g., *"Mortal Peril"*) are purely aesthetic and strictly decoupled from real-world emergency/SOS features.

*Note: Application implementation and framework scaffolding will be introduced in subsequent commits.*

