import React, { useEffect } from 'react';
import { X, CheckCircle2, Lock, Ban, Ruler, Euro } from 'lucide-react';
import { PublicSpotFeature } from '../../types/public';

interface SpotDetailDrawerProps {
  spot: PublicSpotFeature | null;
  onClose: () => void;
}

function formatPrice(price: number): string {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
  }).format(price);
}

function formatMeters(meters: number): string {
  return new Intl.NumberFormat('fr-FR', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 2,
  }).format(meters);
}

export const SpotDetailDrawer: React.FC<SpotDetailDrawerProps> = ({ spot, onClose }) => {
  // Dismiss on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!spot) return null;

  const { label, linear_meters, price, status } = spot.properties;

  return (
    <div
      className="fixed inset-0 z-40 flex items-end sm:items-center sm:justify-center p-0 sm:p-4 bg-black/30 backdrop-blur-2xs transition-opacity duration-200"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="spot-detail-title"
    >
      {/* Drawer Card */}
      <div
        className="w-full sm:max-w-md bg-white rounded-t-2xl sm:rounded-2xl shadow-xl border border-gray-100 overflow-hidden transform transition-transform duration-200 animate-slide-up sm:animate-scale-up"
        style={{ paddingBottom: 'max(1.25rem, env(safe-area-inset-bottom))' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Mobile grab handle */}
        <div className="w-12 h-1.5 bg-gray-300 rounded-full mx-auto mt-2.5 sm:hidden" />

        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-3 sm:pt-5 pb-3 border-b border-gray-100">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400">
              Emplacement
            </span>
            <h3
              id="spot-detail-title"
              className="text-xl sm:text-2xl font-black text-gray-900 leading-tight"
            >
              {label}
            </h3>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-full transition"
            aria-label="Fermer la fiche du stand"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 space-y-4">
          {/* Status Badge Banner */}
          {status === 'available' && (
            <div className="flex items-start gap-3 p-3.5 rounded-xl bg-emerald-50 border border-emerald-200/80 text-emerald-900">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
              <div>
                <div className="text-sm font-bold">Disponible à la réservation</div>
                <div className="text-xs text-emerald-700 mt-0.5">
                  Cet emplacement est libre et peut être réservé pour le vide-grenier.
                </div>
              </div>
            </div>
          )}

          {status === 'locked' && (
            <div className="flex items-start gap-3 p-3.5 rounded-xl bg-amber-50 border border-amber-200/80 text-amber-900">
              <Lock className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <div className="text-sm font-bold">Réservation en cours (verrouillé temporairement)</div>
                <div className="text-xs text-amber-700 mt-0.5">
                  Un visiteur est en train de finaliser sa commande pour cette place. Si le paiement
                  n'est pas validé sous 15 minutes, l'emplacement redeviendra disponible.
                </div>
              </div>
            </div>
          )}

          {status === 'reserved' && (
            <div className="flex items-start gap-3 p-3.5 rounded-xl bg-gray-50 border border-gray-200 text-gray-800">
              <Ban className="w-5 h-5 text-gray-500 flex-shrink-0 mt-0.5" />
              <div>
                <div className="text-sm font-bold">Emplacement déjà réservé</div>
                <div className="text-xs text-gray-500 mt-0.5">
                  Cette place a été attribuée à un exposant inscrit. Elle n'est plus disponible à la
                  vente.
                </div>
              </div>
            </div>
          )}

          {status === 'blocked' && (
            <div className="flex items-start gap-3 p-3.5 rounded-xl bg-gray-50 border border-gray-200 text-gray-700">
              <Ban className="w-5 h-5 text-gray-400 flex-shrink-0 mt-0.5" />
              <div>
                <div className="text-sm font-bold">Emplacement non disponible</div>
                <div className="text-xs text-gray-500 mt-0.5">
                  Cet espace est réservé pour des raisons techniques ou d'organisation.
                </div>
              </div>
            </div>
          )}

          {/* Details Grid: Linear meters & Price / Availability */}
          <div className="grid grid-cols-2 gap-3 pt-1">
            <div className="bg-[#FBFBFA] border border-gray-200/80 rounded-xl p-3.5 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gray-100 text-gray-700 flex items-center justify-center flex-shrink-0">
                <Ruler className="w-5 h-5" />
              </div>
              <div>
                <div className="text-xs text-gray-500 font-medium">Métrage linéaire</div>
                <div className="text-base sm:text-lg font-bold text-gray-900">
                  {formatMeters(linear_meters)} m
                </div>
              </div>
            </div>

            {status === 'available' || status === 'locked' ? (
              <div className="bg-[#FBFBFA] border border-gray-200/80 rounded-xl p-3.5 flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-700 flex items-center justify-center flex-shrink-0">
                  <Euro className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-xs text-gray-500 font-medium">Tarif total</div>
                  <div className="text-base sm:text-lg font-bold text-emerald-700">
                    {formatPrice(price)}
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-gray-50/80 border border-gray-200 rounded-xl p-3.5 flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gray-100 text-gray-400 flex items-center justify-center flex-shrink-0">
                  <Ban className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-xs text-gray-400 font-medium">Disponibilité</div>
                  <div className="text-sm font-bold text-gray-500">
                    Indisponible à la vente
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="px-5 pt-2 pb-1 sm:pb-3 flex items-center justify-end">
          <button
            onClick={onClose}
            className="w-full sm:w-auto px-5 py-2.5 text-sm font-semibold rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-700 transition"
          >
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
};

