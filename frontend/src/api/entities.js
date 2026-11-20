import {api} from './client.js';
export const datasets={list:()=>api('/datasets'),get:id=>api('/datasets/'+id),create:data=>api('/datasets',{method:'POST',body:JSON.stringify(data)})};
export const jobs={list:()=>api('/jobs'),get:id=>api('/jobs/'+id),create:data=>api('/jobs',{method:'POST',body:JSON.stringify(data)}),approve:id=>api('/jobs/'+id+'/approve',{method:'POST'})};
export const reports={list:()=>api('/reports'),create:data=>api('/reports',{method:'POST',body:JSON.stringify(data)}),toggle:id=>api('/reports/'+id+'/toggle',{method:'POST'}),deliveries:()=>api('/deliveries')};
export const holdouts={
 list:()=>api('/holdouts'),
 get:id=>api('/holdouts/'+id),
 seal:data=>api('/holdouts',{method:'POST',body:JSON.stringify(data)}),
 register:(id,data)=>api('/holdouts/'+id+'/register',{method:'POST',body:JSON.stringify(data)}),
 unseal:(id)=>api('/holdouts/'+id+'/unseal',{method:'POST'}),
 retry:id=>api('/holdouts/'+id+'/retry',{method:'POST'}),
 task:id=>api('/holdouts/'+id+'/task'),
 reviews:()=>api('/holdouts/reviews/completed')
};
