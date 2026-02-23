#!/usr/bin/python3

#
# Misc methods to retrieve system information.
#

import os
import time
import socket
import json

try:
	import urllib.request
	import urllib.error
	URLLIB_AVAILABLE = True
except:
	URLLIB_AVAILABLE = False

def argonsysinfo_listcpuusage(sleepsec = 1):
	outputlist = []
	curusage_a = argonsysinfo_getcpuusagesnapshot()
	time.sleep(sleepsec)
	curusage_b = argonsysinfo_getcpuusagesnapshot()

	for cpuname in curusage_a:
		if cpuname == "cpu":
			continue
		if curusage_a[cpuname]["total"] == curusage_b[cpuname]["total"]:
			outputlist.append({"title": cpuname, "value": "0%"})
		else:
			total = curusage_b[cpuname]["total"]-curusage_a[cpuname]["total"]
			idle = curusage_b[cpuname]["idle"]-curusage_a[cpuname]["idle"]
			outputlist.append({"title": cpuname, "value": int(100*(total-idle)/(total))})
	return outputlist

def argonsysinfo_getcpuusagesnapshot():
	cpupercent = {}
	errorflag = False
	try:
		cpuctr = 0
		tempfp = open("/proc/stat", "r")
		alllines = tempfp.readlines()
		for temp in alllines:
			temp = temp.replace('\t', ' ')
			temp = temp.strip()
			while temp.find("  ") >= 0:
				temp = temp.replace("  ", " ")
			if len(temp) < 3:
				cpuctr = cpuctr +1
				continue

			checkname = temp[0:3]
			if checkname == "cpu":
				infolist = temp.split(" ")
				idle = 0
				total = 0
				colctr = 1
				while colctr < len(infolist):
					curval = int(infolist[colctr])
					if colctr == 4 or colctr == 5:
						idle = idle + curval
					total = total + curval
					colctr = colctr + 1
				if total > 0:
					cpupercent[infolist[0]] = {"total": total, "idle": idle}
			cpuctr = cpuctr +1

		tempfp.close()
	except IOError:
		errorflag = True
	return cpupercent


def argonsysinfo_liststoragetotal():
	outputlist = []
	ramtotal = 0
	errorflag = False

	try:
		hddctr = 0
		tempfp = open("/proc/partitions", "r")
		alllines = tempfp.readlines()

		for temp in alllines:
			temp = temp.replace('\t', ' ')
			temp = temp.strip()
			while temp.find("  ") >= 0:
				temp = temp.replace("  ", " ")
			infolist = temp.split(" ")
			if len(infolist) >= 4:
				if infolist[3] != "name":
					parttype = infolist[3][0:3]
					if parttype == "ram":
						ramtotal = ramtotal + int(infolist[2])
					elif parttype[0:2] == "sd" or parttype[0:2] == "hd":
						lastchar = infolist[3][-1]
						if lastchar.isdigit() == False:
							outputlist.append({"title": infolist[3], "value": argonsysinfo_kbstr(int(infolist[2]))})
					else:
						lastchar = infolist[3][-2]
						if lastchar[0] != "p":
							outputlist.append({"title": infolist[3], "value": argonsysinfo_kbstr(int(infolist[2]))})

		tempfp.close()
	except IOError:
		errorflag = True
	return outputlist

def argonsysinfo_getram():
	totalram = 0
	totalfree = 0
	tempfp = open("/proc/meminfo", "r")
	alllines = tempfp.readlines()

	for temp in alllines:
		temp = temp.replace('\t', ' ')
		temp = temp.strip()
		while temp.find("  ") >= 0:
			temp = temp.replace("  ", " ")
		infolist = temp.split(" ")
		if len(infolist) >= 2:
			if infolist[0] == "MemTotal:":
				totalram = int(infolist[1])
			elif infolist[0] == "MemFree:":
				totalfree = totalfree + int(infolist[1])
			elif infolist[0] == "Buffers:":
				totalfree = totalfree + int(infolist[1])
			elif infolist[0] == "Cached:":
				totalfree = totalfree + int(infolist[1])
	if totalram == 0:
		return "0%"
	return [str(int(100*totalfree/totalram))+"%", str((totalram+512*1024)>>20)+"GB"]

def argonsysinfo_getcputemp():
	try:
		tempfp = open("/sys/class/thermal/thermal_zone0/temp", "r")
		temp = tempfp.readline()
		tempfp.close()
		return float(int(temp)/1000)
	except IOError:
		return 0


