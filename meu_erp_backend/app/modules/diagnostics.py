"""Diagnostico temporario e protegido da API, Supabase e autenticacao."""
from __future__ import annotations

import secrets
from datetime import UTC, datetime
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.config import get_settings
from app.core.database import check_database_connection, supabase_project_id


api_router = APIRouter(prefix="/health", tags=["Diagnostico"])
page_router = APIRouter(tags=["Diagnostico"])
basic = HTTPBasic(auto_error=False)


def require_diagnostic_admin(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(basic)],
) -> None:
    settings = get_settings()
    if not settings.diagnostic_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if not settings.diagnostic_username or not settings.diagnostic_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Diagnostico habilitado sem credenciais administrativas.",
        )
    valid = bool(credentials) and secrets.compare_digest(
        credentials.username.encode("utf-8"), settings.diagnostic_username.encode("utf-8")
    ) and secrets.compare_digest(
        credentials.password.encode("utf-8"), settings.diagnostic_password.encode("utf-8")
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acesso administrativo obrigatorio.",
            headers={"WWW-Authenticate": 'Basic realm="Lumina diagnostics"'},
        )


Admin = Annotated[None, Depends(require_diagnostic_admin)]


@api_router.get("/supabase")
def supabase_health(response: Response, _: Admin) -> dict:
    settings = get_settings()
    started = perf_counter()
    configured_project = supabase_project_id()
    configuration = {
        "url_configured": settings.supabase_is_configured,
        "publishable_key_configured": bool(settings.effective_anon_key),
        "secret_key_configured": bool(settings.effective_secret_key),
    }
    connected = False
    error_stage = None
    try:
        check_database_connection()
        connected = configured_project == settings.supabase_expected_project_id
        if not connected:
            error_stage = "project_validation"
    except Exception:
        error_stage = "supabase_connection"
    if not connected:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    response.headers["Cache-Control"] = "no-store"
    return {
        "api": "online",
        "supabase": "connected" if connected else "disconnected",
        "project_id": configured_project,
        "configuration": configuration,
        "response_time_ms": round((perf_counter() - started) * 1000, 2),
        "tested_at": datetime.now(UTC).isoformat(),
        "error_stage": error_stage,
    }


