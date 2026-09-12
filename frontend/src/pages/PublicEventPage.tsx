import React, { useState, useEffect, useCallback } from 'react';
import { AlertCircle, AlertTriangle, ArrowLeft, Map as MapIcon } from 'lucide-react';
import { PublicEventResponse, PublicSpotFeature } from '../types/public';
import { fetchPublicEvent, fetchPublicSpots } from '../lib/api';
import { PublicHeader } from '../components/public/PublicHeader';
import { PublicMap } from '../components/public/PublicMap';
import { SpotDetailDrawer } from '../components/public/SpotDetailDrawer';

interface PublicEventPageProps {
  slug: string;
  onNavigateHome?: () => void;
}

export const PublicEventPage: React.FC<PublicEventPageProps> = ({ slug, onNavigateHome }) => {
  const [event, setEvent] = useState<PublicEventResponse | null>(null);
  const [spots, setSpots] = useState<PublicSpotFeature[]>([]);
  const [selectedSpot, setSelectedSpot] = useState<PublicSpotFeature | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [notFound, setNotFound] = useState<boolean>(false);
  const [initialError, setInitialError] = useState<string | null>(null);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Initial event + spots load
  const loadInitialData = useCallback(async () => {
    setLoading(true);
    setNotFound(false);
    setInitialError(null);
    setErrorBanner(null);

    try {
      const [eventData, spotsData] = await Promise.all([
        fetchPublicEvent(slug),
        fetchPublicSpots(slug),
      ]);
      setEvent(eventData);
      setSpots(spotsData.features);
    } catch (err: any) {
      if (err?.status === 404 || err?.message?.includes('introuvable')) {
        setNotFound(true);
      } else {
        setInitialError(err?.message || "Impossible de charger le vide-grenier");
      }
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Isolated spots polling (only re-fetches dynamic spots, only when tab is visible)
  const pollSpots = useCallback(async () => {
    if (typeof document !== 'undefined' && document.visibilityState !== 'visible') {
      return;
    }
    try {
      setIsRefreshing(true);
      const spotsData = await fetchPublicSpots(slug);
      setSpots(spotsData.features);
      setSelectedSpot((curr) => {
        if (!curr) return null;
        return spotsData.features.find((s) => s.id === curr.id) || curr;
      });
      setErrorBanner(null);
    } catch {
      setErrorBanner('Impossible de rafraîchir le plan');
      setTimeout(() => setErrorBanner(null), 4000);
    } finally {
      setIsRefreshing(false);
    }
  }, [slug]);

  // Stable 10-second polling interval for real-time spots updates
  useEffect(() => {
    if (!event) return;
    const interval = setInterval(() => {
      pollSpots();
    }, 10000);
    return () => clearInterval(interval);
  }, [event?.id, pollSpots]);

  // Spot selection handler
  const handleSpotSelect = (spot: PublicSpotFeature) => {
    setSelectedSpot(spot);
  };

  // Close drawer
  const handleCloseDrawer = () => {
    setSelectedSpot(null);
  };

  // 1. Loading State (Skeleton Loader)
  if (loading && !event && !notFound && !initialError) {
    return (
      <div className="min-h-screen bg-[#FBFBFA] flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full text-center space-y-4 animate-pulse">
          <div className="w-16 h-16 bg-emerald-100 text-emerald-700 rounded-2xl flex items-center justify-center mx-auto shadow-xs">
            <MapIcon className="w-8 h-8 animate-bounce" />
          </div>
          <div className="h-6 bg-gray-200 rounded-lg w-3/4 mx-auto" />
          <div className="h-4 bg-gray-200 rounded-lg w-1/2 mx-auto" />
          <p className="text-sm font-medium text-gray-600 pt-2">
            Chargement du plan du vide-grenier...
          </p>
        </div>
      </div>
    );
  }

  // 2. Not Found State (404)
  if (notFound) {
    return (
      <div className="min-h-screen bg-[#FBFBFA] flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-sm border border-gray-200 p-8 text-center">
          <div className="w-14 h-14 bg-red-50 text-red-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-extrabold text-gray-900">Événement introuvable</h2>
          <p className="text-sm text-gray-500 mt-2 leading-relaxed">
            Le vide-grenier demandé n'existe pas ou l'adresse URL est incorrecte.
          </p>
          {onNavigateHome && (
            <button
              onClick={onNavigateHome}
              className="mt-6 inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-semibold shadow-xs transition active:scale-95"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Retour à l'accueil</span>
            </button>
          )}
        </div>
      </div>
    );
  }

  // 3. Full-page Error State (Network or server error on initial load)
  if (initialError) {
    return (
      <div className="min-h-screen bg-[#FBFBFA] flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-sm border border-gray-200 p-8 text-center">
          <div className="w-14 h-14 bg-red-50 text-red-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-extrabold text-gray-900">Erreur de chargement</h2>
          <p className="text-sm text-gray-500 mt-2 leading-relaxed">{initialError}</p>
          <div className="mt-6 flex items-center justify-center gap-3">
            {onNavigateHome && (
              <button
                onClick={onNavigateHome}
                className="px-4 py-2.5 rounded-xl border border-gray-200 text-gray-700 hover:bg-gray-50 text-sm font-semibold transition"
              >
                Accueil
              </button>
            )}
            <button
              onClick={() => loadInitialData()}
              className="px-5 py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-semibold shadow-xs transition active:scale-95"
            >
              Réessayer
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 4. Nominal Public Map Presentation
  return (
    <div className="h-screen w-full flex flex-col bg-[#FBFBFA] overflow-hidden">
      {/* Discreet refresh error banner */}
      {errorBanner && (
        <div className="fixed top-2 left-1/2 transform -translate-x-1/2 z-50 bg-amber-50 border border-amber-300 text-amber-900 px-4 py-2 rounded-full shadow-lg text-xs font-semibold flex items-center gap-2 animate-fade-in">
          <AlertTriangle className="w-4 h-4 text-amber-600" />
          <span>{errorBanner}</span>
        </div>
      )}

      {/* Public Header */}
      {event && (
        <PublicHeader
          event={event}
          onRefresh={pollSpots}
          isRefreshing={isRefreshing}
        />
      )}

      {/* Main Map Area with flexible height */}
      <main className="flex-1 min-h-0 w-full relative">
        {event && (
          <PublicMap
            event={event}
            spots={spots}
            selectedSpot={selectedSpot}
            onSpotSelect={handleSpotSelect}
          />
        )}
      </main>

      {/* Stall Detail Drawer */}
      <SpotDetailDrawer
        spot={selectedSpot}
        onClose={handleCloseDrawer}
      />
    </div>
  );
};

