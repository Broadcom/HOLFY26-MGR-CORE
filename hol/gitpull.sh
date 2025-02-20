#! /bin/sh
# version 1.1 - 11-October 2024

# the only job of this script is to do the initial git pull for the core account

# because we're running as a cron job, source the environment variables
. /home/core/.bashrc

# initialize the logfile
logfile='/tmp/labstartupmgr.log'
> ${logfile}

cd /home/core

proxyready=`nmap -p 3128 proxy | grep open`
while [ $? != 0 ];do
   echo "Waiting for proxy to be ready..." >> ${logfile}
   proxyready=`nmap -p 3128 proxy | grep open`
   sleep 1
done

ctr=0
while true;do
   if [ $ctr -gt 30 ];then
      echo "FATAL could not perform git pull." >> ${logfile}
      exit  # do we exit here or just report?
   fi
   git pull origin master >> ${logfile} 2>&1
   if [ $? = 0 ];then
      > /tmp/ERcoregitdone
      break
   else
      gitresult=`grep 'could not be found' ${logfile}`
      if [ $? = 0 ];then
         echo "The git project ${gitproject} does not exist." >> ${logfile}
         echo "FAIL - No GIT Project" > $startupstatus
         exit 1
      else
         echo "Could not complete git pull. Will try again." >> ${logfile}
      fi
  fi
  ctr=`expr $ctr + 1`
  sleep 5
done

