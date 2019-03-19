KSQL_VERSION := $(shell awk '/version:/ {print $$2}' ksql-server/snap/snapcraft.yaml | head -1 | sed "s/'//g")

.PHONY: all
all: snap charm

.PHONY: schnapp
schnapp: snap fat-charm

.PHONY: snap
snap: ksql-server/ksql-server_$(KSQL_VERSION)_amd64.snap

ksql-server/ksql-server_$(KSQL_VERSION)_amd64.snap:
	(cd ksql-server; SNAPCRAFT_BUILD_ENVIRONMENT_MEMORY=6G snapcraft)

.PHONY: charm
charm: charm/builds/ksql

.PHONY: fat-charm
fat-charm: ksql-server/ksql-server_$(KSQL_VERSION)_amd64.snap ./charm/builds/ksql
	cp -rf $< charm/ksql
	$(MAKE) -C charm/ksql

charm/builds/ksql:
	$(MAKE) -C charm/ksql

.PHONY: clean
clean: clean-charm clean-snap

.PHONY: clean-charm
clean-charm:
	$(RM) -r charm/builds charm/deps
	$(RM) charm/ksql/*.snap

.PHONY: clean-snap
clean-snap:
	(cd ksql-server; snapcraft clean)
	
sysdeps: /snap/bin/charm /snap/bin/snapcraft
/snap/bin/charm:
	sudo snap install charm --classic
/snap/bin/snapcraft:
	sudo snap install snapcraft --classic
