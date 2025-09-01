"""
GKE WebSocket API - Interactive shell endpoints
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from websockets.exceptions import ConnectionClosed
from fastapi.responses import HTMLResponse

from server.core.logging import get_api_logger, get_websocket_logger
from server.core.security import require_api_key
from server.services.gke.gke_websocket_shell import gke_shell_service

logger = get_api_logger()
websocket_logger = get_websocket_logger()

router = APIRouter(prefix="/v1/gke", tags=["gke-websocket"])

@router.get("/shell/{session_id}")
async def gke_shell_page(session_id: str, k8s_ns: str, pod: str):
    """HTML page for GKE WebSocket shell"""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>OnMemOS GKE Shell - {session_id}</title>
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
            .info {{
                color: #4CAF50;
            }}
            .error {{
                color: #f44336;
            }}
            .warning {{
                color: #ff9800;
            }}
            .success {{
                color: #4CAF50;
            }}
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
            const sessionId = '{session_id}';
            const k8sNs = '{k8s_ns}';
            const pod = '{pod}';
            
            // WebSocket connection
            const ws = new WebSocket(`ws://${{window.location.host}}/v1/gke/shell/${{sessionId}}?k8s_ns=${{k8sNs}}&pod=${{pod}}`);
            
            ws.onopen = function(event) {{
                appendToTerminal('🔗 Connected to GKE shell...', 'info');
            }};
            
            ws.onmessage = function(event) {{
                const data = JSON.parse(event.data);
                handleMessage(data);
            }};
            
            ws.onclose = function(event) {{
                appendToTerminal('🔌 Connection closed', 'error');
            }};
            
            ws.onerror = function(error) {{
                appendToTerminal('❌ WebSocket error: ' + error, 'error');
            }};
            
            function handleMessage(data) {{
                const type = data.type;
                const content = data.content;
                
                switch(type) {{
                    case 'output':
                        appendToTerminal(content);
                        break;
                    case 'error':
                        appendToTerminal(content, 'error');
                        break;
                    case 'info':
                        appendToTerminal(content, 'info');
                        break;
                    case 'warning':
                        appendToTerminal(content, 'warning');
                        break;
                    case 'success':
                        appendToTerminal(content, 'success');
                        break;
                    case 'clear':
                        terminal.innerHTML = '';
                        break;
                    case 'prompt':
                        // Don't display prompt, it will be shown in input
                        break;
                    default:
                        appendToTerminal(content);
                }}
            }}
            
            function appendToTerminal(text, className = '') {{
                const div = document.createElement('div');
                div.textContent = text;
                if (className) {{
                    div.className = className;
                }}
                terminal.appendChild(div);
                terminal.scrollTop = terminal.scrollHeight;
            }}
            
            input.addEventListener('keypress', function(e) {{
                if (e.key === 'Enter') {{
                    const command = input.value.trim();
                    if (command) {{
                        // Send command
                        ws.send(JSON.stringify({{
                            type: 'command',
                            command: command
                        }}));
                        
                        // Clear input
                        input.value = '';
                    }}
                }}
            }});
            
            // Handle window resize
            window.addEventListener('resize', function() {{
                ws.send(JSON.stringify({{
                    type: 'resize',
                    cols: Math.floor(terminal.clientWidth / 8),
                    rows: Math.floor(terminal.clientHeight / 20)
                }}));
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@router.websocket("/shell/{session_id}")
async def gke_websocket_shell(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for GKE interactive shell with billing integration"""
    await websocket.accept()
    
    try:
        # Extract query parameters
        k8s_ns = websocket.query_params.get("k8s_ns")
        pod = websocket.query_params.get("pod")
        
        if not k8s_ns or not pod:
            await websocket.close(code=1008, reason="Missing k8s_ns or pod parameters")
            return
        
        # Get user_id from session (for billing integration)
        user_id = None
        try:
            from server.services.sessions.manager import sessions_manager
            session_info = sessions_manager.get_session(session_id)
            if session_info:
                user_id = session_info.get("user")
                logger.info(f"Found user {user_id} for session {session_id}")
        except Exception as e:
            logger.warning(f"Could not get user_id for session {session_id}: {e}")
        
        # Handle WebSocket connection with billing
        await gke_shell_service.handle_websocket(websocket, session_id, k8s_ns, pod, user_id)
        
    except WebSocketDisconnect:
        websocket_logger.info(f"WebSocket disconnected: {session_id}")
    except ConnectionClosed as e:
        # Normal WebSocket closure - not an error
        if e.code == 1000:
            websocket_logger.debug(f"WebSocket connection closed normally: {e}")
        else:
            websocket_logger.info(f"WebSocket connection closed with code {e.code}: {e}")
    except Exception as e:
        websocket_logger.error(f"WebSocket error: {e}")
        if websocket.client_state.value < 3:  # Not closed
            await websocket.close(code=1011, reason=f"Internal error: {str(e)}")
