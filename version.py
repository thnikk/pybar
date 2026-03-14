#!/usr/bin/python3 -u
"""
Description: Version string resolution
Author: thnikk
"""
import os
from subprocess import run, CalledProcessError, PIPE


def get_version():
    """ Return the app version string.

    Priority:
    1. VERSION file written by CI at build time
    2. git describe for dev runs
    3. 'unknown' as a last resort
    """
    # Check for a VERSION file baked in by CI
    version_file = os.path.join(os.path.dirname(__file__), 'VERSION')
    if os.path.exists(version_file):
        try:
            with open(version_file, 'r') as f:
                v = f.read().strip()
            if v:
                return v
        except OSError:
            pass

    # Fall back to git describe for dev runs
    try:
        result = run(
            ['git', 'describe', '--tags', '--always'],
            stdout=PIPE, stderr=PIPE, check=True
        )
        return result.stdout.decode().strip()
    except (CalledProcessError, FileNotFoundError):
        pass

    return 'unknown'
