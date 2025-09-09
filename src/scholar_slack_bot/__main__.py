"""Command-line entry point for the Scholar Slack bot package."""

# Import the CLI's ``main`` function from the dedicated module.
from .cli import main

if __name__ == "__main__":
    # Execute the CLI when the package is invoked as a module.
    main()
