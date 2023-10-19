# Copyright 2023
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

""" Fixing Helm Chart based on Kube-linter results
"""

from typing import Callable
import json
import fix_template
import kics_fix_chart


def iterate_checks(chart_folder: str, json_path: str) -> None:
    """Parses JSON data and iterates "query_id" keys.

    Args:
        chart_folder (str): The name of the chart to fix.
        json_path (str): The path to the JSON file to parse.
    """

    # Load the JSON file
    with open(json_path, 'r', encoding="utf-8") as file:
        results = json.load(file)

    template = fix_template.parse_yaml_template(chart_folder)

    # List of all checks
    all_checks = []

    if "Reports" in results:
        print("Starting to fix chart's issues ...\n")

        if "Reports" not in results or results["Reports"] is None or not results["Reports"]:
            pass

        else:
            for check in results["Reports"]:
                print(f"{check['Check']}: {check['Diagnostic']['Message']}")
                check_id = fix_issue(check, template)
                all_checks.append(check_id)

    print("\nAll issues fixed!\n")

    # Print all found checks
    all_checks = [str(x) for x in all_checks if x is not None]
    all_checks = ", ".join(all_checks)
    all_checks = all_checks.split(", ")
    all_checks.sort()

    # Print info
    print(f"Total number of checks: {len(all_checks)}")
    print(", ".join(all_checks))
    # For check_ from 0 to 66 (i.e., check_0, check_1, ..., check_66), print the
    # # occurrences of each check in all_checks, all in one line
    # for i in range(0, 67):
    #     print(f"{all_checks.count(f'check_{i}')}", end=" ")

    name = f"fixed_{chart_folder}_kubelinter_fixed"
    fix_template.save_yaml_template(template, name)


def get_container_path(template: dict, resource_path: str, cont_name: str) -> str:
    """Returns the path to the container in the template.
    
    Args:
        template (dict): The parsed YAML template.
        resource_path (str): The path to the resource in the template.
        cont_name (str): The name of the container.
    
    Returns:
        str: The path to the container in the template.
    """

    cont_path = ""
    for document in template:
        aux_path = ""

        if fix_template.check_resource_path(resource_path.split("/"), document):
            document = document["spec"]
            cont_path += "spec/"

            if "template" in document:
                document = document["template"]["spec"]
                cont_path += "template/spec/"
            elif "jobTemplate" in document:
                document = document["jobTemplate"]["spec"]["template"]["spec"]
                cont_path += "jobTemplate/spec/template/spec/"

            for idx, container in enumerate(document["containers"]):
                if container["name"] == cont_name:
                    aux_path = "containers/" + str(idx)
                    break

            if not aux_path and "initContainers" in document:
                for idx, container in enumerate(document["initContainers"]):
                    if container["name"] == cont_name:
                        aux_path = "initContainers/" + str(idx)
                        break

        if aux_path:
            cont_path += aux_path
            break

    return cont_path


def fix_issue(check: str, template: dict) -> str:
    """Fixes a check based on the Kubelinter check ID.

    Source: https://docs.kubelinter.io/#/generated/checks

    Args:
        check (dict): The dictionary representing a check to fix.
        template (dict): The parsed YAML template.
    """

    # Get function from lookup dictionary
    my_lookup = LookupClass()
    check_id = my_lookup.get_value(check["Check"])

    # Check if the function exists and call it
    if check_id is not None:

        # resource["kind"]["namespace"]["name"]
        kind = check["Object"]["K8sObject"]["GroupVersionKind"]["Kind"]
        namespace = check["Object"]["K8sObject"]["Namespace"]
        if not namespace:
            namespace = "default"
        name = check["Object"]["K8sObject"]["Name"]
        resource_path = f"{kind}/{namespace}/{name}"

        # spec/template/spec/containers/0/
        obj_path = ""

        if "container" in check["Diagnostic"]["Message"]:
            # Extract characters between \" and \"
            cont_name = check["Diagnostic"]["Message"].split("\"")[1]
            # Find container path based on container name
            obj_path = get_container_path(template, resource_path, cont_name)

        paths = {
            "resource_path": resource_path,
            "obj_path": obj_path
        }

        # Memory limits & requests
        if check["Check"] == "unset-memory-requirements":
            fix_template.set_template(template, "check_1", paths)
            fix_template.set_template(template, "check_2", paths)

            k8s_resource = kics_fix_chart.get_resource_dict(template, resource_path.split("/"))

            if k8s_resource and k8s_resource is not None:
                if "spec" in k8s_resource:
                    k8s_resource = k8s_resource["spec"]
                    if "template" in k8s_resource:
                        k8s_resource = k8s_resource["template"]["spec"]
                    elif "jobTemplate" in k8s_resource:
                        k8s_resource = k8s_resource["jobTemplate"]["spec"]["template"]["spec"]

                # if "initContainers" in k8s_resource and k8s_resource["initContainers"] is not None:
                #     for idx, container in enumerate(k8s_resource["initContainers"]):
                        # paths["obj_path"] = paths["obj_path"].replace("containers", "initContainers")
                        # Replace the container index with idx
                        # paths["obj_path"] = paths["obj_path"].replace(paths["obj_path"].split("/")[-1], str(idx))
                        # fix_template.set_template(template, "check_1", paths)
                        # fix_template.set_template(template, "check_2", paths)

            return "check_1, check_2"

        # CPU limits & requests
        elif check["Check"] == "unset-cpu-requirements":
            fix_template.set_template(template, "check_4", paths)
            fix_template.set_template(template, "check_5", paths)
            return "check_4, check_5"

        # allowPrivilegeEscalation + privileged + Capabilities
        elif check["Check"] == "privilege-escalation-container":
            fix_template.set_template(template, "check_22", paths)
            fix_template.set_template(template, "check_21", paths)
            fix_template.set_template(template, "check_34", paths)
            return "check_22, check_21, check_34"

        else:
            fix_template.set_template(template, check_id, paths)
            return check_id

    else:
        print("No fix found for check ID: " + check["Check"])
        return None


class LookupClass:
    """This class is used to lookup the function to be called for each check.
    """

    _LOOKUP = {
        "latest-tag": "check_0",
        "unset-memory-requirements": "check_1",
        "unset-cpu-requirements": "check_4",
        "no-readiness-probe": "check_8",
        "host-pid": "check_10",
        "host-ipc": "check_11",
        "host-network": "check_12",
        "docker-sock": "check_15",
        "privileged-container": "check_21",
        "privilege-escalation-container": "check_22",
        "drop-net-raw-capability": "check_23",
        "no-read-only-root-fs": "check_27",
        "run-as-non-root": "check_28",
        "env-var-secret": "check_33",
        "deprecated-service-account-field": "check_37",
        "wildcard-in-rules": "check_39",
        "unsafe-sysctls": "check_41",
        "sensitive-host-mounts": "check_47",
        "dangling-service": "check_57",
        "non-existent-service-account": "check_58",
        "pdb-max-unavailable": "check_67",
        "ssh-port": "check_68",
        "no-anti-affinity": "",
        "mismatching-selector": "",
    }

    @classmethod
    def get_value(cls, key) -> Callable:
        """ Get the function to be called for each check.

        Args:
            key (str): The check number.
        """
        return cls._LOOKUP.get(key)

    @classmethod
    def print_value(cls, key) -> None:
        """ Print the function to be called for each check."""
        print(cls._LOOKUP.get(key))
