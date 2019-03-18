#!/bin/bash
                               
set -eu

mkdir -p $SNAP_COMMON/etc $SNAP_COMMON/log $SNAP_COMMON/kafka-streams

if [ ! -f $SNAP_COMMON/etc/ksql-server.properties ]; then
	cat >$SNAP_COMMON/etc/ksql-server.properties <<EOF
bootstrap.servers=localhost:9092
listeners=http://localhost:8088
state.dir=$SNAP_COMMON/kafka-streams
EOF
fi
if [ ! -f $SNAP_COMMON/etc/log4j.properties ]; then
	cp $SNAP/etc/ksql/log4j.properties $SNAP_COMMON/etc
fi

export KSQL_LOG4J_OPTS="-Dlog4j.configuration=file:$SNAP_COMMON/etc/log4j.properties"
export LOG_DIR=$SNAP_COMMON/log
export PATH=$SNAP/usr/lib/jvm/default-java/bin:$PATH
unset JAVA_HOME

$SNAP/usr/bin/ksql-server-start $SNAP_COMMON/etc/ksql-server.properties
