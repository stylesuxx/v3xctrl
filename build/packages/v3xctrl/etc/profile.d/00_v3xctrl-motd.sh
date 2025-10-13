#!/bin/bash
ENV_PATH="/run/v3xctrl.env"
source "${ENV_PATH}"

RED='\033[0;31m'
NC='\033[0m'
IP=$(ip -4 addr show wlan0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')

echo -e "\

                ${REB}.oooo.${NC}                             .            oooo
             ${REB}.BP\"\"YBBb${NC}                          .oB            \`BBB
 oooo    ooo       ${REB}]BP'${NC} oooo    ooo  .ooooo.  .oBBBoo oooo BBb  BBB
  \`BB.  .B'      ${REB}<3Bb.${NC}   \`BBb..BP'  BBB' \`\"YB   BBB   \`BBB\"\"BP  BBB
   \`BB..B'        ${REB}\`BBb.${NC}    YBBB'    BBB         BBB    BBB      BBB
    \`BBB'    ${REB}o.   .BBP${NC}   .oB\"'BBb   BBB   .oB   BBB .  BBB      BBB
     \`B'     ${REB}\`BbBBBP'${NC}   oBB'   BBBo \`YBboBBP'   \"BBB\" BBBBb    oBBBo

 Video eXchange and ConTRoL                         /vɛks kənˈtɹoʊl/

 Web Configurator:   http://${IP}:${network_ports_webinterface}
 Start video stream: sudo systemctl start v3xctrl-video
 Start control:      sudo systemctl start v3xctrl-control
 Mount Read/Write:   sudo v3xctrl-remount rw"