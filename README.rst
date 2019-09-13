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

Example of :code:`rp.ini`:

.. code-block:: text

    [base]
    rp_uuid = fb586627-32be-47dd-93c1-678873458a5f
    rp_endpoint = http://192.168.1.10:8080
    rp_project = user_personal
    rp_launch = AnyLaunchName {}
    rp_launch_tags = Nose;Smoke
    rp_launch_description = Smoke test

If you like to override the above parameters from command line, or from CI environment based on your build, then pass
- :code:`--rp-launch "(unit tests)"` during invocation.

Launching
~~~~~~~~~

To run test with Report Portal you must provide '--with-reportportal' flag:

.. code-block:: bash

    tox --with-reportportal


Copyright Notice
----------------
..  Copyright Notice:  https://github.com/reportportal/agent-python-pytest#copyright-notice

Licensed under the GPLv3_ license (see the LICENSE file).

.. _GPLv3:  https://www.gnu.org/licenses/quick-guide-gplv3.html

