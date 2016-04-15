/system script
job remove [find script=block-address]
remove [find name=block-address]
add name=block-address policy=read,write,test source=":while ( true ) do={\
    \n    :do {\
    \n        /tool fetch url=https://YOURHTTPSERVER dst-path=blacklist\
    \n        :local content [/file get [/file find name=blacklist] contents] ;\
    \n        :if ([:pick \"\$content\" 0] != \"#\") do={\
    \n            /ip firewall address-list remove [find list=blacklist address=\$content]\
    \n            /ip firewall address-list add list=blacklist timeout=1h address=\$content\
    \n            :log info \"Blocked \$content\"\
    \n        }\
    \n    } on-error={\
    \n        :log error \"Error fetching blacklist\"\
    \n        :delay 3\
    \n    }\
    \n};"
:execute {/system script run block-address};