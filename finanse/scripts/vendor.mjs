import {mkdir, copyFile, readFile, writeFile} from 'node:fs/promises';
const base = new URL('../', import.meta.url);
await mkdir(new URL('vendor/', base), {recursive:true});
for (const name of ['three.module.js','three.core.js']) await copyFile(new URL(`node_modules/three/build/${name}`, base),new URL(`vendor/${name}`,base));
const controls = await readFile(new URL('node_modules/three/examples/jsm/controls/OrbitControls.js',base),'utf8');
await writeFile(new URL('vendor/OrbitControls.js',base),controls.replace("from 'three'", "from './three.module.js'"));
await copyFile(new URL('node_modules/three/LICENSE',base),new URL('vendor/THREE-LICENSE.txt',base));
