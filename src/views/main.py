import asyncio
import ssl
import json
import os
import re
import time
import socket
import subprocess
import sys
import base64
import tempfile
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Set
import ipaddress
from pydantic import Field

from dotenv import load_dotenv
import html
import databases
import httpx
import routeros_api
import sqlalchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from fastapi import FastAPI, HTTPException, WebSocket, Query, Depends, Request, Body, Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from starlette.websockets import WebSocketDisconnect

from pydantic import BaseModel
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, unquote

# 🔐 Usamos SOLO PyJWT (NO python-jose)
import jwt  # PyJWT

# === QR Scan (opción remota con celular) ===
import secrets

# ⚠️ CREÁ LA APP ANTES DE CUALQUIER @app.*
app = FastAPI(title="Monitor360 API", version="18.0.0-multi-tenant")

# ✅ Healthcheck simple para Docker / Nginx
@app.get("/healthz")
async def healthz():
    """
    Endpoint de salud liviano: no consulta DB ni dependencias externas.
    Devuelve un JSON mínimo que sirve para healthchecks del compose.
    """
    return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}


load_dotenv()

FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "https://www.monitor360.media")

# Sesiones efímeras de escaneo para la Opción B
SCAN_SESSIONS: dict[str, dict] = {}  # sid -> { owner_id, created, status, result }
SCAN_TTL_SECONDS = 300  # 5 min

# Caché de resolución de tipo de interfaz por (ip_dispositivo, nombre_iface)
_M360_KIND_CACHE: dict[tuple[str, str], str] = {}

# Ruta al archivo scanner.html (lo vamos a subir más adelante)
SCANNER_HTML_PATH = os.path.join(os.path.dirname(__file__), "scanner.html")

# ==============================================================
# 📡 AUTO-REGISTRO MIKROTIK CLIENTE (POST /api/vpns/mikrotik-auto)
# ==============================================================

# 🔧 ENV esperados (con defaults razonables)
WG_POOL_CIDR = os.getenv("WG_POOL_CIDR", "10.10.13.0/24")        # Pool para asignar Address a clientes
WG_SERVER_PUBLIC_KEY = os.getenv("WG_SERVER_PUBLIC_KEY", "")     # Public key del servidor WG (obligatorio si no viene en request)
WG_ENDPOINT_HOST = os.getenv("WG_ENDPOINT_HOST", "")             # DynDNS/IP público del servidor (fallback)
WG_ENDPOINT_PORT = int(os.getenv("WG_ENDPOINT_PORT", "51820"))   # Puerto UDP del servidor (fallback)
WG_DNS_DEFAULT = os.getenv("WG_DNS_DEFAULT", "1.1.1.1")          # DNS por defecto para el cliente
WG_INTERFACE = os.getenv("WG_INTERFACE", "wg0")                  # Nombre interfaz en server (wg0 por defecto)

# ── Helpers WireGuard (server) ─────────────────────────────────

def _wg_exec(args: List[str]) -> subprocess.CompletedProcess:
    """
    Ejecuta un comando wg/wg-quick de forma segura. Lanza HTTPException si falla.
    """
    try:
        cp = subprocess.run(
            args, check=True, capture_output=True, text=True, env={**os.environ, **WG_ENV_BASE}
        )
        return cp
    except subprocess.CalledProcessError as e:
        stdout, stderr = e.stdout.strip(), e.stderr.strip()
        raise HTTPException(status_code=500, detail=f"WG error: {' '.join(args)} | {stderr or stdout or e!r}")

def _wg_generate_keypair() -> Tuple[str, str]:
    """
    Genera (private, public) usando binarios wg. Alternativa sin binarios:
    usar pynacl, pero wg está disponible en el container del backend.
    """
    # gen private
    cp_priv = _wg_exec(["wg", "genkey"])
    priv = cp_priv.stdout.strip()
    # derive public
    cp_pub = subprocess.run(["wg", "pubkey"], input=priv, capture_output=True, text=True, check=True)
    pub = cp_pub.stdout.strip()
    if not priv or not pub:
        raise HTTPException(status_code=500, detail="No se pudo generar keypair de WireGuard.")
    return priv, pub

def _wg_add_peer(server_iface: str, client_pubkey: str, client_ip_cidr: str, allowed_ips: List[str]) -> None:
    """
    Da de alta el peer del cliente en el servidor.
    - allowed_ips del peer en el server suelen ser el /32 del cliente (ruteo de retorno).
    - El cliente usará AllowedIPs = 0.0.0.0/0 (o lo que envíes).
    """
    # En el server, lo importante es enrutar el /32 del cliente por este peer:
    client_ip = str(client_ip_cidr.split("/")[0]) + "/32"
    _wg_exec([
        "wg", "set", server_iface,
        "peer", client_pubkey,
        "allowed-ips", client_ip
    ])

def _wg_remove_peer(server_iface: str, client_pubkey: str) -> None:
    """
    Remueve el peer del cliente del server. No falla si ya no existe.
    """
    try:
        _wg_exec(["wg", "set", server_iface, "peer", client_pubkey, "remove"])
    except HTTPException:
        # Silencioso: si no existe, no importa
        pass

def _wg_dump_peers(server_iface: str) -> List[Dict[str, Any]]:
    """
    Parsea 'wg show <iface> dump' de forma robusta.
    Formatos esperados por línea (peers):
    A) iface \t peer_pub \t psk \t endpoint \t allowed_ips \t latest \t rx \t tx \t keepalive
    B) peer_pub \t psk \t endpoint \t allowed_ips \t latest \t rx \t tx \t keepalive
    """
    cp = _wg_exec(["wg", "show", server_iface, "dump"])
    lines = cp.stdout.strip().splitlines()

    if not lines:
        return []

    peers: List[Dict[str, Any]] = []
    # La primera línea es la interfaz; las siguientes son peers
    for ln in lines[1:]:
        cols = ln.split("\t")
        if len(cols) < 8:
            # línea inesperada, la ignoramos
            continue

        # Si la primera columna coincide con la iface, el formato es A (con iface al inicio)
        offset = 1 if cols[0] == server_iface else 0
        # Aseguramos longitud suficiente tras el offset
        if len(cols) < offset + 8:
            continue

        peer_public = cols[offset + 0]
        preshared = cols[offset + 1]
        endpoint = cols[offset + 2] or ""
        allowed_ips = cols[offset + 3] or ""
        latest_str = cols[offset + 4] or "0"
        rx_str = cols[offset + 5] or "0"
        tx_str = cols[offset + 6] or "0"
        keepalive = cols[offset + 7] or ""

        # Normalizamos numéricos
        try:
            latest = int(latest_str)
        except Exception:
            latest = 0
        try:
            rx_bytes = int(rx_str)
        except Exception:
            rx_bytes = 0
        try:
            tx_bytes = int(tx_str)
        except Exception:
            tx_bytes = 0

        last_hs_iso = None
        if latest > 0:
            last_hs_iso = datetime.fromtimestamp(latest, tz=timezone.utc).isoformat()

        peers.append({
            "peer_public_key": peer_public,
            "preshared_key": preshared,
            "endpoint": endpoint,
            "allowed_ips": allowed_ips,
            "latest_handshake_epoch": latest,
            "latest_handshake": last_hs_iso,
            "rx_bytes": rx_bytes,
            "tx_bytes": tx_bytes,
            "persistent_keepalive": keepalive,
            "server_iface": server_iface,
        })

    return peers


def _get_peer_status(server_iface: str, peer_pub: str) -> Optional[Dict[str, Any]]:
    """
    Busca un peer por public key usando el parser robusto.
    """
    for p in _wg_dump_peers(server_iface):
        if p.get("peer_public_key") == peer_pub:
            return p
    return None

# ── Modelos request/response ──────────────────────────────────

class MikrotikAutoReq(BaseModel):
    """
    Auto-registra un MikroTik como peer y devuelve su configuración cliente
    (Address/AllowedIPs/DNS + Peer), lista para pegar.
    """
    device_id: Optional[str] = Field(None, description="ID del dispositivo en tu DB (opcional pero recomendado)")
    owner_id: Optional[str] = Field(None, description="Owner del dispositivo (opcional)")
    # Si no envías estos, se usan los de ENV:
    endpoint_host: Optional[str] = Field(None, description="DynDNS/IP público del servidor WireGuard")
    endpoint_port: Optional[int] = Field(None, ge=1, le=65535, description="Puerto UDP del servidor WireGuard")
    server_public_key: Optional[str] = Field(None, description="Public key del servidor WireGuard")
    # Config del cliente:
    allowed_ips: List[str] = Field(default_factory=lambda: ["0.0.0.0/0"], description="Rutas del cliente")
    dns: Optional[str] = Field(None, description="DNS a configurar en el cliente (ej: 1.1.1.1)")
    # Permitir forzar interfaz servidor (raro cambiarlo)
    server_iface: Optional[str] = Field(None, description="Nombre de la interfaz wg del servidor (default wg0)")

class MikrotikAutoResp(BaseModel):
    interface_address: str         # Ej: "10.10.13.2/24"
    client_private_key: str        # PrivateKey generada para el cliente (MikroTik)
    client_public_key: str         # PublicKey derivada del cliente
    peer_public_key: str           # Server public key
    peer_endpoint: str             # Ej: "vpn.midominio.com:51820"
    peer_allowed_ips: str          # Ej: "0.0.0.0/0"
    server_interface: str          # ej: "wg0"
    verify_status_url: str         # endpoint para consultar handshake
    conf_ini: str                  # Snippet wg-quick/ini (clientes estándar)
    mikrotik_interface: str        # Nombre sugerido de interfaz WireGuard en RouterOS
    mikrotik_cli: str              # Script listo para pegar en RouterOS


# --- Utilidades IP/pool ya existentes ---

def _cidr_hosts(cidr: str) -> List[ipaddress.IPv4Address]:
    try:
        net4 = ipaddress.IPv4Network(cidr, strict=False)
    except Exception:
        raise HTTPException(status_code=400, detail=f"WG_POOL_CIDR debe ser IPv4. Recibido: '{cidr}'")
    return [h for h in net4.hosts()]

async def _get_used_addresses_from_db() -> Set[str]:
    used: Set[str] = set()
    try:
        if "database" in globals() and "devices_table" in globals():
            cols = getattr(devices_table.c, "wg_address", None)
            if cols is not None:
                query = sqlalchemy.select(devices_table.c.wg_address).where(
                    devices_table.c.wg_address.isnot(None)
                )
                rows = await database.fetch_all(query)
                for r in rows:
                    addr = str(r["wg_address"]).split("/")[0]
                    used.add(addr)
        return used
    except Exception as e:
        print(f"[WG-ALLOC] Aviso: no pude leer wg_address desde DB ({e}). Continúo sin DB.")
        return set()

async def _persist_assigned_address(device_id: Optional[str], owner_id: Optional[str], assigned_cidr: str) -> None:
    if not device_id or not owner_id:
        return
    try:
        if "database" in globals() and "devices_table" in globals():
            values = {}
            if getattr(devices_table.c, "wg_address", None) is not None:
                values["wg_address"] = assigned_cidr
            if getattr(devices_table.c, "updated_at", None) is not None:
                values["updated_at"] = datetime.now(timezone.utc)
            if not values:
                return
            query = (
                devices_table.update()
                .where(
                    (devices_table.c.id == device_id) &
                    (devices_table.c.owner_id == owner_id)
                )
                .values(**values)
            )
            await database.execute(query)
    except Exception as e:
        print(f"[WG-ALLOC] Aviso: no pude persistir wg_address en DB ({e}). Continúo igual.")

def _build_client_conf(address_cidr: str, dns: str, server_pub: str, endpoint: str, allowed_ips: List[str], client_priv: str) -> str:
    allowed = ", ".join(allowed_ips) if allowed_ips else "0.0.0.0/0"
    return (
        "[Interface]\n"
        f"PrivateKey = {client_priv}\n"
        f"Address = {address_cidr}\n"
        f"DNS = {dns}\n"
        "\n"
        "[Peer]\n"
        f"PublicKey = {server_pub}\n"
        f"AllowedIPs = {allowed}\n"
        f"Endpoint = {endpoint}\n"
        "PersistentKeepalive = 25\n"
    )
def _build_mikrotik_cli(
    iface_name: str,
    address_cidr: str,
    client_priv: str,
    server_pub: str,
    endpoint_host: str,
    endpoint_port: int,
    allowed_ips: List[str],
) -> str:
    """
    Genera comandos RouterOS (v7) para usar MikroTik como *cliente* WireGuard.
    Puntos clave:
      - Se configura Address en la interfaz (ej.: 10.10.13.2/24)
      - Allowed-Address en el peer = 0.0.0.0/0 (o lo que envíes)
      - route-distance=254 para NO tomar la ruta por defecto del router;
        de este modo no “pisás” el default route del cliente y
        podés hacer PBR/VRF sin romper el forwarding normal.
      - Persistent Keepalive a 25s
    """
    # Normalizar AllowedIPs (IPv4)
    allowed = [ip.strip() for ip in (allowed_ips or ["0.0.0.0/0"])]
    allowed_str = ",".join(allowed)

    # Algunos campos aceptan "0" (listen-port) para cliente sin puerto entrante
    return (
        f'/interface wireguard add name={iface_name} private-key="{client_priv}" listen-port=0\n'
        f'/ip address add address={address_cidr} interface={iface_name}\n'
        f'/interface wireguard peers add interface={iface_name} public-key="{server_pub}" '
        f'endpoint-address={endpoint_host} endpoint-port={endpoint_port} '
        f'allowed-address={allowed_str} persistent-keepalive=25s route-distance=254\n'
        # (Opcional recomendado si vas a sacar tráfico LAN por el túnel)
        # f'# /ip firewall nat add chain=srcnat action=masquerade out-interface={iface_name}\n'
        # (Opcional PBR: marcar rutas específicas y enrutar por {iface_name})
        # f'# /routing rule add action=lookup-only-in-table table=<tu_tabla> src-address=<LAN/CIDR>\n'
    )


# ──────────────────────────────────────────────────────────────

@app.post("/api/vpns/mikrotik-auto", response_model=MikrotikAutoResp)
async def mikrotik_auto_register(
    payload: MikrotikAutoReq = Body(...),
    creds: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
):
    """
    Flujo robusto:
    1) Genera keypair del cliente.
    2) Reserva Address libre del pool.
    3) Da de alta el peer en el servidor (wg set … peer …).
    4) Persiste la Address en DB (opcional, si la columna existe).
    5) Devuelve INI listo + URL para consultar estado de handshake.

    Si algo falla en (3) o (4), hace rollback del peer para no dejar basura.
    """

    # 1) Resolver parámetros
    pool_cidr = WG_POOL_CIDR
    server_pub = payload.server_public_key or WG_SERVER_PUBLIC_KEY
    if not server_pub:
        raise HTTPException(status_code=400, detail="Falta server_public_key (en request o ENV).")

    endpoint_host = payload.endpoint_host or WG_ENDPOINT_HOST
    endpoint_port = payload.endpoint_port or WG_ENDPOINT_PORT
    if not endpoint_host or not endpoint_port:
        raise HTTPException(status_code=400, detail="Falta endpoint del servidor (endpoint_host/port).")

    endpoint_str = f"{endpoint_host}:{endpoint_port}"
    dns_to_use = payload.dns or WG_DNS_DEFAULT
    allowed_ips = payload.allowed_ips or ["0.0.0.0/0"]
    server_iface = payload.server_iface or WG_INTERFACE

    # 2) Generar keypair cliente
    client_priv, client_pub = _wg_generate_keypair()

    # 3) Asignar Address libre del pool (IPv4 forzado)
    try:
        net4 = ipaddress.IPv4Network(pool_cidr, strict=False)
    except Exception:
        raise HTTPException(status_code=400, detail=f"WG_POOL_CIDR debe ser IPv4. Recibido: '{pool_cidr}'")

    all_hosts = list(net4.hosts())
    if not all_hosts:
        raise HTTPException(status_code=409, detail="El pool no tiene hosts disponibles")

    used = await _get_used_addresses_from_db()

    # por convención .1 es el servidor; evitamos asignarla
    server_ip = all_hosts[0]
    candidate = None
    for host in all_hosts:
        if host == server_ip:
            continue
        if str(host) not in used:
            candidate = host
            break

    if not candidate:
        raise HTTPException(status_code=409, detail="No hay direcciones libres en el pool")

    mask = net4.prefixlen
    client_address_cidr = f"{candidate}/{mask}"

    # 4) Alta del peer y manejo de rollback
    peer_created = False
    try:
        _wg_add_peer(server_iface, client_pub, client_address_cidr, allowed_ips)
        peer_created = True

        # 5) (Opcional) Persistir Address en DB — si falla, seguimos igual
        try:
            await _persist_assigned_address(payload.device_id, payload.owner_id, client_address_cidr)
        except Exception as e:
            print(f"[WG-AUTO] Aviso: no se pudo persistir en DB ({e}), continúo igual.")

    except Exception as e:
        # rollback si el peer ya se había creado
        if peer_created:
            try:
                _wg_remove_peer(server_iface, client_pub)
            except Exception as e2:
                print(f"[WG-ROLLBACK] No se pudo remover peer tras error: {e2!r}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Fallo al registrar peer: {e!r}")

    # 6) Construir respuesta / snippet INI
    conf_ini = _build_client_conf(
        address_cidr=client_address_cidr,
        dns=dns_to_use,
        server_pub=server_pub,
        endpoint=endpoint_str,
        allowed_ips=allowed_ips,
        client_priv=client_priv,
    )

    verify_url = f"/api/vpns/peer-status/{client_pub}"

        # --- nombre sugerido de interfaz MikroTik (estable y corto) ---
    # Evitamos caracteres no válidos y colisiones.
    mikrotik_iface = f"wg-m360-{uuid.uuid4().hex[:6]}"

    # --- script MikroTik listo para pegar ---
    mikrotik_cli = _build_mikrotik_cli(
        iface_name=mikrotik_iface,
        address_cidr=client_address_cidr,
        client_priv=client_priv,
        server_pub=server_pub,
        endpoint_host=endpoint_host,
        endpoint_port=endpoint_port,
        allowed_ips=allowed_ips,  # normalmente ["0.0.0.0/0"]
    )

    return MikrotikAutoResp(
        interface_address=client_address_cidr,
        client_private_key=client_priv,
        client_public_key=client_pub,
        peer_public_key=server_pub,
        peer_endpoint=endpoint_str,
        peer_allowed_ips=", ".join(allowed_ips),
        server_interface=server_iface,
        verify_status_url=verify_url,
        conf_ini=conf_ini,                 # clientes wg-quick (Windows, Linux, móviles)
        mikrotik_interface=mikrotik_iface, # nombre sugerido en RouterOS
        mikrotik_cli=mikrotik_cli,         # <- comandos listos para pegar en MikroTik
    )


