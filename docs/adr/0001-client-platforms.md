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
   - *Rationale for Non-Selection*: Flutter enables cross-platform development with a shared Dart codebase, but choosing it would introduce a separate language ecosystem alongside TypeScript web tooling. Standard DOM-oriented web architectures in Next.js offer better alignment with the text-heavy reading, semantic HTML, and accessibility needs of Hogwarts Trials and Pensieve.
2. **Native iOS (Swift) & Android (Kotlin)**:
   - *Rationale for Non-Selection*: Maintaining two separate platform codebases for The Burrow Clock would require duplicate implementation effort and increase ongoing maintenance for the project.
3. **Single Universal React Native Application (React Native Web for All Products)**:
   - *Rationale for Non-Selection*: Using React Native Web for Hogwarts Trials and Pensieve would add cross-platform abstractions where standard web primitives in Next.js provide a more direct fit for desktop and responsive web layouts.
4. **Separate Unrelated Client Stacks (e.g., Vue, Svelte, Flutter)**:
   - *Rationale for Non-Selection*: Fragmenting the frontend across differing framework ecosystems would increase context-switching and prevent sharing TypeScript contract definitions and tooling.

