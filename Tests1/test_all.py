"""Master test runner for all generated features - Windows Compatible"""
import subprocess
import json
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def install_pytest():
    """Ensure pytest is installed"""
    try:
        import pytest
        return True
    except ImportError:
        console.print("[yellow]Installing pytest...[/yellow]")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pytest"], check=True)
        return True


def test_project(project_path: Path):
    """Test a single project"""
    console.print(f"\n[cyan]Testing: {project_path.name}[/cyan]")

    # Install dependencies if requirements.txt exists
    req_file = project_path / "requirements.txt"
    if req_file.exists():
        console.print("  Installing dependencies...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-r", str(req_file)],
                timeout=120,
                check=False
            )
        except subprocess.TimeoutExpired:
            console.print("  [yellow]âš ï¸  Dependency installation timeout[/yellow]")
        except Exception as e:
            console.print(f"  [yellow]âš ï¸  Dependency install error: {e}[/yellow]")

    # Check if test files exist
    test_files = list(project_path.glob("test_*.py"))
    test_dir = project_path / "tests"
    has_tests = len(test_files) > 0 or test_dir.exists()

    if not has_tests:
        return {
            "name": project_path.name,
            "status": "âš ï¸  NO TESTS",
            "tests": 0,
            "output": "No test files found"
        }

    # Run pytest
    console.print("  Running tests...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--tb=short", "--maxfail=3"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=60
        )

        output = result.stdout + result.stderr
        passed = output.count("passed")
        failed = output.count("failed")

        if result.returncode == 0:
            status = "âœ… PASS"
        elif result.returncode == 5:  # No tests collected
            status = "âš ï¸  NO TESTS"
            passed = 0
        else:
            status = "âŒ FAIL"

        return {
            "name": project_path.name,
            "status": status,
            "tests": passed,
            "failed": failed,
            "output": output[:500]  # First 500 chars
        }

    except subprocess.TimeoutExpired:
        return {
            "name": project_path.name,
            "status": "â±ï¸  TIMEOUT",
            "tests": 0,
            "output": "Test execution timeout after 60s"
        }
    except Exception as e:
        return {
            "name": project_path.name,
            "status": "âŒ ERROR",
            "tests": 0,
            "output": str(e)
        }


def check_structure():
    """Check project structure and list what we have"""
    console.print("\n[bold magenta]Project Structure Check[/bold magenta]")

    base_paths = {
        "frontend": Path("frontend"),
        "backend": Path("backend"),
        "infrastructure": Path("infrastructure")
    }

    structure = {}
    for name, path in base_paths.items():
        if path.exists():
            projects = [p for p in path.iterdir() if p.is_dir() and not p.name.startswith(".")]
            structure[name] = len(projects)
            console.print(f"  [green]âœ“[/green] {name}: {len(projects)} projects")
        else:
            structure[name] = 0
            console.print(f"  [red]âœ—[/red] {name}: not found")

    return structure


def main():
    console.print("[bold blue]â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•[/bold blue]")
    console.print("[bold blue]  Testing All Generated Features  [/bold blue]")
    console.print("[bold blue]â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•[/bold blue]")

    # Install pytest if needed
    if not install_pytest():
        console.print("[red]Failed to install pytest. Exiting.[/red]")
        return

    # Check structure
    structure = check_structure()
    total_projects = sum(structure.values())

    if total_projects == 0:
        console.print("\n[red]No projects found! Please consolidate your code first.[/red]")
        console.print("\nExpected structure:")
        console.print("  unified_app/")
        console.print("    â”œâ”€â”€ frontend/")
        console.print("    â”œâ”€â”€ backend/")
        console.print("    â””â”€â”€ infrastructure/")
        return

    # Test all projects
    base_paths = [Path("frontend"), Path("backend"), Path("infrastructure")]
    results = []

    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
    ) as progress:
        task = progress.add_task(f"Testing {total_projects} projects...", total=total_projects)

        for base in base_paths:
            if not base.exists():
                continue

            console.print(f"\n[bold magenta]â•â•â• Testing {base} â•â•â•[/bold magenta]")

            for project in sorted(base.iterdir()):
                if project.is_dir() and not project.name.startswith("."):
                    result = test_project(project)
                    results.append(result)
                    progress.advance(task)

    # Summary table
    console.print("\n[bold blue]â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•[/bold blue]")
    console.print("[bold blue]        Test Results Summary        [/bold blue]")
    console.print("[bold blue]â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•[/bold blue]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Project", style="cyan", no_wrap=False, width=40)
    table.add_column("Status", style="bold", width=12)
    table.add_column("Passed", justify="right", width=8)
    table.add_column("Failed", justify="right", width=8)

    for r in results:
        status_style = "green" if "PASS" in r["status"] else "red" if "FAIL" in r["status"] else "yellow"
        table.add_row(
            r["name"][:40],
            f"[{status_style}]{r['status']}[/{status_style}]",
            str(r.get("tests", 0)),
            str(r.get("failed", 0))
        )

    console.print(table)

    # Statistics
    passed = sum(1 for r in results if "PASS" in r["status"])
    failed = sum(1 for r in results if "FAIL" in r["status"])
    no_tests = sum(1 for r in results if "NO TESTS" in r["status"])
    errors = sum(1 for r in results if "ERROR" in r["status"] or "TIMEOUT" in r["status"])

    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  âœ… Passed: {passed}")
    console.print(f"  âŒ Failed: {failed}")
    console.print(f"  âš ï¸  No Tests: {no_tests}")
    console.print(f"  â— Errors: {errors}")
    console.print(f"  ðŸ“Š Total: {len(results)}")

    # Save detailed results
    output_file = Path("test_results.json")
    output_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    console.print(f"\n[green]âœ“ Detailed results saved to {output_file}[/green]")

    # Show failures
    failures = [r for r in results if "FAIL" in r["status"] or "ERROR" in r["status"]]
    if failures:
        console.print(f"\n[bold red]Failed Projects ({len(failures)}):[/bold red]")
        for f in failures[:5]:  # Show first 5 failures
            console.print(f"\n[red]â€¢ {f['name']}[/red]")
            console.print(f"  {f['output'][:200]}...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Testing interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Unexpected error: {e}[/red]")
        import traceback

        traceback.print_exc()
