# Hogwarts Trials Web Scaffold

This is the initial web application scaffold for Hogwarts Trials. It serves as the foundation for the client application but does not yet contain any business logic, API integrations, or gameplay features.

## Toolchain

- **Framework:** [Next.js](https://nextjs.org) (App Router)
- **Language:** TypeScript
- **Package Manager:** pnpm

## Local Development

Ensure you have run `pnpm install` from the repository root.

To start the development server:

```bash
pnpm --filter hogwarts-trials-web run dev
```

The application will be available at [http://localhost:3000](http://localhost:3000).

## Validation Commands

Run these checks before committing:

```bash
pnpm --filter hogwarts-trials-web run lint
pnpm --filter hogwarts-trials-web run typecheck
pnpm --filter hogwarts-trials-web run build
```