def argonsysinfo_getmaxhddtemp():
	maxtempval = 0
	try:
		hddtempobj = argonsysinfo_gethddtemp()
		for curdev in hddtempobj:
			if hddtempobj[curdev] > maxtempval:
				maxtempval = hddtempobj[curdev]
		return maxtempval
	except:
		return maxtempval

def argonsysinfo_gethddtemp():
	hddtempcmd = "/usr/sbin/smartctl"
	if os.path.exists(hddtempcmd) == False:
		hddtempcmd = "/usr/sbin/hddtemp"

	outputobj = {}
	if os.path.exists(hddtempcmd):
		try:
			tmp = os.popen("lsblk | grep -e '0 disk' | awk '{print $1}'").read()
			alllines = tmp.split("\n")
			for curdev in alllines:
				if curdev[0:2] == "sd" or curdev[0:2] == "hd":
					tempval = argonsysinfo_getdevhddtemp(hddtempcmd,curdev)
					if tempval > 0:
						outputobj[curdev] = tempval
			return outputobj
		except:
			return outputobj
	return outputobj

def argonsysinfo_getdevhddtemp(hddtempcmd, curdev):
	cmdstr = ""
	if hddtempcmd == "/usr/sbin/hddtemp":
		cmdstr = "/usr/sbin/hddtemp -n sata:/dev/"+curdev
	elif hddtempcmd == "/usr/sbin/smartctl":
		cmdstr = "/usr/sbin/smartctl -d sat -A /dev/"+curdev+" | grep Temperature_Celsius | awk '{print $10}'"

	tempval = 0
	if len(cmdstr) > 0:
		try:
			temperaturestr = os.popen(cmdstr+" 2>&1").read()
			tempval = float(temperaturestr)
		except:
			tempval = -1

	return tempval

def argonsysinfo_getip():
	ipaddr = ""
	st = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	try:
		st.connect(('254.255.255.255', 1))
		ipaddr = st.getsockname()[0]
	except Exception:
		ipaddr = 'N/A'
	finally:
		st.close()
	return ipaddr


def argonsysinfo_getrootdev():
	tmp = os.popen('mount').read()
	alllines = tmp.split("\n")

	for temp in alllines:
		temp = temp.replace('\t', ' ')
		temp = temp.strip()
		while temp.find("  ") >= 0:
			temp = temp.replace("  ", " ")
		infolist = temp.split(" ")
		if len(infolist) >= 3:
			if infolist[2] == "/":
				return infolist[0]
	return ""

def argonsysinfo_listhddusage():
	outputobj = {}
	raidlist = argonsysinfo_listraid()
	raiddevlist = []
	raidctr = 0
	while raidctr < len(raidlist['raidlist']):
		raiddevlist.append(raidlist['raidlist'][raidctr]['title'])
		raidctr = raidctr + 1

	rootdev = argonsysinfo_getrootdev()

	tmp = os.popen('df').read()
	alllines = tmp.split("\n")

	for temp in alllines:
		temp = temp.replace('\t', ' ')
		temp = temp.strip()
		while temp.find("  ") >= 0:
			temp = temp.replace("  ", " ")
		infolist = temp.split(" ")
		if len(infolist) >= 6:
			if infolist[1] == "Size":
				continue
			if len(infolist[0]) < 5:
				continue
			elif infolist[0][0:5] != "/dev/":
				continue
			curdev = infolist[0]
			if curdev == "/dev/root" and rootdev != "":
				curdev = rootdev
			tmpidx = curdev.rfind("/")
			if tmpidx >= 0:
				curdev = curdev[tmpidx+1:]

			if curdev in raidlist['hddlist']:
				continue
			elif curdev in raiddevlist:
				if curdev in outputobj:
					continue
			elif curdev[0:2] == "sd" or curdev[0:2] == "hd":
				curdev = curdev[0:-1]
			else:
				curdev = curdev[0:-2]

			if curdev in outputobj:
				outputobj[curdev] = {"used":outputobj[curdev]['used']+int(infolist[2]), "total":outputobj[curdev]['total']+int(infolist[1])}
			else:
				outputobj[curdev] = {"used":int(infolist[2]), "total":int(infolist[1])}

	return outputobj

def argonsysinfo_kbstr(kbval, wholenumbers = True):
	remainder = 0
	suffixidx = 0
	suffixlist = ["KB", "MB", "GB", "TB"]
	while kbval > 1023 and suffixidx < len(suffixlist):
		remainder = kbval & 1023
		kbval  = kbval >> 10
		suffixidx = suffixidx + 1

	remainderstr = ""
	if kbval < 100 and wholenumbers == False:
		remainder = int((remainder+50)/100)
		if remainder > 0:
			remainderstr = "."+str(remainder)
	elif remainder >= 500:
		kbval = kbval + 1
	return str(kbval)+remainderstr + suffixlist[suffixidx]

