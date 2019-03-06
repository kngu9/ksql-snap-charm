#!/bin/bash
                               
set -eu

mkdir -p $SNAP_DATA/etc $SNAP_DATA/log

if [ ! -f $SNAP_DATA/etc/ksql-server.properties ]; then
    cp $SNAP/etc/ksql/*.properties $SNAP_DATA/etc
fi

export KSQL_LOG4J_OPTS="-Dlog4j.configuration=file:$SNAP_DATA/etc/log4j.properties"
export LOG_DIR=$SNAP_DATA/log
export PATH=$SNAP/usr/lib/jvm/default-java/bin:$PATH
unset JAVA_HOME                

$SNAP/usr/bin/ksql-server-start $SNAP_DATA/etc/ksql-server.properties
