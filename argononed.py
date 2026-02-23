#!/usr/bin/python3

#
# This script set fan speed and monitor power button events.
#
# Fan Speed is set by sending 0 to 100 to the MCU (Micro Controller Unit)
# The values will be interpreted as the percentage of fan speed, 100% being maximum
#
# Power button events are sent as a pulse signal to BCM Pin 4 (BOARD P7)
# A pulse width of 20-30ms indicates reboot request (double-tap)
# A pulse width of 40-50ms indicates shutdown request (hold and release after 3 secs)
#
# Standard Deployment/Triggers:
#  * Raspbian, OSMC: Runs as service via /lib/systemd/system/argononed.service
#  * lakka, libreelec: Runs as service via /storage/.config/system.d/argononed.service
#  * recalbox: Runs as service via /etc/init.d/
#

import sys
import os
import time
from threading import Thread
from queue import Queue

sys.path.append("/etc/argon/")
from argonsysinfo import *
from argonregister import *
from argonpowerbutton import *

# Initialize I2C Bus
bus = argonregister_initializebusobj()

OLED_ENABLED=False

if os.path.exists("/etc/argon/argoneonoled.py"):
	import datetime
	from argoneonoled import *
	OLED_ENABLED=True

OLED_CONFIGFILE   = "/etc/argoneonoled.conf"
UNIT_CONFIGFILE   = "/etc/argonunits.conf"
PIHOLE_CONFIGFILE = "/etc/argonpihole.conf"

SHUTDOWN_FLAGFILE = "/dev/shm/argonshutdownflag.txt"

def get_fanspeed(tempval, configlist):
	for curconfig in configlist:
		curpair = curconfig.split("=")
		tempcfg = float(curpair[0])
		fancfg = int(float(curpair[1]))
		if tempval >= tempcfg:
			if fancfg < 1:
				return 0
			elif fancfg < 25:
				return 25
			return fancfg
	return 0

def load_config(fname):
	newconfig = []
	try:
		with open(fname, "r") as fp:
			for curline in fp:
				if not curline:
					continue
				tmpline = curline.strip()
				if not tmpline:
					continue
				if tmpline[0] == "#":
					continue
				tmppair = tmpline.split("=")
				if len(tmppair) != 2:
					continue
				tempval = 0
				fanval = 0
				try:
					tempval = float(tmppair[0])
					if tempval < 0 or tempval > 100:
						continue
				except:
					continue
				try:
					fanval = int(float(tmppair[1]))
					if fanval < 0 or fanval > 100:
						continue
				except:
					continue
				newconfig.append( "{:5.1f}={}".format(tempval,fanval))
		if len(newconfig) > 0:
			newconfig.sort(reverse=True)
	except:
		return []
	return newconfig

def load_oledconfig(fname):
	output={}
	try:
		with open(fname, "r") as fp:
			for curline in fp:
				if not curline:
					continue
				tmpline = curline.strip()
				if not tmpline:
					continue
				if tmpline[0] == "#":
					continue
				tmppair = tmpline.split("=")
				if len(tmppair) != 2:
					continue
				if tmppair[0] == "switchduration":
					output['screenduration']=int(tmppair[1])
				elif tmppair[0] == "screensaver":
					output['screensaver']=int(tmppair[1])
				elif tmppair[0] == "screenlist":
					output['screenlist']=tmppair[1].replace("\"", "").split(" ")
				elif tmppair[0] == "enabled":
					output['enabled']=tmppair[1].replace("\"", "")
	except:
		return {}
	return output

def load_unitconfig(fname):
	output={"temperature": "C"}
	try:
		with open(fname, "r") as fp:
			for curline in fp:
				if not curline:
					continue
				tmpline = curline.strip()
				if not tmpline:
					continue
				if tmpline[0] == "#":
					continue
				tmppair = tmpline.split("=")
				if len(tmppair) != 2:
					continue
				if tmppair[0] == "temperature":
					output['temperature']=tmppair[1].replace("\"", "")
	except:
		return {}
	return output

def load_piholeconfig(fname):
	output = {}
	try:
		with open(fname, "r") as fp:
			for curline in fp:
				if not curline:
					continue
				tmpline = curline.strip()
				if not tmpline:
					continue
				if tmpline[0] == "#":
					continue
				tmppair = tmpline.split("=", 1)
				if len(tmppair) != 2:
					continue
				if tmppair[0] == "password":
					output["password"] = tmppair[1].strip().replace('"', '')
	except:
		return {}
	return output

