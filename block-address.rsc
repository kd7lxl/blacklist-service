/system script
job remove [find script=block-address]
remove [find name=block-address]
add name=block-address policy=read,write,test source=":while ( true ) do={\
    \n    :do {\
    \n        /tool fetch url=https://YOURHTTPSERVER dst-path=blacklist\
    \n        :local content [/file get [/file find name=blacklist] contents] ;\
    \n        :local contentLen [ :len \$content ] ;\
    \n        :local lineEnd 0;\
    \n        :local line \"\";\
    \n        :local lastEnd 0;\
    \n        :do {\
    \n            :set lineEnd [:find \$content \"\\n\" \$lastEnd ] ;\
    \n            :set line [:pick \$content \$lastEnd \$lineEnd] ;\
    \n            :set lastEnd ( \$lineEnd + 1 ) ;\
    \n            :if ( [:pick \$line 0] != \"#\" ) do={\
    \n                :local entry [:pick \$line 0 (\$lineEnd -1) ]\
    \n                :if ( [:len \$entry ] > 0 ) do={\
    \n                    /ip firewall address-list remove [find list=blacklist address=\$entry]\
    \n                    /ip firewall address-list add list=blacklist timeout=1d address=\$entry\
    \n                    :put \"Blocked \$entry\"\
    \n                    :log info \"Blocked \$entry\"\
    \n                }\
    \n            }\
    \n        } while (\$lastEnd < \$contentLen)\
    \n    } on-error={\
    \n        :put \"Error fetching blacklist\"\
    \n        :log error \"Error fetching blacklist\"\
    \n        :delay 3\
    \n    }\
    \n};"
:execute {/system script run block-address};