# ──────────────────────────────────────────────────────────────
# 🔎 Endpoint de verificación de estado/handshake del peer
# ──────────────────────────────────────────────────────────────

@app.get("/api/vpns/peer-status/{peer_public_key}")
async def get_peer_status(peer_public_key: str, server_iface: str = Query(WG_INTERFACE)):
    st = _get_peer_status(server_iface, peer_public_key)
    if not st:
        return {
            "connected": False,
            "latest_handshake": None,
            "rx_bytes": 0,
            "tx_bytes": 0,
            "server_iface": server_iface,
        }

    # Conectado si hubo handshake en los últimos 180s
    connected = bool(
        st["latest_handshake_epoch"] and
        (datetime.now(timezone.utc).timestamp() - st["latest_handshake_epoch"] < 180)
    )

    return {
        "connected": connected,
        "latest_handshake": st["latest_handshake"],
        "rx_bytes": st["rx_bytes"],
        "tx_bytes": st["tx_bytes"],
        "server_iface": st["server_iface"],
        "allowed_ips_on_server": st.get("allowed_ips", ""),
        "endpoint": st.get("endpoint", ""),
    }


# ==========================================================
# Configuración general: SUPABASE / POSTGRES
# ==========================================================
RAW_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

def _session_valid(s: Optional[dict]) -> bool:
    """Valida que la sesión exista y no esté vencida."""
    if not s:
        return False
    created = s.get("created")
    if not created:
        return False
    return (datetime.now(timezone.utc) - created) < timedelta(seconds=SCAN_TTL_SECONDS)


# === Modelo para recibir datos escaneados ===
class ScanPayload(BaseModel):
    config_data: str

def _to_asyncpg_base_dsn(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # ✅ No tocar parámetros de query, asyncpg ignora los que no soporta.
    return url

ASYNC_DATABASE_URL = _to_asyncpg_base_dsn(RAW_DATABASE_URL)
IS_POSTGRES = ASYNC_DATABASE_URL.startswith("postgresql+asyncpg://")
print(f"[DB] DSN={ASYNC_DATABASE_URL}")

# --- SSL context para asyncpg ---
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

database = databases.Database(
    ASYNC_DATABASE_URL,
    ssl=ctx,
    min_size=1,
    max_size=2,
    timeout=30.0,
)
# ==========================================================
# Auth (Supabase JWT) – Compatibilidad HS256 + RS256
# ==========================================================
SUPABASE_PROJECT_REF = os.getenv("SUPABASE_PROJECT_REF")
if not SUPABASE_PROJECT_REF:
    raise RuntimeError("SUPABASE_PROJECT_REF no configurado (ej: abcd1234).")

SUPABASE_URL = os.getenv("SUPABASE_URL", f"https://{SUPABASE_PROJECT_REF}.supabase.co").rstrip("/")

# HS256 (legacy) – solo funciona si seteás SUPABASE_JWT_SECRET
SUPABASE_JWT_SECRET = (os.getenv("SUPABASE_JWT_SECRET", "").strip())

# RS256 (nuevo) – JWKS de Supabase
JWKS_URL = f"{SUPABASE_URL}/auth/v1/keys"
try:
    _jwks_client = jwt.PyJWKClient(JWKS_URL)
except Exception as e:
    _jwks_client = None
    print(f"[JWT] No se inicializó JWKS; se intentará HS256 si hay secreto. Motivo: {e}")

bearer = HTTPBearer(auto_error=False)


def _decode_hs256(token: str) -> Optional[dict]:
    if not SUPABASE_JWT_SECRET:
        return None
    try:
        return jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
            leeway=300,
        )
    except Exception as e:
        print(f"[JWT HS256] inválido: {e}")
        return None


def _decode_rs256(token: str) -> Optional[dict]:
    if _jwks_client is None:
        return None
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
            leeway=300,
        )
    except Exception as e:
        print(f"[JWT RS256] inválido: {e}")
        return None


def _owner_from_token(token: str) -> str | None:
    """Devuelve el sub (owner_id) o None si no se pudo validar."""
    try:
        hdr = jwt.get_unverified_header(token)
        print(f"[JWT DEBUG] Header recibido: alg={hdr.get('alg')} kid={hdr.get('kid')}")
    except Exception as e:
        print(f"[JWT DEBUG] no pude leer header: {e}")

    # 1) Intento HS256
    if SUPABASE_JWT_SECRET:
        payload = _decode_hs256(token)
        if payload:
            print(f"[JWT DEBUG] HS256 payload sub={payload.get('sub')}")
            return payload.get("sub")

    # 2) Intento RS256
    payload = _decode_rs256(token)
    if payload:
        print(f"[JWT DEBUG] RS256 payload sub={payload.get('sub')}")
        return payload.get("sub")

    return None


def _extract_token_from_request(request: Request, creds: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    # 1) Authorization header
    if creds and (creds.scheme or "").lower() == "bearer" and creds.credentials:
        return creds.credentials
    # 2) Query param (?token=)
    if "token" in request.query_params:
        return request.query_params.get("token")
    # 3) Cookie
    ck = request.cookies.get("sb-access-token")
    if ck:
        return ck
    return None


async def get_owner_id(request: Request, creds: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    token = _extract_token_from_request(request, creds)

    if token:
        owner_id = _owner_from_token(token)
        if owner_id:
            return owner_id

        # hint útil cuando el token es HS256 y falta la secret
        try:
            alg = jwt.get_unverified_header(token).get("alg")
            if alg == "HS256" and not SUPABASE_JWT_SECRET:
                print("[JWT HINT] Token HS256 pero SUPABASE_JWT_SECRET no está seteada o es incorrecta.")
        except Exception:
            pass

        raise HTTPException(status_code=401, detail="Token inválido o expirado.")

    raise HTTPException(status_code=401, detail="Falta token (Authorization Bearer / ?token / cookie).")


# Env y rutas para WireGuard (userspace/boringtun)
# ==========================================================

WG_ENV_BASE = {
    "WG_QUICK_USERSPACE_IMPLEMENTATION": "boringtun",
    "WG_ENDPOINT_RESOLUTION_RETRIES": "2",
    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
}

# ==========================================================
# Base de datos (SQLAlchemy)
# ==========================================================

metadata = sqlalchemy.MetaData()

credentials_table = sqlalchemy.Table(
    "credentials",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String, unique=True),
    sqlalchemy.Column("username", sqlalchemy.String),
    sqlalchemy.Column("password", sqlalchemy.String),
    sqlalchemy.Column("owner_id", sqlalchemy.String),  # UUID texto
)

devices_table = sqlalchemy.Table(
    "devices",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.String, primary_key=True),
    sqlalchemy.Column("client_name", sqlalchemy.String),
    sqlalchemy.Column("ip_address", sqlalchemy.String, unique=True),
    sqlalchemy.Column("mac_address", sqlalchemy.String),
    sqlalchemy.Column("node", sqlalchemy.String),
    sqlalchemy.Column("status", sqlalchemy.String),
    sqlalchemy.Column("credential_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("credentials.id"), nullable=True),
    sqlalchemy.Column("is_maestro", sqlalchemy.Boolean, default=False),
    sqlalchemy.Column("maestro_id", sqlalchemy.String, sqlalchemy.ForeignKey("devices.id"), nullable=True),
    sqlalchemy.Column("vpn_profile_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("vpn_profiles.id"), nullable=True),
    sqlalchemy.Column("owner_id", sqlalchemy.String),  # UUID texto
        # 👇 nuevas columnas usadas por la rotación/keepalive
    sqlalchemy.Column("last_auth_ok", sqlalchemy.DateTime, nullable=True),
    sqlalchemy.Column("last_auth_fail", sqlalchemy.DateTime, nullable=True),
    sqlalchemy.Column("rotations_count", sqlalchemy.Integer, nullable=True, server_default="0"),
)

monitors_table = sqlalchemy.Table(
    "monitors",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column(
        "device_id",
        sqlalchemy.String,
        sqlalchemy.ForeignKey("devices.id", ondelete="CASCADE"),
        unique=True,
    ),
    sqlalchemy.Column("owner_id", sqlalchemy.String),
)

sensors_table = sqlalchemy.Table(
    "sensors",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column(
        "monitor_id",
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey("monitors.id", ondelete="CASCADE"),
    ),
    sqlalchemy.Column("sensor_type", sqlalchemy.String),
    sqlalchemy.Column("name", sqlalchemy.String),
    sqlalchemy.Column("config", sqlalchemy.JSON),
    sqlalchemy.Column("owner_id", sqlalchemy.String),
)

ping_results_table = sqlalchemy.Table(
    "ping_results",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column(
        "sensor_id",
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey("sensors.id", ondelete="CASCADE"),
    ),
    sqlalchemy.Column("timestamp", sqlalchemy.DateTime, default=lambda: datetime.now(timezone.utc)),
    sqlalchemy.Column("latency_ms", sqlalchemy.Float),
    sqlalchemy.Column("status", sqlalchemy.String),
)

ethernet_results_table = sqlalchemy.Table(
    "ethernet_results",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column(
        "sensor_id",
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey("sensors.id", ondelete="CASCADE"),
    ),
    sqlalchemy.Column("timestamp", sqlalchemy.DateTime),
    sqlalchemy.Column("status", sqlalchemy.String),
    sqlalchemy.Column("speed", sqlalchemy.String),
    sqlalchemy.Column("rx_bitrate", sqlalchemy.String),
    sqlalchemy.Column("tx_bitrate", sqlalchemy.String),
)

settings_table = sqlalchemy.Table(
    "settings",
    metadata,
    sqlalchemy.Column("key", sqlalchemy.String, primary_key=True),
    sqlalchemy.Column("value", sqlalchemy.String),
)

notification_channels_table = sqlalchemy.Table(
    "notification_channels",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String, unique=True),
    sqlalchemy.Column("type", sqlalchemy.String),
    sqlalchemy.Column("config", sqlalchemy.JSON),
    sqlalchemy.Column("owner_id", sqlalchemy.String),
)

alert_history_table = sqlalchemy.Table(
    "alert_history",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column(
        "sensor_id",
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey("sensors.id", ondelete="CASCADE"),
    ),
    sqlalchemy.Column(
        "channel_id",
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey("notification_channels.id", ondelete="CASCADE"),
    ),
    sqlalchemy.Column("timestamp", sqlalchemy.DateTime, default=lambda: datetime.now(timezone.utc)),
    sqlalchemy.Column("details", sqlalchemy.String),
)

vpn_profiles_table = sqlalchemy.Table(
    "vpn_profiles",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String, unique=True),
    sqlalchemy.Column("config_data", sqlalchemy.Text),
    sqlalchemy.Column("check_ip", sqlalchemy.String),
    sqlalchemy.Column("is_default", sqlalchemy.Boolean, default=False),
    sqlalchemy.Column("owner_id", sqlalchemy.String),
)

# ==========================================================
# Inicialización de esquema en Postgres (async)
# ==========================================================

# Si querés correr create_all, seteá RUN_DB_MIGRATIONS=1 en el entorno
RUN_DB_MIGRATIONS = os.getenv("RUN_DB_MIGRATIONS", "0") == "1"

# ───────────────────── DB INIT & SHUTDOWN ─────────────────────

_db_started = False
_keepalive_task: Optional[asyncio.Task] = None

async def init_db():
    """
    Inicializa la conexión a Supabase una sola vez.
    """
    global _db_started
    if _db_started:
        print("[DB] init_db ya se ejecutó, skip")
        return

    try:
        await database.connect()
        print("[DB] Conexión a Supabase OK")
        _db_started = True
    except Exception as e:
        print(f"[DB] Error conectando a Supabase: {e!r}")
        raise


async def keep_db_alive():
    """
    Mantiene la conexión activa enviando SELECT 1 cada 5 min.
    """
    while True:
        try:
            await database.execute("SELECT 1;")
            print("[DB] keepalive OK")
        except Exception as e:
            print(f"[DB] keepalive error: {e}")
        await asyncio.sleep(300)


@app.on_event("startup")
async def startup():
    global _keepalive_task
    await init_db()
    if _keepalive_task is None:
        _keepalive_task = asyncio.create_task(keep_db_alive())
    # 🔹 Iniciar el loop global de keepalive RouterOS
    asyncio.create_task(keepalive_routeros_loop())        

    # lanzar tasks de sensores
    rows = await database.fetch_all(sensors_table.select())
    for s in rows:
        try:
            asyncio.create_task(launch_sensor_task(s["id"]))
        except Exception as e:
            print(f"[SENSORS] No se pudo lanzar {s['id']}: {e}")


@app.on_event("shutdown")
async def on_shutdown():
    # cerrar pools de RouterOS
    for pool in list(connection_pools.values()):
        try:
            pool.disconnect()
        except Exception:
            pass

    # cancelar tasks
    for task_id in list(running_tasks.keys()):
        try:
            running_tasks[task_id].cancel()
        except Exception:
            pass

    # bajar todas las VPN
    await teardown_all_vpns()

    # cerrar DB
    try:
        await database.disconnect()
        print("[DB] Conexión a Supabase cerrada.")
    except Exception as e:
        print(f"[DB] Error al cerrar conexión: {e}")

# ==========================================================
# Modelos Pydantic
# ==========================================================

class CredentialCreate(BaseModel):
    name: str
    username: str
    password: str

class CredentialResponse(BaseModel):
    id: int
    name: str
    username: str

class ManualDevice(BaseModel):
    client_name: str
    ip_address: str
    mac_address: Optional[str] = ""
    node: Optional[str] = ""
    maestro_id: Optional[str] = None
    vpn_profile_id: Optional[int] = None

class MonitorCreate(BaseModel):
    device_id: str

class SensorCreate(BaseModel):
    monitor_id: int
    sensor_type: str
    name: str
    config: Dict[str, Any]

class SensorUpdate(BaseModel):
    name: str
    config: Dict[str, Any]

class NotificationChannelCreate(BaseModel):
    name: str
    type: str
    config: Dict[str, Any]

class TelegramToken(BaseModel):
    bot_token: str

class VpnProfileCreate(BaseModel):
    name: str
    config_data: str
    check_ip: str

class VpnProfileUpdate(BaseModel):
    name: Optional[str] = None
    config_data: Optional[str] = None
    check_ip: Optional[str] = None
    is_default: Optional[bool] = None

class VpnAssociation(BaseModel):
    vpn_profile_id: Optional[int]

class IsolatedConnectionTest(BaseModel):
    ip_address: str
    vpn_profile_id: Optional[int] = None
    maestro_id: Optional[str] = None

# ==========================================================
# Utilidades de shell / WireGuard
# ==========================================================

async def run_command(command: List[str], env: Optional[Dict[str, str]] = None, *, quiet: bool = False) -> Tuple[bool, str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    def sync_run() -> subprocess.CompletedProcess:
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            env=merged_env,
            startupinfo=startupinfo,
        )

    try:
        result = await asyncio.to_thread(sync_run)
        if result.returncode == 0:
            return True, result.stdout
        else:
            err = result.stderr or result.stdout
            if not quiet:
                print(f"Error en comando: {command} -> {err}\n")
            return False, err
    except FileNotFoundError:
        msg = f"Error: comando no encontrado: {command[0]}"
        if not quiet:
            print(msg)
        return False, msg
    except Exception as e:
        msg = f"Error inesperado ejecutando {command}: {e}"
        if not quiet:
            print(msg)
        return False, msg


async def wg_cmd(args: List[str]) -> Tuple[bool, str]:
    return await run_command(args, env=WG_ENV_BASE)

async def ip_quiet(args: list[str]) -> tuple[bool, str]:
    # NO loguea errores y además trata como "OK" los típicos de idempotencia
    ok, out = await run_command(args, env=WG_ENV_BASE, quiet=True)
    if ok:
        return True, out
    s = (out or "")
    benignos = (
        "No such file or directory",
        "No such process",
        "File exists",
        "RTNETLINK answers: File exists",
        "FIB table does not exist",
        "Cannot find device",
        "not found in table",
    )
    if any(b in s for b in benignos):
        return True, out
    return False, out



VPN_STATE: Dict[int, Dict[str, Any]] = {}

# --- LOCKS por perfil para evitar carreras de wg-quick up ---
_WG_PROFILE_LOCKS: Dict[int, asyncio.Lock] = {}

# --- Prioridad base para la regla "from <src>" (separada de las "to <dest>") ---
FROM_RULE_BASE = 11000
def _from_rule_priority(profile_id: int) -> int:
    return FROM_RULE_BASE + int(profile_id)

async def _iface_ipv4(iface: str) -> Optional[str]:
    ok, out = await run_command(
        ["sh", "-lc", f"ip -4 -o addr show dev {iface} | awk '{{print $4}}' | cut -d/ -f1 | head -n1"],
        env=WG_ENV_BASE, quiet=True
    )
    if ok:
        ip = (out or "").strip()
        return ip or None
    return None

async def _pbr_ensure_rule_from_src(profile_id: int, iface: str) -> None:
    """
    Agrega 'ip rule add pref <X> from <TUNIP>/32 lookup <tabla>' si falta.
    Idempotente: no duplica si ya existe.
    """
    tun_ip = await _iface_ipv4(iface)
    if not tun_ip:
        print(f"[VPN] WARN: no pude leer IP del túnel en {iface} para regla 'from'")
        return
    tbl = _policy_table_id(profile_id)
    pref = _from_rule_priority(profile_id)

    ok, rules = await run_command(["ip", "rule", "show"], env=WG_ENV_BASE, quiet=True)
    if ok and f"from {tun_ip} lookup {tbl}" in (rules or ""):
        return

    await ip_quiet(["ip", "rule", "add", "pref", str(pref), "from", f"{tun_ip}/32", "lookup", str(tbl)])