def load_fancpuconfig():
	fanconfig = ["65=100", "60=55", "55=30"]
	tmpconfig = load_config("/etc/argononed.conf")
	if len(tmpconfig) > 0:
		fanconfig = tmpconfig
	return fanconfig

def load_fanhddconfig():
	fanhddconfig = ["50=100", "40=55", "30=30"]
	fanhddconfigfile = "/etc/argononed-hdd.conf"
	if os.path.isfile(fanhddconfigfile):
		tmpconfig = load_config(fanhddconfigfile)
		if len(tmpconfig) > 0:
			fanhddconfig = tmpconfig
	else:
		fanhddconfig = []
	return fanhddconfig

def temp_check():
	INITIALSPEEDVAL = 200
	argonregsupport = argonregister_checksupport(bus)
	fanconfig = load_fancpuconfig()
	fanhddconfig = load_fanhddconfig()
	prevspeed = INITIALSPEEDVAL
	while True:
		val = argonsysinfo_getcputemp()
		newspeed = get_fanspeed(val, fanconfig)
		val = argonsysinfo_getmaxhddtemp()
		tmpspeed = get_fanspeed(val, fanhddconfig)
		if tmpspeed > newspeed:
			newspeed = tmpspeed
		if prevspeed == newspeed:
			time.sleep(30)
			continue
		elif newspeed < prevspeed and prevspeed != INITIALSPEEDVAL:
			time.sleep(30)
		prevspeed = newspeed
		try:
			if newspeed > 0:
				argonregister_setfanspeed(bus, 100, argonregsupport)
			argonregister_setfanspeed(bus, newspeed, argonregsupport)
			time.sleep(30)
		except IOError:
			time.sleep(60)


