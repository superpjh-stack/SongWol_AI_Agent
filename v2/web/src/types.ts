export type Evidence = {title:string;kind:string;result?:unknown;source?:string;retrieved_at?:string;error?:string};
export type Message = {role:'user'|'assistant';text:string;mode?:string;evidence?:Evidence[];retrieved_at?:string};
export type Document = {id:string;title:string;revision:string;approval:string;body:string};
export type Row = Record<string, string | number | null>;
export type Lot = Row & {print_lot:string;order_no:string;status:string;fabric_lot:string;planned_qty:number;good_qty:number;defect_qty:number;process:string};
export type LotTrace = Record<'work_order'|'order'|'quality'|'conditions'|'inventory'|'shipment'|'claims',Row[]>;
export type Workspace = {summary:Record<string,number>;lots:Lot[];tables:Record<string,string>;questions:Record<string,string[]>;meta:{demo_data:boolean;source:string;approval?:string;daily_start?:string;daily_end?:string;daily_anchor?:string;today?:string;access_required?:boolean;realtime_model?:string;realtime_voice?:string;ai_configured:boolean;as_of:string;retrieved_at:string}};
export type HistoryEntry = {text:string;lot:string};
export type View = 'assistant'|'home'|'lots'|'library';
export function stored<T>(key:string,fallback:T):T {try{return JSON.parse(sessionStorage.getItem(key)||'null')??fallback}catch{return fallback}}
export function save(key:string,value:unknown){try{sessionStorage.setItem(key,JSON.stringify(value))}catch{/* Session storage can be disabled. */}}
export class ApiError extends Error {
 constructor(message:string,public status:number){super(message);this.name='ApiError'}
}
export async function request<T>(token:string,path:string,options:RequestInit={}):Promise<T>{
 const response=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json',Authorization:'Bearer '+token,...options.headers}});
 const data=await response.json();
 if(!response.ok)throw new ApiError(data.detail||'요청을 처리하지 못했습니다.',response.status);
 return data as T;
}
export const summaryLabels:Record<string,string>={open_orders:'진행 주문',quality_holds:'품질 보류',stock_issues:'재고 주의',shipment_pending:'승인 대기'};

export type DailyData={requested_start:string;requested_end:string;sample_as_of:string;inventory:Row[];plans:Row[];actuals:Row[];daily_totals:Row[];notes:string[]};
