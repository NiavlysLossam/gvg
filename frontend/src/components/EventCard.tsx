import React from 'react';
import { Calendar, Clock, MapPin, Map, ChevronRight, Layers } from 'lucide-react';
import { EventModel } from '../types/event';

interface EventCardProps {
  event: EventModel;
}

export const EventCard: React.FC<EventCardProps> = ({ event }) => {
  const startDate = new Date(event.start_date);
  const formattedDate = startDate.toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 hover:border-gray-300 transition flex flex-col justify-between">
      <div className="space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mr-1.5 animate-pulse" />
              Brouillon / Configuration du plan
            </span>
            <h3 className="text-lg font-bold text-gray-900 mt-2">{event.title}</h3>
          </div>
          <div className="text-right">
            <div className="text-lg font-extrabold text-emerald-700">
              {(event.price_per_meter ?? (event.price_per_meter_cents ? event.price_per_meter_cents / 100 : 0)).toFixed(2)} €
            </div>
            <div className="text-xs text-gray-500 font-medium">par mètre linéaire</div>
          </div>
        </div>

        {event.description && (
          <p className="text-sm text-gray-600 line-clamp-2">{event.description}</p>
        )}

        <div className="space-y-2 text-sm text-gray-600 pt-2 border-t border-gray-100">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-gray-400" />
            <span className="capitalize">{formattedDate}</span>
          </div>

          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-gray-400" />
            <span>
              Public : {event.public_start_time || '08:00'} - {event.public_end_time || '18:00'} | Installation : {event.setup_start_time || '06:00'} - {event.setup_end_time || '08:00'}
            </span>
          </div>

          {event.location_address && (
            <div className="flex items-center gap-2">
              <MapPin className="w-4 h-4 text-gray-400" />
              <span>{event.location_address}</span>
            </div>
          )}

          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-gray-400" />
            <span>
              Mode : {event.map_type === 'geographic' ? 'Extérieur (GPS / Satellite)' : 'Intérieur (Salle / Planaire)'}
            </span>
          </div>
        </div>
      </div>

      <div className="pt-6 mt-4 border-t border-gray-100 flex items-center justify-between">
        <div className="text-xs text-gray-400">
          Slug : <code className="bg-gray-100 px-1.5 py-0.5 rounded text-gray-600">{event.slug}</code>
        </div>

        <button
          type="button"
          onClick={() => alert(`Prêt pour le calibrage du fond de plan (Story 1.2) sur l'événement : ${event.title}`)}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 text-sm font-semibold rounded-lg transition"
        >
          <Map className="w-4 h-4 text-emerald-600" />
          <span>Configurer le plan (Story 1.2)</span>
          <ChevronRight className="w-4 h-4 ml-0.5" />
        </button>
      </div>
    </div>
  );
};