def display_loop(readq):

	oledscreenwidth = oled_getmaxX()
	fontwdSml = 6   # 6x8  font
	fontwdReg = 8   # 8x16 font

	# Load Pi-hole password
	pihole_password = ""
	tmpconfig = load_piholeconfig(PIHOLE_CONFIGFILE)
	if "password" in tmpconfig:
		pihole_password = tmpconfig["password"]

	# Screen IDs
	SCREEN_LOGO   = 0
	SCREEN_MAIN   = 1
	SCREEN_BAQ    = 2
	SCREEN_HEALTH = 3
	SCREEN_CMD    = 4
	SCREEN_X      = 5

	screenid    = SCREEN_MAIN
	refresh_sec = 30

	# Create one session at startup; reuse it every fetch cycle
	api_url = argonsysinfo_getpihole_apiurl()
	sid = argonsysinfo_getpihole_sid(api_url, pihole_password)

	def ensure_session():
		nonlocal sid
		if not sid:
			sid = argonsysinfo_getpihole_sid(api_url, pihole_password)
		return sid is not None

	def fetch_pihole():
		"""Fetch only Pi-hole stats. Returns dict with Pi-hole keys."""
		nonlocal sid
		if not ensure_session():
			return {}
		data = argonsysinfo_getpaddinfo(api_url, sid)
		if data.get("status") == "401":
			sid = None
			if ensure_session():
				data = argonsysinfo_getpaddinfo(api_url, sid)
		if data.get("status") == "ok":
			return data
		return {}

	def fetch_sysinfo():
		"""Fetch system stats independently of Pi-hole. Always returns valid values."""
		info = {}

		# CPU
		try:
			cpu_list = argonsysinfo_listcpuusage(1)
			vals = [c["value"] for c in cpu_list if isinstance(c["value"], int)]
			info["cpu_pct"] = str(int(sum(vals) / len(vals))) if vals else "0"
		except:
			info["cpu_pct"] = "N/A"

		# RAM
		try:
			ram = argonsysinfo_getram()
			info["ram_pct"]   = ram[0]
			info["ram_total"] = ram[1]
		except:
			info["ram_pct"]   = "N/A"
			info["ram_total"] = "N/A"

		# Disk
		try:
			hdd = argonsysinfo_listhddusage()
			total_used  = sum(hdd[d]["used"]  for d in hdd)
			total_space = sum(hdd[d]["total"] for d in hdd)
			if total_space > 0:
				info["disk_used"]  = argonsysinfo_kbstr(total_used)
				info["disk_total"] = argonsysinfo_kbstr(total_space)
			else:
				info["disk_used"]  = "N/A"
				info["disk_total"] = "N/A"
		except:
			info["disk_used"]  = "N/A"
			info["disk_total"] = "N/A"

		# CPU temp
		try:
			temp_val = argonsysinfo_getcputemp()
			info["cpu_temp"] = "{:.1f}".format(temp_val)
		except:
			info["cpu_temp"] = "N/A"

		# IP
		try:
			info["ip"] = argonsysinfo_getip()
		except:
			info["ip"] = "N/A"

		return info

	def get_screen_list(pihole):
		if pihole.get("blocking", "") == "disabled":
			return [SCREEN_LOGO, SCREEN_MAIN, SCREEN_BAQ, SCREEN_HEALTH, SCREEN_CMD, SCREEN_X]
		return [SCREEN_LOGO, SCREEN_MAIN, SCREEN_BAQ, SCREEN_HEALTH, SCREEN_CMD]

	def draw_screen(screen, pihole, sysinfo):
		# oled_loadbg initialises the display buffer correctly.
		# bgblank.bin is a 128x64 all-black image in /etc/argon/oled/
		oled_loadbg("bgblank")

		# Y-coordinates MUST be strict multiples of 8 (0,8,16,24,32,40,48,56)
		# The 8x16 font occupies 2 rows, so use y and y+8 for its space.
		# Never exceed y=56 for small font or y=48 for large font.

		if screen == SCREEN_LOGO:
			# -------------------------------------------------------
			# Screen 0: Pi-hole logo
			# -------------------------------------------------------
			oled_loadbg("piholelogo")

		elif screen == SCREEN_MAIN:
			# -------------------------------------------------------
			# Screen 1: PI-HOLE STATUS
			# y= 0  "PI-HOLE STATUS"   small font
			# y= 8  (blank)
			# y=16  "14.3%"            large font (2 rows: 16-32)
			# y=32  clients             small font
			# y=40  "BLOCKED"          small font
			# y=48  "8900 / 116000"    small font
			# y=56  gravity list size   small font
			# -------------------------------------------------------
			pct     = pihole.get("percent_blocked", "N/A")
			count   = pihole.get("queries_blocked", "N/A")
			total   = pihole.get("queries_total",   "N/A")
			clients = pihole.get("clients",         "N/A")

			oled_writetextaligned("Pi-Hole Status",        0,  0, oledscreenwidth, 1, fontwdSml)
			oled_writetextaligned(pct + "% Blocked",        0, 16, oledscreenwidth, 1, fontwdReg)
			oled_writetextaligned(clients + " clients",     0, 40, oledscreenwidth, 1, fontwdSml)
			oled_writetextaligned("Blocked / Queries",      0, 48, oledscreenwidth, 1, fontwdSml)
			oled_writetextaligned(count + " / " + total,    0, 56, oledscreenwidth, 1, fontwdSml)

		elif screen == SCREEN_BAQ:
			# -------------------------------------------------------
			# Screen 2: Pi-Hole Stats
			# y= 0  title
			# y= 8  (blank)
			# y=16  Blk List: (gravity size)
			# y=24  Top:
			# y=32  C: top client
			# y=40  A: top allowed domain
			# y=48  B: top blocked domain
			# -------------------------------------------------------
			gravity     = pihole.get("gravity_display", "N/A")
			top_client  = pihole.get("top_client",      "N/A")
			top_domain  = pihole.get("top_domain",      "N/A")
			top_blocked = pihole.get("top_blocked",     "N/A")

			# 21 chars per line at 6px font, label is 3 chars leaving 18
			def trunc(s, maxlen=18):
				return s if len(s) <= maxlen else s[:maxlen-2] + ".."

			oled_writetextaligned("Pi-Hole Data",            0,  0, oledscreenwidth, 1, fontwdSml)
			oled_writetextaligned("Gravity: " + gravity,     0, 16, oledscreenwidth, 1, fontwdSml)
			oled_writetextaligned("Top:",                    0, 32, oledscreenwidth, 1, fontwdSml)
			oled_writetextaligned("C: " + trunc(top_client), 0, 40, oledscreenwidth, 1, fontwdSml)
			oled_writetextaligned("A: " + trunc(top_domain), 0, 48, oledscreenwidth, 1, fontwdSml)
			oled_writetextaligned("B: " + trunc(top_blocked),0, 56, oledscreenwidth, 1, fontwdSml)

		elif screen == SCREEN_CMD:
			# -------------------------------------------------------
			# Screen 3: System Data
			# y= 0  title
			# y= 8  (blank gap)
			# y=16  IP
			# y=24  CPU %
			# y=32  Temp
			# y=40  RAM %
			# y=48  Disk used/total
			# -------------------------------------------------------
			ip         = sysinfo.get("ip",        "N/A")
			cpu        = sysinfo.get("cpu_pct",   "N/A")
			temp       = sysinfo.get("cpu_temp",  "N/A")
			ram_pct    = sysinfo.get("ram_pct",   "N/A")
			disk_used  = sysinfo.get("disk_used",  "N/A")
			disk_total = sysinfo.get("disk_total", "N/A")

			oled_writetextaligned("System Data",                                   0,  0, oledscreenwidth, 1, fontwdSml)
			oled_writetextaligned("IP:   " + ip,                                   0, 16, oledscreenwidth, 1, fontwdSml)
			oled_writetextaligned("CPU:  " + str(cpu) + "%",                       0, 24, oledscreenwidth, 1, fontwdSml)
			oled_writetextaligned("Temp: " + str(round(float(temp) * 9/5 + 32, 1)) + "F" if temp != "N/A" else "Temp: N/A",                      0, 32, oledscreenwidth, 1, fontwdSml)
			oled_writetextaligned("RAM:  " + ram_pct,                              0, 40, oledscreenwidth, 1, fontwdSml)
			oled_writetextaligned("Disk: " + disk_used + "/" + disk_total,         0, 48, oledscreenwidth, 1, fontwdSml)

		elif screen == SCREEN_HEALTH:
			# -------------------------------------------------------
			# Screen 4: Pi-hole Health
			# y= 0  title
			# y= 8  (blank)
			# y=16  Core version
			# y=24  FTL version
			# y=32  Web version
			# y=40  (blank)
			# y=48  Node name
			# y=56  DNS domain
			# -------------------------------------------------------
			ph_ver    = pihole.get("version_core", "N/A")
			ftl_ver   = pihole.get("version_ftl",  "N/A")
			web_ver   = pihole.get("version_web",  "N/A")
			node_name = pihole.get("node_name",    "N/A")
			domain    = pihole.get("dns_domain",   "N/A")

			oled_writetextaligned("Pi-Hole Health",             0,  0, oledscreenwidth, 1, fontwdSml)
			oled_writetextaligned("Core: " + ph_ver,            0, 16, oledscreenwidth, 1, fontwdSml)
			oled_writetextaligned("FTL:  " + ftl_ver,           0, 24, oledscreenwidth, 1, fontwdSml)
			oled_writetextaligned("Web:  " + web_ver,           0, 32, oledscreenwidth, 1, fontwdSml)
			oled_writetextaligned("Node: " + node_name,         0, 48, oledscreenwidth, 1, fontwdSml)
			oled_writetextaligned("Domain: " + domain,            0, 56, oledscreenwidth, 1, fontwdSml)

		elif screen == SCREEN_X:
			# -------------------------------------------------------
			# Screen 6: X - Pi-hole disabled warning
			# y= 0  "!! WARNING !!"   small font
			# y=16  "PI-HOLE"         large font (2 rows: 16-32)
			# y=32  "DISABLED"        large font (2 rows: 32-48)
			# y=56  "Blocking is OFF" small font
			# -------------------------------------------------------
			oled_writetextaligned("!! WARNING !!",   0,  0, oledscreenwidth, 1, fontwdSml)
			oled_writetextaligned("PI-HOLE",         0, 16, oledscreenwidth, 1, fontwdReg)
			oled_writetextaligned("DISABLED",        0, 32, oledscreenwidth, 1, fontwdReg)
			oled_writetextaligned("Blocking is OFF", 0, 56, oledscreenwidth, 1, fontwdSml)

	# -----------------------------------------------------------------------
	# Initial data fetch
	# -----------------------------------------------------------------------
	pihole  = fetch_pihole()
	sysinfo = fetch_sysinfo()
	screens = get_screen_list(pihole)

	if screenid >= len(screens):
		screenid = 0

	# Quiet hours: display off between 22:00 and 06:00
	QUIET_START = 22
	QUIET_END   = 6

	def is_quiet_hours():
		hour = datetime.datetime.now().hour
		if QUIET_START > QUIET_END:
			# Spans midnight e.g. 22:00 -> 06:00
			return hour >= QUIET_START or hour < QUIET_END
		return QUIET_START <= hour < QUIET_END

	# Track whether display is currently on
	display_on = not is_quiet_hours()
	if not display_on:
		oled_power(False)

	while True:
		# Shutdown check
		try:
			if os.path.isfile(SHUTDOWN_FLAGFILE):
				if sid:
					argonsysinfo_delete_pihole_sid(api_url, sid)
				oled_fill(0)
				oled_reset()
				return
		except:
			pass

		# Draw only if display is on
		if display_on:
			try:
				draw_screen(screens[screenid], pihole, sysinfo)
				oled_power(True)
				oled_flushimage(True)
				oled_reset()
			except:
				pass

		# Wait, checking queue each second
		advanced = False
		for i in range(refresh_sec):
			time.sleep(1)
			if not readq.empty():
				qdata = readq.get()
				if qdata == "OLEDSWITCH":
					screenid = (screenid + 1) % len(screens)
					readq.task_done()
					advanced = True
					# Button press always wakes display for one cycle
					if not display_on:
						display_on = True
					break
				elif qdata == "OLEDSTOP":
					if sid:
						argonsysinfo_delete_pihole_sid(api_url, sid)
					oled_fill(0)
					oled_reset()
					readq.task_done()
					return
				else:
					readq.task_done()

		# Always advance screen and refresh data regardless of display state
		if not advanced:
			screenid = (screenid + 1) % len(screens)
			try:
				pihole  = fetch_pihole()
				sysinfo = fetch_sysinfo()
				screens = get_screen_list(pihole)
				if screenid >= len(screens):
					screenid = 0
			except:
				pass

		# If blocking is disabled, jump to warning screen and stay there
		if pihole.get("blocking", "") == "disabled":
			screenid = screens.index(SCREEN_X) if SCREEN_X in screens else screenid
			advanced = False  # prevent skip on next cycle

		# After each cycle, check whether display should be on or off
		in_quiet = is_quiet_hours()
		if in_quiet and display_on and not advanced:
			# Quiet hours just started or button-wake cycle ended - turn off
			display_on = False
			oled_power(False)
		elif not in_quiet and not display_on:
			# Quiet hours ended - turn back on
			# Also force display on if blocking is disabled (warning must show)
			display_on = True
		elif pihole.get("blocking", "") == "disabled" and not display_on:
			# Always show warning screen even during quiet hours
			display_on = True

	if sid:
		argonsysinfo_delete_pihole_sid(api_url, sid)
	oled_fill(0)
	oled_reset()


def display_defaultimg():
	oled_fill(0)
	oled_reset()

if len(sys.argv) > 1:
	cmd = sys.argv[1].upper()
	if cmd == "SHUTDOWN":
		try:
			with open(SHUTDOWN_FLAGFILE, "w") as f:
				f.write("signalled")
		except:
			pass
		argonregister_signalpoweroff(bus)
		if OLED_ENABLED == True:
			display_defaultimg()

	elif cmd == "FANOFF":
		argonregister_setfanspeed(bus, 0)
		if OLED_ENABLED == True:
			display_defaultimg()

	elif cmd == "SERVICE":
		try:
			ipcq = Queue()
			if len(sys.argv) > 2:
				cmd = sys.argv[2].upper()
			if cmd == "OLEDSWITCH":
				t1 = Thread(target = argonpowerbutton_monitorswitch, args =(ipcq, ))
			else:
				t1 = Thread(target = argonpowerbutton_monitor, args =(ipcq, ))

			t2 = Thread(target = temp_check)
			if OLED_ENABLED == True:
				t3 = Thread(target = display_loop, args =(ipcq, ))

			t1.start()
			t2.start()
			if OLED_ENABLED == True:
				t3.start()

			ipcq.join()
		except Exception:
			sys.exit(1)
