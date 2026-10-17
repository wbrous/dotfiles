---
name: logto-react-isloading-authgate-remount-loop
description: "Browser freezes/crashes or endless request loop on a page using @logto/react useLogto with an auth gate showing Loading on isLoading; tabs reset, effects refire."
---

# Logto `isLoading` auth-gate remount loop

## Symptom
Page (e.g. a tab whose panel fetches via an API client) hangs/crashes the browser; tabs snap back to default; the same request fires repeatedly.

## Cause
`@logto/react` `useLogto().isLoading` is a counter flag that goes true around EVERY SDK call, including each `getAccessToken` (the API client calls it per request via a custom `fetch`). A gate like:

```tsx
if (isLoading) return <Loading/>;
if (!isAuthenticated) return <Landing/>;
return <AppShell>{children}</AppShell>;
```
unmounts the whole authed subtree on every request -> remount -> effects refire -> request -> loop.

## Fix
Order the checks so authenticated wins:
```tsx
if (isAuthenticated) return <AppShell>{children}</AppShell>;
if (isLoading) return <Loading/>;
return <Landing/>;
```
Document why in the component's doc comment.

## Verify without real Logto
Throwaway script in the app dir (so react resolves): happy-dom `GlobalRegistrator` + `react-dom/client` + `act`, real `LogtoProvider` with `LogtoClientClass` stub. The stub MUST implement every method `useLogto` binds eagerly (getRefreshToken, getAccessToken, getAccessTokenClaims, getOrganizationToken(+Claims), getIdToken(+Claims), signIn, signOut, fetchUserInfo, clearAccessToken, clearAllTokens) or it throws on `.bind`. Probe child calls `getAccessToken` in a mount effect and counts runs over ~400ms: broken gate = dozens, fixed = 1. Delete the script after.

## Where it was found
optic-fyi `apps/dashboard/src/tenants/parent/views/AuthGate.tsx`.
