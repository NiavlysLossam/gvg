import React, { useState, useEffect } from 'react';
import {
  Calendar,
  Clock,
  MapPin,
  Map as MapIcon,
  Tag,
  Coffee,
  Utensils,
  Car,
  Accessibility,
  FileText,
  Mail,
  Share2,
  Maximize2,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  ExternalLink,
  ChevronRight,
  Sparkles,
  Info,
  X,
} from 'lucide-react';
import { PublicEventResponse } from '../types/public';
import { fetchPublicEvent } from '../lib/api';

interface EventShowcasePageProps {
  slug: string;
  onNavigateToMap: () => void;
  onNavigateToReservation?: () => void;
  onNavigateHome?: () => void;
}

export const EventShowcasePage: React.FC<EventShowcasePageProps> = ({
  slug,
  onNavigateToMap,
  onNavigateToReservation: _onNavigateToReservation,
  onNavigateHome,
}) => {
  const [event, setEvent] = useState<PublicEventResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lightboxOpen, setLightboxOpen] = useState<boolean>(false);
  const [copiedLink, setCopiedLink] = useState<boolean>(false);
  const [posterLoadError, setPosterLoadError] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);
    setPosterLoadError(false);

    fetchPublicEvent(slug)
      .then((data) => {
        if (isMounted) {
          setEvent(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(
            err instanceof Error
              ? err.message
              : "Impossible de charger les informations de cet événement."
          );
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [slug]);

  const formatDateRange = (startDateStr?: string, endDateStr?: string): string => {
    if (!startDateStr) return '';
    try {
      const start = new Date(startDateStr);
      const options: Intl.DateTimeFormatOptions = {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      };
      const startFormatted = new Intl.DateTimeFormat('fr-FR', options).format(start);
      const capitalized = startFormatted.charAt(0).toUpperCase() + startFormatted.slice(1);

      if (!endDateStr) return capitalized;
      const end = new Date(endDateStr);
      if (start.toDateString() === end.toDateString()) {
        return capitalized;
      }
      const endFormatted = new Intl.DateTimeFormat('fr-FR', options).format(end);
      return `Du ${capitalized} au ${endFormatted}`;
    } catch {
      return startDateStr;
    }
  };

  const handleShare = async () => {
    if (navigator.share && event) {
      try {
        await navigator.share({
          title: event.title,
          text: `Découvrez le vide-grenier « ${event.title} » et réservez votre stand !`,
          url: window.location.href,
        });
        return;
      } catch {
        // user cancelled or unsupported
      }
    }

    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2500);
    } catch {
      // ignore
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="flex flex-col items-center space-y-4 max-w-sm text-center">
          <div className="w-12 h-12 border-4 border-emerald-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-gray-600 font-medium">Chargement de la vitrine de l'événement...</p>
        </div>
      </div>
    );
  }

  if (error || !event) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white p-8 rounded-2xl shadow-sm border border-gray-200 max-w-md w-full text-center space-y-4">
          <div className="w-14 h-14 rounded-full bg-amber-50 text-amber-600 flex items-center justify-center mx-auto">
            <AlertCircle className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold text-gray-900">Événement introuvable</h2>
          <p className="text-sm text-gray-600">
            {error || "Cet événement n'existe pas ou n'est plus accessible au public."}
          </p>
          {onNavigateHome && (
            <button
              type="button"
              onClick={onNavigateHome}
              className="inline-flex items-center justify-center gap-2 w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-xl transition"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Retour à l'accueil</span>
            </button>
          )}
        </div>
      </div>
    );
  }

  const rawPosterUrl = event.poster_image_url || event.background_image_url;
  const posterUrl = !posterLoadError ? rawPosterUrl : null;
  const totalSpots = event.total_spots ?? 0;
  const availableSpots = event.available_spots ?? 0;
  const hasConfiguredSpots = totalSpots > 0;
  const isSoldOut = hasConfiguredSpots && availableSpots === 0;
  const occupancyPercent =
    totalSpots > 0
      ? Math.round(((totalSpots - availableSpots) / totalSpots) * 100)
      : 0;
  const priceDisplay = (
    event.price_per_meter ?? (event.price_per_meter_cents ? event.price_per_meter_cents / 100 : 0)
  ).toFixed(2);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col pb-20 sm:pb-12">
      {/* Top Navigation Bar */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30 shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {onNavigateHome && (
            <button
              type="button"
              onClick={onNavigateHome}
              className="inline-flex items-center gap-2 text-sm font-semibold text-gray-600 hover:text-emerald-700 transition"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="hidden sm:inline">Tous les vide-greniers</span>
              <span className="sm:hidden">Accueil</span>
            </button>
          )}

          <div className="flex items-center gap-2 sm:gap-3 ml-auto">
            <button
              type="button"
              onClick={handleShare}
              className="p-2 rounded-xl border border-gray-200 text-gray-600 hover:bg-gray-100 hover:text-gray-900 transition flex items-center gap-1.5 text-xs font-semibold"
              title="Partager cet événement"
              aria-label="Partager cet événement"
            >
              <Share2 className="w-4 h-4" />
              <span className="hidden md:inline">
                {copiedLink ? 'Lien copié !' : 'Partager'}
              </span>
            </button>

            <button
              type="button"
              onClick={onNavigateToMap}
              className="inline-flex items-center gap-2 py-2 px-4 bg-emerald-600 hover:bg-emerald-700 text-white text-xs sm:text-sm font-semibold rounded-xl shadow-xs transition"
            >
              <MapIcon className="w-4 h-4" />
              <span>Consulter le plan</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-10 flex-1 space-y-8 sm:space-y-12">
        {/* HERO SHOWCASE SECTION */}
        <section className="bg-white rounded-3xl border border-gray-200 shadow-sm overflow-hidden grid grid-cols-1 lg:grid-cols-12 gap-0">
          {/* Poster Column */}
          <div className="lg:col-span-5 bg-gradient-to-br from-slate-900 to-slate-800 p-6 sm:p-8 flex flex-col items-center justify-center relative min-h-[320px] sm:min-h-[440px]">
            {posterUrl ? (
              <div className="relative group max-w-sm w-full rounded-2xl overflow-hidden shadow-2xl border-2 border-white/20">
                <img
                  src={posterUrl}
                  alt={`Affiche officielle - ${event.title}`}
                  onError={() => setPosterLoadError(true)}
                  className="w-full h-auto max-h-[500px] object-cover object-center transition duration-300 group-hover:scale-105 cursor-pointer"
                  onClick={() => setLightboxOpen(true)}
                />
                <button
                  type="button"
                  onClick={() => setLightboxOpen(true)}
                  className="absolute bottom-3 right-3 bg-black/70 hover:bg-black/90 text-white text-xs font-semibold py-1.5 px-3 rounded-lg backdrop-blur-xs flex items-center gap-1.5 transition"
                >
                  <Maximize2 className="w-3.5 h-3.5" />
                  <span>Agrandir l'affiche</span>
                </button>
              </div>
            ) : (
              <div className="max-w-xs w-full bg-white/10 backdrop-blur-md rounded-2xl p-8 border border-white/20 text-center text-white space-y-4 shadow-xl">
                <div className="w-16 h-16 rounded-2xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto border border-emerald-500/30">
                  <Sparkles className="w-8 h-8" />
                </div>
                <div>
                  <span className="inline-block px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 mb-2">
                    Affiche officielle
                  </span>
                  <h3 className="text-xl font-bold leading-tight">{event.title}</h3>
                </div>
                <p className="text-xs text-slate-300">
                  Édition officielle &bull; Inscriptions ouvertes aux particuliers et professionnels.
                </p>
              </div>
            )}
          </div>

          {/* Event Details & Primary CTA Column */}
          <div className="lg:col-span-7 p-6 sm:p-10 flex flex-col justify-between space-y-6">
            <div className="space-y-4">
              {/* Status Badge */}
              <div className="flex flex-wrap items-center gap-2.5">
                {hasConfiguredSpots ? (
                  isSoldOut ? (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200">
                      <span className="w-2 h-2 rounded-full bg-amber-500" />
                      Complet
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                      <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                      Inscriptions en ligne ouvertes
                    </span>
                  )
                ) : (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-blue-50 text-blue-800 border border-blue-200">
                    <span className="w-2 h-2 rounded-full bg-blue-500" />
                    Inscriptions prochainement
                  </span>
                )}

                <span className="text-xs font-medium text-gray-500">
                  Événement {event.map_type === 'geographic' ? 'en plein air' : 'en intérieur / salle'}
                </span>
              </div>

              {/* Sold out full-width alert banner */}
              {isSoldOut && (
                <div className="p-4 rounded-2xl bg-amber-50 border border-amber-300 text-amber-900 flex items-start sm:items-center gap-3 shadow-xs">
                  <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5 sm:mt-0" />
                  <div className="text-sm font-semibold">
                    Cet événement est actuellement complet ! Tous les emplacements disponibles ont été réservés. Vous pouvez néanmoins consulter le plan interactif.
                  </div>
                </div>
              )}

              {/* Title */}
              <h1 className="text-2xl sm:text-4xl font-extrabold text-gray-900 tracking-tight leading-tight">
                {event.title}
              </h1>

              {/* Quick Info Badges */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                <div className="flex items-center gap-3 p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80">
                  <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0">
                    <Calendar className="w-5 h-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      Date de l'événement
                    </div>
                    <div className="text-sm font-bold text-gray-900 capitalize truncate">
                      {formatDateRange(event.start_date, event.end_date)}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80">
                  <div className="w-10 h-10 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center shrink-0">
                    <MapPin className="w-5 h-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      Lieu & Adresse
                    </div>
                    <div className="text-sm font-bold text-gray-900 truncate" title={event.location_address || 'Adresse à préciser'}>
                      {event.location_address || 'Lieu communiqué par l\'organisateur'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Spots availability & Price Banner */}
              <div className="p-4 sm:p-5 rounded-2xl bg-emerald-50/70 border border-emerald-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="text-xs font-semibold text-emerald-800 uppercase tracking-wider flex items-center gap-1.5">
                    <Tag className="w-3.5 h-3.5" />
                    <span>Tarif exposant</span>
                  </div>
                  <div className="text-2xl font-black text-emerald-950">
                    {priceDisplay} &euro;
                    <span className="text-sm font-semibold text-emerald-800 ml-1">/ mètre linéaire</span>
                  </div>
                </div>

                <div className="text-left sm:text-right w-full sm:w-auto">
                  <div className="text-xs font-semibold text-emerald-900">
                    {hasConfiguredSpots ? (
                      `${availableSpots} place${availableSpots > 1 ? 's' : ''} disponible${availableSpots > 1 ? 's' : ''} sur ${totalSpots}`
                    ) : (
                      'Plan en cours de préparation'
                    )}
                  </div>
                  {hasConfiguredSpots && (
                    <div className="w-full sm:w-44 bg-emerald-200/80 h-2 rounded-full mt-1.5 overflow-hidden">
                      <div
                        className="bg-emerald-600 h-full rounded-full transition-all duration-500"
                        style={{ width: `${occupancyPercent}%` }}
                      />
                    </div>
                  )}
                </div>
              </div>

              {/* Short summary */}
              {event.description && (
                <p className="text-sm sm:text-base text-gray-600 line-clamp-3 leading-relaxed">
                  {event.description}
                </p>
              )}
            </div>

            {/* Main Action Button */}
            <div className="pt-2">
              <button
                type="button"
                onClick={onNavigateToMap}
                className={`w-full py-4 px-6 text-white text-base sm:text-lg font-bold rounded-2xl shadow-md hover:shadow-lg transition transform hover:-translate-y-0.5 flex items-center justify-center gap-3 cursor-pointer group ${
                  isSoldOut
                    ? 'bg-gradient-to-r from-amber-600 to-amber-700 hover:from-amber-700 hover:to-amber-800'
                    : 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700'
                }`}
              >
                <MapIcon className="w-5 h-5 group-hover:rotate-12 transition-transform" />
                <span>
                  {isSoldOut
                    ? 'Consulter le plan (Complet)'
                    : !hasConfiguredSpots
                    ? 'Consulter le plan du vide-grenier'
                    : 'Consulter le plan & Réserver mes emplacements'}
                </span>
                <ChevronRight className="w-5 h-5 ml-auto sm:ml-0" />
              </button>
              <p className="text-xs text-center text-gray-500 mt-2">
                Sélectionnez vos stands directement sur la carte interactive &bull; Paiement sécurisé
              </p>
            </div>
          </div>
        </section>

        {/* PRACTICAL TIMETABLE & DETAILS GRID */}
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-emerald-600" />
            <h2 className="text-xl font-bold text-gray-900">Horaires et modalités pratiques</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Installation exposants */}
            <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-xs space-y-2">
              <div className="w-10 h-10 rounded-xl bg-orange-100 text-orange-700 flex items-center justify-center font-bold">
                <Clock className="w-5 h-5" />
              </div>
              <h3 className="font-bold text-gray-900 text-sm">Installation Exposants</h3>
              <p className="text-xl font-extrabold text-orange-600">
                {event.setup_start_time || '06:00'} &ndash; {event.setup_end_time || '08:00'}
              </p>
              <p className="text-xs text-gray-500 leading-relaxed">
                Accueil et placement des exposants. Présentation obligatoire de votre attestation.
              </p>
            </div>

            {/* Ouverture au public */}
            <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-xs space-y-2">
              <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold">
                <Sparkles className="w-5 h-5" />
              </div>
              <h3 className="font-bold text-gray-900 text-sm">Ouverture au Public</h3>
              <p className="text-xl font-extrabold text-emerald-600">
                {event.public_start_time || '08:00'} &ndash; {event.public_end_time || '18:00'}
              </p>
              <p className="text-xs text-gray-500 leading-relaxed">
                Entrée libre et gratuite pour tous les visiteurs et chineurs.
              </p>
            </div>

            {/* Lieu & Itinéraire */}
            <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-xs space-y-2">
              <div className="w-10 h-10 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center font-bold">
                <MapPin className="w-5 h-5" />
              </div>
              <h3 className="font-bold text-gray-900 text-sm">Lieu de l'événement</h3>
              <p className="text-sm font-semibold text-gray-900 line-clamp-2">
                {event.location_address || 'Consultez la carte officielle'}
              </p>
              {event.location_address && (
                <a
                  href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
                    event.location_address
                  )}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800 transition"
                >
                  <span>Itinéraire Google Maps</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>

            {/* Tarif & Règlementation */}
            <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-xs space-y-2">
              <div className="w-10 h-10 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center font-bold">
                <Tag className="w-5 h-5" />
              </div>
              <h3 className="font-bold text-gray-900 text-sm">Tarif au Mètre</h3>
              <p className="text-xl font-extrabold text-purple-600">
                {priceDisplay} &euro; / mètre
              </p>
              <p className="text-xs text-gray-500 leading-relaxed">
                Règlement conforme à l'article L. 310-2 du Code de commerce.
              </p>
            </div>
          </div>
        </section>

        {/* COMMODITÉS ET SERVICES */}
        <section className="bg-white rounded-3xl border border-gray-200 p-6 sm:p-8 shadow-xs space-y-6">
          <div className="flex items-center gap-2">
            <Coffee className="w-5 h-5 text-emerald-600" />
            <h2 className="text-xl font-bold text-gray-900">Services &amp; commodités sur place</h2>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
            <div className="p-4 rounded-2xl bg-slate-50 border border-gray-200/80 flex flex-col items-center text-center space-y-2">
              <div className="w-12 h-12 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center">
                <Coffee className="w-6 h-6" />
              </div>
              <div className="font-bold text-sm text-gray-900">Buvette &amp; Café</div>
              <div className="text-xs text-gray-500">Boissons fraîches et café chaud dès l'aube</div>
            </div>

            <div className="p-4 rounded-2xl bg-slate-50 border border-gray-200/80 flex flex-col items-center text-center space-y-2">
              <div className="w-12 h-12 rounded-xl bg-red-100 text-red-700 flex items-center justify-center">
                <Utensils className="w-6 h-6" />
              </div>
              <div className="font-bold text-sm text-gray-900">Restauration</div>
              <div className="text-xs text-gray-500">Sandwiches, frites &amp; crêpes sur place</div>
            </div>

            <div className="p-4 rounded-2xl bg-slate-50 border border-gray-200/80 flex flex-col items-center text-center space-y-2">
              <div className="w-12 h-12 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <div className="font-bold text-sm text-gray-900">Sanitaires</div>
              <div className="text-xs text-gray-500">Toilettes publiques accessibles sur le site</div>
            </div>

            <div className="p-4 rounded-2xl bg-slate-50 border border-gray-200/80 flex flex-col items-center text-center space-y-2">
              <div className="w-12 h-12 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center">
                <Car className="w-6 h-6" />
              </div>
              <div className="font-bold text-sm text-gray-900">Parking</div>
              <div className="text-xs text-gray-500">Stationnement à proximité immédiate</div>
            </div>

            <div className="p-4 rounded-2xl bg-slate-50 border border-gray-200/80 flex flex-col items-center text-center space-y-2 col-span-2 sm:col-span-1">
              <div className="w-12 h-12 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center">
                <Accessibility className="w-6 h-6" />
              </div>
              <div className="font-bold text-sm text-gray-900">Accès PMR</div>
              <div className="text-xs text-gray-500">Allées et cheminements adaptés</div>
            </div>
          </div>
        </section>

        {/* DESCRIPTION & RÈGLEMENT */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Description complète */}
          <div className="lg:col-span-7 bg-white rounded-3xl border border-gray-200 p-6 sm:p-8 shadow-xs space-y-4">
            <div className="flex items-center gap-2">
              <Info className="w-5 h-5 text-emerald-600" />
              <h2 className="text-xl font-bold text-gray-900">À propos de l'événement</h2>
            </div>
            <div className="text-gray-700 text-sm sm:text-base leading-relaxed whitespace-pre-line">
              {event.description || "Aucune description complémentaire renseignée pour cet événement."}
            </div>
          </div>

          {/* Règlement & Contact Organisateur */}
          <div className="lg:col-span-5 space-y-6">
            <div className="bg-white rounded-3xl border border-gray-200 p-6 sm:p-8 shadow-xs space-y-4">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-emerald-600" />
                <h2 className="text-xl font-bold text-gray-900">Consignes &amp; Règlement</h2>
              </div>
              <div className="text-xs sm:text-sm text-gray-600 leading-relaxed whitespace-pre-line bg-slate-50 p-4 rounded-xl border border-gray-200/60 max-h-56 overflow-y-auto">
                {event.rules_text ||
                  "Installation des exposants dans le calme aux emplacements attribués. Respect de la propreté du site à votre départ. Vente d'armes et d'objets illicites strictement interdite."}
              </div>
            </div>

            {event.organizer_email && (
              <div className="bg-white rounded-3xl border border-gray-200 p-6 shadow-xs flex items-center justify-between gap-4">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0">
                    <Mail className="w-5 h-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-gray-500">Contact Organisateur</div>
                    <div className="text-sm font-bold text-gray-900 truncate">
                      {event.organizer_email}
                    </div>
                  </div>
                </div>
                <a
                  href={`mailto:${event.organizer_email}`}
                  className="px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-gray-800 text-xs font-semibold transition shrink-0"
                >
                  Écrire
                </a>
              </div>
            )}
          </div>
        </section>
      </main>

      {/* STICKY BOTTOM ACTION BAR (MOBILE ONLY) */}
      <div className="fixed bottom-0 inset-x-0 bg-white/95 backdrop-blur-md border-t border-gray-200 p-4 sm:hidden z-40 flex items-center justify-between gap-4 shadow-lg">
        <div>
          <div className="text-xs font-semibold text-gray-500">Tarif stand</div>
          <div className="text-lg font-black text-emerald-700">
            {priceDisplay} &euro;
            <span className="text-xs font-normal text-gray-500"> / m</span>
          </div>
        </div>

        <button
          type="button"
          onClick={onNavigateToMap}
          className={`flex-1 py-3 px-4 text-white font-bold text-sm rounded-xl shadow-md flex items-center justify-center gap-2 transition ${
            isSoldOut ? 'bg-amber-600 hover:bg-amber-700' : 'bg-emerald-600 hover:bg-emerald-700'
          }`}
        >
          <MapIcon className="w-4 h-4" />
          <span>{isSoldOut ? 'Voir le plan (Complet)' : 'Voir le plan & Réserver'}</span>
        </button>
      </div>

      {/* POSTER LIGHTBOX MODAL */}
      {lightboxOpen && posterUrl && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setLightboxOpen(false)}
        >
          <div
            className="relative max-w-4xl max-h-[90vh] bg-transparent flex items-center justify-center"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              onClick={() => setLightboxOpen(false)}
              className="absolute -top-12 right-0 bg-white/20 hover:bg-white/40 text-white p-2 rounded-full backdrop-blur-md transition"
              aria-label="Fermer la prévisualisation"
            >
              <X className="w-6 h-6" />
            </button>
            <img
              src={posterUrl}
              alt={`Affiche - ${event.title}`}
              onError={() => {
                setPosterLoadError(true);
                setLightboxOpen(false);
              }}
              className="max-h-[85vh] max-w-full rounded-2xl shadow-2xl object-contain border border-white/20"
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default EventShowcasePage;

