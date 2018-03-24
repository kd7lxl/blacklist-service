# Blacklist-as-a-Service

Blacklist-as-a-Service is a set of scripts and configuration files that allow
watching a log file for failed login attempts to Mikrotik routers then blocking
the source of the login attempt on another Mikrotik router.

The intention is that this be run against the aggregate HamWAN network logfile
to block addresses at the edge routers after multiple failed login attempts.

It is made up of the following components:

* Mikrotik router configured for remote syslog
* Syslog server
* fail2ban running on syslog server
* a fail2ban filter watching the log for failed login attempts
* a fail2ban action to publish an address to Redis
* Redis server
* A Python script that subscribes to the Redis server and provides a longpoll
HTTP server
* Optional: a reverse proxy to wrap HTTPS around the longpoll server
* A Mikrotik script that fetchs the address from the longpoll HTTP server and
adds the address to a address list
* A Mikrotik firewall rule to block traffic where source is the blacklist
address list

## Installation

It is assumed you already have your Mikrotik devices logging to a central
syslog server into a file at `LOGPATH`. Install the following on this server.

### Prerequisite: fail2ban

```bash
$ sudo apt-get install fail2ban
$ sudo cp -r fail2ban /etc/
```

Add the following to `/etc/fail2ban/jail.conf`:

```
[mikrotik]

enabled  = true
filter   = mikrotik-auth 
logpath  = LOGPATH
action   = hamwan-blacklist
bantime  = 3
```

```bash
$ sudo service fail2ban reload
```

### Blacklist service

The blacklist service depends on Redis. Redis and the blacklist service can be installed standalone or via docker.

### Standalone

#### Redis

```bash
$ sudo apt-get install redis-server
$ redis-server
```

#### Longpoll HTTP server

```bash
git clone https://github.com/kd7lxl/blacklist-service.git
cd blacklist-service
virtualenv env
source env/bin/activate
(env)$ pip install -r requirements.txt
(env)$ ./blacklist-longpoll-server.py
```

Don't forget to add startup hooks to launch this at boot.

### Docker

```bash
git clone https://github.com/kd7lxl/blacklist-service.git
cd blacklist-sevice
docker-compose up -d
```

That's it! Redis and the blacklist service will now start at boot.

### Mikrotik Edge Router

#### Import the script

Open `block-address.rsc` for editing and change `YOURHTTPSERVER` to target your
longpoll HTTP server.

Now upload and install it:
```
scp block-address.rsc edgerouter:
ssh edgerouter "import block-address.rsc"
```

If you have implemented an HTTPS server, don't forget to add the certs to your
router and `check-certificate=yes` to the script--certificates are not verified
by default!

#### Add firewall rule

```
/ip firewall filter add action=drop chain=forward src-address-list=blacklist place-before=1
```
Suggestion: add a whitelist rule before this to avoid locking yourself out.

#### Schedule script to run at startup

```
/system schedule add name=block-address on-event=block-address start-time=startup
```
