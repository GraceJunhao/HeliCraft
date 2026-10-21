# Configuration for an independent deployment

The public source does not contain the hosted service's API key, SMTP authorization
code, session secret, user database or tunnel configuration. Configure your own values
through environment variables. `.env.example` contains only empty placeholders and
example settings. Do not put real values in that file.

| Variable | Purpose |
| --- | --- |
| `HELICRAFT_SMTP_USER` | Sender account for the existing email-login workflow |
| `HELICRAFT_SMTP_PASS` | SMTP password or provider authorization code |
| `HELICRAFT_SMTP_HOST` | SMTP hostname; the existing mail function uses SSL port 465 |
| `HELICRAFT_AI_SESSION_SECRET` | Independent signing secret, at least 32 characters |
| `HELICRAFT_AI_API_KEY` | Your provider credential for Jack |
| `HELICRAFT_AI_MODEL` | Provider model identifier available to your account |
| `HELICRAFT_AI_BASE_URL` | Provider's HTTPS API base URL |
| `HELICRAFT_AI_COOKIE_SECURE` | `0` for local HTTP testing, `1` for HTTPS deployment |
| `HELICRAFT_AI_PUBLIC_ORIGIN` | Browser origin of your deployment |

Generate a new signing secret locally, then put the result in your private `.env`:

```sh
python -c "import secrets; print(secrets.token_hex(32))"
```

Uvicorn loads `.env` when launched with `--env-file .env`. A systemd deployment can
instead use an administrator-managed EnvironmentFile outside the source checkout.
Do not copy a production service unit or environment file into this repository.

The packaging tool replaces recognized literal configuration assignments only in its
in-memory publication copy. It does not change the running installation. Unknown
suspect values stop packaging and require a targeted review of the indicated source
location. Reports contain file names, line numbers and reasons, never matched values.

Before publishing, inspect the extracted candidate, including comments and HTML.
Automated pattern checks cannot prove the absence of all personal data or secrets.
`.gitignore` prevents common accidental additions but cannot remove files that are
already tracked or erase credentials from earlier Git commits. If a credential has
already been exposed, revoke it at the provider and separately address repository history.
