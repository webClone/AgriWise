"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { 
  X, 
  Layers,
  LayoutDashboard, 
  Database, 
  UserCog, 
  Brain, 
  Headset 
} from "lucide-react";
import { useLayer10 } from "@/hooks/useLayer10";

export default function FloatingActionMenu() {
  const [isOpen, setIsOpen] = useState(false);
  const params = useParams();
  const currentPath = usePathname();

  // Handle potential missing params if used outside context (fallback safe)
  const farmId = params?.id as string;
  const plotId = params?.plotId as string;
  
  const baseUrl = `/farm/${farmId}/plot/${plotId}`;

  const menuItems = [
    { label: "Overview", icon: <LayoutDashboard size={20} />, href: baseUrl },
    { label: "Raw Data", icon: <Database size={20} />, href: `${baseUrl}/raw-data` },
    { label: "User Inputs", icon: <UserCog size={20} />, href: `${baseUrl}/user-inputs` },
    { label: "AgriBrain Analysis", icon: <Brain size={20} />, href: `${baseUrl}/analysis` },
    { label: "Live Assistance", icon: <Headset size={20} />, href: `${baseUrl}/live-assistance` },
  ];

  const { isDecideMode } = useLayer10();

  if (!farmId || !plotId || isDecideMode) return null;

  return (
    <div className="fixed bottom-32 right-6 z-50 flex flex-col items-end gap-3 pointer-events-none">
      
      {/* Menu Items Container */}
      <div 
        className={`
          flex flex-col-reverse gap-2 transition-all duration-300 ease-in-out origin-bottom-right
          ${isOpen ? "opacity-100 scale-100 translate-y-0" : "opacity-0 scale-95 translate-y-4 pointer-events-none"}
        `}
      >
        {menuItems.map((item, index) => {
          const isActive = currentPath === item.href;
          return (
            <Link
              key={index}
              href={item.href}
              onClick={() => setIsOpen(false)}
              className={`
                pointer-events-auto group flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl shadow-lg border transition-all active:scale-95
                ${isActive 
                  ? "bg-white/10 border-white/15 text-white" 
                  : "bg-[#0B1015]/80 backdrop-blur-xl text-slate-300 border-white/8 hover:bg-white/10 hover:text-white"
                }
              `}
            >
              <span className={`transition-transform ${isActive ? "text-emerald-400" : "text-slate-400 group-hover:text-slate-200"}`}>
                {item.icon}
              </span>
              <span className="font-medium text-sm whitespace-nowrap">
                {item.label}
              </span>
            </Link>
          );
        })}
      </div>

      {/* Main Toggle — subdued glass pill */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`
          pointer-events-auto flex items-center justify-center w-11 h-11 rounded-xl shadow-lg transition-all duration-300 transform active:scale-95
          ${isOpen 
            ? "bg-white/15 backdrop-blur-xl text-white border border-white/15 rotate-90 opacity-100 scale-100" 
            : "bg-[#0B1015]/70 backdrop-blur-xl text-slate-400 hover:text-white border border-white/8 hover:bg-white/20 rotate-0 opacity-40 hover:opacity-100 scale-90 hover:scale-100"
          }
        `}
        aria-label="Toggle Menu"
      >
        {isOpen ? <X size={18} /> : <Layers size={18} />}
      </button>

    </div>
  );
}
