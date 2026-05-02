import sys

from hand_controller.app import main


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.append("--ui-live")
    main()
