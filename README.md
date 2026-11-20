# Easynet Web

A modern, local, read-only interface for monitoring an Ecoforest heat pump
through its EasyNet web interface.

The application keeps a long-term copy of EasyNet measurements and exposes a
responsive web dashboard with current status, historical power data, and daily,
monthly, and annual energy summaries.

> **Enjoying the project? Buy me a coffee!**
> You can support its development with a voluntary donation on Ko-fi.

[![Support this project on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/mcalve)

## Features

- Current heat-pump status and operating program.
- Heating, cooling, DHW, and demand status.
- Electrical and thermal power.
- Instantaneous COP.
- Temperatures and circuit pressures.
- Current-day and current-month energy counters.
- Active alarm status.
- Five-minute historical power charts.
- Daily consumption and production chart for a selected month.
- Annual chart using EasyNet's native monthly counters.
- ACS, heating, cooling, passive cooling, pool, auxiliary consumption, SPF,
  and SPFG in the annual view when reported by the machine.
- Persistent history beyond EasyNet's approximately three-month retention.
- Clock-change handling and data-quality tracking for incomplete days.
- English, Spanish, German, French, Italian, Dutch, and Polish.
- Celsius/Fahrenheit selection.
- Editable private EasyNet IP through the application.
- Responsive desktop and mobile layout.
- Local SQLite backups.

The application is currently **read-only**. It does not write registers, coils,
settings, or commands to EasyNet.

## Architecture

```text
Browser on the trusted LAN
        |
      Caddy
        |
 FastAPI + collector
        |
      SQLite
        |
      EasyNet
```

- `backend/`: FastAPI API, EasyNet client, collector, CSV importer, and SQLite.
- `frontend/`: React/TypeScript responsive web application and charts.
- `deploy/`: systemd units, Caddy configuration, and backup tooling.
- `fixtures/`: sanitized protocol responses and historical CSV fixtures.

The collector serializes requests because EasyNet's embedded web server is not
designed for concurrent access. Historical CSV files are imported
idempotently, and repeated files do not duplicate samples.

## Requirements

Recommended deployment target:

- Raspberry Pi 4 or equivalent Linux machine.
- Raspberry Pi OS/Debian 13 or another compatible Linux distribution.
- Python 3.12 or later.
- Node.js 22 LTS or later.
- Caddy.
- Network access to EasyNet.

EasyNet must remain reachable only from the trusted LAN. Do not expose EasyNet
directly to the Internet.

## Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Minimum configuration, adapted to the actual EasyNet address:

```dotenv
EASYNET_HOST=https://192.0.2.10
```

`192.0.2.10` is a documentation-only address. Replace it with the EasyNet IP
or resolvable hostname on your network.

For HTTPS access to this web application, also set the address clients will
use:

```dotenv
EASYNET_HTTPS_ADDRESS=192.0.2.20
```

If the installed EasyNet firmware requires authentication, add:

```dotenv
EASYNET_USERNAME=
EASYNET_PASSWORD=
```

Credentials are optional for installations that allow local reads without
authentication. When configured, they are used only by the backend collector
and are never sent to the browser.

The application stores the active EasyNet IP in SQLite. The IP can later be
changed from the Settings dialog after successful deployment.

EasyNet commonly uses a self-signed HTTPS certificate. Certificate verification
is disabled by default for this private connection:

```dotenv
EASYNET_VERIFY_TLS=false
```

## Development

### Backend

```bash
python3 -m venv .venv
.venv/bin/pip install -e . pytest pytest-asyncio ruff -c constraints.txt
.venv/bin/pytest
.venv/bin/ruff check backend
```

### Frontend

```bash
cd frontend
npm ci
npm test
npm run build
```

## Deployment on Raspberry Pi

See [deploy/README.md](deploy/README.md) for the complete systemd and Caddy
deployment procedure. It is a reference deployment; the same backend and
static frontend can be run with another service manager, container platform,
or reverse proxy as long as the API remains private and the database volume is
persistent.

Expected production paths:

- Code: `/opt/easynet-web`
- Data: `/var/lib/easynet-web`
- Configuration: `/etc/easynet-web.env`
- Local backups: `/var/lib/easynet-web/backups`

The API listens on loopback and Caddy serves the web application to the local
network. The HTTPS example reads `EASYNET_HTTPS_ADDRESS`; a separate
HTTP-only Caddyfile is provided on port 8080 for initial setup.

The web application does not need a public hostname or public Internet
exposure.

## HTTPS and PWA

The web application includes PWA metadata and a service worker. Full PWA
installation requires a secure context. Use either a trusted hostname or a
private IP with Caddy's internal certificate, then trust the Caddy root CA on
each client.

The web interface remains usable over trusted LAN HTTP during initial setup,
but that mode is not the recommended final state.

## Historical data

EasyNet historical CSV files contain samples at approximately five-minute
intervals. The collector:

1. checks the current `/historic/` file;
2. checks closed days under `/historic/backup/`;
3. imports available retained days without duplicates;
4. preserves repeated local times during clock changes;
5. recalculates daily and monthly energy summaries;
6. reads native EasyNet monthly counters for the annual chart.

The application records data quality internally:

- complete;
- estimated;
- incomplete.

Totals derived from an incomplete day should be treated as lower-confidence
measurements, especially if EasyNet missed several intervals.

## Backup

The included systemd timer runs a daily SQLite backup using SQLite's online
backup API. Backups are stored locally with a 14-day retention period.

Run a manual backup with:

```bash
sudo systemctl start easynet-backup.service
```

Copying the active SQLite file directly is not recommended.

## Security

- Keep the application on a trusted local network.
- Do not forward the application or EasyNet ports directly to the Internet.
- Protect `/etc/easynet-web.env`; it contains EasyNet credentials.
- Run the service as its dedicated unprivileged `easynet` user.
- Keep the Raspberry Pi and dependencies updated.
- This release is read-only and has no EasyNet write endpoint.

## Compatibility

Protocol decoding has been verified against one Ecoforest ecoGEO installation
using EasyNet 2024 firmware. Other models, firmware versions, optional
components, and configurations can expose different blocks or units.

If EasyNet returns an unsupported response, the application reports an error
instead of inventing or silently retaining a valid-looking new value.

## Safety and disclaimer

This project is unofficial and is not affiliated with, endorsed by, or
supported by Ecoforest.

Use this software at your own risk. No warranty is provided. Review values and
machine behavior against the official EasyNet interface, and consult your
installer when diagnosing alarms or unexpected operation.

To the fullest extent permitted by applicable law, the author and contributors
accept no liability for faults, malfunctions, damage to the heat pump or
connected equipment, or any other loss arising from the use of this project.

**Ecoforest** and **ecoGEO** are trademarks of their respective owners within
the Ecoforest group. They are used only to identify compatible equipment; no
ownership of those trademarks is claimed.

## Acknowledgements

The EasyNet protocol investigation was informed by the
[Ecoforest ecoGEO integration for Home Assistant by bytestorm](https://github.com/bytestorm/ecoforest_ecogeo)
and by the separately developed
[homebridge-ecoforest-ecogeo](https://github.com/mcalvete/homebridge-ecoforest-ecogeo)
plugin. Those projects are independent dependencies and references, not
runtime requirements of this application.

## License

Released under the [MIT License](LICENSE).

## Support the project

**Keeping your home comfortable? Buy me a coffee!**

If this project makes your ecoGEO a little smarter, consider supporting its
development with a donation on [Ko-fi](https://ko-fi.com/mcalve).
Donations are entirely optional and always appreciated. Thank you for your support!

[![Support this project on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/mcalve)

