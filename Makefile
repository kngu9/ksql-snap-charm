KSQL_VERSION := $(shell awk '/version:/ {print $$2}' ksql-server/snap/snapcraft.yaml | head -1 | sed "s/'//g")

.PHONY: all
all: snap lint charm

.PHONY: lint
lint:
	flake8 --ignore=E121,E123,E126,E226,E24,E704,E265 charm/ksql

.PHONY: snap
snap: ksql-server/ksql-server_$(KSQL_VERSION)_amd64.snap

ksql-server/ksql-server_$(KSQL_VERSION)_amd64.snap:
	(cd ksql-server; SNAPCRAFT_BUILD_ENVIRONMENT_MEMORY=6G snapcraft)

.PHONY: charm
charm: charm/builds/ksql

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
	$(RM) ksql-server/ksql-server_$(KSQL_VERSION)_amd64.snap
	
sysdeps: /snap/bin/charm /snap/bin/snapcraft
/snap/bin/charm:
	sudo snap install charm --classic
/snap/bin/snapcraft:
	sudo snap install snapcraft --classic
