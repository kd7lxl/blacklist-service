# Runbook: No addresses being blocked

Use this when edge routers aren't receiving/blocking addresses that should have
been banned. The pipeline has five hops, and any one of them can silently
drop data:

```
Mikrotik router --syslog--> rsyslog --file--> fail2ban --redis publish--> Redis --pub/sub--> longpoll server --HTTP--> edge router
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full diagram.

## Fast triage

Work from the *end* of the pipe backward — it's faster to confirm the HTTP
server and Redis link with one manual command than to first verify syslog is
flowing.

1. **Longpoll HTTP server** responding at all? → [Check the longpoll endpoint](#1-check-the-longpoll-http-endpoint)
2. **Redis → server** link works (manual publish shows up in curl)? → same section, "manual end-to-end test"
3. **fail2ban → Redis** link works (bans actually call `redis-cli publish`)? → [Check fail2ban logs](#2-check-fail2ban-logs)
4. **fail2ban is watching the right file** and the filter matches real log lines? → [Check fail2ban's logpath](#3-check-fail2bans-log-watch-path) and [Check the logfile](#4-check-the-logfile)
5. **rsyslog is actually receiving and writing Mikrotik entries**? → [Check rsyslog config](#5-check-rsyslog-config)

Whichever hop is the first one that *doesn't* work is where the problem is.

---

## 1. Check the longpoll HTTP endpoint

The server (`blacklist-longpoll-server.py`) listens on port `1234`. On a
request it immediately writes `# longpoll begin`, then polls Redis with a
4-second timeout in a loop of up to 100 iterations, writing `# longpoll wait`
each time it times out, an IP address the moment a message arrives on the
`blacklist` channel (then closes), or `# longpoll timeout` after all 100
iterations (~400s) with nothing published.

```bash
curl -v http://SERVER:1234/
```

Expected output over time:

```
# longpoll begin
# longpoll wait
# longpoll wait
...
203.0.113.5        <- appears here if something gets banned/published
```

Diagnose from what you see:

- **Nothing at all, connection hangs or refused** — the process/container
  isn't up or isn't listening.
  - Docker: `docker-compose ps`, `docker-compose logs web`
  - Standalone: `ps aux | grep blacklist-longpoll-server`, check whatever
    supervises it (systemd unit / init script)
  - Confirm the port is bound: `ss -ltnp | grep 1234`
  - The Dockerfile's own healthcheck is exactly this request:
    `curl --head --fail http://localhost:1234/`
- **`# longpoll begin` appears, then nothing but `# longpoll wait` forever,
  even during a known ban** — the HTTP server is fine but isn't hearing from
  Redis. Go to the manual end-to-end test below.
- **Connection reset / 500 / traceback** — check `docker-compose logs web`
  for a Python exception (commonly a Redis connection failure — see
  `REDIS_HOST` env var in `docker-compose.yml`).

### Manual end-to-end test (isolates Redis↔server from fail2ban↔syslog)

While a `curl -v http://SERVER:1234/` is running and waiting, from the syslog
host run:

```bash
redis-cli publish blacklist '192.0.2.1'
```

- **Shows up in the curl output within ~4s** → the Redis→HTTP server leg is
  healthy. The problem is upstream: fail2ban isn't publishing, or syslog/log
  file isn't feeding fail2ban. Continue to section 2.
- **Doesn't show up** → the server isn't subscribed to the right Redis
  instance/channel.
  - Confirm Redis is reachable from wherever the server runs:
    `docker-compose exec web sh -c 'redis-cli -h $REDIS_HOST ping'` (or
    `redis-cli -h localhost ping` standalone)
  - Confirm `REDIS_HOST` is set correctly for the server process (docker-compose
    sets it to the `redis` service name; standalone defaults to `localhost`)
  - Confirm you published to the same Redis instance the server is bound to —
    port bindings in `docker-compose.yml` are `127.0.0.1` only, so publishing
    from a different host will silently go to the wrong (or no) Redis.

## 2. Check fail2ban logs

Default location: `/var/log/fail2ban.log`.

```bash
sudo tail -f /var/log/fail2ban.log
```

Trigger (or wait for) a failed Mikrotik login and look for, in order:

- `Jail 'mikrotik' started` — confirms the jail loaded at all. If missing,
  check `sudo fail2ban-client status` for a jail list and
  `sudo systemctl status fail2ban`.
- `[mikrotik] Found <ip>` — the filter regex matched a log line. If you never
  see `Found` despite known failed logins, the problem is the filter regex or
  the logpath (sections 3–4).