async def _pbr_del_rule_from_src(profile_id: int) -> None:
    """Borra la regla 'from <tunip>' por prioridad (pref)."""
    pref = _from_rule_priority(profile_id)
    await ip_quiet(["ip", "rule", "del", "pref", str(pref)])



def _iface_name_for_profile(profile_id: int) -> str:
    return f"m360-p{profile_id}"


def _conf_path_for_profile(profile_id: int) -> str:
    return os.path.join(tempfile.gettempdir(), f"{_iface_name_for_profile(profile_id)}.conf")


def validate_wg_config(raw: str) -> None:
    """
    Valida la estructura básica de un archivo de configuración WireGuard.
    Lanza HTTPException(400) si falta algún campo esencial.
    """
    if not raw or "[Interface]" not in raw or "[Peer]" not in raw:
        raise HTTPException(status_code=400, detail="Config inválido: falta [Interface] o [Peer].")

    if not re.search(r"(?mi)^PrivateKey\s*=\s*\S+", raw):
        raise HTTPException(status_code=400, detail="Config inválido: falta PrivateKey en [Interface].")

    if not re.search(r"(?mi)^Address\s*=\s*\d+\.\d+\.\d+\.\d+/\d+", raw):
        raise HTTPException(status_code=400, detail="Config inválido: falta Address IPv4 en [Interface].")

    if not re.search(r"(?mi)^\[Peer\]", raw):
        raise HTTPException(status_code=400, detail="Config inválido: falta bloque [Peer].")

    if not re.search(r"(?mi)^PublicKey\s*=\s*\S+", raw):
        raise HTTPException(status_code=400, detail="Config inválido: falta PublicKey en [Peer].")

    if not re.search(r"(?mi)^AllowedIPs\s*=\s*\S+", raw):
        raise HTTPException(status_code=400, detail="Config inválido: falta AllowedIPs en [Peer].")
    

def _normalize_wg_config(raw: str) -> str:
    """
    Normaliza el config de WireGuard para evitar errores:
      - Elimina DNS
      - Se queda solo con la Address IPv4
      - Simplifica AllowedIPs
    """
    out = []
    for ln in raw.splitlines():
        l = ln.strip()
        if not l:
            continue

        # 1) Quitar DNS
        if l.lower().startswith("dns="):
            continue

        # 2) Normalizar Address: solo IPv4
        if l.lower().startswith("address"):
            parts = [p.strip() for p in l.split("=", 1)[1].split(",")]
            ipv4 = next((p for p in parts if "." in p), parts[0])
            out.append(f"Address = {ipv4}")
            continue

        # 3) Normalizar AllowedIPs
        if l.lower().startswith("allowedips"):
            parts = [p.strip() for p in l.split("=", 1)[1].split(",")]
            if "0.0.0.0/32" in parts:
                out.append("AllowedIPs = 0.0.0.0/0")
            elif "0.0.0.0/0" in parts:
                out.append("AllowedIPs = 0.0.0.0/0")
            else:
                ipv4_only = [p for p in parts if "." in p]
                if ipv4_only:
                    out.append("AllowedIPs = " + ",".join(ipv4_only))
            continue

        # 4) Mantener el resto tal cual
        out.append(ln)

    return "\n".join(out) + "\n"


async def _iface_exists_up(iface: str) -> bool:
    ok, out = await wg_cmd(["ip", "link", "show", iface])
    if not ok:
        return False
    return "state UP" in out or "UP" in out


# ==========================================================
# Policy Based Routing por perfil WG (tablas/reglas por destino)
# ==========================================================

POLICY_TABLE_BASE = 10000     # tabla = 10000 + profile_id
RULE_PRIO_BASE    = 10000     # prioridad = 10000 + profile_id

def _policy_table_id(profile_id: int) -> int:
    return POLICY_TABLE_BASE + profile_id

def _rule_priority(profile_id: int) -> int:
    return RULE_PRIO_BASE + profile_id

def _inject_table_off(raw: str) -> str:
    """
    Inserta 'Table = off' en [Interface] si no está presente.
    No toca AllowedIPs (podés dejar 0.0.0.0/0).
    """
    if not raw:
        return raw
    lines = raw.splitlines()
    out = []
    in_iface = False
    has_table = False
    for ln in lines:
        l = ln.strip()
        if l.startswith("[") and l.endswith("]"):
            if in_iface and not has_table:
                out.append("Table = off")
            in_iface = (l.lower() == "[interface]")
            has_table = False
            out.append(ln)
            continue
        if in_iface and l.lower().startswith("table"):
            has_table = True
        out.append(ln)
    if in_iface and not has_table:
        out.append("Table = off")
    return "\n".join(out) + "\n"

async def _pbr_ensure_table(profile_id: int, iface: str):
    """
    Crea/actualiza la tabla de rutas dedicada del perfil con default por el iface.
    """
    tbl = _policy_table_id(profile_id)
    await ip_quiet(["ip", "route", "replace", "default", "dev", iface, "table", str(tbl)])
    return tbl

# ==========================================================
# VRF por perfil (aislamiento por túnel al estilo BTH)
# ==========================================================

def _vrf_name_for_profile(profile_id: int) -> str:
    # Ej: m360-vrfp12
    return f"m360-vrfp{profile_id}"

async def _ensure_vrf(profile_id: int, iface: str) -> Optional[str]:
    """
    Crea/asegura un VRF dedicado para este perfil y asocia la interfaz WG.
    Idempotente y tolerante a kernels sin soporte VRF (en ese caso, no rompe).
    Devuelve el nombre del VRF si quedó activo, o None si no se pudo.
    """
    vrf = _vrf_name_for_profile(profile_id)
    table_id = _policy_table_id(profile_id)  # reutilizamos la misma tabla dedicada que ya usás para PBR

    # 1) Crear VRF (si no existe) y levantarlo
    ok, _ = await ip_quiet(["ip", "link", "add", vrf, "type", "vrf", "table", str(table_id)])
    ok2, _ = await ip_quiet(["ip", "link", "set", vrf, "up"])
    if not (ok or ok2):
        # Si no hay soporte VRF o falló, lo dejamos pasar (seguís con PBR como hasta ahora)
        print(f"[VRF] Advertencia: no se pudo crear/levantar VRF '{vrf}' (kernel sin soporte o error). Se sigue sin VRF.")
        return None

    # 2) Asociar la interfaz WireGuard al VRF (idempotente)
    await ip_quiet(["ip", "link", "set", iface, "master", vrf])

    # 3) Asegurar reglas mínimas en la tabla del VRF:
    #    - Ruta por defecto por el propio iface en esa tabla (coherente con tu PBR actual)
    await ip_quiet(["ip", "route", "replace", "default", "dev", iface, "table", str(table_id)])

    #    - Regla para que todo lo que ENTRE por el túnel use la tabla del VRF
    #      (esto ayuda a que el tráfico de retorno quede aislado)
    await ip_quiet(["ip", "rule", "add", "iif", iface, "table", str(table_id)])

    print(f"[VRF] VRF '{vrf}' activo para {iface} (tabla {table_id})")
    return vrf

async def _vrf_exec(profile_id: int, cmd: List[str]) -> Tuple[bool, str]:
    """
    Ejecuta un comando 'dentro' del VRF del perfil, si existe.
    Útil para ping/traceroute/SNMP aislados:
      await _vrf_exec(pid, ["ping", "-c", "2", "192.168.216.2"])
    """
    vrf = _vrf_name_for_profile(profile_id)
    # Probar que el VRF exista; si no, ejecutar plano
    ok, _ = await run_command(["ip", "link", "show", vrf], env=WG_ENV_BASE, quiet=True)
    if not ok:
        return await run_command(cmd, env=WG_ENV_BASE, quiet=False)
    return await run_command(["ip", "vrf", "exec", vrf] + cmd, env=WG_ENV_BASE, quiet=False)

# ───────────────────────────────────────────────────────────
#   REFCOUNTS por (perfil, IP) para reglas y rutas host
# ───────────────────────────────────────────────────────────
def _state_for(profile_id: int) -> dict:
    st = VPN_STATE.setdefault(profile_id, {})
    st.setdefault("dest_rule_refs", {})   # ip -> int
    st.setdefault("host_route_refs", {})  # ip -> int
    return st

async def _pbr_add_rule_to_dest(profile_id: int, dest_ip: str):
    st = _state_for(profile_id)
    refs: Dict[str, int] = st["dest_rule_refs"]
    cnt = refs.get(dest_ip, 0)
    tbl = _policy_table_id(profile_id)
    prio = _rule_priority(profile_id)
    if cnt == 0:
        # idempotente: primero intento borrar silencioso, luego agrego
        await ip_quiet(["ip", "rule", "del", "to", dest_ip, "lookup", str(tbl)])
        await ip_quiet(["ip", "rule", "add", "to", dest_ip, "lookup", str(tbl), "priority", str(prio)])
    refs[dest_ip] = cnt + 1

async def _pbr_del_rule_to_dest(profile_id: int, dest_ip: str):
    st = _state_for(profile_id)
    refs: Dict[str, int] = st["dest_rule_refs"]
    cnt = refs.get(dest_ip, 0)
    tbl = _policy_table_id(profile_id)
    if cnt <= 1:
        await ip_quiet(["ip", "rule", "del", "to", dest_ip, "lookup", str(tbl)])
        refs.pop(dest_ip, None)
    else:
        refs[dest_ip] = cnt - 1

async def _pin_host_route(profile_id: int, ip: str, iface: str):
    """
    Agrega/asegura una ruta host específica hacia 'ip' vía 'iface'
    en la tabla del perfil. Con refcount para no pisarnos entre tasks.
    """
    st = _state_for(profile_id)
    refs: Dict[str, int] = st["host_route_refs"]
    cnt = refs.get(ip, 0)
    tbl = _policy_table_id(profile_id)
    if cnt == 0:
        await ip_quiet(["ip", "route", "replace", ip, "dev", iface, "table", str(tbl)])
        print(f"[VPN] pin host {ip} -> iface={iface} tbl={tbl}")
    refs[ip] = cnt + 1

async def _unpin_host_route(profile_id: int, ip: str):
    """
    Elimina la ruta host específica cuando el refcount llega a 0.
    """
    st = _state_for(profile_id)
    refs: Dict[str, int] = st["host_route_refs"]
    cnt = refs.get(ip, 0)
    tbl = _policy_table_id(profile_id)
    if cnt <= 1:
        await ip_quiet(["ip", "route", "del", ip, "table", str(tbl)])
        refs.pop(ip, None)
        print(f"[VPN] unpin host {ip} tbl={tbl}")
    else:
        refs[ip] = cnt - 1

async def _pbr_clear_all(profile_id: int):
    """
    Limpieza completa de la tabla/reglas del perfil.
    Útil cuando la VPN cae a refcount 0.
    """
    st = _state_for(profile_id)

    # Borrar todas las reglas 'to <dest>' que sepamos
    for ip in list(st["dest_rule_refs"].keys()):
        try:
            await ip_quiet(["ip", "rule", "del", "to", ip, "lookup", str(_policy_table_id(profile_id))])
        except Exception:
            pass
    st["dest_rule_refs"] = {}

    # Flush de rutas de la tabla y vaciar refcounts de host
    await ip_quiet(["ip", "route", "flush", "table", str(_policy_table_id(profile_id))])
    st["host_route_refs"] = {}

async def ensure_vpn_up(profile_id: int) -> str:
    iface = _iface_name_for_profile(profile_id)
    lock = _WG_PROFILE_LOCKS.setdefault(profile_id, asyncio.Lock())

    async with lock:
        st = VPN_STATE.get(profile_id)

        # Reuse si ya está arriba
        if st and st.get("up") and await _iface_exists_up(iface):
            # Reforzar idempotentemente PBR base (tabla + regla from)
            await _pbr_ensure_table(profile_id, iface)
            await _pbr_ensure_rule_from_src(profile_id, iface)
            # VRF: aislar el túnel (si el kernel lo soporta). No rompe si falla.
            await _ensure_vrf(profile_id, iface)


            st["refcount"] = st.get("refcount", 0) + 1
            VPN_STATE[profile_id] = st
            print(f"[VPN] reuse {iface} (perfil {profile_id}) ref={st['refcount']}")
            return iface

        # Cargar perfil
        vpn = await database.fetch_one(
            vpn_profiles_table.select().where(vpn_profiles_table.c.id == profile_id)
        )
        if not vpn:
            raise HTTPException(status_code=404, detail=f"Perfil VPN {profile_id} no encontrado")

        conf_path = _conf_path_for_profile(profile_id)
        try:
            with open(conf_path, "w") as f:
                raw_cfg = vpn["config_data"]
                f.write(_inject_table_off(raw_cfg))
            os.chmod(conf_path, 0o600)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"No se pudo escribir config WG: {e}")

        # Levantar wg-quick (tolerante a 'already exists')
        t_wg = time.monotonic()
        ok, out = await wg_cmd(["wg-quick", "up", conf_path])
        print(f"[VPN] wg-quick up dt={(time.monotonic()-t_wg)*1000:.1f}ms iface={iface} ok={ok}")
        if not ok:
            ok_show, _ = await wg_cmd(["wg", "show", iface])
            if not ok_show:
                await wg_cmd(["wg-quick", "down", conf_path])
                t_wg2 = time.monotonic()
                ok2, out2 = await wg_cmd(["wg-quick", "up", conf_path])
                print(f"[VPN] wg-quick up (retry) dt={(time.monotonic()-t_wg2)*1000:.1f}ms ok={ok2}")
                if not ok2:
                    raise HTTPException(status_code=500, detail=f"No se pudo activar túnel WG: {out2 or out}")
            # si ok_show == True, seguimos como éxito (caso 'already exists')

        # PBR base: tabla con default dev y regla "from <tunip>"
        await _pbr_ensure_table(profile_id, iface)
        await _pbr_ensure_rule_from_src(profile_id, iface)

        # Esperar UP
        for _ in range(30):
            if await _iface_exists_up(iface):
                st2 = VPN_STATE.get(profile_id) or {}
                st2.update({
                    "iface": iface,
                    "conf_path": conf_path,
                    "refcount": st2.get("refcount", 0) + 1,
                    "up": True,
                })
                VPN_STATE[profile_id] = st2
                print(f"[VPN] UP {iface} (perfil {profile_id})")
                return iface
            await asyncio.sleep(0.1)

        raise HTTPException(status_code=500, detail=f"Interfaz {iface} no está UP tras levantar WG")


async def release_vpn(profile_id: int):
    st = VPN_STATE.get(profile_id)
    if not st:
        return
    st["refcount"] = max(0, st.get("refcount", 0) - 1)
    VPN_STATE[profile_id] = st
    if st["refcount"] == 0:
        # limpiamos reglas y tabla del perfil
        try:
            await _pbr_clear_all(profile_id)
        except Exception:
            pass
        try:
            await _pbr_del_rule_from_src(profile_id)
        except Exception:
            pass

async def teardown_all_vpns():
    for pid, st in list(VPN_STATE.items()):
        conf = st.get("conf_path")
        if conf and os.path.exists(conf):
            await wg_cmd(["wg-quick", "down", conf])
            try:
                os.remove(conf)
            except Exception:
                pass
            try:
                await _pbr_clear_all(pid)          # 👈 flush de reglas 'to' y tabla
            except Exception:
                pass
            try:
                await _pbr_del_rule_from_src(pid)  # 👈 borra 'from <tunip>'
            except Exception:
                pass
        VPN_STATE[pid]["up"] = False
        print(f"[VPN] DOWN {st.get('iface')} (perfil {pid})")


# ==========================================================
# Utilidades de conectividad / Mikrotik
# ==========================================================

async def tcp_port_reachable(ip: str, port: int, timeout_s: float = 1.5) -> bool:
    def sync_try():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout_s)
            try:
                s.connect((ip, port))
                return True
            except Exception:
                return False
    return await asyncio.to_thread(sync_try)

async def test_and_get_credential_id(
    ip_address: str,
    owner_id: str,
    *,
    per_cred_timeout: float = 3.0,
    overall_timeout: float = 8.0,
) -> Optional[int]:
    """
    Intenta loguear a Mikrotik (API puerto 8728) probando las credenciales del owner.
    - Evita bloquear el event-loop ejecutando el login en un thread.
    - Timeout por credencial (per_cred_timeout) y total (overall_timeout).
    Devuelve el credential_id que funcionó o None.
    """
    run_id = uuid.uuid4().hex[:8]
    t0 = time.time()

    # Traer credenciales del owner
    all_creds = await database.fetch_all(
        credentials_table.select().where(credentials_table.c.owner_id == owner_id)
    )
    n_creds = len(all_creds)
    print(f"[REACH] >>> inicio test_and_get_credential_id ip={ip_address} owner={owner_id} creds={n_creds} per_cred={per_cred_timeout}s overall={overall_timeout}s")

    if n_creds == 0:
        print("[REACH] No hay credenciales configuradas para este owner.")
        return None

    # Chequeo rápido de puerto para cortar temprano si está cerrado
    if not await tcp_port_reachable(ip_address, 8728, timeout_s=1.5):
        print(f"[REACH] {ip_address}:8728 inalcanzable (puerto cerrado o host caído)")
        return None

    # Función sincrónica que hace el login y lectura mínima
    def _login_once_sync(user: str, pwd: str) -> bool:
        conn = None
        try:
            # NOTA: no pasamos kwargs raros para no romper compat;
            # el timeout lo manejamos por afuera (wait_for + to_thread)
            conn = routeros_api.RouterOsApiPool(
                ip_address,
                username=user,
                password=pwd,
                port=8728,
                plaintext_login=True,
                use_ssl=False,
            )
            api = conn.get_api()
            # Llamado mínimo que confirma login OK
            api.get_resource("/system/identity").get()
            return True
        finally:
            if conn:
                try:
                    conn.disconnect()
                except Exception:
                    pass

    # Límite total
    try:
        async with asyncio.timeout(overall_timeout):
            for cred in all_creds:
                cname = cred["name"]
                cuser = cred["username"]
                print(f"[REACH]   -> probando cred='{cname}' user='{cuser}'")

                try:
                    ok = await asyncio.wait_for(
                        asyncio.to_thread(_login_once_sync, cuser, cred["password"]),
                        timeout=per_cred_timeout,
                    )
                    if ok:
                        dt = (time.time() - t0) * 1000
                        print(f"[REACH] ¡Éxito con cred='{cname}' en {dt:.1f}ms!")
                        return cred["id"]
                except asyncio.TimeoutError:
                    print(f"[REACH] Timeout con cred='{cname}' en {ip_address}")
                except routeros_api.exceptions.RouterOsApiConnectionError as e:
                    print(f"[REACH] Fallo conexión cred='{cname}' -> {e}")
                except Exception as e:
                    print(f"[REACH] Error inesperado cred='{cname}': {e}")

    except TimeoutError:
        print(f"[REACH] Timeout total overall={overall_timeout}s")

    print(f"[REACH] Ninguna credencial válida para {ip_address}.")
    return None

