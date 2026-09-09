const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ctx = vm.createContext({});
vm.runInContext(fs.readFileSync('RecoveryModel.js','utf8'), ctx);
const recipe = {identity:'app:one',label:'One',detail:'Native restore'};
const saved = {id:'s1',key:'k1',recipe,placement:{workspace:'10'},title:'Old'};
const window = {key:'k1',address:'0x1',recipe,placement:{workspace:'2'},title:'One',status:'saved'};
let model=ctx.build({saved:[saved],windows:[window]});
assert.equal(model.count,1); assert.equal(model.dirty,false); assert.equal(model.groups[0].workspace,'2');
assert.equal(model.groups[0].rows[0].id,'s1');
model=ctx.build({saved:[saved],windows:[]});
assert.equal(model.groups[0].rows[0].status,'Closed · saved');
model=ctx.build({saved:[saved],windows:[{...window,status:'changed'}]});
assert.equal(model.dirty,false); assert.equal(model.error,true); assert.equal(model.groups[0].rows[0].saved,true);
model=ctx.build({saved:[],windows:[{...window,recipe:null,status:'unsupported'}]});
assert.equal(model.dirty,true); assert.equal(model.groups[0].rows[0].eligible,false);
assert.equal(model.rows[0].needsAdapter,true);
assert.deepEqual(Array.from(ctx.primaryAction(model.rows[0])), ['create-adapter','--address','0x1','--key','k1']);
model=ctx.build({saved:[],windows:[window]}); assert.equal(model.dirty,true);
model=ctx.build({saved:[saved],windows:[],last_restore:[{id:'s1',error:'Failed'}]}); assert.equal(model.error,true);
model=ctx.build({saved:[saved],windows:[window],last_restore:[{id:'s1',error:'Failed'}]}); assert.equal(model.error,false);
model=ctx.build({saved:[saved],windows:[{...window,key:'k2',recipe:{...recipe,identity:'other'}}]});
assert.equal(model.count,2); assert.equal(model.groups[0].workspace,'2');assert.equal(model.groups[1].workspace,'10');
console.log('PASS: grouping, deduplication, closed records, dirty/error status and toggle state');

model=ctx.build({saved:[],windows:[window],skipped:{k1:true}});
assert.equal(model.dirty,false);assert.equal(model.groups[0].rows[0].undecided,false);
model=ctx.build({saved:[],windows:[{...window,key:'new-window'}],skipped:{k1:true}});
assert.equal(model.dirty,true);assert.equal(model.groups[0].rows[0].undecided,true);

model=ctx.build({saved:[saved],windows:[{...window,recipe:{...recipe,needs_adapter:true}}]});
assert.equal(model.rows[0].needsAdapter,true);
assert.equal(model.rows[0].saved,false);
assert.equal(model.rows[0].eligible,false);
assert.equal(model.rows[0].undecided,true);
model=ctx.build({saved:[],windows:[{...window,recipe:{...recipe,needs_adapter:true}}],skipped:{k1:true}});
assert.equal(model.dirty,false);
assert.equal(model.rows[0].needsAdapter,true);

model=ctx.build({windows:[
 {...window,key:'second',placement:{workspace:'1',group:{id:'a',index:1}}},
 {...window,key:'alone',placement:{workspace:'1'}},
 {...window,key:'first',placement:{workspace:'1',group:{id:'a',index:0}}}
]});
assert.equal(model.rows[0].key,'first');
assert.equal(model.rows[1].key,'second');
assert.equal(model.rows[0].groupLabel,'1:1');
assert.equal(model.rows[1].groupLabel,'1:2');
assert.equal(model.rows[2].groupLabel,'–');

model=ctx.build({saved:[saved],windows:[]});
assert.equal(model.rows[0].closed,true);
assert.deepEqual(Array.from(ctx.primaryAction(model.rows[0])), ['restore','--id','s1']);
model=ctx.build({saved:[saved],windows:[window]});
assert.equal(!!model.rows[0].closed,false);
assert.deepEqual(Array.from(ctx.primaryAction(model.rows[0])), ['forget','--id','s1']);
model=ctx.build({saved:[saved],windows:[],last_restore:[{id:'s1',error:'Launch failed'}]});
assert.equal(model.rows[0].closed,true);
assert.equal(model.rows[0].detail,'Launch failed');

const placed = (key,x,y,group) => ({...window,key,placement:{workspace:'1',at:[x,y],group}});
model=ctx.build({windows:[
 placed('bottom-left',0,500), placed('top-right',800,0),
 placed('tab2',0,0,{id:'g',index:1}), placed('middle',400,250),
 placed('tab1',0,0,{id:'g',index:0})
]});
assert.deepEqual(Array.from(model.rows,r=>r.key), ['tab1','tab2','top-right','middle','bottom-left']);
model=ctx.build({windows:[placed('live',800,0)],saved:[{...saved,recipe:{...recipe,identity:'closed-app'},placement:{workspace:'1',at:[0,500]}}]});
assert.equal(model.rows[0].key,'live');
assert.equal(model.rows[1].closed,true);
