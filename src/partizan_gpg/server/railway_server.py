import os
from textual_serve.server import Server


port = int(os.environ.get("PORT", 8000))
url = os.environ.get("RAILWAY_URL")
server = Server(
    "Partizan Guard GPG",
    port=port,
    host="0.0.0.0",
    public_url=url
)
server.serve()