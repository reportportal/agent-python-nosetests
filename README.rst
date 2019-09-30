===================
agent-python-nose
===================


Nose plugin for reporting test results of Nose to the 'Reportal Portal'.

* Usage
* Configuration
* Examples
* Launching
* Send attachement (screenshots)
* Troubleshooting
* Copyright Notice

Usage
-----

Installation
~~~~~~~~~~~~

To install nose plugin execute next command in a terminal:

.. code-block:: bash

    pip install nose-reportportal


Configuration
~~~~~~~~~~~~~

Prepare the config file :code:`rp.ini` in root directory of tests

The :code:`rp.ini` file should have next mandatory fields:

- :code:`rp_uuid` - value could be found in the User Profile section
- :code:`rp_project` - name of project in Report Potal
- :code:`rp_endpoint` - address of Report Portal Server
- :code:`rp_launch` - name of a launch
- :code:`rp_launch_description` - description of a launch

Example of :code:`rp.ini`:

.. code-block:: text

    [base]
    rp_uuid = fb586627-32be-47dd-93c1-678873458a5f
    rp_endpoint = http://192.168.1.10:8080
    rp_project = user_personal
    rp_launch = AnyLaunchName {}
    rp_launch_tags = Nose;Smoke
    rp_launch_description = Smoke test

You need to add --rp-config-file to point to config file
- :code:`--rp-config-file rp.ini`
If you like to override some of parameters above from command line, or from CI environment based on your build, then pass
- :code:`--rp-launch` to change launch name.
- :code:`--rp-mode` to change mode of run report portal agent
- :code:`--rp-launch-description` to change description of a launch

Launching
~~~~~~~~~

To run test with Report Portal you must provide '--with-reportportal' flag:

.. code-block:: bash

    nosetests --with-reportportal --rp-config-file rp.ini



Copyright Notice
----------------
..  Copyright Notice:  https://github.com/reportportal/agent-python-pytest#copyright-notice

Licensed under the GPLv3_ license (see the LICENSE file).

.. _GPLv3:  https://www.gnu.org/licenses/quick-guide-gplv3.html

