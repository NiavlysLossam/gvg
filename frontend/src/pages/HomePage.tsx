import React, { useState, useEffect, useMemo } from 'react';
import {
  Search,
  MapPin,
  Calendar,
  Clock,
  Tag,
  ArrowRight,
  Store,
  LayoutDashboard,
  LogIn,
  AlertCircle,
  RefreshCw,
  X,
  Sparkles,
  Map as MapIcon,
} from 'lucide-react';
import { PublicEventListItem } from '../types/public';
import { fetchPublicEvents } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';

interface HomePageProps {
  onViewEvent: (slug: string) => void;
  onReserveEvent?: (slug: string) => void;
  onNavigateAdmin: () => void;
  onNavigateLogin: () => void;
}

function formatDateRange(startDateStr: string, endDateStr: string): string {
  try {
    const start = new Date(startDateStr);
    const end = new Date(endDateStr);
    const isSameDay =
      start.getFullYear() === end.getFullYear() &&
      start.getMonth() === end.getMonth() &&
      start.getDate() === end.getDate();

    if (isSameDay) {
      const formatted = new Intl.DateTimeFormat('fr-FR', {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      }).format(start);
      return formatted.charAt(0).toUpperCase() + formatted.slice(1);
    }

    // Different days
    const dayFormatter = new Intl.DateTimeFormat('fr-FR', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });

    const startPart = new Intl.DateTimeFormat('fr-FR', {
      day: 'numeric',
      month: start.getMonth() === end.getMonth() ? undefined : 'short',
    }).format(start);
    const endPart = dayFormatter.format(end);

    return `Du ${startPart} au ${endPart}`;
  } catch {
    return startDateStr.slice(0, 10);
  }
}

function formatPrice(price: number): string {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
  }).format(price);
}

