#!/bin/bash
ENV_PATH="/run/v3xctrl.env"
source "${ENV_PATH}"

RED='\033[0;31m'
NC='\033[0m'
IP=$(ip -4 addr show wlan0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')

echo -e "\

                ${RED}.oooo.${NC}                             .            oooo
             ${RED}.BP\"\"YBBb${NC}                          .oB            \`BBB
 oooo    ooo       ${RED}]BP'${NC} oooo    ooo  .ooooo.  .oBBBoo oooo BBb  BBB
  \`BB.  .B'      ${RED}<3Bb.${NC}   \`BBb..BP'  BBB' \`\"YB   BBB   \`BBB\"\"BP  BBB
   \`BB..B'        ${RED}\`BBb.${NC}    YBBB'    BBB         BBB    BBB      BBB
    \`BBB'    ${RED}o.   .BBP${NC}   .oB\"'BBb   BBB   .oB   BBB .  BBB      BBB
     \`B'     ${RED}\`BbBBBP'${NC}   oBB'   BBBo \`YBboBBP'   \"BBB\" BBBBb    oBBBo

 Video eXchange and ConTRoL                         /vɛks kənˈtɹoʊl/

 Web Configurator:   http://${IP}:${network_ports_webinterface}
 Start video stream: sudo systemctl start v3xctrl-video
 Start control:      sudo systemctl start v3xctrl-control"

if grep -q "overlayroot" /proc/mounts 2>/dev/null; then
  echo " Mount Read/Write:   sudo v3xctrl-remount rw"
  echo
  echo " =========================================="
  echo "          SYSTEM IN READ-ONLY MODE         "
  echo " =========================================="
  echo " Root filesystem is protected with overlay"
  echo " All changes are stored in RAM (tmpfs)"
  echo " Changes will be LOST on reboot/power cycle"
  echo " =========================================="
  echo
else
  echo " Mount Read-Only:    sudo v3xctrl-remount ro"
  echo
fi
