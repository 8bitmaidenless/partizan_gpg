import os
from textual_serve.server import Server


# port = int(os.environ.get("PORT", 8000))
# # server = Server(
# #     "python partizan_gpg.tui.app",
# #     port=port,
# #     host="0.0.0.0",
# # )
# server = Server()

# def main():
#     server.serve()
def main():
    port =int(os.environ.get("PORT", 8000))
    server = Server(
        "python -m partizan_gpg",
        port=port,
        host="0.0.0.0"
    )
    server.serve()