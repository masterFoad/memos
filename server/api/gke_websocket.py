"""
GKE WebSocket API - Interactive shell endpoints
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosed
from fastapi.responses import HTMLResponse
import json

from server.core.logging import get_api_logger, get_websocket_logger
from server.core.security import verify_passport  # validate user passports for WS
from server.services.gke.gke_websocket_shell import gke_shell_service

logger = get_api_logger()
websocket_logger = get_websocket_logger()

router = APIRouter(prefix="/v1/gke", tags=["gke-websocket"])


@router.get("/shell/{session_id}")
async def gke_shell_page(session_id: str, k8s_ns: str, pod: str):
    """HTML page for GKE WebSocket shell (passport is read from the page URL querystring and forwarded to WS)."""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>OnMemOS GKE Shell - {session_id}</title>
        <meta charset="utf-8" />
        <style>
            body {{
                font-family: 'Courier New', monospace;
                background-color: #1e1e1e;
                color: #ffffff;
                margin: 0;
                padding: 20px;
            }}
            #terminal {{
                background-color: #000000;
                border: 1px solid #333;
                border-radius: 5px;
                padding: 10px;
                height: 80vh;
                overflow-y: auto;
                white-space: pre-wrap;
                font-size: 14px;
                line-height: 1.4;
            }}
            #input {{
                background-color: #000000;
                border: 1px solid #333;
                border-radius: 5px;
                color: #ffffff;
                font-family: 'Courier New', monospace;
                font-size: 14px;
                padding: 10px;
                width: 100%;
                margin-top: 10px;
                outline: none;
            }}
            .info {{ color: #4CAF50; }}
            .error {{ color: #f44336; }}
            .warning {{ color: #ff9800; }}
            .success {{ color: #4CAF50; }}
        </style>
    </head>
    <body>
        <h2>🚀 OnMemOS GKE Interactive Shell</h2>
        <p><strong>Session:</strong> {session_id} | <strong>Pod:</strong> {pod} | <strong>Namespace:</strong> {k8s_ns}</p>
        <div id="terminal"></div>
        <input type="text" id="input" placeholder="Enter command or type /help for available commands..." autofocus>
        
        <script>
            const terminal = document.getElementById('terminal');
            const input = document.getElementById('input');
            const sessionId = {json.dumps(session_id)};
            const k8sNs = {json.dumps(k8s_ns)};
            const pod = {json.dumps(pod)};

            // pull passport from the page URL (e.g. .../shell/<id>?k8s_ns=...&pod=...&passport=YOUR_PASSPORT)
            const params = new URLSearchParams(window.location.search);
            const passport = params.get('passport') || '';

            function wsScheme() {{
                return window.location.protocol === 'https:' ? 'wss' : 'ws';
            }}

            // WebSocket connection (forward passport to WS querystring)
            const wsUrl = `${{wsScheme()}}://${{window.location.host}}/v1/gke/shell/${{sessionId}}?k8s_ns=${{encodeURIComponent(k8sNs)}}&pod=${{encodeURIComponent(pod)}}` + (passport ? `&passport=${{encodeURIComponent(passport)}}` : '');
            const ws = new WebSocket(wsUrl);
            
            ws.onopen = function() {{
                appendToTerminal('🔗 Connected to GKE shell...', 'info');
            }};
            
            ws.onmessage = function(event) {{
                try {{
                    const data = JSON.parse(event.data);
                    handleMessage(data);
                }} catch (e) {{
                    appendToTerminal(String(event.data));
                }}
            }};
            
            ws.onclose = function() {{
                appendToTerminal('🔌 Connection closed', 'error');
            }};
            
            ws.onerror = function(error) {{
                appendToTerminal('❌ WebSocket error: ' + error, 'error');
            }};
            
            function handleMessage(data) {{
                const type = data.type;
                const content = data.content || data.message || '';
                
                switch(type) {{
                    case 'output':   appendToTerminal(content); break;
                    case 'error':    appendToTerminal(content, 'error'); break;
                    case 'info':     appendToTerminal(content, 'info'); break;
                    case 'warning':  appendToTerminal(content, 'warning'); break;
                    case 'success':  appendToTerminal(content, 'success'); break;
                    case 'clear':    terminal.innerHTML = ''; break;
                    case 'prompt':   /* prompts are handled client-side */ break;
                    default:         appendToTerminal(content || JSON.stringify(data));
                }}
            }}
            
            function appendToTerminal(text, className = '') {{
                const div = document.createElement('div');
                div.textContent = text;
                if (className) div.className = className;
                terminal.appendChild(div);
                terminal.scrollTop = terminal.scrollHeight;
            }}
            
            input.addEventListener('keypress', function(e) {{
                if (e.key === 'Enter') {{
                    const command = input.value.trim();
                    if (command) {{
                        ws.send(JSON.stringify({{ type: 'command', command }}));
                        input.value = '';
                    }}
                }}
            }});
            
            // Handle window resize
            function sendResize() {{
                if (ws.readyState === WebSocket.OPEN) {{
                    ws.send(JSON.stringify({{
                        type: 'resize',
                        cols: Math.floor(terminal.clientWidth / 8),
                        rows: Math.floor(terminal.clientHeight / 20)
                    }}));
                }}
            }}
            window.addEventListener('resize', sendResize);
            // initial size
            sendResize();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


def _get_passport_from_ws_query(websocket: WebSocket) -> str:
    """Extract passport from WebSocket query string (required)."""
    passport = websocket.query_params.get("passport")
    if not passport:
        raise ValueError("passport required")
    return passport


@router.websocket("/shell/{session_id}")
async def gke_websocket_shell(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for GKE interactive shell with billing integration."""
    try:
        # Validate query params BEFORE accepting
        k8s_ns = websocket.query_params.get("k8s_ns")
        pod = websocket.query_params.get("pod")
        if not k8s_ns or not pod:
            await websocket.close(code=1008, reason="Missing k8s_ns or pod parameters")
            return

        # Validate passport BEFORE accept (and ensure session ownership)
        try:
            passport = _get_passport_from_ws_query(websocket)
            user_info = await verify_passport(x_api_key=passport)
        except Exception as e:
            await websocket.close(code=1008, reason=f"passport error: {e}")
            return

        # Check session ownership
        try:
            from server.services.sessions.manager import sessions_manager
            session_info = await sessions_manager.get_session(session_id)
            if not session_info:
                await websocket.close(code=1008, reason="Session not found")
                return
            owner_user_id = session_info.get("user")
            if not owner_user_id or owner_user_id != user_info.get("user_id"):
                await websocket.close(code=1008, reason="Session not owned by passport user")
                return
        except Exception as e:
            await websocket.close(code=1011, reason=f"Session check failed: {e}")
            return

        # OK to accept now
        await websocket.accept()

        # Handle WebSocket connection with billing
        await gke_shell_service.handle_websocket(websocket, session_id, k8s_ns, pod, user_info.get("user_id"))

    except WebSocketDisconnect:
        websocket_logger.info(f"WebSocket disconnected: {session_id}")
    except ConnectionClosed as e:
        # Normal WebSocket closure - not an error
        if getattr(e, "code", None) == 1000:
            websocket_logger.debug(f"WebSocket connection closed normally: {e}")
        else:
            websocket_logger.info(f"WebSocket connection closed with code {getattr(e, 'code', 'unknown')}: {e}")
    except Exception as e:
        websocket_logger.error(f"WebSocket error: {e}")
        # Try to notify client if still open-ish
        try:
            await websocket.send_text(
                '{"type":"error","message":' + json.dumps(f"Internal error: {str(e)}") + "}"
            )
        except Exception:
            pass
        try:
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass
