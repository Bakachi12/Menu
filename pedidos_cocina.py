"""Copia del HTML para el empaquetado actual de Menu.exe. La prueba comprueba su igualdad."""
PAGINA = r'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PedidosCocina</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#0b1220;color:#f4f2ed;font:17px system-ui}
main{max-width:1040px;margin:auto;padding:24px}header{display:flex;align-items:baseline;gap:20px;flex-wrap:wrap;border-bottom:1px solid #34445a}
h1{font-size:30px;margin:0 0 14px}#estado{color:#e7be72}#cola{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(290px,100%),1fr));gap:14px;margin-top:20px}
article{background:#172234;border:1px solid #34445a;border-radius:12px;padding:18px}h2{margin:10px 0;font-size:24px}
small{color:#d4c4aa}p{margin:6px 0}.extra{color:#ffcf78;font-weight:650}
button{margin-top:12px;border:0;border-radius:8px;background:#e4b866;color:#151b24;font:600 17px system-ui;min-height:46px;padding:8px 20px}
[hidden]{display:none!important}form{max-width:440px;margin:24px auto;padding:22px;background:#172234;border-radius:12px}
label,input{display:block;width:100%}label{margin:14px 0 5px}input{background:#0b1220;border:1px solid #546782;color:#fff;border-radius:8px;padding:12px;font:inherit}
.secundario{background:#28364a;color:#fff}nav{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
</style></head><body><main>
<header><h1>PedidosCocina</h1><span id="estado" role="status"></span></header>
<form id="vincular"><h2>Vincular tablet</h2>
<label for="enlace">Enlace de PedidosCocina generado en la caja</label>
<input id="enlace" type="password" autocomplete="off" required><button>Vincular con la caja</button></form>
<form hidden id="acceso"><h2>Iniciar sesión</h2><label for="usuario">Usuario</label>
<input id="usuario" autocomplete="username" required maxlength="128">
<label for="password">Contraseña</label><input id="password" type="password" autocomplete="current-password" maxlength="128" required>
<button id="entrar">Iniciar sesión</button> <button class="secundario" type="button" id="cambiar">Cambiar vínculo</button></form>
<nav hidden id="perfil"><strong id="nombre"></strong><button id="historial" class="secundario">Rellamar orden</button><button class="secundario" id="salir">Cerrar sesión</button></nav>
<section hidden id="cola"></section><button hidden id="mas" class="secundario">Ver anteriores</button><button hidden id="volver" class="secundario">Página anterior</button></main>
<script>
const el=id=>document.getElementById(id);
const estado=el('estado'), cola=el('cola');
let clave='', token='';
function modo(vista){
  el('vincular').hidden=vista!=='vincular'; el('acceso').hidden=vista!=='acceso';
  el('perfil').hidden=cola.hidden=vista!=='cola';
}
function direccion(valor){
  const url=new URL(valor);
  if(!['http:','https:'].includes(url.protocol)||url.username||url.password||
     url.pathname!=='/cocina'||url.search||!/^#[A-Za-z0-9_-]{20,100}$/.test(url.hash))
    throw Error('Copia el enlace completo de PedidosCocina desde Configuración en la caja.');
  return url;
}
function guardar(k,v){try{if(v)localStorage.setItem(k,v);else localStorage.removeItem(k)}catch{}}
function leer(k){try{return localStorage.getItem(k)||''}catch{return ''}}
const alojada=['http:','https:'].includes(location.protocol)&&location.pathname==='/cocina';
if(alojada){
  if(location.hash){
    try{clave=direccion(location.href).hash.slice(1);guardar('cocina-vinculo',clave)}
    catch(e){estado.textContent=e.message}
    history.replaceState(null,'',location.pathname);
  }else clave=leer('cocina-vinculo');
}else el('enlace').value=leer('cocina-destino');
modo(clave?'acceso':'vincular');
el('vincular').onsubmit=e=>{
  e.preventDefault();
  try{
    const url=direccion(el('enlace').value.trim());
    if(!alojada)guardar('cocina-destino',url.href);
    location.replace(url.href);
    if(alojada && url.origin===location.origin)location.reload();
  }catch{estado.textContent='Pega el enlace completo de cocina, incluida su clave.'}
};
el('cambiar').onclick=()=>{clave='';guardar('cocina-vinculo','');el('enlace').value='';modo('vincular');estado.textContent=''};
function cerrar(){
  token=''; historial=false; paginas=[null]; revision++; controles(); ultimaCola='';cola.replaceChildren();el('nombre').textContent='';
  el('password').value='';modo('acceso');
}
async function api(ruta,method='GET',datos){
  const sesion=token;
  const r=await fetch(ruta,{method,headers:{Authorization:'Bearer '+clave,'X-Sesion':sesion,
    ...(datos?{'Content-Type':'application/json'}:{})},body:datos?JSON.stringify(datos):undefined,cache:'no-store'});
  if(!r.ok){
    if(r.status===401&&sesion&&sesion===token)cerrar();
    const error=await r.json();throw Error(error.error||'No se pudo conectar con la caja.');
  }
  return r.json();
}
el('acceso').onsubmit=async e=>{
  e.preventDefault();el('entrar').disabled=el('cambiar').disabled=true;
  try{
    const r=await api('/api/cocina/login','POST',{usuario:el('usuario').value.trim(),password:el('password').value});
    token=r.token;el('password').value='';el('nombre').textContent=r.usuario;estado.textContent='Cargando órdenes…';modo('cola');actualizar();
  }catch(e){estado.textContent=e.message}
  finally{el('entrar').disabled=el('cambiar').disabled=false}
};
el('salir').onclick=async()=>{
  const fin=api('/api/cocina/logout','POST');cerrar();estado.textContent='Sesión cerrada';
  try{await fin}catch{/* El token se descarta también cuando la caja está desconectada. */}
};
function texto(padre,tipo,valor,clase=''){
  const n=document.createElement(tipo);n.className=clase;n.textContent=valor;padre.append(n);return n;
}
let historial=false, paginas=[null], revision=0, consultando=false, cambiando=false, ultimaCola='';
function controles(){
  el('historial').textContent=historial?'Volver a pendientes':'Rellamar orden';
  el('mas').hidden=true;el('volver').hidden=!historial||paginas.length===1;
}
function cambiarVista(){
  revision++;ultimaCola='';cola.replaceChildren();controles();estado.textContent='Cargando…';actualizar();
}
el('historial').onclick=()=>{historial=!historial;paginas=[null];cambiarVista()};
el('volver').onclick=()=>{paginas.pop();cambiarVista()};
async function cambiarOrden(id,accion){
  if(cambiando||!token)return;
  cambiando=true;revision++;consultando=false;
  try{
    await api('/api/cocina/'+id+'/'+accion,'POST');
  }catch(e){estado.textContent=e.message;return}
  finally{cambiando=false}
  actualizar();
}
async function actualizar(){
  if(!token||cambiando)return;
  const turno=++revision;
  consultando=true;
  try{
    const antes=paginas[paginas.length-1];
    const datos=await api(historial?'/api/cocina/listas'+(antes?'?antes='+antes:''):'/api/cocina');
    if(turno!==revision||!token)return;
    const ordenes=historial?datos.ordenes:datos;
    estado.textContent=historial?(ordenes.length?'Órdenes listas':'Sin órdenes listas en esta página'):
      (ordenes.length?'Pendientes: '+ordenes.length:'Sin órdenes pendientes');
    el('mas').hidden=!historial||!datos.hay_mas;
    if(historial&&datos.hay_mas)el('mas').onclick=()=>{paginas.push(ordenes[ordenes.length-1].id);cambiarVista()};
    const contenido=JSON.stringify(ordenes);
    if(contenido===ultimaCola)return;
    const grupo=document.createDocumentFragment();
    for(const o of ordenes){
      const tarjeta=document.createElement('article');
      const hora=new Date(o.fecha).toLocaleTimeString('es-PA',{hour:'2-digit',minute:'2-digit'});
      texto(tarjeta,'small','#'+o.id+' · '+hora+' · '+o.mesa+(o.cliente?' · '+o.cliente:''));
      texto(tarjeta,'h2',o.plato);
      if(o.preparacion)texto(tarjeta,'p','Preparación: '+o.preparacion);
      if(o.acompanamiento)texto(tarjeta,'p','Acompañamiento: '+o.acompanamiento);
      if(o.extra)texto(tarjeta,'p','1 porción extra de '+o.extra,'extra');
      const accion=historial?'rellamar':'lista';
      const boton=texto(tarjeta,'button',historial?'Devolver a pendientes':'Marcar lista');
      boton.onclick=()=>cambiarOrden(o.id,accion);
      grupo.append(tarjeta);
    }
    cola.replaceChildren(grupo);
    ultimaCola=contenido;
  }catch(e){if(!token||turno===revision)estado.textContent=e.message}
  finally{if(turno===revision)consultando=false}
}
setInterval(()=>{if(!consultando&&!cambiando)actualizar()},2000);
</script></body></html>
'''.encode('utf-8')
