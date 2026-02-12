"use client";

import Link from "next/link";
import { useState } from "react";

// Icons
const HomeIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
  </svg>
);

const FarmIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
  </svg>
);

const CalendarIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
  </svg>
);

const WeatherIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z" />
  </svg>
);

const UserIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
  </svg>
);

const ChevronLeft = () => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" style={{ width: "20px", height: "20px" }}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
  </svg>
);

const ChevronRight = () => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" style={{ width: "20px", height: "20px" }}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
  </svg>
);

interface Task {
  id: string;
  title: string;
  type: string;
  icon: string;
  date: Date;
  completed: boolean;
}

const ARABIC_MONTHS = [
  "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
  "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
];

const ARABIC_DAYS = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"];
const ARABIC_DAYS_SHORT = ["أحد", "اثن", "ثلا", "أرب", "خمي", "جمع", "سبت"];

export default function CalendarPage() {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  
  // Demo tasks
  const [tasks] = useState<Task[]>([
    { id: "1", title: "سقي القمح", type: "irrigation", icon: "💧", date: new Date(2026, 0, 22), completed: false },
    { id: "2", title: "تسميد البطاطا", type: "fertilizing", icon: "🌱", date: new Date(2026, 0, 24), completed: false },
    { id: "3", title: "مكافحة الحشرات", type: "pest_control", icon: "🐛", date: new Date(2026, 0, 25), completed: false },
    { id: "4", title: "تقليم الزيتون", type: "pruning", icon: "✂️", date: new Date(2026, 0, 28), completed: false },
    { id: "5", title: "حصاد الخضروات", type: "harvest", icon: "🥬", date: new Date(2026, 1, 2), completed: false },
  ]);

  const today = new Date();
  
  const getDaysInMonth = (date: Date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDay = firstDay.getDay();
    
    return { daysInMonth, startingDay };
  };

  const { daysInMonth, startingDay } = getDaysInMonth(currentDate);

  const prevMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1));
  };

  const nextMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1));
  };

  const isToday = (day: number) => {
    return (
      day === today.getDate() &&
      currentDate.getMonth() === today.getMonth() &&
      currentDate.getFullYear() === today.getFullYear()
    );
  };

  const isSelected = (day: number) => {
    if (!selectedDate) return false;
    return (
      day === selectedDate.getDate() &&
      currentDate.getMonth() === selectedDate.getMonth() &&
      currentDate.getFullYear() === selectedDate.getFullYear()
    );
  };

  const hasTask = (day: number) => {
    return tasks.some(task => {
      const taskDate = new Date(task.date);
      return (
        taskDate.getDate() === day &&
        taskDate.getMonth() === currentDate.getMonth() &&
        taskDate.getFullYear() === currentDate.getFullYear()
      );
    });
  };

  const getTasksForDate = (date: Date | null) => {
    if (!date) return [];
    return tasks.filter(task => {
      const taskDate = new Date(task.date);
      return (
        taskDate.getDate() === date.getDate() &&
        taskDate.getMonth() === date.getMonth() &&
        taskDate.getFullYear() === date.getFullYear()
      );
    });
  };

  const getUpcomingTasks = () => {
    const now = new Date();
    return tasks
      .filter(task => new Date(task.date) >= now)
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .slice(0, 5);
  };

  const formatDate = (date: Date) => {
    return `${ARABIC_DAYS[date.getDay()]}، ${date.getDate()} ${ARABIC_MONTHS[date.getMonth()]}`;
  };

  const selectedDateTasks = getTasksForDate(selectedDate);
  const upcomingTasks = getUpcomingTasks();

  return (
    <main className="page">
      {/* Header */}
      <header className="page-header">
        <h1 className="page-title">التقويم الزراعي</h1>
        <p className="page-subtitle">تتبع مهامك ومواعيد محاصيلك</p>
      </header>

      {/* Calendar */}
      <div className="card fade-in" style={{ marginBottom: "1.5rem" }}>
        {/* Month Navigation */}
        <div className="calendar-header">
          <button className="btn btn-icon btn-secondary" onClick={nextMonth}>
            <ChevronRight />
          </button>
          <h3 style={{ margin: 0 }}>
            {ARABIC_MONTHS[currentDate.getMonth()]} {currentDate.getFullYear()}
          </h3>
          <button className="btn btn-icon btn-secondary" onClick={prevMonth}>
            <ChevronLeft />
          </button>
        </div>

        {/* Day Names */}
        <div className="calendar-grid" style={{ marginBottom: "0.5rem" }}>
          {ARABIC_DAYS_SHORT.map((day, index) => (
            <div key={index} style={{ textAlign: "center", fontSize: "0.75rem", color: "var(--foreground-muted)", padding: "0.5rem 0" }}>
              {day}
            </div>
          ))}
        </div>

        {/* Calendar Days */}
        <div className="calendar-grid">
          {/* Empty cells for days before the first day of month */}
          {Array.from({ length: startingDay }).map((_, index) => (
            <div key={`empty-${index}`} className="calendar-day" />
          ))}
          
          {/* Days of the month */}
          {Array.from({ length: daysInMonth }).map((_, index) => {
            const day = index + 1;
            return (
              <div
                key={day}
                className={`calendar-day ${isToday(day) ? "today" : ""} ${isSelected(day) ? "selected" : ""} ${hasTask(day) ? "has-task" : ""}`}
                onClick={() => setSelectedDate(new Date(currentDate.getFullYear(), currentDate.getMonth(), day))}
                style={{
                  cursor: "pointer",
                  background: isSelected(day) && !isToday(day) ? "var(--background-tertiary)" : undefined,
                  fontWeight: hasTask(day) ? 600 : undefined
                }}
              >
                {day}
              </div>
            );
          })}
        </div>
      </div>

      {/* Selected Date Tasks */}
      {selectedDate && (
        <div className="slide-up" style={{ marginBottom: "1.5rem" }}>
          <h2 style={{ fontSize: "1.1rem", marginBottom: "1rem" }}>
            📅 {formatDate(selectedDate)}
          </h2>
          {selectedDateTasks.length === 0 ? (
            <div className="card" style={{ textAlign: "center", padding: "1.5rem" }}>
              <p style={{ margin: 0, color: "var(--foreground-muted)" }}>لا توجد مهام في هذا اليوم</p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {selectedDateTasks.map(task => (
                <div key={task.id} className="card" style={{ padding: "1rem", display: "flex", alignItems: "center", gap: "1rem" }}>
                  <div style={{ 
                    width: "48px", 
                    height: "48px", 
                    background: "rgba(34, 197, 94, 0.1)", 
                    borderRadius: "12px", 
                    display: "flex", 
                    alignItems: "center", 
                    justifyContent: "center", 
                    fontSize: "1.5rem" 
                  }}>
                    {task.icon}
                  </div>
                  <div style={{ flex: 1 }}>
                    <h4 style={{ margin: 0, fontSize: "1rem" }}>{task.title}</h4>
                  </div>
                  <input 
                    type="checkbox" 
                    checked={task.completed}
                    readOnly
                    style={{ width: "24px", height: "24px", accentColor: "var(--color-primary-500)" }}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Upcoming Tasks */}
      <div className="fade-in">
        <h2 style={{ fontSize: "1.1rem", marginBottom: "1rem" }}>📋 المهام القادمة</h2>
        {upcomingTasks.length === 0 ? (
          <div className="empty-state">
            <div className="emoji">📅</div>
            <div className="title">لا توجد مهام قادمة</div>
            <div className="subtitle">أضف محاصيل لتظهر المهام تلقائياً</div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            {upcomingTasks.map(task => {
              const taskDate = new Date(task.date);
              const isTaskToday = taskDate.toDateString() === today.toDateString();
              const isTomorrow = taskDate.toDateString() === new Date(today.getTime() + 86400000).toDateString();
              
              let dateLabel = formatDate(taskDate);
              if (isTaskToday) dateLabel = "اليوم";
              if (isTomorrow) dateLabel = "غداً";
              
              return (
                <div key={task.id} className="card" style={{ padding: "1rem", display: "flex", alignItems: "center", gap: "1rem" }}>
                  <div style={{ 
                    width: "48px", 
                    height: "48px", 
                    background: isTaskToday ? "rgba(251, 191, 36, 0.1)" : "rgba(34, 197, 94, 0.1)", 
                    borderRadius: "12px", 
                    display: "flex", 
                    alignItems: "center", 
                    justifyContent: "center", 
                    fontSize: "1.5rem" 
                  }}>
                    {task.icon}
                  </div>
                  <div style={{ flex: 1 }}>
                    <h4 style={{ margin: 0, fontSize: "1rem" }}>{task.title}</h4>
                    <p style={{ margin: 0, fontSize: "0.85rem", color: isTaskToday ? "var(--color-warning-500)" : "var(--foreground-muted)" }}>
                      {dateLabel}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Bottom Navigation */}
      <nav className="nav-bottom">
        <Link href="/" className="nav-item">
          <HomeIcon />
          <span>الرئيسية</span>
        </Link>
        <Link href="/farm" className="nav-item">
          <FarmIcon />
          <span>المزارع</span>
        </Link>
        <Link href="/calendar" className="nav-item active">
          <CalendarIcon />
          <span>التقويم</span>
        </Link>
        <Link href="/weather" className="nav-item">
          <WeatherIcon />
          <span>الطقس</span>
        </Link>
        <Link href="/profile" className="nav-item">
          <UserIcon />
          <span>حسابي</span>
        </Link>
      </nav>
    </main>
  );
}