# ==========================================================
# WebSocket manager para escaneo remoto (NUEVO)
# ==========================================================
class ScanConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        print(f"[SCAN WS] Conectado: {session_id}")

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            print(f"[SCAN WS] Desconectado: {session_id}")

    async def send_config_data(self, session_id: str, config_data: str):
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await websocket.send_text(json.dumps({"type": "scan_result", "data": config_data}))
            print(f"[SCAN WS] Datos enviados a: {session_id}")
            return True
        print(f"[SCAN WS] Error: Sesión no encontrada para enviar datos: {session_id}")
        return False

scan_manager = ScanConnectionManager()

# Modelo para el payload del celular
class ScanData(BaseModel):
    config_data: str


# ==========================================================
# WebSocket broadcast manager (por owner) — DEBUG EXTENDIDO
# ==========================================================
class ConnectionManager:
    def __init__(self):
        # guardamos (websocket, owner_id_normalizado)
        self.active: Set[Tuple[WebSocket, str]] = set()

    async def connect(self, websocket: WebSocket, owner_id: str):
        oid = (str(owner_id) if owner_id is not None else "").strip().lower()
        await websocket.accept()
        self.active.add((websocket, oid))
        # por defecto, sin suscripciones específicas hasta que el cliente mande un mensaje
        websocket.scope["subs"] = set()
        print(f"[MANAGER] connect owners={len(self.active)} -> {oid}")

    def disconnect(self, websocket: WebSocket):
        removed = False
        for item in list(self.active):
            ws, _oid = item
            if ws is websocket:
                self.active.remove(item)
                removed = True
        if removed:
            print(f"[MANAGER] disconnect owners={len(self.active)}")

    async def broadcast_for(self, owner_id: str, message: str):
        """Primero intenta emitir por owner. Si nadie lo recibe (p.ej. owner legacy),
        hace fallback por suscripción: entrega a sockets con subscribe_all (subs=None)
        o que estén suscriptos explícitamente al sensor_id del payload.
        """
        target = (str(owner_id) if owner_id is not None else "").strip().lower()
        sent = mismatches = errs = 0

        for (ws, oid) in list(self.active):
            if oid != target:
                mismatches += 1
                continue
            try:
                await ws.send_text(message)
                sent += 1
            except Exception as e:
                errs += 1
                try:
                    self.active.remove((ws, oid))
                except Exception:
                    pass

        # Fallback si no hubo entregas por owner
        if sent == 0:
            sid = None
            try:
                payload = json.loads(message)
                sid = payload.get("sensor_id", None)
            except Exception:
                sid = None

            if sid is not None:
                sent_fb = errs_fb = 0
                for (ws, oid) in list(self.active):
                    subs = ws.scope.get("subs", set())
                    try:
                        # subscribe_all => subs is None
                        if subs is None or (isinstance(subs, set) and (len(subs) == 0 or sid in subs)):
                            await ws.send_text(message)
                            sent_fb += 1
                    except Exception:
                        errs_fb += 1
                        try:
                            self.active.remove((ws, oid))
                        except Exception:
                            pass
                print(f"[MANAGER] broadcast_fallback sid={sid} owner={target} sent={sent_fb} errs={errs_fb}")

        print(f"[MANAGER] broadcast_result owner={target} sent={sent} mismatch={mismatches} errors={errs}")

manager = ConnectionManager()
running_tasks: Dict[int, asyncio.Task] = {}
connection_pools: Dict[str, routeros_api.RouterOsApiPool] = {}

# ==========================================================
# Rotación automática de credenciales (estado + utilidades)
# ==========================================================

# Cooldown para no martillar (por IP)
ROTATION_COOLDOWN_SECONDS = 180  # 3 minutos

# Estado de rotación por IP (para evitar carreras y respetar cooldown)
_rotation_last_try: Dict[str, float] = {}      # ip -> epoch seconds del último intento
_ROTATE_LOCKS: Dict[str, asyncio.Lock] = {}    # ip -> lock

async def _emit_credential_rotated(
    *,
    owner_id: str,
    device_id: str,
    device_ip: str,
    old_credential_id: Optional[int],
    new_credential_id: Optional[int],
    ok: bool,
    reason: Optional[str] = None,
) -> None:
    """
    Emite un evento WS informativo cuando se reasigna (o falla) la rotación de credenciales.
    """
    payload = {
        "type": "device_credential_rotated",
        "device_id": device_id,
        "ip_address": device_ip,
        "old_credential_id": old_credential_id,
        "new_credential_id": new_credential_id,
        "ok": ok,
        "reason": reason,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await manager.broadcast_for(owner_id, json.dumps(payload))
    except Exception as e:
        print(f"[ROTATE] broadcast error: {e}")

async def rotate_device_credentials_on_auth_failure(device_ip: str, owner_id: str) -> Optional[int]:
    """
    Cuando se detecta fallo de autenticación contra 'device_ip', intenta:
      1) Respetar cooldown y serializar con lock por IP.
      2) Probar todas las credenciales del owner (test_and_get_credential_id).
      3) Si encuentra una distinta a la actual, actualizar devices.credential_id.
      4) Invalidar/reciclar pool en connection_pools para reabrir con la nueva.
      5) Emitir evento WS 'device_credential_rotated'.
      6) Registrar auditoría en DB (ok/fail/contador).
    """
    now = time.time()
    last = _rotation_last_try.get(device_ip, 0.0)
    if now - last < ROTATION_COOLDOWN_SECONDS:
        print(f"[ROTATE] cooldown activo para {device_ip} ({int(now - last)}s)")
        return None

    lock = _ROTATE_LOCKS.setdefault(device_ip, asyncio.Lock())
    async with lock:
        now2 = time.time()
        last2 = _rotation_last_try.get(device_ip, 0.0)
        if now2 - last2 < ROTATION_COOLDOWN_SECONDS:
            print(f"[ROTATE] (locked) cooldown activo para {device_ip} ({int(now2 - last2)}s)")
            return None
        _rotation_last_try[device_ip] = now2

        dev = await database.fetch_one(
            devices_table.select().where(
                (devices_table.c.ip_address == device_ip) &
                (devices_table.c.owner_id == owner_id)
            )
        )
        if not dev:
            print(f"[ROTATE] device no encontrado para ip={device_ip} owner={owner_id}")
            return None

        device_id = dev["id"]
        old_cred_id: Optional[int] = dev["credential_id"]

        try:
            new_cred_id = await test_and_get_credential_id(
                device_ip, owner_id, per_cred_timeout=3.0, overall_timeout=8.0
            )
        except Exception as e:
            print(f"[ROTATE] error en test_and_get_credential_id: {e}")
            await _emit_credential_rotated(
                owner_id=owner_id,
                device_id=device_id,
                device_ip=device_ip,
                old_credential_id=old_cred_id,
                new_credential_id=None,
                ok=False,
                reason=f"error_test:{e}",
            )
            return None

        if not new_cred_id:
            # No se encontró ninguna válida → registrar fallo
            await database.execute(
                devices_table.update()
                .where(
                    (devices_table.c.id == device_id) &
                    (devices_table.c.owner_id == owner_id)
                )
                .values(last_auth_fail=datetime.now(timezone.utc))
            )

            await _emit_credential_rotated(
                owner_id=owner_id,
                device_id=device_id,
                device_ip=device_ip,
                old_credential_id=old_cred_id,
                new_credential_id=None,
                ok=False,
                reason="no_valid_credentials",
            )
            print(f"[ROTATE] no hay credenciales válidas para {device_ip}")
            return None

        if old_cred_id == new_cred_id:
            print(f"[ROTATE] credencial vigente sigue siendo válida ip={device_ip} cred_id={new_cred_id}")
            await database.execute(
                devices_table.update()
                .where(
                    (devices_table.c.id == device_id) &
                    (devices_table.c.owner_id == owner_id)
                )
                .values(last_auth_ok=datetime.now(timezone.utc))
            )
            return new_cred_id

        # ✅ Nueva credencial válida → actualizar DB y auditoría
        try:
            await database.execute(
                devices_table.update()
                .where(
                    (devices_table.c.id == device_id) &
                    (devices_table.c.owner_id == owner_id)
                )
                .values(
                    credential_id=new_cred_id,
                    last_auth_ok=datetime.now(timezone.utc),
                    rotations_count=sqlalchemy.text("COALESCE(rotations_count,0)+1")
                )
            )
        except Exception as e:
            print(f"[ROTATE] error actualizando devices.credential_id: {e}")
            await _emit_credential_rotated(
                owner_id=owner_id,
                device_id=device_id,
                device_ip=device_ip,
                old_credential_id=old_cred_id,
                new_credential_id=None,
                ok=False,
                reason=f"db_error:{e}",
            )
            return None

        # Invalidar pool existente y forzar reconexión con nueva credencial
        pool = connection_pools.get(device_ip)
        if pool:
            try:
                pool.disconnect()
            except Exception:
                pass
            connection_pools.pop(device_ip, None)

        await _emit_credential_rotated(
            owner_id=owner_id,
            device_id=device_id,
            device_ip=device_ip,
            old_credential_id=old_cred_id,
            new_credential_id=new_cred_id,
            ok=True,
            reason="rotated",
        )
        print(f"[ROTATE] rotación OK ip={device_ip} old={old_cred_id} new={new_cred_id}")
        return new_cred_id

# ==========================================================
# Alertas y estado
# ==========================================================

last_alert_times: Dict[Tuple[int, str], datetime] = {}
last_known_statuses: Dict[int, Dict[str, Any]] = {}

# 👇 NUEVO: contadores de fallos consecutivos por (sensor_id, tipo_alerta)
alert_fail_counters: Dict[Tuple[int, str], int] = {}


async def send_webhook_notification(config: dict, message_details: dict):
    url = config.get("url")
    if not url:
        return
    text = (
        f"🚨 **Alerta: {message_details['sensor_name']}**\n"
        f"**Dispositivo:** {message_details['client_name']} ({message_details['ip_address']})\n"
        f"**Motivo:** {message_details['reason']}"
    )
    payload = {"content": text}
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json=payload, timeout=10)
        except httpx.RequestError as e:
            print(f"[ERROR Webhook] {e}")


async def send_telegram_notification(config: dict, message_details: dict):
    bot_token = config.get("bot_token")
    chat_id = config.get("chat_id")
    if not bot_token or not chat_id:
        return

    def esc(x: str) -> str:
        return html.escape(str(x), quote=False)

    text = (
        f"<b>Alerta: {esc(message_details['sensor_name'])}</b>\n\n"
        f"<b>Dispositivo:</b> {esc(message_details['client_name'])} ({esc(message_details['ip_address'])})\n"
        f"<b>Motivo:</b> {esc(message_details['reason'])}"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=10)
            response.raise_for_status()
        except httpx.RequestError as e:
            print(f"[ERROR Telegram] {e}")
        except httpx.HTTPStatusError as e:
            print(f"[ERROR Telegram] {e.response.status_code} - {e.response.text}")


async def send_notification(channel_id: int, message_details: dict, owner_id: str):
    channel = await database.fetch_one(
        notification_channels_table.select().where(
            (notification_channels_table.c.id == channel_id) &
            (notification_channels_table.c.owner_id == owner_id)
        )
    )
    if not channel:
        print("[ALERT] Canal no encontrado o no pertenece al owner.")
        return
    cfg = channel["config"] if isinstance(channel["config"], dict) else json.loads(channel["config"])
    if channel["type"] == "webhook":
        await send_webhook_notification(cfg, message_details)
    elif channel["type"] == "telegram":
        await send_telegram_notification(cfg, message_details)


async def check_and_trigger_alerts(
    sensor_id: int,
    sensor_name: str,
    result: dict,
    device_info: dict,
    sensor_config: dict,
):
    """
    Evalúa alertas configuradas en el sensor con soporte de 'tolerancia' (fallos consecutivos).
    Para activar, incluir en cada alerta: {"tolerance_count": N}. Por defecto N=1 (sin tolerancia).
    """
    alert_configs = sensor_config.get("alerts", [])
    if not alert_configs:
        return

    # Si el sensor es de tipo ethernet y la interfaz es VLAN,
    # no evaluamos alertas de capa 1 (link_down, speed_change).
    kind = (sensor_config.get("_resolved_interface_kind") or sensor_config.get("interface_kind") or "auto").lower()
    supports_link_state = (kind != "vlan")

    now = datetime.now(timezone.utc)

    for alert in alert_configs:
        a_type = alert.get("type")
        if not a_type:
            continue

        alert_key = (sensor_id, a_type)
        cooldown = timedelta(minutes=int(alert.get("cooldown_minutes", 5)))
        tolerance = max(1, int(alert.get("tolerance_count", 1)))  # 👈 tolerancia (N fallos consecutivos)
        last_alert_time = last_alert_times.get(alert_key)

        # Respeta cooldown
        if last_alert_time and (now - last_alert_time) < cooldown:
            continue

        # Ignorar alertas L1 si es VLAN
        if a_type in ("link_down", "speed_change") and not supports_link_state:
            continue

        # ---- Detectar "fallo" según tipo de alerta ----
        failure_detected = False
        reason = ""

        if a_type == "timeout":
            if result.get("status") == "timeout":
                failure_detected = True
                reason = "El sensor ha entrado en estado de Timeout."

        elif a_type == "high_latency":
            if result.get("status") == "ok" and result.get("latency_ms", 0) > alert.get("threshold_ms", 0):
                failure_detected = True
                reason = (
                    f"Latencia alta detectada: {result['latency_ms']:.2f} ms "
                    f"(Umbral: {alert.get('threshold_ms', 0)} ms)."
                )

        elif a_type == "speed_change":
            last_speed = last_known_statuses.get(sensor_id, {}).get("speed")
            current_speed = result.get("speed")
            if last_speed is not None and current_speed is not None and current_speed != last_speed:
                failure_detected = True
                reason = f"La velocidad del puerto cambió de {last_speed} a {current_speed}."

        elif a_type == "traffic_threshold":
            threshold_bps = float(alert.get("threshold_mbps", 0)) * 1_000_000
            rx_bps = int(result.get("rx_bitrate", 0) or 0)
            tx_bps = int(result.get("tx_bitrate", 0) or 0)
            direction = (alert.get("direction") or "any").lower()
            if (direction in ("any", "rx") and rx_bps > threshold_bps):
                failure_detected = True
                reason = (
                    f"Tráfico de bajada superó el umbral: {(rx_bps/1_000_000):.2f} Mbps "
                    f"(Umbral: {alert.get('threshold_mbps', 0)} Mbps)."
                )
            elif (direction in ("any", "tx") and tx_bps > threshold_bps):
                failure_detected = True
                reason = (
                    f"Tráfico de subida superó el umbral: {(tx_bps/1_000_000):.2f} Mbps "
                    f"(Umbral: {alert.get('threshold_mbps', 0)} Mbps)."
                )

        # ---- Aplicar tolerancia (contador de fallos consecutivos) ----
        if failure_detected:
            new_count = alert_fail_counters.get(alert_key, 0) + 1
            alert_fail_counters[alert_key] = new_count

            # ¿Aún por debajo de la tolerancia? Solo logueamos y seguimos.
            if new_count < tolerance:
                print(f"[ALERT] {a_type} fallo {new_count}/{tolerance} (sensor={sensor_id}), aún no se alerta.")
                continue

            # Al llegar a la tolerancia: disparamos y reseteamos contador.
            alert_fail_counters[alert_key] = 0

            message = {
                "sensor_name": sensor_name,
                "client_name": device_info["client_name"],
                "ip_address": device_info["ip_address"],
                "reason": reason or f"Condición '{a_type}' alcanzó tolerancia ({tolerance}).",
            }

            await send_notification(alert["channel_id"], message, device_info["owner_id"])
            await database.execute(
                alert_history_table.insert().values(
                    sensor_id=sensor_id,
                    channel_id=alert["channel_id"],
                    timestamp=now,
                    details=json.dumps(message),
                )
            )
            last_alert_times[alert_key] = now

        else:
            # Si NO hay fallo en este ciclo, reiniciamos el contador de fallos consecutivos
            if alert_key in alert_fail_counters and alert_fail_counters[alert_key] != 0:
                alert_fail_counters[alert_key] = 0

    # Guardar último "speed" observado (para speed_change)
    if "speed" in result:
        last_known_statuses.setdefault(sensor_id, {})["speed"] = result["speed"]


# ==========================================================
# Tareas de sensores
# ==========================================================

