const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('administracion.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
class Element{constructor(tag='div'){this.tag=tag;this.children=[];this.dataset={};this.classList={toggle(){}};this.value='';this.textContent='';this.hidden=false;this.open=false}append(...items){this.children.push(...items)}replaceChildren(...items){this.children=[...items]}showModal(){this.open=true}close(){this.open=false}}
const elements=new Map(),saved=new Map(),calls=[];function el(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id)}
const panel={usuario:'Admin',caja_usuario:{nombre:'Alberto'},turno:null,total_centimos:900,pagos:{Efectivo:0,Yappy:900,Clave:0,Visa:0},cuentas_abiertas:1,
 ventas:[{id:1,fecha:'2026-11-14 10:00:00',cajero:'Alberto',cliente:'Ana',mesa:'Mesa 01',metodo:'Yappy',total_centimos:900}],
 productos:[{id:1,nombre:'Café',categoria:'Bebidas',seccion:'Bebidas',precio_centimos:250,activo:1}],inventario:[{id:1,nombre:'Café',categoria:'Bebidas',cantidad:20}],
 hojas:[{turno_id:1,cajero:'Alberto',asignacion_fecha:'2026-11-14 10:00:00',estado:'activo'}],usuarios:[{nombre:'Alberto',usuario:'alberto',rol:'venta_libre'}]};
let forbidden=false;
const context={Node:Element,document:{getElementById:el,createElement:t=>new Element(t)},location:{hash:'#enlace-de-prueba',pathname:'/admin'},history:{replaceState(){}},sessionStorage:{getItem:k=>saved.get(k)||null,setItem:(k,v)=>saved.set(k,v),removeItem:k=>saved.delete(k)},setInterval(){},console,fetch:async(path,opts)=>{calls.push({path,opts});return {ok:!forbidden,status:forbidden?401:200,json:async()=>forbidden?{error:'Enlace retirado'}:path.endsWith('/login')?{token:'sesion-admin'}:path.includes('/hoja/')?{filas:[{producto:'Café',recibida:20,agregada:0,vendida:1,dinero_centimos:250,entregada:19,cajero:'Alberto'}],resumen:{importes:{Yappy:250},cocina_unidades:0,cocina_centimos:0,cocina:[],ambiguas:0}}:panel}}};
vm.createContext(context);vm.runInContext(source,context);const run=s=>vm.runInContext(s,context);
(async()=>{
 el('user').value='Admin';el('pass').value='Admin';await el('loginform').onsubmit({preventDefault(){}});
 assert.equal(el('app').hidden,false);assert.equal(el('login').hidden,true);assert.equal(el('pass').value,'');assert.equal(saved.get('admin-session'),'sesion-admin');
 for(const key of ['resumen','cobros','inventario','hojas','productos','usuarios']){run(`view='${key}';render()`);assert.ok(el('content').children.length>0,key)}
 await run('openSheet(1)');assert.equal(el('sheet').open,true);assert.match(el('sheettitle').textContent,/Alberto/);
 forbidden=true;await assert.rejects(run("api('panel')"));assert.equal(el('login').hidden,false);assert.equal(saved.has('admin-session'),false);
 assert.equal(calls[0].opts.headers.Authorization,'Bearer enlace-de-prueba');
 console.log('OK: login Admin, seis vistas, hoja detallada y revocación de sesión web');
})().catch(e=>{console.error(e);process.exitCode=1});
