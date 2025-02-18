#!/usr/bin/python3
version = '1.20 23-January 2025'
import sys
import os
import configparser
import subprocess
import datetime
import json
import socket
import shutil
import time
import requests
import zipfile
import json
sys.path.append('/home/holuser/hol')
import lsfunctions as lsf
from pathlib import Path
from requests.auth import HTTPBasicAuth
from cryptography.fernet import Fernet
from xml.dom.minidom import parseString  # pyCharm complains about this but it works.

while not os.path.isfile("/tmp/config.ini"):
    print('Waiting for /tmp/config.ini...')
    time.sleep(5)

holconfig = configparser.ConfigParser()
holconfig.read('/tmp/config.ini')
if 'labtype' in holconfig['VPOD'].keys():
    labtype = holconfig.get('VPOD', 'labtype')

# print(f'labtype: {labtype}')

if labtype == "HOL":
    proxies = {
        "http": "http://proxy:3128",
        "https": "http://proxy:3128"   
    }
else:
    proxies = {
        "http": "",
        "https": ""   
    }


def get_ovf_property(pname):
    """
        Return a dict of the requested OVF property in the ovfenv
        param pname: the name of the OVF property value to return
    """
    properties = {}
    xml_parts = lsf.getfilecontents('/home/holuser/egwagent/guestinfo.ovfEnv')
    raw_data = parseString(xml_parts)
    for prop in raw_data.getElementsByTagName('Property'):
        key, value = [prop.attributes['oe:key'].value,
                      prop.attributes['oe:value'].value]
        properties[key] = value
        if key == pname:
            return properties[key]


def get_prepop_id():    
    global vlp_token
    global vlp_urn
    headers = {"Cookie": f'nee-token={vlp_token}'}
    resp = ''
    
    vlp_url = f'{vlp_api}/admin/Vapp?tenant={vlp_tenant}&urn={vlp_urn}'
    resp = requests.get(vlp_url, headers=headers, proxies=proxies)
    if resp.status_code == 200:
        begin = resp.text.find('Prepop')
        prepop_id = resp.text[begin+6:begin+13]
        return prepop_id
    else:
        print(resp.status_code)
        return 0


def verify_er():    
    global vlp_token
    global vlp_urn
    global ovdc
    headers = {"Cookie": f'nee-token={vlp_token}'}
    resp = ''
    id = get_prepop_id()
    if id != 0:
        vlp_url = f'{vlp_api}/admin/cloudVapps/{id}'
        resp = requests.get(vlp_url, headers=headers, proxies=proxies)
        # need to get the ovdc in desktop here
        vlpjson = json.loads(resp.text)
        ovdc = vlpjson['data']['cloudOrgVdc']['name']
        # print(ovdc)
        if resp.text.find('"prepopExplicitlyReady": true,'):
            return True
        else:
            return False
    else:
        return False


def get_vlp_config():
    encryptedfile = '/home/core/secret.config.ini'
    configfile = '/home/core/coreconfig.ini'
    # open the key
    with open('/home/core/filekey.key', 'rb') as filekey:
        key = filekey.read()   
    # decrypt using the key
    fernet = Fernet(key)
    # open the encrypted file
    with open(encryptedfile, 'rb') as enc_file:
        encrypted = enc_file.read()
    decrypted = fernet.decrypt(encrypted)
    with open(configfile, 'w') as confile:
        confile.write(decrypted.decode('utf-8'))
    confile.close()
    with open(configfile, 'r') as conf:
        configini = conf.read()
    conf.close()
    return configini


def vlp_login():
    global vlp_token
    vlp_url = f'{vlp_api}/login'
    user_name = f'{vlp_user}@{vlp_tenant}'
    # print(f'{user_name} {vlp_pass}')
    response = requests.post(vlp_url, auth=HTTPBasicAuth(user_name, vlp_pass), proxies=proxies)
    if response.status_code == 200:
        resjson = json.loads(response.text)
        vlp_token = resjson['data']['nee-token']
        lsf.write_output(f'Successful log in to {vlp_tenant}', logfile=logfile)
        return True
    else:
        lsf.write_output(f'Could not log in to VLP as {user_name}', logfile=logfile)
        lsf.write_output(response.text, logfile=logfile)
        Path('/tmp/vlpdone').touch()
        return False


