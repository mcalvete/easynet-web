# Deployment

This guide describes a generic Linux deployment. The recommended target is a
Raspberry Pi or another machine that remains on the same trusted network as
EasyNet. Do not run the application, frontend, or API as `root`.

## Requirements

- Python 3.12 or later.
- Node.js 22 LTS or later.
- Caddy.
- `systemd`.
- A machine that can reach EasyNet.
- SSH or console access for installation.

## Recommended paths

- Source/build: `/opt/easynet-web`
- Data: `/var/lib/easynet-web`
- Configuration: `/etc/easynet-web.env`
- Logs: systemd journal
- Local backups: `/var/lib/easynet-web/backups`

These paths are the defaults used by the supplied service files. They can be
changed, but the units and Caddyfile must be edited consistently.

## 1. Create the service account

```bash
sudo useradd --system --home /var/lib/easynet-web --shell /usr/sbin/nologin easynet
sudo install -d -o easynet -g easynet -m 755 /opt/easynet-web
sudo install -d -o easynet -g easynet -m 750 \
  /var/lib/easynet-web /var/lib/easynet-web/backups /var/log/easynet-web
```

## 2. Install the source

Copy this repository to `/opt/easynet-web` using your normal deployment tool.
Do not copy `.env`, `.venv`, `node_modules`, local databases, or local logs.
After copying:

```bash
sudo chown -R easynet:easynet /opt/easynet-web
sudo chmod 755 /opt/easynet-web
```

Create the Python environment:

```bash
sudo -u easynet python3 -m venv /opt/easynet-web/.venv
sudo -u easynet /opt/easynet-web/.venv/bin/pip install \
  -e /opt/easynet-web -c /opt/easynet-web/constraints.txt
```

Build the frontend:

```bash
sudo -u easynet bash -c \
  'cd /opt/easynet-web/frontend && npm ci && npm run build'
```

The resulting files are served from `/opt/easynet-web/frontend/dist`.

## 3. Configure the application

Copy the template and restrict its permissions:

```bash
sudo install -m 600 -o easynet -g easynet \
  /opt/easynet-web/.env.example /etc/easynet-web.env
```

Set at least:

```dotenv
EASYNET_HOST=https://YOUR_EASYNET_HOST
EASYNET_HTTPS_ADDRESS=YOUR_EASYNET_WEB_HOST_OR_IP
DATABASE_PATH=/var/lib/easynet-web/easynet.db
API_HOST=127.0.0.1
API_PORT=8000
```

`EASYNET_USERNAME` and `EASYNET_PASSWORD` are optional. Add them only when the
installed EasyNet firmware requires authentication.

## 4. Install systemd services

Install the API service and backup timer:

```bash
sudo install -m 644 \
  /opt/easynet-web/deploy/systemd/easynet-web.service \
  /etc/systemd/system/easynet-web.service
sudo install -m 644 \
  /opt/easynet-web/deploy/systemd/easynet-backup.service \
  /etc/systemd/system/easynet-backup.service
sudo install -m 644 \
  /opt/easynet-web/deploy/systemd/easynet-backup.timer \
  /etc/systemd/system/easynet-backup.timer
sudo install -m 755 -o root -g root \
  /opt/easynet-web/deploy/backup-easynet.sh \
  /usr/local/libexec/easynet-backup
sudo systemctl daemon-reload
sudo systemctl enable --now easynet-web
sudo systemctl enable --now easynet-backup.timer
```

## 5. Choose an access mode

### HTTPS by private IP

Use this when clients connect by a private IP address, including through a
routed VPN.

Set the address in `/etc/easynet-web.env`:

```dotenv
EASYNET_HTTPS_ADDRESS=192.0.2.20
```

Then configure Caddy:

```bash
sudo install -d -m 755 /etc/systemd/system/caddy.service.d
sudo install -m 644 \
  /opt/easynet-web/deploy/systemd/caddy-easynet.conf \
  /etc/systemd/system/caddy.service.d/easynet.conf
sudo install -m 644 /opt/easynet-web/deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl daemon-reload
sudo env EASYNET_HTTPS_ADDRESS=192.0.2.20 \
  caddy validate --config /etc/caddy/Caddyfile
sudo systemctl restart caddy
```

Caddy issues an internal certificate whose subject is the configured IP. The
IP must be reachable from the Caddy host.

### HTTPS by local hostname

Use this when a local hostname resolves consistently for all clients, for
example `easynet.example.lan`:

```dotenv
EASYNET_HTTPS_ADDRESS=easynet.example.lan
```

Install the same Caddy drop-in and Caddyfile shown above. Names ending in
`.local` use mDNS and normally do not resolve across routed VPNs; prefer a
hostname provided by ordinary local DNS for cross-network access.

### Temporary HTTP

For initial setup, an HTTP-only Caddyfile is also provided:

```bash
sudo install -m 644 /opt/easynet-web/deploy/Caddyfile.http /etc/caddy/Caddyfile
sudo systemctl restart caddy
```

This serves the application on port 8080. Keep it on a trusted network and
switch to HTTPS before relying on PWA installation or remote VPN access.

## 6. Trust the internal CA

Caddy stores its local root certificate at:

```text
/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt
```

Every client must trust that CA:

- macOS: import `root.crt` in Keychain Access and trust it for SSL.
- iPhone/iPad: install the profile, then enable full trust under
  `Settings > General > About > Certificate Trust Settings`.

The certificate is a public trust anchor, not a private server key. Never
publish EasyNet credentials or Caddy's private key.

## Verification

```bash
sudo systemctl status easynet-web
sudo systemctl status caddy
sudo systemctl status easynet-backup.timer
curl --fail http://127.0.0.1:8000/api/health
```

For the selected HTTPS address, run on the Caddy host:

```bash
curl --cacert /var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt \
  --fail https://YOUR_HTTPS_ADDRESS/api/health
```

The browser should report a secure context and register the Service Worker.
On a phone, install the web app from the browser's share/add-to-home-screen
menu after the CA is trusted.

## Backups

The timer creates a consistent local SQLite backup every day and retains 14
days. Test one manually:

```bash
sudo systemctl start easynet-backup.service
sudo journalctl -u easynet-backup.service -n 30 --no-pager
```

Copying the active database directly is not recommended. Any encrypted or
off-site copy procedure should be managed outside this public repository and
tested with a full restore.