def argonsysinfo_listraid():
	hddlist = []
	outputlist = []

	ramtotal = 0
	errorflag = False
	try:
		hddctr = 0
		tempfp = open("/proc/mdstat", "r")
		alllines = tempfp.readlines()
		for temp in alllines:
			temp = temp.replace('\t', ' ')
			temp = temp.strip()
			while temp.find("  ") >= 0:
				temp = temp.replace("  ", " ")
			infolist = temp.split(" ")
			if len(infolist) >= 4:
				if infolist[0] != "Personalities" and infolist[1] == ":":
					devname = infolist[0]
					raidtype = infolist[3]
					hddctr = 4
					while hddctr < len(infolist):
						tmpdevname = infolist[hddctr]
						tmpidx = tmpdevname.find("[")
						if tmpidx >= 0:
							tmpdevname = tmpdevname[0:tmpidx]
						hddlist.append(tmpdevname)
						hddctr = hddctr + 1
					devdetail = argonsysinfo_getraiddetail(devname)
					outputlist.append({"title": devname, "value": raidtype, "info": devdetail})

		tempfp.close()
	except IOError:
		errorflag = True

	return {"raidlist": outputlist, "hddlist": hddlist}


def argonsysinfo_getraiddetail(devname):
	state = ""
	raidtype = ""
	size = 0
	used = 0
	total = 0
	working = 0
	active = 0
	failed = 0
	spare = 0
	rebuildstat = ""
	tmp = os.popen('mdadm -D /dev/'+devname).read()
	alllines = tmp.split("\n")

	for temp in alllines:
		temp = temp.replace('\t', ' ')
		temp = temp.strip()
		while temp.find("  ") >= 0:
			temp = temp.replace("  ", " ")
		infolist = temp.split(" : ")
		if len(infolist) == 2:
			if infolist[0].lower() == "raid level":
				raidtype = infolist[1]
			elif infolist[0].lower() == "array size":
				tmpidx = infolist[1].find(" ")
				if tmpidx > 0:
					size = (infolist[1][0:tmpidx])
			elif infolist[0].lower() == "used dev size":
				tmpidx = infolist[1].find(" ")
				if tmpidx > 0:
					used = (infolist[1][0:tmpidx])
			elif infolist[0].lower() == "state":
				tmpidx = infolist[1].rfind(" ")
				if tmpidx > 0:
					state = (infolist[1][tmpidx+1:])
				else:
					state = infolist[1]
			elif infolist[0].lower() == "total devices":
				total = infolist[1]
			elif infolist[0].lower() == "active devices":
				active = infolist[1]
			elif infolist[0].lower() == "working devices":
				working = infolist[1]
			elif infolist[0].lower() == "failed devices":
				failed = infolist[1]
			elif infolist[0].lower() == "spare devices":
				spare = infolist[1]
			elif infolist[0].lower() == "rebuild status":
				tmpidx = infolist[1].find("%")
				if tmpidx > 0:
					rebuildstat = (infolist[1][0:tmpidx])+"%"
	return {"state": state, "raidtype": raidtype, "size": int(size), "used": int(used), "devices": int(total), "active": int(active), "working": int(working), "failed": int(failed), "spare": int(spare), "rebuildstat": rebuildstat}


# =============================================================================
# Pi-hole API functions
# Modelled on the same approach as github.com/RPiSpy/pi-hole-screen
# Uses urllib (Python standard library) instead of curl subprocess calls.
# =============================================================================

def argonsysinfo_getpihole_apiurl():
	"""Discover the Pi-hole FTL API URL via CHAOS DNS query."""
	try:
		result = os.popen(
			"dig +short chaos txt local.api.ftl @localhost 2>/dev/null"
		).read().strip()
		if result:
			parts = result.split('"')
			if len(parts) >= 2:
				first_url = parts[1].strip()
				if first_url:
					if not first_url.endswith("/"):
						first_url += "/"
					return first_url
	except:
		pass
	return "http://127.0.0.1:80/api/"


def argonsysinfo_pihole_request(url, sid=None, method="GET", payload=None):
	"""
	Make an HTTP request to the Pi-hole API using urllib.
	Returns parsed JSON as a dict, or None on failure.
	Handles HTTP error responses gracefully by reading the error body.
	"""
	try:
		data = None
		if payload is not None:
			data = json.dumps(payload).encode("utf-8")

		req = urllib.request.Request(url, data=data, method=method)
		req.add_header("Content-Type", "application/json")
		req.add_header("Accept", "application/json")
		if sid:
			req.add_header("sid", sid)

		try:
			with urllib.request.urlopen(req, timeout=5) as response:
				return json.loads(response.read().decode("utf-8"))
		except urllib.error.HTTPError as e:
			# Read the error body - Pi-hole returns useful JSON even on errors
			try:
				body = e.read().decode("utf-8")
				return json.loads(body)
			except:
				return None
	except:
		return None


