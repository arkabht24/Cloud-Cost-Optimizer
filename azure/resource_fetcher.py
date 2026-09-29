import json
import os
import shutil
import subprocess
from typing import Optional


DEMO_RESOURCE_GROUP = "demo-cost-lab"
DEMO_RESOURCES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "sample_azure_resources.json"
)


def _get_az_executable() -> str:
    """Resolve Azure CLI from PATH or common Windows install locations."""
    az_path = shutil.which("az")
    if az_path:
        return az_path

    common_windows_paths = [
        r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
        r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
        r"C:\Program Files\Azure CLI\az.cmd",
        r"C:\Program Files (x86)\Azure CLI\az.cmd",
    ]

    for candidate in common_windows_paths:
        if os.path.exists(candidate):
            return candidate

    return "az"


def run_azure_cli(args: list[str], *, check: bool = True) -> str:
    az_executable = _get_az_executable()
    normalized_args = list(args)
    if normalized_args and normalized_args[0].lower() == "az":
        normalized_args = normalized_args[1:]

    if not shutil.which(az_executable) and not os.path.exists(az_executable):
        raise RuntimeError(
            "Azure CLI is not installed or not available on PATH. "
            "Please install Azure CLI and reopen the terminal before using this app."
        )

    if os.name == "nt":
        # On Windows Azure CLI is typically installed as az.cmd or az.exe.
        # Calling the .cmd wrapper directly via cmd /c is the reliable pattern.
        if az_executable.lower().endswith(".cmd") or az_executable.lower().endswith("az"):
            command = ["cmd", "/c", "az", *normalized_args]
        else:
            command = [az_executable, *normalized_args]
    else:
        command = [az_executable, *normalized_args]

    result = subprocess.run(command, capture_output=True, text=True)
    if check and result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or "Azure CLI command failed."
        raise RuntimeError(details)
    return result.stdout.strip()


def build_azure_login_command() -> list[str]:
    return ["login", "--use-device-code"]


def build_subscription_set_command(subscription: str) -> list[str]:
    return ["account", "set", "--subscription", subscription]


def login_to_azure(subscription: Optional[str] = None) -> str:
    run_azure_cli(build_azure_login_command())
    if subscription and subscription.strip():
        run_azure_cli(build_subscription_set_command(subscription.strip()))
    return run_azure_cli(["az", "account", "show", "--query", "name", "-o", "tsv"])


def get_active_subscription() -> str:
    try:
        return run_azure_cli(["az", "account", "show", "--query", "name", "-o", "tsv"])
    except Exception:
        return ""


def fetch_all_resources(resource_group: str, subscription: Optional[str] = None) -> list:
    """Return Azure resources, or a local fixture for the built-in demo group."""
    if resource_group.strip().lower() == DEMO_RESOURCE_GROUP:
        with open(DEMO_RESOURCES_PATH, encoding="utf-8") as sample_file:
            return json.load(sample_file)

    if subscription and subscription.strip():
        run_azure_cli(build_subscription_set_command(subscription.strip()))

    result = run_azure_cli([
        "az",
        "resource",
        "list",
        "--resource-group",
        resource_group,
        "--output",
        "json",
    ])
    return json.loads(result) if result else []
