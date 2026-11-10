// Keep the explicit address grammar in sync with v2/wake.py.
export function callsSongwol(text:string):boolean {
 return /^[\s"'“‘]*송월아(?=$|[\s,，.!?。！？:：~～])/u.test(text.trim());
}
