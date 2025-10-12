#!/bin/bash
ENV_PATH="/run/v3xctrl.env"
source "${ENV_PATH}"

RED='\033[0;31m'
NC='\033[0m'
IP=$(ip -4 addr show wlan0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')

echo -e "\

                ${RED}.oooo.${NC}                             .            oooo
             ${RED}.dP\"\"YDDb${NC}                          .oD            \`DDD
 oooo    ooo       ${RED}]DP'${NC} oooo    ooo  .ooooo.  .oDDDoo oooo dDb  DDD
  \`DD.  .D'      ${RED}<3Db.${NC}   \`DDb..DP'  dDD' \`\"YD   DDD   \`DDD\"\"DP  DDD
   \`DD..D'        ${RED}\`DDb.${NC}    YDDD'    DDD         DDD    DDD      DDD
    \`DDD'    ${RED}o.   .DDP${NC}   .oD\"'DDb   DDD   .oD   DDD .  DDD      DDD
     \`D'     ${RED}\`DbdDDP'${NC}   oDD'   DDDo \`YDbodDP'   \"DDD\" dDDDb    oDDDo

 Video eXchange and ConTRoL                         /vɛks kənˈtɹoʊl/

 Web Configurator:   http://${IP}:${network_ports_webinterface}
 Start video stream: sudo systemctl start v3xctrl-video
 Start control:      sudo systemctl start v3xctrl-control
 Mount Read/Write:   sudo v3xctrl-remount rw"