from sd_core.log import setup_logging

from sd_watcher_afk.afk import AFKWatcher
from sd_watcher_afk.config import parse_args


def main() -> None:
    """
     Entry point for AFK watcher. Sets up logging starts the watcher and waits for it to finish.
     
     
     @return A tuple containing exit code and error message if there was an error or None otherwise. This is called from sys. exit
    """
    args = parse_args()

    # Set up logging
    setup_logging(
        "sd-watcher-afk",
        testing=args.testing,
        verbose=args.verbose,
        log_stderr=True,
        log_file=True,
    )

    # Start watcher
    watcher = AFKWatcher(args, testing=args.testing)
    watcher.run()


# main function for the main module
if __name__ == "__main__":
    main()
