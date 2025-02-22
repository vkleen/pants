# Copyright 2018 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources()

python_test_utils(name="test_utils")

python_tests(
    name="tests",
    overrides={
        "coverage_py_test.py": {"timeout": 20},
        "coverage_py_integration_test.py": {
            "tags": ["platform_specific_behavior"],
            "timeout": 480,
        },
        "export_integration_test.py": {"timeout": 300},
        "lockfile_test.py": {"timeout": 120},
        "package_pex_binary_integration_test.py": {
            "dependencies": [":platforms"],
            "timeout": 120,
        },
        "pytest_runner_integration_test.py": {
            "tags": ["platform_specific_behavior"],
            "timeout": 600,
        },
        "repl_integration_test.py": {
            "tags": ["platform_specific_behavior"],
            "timeout": 300,
        },
        "run_pex_binary_integration_test.py": {"timeout": 600},
        "run_python_source_integration_test.py": {"timeout": 180},
        "setup_py_integration_test.py": {
            "dependencies": ["testprojects/src/python:native_directory"],
            "tags": ["platform_specific_behavior"],
            "timeout": 180,
        },
        "setup_py_test.py": {"timeout": 150},
    },
)

resources(name="platforms", sources=["platform*.json"])