async def launch_sensor_task(sensor_id: int):
    q = (
        sqlalchemy.select(
            sensors_table.c.id,
            sensors_table.c.name,
            sensors_table.c.sensor_type,
            sensors_table.c.config,
            devices_table.c.id.label("device_id"),
            devices_table.c.client_name,
            devices_table.c.ip_address,
            devices_table.c.credential_id,
            devices_table.c.maestro_id,
            devices_table.c.vpn_profile_id,
            devices_table.c.owner_id.label("device_owner_id"),
        )
        .select_from(sensors_table.join(monitors_table).join(devices_table))
        .where(sensors_table.c.id == sensor_id)
    )

    row = await database.fetch_one(q)
    if not row:
        print(f"[SENSORS] No encontrado sensor {sensor_id}")
        return

    cfg = row["config"]
    if isinstance(cfg, str):
        try:
            cfg = json.loads(cfg)
        except Exception:
            cfg = {}
    elif not isinstance(cfg, dict):
        cfg = {}

    device_info = {
        "id": row["device_id"],
        "client_name": row["client_name"],
        "ip_address": row["ip_address"],
        "credential_id": row["credential_id"],
        "maestro_id": row["maestro_id"],
        "vpn_profile_id": row["vpn_profile_id"],
        "owner_id": row["device_owner_id"],
    }

    if sensor_id in running_tasks:
        try:
            running_tasks[sensor_id].cancel()
        except Exception:
            pass
        running_tasks.pop(sensor_id, None)

    if row["sensor_type"] == "ping":
        task = asyncio.create_task(run_ping_monitor(row["id"], row["name"], cfg, device_info))
    elif row["sensor_type"] == "ethernet":
        task = asyncio.create_task(run_ethernet_monitor(row["id"], row["name"], cfg, device_info))
    else:
        print(f"[SENSORS] Tipo desconocido {row['sensor_type']} para sensor {row['id']}")
        return

    running_tasks[row["id"]] = task
    print(f"[SENSORS] Task #{row['id']} lanzada ({row['sensor_type']})")

async def _ensure_origin_connectivity(origin_device_info: dict):
    pid = origin_device_info.get("vpn_profile_id")
    if pid:
        iface = await ensure_vpn_up(pid)
        # Tráfico hacia la IP del Mikrotik por la tabla de ese perfil
        ip = origin_device_info.get("ip_address")
        if ip:
            await _pbr_add_rule_to_dest(pid, ip)
            await _pin_host_route(pid, ip, iface)

async def _release_origin_connectivity(origin_device_info: dict):
    pid = origin_device_info.get("vpn_profile_id")
    if pid:
        ip = origin_device_info.get("ip_address")
        if ip:
            try:
                await _unpin_host_route(pid, ip)
                await _pbr_del_rule_to_dest(pid, ip)
            except Exception:
                pass
        await release_vpn(pid)

