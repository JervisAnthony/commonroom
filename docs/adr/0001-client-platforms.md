# ADR 0001: Client Platform Strategy

## Status
Accepted

## Context
The **Commonroom** ecosystem comprises three distinct user-facing applications with differing primary interaction models and form-factor requirements:

1. **Hogwarts Trials**: Academic trivia, examination progression, and house competitions require rich interactive desktop and responsive web layouts, fast page loads, and accessible typography.
2. **Pensieve**: AI companion interactions, canonical lore reading, and wizarding world news discovery benefit from web-first responsive reading experiences, markdown rendering, and accessible search interfaces.
3. **The Burrow Clock**: Consensual friend and family presence sharing requires native mobile hardware integration, including battery-efficient background location telemetry, mobile push notifications, and geofencing capabilities.

The client platform strategy must establish frontend consistency across the repository without forcing inappropriate form factors onto products that do not require them for MVP.

---

## Decision

We adopt a **TypeScript-first, React-aligned client architecture** tailored per product domain:

1. **Hogwarts Trials**: Web-first client using **TypeScript**, **React**, and **Next.js**.
2. **Pensieve**: Web-first client using **TypeScript**, **React**, and **Next.js**.
3. **The Burrow Clock**: Mobile-first client using **TypeScript**, **React Native**, and **Expo**.

### Future Expansion Scope
- Future mobile clients for Hogwarts Trials or Pensieve may reuse React Native and Expo where justified by user demand, but they are explicitly excluded from the current baseline implementation scope.
- Exact framework versions will be selected during application scaffolding based on current stable releases.

---

## Consequences

### Positive
- **Language Consistency**: TypeScript is standard across all frontend codebases, allowing shared type definitions and contract consumption from `commonroom-core`.
- **Component Mental Model**: React component patterns, state management concepts, and developer familiarity apply across both web (Next.js) and mobile (React Native / Expo).
- **Native Mobile Capabilities**: Expo provides a mature ecosystem for native mobile device APIs (location services, geofences, background tasks, and notifications) essential for The Burrow Clock.
- **Web Performance**: Next.js provides optimized server rendering, static generation for lore/news content, and rapid client routing for Hogwarts Trials and Pensieve.

### Trade-offs
- Web and mobile runtimes remain distinct environments (Next.js web runtime vs. React Native mobile runtime), requiring separate client build pipelines.

---

## Alternatives Considered

1. **Flutter**:
   - *Rationale for Rejection*: While Flutter provides cross-platform mobile and web output from a single Dart codebase, it introduces a non-standard web rendering model (Canvas/WASM-based DOM) that impairs web accessibility, SEO, and document layout for lore reading in Pensieve and trivia in Hogwarts Trials. It also diverges from the TypeScript contract ecosystem.
2. **Native iOS (Swift) & Android (Kotlin)**:
   - *Rationale for Rejection*: Maintaining two separate native codebases for The Burrow Clock introduces excessive maintenance overhead and splits engineering effort for a community fan project.
3. **Single Universal React Native Application (React Native Web for All Products)**:
   - *Rationale for Rejection*: Forcing Hogwarts Trials and Pensieve into React Native Web imposes unnecessary UI/UX constraints on web layout, browser navigation, and rich document styling where Next.js provides a vastly superior web-native experience.
4. **Separate Unrelated Client Stacks (e.g., Vue, Svelte, Flutter)**:
   - *Rationale for Rejection*: Fragmenting the frontend across different ecosystems would eliminate shared frontend tooling, prevent reusable TypeScript contracts, and increase developer cognitive overhead.

