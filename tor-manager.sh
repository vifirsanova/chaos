#!/bin/bash

if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

systemctl unmask tor
systemctl enable tor
systemctl restart tor
systemctl restart postgresql
(.venv/bin/python3 run.py) &
journalctl -u tor -f