async def run_ping_monitor(sensor_id: int, name: str, config: dict, device_info: dict):
    interval = int(config.get("interval_sec", 60))
    latency_threshold_visual = int(config.get("latency_threshold_ms", 150))
    ping_type = config.get("ping_type", "maestro_to_device")

    origin_device_info: Dict[str, Any] = {}
    target_ip: str = ""

    if ping_type == "maestro_to_device":
        maestro_id = device_info.get("maestro_id")
        if not maestro_id:
            print(f"[PING#{sensor_id}] modo=maestro_to_device sin maestro_id. Saliendo.")
            return
        maestro_device = await database.fetch_one(
            devices_table.select().where(devices_table.c.id == maestro_id)
        )
        if not maestro_device:
            print(f"[PING#{sensor_id}] maestro_id {maestro_id} no encontrado. Saliendo.")
            return
        origin_device_info = dict(maestro_device._mapping)
        target_ip = device_info["ip_address"]
    else:
        origin_device_info = device_info
        target_ip = config.get("target_ip", "")
        if not target_ip:
            print(f"[PING#{sensor_id}] falta 'target_ip' en config. Saliendo.")
            return

    origin_ip = origin_device_info["ip_address"]
    print(f"[PING#{sensor_id}] INICIO origin={origin_ip} -> target={target_ip} tipo={ping_type}")

    await _ensure_origin_connectivity(origin_device_info)

    try:
        while sensor_id in running_tasks:
            current_status, current_latency = "error", 9999.0
            try:
                if origin_ip not in connection_pools:
                    cred = await database.fetch_one(
                        credentials_table.select().where(
                            credentials_table.c.id == origin_device_info["credential_id"]
                        )
                    )
                    if not cred:
                        raise Exception(f"Credenciales no encontradas para {origin_ip}")
                    connection_pools[origin_ip] = routeros_api.RouterOsApiPool(
                        origin_ip,
                        username=cred["username"],
                        password=cred["password"],
                        port=8728,
                        plaintext_login=True,
                        use_ssl=False,
                    )
                api = connection_pools[origin_ip].get_api()

                ping_result = api.get_resource("/").call("ping", {"address": target_ip, "count": "1"})
                if ping_result and ping_result[0].get("received") == "1":
                    time_str = ping_result[0].get("avg-rtt", "0ms")
                    seconds = 0
                    millis = 0
                    s_match = re.search(r"(\d+)s", time_str)
                    ms_match = re.search(r"(\d+)ms", time_str)
                    if s_match:
                        seconds = int(s_match.group(1))
                    if ms_match:
                        millis = int(ms_match.group(1))
                    current_latency = seconds * 1000 + millis
                    current_status = "high_latency" if current_latency > latency_threshold_visual else "ok"
                else:
                    current_status = "timeout"

                result_data = {"status": current_status, "latency_ms": current_latency}
                await database.execute(
                    ping_results_table.insert().values(
                        sensor_id=sensor_id, timestamp=datetime.now(timezone.utc), **result_data
                    )
                )

                broadcast_data = {
                    "sensor_id": sensor_id,
                    "sensor_type": "ping",
                    **result_data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                await manager.broadcast_for(device_info["owner_id"], json.dumps(broadcast_data))

                await check_and_trigger_alerts(sensor_id, name, result_data, device_info, config)

            except Exception as e:
                print(f"[PING#{sensor_id}] Error en ciclo: {e}")

                result_data = {"status": "timeout", "latency_ms": None}
                ts = datetime.now(timezone.utc)

                try:
                    await database.execute(
                        ping_results_table.insert().values(
                            sensor_id=sensor_id, timestamp=ts, **result_data
                        )
                    )
                    await manager.broadcast_for(
                        device_info["owner_id"],
                        json.dumps({
                            "sensor_id": sensor_id,
                            "sensor_type": "ping",
                            **result_data,
                            "timestamp": ts.isoformat(),
                        })
                    )
                except Exception as _db_e:
                    print(f"[PING#{sensor_id}] Error guardando timeout: {_db_e}")

                try:
                    await check_and_trigger_alerts(sensor_id, name, result_data, device_info, config)
                except Exception as _alert_e:
                    print(f"[PING#{sensor_id}] Error alerts timeout: {_alert_e}")

                # ⚙️ Intentar recuperación de conexión
                ip = origin_ip
                owner_id = device_info["owner_id"]

                # 1️⃣ Intentar rotación si el error parece de autenticación
                auth_keywords = ("authentication", "invalid user", "password", "login failed", "logon failure")
                if any(k in str(e).lower() for k in auth_keywords):
                    print(f"[PING#{sensor_id}] Detectado fallo de auth -> rotando credenciales para {ip}")
                    new_cred = await rotate_device_credentials_on_auth_failure(ip, owner_id)
                    if new_cred:
                        cred = await database.fetch_one(
                            credentials_table.select().where(credentials_table.c.id == new_cred)
                        )
                        if cred:
                            try:
                                connection_pools[ip] = routeros_api.RouterOsApiPool(
                                    ip,
                                    username=cred["username"],
                                    password=cred["password"],
                                    port=8728,
                                    plaintext_login=True,
                                    use_ssl=False,
                                )
                                print(f"[PING#{sensor_id}] Reconectado tras rotación con cred_id={new_cred}")
                            except Exception as e2:
                                print(f"[PING#{sensor_id}] Falló reconexión post-rotación: {e2}")
                        else:
                            print(f"[PING#{sensor_id}] Nueva credencial {new_cred} no encontrada en DB.")
                    else:
                        print(f"[PING#{sensor_id}] No se encontró credencial válida tras rotación.")
                else:
                    # 2️⃣ Si no es error de auth, intentar reconectar con la misma credencial
                    try:
                        api = connection_pools[ip].get_api()
                        api.get_resource("/system/identity").get()
                    except Exception as e_conn:
                        print(f"[RECONNECT] {ip} reiniciando conexión: {e_conn}")
                        cred = await database.fetch_one(
                            credentials_table.select().where(
                                credentials_table.c.id == origin_device_info["credential_id"]
                            )
                        )
                        if cred:
                            try:
                                connection_pools[ip] = routeros_api.RouterOsApiPool(
                                    ip,
                                    username=cred["username"],
                                    password=cred["password"],
                                    port=8728,
                                    plaintext_login=True,
                                    use_ssl=False,
                                )
                                print(f"[RECONNECT] {ip} restablecida OK")
                            except Exception as e2:
                                print(f"[RECONNECT] {ip} fallo: {e2}")


            await asyncio.sleep(interval)
    finally:
        await _release_origin_connectivity(origin_device_info)
        print(f"[PING#{sensor_id}] FIN")

async def run_ethernet_monitor(sensor_id: int, name: str, config: dict, device_info: dict):
    """
    Distingue automágicamente Ethernet física vs VLAN.
    - Ethernet: link (up/down) + speed + tráfico
    - VLAN: status="ok", speed="N/A" + tráfico

    Regla: no usar /interface/ethernet/monitor (ROS7 rompe con 'unknown parameter interface').
           Para tráfico usar siempre /interface monitor-traffic.
    """
    from typing import Optional
    import re

    interval = int(config.get("interval_sec", 30))
    interface_name: Optional[str] = config.get("interface_name")
    print(f"[DEBUG CONFIG TYPE] sensor={sensor_id} type={type(config)} value={config}")
    interface_kind_cfg = (config.get("interface_kind") or "auto").lower()  # "auto" | "ethernet" | "vlan"
    device_ip = device_info["ip_address"]

    # --- caché pegajosa por proceso ---
    global _M360_KIND_CACHE
    if not isinstance(globals().get("_M360_KIND_CACHE"), dict):
        _M360_KIND_CACHE = {}
    cache_key = (device_ip, interface_name or "")

    await _ensure_origin_connectivity(device_info)

    def _parse_link_up(val: Optional[str]) -> bool:
        if val is None:
            return False
        s = str(val).lower()
        return s in ("link-ok", "link_ok", "ok", "up", "running", "true", "yes")

    def _looks_like_vlan(name: Optional[str]) -> bool:
        if not name:
            return False
        n = name.lower()
        # vlan70-ARBOLEDA | vlan10 | ether1.30 | bridge.20 -> suelen ser VLAN
        return ("vlan" in n) or bool(re.search(r"\.\d+$", n))

    async def _detect_kind(api) -> str:
        """Heurística + consultas: devuelve 'ethernet' o 'vlan'."""
        # Forzado por config
        if interface_kind_cfg in ("ethernet", "vlan"):
            return interface_kind_cfg

        # Caché
        cached = _M360_KIND_CACHE.get(cache_key)
        if cached in ("ethernet", "vlan"):
            return cached

        # Heurística por nombre primero
        if _looks_like_vlan(interface_name):
            _M360_KIND_CACHE[cache_key] = "vlan"
            return "vlan"

        # /interface/vlan ¿existe?
        try:
            row = api.get_resource("/interface/vlan").get(name=interface_name)
            if row:
                _M360_KIND_CACHE[cache_key] = "vlan"
                return "vlan"
        except Exception:
            pass

        # /interface (type)
        try:
            rows = api.get_resource("/interface").get(name=interface_name)
            if rows:
                t = (rows[0].get("type") or "").lower()
                if "vlan" in t:
                    _M360_KIND_CACHE[cache_key] = "vlan"
                    return "vlan"
                if "ether" in t:
                    _M360_KIND_CACHE[cache_key] = "ethernet"
                    return "ethernet"
        except Exception:
            pass

        # /interface/ethernet ¿existe?
        try:
            row = api.get_resource("/interface/ethernet").get(name=interface_name)
            if row:
                _M360_KIND_CACHE[cache_key] = "ethernet"
                return "ethernet"
        except Exception:
            pass

        _M360_KIND_CACHE[cache_key] = "ethernet"
        return "ethernet"

    async def _do_vlan_path(api) -> dict:
        """VLAN: sin L1 → solo tráfico."""
        local = {"status": "ok", "speed": "N/A", "rx_bitrate": "0", "tx_bitrate": "0"}
        try:
            mon = api.get_resource("/interface").call(
                "monitor-traffic", {"interface": interface_name, "once": ""}
            )
            if mon:
                local["rx_bitrate"] = mon[0].get("rx-bits-per-second", "0") or "0"
                local["tx_bitrate"] = mon[0].get("tx-bits-per-second", "0") or "0"
        except Exception as e_tra:
            print(f"[ETH#{sensor_id}] (VLAN) monitor-traffic warn: {e_tra}")
        return local

    try:
        while sensor_id in running_tasks:
            result_data = {"status": "error", "speed": "N/A", "rx_bitrate": "0", "tx_bitrate": "0"}
            try:
                if device_ip not in connection_pools:
                    credential_id = device_info.get("credential_id")
                    if not credential_id:
                        raise Exception("Falta credential_id")
                    cred = await database.fetch_one(
                        credentials_table.select().where(credentials_table.c.id == credential_id)
                    )
                    if not cred:
                        raise Exception("Credenciales no encontradas")
                    connection_pools[device_ip] = routeros_api.RouterOsApiPool(
                        device_ip,
                        username=cred["username"],
                        password=cred["password"],
                        port=8728,
                        plaintext_login=True,
                        use_ssl=False,
                    )
                api = connection_pools[device_ip].get_api()

                # === HOTFIX incondicional: si está forzado VLAN en la config, no detectes nada y ve directo ===
                forced_kind = str((config.get("interface_kind") or "auto")).lower()
                if forced_kind == "vlan":
                    config["_resolved_interface_kind"] = "vlan"
                    print(f"[ETH#{sensor_id}] FORCED VLAN -> usando monitor-traffic en {interface_name}")
                    result_data.update(await _do_vlan_path(api))

                    ts = datetime.now(timezone.utc)
                    await database.execute(
                        ethernet_results_table.insert().values(sensor_id=sensor_id, timestamp=ts, **result_data)
                    )
                    await manager.broadcast_for(
                        device_info["owner_id"],
                        json.dumps({
                            "sensor_id": sensor_id,
                            "sensor_type": "ethernet",
                            **result_data,
                            "timestamp": ts.isoformat(),
                        })
                    )
                    await check_and_trigger_alerts(sensor_id, name, result_data, device_info, config)
                    await asyncio.sleep(interval)
                    continue  # <<< no sigas al camino ethernet

                # === detectar tipo (y recordarlo para alertas) ===
                interface_kind_raw = config.get("interface_kind") if isinstance(config, dict) else None
                interface_kind_cfg_local = str(interface_kind_raw).lower() if interface_kind_raw else None

                if interface_kind_cfg_local:
                    effective_kind = interface_kind_cfg_local
                else:
                    effective_kind = await _detect_kind(api)

                config["_resolved_interface_kind"] = effective_kind
                is_vlan = (effective_kind == "vlan")

                print(f"[DEBUG VLAN FINAL] sensor={sensor_id} interface={interface_name} kind={effective_kind}")

                if is_vlan:
                    # VLAN: solo monitor-traffic
                    result_data.update(await _do_vlan_path(api))

                else:
                    # === Ethernet físico: estado + velocidad + tráfico (sin usar /interface/ethernet/monitor) ===
                    try:
                        # 1) Estado básico (running) y tipo desde /interface
                        if_rows = api.get_resource("/interface").get(name=interface_name)
                        iface_type = (if_rows[0].get("type") or "").lower() if if_rows else ""
                        result_data["status"] = "link_up" if (if_rows and if_rows[0].get("running")) else "link_down"

                        # 2) Si realmente es VLAN (por type o nombre), pivot inmediato
                        if "vlan" in iface_type or _looks_like_vlan(interface_name):
                            _M360_KIND_CACHE[cache_key] = "vlan"
                            config["_resolved_interface_kind"] = "vlan"
                            print(f"[ETH#{sensor_id}] detected VLAN -> usando monitor-traffic")
                            result_data.update(await _do_vlan_path(api))
                        else:
                            # 3) Velocidad: /interface/ethernet get (si aplica)
                            try:
                                eth_info = api.get_resource("/interface/ethernet").get(name=interface_name)
                                if eth_info:
                                    result_data["speed"] = (
                                        eth_info[0].get("speed")
                                        or eth_info[0].get("rate")
                                        or result_data["speed"]
                                    )
                            except Exception as e_get:
                                print(f"[ETH#{sensor_id}] ethernet get speed error: {e_get}")

                            # 4) Tráfico: monitor-traffic
                            try:
                                monitor = api.get_resource("/interface").call(
                                    "monitor-traffic", {"interface": interface_name, "once": ""}
                                )
                                if monitor:
                                    result_data["rx_bitrate"] = monitor[0].get("rx-bits-per-second", "0") or "0"
                                    result_data["tx_bitrate"] = monitor[0].get("tx-bits-per-second", "0") or "0"
                            except Exception as e_tra:
                                print(f"[ETH#{sensor_id}] monitor-traffic error: {e_tra}")

                    except Exception as e_mon:
                        print(f"[ETH#{sensor_id}] ethernet path error: {e_mon}")
                        # En error, al menos intentamos tráfico genérico:
                        try:
                            result_data.update(await _do_vlan_path(api))
                        except Exception:
                            pass

                # Persistencia + WS + alertas
                ts = datetime.now(timezone.utc)
                await database.execute(
                    ethernet_results_table.insert().values(sensor_id=sensor_id, timestamp=ts, **result_data)
                )
                await manager.broadcast_for(
                    device_info["owner_id"],
                    json.dumps({
                        "sensor_id": sensor_id,
                        "sensor_type": "ethernet",
                        **result_data,
                        "timestamp": ts.isoformat(),
                    })
                )
                await check_and_trigger_alerts(sensor_id, name, result_data, device_info, config)

            except Exception as e:
                print(f"[ETH#{sensor_id}] Error en ciclo: {e}")

                ts = datetime.now(timezone.utc)
                kind_raw = config.get("_resolved_interface_kind") or interface_kind_cfg
                kind_now = str(kind_raw).lower() if kind_raw else "auto"
                if kind_now == "vlan":
                    result_data = {"status": "ok", "speed": "N/A", "rx_bitrate": "0", "tx_bitrate": "0"}
                else:
                    result_data = {"status": "link_down", "speed": "N/A", "rx_bitrate": "0", "tx_bitrate": "0"}

                try:
                    await database.execute(
                        ethernet_results_table.insert().values(sensor_id=sensor_id, timestamp=ts, **result_data)
                    )
                    await manager.broadcast_for(
                        device_info["owner_id"],
                        json.dumps({
                            "sensor_id": sensor_id,
                            "sensor_type": "ethernet",
                            **result_data,
                            "timestamp": ts.isoformat(),
                        })
                    )
                    await check_and_trigger_alerts(sensor_id, name, result_data, device_info, config)
                except Exception as _e2:
                    print(f"[ETH#{sensor_id}] Error guardando/broadcast en error: {_e2}")

                ip = device_ip
                owner_id = device_info["owner_id"]

                # 1️⃣ Intentar rotación si parece error de auth
                auth_keywords = ("authentication", "invalid user", "password", "login failed", "logon failure")
                if any(k in str(e).lower() for k in auth_keywords):
                    print(f"[ETH#{sensor_id}] Auth error detectado -> rotando credenciales para {ip}")
                    new_cred = await rotate_device_credentials_on_auth_failure(ip, owner_id)
                    if new_cred:
                        cred = await database.fetch_one(
                            credentials_table.select().where(credentials_table.c.id == new_cred)
                        )
                        if cred:
                            try:
                                connection_pools[ip] = routeros_api.RouterOsApiPool(
                                    ip,
                                    username=cred["username"],
                                    password=cred["password"],
                                    port=8728,
                                    plaintext_login=True,
                                    use_ssl=False,
                                )
                                print(f"[ETH#{sensor_id}] Reconectado tras rotación con cred_id={new_cred}")
                            except Exception as e2:
                                print(f"[ETH#{sensor_id}] Falló reconexión post-rotación: {e2}")
                        else:
                            print(f"[ETH#{sensor_id}] Nueva credencial {new_cred} no encontrada en DB.")
                    else:
                        print(f"[ETH#{sensor_id}] No se encontró credencial válida tras rotación.")
                else:
                    # 2️⃣ Reintento normal
                    if ip in connection_pools:
                        try:
                            connection_pools[ip].disconnect()
                        except Exception:
                            pass
                        connection_pools.pop(ip, None)


            await asyncio.sleep(interval)
    finally:
        await _release_origin_connectivity(device_info)

# --- Mantenemos las conexiones RouterOS activas y saludables ---
async def keepalive_routeros_loop():
    """
    Recorre los pools RouterOS y verifica que sigan autenticando correctamente.
    Si una conexión falla por error de autenticación o socket roto,
    intenta rotar las credenciales automáticamente (re-arrienda).
    """
    while True:
        for ip, pool in list(connection_pools.items()):
            try:
                api = pool.get_api()
                api.get_resource("/system/identity").get()
                # print(f"[KEEPALIVE] {ip} OK")  # opcional debug
            except Exception as e:
                print(f"[KEEPALIVE] {ip} error: {e}")

                # --- detectar posible fallo de autenticación ---
                auth_keywords = ("authentication", "logon failure", "invalid user", "password", "login failed")
                auth_error = any(k in str(e).lower() for k in auth_keywords)

                try:
                    pool.disconnect()
                except Exception:
                    pass
                connection_pools.pop(ip, None)

                # --- Buscar el owner correspondiente al dispositivo ---
                dev = await database.fetch_one(
                    devices_table.select().where(devices_table.c.ip_address == ip)
                )
                if not dev:
                    print(f"[KEEPALIVE] {ip} sin device registrado.")
                    continue

                owner_id = dev["owner_id"]

                if auth_error:
                    # 🔄 Fallo de autenticación → intentar rotación automática
                    print(f"[KEEPALIVE] {ip} autenticación fallida → rotando credenciales…")
                    new_cred_id = await rotate_device_credentials_on_auth_failure(ip, owner_id)
                    if new_cred_id:
                        try:
                            cred = await database.fetch_one(
                                credentials_table.select().where(credentials_table.c.id == new_cred_id)
                            )
                            if cred:
                                connection_pools[ip] = routeros_api.RouterOsApiPool(
                                    ip,
                                    username=cred["username"],
                                    password=cred["password"],
                                    port=8728,
                                    plaintext_login=True,
                                    use_ssl=False,
                                )
                                print(f"[KEEPALIVE] {ip} reconectado con nueva credencial {new_cred_id}")
                        except Exception as e2:
                            print(f"[KEEPALIVE] {ip} fallo reconexión post-rotación: {e2}")
                    else:
                        print(f"[KEEPALIVE] {ip} sin credenciales válidas tras rotación.")
                else:
                    # 🔁 Si no es auth error, intentar reconectar con la misma
                    cred = await database.fetch_one(
                        credentials_table.select().where(credentials_table.c.id == dev["credential_id"])
                    )
                    if cred:
                        try:
                            connection_pools[ip] = routeros_api.RouterOsApiPool(
                                ip,
                                username=cred["username"],
                                password=cred["password"],
                                port=8728,
                                plaintext_login=True,
                                use_ssl=False,
                            )
                            print(f"[KEEPALIVE] {ip} reconectado OK (misma credencial).")
                        except Exception as e2:
                            print(f"[KEEPALIVE] {ip} reconexión falló: {e2}")
        await asyncio.sleep(30)


# === Aggregation helpers (bucketing por ventana) ===
def _choose_bucket_seconds(start_dt: datetime, end_dt: datetime, max_points: int = 2000) -> int:
    """
    Devuelve tamaño de bucket (segundos) para mantener ~max_points.
    Usa una escala discreta que funciona bien para 7d/30d.
    """
    window_secs = max(1, int((end_dt - start_dt).total_seconds()))
    target = max(1, int(max_points))
    raw = max(1, window_secs // target)
    allowed = [60, 300, 900, 3600, 21600, 86400]  # 1m,5m,15m,1h,6h,1d
    for b in allowed:
        if raw <= b:
            return b
    return allowed[-1]




# ==========================================================
# FastAPI app
# ==========================================================

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://monitor360.media",
        "https://www.monitor360.media",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================================
# Helpers SQL por owner
# ==========================================================

def _monitors_query_sql_for_owner(owner_id: str) -> Tuple[str, dict]:
    if IS_POSTGRES:
        sql = """
        SELECT
          m.id AS monitor_id,
          d.id AS device_id,
          d.client_name,
          d.ip_address,
          d.credential_id,
          d.maestro_id,
          d.vpn_profile_id,
          d.last_auth_ok,
          d.last_auth_fail,
          d.rotations_count,
          COALESCE(
            json_agg(
              json_build_object(
                'id', s.id,
                'name', s.name,
                'sensor_type', s.sensor_type,
                'config', s.config
              )
            ) FILTER (WHERE s.id IS NOT NULL),
            '[]'::json
          ) AS sensors
        FROM monitors m
        JOIN devices d ON m.device_id = d.id
        LEFT JOIN sensors s ON s.monitor_id = m.id
        WHERE d.owner_id = :owner_id
        GROUP BY
          m.id,
          d.id,
          d.client_name,
          d.ip_address,
          d.credential_id,
          d.maestro_id,
          d.vpn_profile_id,
          d.last_auth_ok,
          d.last_auth_fail,
          d.rotations_count
        ORDER BY m.id ASC
        """
        return sql, {"owner_id": owner_id}
    else:
        # SQLite fallback
        sql = """
        SELECT
          m.id AS monitor_id,
          d.id AS device_id,
          d.client_name,
          d.ip_address,
          d.credential_id,
          d.maestro_id,
          d.vpn_profile_id,
          d.last_auth_ok,
          d.last_auth_fail,
          d.rotations_count,
          (SELECT json_group_array(
              json_object(
                'id', s.id,
                'name', s.name,
                'sensor_type', s.sensor_type,
                'config', json(s.config)
              )
            )
           FROM sensors s WHERE s.monitor_id = m.id) AS sensors
        FROM monitors m
        JOIN devices d ON m.device_id = d.id
        WHERE d.owner_id = :owner_id
        ORDER BY m.id ASC
        """
        return sql, {"owner_id": owner_id}


# ==========================================================
# Endpoints: dispositivos / credenciales / monitores / sensores
# ==========================================================

# === Endpoints de sesiones QR ===

# ==========================================================
# Endpoints para el escaneo QR Remoto (unificados bajo /api)
# ==========================================================

@app.post("/api/qr/start")
async def start_qr_session(owner_id: str = Depends(get_owner_id)):
    session_id = str(uuid.uuid4())
    mobile_url = f"{FRONTEND_BASE_URL}/scan/{session_id}"

    SCAN_SESSIONS[session_id] = {
        "owner_id": owner_id,
        "created": datetime.now(timezone.utc),
        "status": "pending",
        "result": None,
    }

    return {
        "session_id": session_id,
        "mobile_url": mobile_url,
        "expires_in": SCAN_TTL_SECONDS,
    }

@app.post("/api/scan/{session_id}")
async def receive_scanned_data(
    session_id: str,
    payload: ScanPayload = Body(...),   # 👈 ahora Pylance reconoce payload
):
    """
    Recibe desde el celular el texto del QR del MikroTik.
    Se valida la sesión y se hace broadcast por WebSocket al navegador del owner.
    """
    s = SCAN_SESSIONS.get(session_id)
    if not _session_valid(s) or s is None:
        raise HTTPException(status_code=404, detail="Sesión inválida o expirada.")

    # Guardamos el resultado escaneado
    s["status"] = "done"
    s["result"] = payload.config_data

    # Broadcast por WS al navegador del owner
    msg = json.dumps({
        "type": "qr_config",
        "session_id": session_id,
        "config_text": payload.config_data,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    await manager.broadcast_for(s["owner_id"], msg)

    return {"ok": True}

@app.get("/api/qr/status/{session_id}")
async def qr_status(session_id: str, owner_id: str = Depends(get_owner_id)):
    """
    Consulta el estado de una sesión QR.
    Si la sesión está expirada o no existe, se borra de SCAN_SESSIONS.
    """
    s = SCAN_SESSIONS.get(session_id)

    # Sesión inexistente
    if s is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")

    # Sesión expirada
    if not _session_valid(s):
        # 🔹 limpieza automática
        SCAN_SESSIONS.pop(session_id, None)
        raise HTTPException(status_code=404, detail="Sesión inválida o expirada.")

    # ✅ Sesión válida → devolvemos estado actual
    return {
        "session_id": session_id,
        "status": s.get("status"),
        "result": s.get("result"),
        "expires_in": SCAN_TTL_SECONDS,
    }


@app.post("/api/devices/test_reachability")
async def test_device_reachability(
    test: IsolatedConnectionTest,
    owner_id: str = Depends(get_owner_id),
):
    """
    Prueba de alcance de un dispositivo:
    - Si se especifica vpn_profile_id: levanta el túnel, valida check_ip si existe.
    - Si se especifica maestro_id: usa el túnel del maestro.
    - Sino: prueba en LAN directa.
    Con timeouts agresivos para no colgar el event-loop.
    """
    trace = uuid.uuid4().hex[:8]
    print(f"[REACH_TEST#{trace}] >>> inicio payload={test.model_dump()} owner={owner_id}")

    async def _short_connectivity_check(ip: str) -> bool:
        # 1. Probar ICMP rápido
        ok, _ = await run_command(["ping", "-c", "1", "-W", "1", ip])
        if ok:
            return True
        # 2. Si ICMP falla, probar TCP a 8728 (API Mikrotik)
        return await tcp_port_reachable(ip, 8728, timeout_s=1.5)

    async def _auth_try(ip: str) -> Optional[int]:
        # margen externo 9s, interno overall 8s, per-cred 3s
        try:
            return await asyncio.wait_for(
                test_and_get_credential_id(ip, owner_id, per_cred_timeout=3.0, overall_timeout=8.0),
                timeout=9.0,
            )
        except asyncio.TimeoutError:
            print(f"[REACH_TEST#{trace}] auth timeout externo (9s) ip={ip}")
            return None

    # Caso 1: VPN explícita
    if test.vpn_profile_id:
        print(f"[REACH_TEST#{trace}] VPN explícita pid={test.vpn_profile_id}")
        vpn = await database.fetch_one(
            vpn_profiles_table.select().where(
                (vpn_profiles_table.c.id == test.vpn_profile_id)
                & (vpn_profiles_table.c.owner_id == owner_id)
            )
        )
        if not vpn:
            raise HTTPException(status_code=404, detail="Perfil VPN no encontrado.")

        vpn_dict = dict(vpn._mapping)
        check_ip = (vpn_dict.get("check_ip") or "").strip()

        t0 = time.time()
        iface = None
        try:
            iface = await ensure_vpn_up(test.vpn_profile_id)
            await asyncio.sleep(0.3)  # breve respiro para rutas
            t1 = (time.time() - t0) * 1000
            print(f"[REACH_TEST#{trace}] vpn_up iface={iface} dt={t1:.1f}ms")

            # (opcional) validar check_ip del perfil
            if check_ip:
                print(f"[REACH_TEST#{trace}] check_ip_try {check_ip}")
                await _pbr_add_rule_to_dest(test.vpn_profile_id, check_ip)
                await _pin_host_route(test.vpn_profile_id, check_ip, iface)
                if not await _short_connectivity_check(check_ip):
                    t2 = (time.time() - t0) * 1000
                    print(f"[REACH_TEST#{trace}] FAIL check_ip en {t2:.1f}ms")
                    return {
                        "reachable": False,
                        "detail": f"VPN levantada pero {check_ip} no responde ICMP ni 8728/tcp.",
                        "used_profile_id": test.vpn_profile_id,
                    }

            # ruta dedicada al Mikrotik destino (regla PBR + pin de host)
            await _pbr_add_rule_to_dest(test.vpn_profile_id, test.ip_address)
            await _pin_host_route(test.vpn_profile_id, test.ip_address, iface)

            cred_id = await _auth_try(test.ip_address)
            total = (time.time() - t0) * 1000
            if cred_id:
                print(f"[REACH_TEST#{trace}] OK auth/alcance via VPN total={total:.1f}ms")
                return {"reachable": True, "credential_id": cred_id, "used_profile_id": test.vpn_profile_id}
            else:
                print(f"[REACH_TEST#{trace}] FAIL auth/alcance via VPN total={total:.1f}ms")
                return {
                    "reachable": False,
                    "detail": "VPN activa pero no se pudo autenticar o alcanzar el dispositivo.",
                    "used_profile_id": test.vpn_profile_id,
                }
        finally:
            # limpieza de rutas host y reglas PBR; luego liberar VPN
            try:
                if check_ip:
                    await _unpin_host_route(test.vpn_profile_id, check_ip)
                    await _pbr_del_rule_to_dest(test.vpn_profile_id, check_ip)
                await _unpin_host_route(test.vpn_profile_id, test.ip_address)
                await _pbr_del_rule_to_dest(test.vpn_profile_id, test.ip_address)
            except Exception:
                pass
            await release_vpn(test.vpn_profile_id)

    # Caso 2: VPN del maestro
    if test.maestro_id:
        print(f"[REACH_TEST#{trace}] usando túnel del maestro id={test.maestro_id}")
        maestro = await database.fetch_one(
            devices_table.select().where(
                (devices_table.c.id == test.maestro_id)
                & (devices_table.c.owner_id == owner_id)
            )
        )
        if not maestro:
            raise HTTPException(status_code=404, detail="Maestro no encontrado.")
        maestro_pid = maestro["vpn_profile_id"]
        if not maestro_pid:
            raise HTTPException(status_code=400, detail="El maestro no tiene un perfil de VPN asociado.")

        t0 = time.time()
        iface = None
        try:
            iface = await ensure_vpn_up(maestro_pid)
            await asyncio.sleep(0.3)
            print(f"[REACH_TEST#{trace}] vpn_up iface={iface}")

            # PBR + pin al destino a través del túnel del maestro
            await _pbr_add_rule_to_dest(maestro_pid, test.ip_address)
            await _pin_host_route(maestro_pid, test.ip_address, iface)

            cred_id = await _auth_try(test.ip_address)
            total = (time.time() - t0) * 1000
            if cred_id:
                print(f"[REACH_TEST#{trace}] OK via maestro total={total:.1f}ms")
                return {"reachable": True, "credential_id": cred_id, "used_profile_id": maestro_pid}
            else:
                print(f"[REACH_TEST#{trace}] FAIL via maestro total={total:.1f}ms")
                return {
                    "reachable": False,
                    "detail": "Túnel del maestro activo pero no se pudo autenticar o alcanzar el dispositivo.",
                    "used_profile_id": maestro_pid,
                }
        finally:
            try:
                await _unpin_host_route(maestro_pid, test.ip_address)
                await _pbr_del_rule_to_dest(maestro_pid, test.ip_address)
            except Exception:
                pass
            await release_vpn(maestro_pid)

    # Caso 3: LAN directa
    print(f"[REACH_TEST#{trace}] LAN directa")
    cred_id = await _auth_try(test.ip_address)
    if cred_id:
        return {"reachable": True, "credential_id": cred_id}
    return {"reachable": False, "detail": "No alcanzable o credenciales incorrectas en LAN."}

@app.put("/api/devices/{device_id}/associate_vpn")
async def associate_vpn_to_maestro(device_id: str, association: VpnAssociation, owner_id: str = Depends(get_owner_id)):
    dev = await database.fetch_one(
        devices_table.select().where(
            (devices_table.c.id == device_id) &
            (devices_table.c.owner_id == owner_id)
        )
    )
    if not dev:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado.")
    if association.vpn_profile_id is not None:
        vpn = await database.fetch_one(
            vpn_profiles_table.select().where(
                (vpn_profiles_table.c.id == association.vpn_profile_id) &
                (vpn_profiles_table.c.owner_id == owner_id)
            )
        )
        if not vpn:
            raise HTTPException(status_code=404, detail="Perfil VPN no encontrado.")

    query = (
        devices_table.update()
        .where((devices_table.c.id == device_id) & (devices_table.c.owner_id == owner_id))
        .values(vpn_profile_id=association.vpn_profile_id)
    )
    await database.execute(query)
    return {"message": "Asociación de VPN actualizada."}

@app.post("/api/credentials", status_code=201)
async def create_credential(cred: CredentialCreate, owner_id: str = Depends(get_owner_id)):
    query = credentials_table.insert().values(
        name=cred.name, username=cred.username, password=cred.password, owner_id=owner_id
    )
    try:
        last_record_id = await database.execute(query)
        return {"id": last_record_id, **cred.dict()}
    except Exception:
        raise HTTPException(status_code=400, detail="Ya existe una credencial con ese nombre.")

@app.get("/api/credentials", response_model=List[CredentialResponse])
async def get_credentials(owner_id: str = Depends(get_owner_id)):
    rows = await database.fetch_all(
        credentials_table.select().where(credentials_table.c.owner_id == owner_id)
    )
    return rows

@app.delete("/api/credentials/{credential_id}", status_code=204)
async def delete_credential(credential_id: int, owner_id: str = Depends(get_owner_id)):
    await database.execute(
        credentials_table.delete().where(
            (credentials_table.c.id == credential_id) &
            (credentials_table.c.owner_id == owner_id)
        )
    )

@app.post("/api/devices/manual", status_code=201)
async def add_device_manually(device: ManualDevice, owner_id: str = Depends(get_owner_id)):
    credential_id: Optional[int] = None
    vpn_to_use = None

    if device.vpn_profile_id:
        vpn_to_use = await database.fetch_one(
            vpn_profiles_table.select().where(
                (vpn_profiles_table.c.id == device.vpn_profile_id) &
                (vpn_profiles_table.c.owner_id == owner_id)
            )
        )
        if not vpn_to_use:
            raise HTTPException(status_code=404, detail="Perfil VPN no encontrado")
    elif device.maestro_id:
        maestro = await database.fetch_one(
            devices_table.select().where(
                (devices_table.c.id == device.maestro_id) &
                (devices_table.c.owner_id == owner_id)
            )
        )
        if not maestro:
            raise HTTPException(status_code=404, detail="Maestro no encontrado")
        if not maestro["vpn_profile_id"]:
            raise HTTPException(status_code=400, detail="El maestro no tiene un perfil de VPN asociado.")
        vpn_to_use = await database.fetch_one(
            vpn_profiles_table.select().where(
                (vpn_profiles_table.c.id == maestro["vpn_profile_id"]) &
                (vpn_profiles_table.c.owner_id == owner_id)
            )
        )
    else:
        vpn_to_use = await database.fetch_one(
            vpn_profiles_table.select().where(
                (vpn_profiles_table.c.is_default == True) &
                (vpn_profiles_table.c.owner_id == owner_id)
            )
        )

    if vpn_to_use:
        pid = vpn_to_use["id"]
        vpn_check_ip = (vpn_to_use["check_ip"] or "").strip()
        iface = None
        try:
            # Levantar túnel y obtener interfaz
            iface = await ensure_vpn_up(pid)
            await asyncio.sleep(0.3)  # pequeño respiro para rutas

            # (opcional) validar check_ip del perfil como sanity-check del túnel
            if vpn_check_ip:
                await _pbr_add_rule_to_dest(pid, vpn_check_ip)
                await _pin_host_route(pid, vpn_check_ip, iface)
                ok_icmp, _ = await run_command(["ping", "-c", "1", "-W", "1", vpn_check_ip])
                if not ok_icmp and not await tcp_port_reachable(vpn_check_ip, 8728, timeout_s=1.5):
                    raise HTTPException(
                        status_code=502,
                        detail=f"VPN levantada pero {vpn_check_ip} no responde ICMP ni 8728/tcp."
                    )

            # PBR + pin hacia el dispositivo a agregar
            await _pbr_add_rule_to_dest(pid, device.ip_address)
            await _pin_host_route(pid, device.ip_address, iface)

            # Probar credenciales a través del túnel
            credential_id = await test_and_get_credential_id(device.ip_address, owner_id)

        finally:
            # Limpieza simétrica (pin + rule) y liberar túnel
            try:
                if vpn_check_ip:
                    await _unpin_host_route(pid, vpn_check_ip)
                    await _pbr_del_rule_to_dest(pid, vpn_check_ip)
                await _unpin_host_route(pid, device.ip_address)
                await _pbr_del_rule_to_dest(pid, device.ip_address)
            except Exception:
                pass
            await release_vpn(pid)

    else:
        credential_id = await test_and_get_credential_id(device.ip_address, owner_id)


    if not credential_id:
        raise HTTPException(status_code=401, detail=f"Autenticación fallida en {device.ip_address}.")

    device_id = str(uuid.uuid4())
    insert_values = {
        "id": device_id,
        "client_name": device.client_name,
        "ip_address": device.ip_address,
        "mac_address": device.mac_address or "",
        "node": device.node or "",
        "status": "MANUAL",
        "credential_id": credential_id,
        "is_maestro": False,
        "maestro_id": (device.maestro_id or None),
        "vpn_profile_id": device.vpn_profile_id if device.vpn_profile_id else (vpn_to_use["id"] if vpn_to_use else None),
        "owner_id": owner_id,
    }

    try:
        await database.execute(devices_table.insert().values(**insert_values))
        created = await database.fetch_one(
            devices_table.select().where(
                (devices_table.c.id == device_id) &
                (devices_table.c.owner_id == owner_id)
            )
        )
        return created

    except IntegrityError as e:
        msg = str(getattr(e, "orig", e))
        print(f"[ADD_DEVICE IntegrityError] {msg}")
        if "unique" in msg.lower() and "ip_address" in msg:
            raise HTTPException(status_code=409, detail="Ya existe un dispositivo con esa IP.")
        if "devices_maestro_id_fkey" in msg:
            raise HTTPException(status_code=400, detail="El maestro referenciado no existe.")
        if "devices_vpn_profile_id_fkey" in msg:
            raise HTTPException(status_code=400, detail="El perfil VPN referenciado no existe.")
        if "devices_credential_id_fkey" in msg:
            raise HTTPException(status_code=400, detail="La credencial referenciada no existe.")
        raise HTTPException(status_code=400, detail=f"Error BD al insertar dispositivo: {msg}")

    except Exception as e:
        print(f"[ADD_DEVICE ERROR] {e!r}")
        raise HTTPException(status_code=400, detail=f"Error inesperado: {e}")

@app.get("/api/devices")
async def get_all_devices(is_maestro: Optional[bool] = None, owner_id: str = Depends(get_owner_id)):
    q = devices_table.select().where(devices_table.c.owner_id == owner_id)
    if is_maestro is not None:
        q = q.where(devices_table.c.is_maestro == is_maestro)
    return await database.fetch_all(q)

@app.put("/api/devices/{device_id}/promote", status_code=200)
async def promote_device_to_maestro(device_id: str, owner_id: str = Depends(get_owner_id)):
    await database.execute(
        devices_table.update()
        .where((devices_table.c.id == device_id) & (devices_table.c.owner_id == owner_id))
        .values(is_maestro=True, maestro_id=None)
    )
    return {"message": "Dispositivo promovido a Maestro."}

@app.delete("/api/devices/{device_id}", status_code=204)
async def remove_device_from_monitor(device_id: str, owner_id: str = Depends(get_owner_id)):
    # verifica propiedad
    dev = await database.fetch_one(
        devices_table.select().where(
            (devices_table.c.id == device_id) & (devices_table.c.owner_id == owner_id)
        )
    )
    if not dev:
        return
    # borra monitores (cascade sensores)
    await database.execute(
        monitors_table.delete().where(
            (monitors_table.c.device_id == device_id) & (monitors_table.c.owner_id == owner_id)
        )
    )
    # borra dispositivo
    await database.execute(
        devices_table.delete().where(
            (devices_table.c.id == device_id) & (devices_table.c.owner_id == owner_id)
        )
    )

@app.get("/api/devices/search", response_model=List[dict])
async def search_monitored_devices(search: Optional[str] = None, owner_id: str = Depends(get_owner_id)):
    if not search:
        return []
    search_term = f"%{search}%"
    q = devices_table.select().where(
        (devices_table.c.owner_id == owner_id) &
        ((devices_table.c.client_name.ilike(search_term)) | (devices_table.c.ip_address.ilike(search_term)))
    )
    return [dict(r._mapping) for r in await database.fetch_all(q)]

@app.post("/api/monitors", status_code=201)
async def create_monitor(monitor: MonitorCreate, owner_id: str = Depends(get_owner_id)):
    dev = await database.fetch_one(
        devices_table.select().where(
            (devices_table.c.id == monitor.device_id) &
            (devices_table.c.owner_id == owner_id)
        )
    )
    if not dev:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado.")

    try:
        last_id = await database.execute(
            monitors_table.insert().values(device_id=monitor.device_id, owner_id=owner_id)
        )
        return {"id": last_id, "device_id": monitor.device_id}
    except Exception:
        raise HTTPException(status_code=400, detail="Ya existe un monitor para este dispositivo.")

@app.post("/api/sensors", status_code=201)
async def add_sensor_to_monitor(sensor: SensorCreate, owner_id: str = Depends(get_owner_id)):
    mon = await database.fetch_one(
        monitors_table.select().where(
            (monitors_table.c.id == sensor.monitor_id) &
            (monitors_table.c.owner_id == owner_id)
        )
    )
    if not mon:
        raise HTTPException(status_code=404, detail="Monitor no encontrado.")

    last_id = await database.execute(
        sensors_table.insert().values(
            monitor_id=sensor.monitor_id,
            sensor_type=sensor.sensor_type,
            name=sensor.name,
            config=sensor.config,
            owner_id=owner_id,
        )
    )
    asyncio.create_task(launch_sensor_task(last_id))
    return {"id": last_id, **sensor.dict(), "config": sensor.config}

@app.post("/api/sensors/{sensor_id}/restart")
async def restart_sensor(sensor_id: int, owner_id: str = Depends(get_owner_id)):
    # verifica propiedad
    q = (
        sqlalchemy.select(sensors_table.c.id)
        .select_from(sensors_table.join(monitors_table, sensors_table.c.monitor_id == monitors_table.c.id))
        .where((sensors_table.c.id == sensor_id) & (monitors_table.c.owner_id == owner_id))
    )
    ok_row = await database.fetch_one(q)
    if not ok_row:
        raise HTTPException(status_code=404, detail="Sensor no encontrado.")

    if sensor_id in running_tasks:
        try:
            running_tasks[sensor_id].cancel()
        except Exception:
            pass
        running_tasks.pop(sensor_id, None)
    asyncio.create_task(launch_sensor_task(sensor_id))
    return {"status": "restarted"}

@app.put("/api/sensors/{sensor_id}")
async def update_sensor(sensor_id: int, sensor_data: SensorUpdate, owner_id: str = Depends(get_owner_id)):
    q_check = (
        sqlalchemy.select(sensors_table.c.id)
        .select_from(sensors_table.join(monitors_table, sensors_table.c.monitor_id == monitors_table.c.id))
        .where((sensors_table.c.id == sensor_id) & (monitors_table.c.owner_id == owner_id))
    )
    ok_row = await database.fetch_one(q_check)
    if not ok_row:
        raise HTTPException(status_code=404, detail="Sensor no encontrado.")

    await database.execute(
        sensors_table.update()
        .where(sensors_table.c.id == sensor_id)
        .values(name=sensor_data.name, config=sensor_data.config)
    )
    asyncio.create_task(launch_sensor_task(sensor_id))
    return {"id": sensor_id, **sensor_data.dict()}

@app.get("/api/monitors")
async def get_all_monitors_with_sensors(owner_id: str = Depends(get_owner_id)):
    sql, params = _monitors_query_sql_for_owner(owner_id)
    results = await database.fetch_all(sql, values=params)
    normalized = []
    for r in results:
        row = dict(r._mapping) if hasattr(r, "_mapping") else dict(r)
        sensors_val = row.get("sensors")
        if isinstance(sensors_val, str):
            row["sensors"] = json.loads(sensors_val) if sensors_val else []
        else:
            row["sensors"] = sensors_val or []
        normalized.append(row)
    return normalized

@app.delete("/api/sensors/{sensor_id}", status_code=204)
async def delete_sensor(sensor_id: int, owner_id: str = Depends(get_owner_id)):
    q_check = (
        sqlalchemy.select(sensors_table.c.id)
        .select_from(sensors_table.join(monitors_table, sensors_table.c.monitor_id == monitors_table.c.id))
        .where((sensors_table.c.id == sensor_id) & (monitors_table.c.owner_id == owner_id))
    )
    ok_row = await database.fetch_one(q_check)
    if not ok_row:
        return
    await database.execute(sensors_table.delete().where(sensors_table.c.id == sensor_id))
    if sensor_id in running_tasks:
        try:
            running_tasks[sensor_id].cancel()
        except Exception:
            pass
        running_tasks.pop(sensor_id, None)

@app.delete("/api/monitors/{monitor_id}", status_code=204)
async def delete_monitor_and_sensors(monitor_id: int, owner_id: str = Depends(get_owner_id)):
    mon = await database.fetch_one(
        monitors_table.select().where(
            (monitors_table.c.id == monitor_id) & (monitors_table.c.owner_id == owner_id)
        )
    )
    if not mon:
        return
    sensors_to_stop = await database.fetch_all(
        sensors_table.select().where(sensors_table.c.monitor_id == monitor_id)
    )
    for sensor in sensors_to_stop:
        sid = sensor["id"] if isinstance(sensor, dict) else sensor.id
        if sid in running_tasks:
            try:
                running_tasks[sid].cancel()
            except Exception:
                pass
            running_tasks.pop(sid, None)
    await database.execute(monitors_table.delete().where(monitors_table.c.id == monitor_id))

@app.get("/api/sensors/{sensor_id}/details")
async def get_sensor_details(sensor_id: int, owner_id: str = Depends(get_owner_id)):
    query = (
        sqlalchemy.select(
            sensors_table,
            devices_table.c.client_name,
            devices_table.c.ip_address,
        )
        .select_from(sensors_table.join(monitors_table).join(devices_table))
        .where((sensors_table.c.id == sensor_id) & (monitors_table.c.owner_id == owner_id))
    )
    result = await database.fetch_one(query)
    if not result:
        raise HTTPException(status_code=404, detail="Sensor no encontrado")
    return result

@app.get("/api/sensors/{sensor_id}/history_range")
async def get_sensor_history(sensor_id: int, time_range: str = Query("24h"), owner_id: str = Depends(get_owner_id)):
    sensor = await database.fetch_one(
        sensors_table.select().where(
            (sensors_table.c.id == sensor_id)
        ).select_from(
            sensors_table.join(monitors_table, sensors_table.c.monitor_id == monitors_table.c.id)
        ).where(
            monitors_table.c.owner_id == owner_id
        )
    )
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor no encontrado")

    range_map = {"1h": 1, "12h": 12, "24h": 24, "7d": 168, "30d": 720}
    hours_to_subtract = range_map.get(time_range, 24)

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(hours=hours_to_subtract)

    history_table = {
        "ping": ping_results_table,
        "ethernet": ethernet_results_table,
    }.get(sensor["sensor_type"])

    if history_table is None:
        return []

    query = (
        history_table.select()
        .where(history_table.c.sensor_id == sensor_id)
        .where(history_table.c.timestamp.between(start_date, end_date))
        .order_by(history_table.c.timestamp.asc())
    )
    return await database.fetch_all(query)


@app.get("/api/sensors/{sensor_id}/history_window")
async def get_sensor_history_window(
    sensor_id: int = Path(...),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    max_points: int = Query(2000, ge=100, le=20000),
    mode: str = Query("auto"),  # "auto" (agregada) | "raw"
    owner_id: str = Depends(get_owner_id),
):
    """
    Devuelve historial entre start/end con agregación adaptativa.
    - mode=raw => datos crudos
    - mode=auto => buckets para ~max_points si Postgres; si no, cae a crudo
    Respuesta: { items: [...], meta: {...} }
    """
    # 1) Validar que el sensor pertenece al owner y obtener tipo
    sensor_row = await database.fetch_one(
        sqlalchemy.select(
            sensors_table.c.id,
            sensors_table.c.sensor_type,
        ).select_from(
            sensors_table.join(monitors_table).join(devices_table)
        ).where(
            (sensors_table.c.id == sensor_id) & (devices_table.c.owner_id == owner_id)
        )
    )
    if not sensor_row:
        raise HTTPException(status_code=404, detail="Sensor no encontrado")

    s_type = sensor_row["sensor_type"]

    # 2) Parse de fechas
    end_dt = datetime.now(timezone.utc) if not end else datetime.fromisoformat(end)
    # si no viene start, default 24h
    start_dt = end_dt - timedelta(hours=24) if not start else datetime.fromisoformat(start)

    # 3) Tablas según tipo
    if s_type == "ping":
        table = "ping_results"
        base_fields = "latency_ms, status"
    elif s_type == "ethernet":
        table = "ethernet_results"
        base_fields = "rx_bitrate, tx_bitrate, status, speed"
    else:
        return {"items": [], "meta": {"from": start_dt.isoformat(), "to": end_dt.isoformat(), "mode": "raw"}}

    # 4) Si no es Postgres o pidieron raw => devolver crudo (ordenado)
    if not IS_POSTGRES or mode == "raw":
        sql = f"""
            SELECT *
              FROM {table}
             WHERE sensor_id = :sid
               AND timestamp BETWEEN :start AND :end
             ORDER BY timestamp ASC
        """
        rows = await database.fetch_all(sql, values={"sid": sensor_id, "start": start_dt, "end": end_dt})
        items = [dict(r._mapping) if hasattr(r, "_mapping") else dict(r) for r in rows]
        return {
            "items": items,
            "meta": {
                "from": start_dt.isoformat(),
                "to": end_dt.isoformat(),
                "bucket_seconds": 0,
                "rows_returned": len(items),
                "mode": "raw",
            },
        }

    # 5) Postgres + auto => bucketing
    bucket = _choose_bucket_seconds(start_dt, end_dt, max_points=max_points)

    if s_type == "ping":
        sql = """
            WITH buckets AS (
              SELECT
                to_timestamp(floor(extract(epoch from timestamp)/:bucket)*:bucket) AS ts,
                latency_ms,
                status
              FROM ping_results
              WHERE sensor_id = :sid AND timestamp BETWEEN :start AND :end
            )
            SELECT
              ts AS timestamp,
              AVG(latency_ms) AS latency_ms,
              (ARRAY_AGG(status ORDER BY ts DESC))[1] AS status
            FROM buckets
            GROUP BY ts
            ORDER BY ts ASC
        """
        vals = {"sid": sensor_id, "start": start_dt, "end": end_dt, "bucket": bucket}

    else:  # ethernet
        sql = """
            WITH buckets AS (
              SELECT
                to_timestamp(floor(extract(epoch from timestamp)/:bucket)*:bucket) AS ts,
                COALESCE(NULLIF(rx_bitrate,'')::bigint,0) AS rx,
                COALESCE(NULLIF(tx_bitrate,'')::bigint,0) AS tx,
                status,
                speed
              FROM ethernet_results
              WHERE sensor_id = :sid AND timestamp BETWEEN :start AND :end
            )
            SELECT
              ts AS timestamp,
              AVG(rx) AS rx_bitrate,
              AVG(tx) AS tx_bitrate,
              (ARRAY_AGG(status ORDER BY ts DESC))[1] AS status,
              (ARRAY_AGG(speed  ORDER BY ts DESC))[1] AS speed
            FROM buckets
            GROUP BY ts
            ORDER BY ts ASC
        """
        vals = {"sid": sensor_id, "start": start_dt, "end": end_dt, "bucket": bucket}

    rows = await database.fetch_all(sql, values=vals)
    items = [dict(r._mapping) if hasattr(r, "_mapping") else dict(r) for r in rows]

    return {
        "items": items,
        "meta": {
            "from": start_dt.isoformat(),
            "to": end_dt.isoformat(),
            "bucket_seconds": bucket,
            "rows_returned": len(items),
            "mode": "aggregated",
        },
    }


# ==========================================================
# Endpoints: canales / alertas / Telegram
# ==========================================================

@app.post("/api/channels", status_code=201)
async def create_channel(channel: NotificationChannelCreate, owner_id: str = Depends(get_owner_id)):
    q = notification_channels_table.insert().values(
        name=channel.name, type=channel.type, config=channel.config, owner_id=owner_id
    )
    last_record_id = await database.execute(q)
    return {**channel.dict(), "id": last_record_id}

@app.get("/api/channels")
async def get_channels(owner_id: str = Depends(get_owner_id)):
    q = notification_channels_table.select().where(notification_channels_table.c.owner_id == owner_id)
    results = await database.fetch_all(q)
    return [dict(r._mapping) for r in results]

@app.delete("/api/channels/{channel_id}", status_code=204)
async def delete_channel(channel_id: int, owner_id: str = Depends(get_owner_id)):
    await database.execute(
        notification_channels_table.delete().where(
            (notification_channels_table.c.id == channel_id) &
            (notification_channels_table.c.owner_id == owner_id)
        )
    )

@app.post("/api/channels/telegram/get_chats")
async def get_telegram_chats(token_data: TelegramToken, owner_id: str = Depends(get_owner_id)):
    bot_token = token_data.bot_token
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Error de la API de Telegram: {data.get('description')}",
                )
            chats: Dict[str, Dict[str, Any]] = {}
            for update in data.get("result", []):
                message = update.get("message") or update.get("my_chat_member", {}).get("chat")
                if message:
                    chat = message.get("chat")
                    if chat:
                        chat_id = chat.get("id")
                        title = chat.get("title") or f"{chat.get('first_name', '')} {chat.get('last_name', '')}".strip()
                        if chat_id and title:
                            chats[chat_id] = {"id": chat_id, "title": title}
            return list(chats.values())
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"No se pudo conectar con la API de Telegram: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error procesando la respuesta: {e}")

@app.get("/api/alerts/history")
async def get_alert_history(owner_id: str = Depends(get_owner_id)):
    query = """
    SELECT h.id, h.timestamp, h.details, s.name as sensor_name, c.name as channel_name
      FROM alert_history h
      JOIN sensors s ON h.sensor_id = s.id
      JOIN notification_channels c ON h.channel_id = c.id
     WHERE s.owner_id = :owner_id AND c.owner_id = :owner_id
     ORDER BY h.timestamp DESC
     LIMIT 100
    """
    return await database.fetch_all(query, values={"owner_id": owner_id})

# ==========================================================
# Endpoints: VPN perfiles
# ==========================================================

@app.post("/api/vpns", status_code=201)
async def create_vpn_profile(profile: VpnProfileCreate, owner_id: str = Depends(get_owner_id)):
    try:
        validate_wg_config(profile.config_data)
        name = (profile.name or "").strip()
        # 🔹 normalizamos el config antes de guardarlo
        cfg_norm = _normalize_wg_config(profile.config_data)

        res = await database.execute(
            vpn_profiles_table.insert().values(
                name=name,
                config_data=cfg_norm,
                check_ip=profile.check_ip or "",
                is_default=False,
                owner_id=owner_id,
            )
        )
        return {**profile.dict(), "config_data": cfg_norm, "id": res}
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Nombre de perfil duplicado.")
    except Exception as e:
        print(f"[DB ERROR] create_vpn_profile -> {e!r}")
        raise HTTPException(status_code=400, detail=f"Error creando perfil: {e}")


@app.get("/api/vpns")
async def list_vpn_profiles(owner_id: str = Depends(get_owner_id)):
    rows = await database.fetch_all(
        vpn_profiles_table.select().where(vpn_profiles_table.c.owner_id == owner_id)
    )
    return [dict(r._mapping) for r in rows]


@app.put("/api/vpns/{profile_id}")
async def update_vpn_profile(
    profile_id: int,
    profile: VpnProfileUpdate,
    owner_id: str = Depends(get_owner_id)
):
    update_data = profile.dict(exclude_unset=True)

    if "config_data" in update_data and update_data["config_data"]:
        update_data["config_data"] = _normalize_wg_config(update_data["config_data"])
    if "config_data" in update_data and update_data["config_data"]:
        validate_wg_config(update_data["config_data"])
        update_data["config_data"] = _normalize_wg_config(update_data["config_data"])
        

    if update_data.get("is_default") is True:
        await database.execute(
            vpn_profiles_table.update()
            .where(vpn_profiles_table.c.owner_id == owner_id)
            .values(is_default=False)
        )
        update_data["is_default"] = True

    q = (
        vpn_profiles_table.update()
        .where((vpn_profiles_table.c.id == profile_id) & (vpn_profiles_table.c.owner_id == owner_id))
        .values(**update_data)
    )
    await database.execute(q)

    # 🔹 leer el perfil actualizado y devolverlo entero
    updated = await database.fetch_one(
        vpn_profiles_table.select().where(
            (vpn_profiles_table.c.id == profile_id) &
            (vpn_profiles_table.c.owner_id == owner_id)
        )
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Perfil no encontrado.")

    return dict(updated._mapping)


@app.delete("/api/vpns/{profile_id}", status_code=204)
async def delete_vpn_profile(profile_id: int, owner_id: str = Depends(get_owner_id)):
    query_check = devices_table.select().where(
        (devices_table.c.vpn_profile_id == profile_id) & (devices_table.c.owner_id == owner_id)
    )
    associated_device = await database.fetch_one(query_check)
    if associated_device:
        raise HTTPException(
            status_code=400,
            detail=f"No se puede eliminar. El perfil está en uso por '{associated_device['client_name']}'.",
        )
    query = vpn_profiles_table.delete().where(
        (vpn_profiles_table.c.id == profile_id) & (vpn_profiles_table.c.owner_id == owner_id)
    )
    await database.execute(query)
    return {}

# =====================================================================
# 🔍 Estado de peers WireGuard (para detectar handshake desde el front)
# =====================================================================

def _parse_wg_dump(stdout: str):
    """
    Parsea el output de `wg show all dump`
    iface\tpublic_key\tpreshared_key\tendpoint\tallowed_ips\tlatest_hs\trx\ttx\tkeepalive
    """
    rows = []
    for line in stdout.strip().splitlines():
        parts = line.split('\t')
        if len(parts) < 9:
            continue
        rows.append({
            "iface": parts[0],
            "public_key": parts[1],
            "endpoint": parts[3],
            "allowed_ips": parts[4],
            "latest_handshake": int(parts[5]) if parts[5].isdigit() else 0,
            "transfer_rx": int(parts[6]) if parts[6].isdigit() else 0,
            "transfer_tx": int(parts[7]) if parts[7].isdigit() else 0,
            "persistent_keepalive": int(parts[8]) if parts[8].isdigit() else 0,
        })
    return rows


async def _peer_status_by_pub(pub_key_b64: str):
    # Ejecuta `wg show all dump` y busca el peer por su public key
    ok, out = await run_command(["wg", "show", "all", "dump"], env=WG_ENV_BASE, quiet=True)
    if not ok:
        raise HTTPException(status_code=500, detail=f"wg show all dump failed: {out}")
    rows = _parse_wg_dump(out)
    for r in rows:
        if r["public_key"] == pub_key_b64:
            r["found"] = True
            return r
    return {"found": False}


# === Versiones con query param (RECOMENDADA para frontend) ===

@app.get("/api/vpns/peer_status")
async def vpn_peer_status_q(pub: str):
    pub = unquote(pub)
    return await _peer_status_by_pub(pub)


@app.get("/api/vpns/peer-status")
async def vpn_peer_status_dash_q(pub: str):
    pub = unquote(pub)
    return await _peer_status_by_pub(pub)


# === Versiones con path param (compatibilidad con versiones viejas del front) ===

@app.get("/api/vpns/peer_status/{pub}")
async def vpn_peer_status_path(pub: str):
    pub = unquote(pub)
    return await _peer_status_by_pub(pub)


@app.get("/api/vpns/peer-status/{pub}")
async def vpn_peer_status_dash_path(pub: str):
    pub = unquote(pub)
    return await _peer_status_by_pub(pub)


# ==========================================================
# WebSocket endpoint (token opcional en ?token=)
# ==========================================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # --------- Autenticación por token en query ---------
    token = websocket.query_params.get("token")
    owner_id = _owner_from_token(token) if token else None
    if not owner_id:
        await websocket.close(code=4401, reason="unauthorized")
        return

    # --------- Helpercitos locales ---------
    async def _owner_sensors(sensor_ids: Optional[List[int]] = None) -> List[dict]:
        q = (
            sqlalchemy.select(sensors_table.c.id, sensors_table.c.sensor_type)
            .select_from(
                sensors_table.join(
                    monitors_table, sensors_table.c.monitor_id == monitors_table.c.id
                ).join(
                    devices_table, monitors_table.c.device_id == devices_table.c.id
                )
            )
            .where(devices_table.c.owner_id == owner_id)
        )
        rows = await database.fetch_all(q)
        sensors = [
            {
                "id": (r.id if hasattr(r, "id") else r[0]),
                "sensor_type": (r.sensor_type if hasattr(r, "sensor_type") else r[1]),
            }
            for r in rows
        ]
        if sensor_ids:
            sset = set(sensor_ids)
            sensors = [s for s in sensors if s["id"] in sset]
        return sensors

    async def _latest_for_sensor(sid: int, stype: str) -> Optional[dict]:
        if stype == "ping":
            row = await database.fetch_one(
                ping_results_table.select()
                .where(ping_results_table.c.sensor_id == sid)
                .order_by(ping_results_table.c.timestamp.desc())
                .limit(1)
            )
            if row:
                return {
                    "sensor_id": sid,
                    "sensor_type": "ping",
                    "status": row["status"],
                    "latency_ms": row["latency_ms"],
                    "timestamp": (
                        row["timestamp"].astimezone(timezone.utc).isoformat()
                        if isinstance(row["timestamp"], datetime)
                        else None
                    ),
                }
        elif stype == "ethernet":
            row = await database.fetch_one(
                ethernet_results_table.select()
                .where(ethernet_results_table.c.sensor_id == sid)
                .order_by(ethernet_results_table.c.timestamp.desc())
                .limit(1)
            )
            if row:
                return {
                    "sensor_id": sid,
                    "sensor_type": "ethernet",
                    "status": row["status"],
                    "speed": row["speed"],
                    "rx_bitrate": row["rx_bitrate"],
                    "tx_bitrate": row["tx_bitrate"],
                    "timestamp": (
                        row["timestamp"].astimezone(timezone.utc).isoformat()
                        if isinstance(row["timestamp"], datetime)
                        else None
                    ),
                }
        return None

    async def _send_initial_batch():
        sub_ids = websocket.scope.get("subs")
        sensors = await _owner_sensors(list(sub_ids) if sub_ids else None)

        items: List[dict] = []
        for s in sensors:
            last = await _latest_for_sensor(s["id"], s["sensor_type"])
            if last:
                items.append(last)
            else:
                now_iso = datetime.now(timezone.utc).isoformat()
                if s["sensor_type"] == "ping":
                    items.append({"sensor_id": s["id"], "sensor_type": "ping",
                                "status": "pending", "latency_ms": None, "timestamp": now_iso})
                elif s["sensor_type"] == "ethernet":
                    items.append({"sensor_id": s["id"], "sensor_type": "ethernet",
                                "status": "pending", "speed": "N/A",
                                "rx_bitrate": "0", "tx_bitrate": "0", "timestamp": now_iso})

        try:
            print(f"[WS] initial_batch -> owner={owner_id} items={len(items)}")
            await websocket.send_text(json.dumps({
                "type": "sensor_batch",
                "items": items,
                "ts": datetime.now(timezone.utc).isoformat(),
            }))
        except WebSocketDisconnect:
            print(f"[WS] cliente cerró antes de aceptar batch")
        except Exception as e:
            print(f"[WS] error enviando sensor_batch: {e}")

    # --------- Registrar conexión ---------
    await manager.connect(websocket, owner_id)
    websocket.scope.setdefault("subs", None)
    print(f"[WS] CONNECT owner={owner_id} total_active={len(manager.active)}")

    try:
        # Handshake + READY + batch inicial AUTOMÁTICO
        await websocket.send_text(json.dumps({
            "type": "welcome",
            "hello": True,
            "ts": datetime.now(timezone.utc).isoformat(),
        }))
        await websocket.send_text(json.dumps({
            "type": "ready",
            "ts": datetime.now(timezone.utc).isoformat(),
        }))
        # Enviar el batch inicial sin esperar pedido del cliente
        await _send_initial_batch()

        # Bucle de mensajes del cliente
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                print(f"[WS] DISCONNECT owner={owner_id}")
                break

            try:
                msg = json.loads(raw)
            except Exception as e:
                print(f"[WS] msg no-JSON: {e}  raw={raw[:200]}")
                continue

            mtype = (msg.get("type") or "").lower()
            print(f"[WS] recv owner={owner_id} type={mtype} msg={msg}")

            if mtype == "ping":
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "ts": datetime.now(timezone.utc).isoformat(),
                }))

            elif mtype == "subscribe_sensors":
                ids = msg.get("sensor_ids")
                if isinstance(ids, list) and all(isinstance(x, int) for x in ids):
                    websocket.scope["subs"] = set(ids)
                    print(f"[WS] subscribe_sensors owner={owner_id} n={len(ids)}")
                else:
                    websocket.scope["subs"] = None
                    print(f"[WS] subscribe_sensors owner={owner_id} -> limpiado (formato inválido)")

                await websocket.send_text(json.dumps({
                    "type": "ready",
                    "ts": datetime.now(timezone.utc).isoformat(),
                }))
                # y mandamos batch tras suscripción
                await _send_initial_batch()

            elif mtype == "subscribe_all":
                websocket.scope["subs"] = None
                print(f"[WS] subscribe_all owner={owner_id}")
                await websocket.send_text(json.dumps({
                    "type": "ready",
                    "ts": datetime.now(timezone.utc).isoformat(),
                }))
                await _send_initial_batch()

            elif mtype == "sync_request" and (msg.get("resource") == "sensors_latest"):
                print(f"[WS] sync_request owner={owner_id} -> sensors_latest")
                await _send_initial_batch()

            else:
                # Mensaje no reconocido
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "error": f"unknown_message_type: {mtype}",
                    "ts": datetime.now(timezone.utc).isoformat(),
                }))

    finally:
        manager.disconnect(websocket)
        print(f"[WS] CLOSE owner={owner_id} total_active={len(manager.active)}")



