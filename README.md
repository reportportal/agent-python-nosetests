agent-python-nose
===================


Nose plugin for reporting test results of Nose to the 'Reportal Portal'.

* Usage
* Configuration
* Launching
* Copyright Notice
* Changes

# Usage

## Installation

To install nose plugin execute next command in a terminal:

```bash
  pip install nose-reportportal
```

# Configuration

Prepare the config file `rp.ini` in root directory of tests

The `rp.ini` file should have next mandatory fields:

`rp_uuid` - value could be found in the User Profile section
`rp_project` - name of project in Report Potal
`rp_endpoint` - address of Report Portal Server, can be found in a environment variable "RP_ENDPOINT" after tests' run
`rp_launch` - name of a launch
`rp_launch_description` - description of a launch

Example of `rp.ini`:

```text
[base]
rp_uuid = fb586627-32be-47dd-93c1-678873458a5f
rp_endpoint = http://192.168.1.10:8080
rp_project = user_personal
rp_launch = AnyLaunchName {}
rp_launch_tags = Nose;Smoke
rp_launch_description = Smoke test
```

You need to add --rp-config-file to point to config file:

```bash

--rp-config-file rp.ini

```

If you like to override some of parameters above from command line, or from CI environment based on your build, then pass

`--rp-launch`  to change launch name.

`--rp-mode` to change mode of run report portal agent

`--rp-launch-description` to change description of a launch

# Launching

To run test with Report Portal you must provide '--with-reportportal' flag:

```bash
nosetests --with-reportportal --rp-config-file rp.ini
```

# Copyright Notice

Copyright Notice:  https://github.com/reportportal/agent-python-nosetests#copyright-notice

Licensed under the Apache License Version 2.0, license (see the LICENSE file).

Apache License Version 2.0:  http://www.apache.org/licenses/LICENSE-2.0

# Changes

## Changes in version 0.0.3 

* a safe logs-sender  was added on a stop test phase  

## Changes in version 0.0.2 

* Added updated capturing for output and logs
* Added environment variable "RP_ENDPOINT" to exclude RP url from url-mockers if it is needed
