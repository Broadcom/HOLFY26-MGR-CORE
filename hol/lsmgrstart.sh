#! /bin/sh
# version 1.4.3 - 28-February 2025

runlabstartupmgr() {
   # we only want one labstartupmgr.py running
   lsprocs=`ps -ef | grep labstartupmgr.py | grep -v grep`
   if [ "$lsprocs" = "" ];then
     echo "Starting ${holroot}/labstartupmgr.py" >> ${logfile}
     # -u unbuffered output
     python3 -u ${holroot}/labstartupmgr.py >> ${logfile} 2>&1 &
  fi
}


# because we're running as a cron job, source the environment variables
. /home/core/.bashrc

holroot=/home/core/hol
lmcholroot=/lmchol/hol
wmcholroot=/wmchol/hol
configini=/tmp/config.ini
logfile='/tmp/labstartupmgr.log'
vmtoolsd=/usr/sbin/vmtoolsd

# the list of tenants using VM Script for ER
ertenants='HOL:hol-test:' # case counts

$vmtoolsd --cmd 'info-get guestinfo.ovfEnv' > /tmp/guestinfo.ovfEnv 2>&1
tmptenant=`grep vlp_vapp_tenant_name /tmp/guestinfo.ovfEnv | awk '{print $3}' | cut -d'=' -f2 | sed s/\"//g`

[ -z "$tmptenant" ] && echo "Non-production deployment. Exiting..." >> ${logfile} && exit

# production deployment. Is Agent ER configured in the tenant?
vlptenant=`echo $tmptenant | sed 's/.$//' | sed 's/.$//'`  # remove the final "/>"

# pause until mount is present
while true;do
   if [ -d ${lmcholroot} ];then
      echo "LMC detected." >> ${logfile}
      #runit=`grep 2535 ${lmcholroot}/vPod.txt` # if 2535 use VLP Agent ER
      break
   elif [ -d ${wmcholroot} ];then    
      echo "WMC detected." >> ${logfile}
      #runit=`grep 2501 ${wmcholroot}/vPod.txt` # debug only run for 2501
      echo "Starting..." > ${wmcholroot}/startup_status.tx
      break
   fi
   echo "Waiting for Main Console mount to complete..." >> ${logfile}
   sleep 5
done

agent_er=`echo ${ertenants} | grep $vlptenant`
if [ "$agent_er" ];then
   echo "Agent ER is configured in the ${vlptenant} tenant. Not using VLP API. Exit." >> ${logfile}  
   #[ "$runit" ] && exit
   exit
elif [ ! -z "$runit" ];then
   echo "Agent ER is configured in the ${vlptenant} tenant. Not using VLP API. Exit." >> ${logfile}  
   exit
else
   echo "Agent ER is NOT configured in the ${vlptenant} tenant. Will use VLP API." >> ${logfile}
fi

runlabstartupmgr

echo "$0 finished." >> ${logfile}

