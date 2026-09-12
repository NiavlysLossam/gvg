import React, { useState, useEffect, useMemo } from 'react';
import {
  ShoppingBag,
  ChevronUp,
  ChevronDown,
  X,
  Clock,
  ArrowRight,
} from 'lucide-react';
import { CartResponse, CartSpotItem } from '../../types/public';

interface CartDrawerProps {
  cart: CartResponse | null;
  onRemoveSpot: (spotId: string) => Promise<void> | void;
  onTimerExpired: () => void;
  onProceedToCheckout?: () => void;
  removingSpotId?: string | null;
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

export const CartDrawer: React.FC<CartDrawerProps> = ({
  cart,
  onRemoveSpot,
  onTimerExpired,
  onProceedToCheckout,
  removingSpotId,
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [remainingSeconds, setRemainingSeconds] = useState<number>(0);

  const spots = cart?.spots || [];
  const totalCount = cart?.total_count || spots.length;
  const totalMeters = cart?.total_linear_meters || spots.reduce((acc, s) => acc + s.linear_meters, 0);
  const totalPrice = cart?.total_price || spots.reduce((acc, s) => acc + s.price, 0);
  const expiresAt = cart?.expires_at;

  // Calculate live countdown timer synced with earliest locked_until
  useEffect(() => {
    if (!expiresAt || totalCount === 0) {
      setRemainingSeconds(0);
      return;
    }

    const calculateRemaining = () => {
      // Append 'Z' if naive ISO string without timezone
      const hasTimezone = /[Zz]$|[+-]\d{2}:\d{2}$/.test(expiresAt);
      const normalizedIso = hasTimezone ? expiresAt : `${expiresAt}Z`;
      const expiryTime = new Date(normalizedIso).getTime();
      const now = Date.now();
      const diffSecs = Math.max(0, Math.floor((expiryTime - now) / 1000));
      return diffSecs;
    };

    // Initial check
    const initial = calculateRemaining();
    setRemainingSeconds(initial);

    if (initial <= 0) {
      onTimerExpired();
      return;
    }

    const interval = setInterval(() => {
      const remaining = calculateRemaining();
      setRemainingSeconds(remaining);
      if (remaining <= 0) {
        clearInterval(interval);
        onTimerExpired();
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [expiresAt, totalCount, onTimerExpired]);

  // Formatted countdown string (MM:SS)
  const timerDisplay = useMemo(() => {
    const mins = Math.floor(remainingSeconds / 60);
    const secs = remainingSeconds % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }, [remainingSeconds]);

  // Warning state when under 2 minutes (120 seconds)
  const isUrgent = remainingSeconds > 0 && remainingSeconds <= 120;

  if (!cart || totalCount === 0) {
    return null;
  }

  const standPlural = totalCount > 1 ? 'stands' : 'stand';
  const summaryText = `${totalCount} ${standPlural} (${formatMeters(totalMeters)} m) • ${formatPrice(totalPrice)}`;

  return (
    <div className="fixed bottom-0 inset-x-0 z-40 flex flex-col items-center pointer-events-none">
      {/* Expanded Backdrop for mobile tap-out */}
      {isExpanded && (
        <div
          className="fixed inset-0 bg-black/25 backdrop-blur-2xs z-0 pointer-events-auto transition-opacity"
          onClick={() => setIsExpanded(false)}
          aria-hidden="true"
        />
      )}

      {/* Cart Container Card */}
      <div
        className={`w-full max-w-lg bg-white shadow-2xl border-t sm:border-x sm:rounded-t-2xl border-gray-200 pointer-events-auto transition-all duration-300 z-10 overflow-hidden flex flex-col ${
          isExpanded ? 'max-h-[85vh]' : 'max-h-24'
        }`}
        style={{ paddingBottom: 'max(0.75rem, env(safe-area-inset-bottom))' }}
      >
        {/* Drag/Expand handle */}
        <button
          type="button"
          onClick={() => setIsExpanded((prev) => !prev)}
          className="w-full pt-2 pb-1.5 flex flex-col items-center justify-center hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 transition"
          aria-label={isExpanded ? 'Réduire le panier' : 'Agrandir le panier'}
        >
          <div className="w-12 h-1 bg-gray-300 rounded-full mb-1" />
        </button>

        {/* Collapsed Bar / Main Header */}
        <div className="px-4 pb-2 flex items-center justify-between gap-2 sm:gap-4">
          <div
            className="flex items-center gap-2 sm:gap-3 cursor-pointer select-none min-w-0 flex-1"
            onClick={() => setIsExpanded((prev) => !prev)}
          >
            <div className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center flex-shrink-0 shadow-xs">
              <ShoppingBag className="w-5 h-5" />
            </div>

            <div className="min-w-0 flex-1">
              <div className="text-xs sm:text-sm font-black text-gray-900 truncate">
                {summaryText}
              </div>
              <div className="flex items-center gap-1.5 mt-0.5">
                {/* Hold Timer Pill */}
                <div
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold tracking-tight transition-colors ${
                    isUrgent
                      ? 'bg-red-50 text-red-700 border border-red-300 animate-pulse'
                      : 'bg-amber-50 text-amber-800 border border-amber-200'
                  }`}
                  title="Temps restant pour finaliser votre réservation"
                >
                  <Clock className={`w-3 h-3 ${isUrgent ? 'text-red-600' : 'text-amber-600'}`} />
                  <span>Réservé : {timerDisplay}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Action buttons on collapsed bar */}
          <div className="flex items-center gap-1.5 flex-shrink-0">
            <button
              type="button"
              onClick={() => setIsExpanded((prev) => !prev)}
              className="p-2 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-xl transition"
              aria-label={isExpanded ? 'Réduire le panier' : 'Voir le détail du panier'}
            >
              {isExpanded ? (
                <ChevronDown className="w-5 h-5" />
              ) : (
                <ChevronUp className="w-5 h-5" />
              )}
            </button>

            {onProceedToCheckout ? (
              <button
                type="button"
                onClick={onProceedToCheckout}
                className="px-3 sm:px-4 py-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-xs sm:text-sm font-bold shadow-xs transition flex items-center gap-1.5 active:scale-95"
              >
                <span>Continuer</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            ) : null}
          </div>
        </div>

        {/* Expanded Item List & Summary */}
        {isExpanded && (
          <div className="px-4 pt-2 pb-3 border-t border-gray-100 flex-1 overflow-y-auto space-y-3">
            <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-gray-400">
              <span>Emplacements sélectionnés ({totalCount})</span>
              <span>Métrage & Tarif</span>
            </div>

            {/* List of Stalls */}
            <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
              {spots.map((spot: CartSpotItem) => {
                const isRemoving = removingSpotId === spot.id;
                return (
                  <div
                    key={spot.id}
                    className="flex items-center justify-between p-2.5 rounded-xl bg-gray-50 border border-gray-200/80 hover:border-blue-300 transition"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="w-7 h-7 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center font-mono font-bold text-xs flex-shrink-0">
                        {spot.label}
                      </div>
                      <div className="min-w-0">
                        <div className="text-xs font-bold text-gray-900">
                          Stand {spot.label}
                        </div>
                        <div className="text-[11px] text-gray-500">
                          {formatMeters(spot.linear_meters)} m linéaires
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <span className="text-xs sm:text-sm font-bold text-emerald-700">
                        {formatPrice(spot.price)}
                      </span>

                      <button
                        type="button"
                        onClick={() => onRemoveSpot(spot.id)}
                        disabled={isRemoving}
                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition disabled:opacity-50"
                        title={`Retirer le stand ${spot.label} du panier`}
                        aria-label={`Retirer le stand ${spot.label}`}
                      >
                        {isRemoving ? (
                          <div className="w-4 h-4 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
                        ) : (
                          <X className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Hold Timer Alert inside expanded view */}
            <div
              className={`p-3 rounded-xl border flex items-start gap-2.5 ${
                isUrgent
                  ? 'bg-red-50 border-red-200 text-red-900'
                  : 'bg-amber-50 border-amber-200 text-amber-900'
              }`}
            >
              <Clock
                className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                  isUrgent ? 'text-red-600 animate-bounce' : 'text-amber-600'
                }`}
              />
              <div className="text-xs leading-relaxed">
                <span className="font-bold">Verrou temporaire de 15 minutes :</span> vos stands
                vous sont réservés pendant encore <strong className="font-mono font-black">{timerDisplay}</strong>. Au-delà, ils
                seront automatiquement libérés pour les autres visiteurs.
              </div>
            </div>

            {/* Total recap line */}
            <div className="pt-2 border-t border-gray-100 flex items-center justify-between text-sm">
              <span className="font-medium text-gray-600">Total à régler :</span>
              <div className="text-right">
                <span className="text-lg font-black text-gray-900">
                  {formatPrice(totalPrice)}
                </span>
                <div className="text-[11px] text-gray-500">
                  {totalCount} {standPlural} • {formatMeters(totalMeters)} m
                </div>
              </div>
            </div>

            {/* Primary Action Button */}
            {onProceedToCheckout && (
              <button
                type="button"
                onClick={onProceedToCheckout}
                className="w-full mt-2 py-3 px-4 rounded-xl bg-emerald-700 hover:bg-emerald-800 active:bg-emerald-900 text-white font-bold text-sm shadow-md transition flex items-center justify-center gap-2 active:scale-98"
              >
                <span>Continuer la réservation</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
