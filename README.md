# MyTVCalendar-PlexSync

# Install pip requests
pip install -r requirements.txt

# Set your Plex server URL
PLEX_URL = "http://1.2.3.4:32400"

# Run the bridge
python3 mytvcalendar_bridge.py

# Complete the steps 
- Link to Plex
- Link to MyTVCalendar.com
- Enjoy!

# Run as a service
- Windows
  - Create a batch file called run_bridge.bat with the following in
  ```
   python C:\Scripts\MyTVCalendar\mytvcalendar_bridge.py
   ```
  - Open Windows Task Scheduler
  - Create a new task to trigger on startup
  - Set the action to start a program and select your .bat file
  - Ensure you check run whether user is logged on or not.

- Linux
  - Create a service file at /etc/systemd/system/mytvcalendar.service
  ```
     [Unit]
     Description=MyTVCalendar Plex Bridge Daemon
     After=network.target
     
     [Service]
     Type=simple
     User=yourusername
     WorkingDirectory=/opt/mytvcalendar #change path to match where your python file is
     ExecStart=/usr/bin/python3 /opt/mytvcalendar/mytvcalendar_bridge.py
     Restart=on-failure
     
     [Install]
     WantedBy=multi-user.target
  ```
  - Run the following commands to start the service and enable it at boot
  ```
  sudo systemctl daemon-reload
  sudo systemctl enable mytvcalendar.service
  sudo systemctl start mytvcalendar.service