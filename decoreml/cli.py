import re
import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import os
import glob
import datetime

def format_validation_message(message):
    if message == "":
        return message
    else:
        return message.replace('\\"', '"') + "\n"


def extract_single(tensor_operation):
    operation_match = re.search(r"= (\w+)\(", tensor_operation)
    operation = operation_match.group(1) if operation_match else "Not found"

    runtimes_match = re.search(
        r"EstimatedRuntime = dict<string, fp64>\(\{\{(.+?)\}\}\)", tensor_operation
    )
    runtimes = {}
    if runtimes_match:
        runtimes_str = runtimes_match.group(1)
        runtimes_pairs = re.findall(r'"(.+?)", (\d+\.\d+)', runtimes_str)
        runtimes = {backend: float(runtime) for backend, runtime in runtimes_pairs}

    selected_backend_match = re.search(
        r'SelectedBackend = string\("(.+?)"\)', tensor_operation
    )
    selected_backend = (
        selected_backend_match.group(1) if selected_backend_match else "Not found"
    )

    name_match = re.search(r'name = string\("(.+?)"\)', tensor_operation)
    name = name_match.group(1) if name_match else "Not found"

    validation_messages = {}
    validation_message_match = re.search(
        r"ValidationMessage = dict<string, string>\(\{\{(.+?)\}\}\)", tensor_operation
    )
    if validation_message_match:
        validation_message_str = validation_message_match.group(1)
        validation_message_pairs = re.findall(
            r'"(.+?)", "(.+)"', validation_message_str
        )
    
        validation_messages = {
            backend: format_validation_message(message) 
            for backend, message in validation_message_pairs
        }

    return operation, runtimes, selected_backend, name, validation_messages


def format_backend(backend):
    if backend == "classic_cpu" or backend == "bnns":
        return f"[blue]{backend}[/blue]"
    elif backend == "mps_graph":
        return f"[green]{backend}[/green]"
    elif backend == "ane":
        return f"[purple]{backend}[/purple]"
    else:
        return backend


def round_runtime(runtime):
    return round(runtime, 4) if runtime != "N/A" else runtime


def find_latest_analytics_file():
    search_path = os.path.expanduser(
        "~/Library/Caches/com.apple.dt.DTMLModelRunnerService/com.apple.e5rt.e5bundlecache/"
    )
    analytics_files = glob.glob(
        os.path.join(search_path, "**", "analytics.mil"), recursive=True
    )
    if not analytics_files:
        raise FileNotFoundError("No analytics.mil files found.")

    latest_file = max(analytics_files, key=os.path.getmtime)
    return latest_file


def parse_mil_file(file_path, debug=False):
    file_provided = True
    if not file_path:
        file_path = find_latest_analytics_file()
        file_provided = False

    with open(file_path, "r") as file:
        content = file.read()

    tensor_operations = [
        line.strip() for line in content.split(";") if line.strip().startswith("tensor")
    ]

    table = Table(title="MIL Operations")
    table.add_column("Operation", style="cyan")
    table.add_column("CPU Runtime", style="blue")
    table.add_column("GPU Runtime", style="green")
    table.add_column("ANE Runtime", style="purple")
    table.add_column("Selected Backend", style="green")
    table.add_column("Name", style="yellow")
    table.add_column("Validation Messages", style="red")

    for operation in tensor_operations:
        if debug:
            print(operation)
        operation, runtimes, selected_backend, name, validation_messages = (
            extract_single(operation)
        )
        cpu_runtime = round_runtime(runtimes.get("classic_cpu", "N/A"))
        gpu_runtime = round_runtime(runtimes.get("mps_graph", "N/A"))
        ane_runtime = round_runtime(runtimes.get("ane", "N/A"))

        validation_messages_str = "\n".join(
            f"{backend}: {message}" for backend, message in validation_messages.items()
        )
        table.add_row(
            operation,
            str(cpu_runtime),
            str(gpu_runtime),
            str(ane_runtime),
            format_backend(selected_backend),
            name,
            validation_messages_str,
        )

    console = Console()
    console.print(Panel(table, expand=False))

    if not file_provided:
        print(f"Using latest analytics file: {file_path}")
        time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
        print(f"analytics.mil last modified: {time}")


def main():
    parser = argparse.ArgumentParser(
        prog="deCoreML",
        usage="%(prog)s [options]",
        description="Find out why your CoreML model isn't running on the Neural Engine! \
                     This script parses the analytics.mil file generated by CoreML model compilation and \
                     displays the selected backend for each operation, along with the estimated runtimes \
                     and reasons why a backend wasn't selected.",
    )
    parser.add_argument("--file_path", help="Path to the MIL file")
    parser.add_argument("--debug", help="Enable debug mode", action="store_true")
    args = parser.parse_args()

    parse_mil_file(args.file_path, args.debug)