export const HomePage: React.FC<HomePageProps> = ({
  onViewEvent,
  onReserveEvent: _onReserveEvent,
  onNavigateAdmin,
  onNavigateLogin,
}) => {
  const { user, isAuthenticated } = useAuth();
  const [events, setEvents] = useState<PublicEventListItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [debouncedQuery, setDebouncedQuery] = useState<string>('');
  const [failedImages, setFailedImages] = useState<Record<string, boolean>>({});

  // Debounce search query for server fetch
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery);
    }, 250);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Asynchronous search with active flag to prevent out-of-order race conditions
  useEffect(() => {
    let active = true;

    const doFetch = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchPublicEvents(debouncedQuery);
        if (active) {
          setEvents(data);
        }
      } catch (err: unknown) {
        if (active) {
          setError(
            err instanceof Error ? err.message : 'Erreur lors du chargement des événements'
          );
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    doFetch();

    return () => {
      active = false;
    };
  }, [debouncedQuery]);

  // Client-side quick filter for ultra-responsive instant typing
  const filteredEvents = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return events;
    return events.filter((evt) => {
      const titleMatch = evt.title.toLowerCase().includes(q);
      const addrMatch = evt.location_address?.toLowerCase().includes(q) || false;
      const descMatch = evt.description?.toLowerCase().includes(q) || false;
      return titleMatch || addrMatch || descMatch;
    });
  }, [events, searchQuery]);

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Public Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-600 text-white flex items-center justify-center font-bold text-lg shadow-sm">
              <MapIcon className="w-5 h-5" />
            </div>
            <div>
              <span className="font-extrabold text-gray-900 text-lg leading-tight tracking-tight">
                GVG
              </span>
              <span className="hidden sm:inline-block ml-2 text-xs text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full font-semibold border border-emerald-200">
                Portail Public
              </span>
              <p className="text-xs text-gray-500 font-medium hidden md:block">
                Vide-Greniers &amp; Brocantes Locales
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            {isAuthenticated ? (
              <div className="flex items-center space-x-2">
                <span className="text-xs text-gray-500 hidden md:inline font-medium">
                  Connecté : <strong className="text-gray-800">{user?.email}</strong>
                </span>
                <button
                  type="button"
                  onClick={onNavigateAdmin}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold rounded-lg shadow-sm transition flex items-center gap-2"
                >
                  <LayoutDashboard className="w-4 h-4" />
                  <span>Tableau de bord</span>
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={onNavigateLogin}
                className="px-4 py-2 bg-white hover:bg-gray-50 text-gray-700 hover:text-gray-900 border border-gray-300 text-sm font-semibold rounded-lg shadow-sm transition flex items-center gap-2"
              >
                <LogIn className="w-4 h-4 text-gray-500" />
                <span>Espace Organisateur</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="bg-gradient-to-b from-emerald-700 via-emerald-800 to-emerald-900 text-white py-14 sm:py-20 px-4 sm:px-6 lg:px-8 shadow-inner relative overflow-hidden">
        {/* Background decoration */}
        <div className="absolute inset-0 opacity-10 pointer-events-none">
          <div className="absolute -top-24 -right-24 w-96 h-96 rounded-full bg-white blur-3xl" />
          <div className="absolute -bottom-24 -left-24 w-96 h-96 rounded-full bg-emerald-300 blur-3xl" />
        </div>

        <div className="max-w-4xl mx-auto text-center relative z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-600/60 border border-emerald-400/30 text-emerald-100 text-xs font-semibold mb-4">
            <Sparkles className="w-3.5 h-3.5 text-emerald-300" />
            <span>Découvrez les vide-greniers et réservez votre stand</span>
          </div>

          <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-white leading-tight">
            Trouvez votre prochain vide-grenier
          </h1>
          <p className="mt-4 text-base sm:text-lg text-emerald-100/90 max-w-2xl mx-auto font-normal">
            Consultez les événements à venir dans votre commune, visualisez le plan interactif et
            choisissez votre emplacement en quelques clics.
          </p>

          {/* Search bar */}
          <div className="mt-8 max-w-2xl mx-auto">
            <div className="relative flex items-center shadow-lg rounded-2xl bg-white text-gray-900 overflow-hidden focus-within:ring-4 focus-within:ring-emerald-400/50 transition">
              <div className="pl-4 text-gray-400 flex items-center pointer-events-none">
                <Search className="w-5 h-5 text-gray-400" />
              </div>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Rechercher par commune, mot-clé, nom d'événement..."
                aria-label="Rechercher un événement"
                className="w-full py-4 pl-3 pr-10 text-sm sm:text-base text-gray-900 placeholder-gray-400 focus:outline-none bg-transparent"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="pr-4 text-gray-400 hover:text-gray-600 transition"
                  title="Effacer la recherche"
                >
                  <X className="w-5 h-5" />
                </button>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Main Events Catalog */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-10">
        {/* Section Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 tracking-tight">
              Événements à venir
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              {filteredEvents.length === 1
                ? '1 événement disponible'
                : `${filteredEvents.length} événements disponibles`}
              {searchQuery.trim() && ` pour « ${searchQuery.trim()} »`}
            </p>
          </div>

          <button
            type="button"
            onClick={() => {
              setLoading(true);
              fetchPublicEvents(debouncedQuery)
                .then((data) => setEvents(data))
                .catch((err) =>
                  setError(err instanceof Error ? err.message : 'Erreur de chargement')
                )
                .finally(() => setLoading(false));
            }}
            disabled={loading}
            className="p-2 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition"
            title="Actualiser les événements"
          >
            <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin text-emerald-600' : ''}`} />
          </button>
        </div>

        {/* Error State */}
        {error && (
          <div className="mb-8 bg-red-50 border border-red-200 text-red-800 px-4 py-4 rounded-xl flex items-center justify-between shadow-sm">
            <div className="flex items-center space-x-3">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
              <p className="text-sm font-medium">{error}</p>
            </div>
            <button
              type="button"
              onClick={() => {
                setLoading(true);
                fetchPublicEvents(debouncedQuery)
                  .then((data) => setEvents(data))
                  .catch((err) =>
                    setError(err instanceof Error ? err.message : 'Erreur de chargement')
                  )
                  .finally(() => setLoading(false));
              }}
              className="text-xs text-red-700 hover:underline font-semibold"
            >
              Réessayer
            </button>
          </div>
        )}

        {/* Loading State */}
        {loading && events.length === 0 ? (
          <div className="py-24 text-center text-gray-500">
            <RefreshCw className="w-10 h-10 animate-spin mx-auto mb-4 text-emerald-600" />
            <p className="text-base font-medium text-gray-700">Chargement des événements...</p>
            <p className="text-xs text-gray-400 mt-1">Recherche des vide-greniers publiés...</p>
          </div>
        ) : filteredEvents.length === 0 ? (
          /* Empty State */
          <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center max-w-lg mx-auto my-8 shadow-sm">
            <div className="w-16 h-16 bg-emerald-50 text-emerald-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <Store className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-bold text-gray-900">
              {searchQuery.trim()
                ? 'Aucun vide-grenier trouvé'
                : 'Aucun événement à venir pour le moment'}
            </h3>
            <p className="text-sm text-gray-500 mt-2 max-w-sm mx-auto">
              {searchQuery.trim()
                ? `Aucun événement ne correspond à « ${searchQuery.trim()} ». Essayez d'élargir vos critères de recherche.`
                : 'Les organisateurs préparent les prochains vide-greniers. Revenez très bientôt pour découvrir les dates !'}
            </p>
            {searchQuery.trim() && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="mt-5 inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold rounded-lg shadow-sm transition"
              >
                <X className="w-4 h-4" />
                <span>Effacer la recherche</span>
              </button>
            )}
          </div>
        ) : (
          /* Event Cards Grid */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredEvents.map((event) => {
              const hasSpots = event.available_spots > 0;
              const isFull = event.total_spots > 0 && event.available_spots === 0;
              const imageUrl = event.poster_image_url || event.background_image_url;
              const hasImage = Boolean(imageUrl) && !failedImages[event.id];

              return (
                <article
                  key={event.id}
                  className="bg-white rounded-2xl border border-gray-200 overflow-hidden shadow-sm hover:shadow-md transition-shadow flex flex-col"
                >
                  {/* Visual Banner */}
                  <div className="relative h-44 bg-gradient-to-br from-emerald-600 via-teal-700 to-emerald-800 flex items-center justify-center overflow-hidden">
                    {hasImage ? (
                      <img
                        src={imageUrl!}
                        alt={event.title}
                        onError={() =>
                          setFailedImages((prev) => ({ ...prev, [event.id]: true }))
                        }
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="text-center text-white/80 p-4">
                        <Store className="w-12 h-12 mx-auto mb-1 text-white/60" />
                        <span className="text-xs uppercase tracking-wider font-semibold text-emerald-100">
                          Vide-Grenier
                        </span>
                      </div>
                    )}

                    {/* Date Badge */}
                    <div className="absolute top-3 left-3 bg-white/95 backdrop-blur-sm text-gray-900 px-3 py-1 rounded-lg text-xs font-bold shadow-sm flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-emerald-600" />
                      <span>{formatDateRange(event.start_date, event.end_date)}</span>
                    </div>

                    {/* Price Badge */}
                    <div className="absolute top-3 right-3 bg-emerald-900/90 backdrop-blur-sm text-white px-2.5 py-1 rounded-lg text-xs font-bold shadow-sm flex items-center gap-1">
                      <Tag className="w-3.5 h-3.5 text-emerald-300" />
                      <span>{formatPrice(event.price_per_meter)} / m</span>
                    </div>
                  </div>

                  {/* Card Content */}
                  <div className="p-5 flex-1 flex flex-col">
                    <h3 className="text-lg font-bold text-gray-900 line-clamp-1 leading-snug">
                      {event.title}
                    </h3>

                    {/* Meta info */}
                    <div className="mt-2.5 space-y-1.5 text-xs text-gray-600">
                      {event.location_address && (
                        <div className="flex items-center gap-1.5 truncate">
                          <MapPin className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                          <span className="truncate">{event.location_address}</span>
                        </div>
                      )}

                      {event.public_start_time && event.public_end_time && (
                        <div className="flex items-center gap-1.5">
                          <Clock className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                          <span>
                            Ouvert au public de {event.public_start_time} à {event.public_end_time}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Description snippet */}
                    {event.description && (
                      <p className="mt-3 text-xs text-gray-500 line-clamp-2 leading-relaxed">
                        {event.description}
                      </p>
                    )}

                    {/* Capacity Badge */}
                    <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between text-xs">
                      <span className="text-gray-500 font-medium">Disponibilité :</span>
                      {hasSpots ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                          <span>
                            {event.available_spots}{' '}
                            {event.available_spots > 1 ? 'stands dispos' : 'stand dispo'}
                            {event.total_spots > 0 && ` / ${event.total_spots}`}
                          </span>
                        </span>
                      ) : isFull ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-semibold bg-red-50 text-red-700 border border-red-200">
                          <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                          <span>Complet</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-semibold bg-gray-100 text-gray-600">
                          <span>Plan en préparation</span>
                        </span>
                      )}
                    </div>

                    {/* Action Buttons */}
                    <div className="mt-5 pt-3 flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => onViewEvent(event.slug)}
                        className="flex-1 py-2 px-3 bg-gray-100 hover:bg-gray-200 text-gray-800 text-xs font-semibold rounded-lg transition text-center"
                      >
                        Voir l'événement
                      </button>

                      {/* Directly navigate to the interactive map view so visitors can choose their stall */}
                      <button
                        type="button"
                        onClick={() => onViewEvent(event.slug)}
                        disabled={!hasSpots}
                        className={`py-2 px-3 text-xs font-semibold rounded-lg transition flex items-center justify-center gap-1 shadow-sm ${
                          hasSpots
                            ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                            : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                        }`}
                        title={
                          hasSpots
                            ? 'Sélectionner un stand sur le plan'
                            : 'Aucun stand disponible actuellement'
                        }
                      >
                        <span>Réserver</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </main>

      {/* Public Footer */}
      <footer className="bg-white border-t border-gray-200 py-8 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-xs text-gray-400">
          <p className="font-medium text-gray-500">
            GVG &copy; 2026 &mdash; Plateforme libre et open-source de gestion de vide-greniers et
            brocantes.
          </p>
          <p className="mt-1">
            Développé pour les associations, communes et organisateurs bénévoles.
          </p>
        </div>
      </footer>
    </div>
  );
};
