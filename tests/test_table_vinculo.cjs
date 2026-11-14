const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('pedidos_table.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
function setup(protocol='http:',hash=''){
 const elements=new Map(), saved=new Map();const calls=[];
 function el(id){if(!elements.has(id))elements.set(id,{hidden:false,value:'',textContent:'',disabled:false,classList:{toggle(){}},focus(){},replaceChildren(){},querySelector(){return null}});return elements.get(id)}
 const location={protocol,pathname:protocol==='file:'?'/pedidos_table.html':'/',origin:'http://192.168.1.2:8765',hash,href:'http://192.168.1.2:8765/'+hash,replace(url){this.redirect=url}};
 const storage={getItem:k=>saved.get(k)||null,setItem:(k,v)=>saved.set(k,v),removeItem:k=>saved.delete(k)};
 const context={document:{getElementById:el},location,localStorage:storage,sessionStorage:storage,navigator:{userAgent:''},history:{replaceState(){}},setInterval(){},setTimeout,clearTimeout,AbortController,URL,console,fetch:async(path,opts)=>{calls.push({path,opts});return {ok:true,status:200,json:async()=>({vinculado:true})}}};context.window=context;
 vm.createContext(context);vm.runInContext(source,context);return {context,el,calls,saved,location,run:s=>vm.runInContext(s,context)};
}
(async()=>{
 const a=setup();assert.equal(a.el('login').hidden,true);assert.equal(a.el('link').hidden,false);
 a.el('key').value='A'.repeat(43);await a.el('link').onsubmit({preventDefault(){}});
 assert.equal(a.calls[0].path,'/api/vinculo');assert.equal(a.el('login').hidden,false);assert.equal(a.saved.get('table-vinculo'),'A'.repeat(43));
 a.run("refresh=async()=>{modo('app')}");
 a.el('user').value='ana';a.el('pass').value='prueba';
 a.context.fetch=async(path,opts)=>{assert.equal(path,'/api/login');assert.equal(JSON.parse(opts.body).usuario,'ana');return {ok:true,status:200,json:async()=>({token:'sesion-prueba',usuario:'ana'})}};
 await a.el('login').onsubmit({preventDefault(){}});assert.equal(a.el('app').hidden,false);assert.equal(a.el('pass').value,'');assert.equal(a.run('token'),'sesion-prueba');
 a.context.fetch=async()=>({ok:false,status:401,json:async()=>({error:'Credenciales incorrectas'})});
 await assert.rejects(a.run("api('/api/login', {usuario:'ana',password:'mal'})"));assert.equal(a.el('login').hidden,false);assert.equal(a.el('link').hidden,true);
 a.context.fetch=async()=>({ok:false,status:401,json:async()=>({error:'Vínculo retirado',vinculo_invalido:true})});
 await assert.rejects(a.run("api('/api/vinculo')"));assert.equal(a.el('link').hidden,false);assert.equal(a.saved.has('table-vinculo'),false);
 a.context.fetch=async()=>{throw new TypeError('Failed to fetch')};await assert.rejects(a.run("api('/api/vinculo')"),/misma red/);
 const b=setup('file:');b.el('key').value='A'.repeat(43);await b.el('link').onsubmit({preventDefault(){}});assert.match(b.el('message').textContent,/enlace completo/);assert.equal(b.calls.length,0);
 b.el('key').value='http://192.168.1.2:8765/#'+'A'.repeat(43);await b.el('link').onsubmit({preventDefault(){}});assert.equal(b.location.redirect,b.el('key').value);assert.equal(b.calls.length,0);
 b.el('key').value='javascript:alert(1)';await b.el('link').onsubmit({preventDefault(){}});assert.match(b.el('message').textContent,/enlace completo/);
 const c=setup('http:','#'+'B'.repeat(43));await new Promise(r=>setTimeout(r,0));assert.equal(c.el('login').hidden,false);assert.equal(c.calls[0].path,'/api/vinculo');
 c.el('change').onclick();assert.equal(c.el('link').hidden,false);assert.equal(c.el('login').hidden,true);
 const d=setup();d.run("renderCart=()=>{};renderWizard=()=>{};mesa='Mesa 01';data={mesas:[{nombre:'Mesa 01',clientes:[],cuenta:[]}],productos:[{id:3,nombre:'Hamburguesa',seccion:'Cocina',precio_centimos:650,preparaciones:['Completa','Sin vegetales']}],recargos:{Yuca:125},acompanamientos:['Yuca']}");
 d.el('client').value='';d.run("agregarProducto(data.productos[0],{preparacion:'Completa',acompanamiento:'Yuca',extra:''});agregarProducto(data.productos[0],{preparacion:'Sin vegetales',acompanamiento:'Yuca',extra:'Yuca'});agregarProducto(data.productos[0],{preparacion:'Completa',acompanamiento:'Yuca',extra:''})");
 assert.equal(d.run('Object.keys(draft()).length'),2);assert.equal(d.run('Object.values(draft())[0].cantidad'),2);assert.equal(d.run('precioLinea(Object.values(draft())[1])'),775);
 d.run('abrirPlato(data.productos[0])');assert.equal(d.el('wizard').hidden,false);assert.equal(d.el('app').inert,true);assert.equal(d.run('personalizacion.paso'),0);
 d.run("personalizacion.preparacion='Sin vegetales'");d.el('wizardnext').onclick();assert.equal(d.run('personalizacion.paso'),1);
 d.run("personalizacion.acompanamiento='Yuca'");d.el('wizardextra').onclick();assert.equal(d.run('personalizacion.extra'),'Yuca');d.el('wizardback').onclick();assert.equal(d.run('personalizacion.preparacion'),'Sin vegetales');d.el('wizardnext').onclick();d.el('wizardnext').onclick();assert.equal(d.el('wizard').hidden,true);assert.equal(d.el('app').inert,false);assert.equal(d.run('Object.values(draft())[1].cantidad'),2);
 d.run('pending={id:"pendiente"};agregarProducto(data.productos[0],{})');assert.equal(d.run('Object.keys(draft()).length'),2);
 console.log('OK: vinculación previa, enlace local, credenciales inválidas, revocación, error de red y cambio de vínculo');
})().catch(e=>{console.error(e);process.exitCode=1});
