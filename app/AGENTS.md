# AI Agent Conventions - AGENTS.md

_Stack: **React** · **TypeScript** · Agent: **Codex**_

> **Apply ALL rules below for every file generated or modified in this project.** > **These rules are non-negotiable and must be followed without exception.**
> Do not summarize, skip, or partially apply these rules.
> Do not use your default style if it conflicts with any rule defined here.
> When in doubt, re-read the relevant section before generating code.
> Use english for code, comments, file names, etc.
> When in doubt about flow or code, ask the user before doing anything.

---

## 1. Project Stack

You are operating inside a **React + TypeScript** codebase.
All code you generate MUST be valid, idiomatic TypeScript for React.

- **Framework**: React
- **Language**: TypeScript
- **Rules file**: AGENTS.md (loaded by Codex)

---

## 2. Directory Structure

You MUST place every file in the correct directory as defined below.
Creating files outside these directories is **strictly forbidden** unless the user explicitly instructs otherwise.

```
src/           # Project source code root.
├── components/           # Shared UI components (Button, Input, Card).
│   └── ComponentName/
│       ├── index.tsx
│       └── ComponentName.tsx
├── hooks/           # Custom React hooks - all prefixed with "use".
├── utils/           # Pure helper functions (formatDate, cn, etc.).
├── styles/           # Global CSS / design tokens.
└── types/           # Global TypeScript interfaces and types.
```

### Directory Roles

Each directory has a single, fixed responsibility. Never mix concerns across directories.

- **`src/`** - Project source code root.
- **`src/components/`** - Shared UI components (Button, Input, Card).
- **`src/hooks/`** - Custom React hooks - all prefixed with "use".
- **`src/utils/`** - Pure helper functions (formatDate, cn, etc.).
- **`src/styles/`** - Global CSS / design tokens.
- **`src/types/`** - Global TypeScript interfaces and types.

---

## 3. Coding Standards & Conventions

Use the linter rules to define your coding style.

---

## 4. Performance & Optimizations

Apply the following optimization techniques proactively - do not wait to be asked.

- **Profile Before You Optimize**: Open React DevTools → Profiler tab. Record an interaction. Find components with long render bars. Only optimize what the profiler proves is slow - premature optimization is wasted effort.
- **React.memo for Expensive Pure Components**: Wrap a component in React.memo when it renders frequently but its props rarely change (e.g., long list items, chart rows). Don't memo everything - if props change every render, memo adds overhead without benefit.
- **useCallback for Stable Handler References**: Wrap event handlers passed to memoized child components in useCallback so they don't get a new reference every render. Pair with React.memo on the child. Measure first.
- **useMemo for Expensive Computations**: Wrap expensive derived calculations (filtering/sorting large arrays, complex transforms) in useMemo. Only apply when the computation is genuinely slow - the React DevTools Profiler will show this.
- **Code-Split Heavy Components with React.lazy + Suspense**: Use React.lazy and Suspense to load heavy or rarely used components on demand (rich text editors, chart libraries, map components). This shrinks the initial JS bundle significantly.
- **Scope Context Narrowly or Replace with a Client State Library**: Every Context consumer re-renders when any value changes. Split large contexts by concern, or replace with a client state library (Zustand, Jotai, Valtio, etc.) that supports granular selector subscriptions.
- **Analyze and Trim the Bundle**: Use vite-bundle-visualizer or source-map-explorer to find large dependencies. Replace bloated libraries with lighter alternatives (date-fns vs moment, lucide-react vs all of @mui/icons). Test with a production build.

---

## 5. Agent Behaviour Rules

These rules govern HOW you operate, not just WHAT you produce.

- **Never invent new folders or files outside the structure in Section 2.**
- **Never use `any` type** in TypeScript code. Use `unknown` with type narrowing instead.
- **Never suppress lint or type errors** with `// @ts-ignore`, `eslint-disable`, or similar directives.
- **Never introduce new dependencies** without explicitly asking the user first.
- **Always validate your output** against Section 3 rules before presenting it.
- **Always explain trade-offs** when you deviate from a rule due to a user's explicit instruction.
- **Readability > brevity.** Write code a junior developer can understand and maintain.
- **Self-check:** Before outputting code, silently verify: correct directory? naming conventions met? no forbidden patterns?

## 6. Git Discipline & Automated Commits

Maintain a clean, atomic Git history.

1. **Pre-commit Check**:
    - Run `git status` and `git diff` to inspect changes.
    - Verify that no secret keys, environment files (`.env`), temporary files, or auto-generated logs are staged.
2. **Commit Policy**:
    - Create atomic commits after completing each logical sub-task (when tests pass).
    - Use **Conventional Commits** format:
        - `feat(scope): add new feature`
        - `fix(scope): resolve bug or edge case`
        - `refactor(scope): internal code improvement without behavior change`
        - `test(scope): add or update unit tests`
        - `docs(scope): update project documentation`
3. **Branch Hygiene**:
    - Keep commits small and easy to review or revert.

## 7. Safety & Guardrails

- **Destructive Operations**: Never drop database tables, purge caches, or execute destructive CLI commands without explicit permission or dry-run validation.
- **Production Safety**: Mock external API calls in unit tests; never hit live production endpoints during testing.
- **No Unused Code**: Clean up debug statements, commented-out code, and temporary console logs before completing a task.
