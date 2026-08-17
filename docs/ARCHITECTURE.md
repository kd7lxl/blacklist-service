# Architecture

Blacklist-as-a-Service watches a central syslog server for failed Mikrotik
login attempts, uses fail2ban to detect repeated failures from the same
address, and publishes offending addresses through Redis to a longpoll HTTP
server. Edge routers poll that server and add returned addresses to a local
firewall block list.

## System Diagram

```mermaid
flowchart TB
    RouterAuth["Mikrotik Router(s)<br/>(syslog client)"]

    subgraph SyslogHost["Central Syslog Server"]
        direction TB
        Syslog["Syslog Server"]
        Fail2ban["fail2ban<br/>(mikrotik-auth filter + action)"]
        Redis[("Redis")]
        Server["HTTP Longpoll Server<br/>blacklist-longpoll-server.py"]
        Proxy["Reverse Proxy<br/>(optional, TLS)"]
    end

    subgraph Edge["Mikrotik Edge Router"]
        direction TB
        Script["block-address.rsc<br/>(scheduled script)"]
        List[("blacklist<br/>address-list")]
        FW["Firewall rule<br/>drop chain=forward"]
    end

    RouterAuth -->|"login failure logged"| Syslog
    Syslog --> Fail2ban
    Fail2ban -->|"PUBLISH blacklist <ip>"| Redis
    Redis -->|"SUBSCRIBE blacklist"| Server
    Server --> Proxy
    Script -->|"GET / (longpoll)"| Proxy
    Proxy -.->|"<ip>"| Script
    Script --> List
    List --> FW
```

## Sequence Diagram

```mermaid
sequenceDiagram
    participant ER as Edge Router<br/>(HTTP client)
    participant Server as HTTP Server<br/>blacklist-service.py
    participant Redis
    participant Fail2ban
    participant Syslog
    participant Router

    ER->>Server: GET /
    Server-->>ER: 200 OK
    Note right of ER: longpoll wait begins
    Server->>Redis: SUBSCRIBE blacklist
    Note over Router,Redis: wait for a login failure to be logged

    Router-)Syslog: 'login failure for user ...'
    Syslog-)Fail2ban: first login failure
    Fail2ban->>Fail2ban: increment counter

    Router-)Syslog: 'login failure for user ...'
    Syslog-)Fail2ban: second login failure
    Fail2ban->>Fail2ban: increment counter

    Router-)Syslog: 'login failure for user ...'
    Syslog-)Fail2ban: third login failure
    Fail2ban->>Fail2ban: increment counter
    Fail2ban-)Redis: PUBLISH blacklist <ip>

    Redis-->>Server: message received
    Server-->>ER: <ip>

    Note over Fail2ban: fail2ban 'findtime' elapsed
    Fail2ban->>Fail2ban: reset counter

    rect rgb(240, 240, 240)
    Note over ER,Router: timeout example - no addresses to ban before timeout window expires
    ER->>Server: GET /
    Server-->>ER: 200 OK
    Server->>Redis: SUBSCRIBE blacklist
    Note over Router,Redis: wait for a login failure to be logged
    Server->>Server: timeout
    Server-->>ER: 192.0.2.0
    Note right of ER: valid but benign '192.0.2.0' added to ban list
    end
```
