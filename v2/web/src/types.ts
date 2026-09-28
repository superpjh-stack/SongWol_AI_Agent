export type Evidence = {title:string;kind:string;result?:unknown;source?:string;retrieved_at?:string;error?:string};
export type Message = {role:'user'|'assistant';text:string;mode?:string;evidence?:Evidence[];retrieved_at?:string};
export type Document = {id:string;title:string;revision:string;approval:string;body:string};
export type Workspace = {summary:Record<string,number>;lots:{print_lot:string;order_no:string;status:string}[];tables:Record<string,string>;questions:Record<string,string[]>;meta:{ai_configured:boolean;as_of:string}};
