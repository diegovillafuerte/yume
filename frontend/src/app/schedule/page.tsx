'use client';

import { useState } from 'react';
import { format, addDays, subDays, startOfDay } from 'date-fns';
import { es } from 'date-fns/locale';
import DashboardLayout from '@/components/layout/DashboardLayout';

type ViewMode = 'calendar' | 'list';

export default function SchedulePage() {
  const [selectedDate, setSelectedDate] = useState(startOfDay(new Date()));
  const [viewMode, setViewMode] = useState<ViewMode>('calendar');

  const goToPreviousDay = () => setSelectedDate(subDays(selectedDate, 1));
  const goToNextDay = () => setSelectedDate(addDays(selectedDate, 1));
  const goToToday = () => setSelectedDate(startOfDay(new Date()));

  return (
    <DashboardLayout>
      <div className="space-y-4">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Agenda</h1>
            <p className="text-gray-600">
              {format(selectedDate, "EEEE d 'de' MMMM", { locale: es })}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {/* View Toggle */}
            <div className="bg-gray-100 rounded-lg p-1 flex">
              <button
                onClick={() => setViewMode('calendar')}
                className={`px-3 py-1.5 text-sm font-medium rounded-md transition ${
                  viewMode === 'calendar'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Calendario
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`px-3 py-1.5 text-sm font-medium rounded-md transition ${
                  viewMode === 'list'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Lista
              </button>
            </div>
          </div>
        </div>

        {/* Date Navigation */}
        <div className="flex items-center justify-between bg-white rounded-lg p-4 shadow-sm">
          <button
            onClick={goToPreviousDay}
            className="p-2 hover:bg-gray-100 rounded-lg transition"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>

          <button
            onClick={goToToday}
            className="px-4 py-2 text-sm font-medium text-blue-600 hover:bg-blue-50 rounded-lg transition"
          >
            Hoy
          </button>

          <button
            onClick={goToNextDay}
            className="p-2 hover:bg-gray-100 rounded-lg transition"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>

        {/* Content */}
        {viewMode === 'calendar' ? (
          <CalendarView date={selectedDate} />
        ) : (
          <ListView date={selectedDate} />
        )}
      </div>
    </DashboardLayout>
  );
}

function CalendarView({ date }: { date: Date }) {
  // Generate time slots from 8 AM to 8 PM
  const timeSlots = Array.from({ length: 12 }, (_, i) => {
    const hour = 8 + i;
    return `${hour.toString().padStart(2, '0')}:00`;
  });

  return (
    <div className="bg-white rounded-lg shadow-sm overflow-hidden">
      <div className="divide-y divide-gray-100">
        {timeSlots.map((time) => (
          <div key={time} className="flex">
            <div className="w-16 py-4 px-3 text-sm text-gray-500 font-medium border-r border-gray-100">
              {time}
            </div>
            <div className="flex-1 py-4 px-4 min-h-[60px] hover:bg-gray-50 transition cursor-pointer">
              {/* Appointments would go here */}
            </div>
          </div>
        ))}
      </div>

      {/* Empty State */}
      <div className="p-8 text-center text-gray-500">
        <svg className="w-12 h-12 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        <p className="font-medium">No hay citas para este día</p>
        <p className="text-sm mt-1">Las citas aparecerán aquí cuando tus clientes las agenden.</p>
      </div>
    </div>
  );
}

function ListView({ date }: { date: Date }) {
  return (
    <div className="bg-white rounded-lg shadow-sm overflow-hidden">
      {/* Table Header */}
      <div className="hidden sm:grid grid-cols-6 gap-4 px-6 py-3 bg-gray-50 text-sm font-medium text-gray-600 border-b">
        <div>Hora</div>
        <div>Cliente</div>
        <div>Servicio</div>
        <div>Empleado</div>
        <div>Estación</div>
        <div>Estado</div>
      </div>

      {/* Empty State */}
      <div className="p-8 text-center text-gray-500">
        <svg className="w-12 h-12 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
        <p className="font-medium">No hay citas para mostrar</p>
        <p className="text-sm mt-1">Conecta tu WhatsApp para empezar a recibir citas.</p>
      </div>
    </div>
  );
}
