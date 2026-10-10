# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import multiprocessing
import sys


def main() -> None:
    """Run the Typer CLI, or the private frozen daemon worker entrypoint."""
    multiprocessing.freeze_support()
    if getattr(sys, "frozen", False) and len(sys.argv) > 1 and sys.argv[1] == "_serve":
        from apps.admin_console.server import main as serve

        serve(sys.argv[2:])
        return

    from artemis.interfaces.cli.main import app

    app()


if __name__ == "__main__":
    main()
