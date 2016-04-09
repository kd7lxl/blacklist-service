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
syslog server into a file at `LOGPATH`.

### fail2ban

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
```

```bash
$ sudo service fail2ban reload
```

### Redis

```bash
$ sudo apt-get install redis-server
$ redis-server
```

### Longpoll HTTP server

```bash
$ virtualenv env
$ source env/bin/activate
(env)$ pip install gevent redis
(env)$ ./longpoll-server.py
```

### Mikrotik Edge Router

```
/system script add name=block-address
/system script edit block-address source
```

```
:while ( true ) do={
:do { /tool fetch url=http://YOURHTTPSERVER }
:local content [/file get [/file find name=blacklist] contents] ;
/ip firewall address-list remove [find list=blacklist address=$content]
/ip firewall address-list add list=blacklist timeout=1w address=$content
:delay 3
};
```

Firewall rule:

```
/ip firewall filter add action=drop chain=input src-address-list=blacklist place-before=1
```

Schedule it to run at startup:

```
/system schedule add name=block-address on-event=block-address start-time=startup
```
