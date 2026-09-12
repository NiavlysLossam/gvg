import React from 'react';
import { Calendar, Clock, MapPin, Tag, RefreshCw } from 'lucide-react';
import { PublicEventResponse } from '../../types/public';

interface PublicHeaderProps {
  event: PublicEventResponse;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

function formatDateRange(startDateStr: string, endDateStr: string): string {
  try {
    const start = new Date(startDateStr);
    const end = new Date(endDateStr);
    const options: Intl.DateTimeFormatOptions = {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    };
    const startFormatted = new Intl.DateTimeFormat('fr-FR', options).format(start);
    // Capitalize first letter
    const capitalized = startFormatted.charAt(0).toUpperCase() + startFormatted.slice(1);
    
    // Check if on same day
    if (start.toDateString() === end.toDateString()) {
      return capitalized;
    }
    const endFormatted = new Intl.DateTimeFormat('fr-FR', options).format(end);
    return `Du ${capitalized} au ${endFormatted}`;
  } catch {
    return `${startDateStr.slice(0, 10)}`;
  }
}

function formatPrice(price: number): string {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
  }).format(price);
}

export const PublicHeader: React.FC<PublicHeaderProps> = ({
  event,
  onRefresh,
  isRefreshing = false,
}) => {
  const dateDisplay = formatDateRange(event.start_date, event.end_date);
  const hoursDisplay =
    event.public_start_time && event.public_end_time
      ? `${event.public_start_time} — ${event.public_end_time}`
      : null;

  return (
    <header className="bg-[#FBFBFA] border-b border-gray-200 shadow-xs z-20">
      <div className="max-w-7xl mx-auto px-3 sm:px-6 py-3 sm:py-4">
        {/* Top brand row */}
        <div className="flex items-center justify-between gap-2 mb-2 sm:mb-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-700 text-white flex items-center justify-center font-extrabold text-sm shadow-xs">
              GVG
            </div>
            <span className="text-xs text-gray-500 font-medium hidden sm:inline">
              Plan interactif public
            </span>
          </div>

          <div className="flex items-center gap-2">
            <div className="text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 flex items-center gap-1.5">
              <Tag className="w-3.5 h-3.5 text-emerald-600" />
              <span>{formatPrice(event.price_per_meter)} / mètre</span>
            </div>

            {onRefresh && (
              <button
                onClick={onRefresh}
                disabled={isRefreshing}
                title="Rafraîchir les disponibilités"
                className="p-1.5 text-gray-500 hover:text-gray-800 rounded-lg hover:bg-gray-100 transition active:scale-95 disabled:opacity-50"
                aria-label="Rafraîchir le plan"
              >
                <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-emerald-600' : ''}`} />
              </button>
            )}
          </div>
        </div>

        {/* Title & Metadata */}
        <div className="flex flex-col gap-1.5">
          <h1 className="text-lg sm:text-2xl font-bold text-gray-900 leading-tight">
            {event.title}
          </h1>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs sm:text-sm text-gray-600">
            <div className="flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
              <span>{dateDisplay}</span>
            </div>

            {hoursDisplay && (
              <div className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                <span>Public : {hoursDisplay}</span>
              </div>
            )}

            {event.location_address && (
              <div className="flex items-center gap-1 truncate max-w-md">
                <MapPin className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                <span className="truncate">{event.location_address}</span>
              </div>
            )}
          </div>
        </div>

        {/* Status Legend Bar */}
        <div className="mt-3 pt-2.5 border-t border-gray-200/80 flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex items-center gap-3 sm:gap-5">
            {/* Available */}
            <div className="flex items-center gap-1.5">
              <span
                className="w-3 h-3 rounded-xs bg-[#10B981] border border-[#059669] shadow-2xs"
                aria-hidden="true"
              />
              <span className="font-semibold text-gray-800">Disponible</span>
            </div>

            {/* Locked */}
            <div className="flex items-center gap-1.5">
              <span
                className="w-3 h-3 rounded-xs bg-[#F59E0B] border border-[#D97706] shadow-2xs"
                aria-hidden="true"
              />
              <span className="font-medium text-gray-700">En cours de réservation</span>
            </div>

            {/* Reserved */}
            <div className="flex items-center gap-1.5">
              <span
                className="w-3 h-3 rounded-xs bg-[#9CA3AF] border border-[#6B7280] shadow-2xs"
                aria-hidden="true"
              />
              <span className="font-medium text-gray-500">Déjà réservé</span>
            </div>
          </div>

          <span className="text-[11px] text-gray-400 hidden md:inline">
            Touchez un stand vert pour consulter les détails
          </span>
        </div>
      </div>
    </header>
  );
};

