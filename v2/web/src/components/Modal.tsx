import {useEffect,useRef,type ReactNode} from 'react';
import {X} from 'lucide-react';

export default function Modal({title,closeLabel='닫기',onClose,children}:{title:string;closeLabel?:string;onClose:()=>void;children:ReactNode}){
 const ref=useRef<HTMLDialogElement>(null);
 useEffect(()=>{const previous=document.activeElement as HTMLElement|null;const dialog=ref.current;dialog?.showModal();return()=>{dialog?.close();previous?.focus()}},[]);
 return <dialog ref={ref} aria-label={title} onCancel={onClose} onClick={e=>{if(e.target===e.currentTarget)onClose()}}><div className="dialog-heading"><h2>{title}</h2><button className="icon-button" aria-label={closeLabel} onClick={onClose}><X size={20}/></button></div>{children}</dialog>;
}
