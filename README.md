# Pi-Hole-Data-on-Argon-ONE-V5-OLED-Display
Modified scripts to show Pi-Hole data on an Argon ONE V5 case equipped with the optional OLED display.

I'm not great at creating github repositories, but I will give it a go. Here are the steps you need to follow to have your Argon ONE V5 OLED screen display pi-hole data.

Step 1: Download and install the original Argon OLED control script by executing the following command:

curl https://download.argon40.com/argon1v5.sh | bash

Step 2: After the installation move bgblank.bin and piholelogo.bin to the folder /etc/argon/oled

Step 3: Edit the file argonpihole.conf and enter the password to your pi-hole where it says "your_pihole_password_here"

Step 4: Move argonpihole.conf to the /etc folder

Step 5: Move the included argononed.py and argonsysinfo.py to the /etc/argon folder.  This will overwrite the existing files with these names in the folder.

Final notes: Using this script makes the Argon Congifuration tool useless as the onfiguration tool can no longer modify the OLED screen.

Features:

The screen will cycle through several pages, one every 30 seconds.

Screen 1: Pi-Hole Logo
Screen 2: Pi-Hole Status (% blocked, # clients, # blocked, # queries)
Screen 3: Pi_hole Data (gravity list size, top client, top allowed domain, top blocked domain)
Screen 4: Pi-Hole Health (Core Version, FLT Version, Web Client Version, Node Name, Domain)
Screen 5: System Data (IP, CPU Usage, Temp, RAM Usage, Disk Usage)
Screen 6: Ad Blocking Disabled (Only shows if ad blocking is disabled.  This screen will stay on until ad blocking is re-enabled)

You can also press the button to cylce through the pages manually.

There is also a sleep timer built in.  The OLED will turn off at 10pm and turn on again at 6am.  You can press the button to manually turn on the screen for 30 seconds during sleep time.  The screen will stay on if ad blocking is turned off.

You can also adjust the sleep time hours by modifying the following lines in argononed.py:

  # Quiet hours: display off between 22:00 and 06:00
	QUIET_START = 22
	QUIET_END   = 6