DIAGNOSTIC_HTML = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Diagnostico Lumina POS</title><style>
:root{color-scheme:dark;--bg:#07111f;--card:#111c2f;--line:#263653;--text:#edf4ff;--muted:#9db0cd;--ok:#18c98b;--warn:#f4bd4a;--bad:#f06464}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(145deg,#07111f,#101a30);color:var(--text);font:15px system-ui,sans-serif;min-height:100vh}.wrap{max-width:960px;margin:auto;padding:36px 20px}h1{margin:0 0 8px;font-size:28px}p{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:24px 0}.card,.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}.label{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.1em}.value{font-size:18px;font-weight:700;margin-top:8px}.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}form{display:grid;gap:14px;margin-top:15px}label{font-weight:650}input{width:100%;margin-top:7px;padding:12px;border-radius:9px;border:1px solid var(--line);background:#091426;color:var(--text)}.password{display:flex;gap:8px}.password input{flex:1}.password button{margin-top:7px}button{padding:11px 16px;border:0;border-radius:9px;background:var(--ok);color:#03140f;font-weight:750;cursor:pointer}button.secondary{background:#263653;color:var(--text)}button:disabled{opacity:.55}.result{margin-top:16px;padding:14px;border-radius:10px;background:#091426;white-space:pre-wrap;line-height:1.55}.small{font-size:12px}.footer{margin-top:18px;color:var(--warn)}
</style></head><body><main class="wrap"><h1>Diagnostico Lumina POS</h1><p>Verificacao temporaria e administrativa. Nenhuma chave, senha ou token e exibido.</p>
<section class="grid"><article class="card"><div class="label">API</div><div id="api" class="value warn">Verificando...</div><div id="apiMeta" class="small"></div></article><article class="card"><div class="label">Supabase</div><div id="supabase" class="value warn">Verificando...</div><div id="project" class="small"></div></article><article class="card"><div class="label">Variaveis de ambiente</div><div id="environment" class="value warn">Verificando...</div></article><article class="card"><div class="label">Perfil</div><div id="profile" class="value warn">Aguardando login</div></article></section>
<section class="panel"><h2>Teste de autenticacao</h2><form id="loginForm" autocomplete="off"><label>E-mail<input id="email" type="email" required autocomplete="username"></label><label>Senha<div class="password"><input id="password" type="password" required autocomplete="current-password"><button class="secondary" id="toggle" type="button">Mostrar</button></div></label><button id="submit" type="submit">Testar login</button></form><div id="result" class="result">Aguardando teste.</div></section><div class="footer">Desative ERP_DIAGNOSTIC_ENABLED depois da validacao.</div></main>
<script>
const $=id=>document.getElementById(id); const set=(id,text,kind)=>{const e=$(id);e.textContent=text;e.className='value '+kind};
async function health(){const begin=performance.now();try{const api=await fetch('/health',{cache:'no-store'});const ms=Math.round(performance.now()-begin);set('api',api.ok?'Conectado':'Erro',api.ok?'ok':'bad');$('apiMeta').textContent=location.origin+' | '+ms+' ms | '+new Date().toLocaleString();const r=await fetch('/api/health/supabase',{cache:'no-store'});const d=await r.json();set('supabase',d.supabase==='connected'?'Conectado':'Desconectado',d.supabase==='connected'?'ok':'bad');$('project').textContent='Projeto: '+(d.project_id||'nao identificado')+' | '+d.response_time_ms+' ms';const c=d.configuration||{};const all=c.url_configured&&c.publishable_key_configured&&c.secret_key_configured;set('environment',all?'Configuradas':'Incompletas',all?'ok':'warn')}catch(e){set('api','Offline','bad');set('supabase','Nao verificado','bad');set('environment','Nao verificado','bad')}}
$('toggle').onclick=()=>{const p=$('password');p.type=p.type==='password'?'text':'password';$('toggle').textContent=p.type==='password'?'Mostrar':'Ocultar'};
$('loginForm').onsubmit=async ev=>{ev.preventDefault();const button=$('submit'),password=$('password');button.disabled=true;$('result').textContent='Testando...';set('profile','Consultando...','warn');try{const response=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:$('email').value,password:password.value})});const data=await response.json();if(!response.ok){const message=data.error?.message||data.detail||'Falha nao identificada.';const cause=response.status===401?'Credenciais incorretas, conta inexistente ou confirmacao pendente.':response.status===429?'Limite de tentativas atingido. Aguarde antes de repetir.':response.status>=500?'Falha de configuracao, rede ou indisponibilidade do Supabase.':'Dados enviados nao foram aceitos.';$('result').textContent=`Autenticacao: falha\nHTTP: ${response.status}\nEtapa: autenticacao\nMensagem: ${message}\nPossivel causa: ${cause}`;set('profile','Nao consultado','bad');return}const a=data.authentication||{},p=data.profile||{};$('result').textContent=`Login realizado\nID do usuario: ${a.user_id||'nao informado'}\nE-mail: ${a.email||'nao informado'}\nE-mail confirmado: ${a.email_confirmed===true?'sim':a.email_confirmed===false?'nao':'nao disponivel'}\nToken recebido: ${data.access_token?'sim':'nao'}\nValidade: ${data.expires_in?data.expires_in+' segundos':'nao disponivel'}\nPerfil: ${p.found?'encontrado':'nao encontrado'}\nNome: ${p.name||'nao disponivel'}\nCPF: ${p.cpf_masked||'nao disponivel'}\nID relacionado: ${p.user_id||a.user_id||'nao informado'}`;set('profile',p.found?'Encontrado':p.lookup_status==='unavailable'?'Consulta indisponivel':'Nao encontrado',p.found?'ok':'warn');data.access_token=null;data.refresh_token=null}catch(e){$('result').textContent='Falha na etapa de comunicacao com a API.';set('profile','Nao consultado','bad')}finally{password.value='';password.type='password';$('toggle').textContent='Mostrar';button.disabled=false}};
health();
</script></body></html>"""


@page_router.get("/teste-conexao", response_class=HTMLResponse, include_in_schema=False)
def diagnostic_page(_: Admin) -> HTMLResponse:
    return HTMLResponse(
        DIAGNOSTIC_HTML,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                "img-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
            ),
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
        },
    )
