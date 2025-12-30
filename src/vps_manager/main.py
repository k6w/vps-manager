import sys
import argparse
from .core import VPSManager, VERSION
from .ui import TerminalUI
from .utils import setup_logging, get_logger

try:
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
except ImportError:
    console = None

logger = get_logger(__name__)

def print_output(message, style="bold green", error=False):
    if console:
        if error:
            console.print(f"[bold red]Error:[/bold red] {message}")
        else:
            console.print(f"[{style}]{message}[/{style}]")
    else:
        prefix = "Error: " if error else ""
        print(f"{prefix}{message}")

def main():
    """Main entry point"""
    setup_logging()
    
    parser = argparse.ArgumentParser(description="VPS NGINX Domain Manager")
    parser.add_argument("--version", action="version", version=f"VPS Manager v{VERSION}")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall VPS Manager")
    parser.add_argument("--check", action="store_true", help="Check environment dependencies")
    parser.add_argument("--batch", action="store_true", help="Run in batch mode (no UI)")
    parser.add_argument("--add-domain", help="Add a new domain")
    parser.add_argument("--port", type=int, help="Backend port for new domain")
    parser.add_argument("--ssl", action="store_true", help="Enable SSL for new domain")
    parser.add_argument("--no-ssl", action="store_true", help="Disable SSL for new domain")
    
    args = parser.parse_args()
    
    manager = VPSManager()
    
    # Handle check
    if args.check:
        print_output("Checking environment...", style="bold blue")
        # Check NGINX
        nginx_active, nginx_status = manager.get_nginx_status()
        if nginx_active:
            print_output(f"[OK] NGINX is {nginx_status}", style="green")
        else:
            print_output(f"[X] NGINX is {nginx_status}", style="red", error=True)
            
        # Check Certbot (simple check)
        success, output = manager.run_command("which certbot")
        if success:
            print_output("[OK] Certbot found", style="green")
        else:
            print_output("[!] Certbot not found", style="yellow")
            
        sys.exit(0)

    # Handle uninstall
    if args.uninstall:
        # In a real CLI app, we might want to ask for confirmation here or require a --force flag
        # For now, we'll just run the uninstall logic which logs what it does
        print_output("Uninstalling VPS Manager...", style="bold red")
        success, message = manager.uninstall_manager()
        print_output(message, style="green" if success else "red", error=not success)
        sys.exit(0 if success else 1)
    
    # Handle batch mode
    if args.batch:
        if args.add_domain:
            if not args.port:
                print_output("--port is required when adding a domain", error=True)
                sys.exit(1)
            
            ssl_enabled = True
            if args.no_ssl:
                ssl_enabled = False
            elif args.ssl:
                ssl_enabled = True
            else:
                # Use default from config
                ssl_enabled = manager.config.get('default_ssl', True)
            
            success, message = manager.add_domain(args.add_domain, args.port, ssl_enabled)
            print_output(message, style="green" if success else "red", error=not success)
            sys.exit(0 if success else 1)
        else:
            print_output("No action specified for batch mode", error=True)
            sys.exit(1)
    
    # Run UI
    try:
        ui = TerminalUI(manager)
        ui.run()
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        print_output(f"An error occurred: {e}", error=True)
        print_output("Check the log file for details.", style="yellow")
        sys.exit(1)

if __name__ == "__main__":
    main()
