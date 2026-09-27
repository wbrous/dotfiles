---
name: logto-remote-admin-console-access
description: "Access or recover a remote Logto Admin Console: public URL over SSH tunnels, temporary port overrides, sign-in-only tenant fix, orphaned admin deletion"
---

# Remote Logto Admin Console access and recovery

Use when the Logto Admin Console runs on a remote host under docker compose and you need browser access, first-run setup is broken, or the admin password is lost. Assumes SSH access to the host and a `postgres` compose service holding Logto's database.

## Prefer the public HTTPS admin URL

This sandbox's browser tool cannot reach localhost/127.0.0.1 SSH tunnels (curl succeeds, the browser gets `ERR_CONNECTION_REFUSED`). Do not fight the tunnel: use the public admin URL through the edge proxy (e.g. `https://admin.accounts.<domain>/`). Only fall back to a tunnel if no public route exists, and verify with curl first — curl working proves nothing about browser reachability.

## Compose may strip the app service's ports

Check the root compose for `ports: !override []` on the Logto `app` service (optic-fyi does this so only Caddy binds host ports). If present, direct `:3001`/`:3002` access fails even via tunnel. Re-expose on loopback only with a temporary override file (never commit this):

```yaml
# /tmp/ports.yml
services:
  app:
    ports:
      - '127.0.0.1:3001:3001'
      - '127.0.0.1:3002:3002'
```

`docker compose -f docker-compose.yml -f /tmp/ports.yml up -d app`, then wait ~25-30s for Logto boot. Early probes return `000`/connection refused while it boots; healthy is `302` on both ports. Consult `docker compose logs app --tail` if unsure.

## "Create account" bounces to sign-in with no register link

Someone set the tenant to sign-in-only mode, which also kills the first-run flow. Confirm and fix in the Logto database (`docker compose exec -T postgres psql -U logto -d logto`):

```sql
select sign_in_mode from sign_in_experiences;
update sign_in_experiences set sign_in_mode='SignInAndRegister' where sign_in_mode='SignIn';
```

After the fix the form shows "No account yet? Create account". No container restart needed.

## Forgotten admin password with no SMTP configured

Delete the orphaned admin row so `/console/welcome` offers Create account again. First confirm which user holds the admin role, then delete only that user's rows:

```sql
select id, username, primary_email from users;
select user_id, role_id from users_roles;
delete from users_roles where user_id='<admin-id>';
delete from users where id='<admin-id>';
```

Leave all other users untouched. Reload `/console/welcome` and verify it offers "Create account" before handing off.

## DNS prerequisite for the public URL

Subdomains served by Caddy must resolve to the host with proxying off (Cloudflare grey cloud, DNS-only). Proxied records break Let's Encrypt HTTP-01 issuance, and none of the Logto/browser flows work until the public URLs answer with real certs.
