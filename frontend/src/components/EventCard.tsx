import React from 'react';
import { Calendar, Clock, MapPin, Map, ChevronRight, Layers, PenTool } from 'lucide-react';
import { EventModel } from '../types/event';

interface EventCardProps {
  event: EventModel;
  onConfigurePlan?: (event: EventModel) => void;
  onOpenEditor?: (event: EventModel) => void;
  onViewPublic?: (slug: string) => void;
}

export const EventCard: React.FC<EventCardProps> = ({
  event,
  onConfigurePlan,
  onOpenEditor,
  onViewPublic,
}) => {
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
            {event.map_type === 'geographic' && event.center_latitude != null && event.center_longitude != null ? (
              <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5" />
                Plan calibré (GPS)
              </span>
            ) : event.map_type === 'planar' && event.background_image_url ? (
              <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-800 border border-indigo-200">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 mr-1.5" />
                Plan calibré (Image)
              </span>
            ) : (
              <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mr-1.5 animate-pulse" />
                Brouillon / Configuration du plan
              </span>
            )}
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

      <div className="pt-5 mt-4 border-t border-gray-100 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => onConfigurePlan?.(event)}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-gray-50 hover:bg-gray-100 text-gray-700 text-xs font-semibold rounded-lg border border-gray-200 transition"
            title="Calibrer le fond de plan"
          >
            <Map className="w-3.5 h-3.5 text-gray-500" />
            <span>Fond de plan</span>
          </button>

          {onViewPublic && (
            <button
              type="button"
              onClick={() => onViewPublic(event.slug)}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 text-xs font-semibold rounded-lg border border-emerald-200 transition"
              title="Voir la vue publique du plan"
            >
              <span>Vue publique</span>
            </button>
          )}
        </div>

        <button
          type="button"
          onClick={() => onOpenEditor?.(event)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg shadow-xs transition"
          title="Ouvrir l'éditeur de tracé vectoriel des stands"
        >
          <PenTool className="w-3.5 h-3.5" />
          <span>Éditeur de stands</span>
          <ChevronRight className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
};
