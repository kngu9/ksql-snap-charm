#!/bin/bash
                               
set -eu

mkdir -p $SNAP_USER_DATA/etc $SNAP_USER_DATA/log

if [ ! -f $SNAP_USER_DATA/etc/log4j.properties ]; then
    cp $SNAP/etc/ksql/log4j*.properties $SNAP_USER_DATA/etc
fi

export HOME=$SNAP_USER_DATA
export KSQL_LOG4J_OPTS="-Dlog4j.configuration=file:$SNAP_USER_DATA/etc/log4j.properties"
export LOG_DIR=$SNAP_USER_DATA/log
export PATH=$SNAP/usr/lib/jvm/default-java/bin:$PATH
unset JAVA_HOME                

$SNAP/usr/bin/ksql "$@"
