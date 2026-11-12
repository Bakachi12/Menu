"""Vista web de la terminal de cocina, incluida también en el ejecutable."""
PAGINA = """<!doctype html>
<html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PedidosCocina</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#0b1220;color:#f4f2ed;font:17px system-ui}
main{max-width:1040px;margin:auto;padding:24px}header{display:flex;align-items:baseline;gap:20px;flex-wrap:wrap;border-bottom:1px solid #34445a}
h1{font-size:30px;margin:0 0 14px}#estado{color:#e7be72}#cola{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(290px,100%),1fr));gap:14px;margin-top:20px}
article{background:#172234;border:1px solid #34445a;border-radius:12px;padding:18px}h2{margin:10px 0;font-size:24px}
small{color:#d4c4aa}p{margin:6px 0}.extra{color:#ffcf78;font-weight:650}
button{margin-top:12px;border:0;border-radius:8px;background:#e4b866;color:#151b24;font:600 17px system-ui;min-height:46px;padding:8px 20px}
</style><main><header><h1>PedidosCocina</h1><span id="estado" role="status"></span></header><section id="cola"></section></main>
<script>
const estado=document.querySelector('#estado'), cola=document.querySelector('#cola');
const clave=location.hash.slice(1)||sessionStorage.getItem('enlaceCocina')||'';
if(location.hash){sessionStorage.setItem('enlaceCocina',clave);history.replaceState(null,'',location.pathname)}
async function api(ruta,method='GET'){
  const r=await fetch(ruta,{method,headers:{Authorization:'Bearer '+clave},cache:'no-store'});
  if(!r.ok)throw Error(r.status===401?'Abre el enlace de cocina generado por la caja.':'Sin conexión con la caja. Reintentando…');
  return r.json();
}
function texto(padre,tipo,valor,clase=''){
  const n=document.createElement(tipo);n.className=clase;n.textContent=valor;padre.append(n);return n;
}
let ocupado=false, ultimaCola='';
async function actualizar(listo){
  if(ocupado)return;
  ocupado=true;
  try{
    if(listo)await api('/api/cocina/'+listo+'/lista','POST');
    const ordenes=await api('/api/cocina');
    estado.textContent=ordenes.length?'Pendientes: '+ordenes.length:'Sin órdenes pendientes';
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
      const boton=texto(tarjeta,'button','Marcar lista');
      boton.onclick=()=>actualizar(o.id);
      grupo.append(tarjeta);
    }
    cola.replaceChildren(grupo);
    ultimaCola=contenido;
  }catch(e){estado.textContent=e.message}
  finally{ocupado=false}
}
actualizar();setInterval(()=>actualizar(),2000);
</script></html>""".encode('utf-8')
