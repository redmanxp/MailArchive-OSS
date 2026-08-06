# Site-specific deploy samples

The generic templates live in `deploy/`:

- `nginx-mailarchive.conf` / `nginx-mailarchive.https.conf`
- `mailarchive-api.service` / `mailarchive-frontend.service`
- `install-systemd.sh` / `install-systemd-user.sh`

Copy and replace placeholders (`mailarchive.example.com`, `__MAILARCHIVE_ROOT__`, `__MAILARCHIVE_USER__`) for your host.
