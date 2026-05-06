import os
from textual_serve.server import Server


port = int(os.environ.get("PORT", 8000))
server = Server(
    "partizan-gpg",
    port=port,
    host="0.0.0.0"
)
server.serve()