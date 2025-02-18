#! /bin/sh
# version 1.1 - 11-October 2024

# the only job of this script is to do the initial git pull for the core account

# because we're running as a cron job, source the environment variables
. /home/core/.bashrc

# initialize the logfile
logfile='/tmp/labstartupmgr.log'
> ${logfile}

cd /home/core

internalgit=10.138.147.254
externalgit=holgitlab.oc.vmware.com

status=`ssh -o ConnectTimeout=5 -T git@$internalgit`
if [ $? != 0 ];then
   repodir='/root/.git'
   cat /home/core/.git/config | sed s/$internalgit/$externalgit/g > /home/core/.git/newconfig
   mv /home/core/.git/config /home/core/.git/oldconfig
   mv /home/core/.git/newconfig /home/core/.git/config
   chmod 664 /home/core/.git/config
fi

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