- `[mikrotik] Ban <ip>` — three `Found`s within `findtime` triggered the ban
  action (`hamwan-blacklist`, i.e. `redis-cli publish blacklist '<ip>'`). If
  you see `Found` repeatedly but never `Ban`, matches aren't landing inside
  the same `findtime` window, or `maxretry` isn't being reached.
- Any error immediately after a `Ban` line — the action command itself
  failed (e.g. `redis-cli` not on fail2ban's `PATH`, wrong host/port,
  connection refused). Reproduce it directly as root to confirm:
  `redis-cli publish blacklist '203.0.113.9'` — if this fails standalone, fix
  it there first.

For more detail, temporarily bump the log level (revert after):

```bash
sudo sed -i 's/^loglevel.*/loglevel = DEBUG/' /etc/fail2ban/fail2ban.conf
sudo service fail2ban reload
```

## 3. Check fail2ban's log watch path

Confirm fail2ban is actually tailing the file rsyslog is writing to:

```bash
sudo fail2ban-client status mikrotik      # bans, currently failed, etc.
sudo fail2ban-client get mikrotik logpath # file(s) this jail is watching
```

Compare that output against the `logpath` configured in the `[mikrotik]`
stanza (installed into `/etc/fail2ban/jail.conf` per the README —
consider moving it to `/etc/fail2ban/jail.local` so it survives package
upgrades). A common failure mode: the README's `LOGPATH` placeholder was
never replaced with the real path, so fail2ban is watching a file that
doesn't exist or isn't the one rsyslog writes to.

If you change `logpath`, reload: `sudo service fail2ban reload`.

## 4. Check the logfile

Tail the real log file (the actual path, not the `LOGPATH` placeholder) while
triggering a failed login:

```bash
sudo tail -f /path/to/mikrotik.log
```

Confirm lines are arriving at all, and that their wording matches the filter
regex in `fail2ban/filter.d/mikrotik-auth.conf`:

```
failregex = login failure for user .* from <HOST> via
```

RouterOS versions/services can word this differently (winbox vs ssh vs
telnet vs api), so the fastest way to check for a match without touching
config is fail2ban's own regex tester:

```bash
fail2ban-regex /path/to/mikrotik.log /etc/fail2ban/filter.d/mikrotik-auth.conf
```

This reports how many lines matched vs. how many failed to match, and prints
example non-matching lines — use it to tell "syslog is delivering data but
the filter can't parse it" apart from "no data is arriving at all."

Also check the file isn't stale/empty (`ls -la`, check timestamps) — a
misconfigured logrotate can truncate the file out from under fail2ban's open
file handle; if so, `sudo fail2ban-client restart`.

## 5. Check rsyslog config

If the logfile in step 4 is empty or missing recent entries, rsyslog isn't
receiving or isn't writing the Mikrotik messages.

Confirm rsyslog is up and listening for remote syslog (Mikrotik typically
sends UDP):

```bash
sudo systemctl status rsyslog
sudo ss -ulnp | grep 514   # UDP
sudo ss -tlnp | grep 514   # TCP, if configured
```

Confirm the receiving module/input is enabled, in `/etc/rsyslog.conf` or
`/etc/rsyslog.d/*.conf`:

```
module(load="imudp")
input(type="imudp" port="514")
```

(or the legacy `$ModLoad imudp` / `$UDPServerRun 514` syntax).

Confirm there's a rule routing Mikrotik's messages to the logfile fail2ban is
watching — typically keyed on source IP or facility, e.g.:

```
if $fromhost-ip == '<mikrotik-router-ip>' then /path/to/mikrotik.log
& stop
```

After any edit, syntax-check before restarting:

```bash
sudo rsyslogd -N1
sudo systemctl restart rsyslog
```

Also confirm from the Mikrotik side that it's actually sending:

- `/system logging action print` — remote target should point at this
  syslog server's IP and port 514
- `/system logging print` — there must be a rule sending the relevant topic
  (e.g. `account`, or whatever topic covers login failures) to that remote
  action
- Firewall between router and syslog host allows UDP/TCP 514 in both
  directions (`sudo iptables -L -n | grep 514` on the syslog host)

## 6. Edge router side (last hop, less common to be at fault)

If everything above checks out but the router still isn't blocking:

```
/system script run block-address
/ip firewall address-list print where list=blacklist
/log print
```

Look for `Blocked <ip>` (success) or `Error fetching blacklist` (the script's
own `/tool fetch` failed — check the URL in `block-address.rsc` matches the
real longpoll server/reverse proxy, and if HTTPS, that `check-certificate` and
certs are set up).
