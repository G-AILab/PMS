#!/bin/bash

# 以下配置信息请自己修改
influxdb_user="root"
influxdb_password="root"
influxdb_host="localhost"
influxdb_port="8086"
backup_location_influxdb=/lab-pool/LabProjects/hdm/workspace/power_model_system/influxdb
expire_backup_delete="ON" #是否开启过期备份删除 ON为开启 OFF为关闭
expire_days=3 #过期时间天数 默认为三天，此项只有在expire_backup_delete开启时有效

# 本行开始以下不需要修改
backup_time=`date +%Y%m%d%H%M`  #定义备份详细时间
backup_Ymd=`date +%Y-%m-%d` #定义备份目录中的年月日时间
backup_3ago=`date -d '3 days ago' +%Y-%m-%d` #3天之前的日期

backup_dir_influxdb=$backup_location_influxdb/$backup_Ymd
influx -user $influxdb_user -password $influxdb_password #登陆influxdb
echo "database influxdb backup start..."
`influxd backup -portable $backup_dir_influxdb`#开始备份
`mkdir -p $backup_dir_influxdb
flag=`echo $?`
if [ $flag == "0" ];then #判断备份有没有成功
        echo "database influxdb success backup to $backup_dir_influxdb"
else
        echo "database indluxdb backup fail!"
        exit
fi

if [ "$expire_backup_delete" == "ON" -a  "$backup_location_influxdb" != "" ];then
    #`find $backup_location/ -type d -o -type f -ctime +$expire_days -exec rm -rf {} \;`
    `find $backup_location_influxdb/ -type d -mtime +$expire_days | xargs rm -rf`
    echo "Expired influxdb backup data delete complete!"
fi
echo "All database backup success! Thank you!"
exit

