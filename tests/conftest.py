import os
import tempfile

os.environ["DOWNLOAD_ORGANIZER_HOME"] = tempfile.mkdtemp(prefix="do-test-home-")
