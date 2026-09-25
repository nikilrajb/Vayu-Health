export type Session = {token:string;username:string;role:string};
export function session():Session|null {try{return JSON.parse(sessionStorage.getItem('vayu-session')||'null');}catch{return null;}}
export function authHeaders():Record<string,string> {const s=session();return s?{Authorization:`Bearer ${s.token}`}:{ };}
