#!/bin/bash
ENV_PATH="/run/v3xctrl.env"
source "${ENV_PATH}"

RED='\033[0;31m'
NC='\033[0m'
IP=$(ip -4 addr show wlan0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')

echo -e "\

                ${RED}.oooo.${NC}                             .            oooo
             ${RED}.dP\"\"Y88b${NC}                          .o8            \`888
 oooo    ooo       ${RED}]8P'${NC} oooo    ooo  .ooooo.  .o888oo oooo d8b  888
  \`88.  .8'      ${RED}<38b.${NC}   \`88b..8P'  d88' \`\"Y8   888   \`888\"\"8P  888
   \`88..8'        ${RED}\`88b.${NC}    Y888'    888         888    888      888
    \`888'    ${RED}o.   .88P${NC}   .o8\"'88b   888   .o8   888 .  888      888
     \`8'     ${RED}\`8bd88P'${NC}   o88'   888o \`Y8bod8P'   \"888\" d888b    o888o

 Video eXchange and ConTRoL                         /vɛks kənˈtɹoʊl/

 Web Configurator:   http://${IP}:${ports_webinterface}
 Start video stream: sudo systemctl start v3xctrl-video
 Start control:      sudo systemctl start v3xctrl-control
 Mount Read/Write:   sudo v3xctrl-remount rw"
