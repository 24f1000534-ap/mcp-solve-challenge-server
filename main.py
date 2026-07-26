"""
Minimal MCP (Model Context Protocol) server.

It exposes ONE tool called `solve_challenge` over a Streamable HTTP endpoint
at POST /mcp. This is NOT using the official MCP Python SDK — it's a
hand-rolled JSON-RPC handler that speaks just enough of the MCP protocol
for the grader to talk to it: initialize -> notifications/initialized ->
tools/list -> tools/call (x5).

Why hand-roll it instead of using the `mcp` SDK package? Because the SDK's
API changes across versions and can be fiddly to deploy on Render. This
version has zero MCP-specific dependencies — just FastAPI, which you
already know how to deploy.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import hashlib

app = FastAPI()

# Your registered exam email — trimmed + lowercased, exactly as required.
EMAIL = "24f1000534@ds.study.iitm.ac.in"


@app.get("/")
def home():
    """Just so visiting the URL in a browser doesn't show an error."""
    return {"status": "MCP server is running", "endpoint": "/mcp (POST)"}


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    body = await request.json()
    method = body.get("method")
    msg_id = body.get("id")  # present on requests, absent on notifications

    # --- notifications (e.g. "notifications/initialized") ---
    # These have no "id" and expect NO JSON-RPC response body, just a
    # 202 Accepted so the client knows we got it.
    if msg_id is None:
        return JSONResponse(content=None, status_code=202)

    # --- initialize handshake ---
    if method == "initialize":
        result = {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "solve-challenge-server", "version": "1.0.0"},
        }

    # --- list our one tool ---
    elif method == "tools/list":
        result = {
            "tools": [
                {
                    "name": "solve_challenge",
                    "description": "Reads X-Exam-Challenge header and returns the required hash.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                }
            ]
        }

    # --- actually run the tool ---
    elif method == "tools/call":
        # IMPORTANT: read the challenge from the HTTP header, NOT the JSON body.
        # Header names are case-insensitive, Starlette handles that for us.
        challenge = request.headers.get("x-exam-challenge", "")

        raw_string = f"{challenge}:{EMAIL}"
        digest = hashlib.sha256(raw_string.encode("utf-8")).hexdigest()
        answer = digest[:16]  # first 16 lowercase hex chars

        result = {
            "content": [
                {"type": "text", "text": answer}
            ]
        }

    # --- anything else we don't support ---
    else:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            },
            status_code=200,
        )

    return JSONResponse(
        content={"jsonrpc": "2.0", "id": msg_id, "result": result},
        status_code=200,
    )
