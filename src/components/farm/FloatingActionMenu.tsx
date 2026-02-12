"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { 
  Menu, 
  X, 
  Layers,
  LayoutDashboard, 
  Database, 
  UserCog, 
  Brain, 
  Headset 
} from "lucide-react";

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

  if (!farmId || !plotId) return null;

  return (
    <div className="fixed bottom-24 left-6 z-50 flex flex-col items-start gap-4">
      
      {/* Menu Items Container */}
      <div 
        className={`
          flex flex-col-reverse gap-3 transition-all duration-300 ease-in-out origin-bottom-left
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
                group flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg border transition-all hover:scale-105 active:scale-95
                ${isActive 
                  ? "bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-400" 
                  : "bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700"
                }
              `}
            >
              <span className={`transition-transform group-hover:scale-110 ${isActive ? "text-emerald-600 dark:text-emerald-400" : "text-blue-600 dark:text-blue-400"}`}>
                {item.icon}
              </span>
              <span className="font-semibold text-sm whitespace-nowrap">
                {item.label}
              </span>
            </Link>
          );
        })}
      </div>

      {/* Main Toggle Button (FAB) */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`
          flex items-center justify-center w-20 h-20 rounded-full shadow-2xl transition-all duration-300 transform hover:scale-110 active:scale-95 z-50
          ${isOpen 
            ? "bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 rotate-90" 
            : "bg-emerald-600 hover:bg-emerald-700 text-white rotate-0 ring-4 ring-emerald-600/30"
          }
        `}
        aria-label="Toggle Menu"
      >
        {isOpen ? <X size={32} /> : <Layers size={32} />}
      </button>

    </div>
  );
}