# Endpoints de depuración (opcionales)
# ==========================================================

@app.get("/api/_debug/wg")
async def debug_wg():
    ip_link = await wg_cmd(["ip", "link", "show"])
    wg_show = await wg_cmd(["wg", "show"])
    return {
        "ip_link_ok": ip_link[0],
        "ip_link": ip_link[1],
        "wg_show_ok": wg_show[0],
        "wg_show": wg_show[1],
        "vpn_state": VPN_STATE,
    }

@app.get("/api/_debug/routes")
async def debug_routes():
    r1 = await wg_cmd(["ip", "-4", "route"])
    r2 = await wg_cmd(["ip", "-6", "route"])
    r3 = await wg_cmd(["ip", "rule"])
    return {
        "ipv4_route_ok": r1[0], "ipv4_route": r1[1],
        "ipv6_route_ok": r2[0], "ipv6_route": r2[1],
        "ip_rule_ok": r3[0],   "ip_rule": r3[1],
    }

@app.get("/api/debug/whoami")
async def whoami(user_id: str = Depends(get_owner_id)):
    return JSONResponse({"owner_id": user_id})

@app.get("/api/debug/dump-token")
async def dump_token(request: Request):
    """
    Devuelve header y payload del JWT recibido en Authorization (o en cookie sb-access-token).
    OJO: NO valida la firma; es solo para depuración.
    """
    # 1) Buscar token en Authorization o cookie
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    if not token:
        token = request.cookies.get("sb-access-token")

    if not token:
        return JSONResponse({"error": "Falta Authorization Bearer o cookie sb-access-token"}, status_code=400)

    # 2) Extraer header/payload sin verificar
    try:
        header = jwt.get_unverified_header(token)
    except Exception as e:
        return JSONResponse({"error": f"No se pudo leer el header: {e}"}, status_code=400)

    try:
        payload = jwt.decode(
            token,
            options={"verify_signature": False, "verify_aud": False},
            leeway=300,
        )
    except Exception as e:
        return JSONResponse({"error": f"No se pudo decodificar el payload: {e}"}, status_code=400)

    return JSONResponse({
        "header": header,
        "payload": payload,
        "alg": header.get("alg"),
        "kid": header.get("kid"),
        "sub_hint": payload.get("sub"),
        "iss": payload.get("iss"),
        "exp": payload.get("exp"),
        "now_utc": datetime.now(timezone.utc).isoformat(),
        "note": "Firma NO verificada (uso exclusivo de debug).",
    })