"""Attach the new subprocess to its controlling terminal, then exec the shell."""

import fcntl
import os
import sys
import termios

if __name__ == "__main__":
    # Popen has already created a session and attached stdio to the slave PTY.
    # This runs in a fresh interpreter, not in the server's forked Python state.
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    os.execvpe(sys.argv[1], sys.argv[1:], os.environ)