def vlp_set_ready(state):
    global vlp_token
    global vlp_urn
    global max_loops
    response = ''
    ready_ctr = 0
    if vlp_tenant == 'NOT REPORTED':
        lsf.write_output(f'vlp_tenant is {vlp_tenant}. Not setting explicitly ready.', logfile=logfile)
        Path('/tmp/vlpdone').touch()
        return
    while True:
        if vlp_login():
            headers = {"Cookie": f'nee-token={vlp_token}'}
            vlp_url = f'{vlp_api}/pool/ready?urn={vlp_urn}&ready={state}'
            try:
                response = requests.post(vlp_url, headers=headers, proxies=proxies)
                if response.status_code == 404:
                    lsf.write_output('Cannot find this prepop.', logfile=logfile)
                    vlp_logout()
                    Path('/tmp/vlpdone').touch()
                    break
                if response.status_code == 200:
                    if verify_er():
                        msg = f'Verified explicitly ready to be {state} for this prepop on {ovdc} in VLP tenant {vlp_tenant}.'
                        lsf.write_output(msg, logfile=logfile)           
                        vlp_logout()
                        Path('/tmp/vlpdone').touch()
                        break
                    else:
                        lsf.write_output(f'Could not set explicitly ready {response.text}', logfile=logfile)
                else:
                    lsf.write_output(f'Could not set explicitly ready {response.text}', logfile=logfile)
            except BaseException as e:
                lsf.write_output(f'{e} Could not set explicitly ready {response.text}', logfile=logfile)
        else:
            if ready_ctr == max_loops:
                Path('/tmp/vlpdone').touch()
                lsf.write_output('Time out setting expliictly ready. Abort!', logfile=logfile)
                exit(2)
            lsf.write_output('Could not set explicitly ready. Will try again...', logfile=logfile)
            time.sleep(5)
            ready_ctr = ready_ctr + 1


def vlp_logout():
    global vlp_token
    vlp_url = f'{vlp_api}/logout'
    headers = {"Cookie": f'nee-token={vlp_token}'}
    response = requests.post(vlp_url, headers=headers, proxies=proxies)
    if response.status_code == 200:
        lsf.write_output(f'Successful log out of {vlp_tenant}', logfile=logfile)
        return True
    else:
        lsf.write_output(f'Could not log out of {vlp_tenant}', logfile=logfile)
        return False


def vlp_delete_endpoint():
    global vlp_token
    global vlp_urn
    global max_loops
    response = ''
    delete_ctr = 0
    if vlp_urn == 'NOT REPORTED':
        lsf.write_output('This is not a VLP prepop. Cannot remediate.', logfile=logfile)
        exit(0)
    while True:
        if vlp_login():
            headers = {"Cookie": f'nee-token={vlp_token}'}
            vlp_url = f'{vlp_api}/pool/undeploy?urn={vlp_urn}&sendNotification=true&severity=3'
            try:
                response = requests.post(vlp_url, headers=headers, proxies=proxies)
                if response.status_code == 200:
                    lsf.write_output('Remediating this prepop.', logfile=logfile)
                else:
                    lsf.write_output(f'Could not remediate failed prepop. {response.text}', logfile=logfile)
            except BaseException as e:
                lsf.write_output(f'{e} Could not remediate failed prepop {response.text}', logfile=logfile)
            vlp_logout()
            Path('/tmp/vlpdone').touch()
            break
        else:
            if delete_ctr == max_loops:
                Path('/tmp/vlpdone').touch()
                lsf.write_output('Time out remediating failed prepop. Abort!', logfile=logfile)
                exit(2)
            lsf.write_output('Could not remediate failed prepop but will try again...', logfile=logfile)
        delete_ctr = delete_ctr + 1
        time.sleep(5)

vlp_token = ''
ovdc = ''
vlp_tenant = get_ovf_property('vlp_vapp_tenant_name')
if not vlp_tenant:
    vlp_tenant = 'NOT REPORTED'
vlp_urn = get_ovf_property('vlp_vapp_urn')
if not vlp_urn:
    vlp_urn = 'NOT REPORTED'

# debug
#vlp_tenant = 'HOL'
#vlp_urn = 'urn:vcloud:vapp:42adabab-7370-41e7-94dc-43f491eba5ee'

vlpconfig = get_vlp_config()
config = configparser.ConfigParser()
config.read_string(vlpconfig)
vlp_user = config.get("VLP", 'vlp_user')
vlp_pass = config.get("VLP", 'vlp_pass')
vlp_api = config.get("VLP", 'vlp_api')
# print(f'{vlp_user} {vlp_pass} {vlp_api}')

# set the timeout
max_minutes = 10
max_seconds = max_minutes * 60
sleep_seconds = 5
max_loops = max_seconds / sleep_seconds

logfile = 'labstartup.log'

lsf.write_output(f'vlpprepop.py version {version}', logfile=logfile)

if len(sys.argv) > 1:
    if sys.argv[1] == 'delete':
        vlp_delete_endpoint()
    else:
        vlp_set_ready(sys.argv[1])

