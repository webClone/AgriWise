"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import CropTimeline from "./CropTimeline";

interface Task {
  id: string;
  title: string;
  titleAr?: string;
  description?: string;
  completed: boolean;
  dueDate: string;
}

interface CropCycle {
  id: string;
  cropNameAr: string;
  cropCode: string;
  variety?: string;
  startDate: string;
  status: string;
  stage: string;
}

interface CycleDashboardProps {
  cycle: CropCycle;
  tasks: Task[];
}

export default function CycleDashboard({ cycle, tasks }: CycleDashboardProps) {
  const router = useRouter();
  const [activeTasks, setActiveTasks] = useState(tasks);

  // Derive stages from tasks for the timeline? 
  // In a real app we'd have explicit stages in DB, but for now we can infer or simpler just use generic
  // Actually, we can just hardcode generic stages for visualization since the dynamic tasks are what matters
  const genericStages = [
    { stage: "PLANTING", nameAr: "الزراعة" },
    { stage: "VEGETATIVE", nameAr: "النمو" },
    { stage: "FLOWERING", nameAr: "الإزهار" },
    { stage: "MATURITY", nameAr: "النضج" },
    { stage: "HARVEST", nameAr: "الحصاد" },
  ];

  const toggleTask = async (taskId: string, currentStatus: boolean) => {
    // Optimistic update
    setActiveTasks(prev => prev.map(t => t.id === taskId ? { ...t, completed: !currentStatus } : t));

    try {
      await fetch(`/api/cycles/${cycle.id}/tasks`, { // Note: using PUT /api/cycles/ID/tasks is slightly wrong path in my plan, I implemented /api/cycles/[id]/tasks but routed it as /api/cycles/[id]/tasks in code?
        // Actually I created `src/app/api/cycles/[id]/tasks/route.ts` which expects `params.id` to be task ID?
        // Wait, my file path was `src/app/api/cycles/[id]/tasks/route.ts` but the code inside expected `id` to be `taskId`.
        // This means the URL should be `/api/cycles/ANYTHING/tasks`, but params would capture the `id`. 
        // THIS IS CONFUSING. I should have made `src/app/api/tasks/[id]/route.ts`.
        // Let's check the file I created.
      });
    } catch (err) {
      console.error(err);
      router.refresh(); // Revert on error
    }
  };
  
  // Correction: I need to check the API route I created.
  // I created `src/app/api/cycles/[id]/tasks/route.ts`
  // The route.ts has `export async function PUT(req, { params })`. `params.id` matches the folder `[id]`.
  // So the URL is `/api/cycles/<TASK_ID>/tasks`. This is weird naming. 
  // I will fix the frontend to use this weird URL for now or should I fix the backend?
  // Frontend: `/api/cycles/${taskId}/tasks` works if the folder is named `[id]` and it's inside `cycles`.
  
  // BETTER FIX: The folder structure `src/app/api/cycles/[id]/tasks/route.ts` implies `id` is the cycle ID.
  // BUT valid Next.js dynamic route `[id]` captures the segment.
  // So query to `/api/cycles/123/tasks` -> params.id = "123".
  // If "123" is intended to be the CycleID, then I can't update a specific task unless I pass TaskID in body or have another segment.
  // My backend code READS `const { id: taskId } = await params;`.
  // So it treats the segment `[id]` as the Task ID.
  // So the URL structure is effectively `/api/cycles/<TASK_ID>/tasks`.
  // It's semantically weird but functional. I will use it.

  const handleTaskToggle = async (task: Task) => {
     setActiveTasks(prev => prev.map(t => t.id === task.id ? { ...t, completed: !t.completed } : t));
     
     try {
         await fetch(`/api/cycles/${task.id}/tasks`, {
             method: 'PUT',
             headers: { 'Content-Type': 'application/json' },
             body: JSON.stringify({ completed: !task.completed })
         });
         router.refresh();
     } catch(e) {
         console.error(e);
     }
  };

  const pendingTasks = activeTasks.filter(t => !t.completed);
  const completedTasks = activeTasks.filter(t => t.completed);

  return (
    <div className="flex flex-col gap-6">
        {/* Header Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="card p-4">
                <div className="text-sm text-gray-500">تاريخ الزراعة</div>
                <div className="font-semibold">{new Date(cycle.startDate).toLocaleDateString('ar-DZ')}</div>
            </div>
            <div className="card p-4">
                <div className="text-sm text-gray-500">الحالة</div>
                <div className="font-semibold text-green-600">
                    {cycle.status === 'PLANTED' ? '🌱 جاري النمو' : cycle.status}
                </div>
            </div>
            <div className="card p-4">
                <div className="text-sm text-gray-500">المهام المتبقية</div>
                <div className="font-semibold text-orange-600">{pendingTasks.length}</div>
            </div>
            <div className="card p-4">
                <div className="text-sm text-gray-500">الإنجاز</div>
                <div className="font-semibold">{Math.round((completedTasks.length / activeTasks.length) * 100) || 0}%</div>
            </div>
        </div>

        {/* Timeline */}
        <div className="card p-6 overflow-hidden">
            <h3 className="font-bold mb-4">الجدول الزمني</h3>
            <CropTimeline stages={genericStages} currentStage="VEGETATIVE" />
        </div>

        {/* Tasks List */}
        <div className="card p-6">
            <div className="flex justify-between items-center mb-4">
                <h3 className="font-bold">📋 المهام الحالية</h3>
                <span className="text-xs text-gray-400">تم إنشاؤها بواسطة AgriBrain AI</span>
            </div>

            <div className="space-y-6 max-h-[500px] overflow-y-auto pl-2 custom-scrollbar p-2">
                {activeTasks.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-slate-400 bg-slate-800/50 rounded-xl border border-dashed border-slate-700 animate-fade-in">
                        <span className="text-4xl mb-2 grayscale opacity-50">🌱</span>
                        <p>لا توجد مهام مسجلة لهذا المحصول.</p>
                    </div>
                ) : (
                    activeTasks
                        .sort((a,b) => new Date(a.dueDate).getTime() - new Date(b.dueDate).getTime())
                        .map((task, index) => {
                            // Helper for dynamic icons
                            const getTaskIcon = (txt: string) => {
                                if (txt.includes('ري') || txt.includes('سقي') || txt.includes('مياه')) return '💧';
                                if (txt.includes('سماد') || txt.includes('تسميد') || txt.includes('يوريا')) return '🧪';
                                if (txt.includes('حشر') || txt.includes('مبيد') || txt.includes('علاج')) return '🛡️';
                                if (txt.includes('حصاد') || txt.includes('جني')) return '🌾';
                                return '📋';
                            };
                            const icon = getTaskIcon((task.titleAr || task.title).toLowerCase());

                            return (
                                <div 
                                    key={task.id}
                                    style={{ animationDelay: `${index * 0.05}s`, animationFillMode: 'both' }} 
                                    className={`slide-up group flex items-start gap-4 p-5 rounded-2xl border transition-all duration-300 relative overflow-hidden ${
                                        task.completed 
                                            ? 'bg-slate-900/40 border-slate-800/50 opacity-60' 
                                            : 'bg-slate-800/80 border-slate-700 shadow-sm hover:border-green-500/40 hover:bg-slate-800 hover:shadow-lg hover:shadow-green-900/10 backdrop-blur-sm'
                                    }`}
                                >
                                    {/* Task Icon/Type */}
                                    <div className={`
                                        flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center text-xl shadow-inner
                                        ${task.completed ? 'bg-slate-800 text-slate-600 grayscale' : 'bg-slate-700/50 text-white'}
                                    `}>
                                        {icon}
                                    </div>

                                    <div className="flex-1 min-w-0 pt-0.5">
                                        <div className="flex justify-between items-start gap-3">
                                            <div>
                                                <h4 className={`font-bold text-lg mb-1 transition-colors ${
                                                    task.completed ? 'text-slate-500 line-through decoration-slate-600' : 'text-slate-100 group-hover:text-green-400'
                                                }`}>
                                                    {task.titleAr || task.title}
                                                </h4>
                                                {task.description && (
                                                    <p className={`text-sm leading-relaxed ${task.completed ? 'text-slate-600' : 'text-slate-400'}`}>
                                                        {task.description}
                                                    </p>
                                                )}
                                            </div>
                                            
                                            {/* Custom Animated Checkbox */}
                                            <button
                                                onClick={() => handleTaskToggle(task)}
                                                className={`
                                                    relative flex-shrink-0 w-8 h-8 rounded-full border-2 transition-all duration-300 flex items-center justify-center
                                                    ${task.completed 
                                                        ? 'bg-green-500 border-green-500 scale-95' 
                                                        : 'border-slate-500 hover:border-green-400 hover:bg-green-400/10'}
                                                `}
                                            >
                                                <svg 
                                                    className={`w-4 h-4 text-white transition-opacity duration-200 ${task.completed ? 'opacity-100' : 'opacity-0'}`} 
                                                    fill="none" 
                                                    viewBox="0 0 24 24" 
                                                    stroke="currentColor" 
                                                    strokeWidth="3"
                                                >
                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                                                </svg>
                                            </button>
                                        </div>

                                        <div className="flex items-center gap-3 mt-4">
                                            <div className={`text-xs px-3 py-1.5 rounded-lg font-medium flex items-center gap-2 transition-colors ${
                                                task.completed 
                                                    ? 'bg-slate-800 text-slate-500' 
                                                    : 'bg-green-500/10 text-green-400 border border-green-500/20'
                                            }`}>
                                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                                </svg>
                                                {new Date(task.dueDate).toLocaleDateString('ar-DZ', { day: 'numeric', month: 'long', year: 'numeric' })}
                                            </div>
                                            
                                            {!task.completed && (
                                                 <span className="text-xs text-slate-500 flex items-center gap-1">
                                                    <span className="w-1.5 h-1.5 rounded-full bg-slate-500"></span>
                                                    مجدولة
                                                 </span>
                                            )}
                                        </div>
                                    </div>
                                    
                                    {/* Active State Glow Line (Left side for RTL) */}
                                    {!task.completed && (
                                        <div className="absolute right-0 top-0 bottom-0 w-1 bg-green-500 opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-r-full" />
                                    )}
                                </div>
                            );
                        })
                )}
            </div>
        </div>
    </div>
  );
}
