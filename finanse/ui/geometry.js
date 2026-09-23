export const radius=n=>3+Math.max(0,Math.min(1,n.priority_score))*5;
export const thickness=e=>.22+Math.min(.9,Math.log1p(Math.max(0,e.sum_kzt))/20);
// Opposite directed edges bend on opposite sides; self-transfers use a full loop.
export function edgePoints(e,positions){const a=positions[e.src],b=positions[e.dst],points=[];
 if(e.src===e.dst){for(let i=0;i<=20;i++){const t=i/20*Math.PI*2;points.push([a[0]+16*Math.sin(t),a[1]+16*(1-Math.cos(t)),a[2]]);}return points;}
 const dx=b[0]-a[0],dy=b[1]-a[1],dz=b[2]-a[2],len=Math.hypot(dx,dy,dz)||1,flat=Math.hypot(dx,dy);const offset=flat>.01?[-dy/flat,dx/flat,0]:[1,0,0];const bend=Math.min(24,len*.12);
 for(let i=0;i<=12;i++){const t=i/12,w=4*t*(1-t)*bend;points.push(a.map((v,j)=>v+(b[j]-v)*t+offset[j]*w));}return points;
}
