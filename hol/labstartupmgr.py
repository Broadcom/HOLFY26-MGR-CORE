#!/usr/bin/python3
# version 1.4 21-May 2024
import socket
import datetime
import os
import time
import subprocess
import requests
import zipfile
import shutil
import asyncio
import sys
sys.path.append('/home/holuser/hol')
sys.path.append('/usr/lib/python3/dist-packages:')
from pathlib import Path
import lsfunctions as lsf
from cryptography.fernet import Fernet
from xml.dom.minidom import parseString

locallog = '/tmp/labstartupmgr.log'
maincon = 'mainconsole'

proxies = {
    "http": "http://proxy:3128",
    "https": "http://proxy:3128"
}


def get_ovf_property(pname):
    """
        Return a dict of the requested OVF property in the ovfenv
        param pname: the name of the OVF property value to return
    """
    properties = {}
    xml_parts = lsf.getfilecontents(guestinfofile)
    raw_data = parseString(xml_parts)
    for prop in raw_data.getElementsByTagName('Property'):
        key, value = [prop.attributes['oe:key'].value,
                      prop.attributes['oe:value'].value]
        properties[key] = value
        if key == pname:
            return properties[key]


def write_output(content, **kwargs):
    """
    convenience function to add the current date time formatted per US convention
    :param content: the message to be printed
    **kwargs: logfile to use
    :return: no return
    """
    lfile = kwargs.get('logfile', locallog)
    now = datetime.datetime.now()
    nowfmt = now.strftime("%m/%d/%Y %H:%M:%S")
    out = f'{nowfmt} {content}'
    try:
        with open(lfile, "a") as lf:
            lf.write(f'{out}\n')
        lf.close()
    except Exception as e:
        write_output(f'Error: {e}')
        pass


def startup_status():
    global statusnic
    global ifconfig
    status = 'not ready'
    shutil.copyfile(f'{lsf.mcholroot}/startup_status.txt', '/tmp/startup_status.txt')
    with open('/tmp/startup_status.txt', 'r') as stat:
        contentlist = stat.readlines()
        content = ' '.join(contentlist)
        content = content.lower()
        if 'ready' in content and 'not ready' not in content:
            status = 'ready'
        elif 'fail' in content or 'timeout' in content:
            status = 'delete'
    stat.close()
    # check the statusnic to be sure - uss sshpass or go down the plink path?
    # checkipcmd = f'{ifconfig} {statusnic} | grep inet'
    return status


logpath = ''
msg = ''
vlpprepop = '/home/core/hol/vlpprepop.py'
# use the VLP Agent guestInfo file
guestinfofile = '/home/holuser/egwagent/guestinfo.ovfEnv'

# test if update.sh came down with the bundle
updatepath = '/home/core/update.sh'
if os.path.isfile(updatepath):
    res = lsf.run_command(f'/usr/bin/bash {updatepath}')

# ping loop until ready
while True:
    res = lsf.run_command(f'ping -c 4 {maincon}')
    if res.returncode == 0:
        write_output(f'Main Console is responsive now. mount is {lsf.mcholroot}', logfile=locallog)
        break
    time.sleep(3)
    write_output('Main Console is not reponding yet...', logfile=locallog)

logpath = f'{lsf.mcholroot}/labstartup.log'
# print(logpath)

# deployed by VLP (prod) or dev?
vlp_cloud = "NOT REPORTED"
ctr = 0

# need a counter here for 2 hours then delete ready or not
maxloops = 120  # number of 5-second loops in 10 minutes
while vlp_cloud == 'NOT REPORTED' or vlp_cloud is None:
    if os.path.isfile(guestinfofile):
        stats = os.stat(guestinfofile)
        if stats.st_size > 0:
            vlp_cloud = get_ovf_property('vlp_org_name')
            if vlp_cloud is None:
                vlp_cloud = 'NOT REPORTED'
            shutil.copy(guestinfofile, '/tmp/')
            write_output(f'vlp_cloud: {vlp_cloud}', logfile=locallog)
    elif ctr > maxloops:
        break
    else:
        write_output(f'vlp_cloud: {vlp_cloud} will try again...', logfile=locallog)
    time.sleep(5)
    ctr += 1

maxloops = 1440  # number of 5-second loops in 2 hours
isready = False
while True:
    podstatus = startup_status()
    if not isready:
        write_output(podstatus, logfile=locallog)
    if podstatus == 'ready' and not isready:  # only set explictly ready the first time
        if vlp_cloud == "NOT REPORTED" or vlp_cloud is None:
            lsf.write_output('Not attempting to set VLP prepop ready since not deployed by VLP...', logfile='labstartup.log')
            Path('/tmp/devdeploy').touch()
            exit(0)
        lsf.write_output('Attempting to set VLP ready...', logfile='labstartup.log')
        out = lsf.run_command(f'/usr/bin/python3 {vlpprepop} True >> {logpath}')
        write_output(out.stdout, logfile=locallog)
        write_output(podstatus, logfile=locallog)
    elif podstatus == 'delete':
        if vlp_cloud == "NOT REPORTED":
            lsf.write_output('Not attempting to remediate VLP prepop since not deployed by VLP...', logfile='labstartup.log')
            Path('/tmp/devdeploy').touch()
            exit(0)
        lsf.write_output('Attempting to remediate VLP prepop...', logfile='labstartup.log')
        out = lsf.run_command(f'/usr/bin/python3 {vlpprepop} delete >> {logpath}')
        write_output(out.stdout, logfile=locallog)
        write_output(podstatus, logfile=locallog)
    if os.path.isfile('/tmp/vlpdone'):
        isready = True
    else:
        isready = False
        # check the ctr here and delete if not ready
        if ctr > maxloops and podstatus != 'ready':
            lsf.write_output('Attempting to remediate VLP prepop after 2 hours...', logfile='labstartup.log')
            out = lsf.run_command(f'python3 {vlpprepop} delete >> {logpath}')
            write_output(out.stdout, logfile=locallog)
            write_output(podstatus, logfile=locallog)         
            exit(0)
    time.sleep(5)
    ctr += 1

