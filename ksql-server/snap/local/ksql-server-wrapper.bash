#!/bin/bash
                               
set -eu

mkdir -p $SNAP_DATA/etc $SNAP_DATA/log $SNAP_DATA/kafka-streams

if [ ! -f $SNAP_DATA/etc/ksql-server.properties ]; then
	cat >$SNAP_DATA/etc/ksql-server.properties <<EOF
bootstrap.servers=localhost:9092
listeners=http://localhost:8088
state.dir=$SNAP_DATA/kafka-streams
EOF
fi
if [ ! -f $SNAP_DATA/etc/log4j.properties ]; then
	cp $SNAP/etc/ksql/log4j.properties $SNAP_DATA/etc
fi

export KSQL_LOG4J_OPTS="-Dlog4j.configuration=file:$SNAP_DATA/etc/log4j.properties"
export LOG_DIR=$SNAP_DATA/log
export PATH=$SNAP/usr/lib/jvm/default-java/bin:$PATH
unset JAVA_HOME

$SNAP/usr/bin/ksql-server-start $SNAP_DATA/etc/ksql-server.properties