def argonsysinfo_getpihole_sid(api_url, password):
	"""Authenticate and return a session ID, or None on failure."""
	try:
		data = argonsysinfo_pihole_request(
			api_url + "auth",
			method="POST",
			payload={"password": password, "totp": None}
		)
		if data:
			session = data.get("session", {})
			if session.get("valid"):
				return session.get("sid")
	except:
		pass
	return None


def argonsysinfo_delete_pihole_sid(api_url, sid):
	"""Delete a Pi-hole session."""
	try:
		argonsysinfo_pihole_request(
			api_url + "auth",
			sid=sid,
			method="DELETE"
		)
	except:
		pass


def argonsysinfo_getpaddinfo(api_url, sid):
	"""
	Query Pi-hole /padd endpoint which returns all stats in one call.
	Returns a dict of display-ready strings.
	Returns status="401" if the session has expired.
	"""
	result = {
		"status":          "error",
		"blocking":        "N/A",
		"queries_total":   "N/A",
		"queries_blocked": "N/A",
		"percent_blocked": "N/A",
		"gravity_size":    "N/A",
		"gravity_display": "N/A",
		"clients":         "N/A",
	}

	try:
		data = argonsysinfo_pihole_request(api_url + "padd", sid=sid)

		if data is None:
			result["status"] = "401"
			return result

		if "error" in data:
			result["status"] = "401"
			return result

		result["blocking"] = str(data.get("blocking", "N/A"))

		queries = data.get("queries", {})
		total   = queries.get("total", 0)
		blocked = queries.get("blocked", 0)
		pct     = queries.get("percent_blocked", 0)
		result["queries_total"]   = str(int(total))
		result["queries_blocked"] = str(int(blocked))
		result["percent_blocked"] = "{:.1f}".format(float(pct))

		grav_raw = data.get("gravity_size", 0)
		result["gravity_size"] = str(int(grav_raw))
		grav = int(grav_raw)
		if grav >= 1000000:
			result["gravity_display"] = "{:.1f}M".format(grav / 1000000)
		elif grav >= 1000:
			result["gravity_display"] = "{:.0f}k".format(grav / 1000)
		else:
			result["gravity_display"] = str(grav)

		result["clients"]    = str(data.get("active_clients", "N/A"))
		result["top_client"] = str(data.get("top_client",   None) or "N/A")
		result["top_domain"] = str(data.get("top_domain",   None) or "N/A")
		result["top_blocked"]= str(data.get("top_blocked",  None) or "N/A")
		result["node_name"]  = str(data.get("node_name",    None) or "N/A")

		# Cache stats: size, inserted, evicted, hit rate
		try:
			cache = data.get("cache", {})
			c_size    = int(cache.get("size",     0))
			c_insert  = int(cache.get("inserted", 0))
			c_evicted = int(cache.get("evicted",  0))
			result["cache_size"]    = str(c_size)
			result["cache_inserted"]= str(c_insert)
			result["cache_evicted"] = str(c_evicted)
			if c_size > 0:
				result["cache_hit_pct"] = "{:.1f}".format(100 * c_insert / c_size)
			else:
				result["cache_hit_pct"] = "0.0"
		except:
			result["cache_size"]    = "N/A"
			result["cache_inserted"]= "N/A"
			result["cache_evicted"] = "N/A"
			result["cache_hit_pct"] = "N/A"

		# DNS config
		try:
			config = data.get("config", {})
			result["dns_upstreams"] = str(config.get("dns_num_upstreams", "N/A"))
			result["dns_domain"]    = str(config.get("dns_domain", "N/A"))
		except:
			result["dns_upstreams"] = "N/A"
			result["dns_domain"]    = "N/A"

		# Version info - correct key names from actual API response
		try:
			version = data.get("version", {})
			result["version_core"] = str(version.get("core", {}).get("local", {}).get("version", "N/A"))
			result["version_ftl"]  = str(version.get("ftl",  {}).get("local", {}).get("version", "N/A"))
			result["version_web"]  = str(version.get("web",  {}).get("local", {}).get("version", "N/A"))
		except:
			result["version_core"] = "N/A"
			result["version_ftl"]  = "N/A"
			result["version_web"]  = "N/A"

		result["status"] = "ok"

	except:
		pass

	return result
