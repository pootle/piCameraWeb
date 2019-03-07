if ifconfig | grep -Fq "wlan0"; then
    if systemctl status wpaping.service 2>&1 | grep -Fq 'could not be found'; then 

        while true; do
            read -p  "Install wpaping (on raspbain lite stretch this stops wifi bouncing)?" yn
            case $yn in
                [Yy]* ) cp wpaping.service /lib/systemd/system;systemctl daemon-reload; systemctl enable wpaping.service; systemctl start wpaping.service;  break;;
                [Nn]* ) exit;;
                * ) echo "Please answer yes or no.";;
            esac
        done
    else
        echo "wpaping service already installed"
    fi
else
    echo "no wireless lan detected"
fi
