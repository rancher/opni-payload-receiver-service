SEVERITIES = HIGH,CRITICAL

ifeq ($(ARCH),)
ARCH=$(shell go env GOARCH)
endif

ORG ?= rancher
TAG ?= v0
REPO=opni-opensearch-fetcher
REPO-PAYLOAD=opni-payload-receiver-service

ifneq ($(DRONE_TAG),)
TAG := $(DRONE_TAG)
endif

.PHONY: image-build
image-build:
	git submodule update --init
	docker build \
		--pull \
		--build-arg PKG=$(PKG) \
		--build-arg SRC=$(SRC) \
		--build-arg TAG=$(TAG:$(BUILD_META)=) \
		--tag $(ORG)/$(REPO):$(TAG) \
		--tag $(ORG)/$(REPO):$(TAG)-$(ARCH) \
	.

.PHONY: image-build-payload
image-build-payload:
	docker build \
		--pull \
		--build-arg PKG=$(PKG) \
		--build-arg SRC=$(SRC) \
		--build-arg TAG=$(TAG:$(BUILD_META)=) \
		--tag $(ORG)/$(REPO-PAYLOAD):$(TAG) \
		--tag $(ORG)/$(REPO-PAYLOAD):$(TAG)-$(ARCH) \
	.

.PHONY: image-push
image-push:
	docker push $(ORG)/$(REPO):$(TAG)-$(ARCH)

.PHONY: image-push-payload
image-push:
	docker push $(ORG)/$(REPO-PAYLOAD):$(TAG)-$(ARCH)

.PHONY: image-manifest
image-manifest:
	DOCKER_CLI_EXPERIMENTAL=enabled docker manifest create --amend \
		$(ORG)/$(REPO):$(TAG) \
		$(ORG)/$(REPO):$(TAG)-$(ARCH)
	DOCKER_CLI_EXPERIMENTAL=enabled docker manifest push \
		$(ORG)/$(REPO):$(TAG)

.PHONY: image-manifest-payload
image-manifest-payload:
	DOCKER_CLI_EXPERIMENTAL=enabled docker manifest create --amend \
		$(ORG)/$(REPO-PAYLOAD):$(TAG) \
		$(ORG)/$(REPO-PAYLOAD):$(TAG)-$(ARCH)
	DOCKER_CLI_EXPERIMENTAL=enabled docker manifest push \
		$(ORG)/$(REPO-PAYLOAD):$(TAG)

.PHONY: image-scan
image-scan:
	trivy --severity $(SEVERITIES) --no-progress --ignore-unfixed $(ORG)/$(REPO):$(TAG)

.PHONY: image-scan-payload
image-scan-payload:
	trivy --severity $(SEVERITIES) --no-progress --ignore-unfixed $(ORG)/$(REPO-PAYLOAD):$(TAG)