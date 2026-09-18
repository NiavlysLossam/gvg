import React, { useState, useEffect, useRef } from 'react';
import {
  ArrowLeft,
  Calendar,
  Clock,
  MapPin,
  Euro,
  Mail,
  FileText,
  CheckCircle2,
  AlertCircle,
  ShieldCheck,
  UploadCloud,
  Trash2,
  ExternalLink,
  Save,
  Loader2,
  ImageIcon,
} from 'lucide-react';
import { EventModel, EventStatus, EventUpdateInput } from '../types/event';
import { updateEvent, uploadEventPoster, deleteEventPoster, ApiError } from '../lib/api';

interface EventSettingsPageProps {
  event: EventModel;
  onBack: () => void;
  onSaved: (updatedEvent: EventModel) => void;
  onViewPublic?: (slug: string) => void;
}

function toDateTimeLocalString(isoString?: string | null): string {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return '';
    const pad = (n: number) => n.toString().padStart(2, '0');
    const YYYY = d.getFullYear();
    const MM = pad(d.getMonth() + 1);
    const DD = pad(d.getDate());
    const hh = pad(d.getHours());
    const mm = pad(d.getMinutes());
    return `${YYYY}-${MM}-${DD}T${hh}:${mm}`;
  } catch {
    return '';
  }
}

export const EventSettingsPage: React.FC<EventSettingsPageProps> = ({
  event,
  onBack,
  onSaved,
  onViewPublic,
}) => {
  // General settings state
  const [title, setTitle] = useState(event.title || '');
  const [description, setDescription] = useState(event.description || '');
  const [status, setStatus] = useState<EventStatus>(event.status || 'draft');
  const [startDate, setStartDate] = useState(toDateTimeLocalString(event.start_date));
  const [endDate, setEndDate] = useState(toDateTimeLocalString(event.end_date));
  const [setupStartTime, setSetupStartTime] = useState(event.setup_start_time || '06:00');
  const [setupEndTime, setSetupEndTime] = useState(event.setup_end_time || '08:00');
  const [publicStartTime, setPublicStartTime] = useState(event.public_start_time || '08:00');
  const [publicEndTime, setPublicEndTime] = useState(event.public_end_time || '18:00');
  const [locationAddress, setLocationAddress] = useState(event.location_address || '');
  const [organizerEmail, setOrganizerEmail] = useState(event.organizer_email || '');
  const [pricePerMeter, setPricePerMeter] = useState<number>(
    event.price_per_meter ?? (event.price_per_meter_cents ? event.price_per_meter_cents / 100 : 4.0)
  );
  const [manualApprovalRequired, setManualApprovalRequired] = useState(
    Boolean(event.manual_approval_required)
  );
  const [rulesText, setRulesText] = useState(event.rules_text || '');

  // Poster upload state
  const [posterUrl, setPosterUrl] = useState<string | null>(event.poster_image_url || null);
  const [uploadingPoster, setUploadingPoster] = useState(false);
  const [posterError, setPosterError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Sync state if event prop changes
  useEffect(() => {
    setTitle(event.title || '');
    setDescription(event.description || '');
    setStatus(event.status || 'draft');
    setStartDate(toDateTimeLocalString(event.start_date));
    setEndDate(toDateTimeLocalString(event.end_date));
    setSetupStartTime(event.setup_start_time || '06:00');
    setSetupEndTime(event.setup_end_time || '08:00');
    setPublicStartTime(event.public_start_time || '08:00');
    setPublicEndTime(event.public_end_time || '18:00');
    setLocationAddress(event.location_address || '');
    setOrganizerEmail(event.organizer_email || '');
    setPricePerMeter(
      event.price_per_meter ?? (event.price_per_meter_cents ? event.price_per_meter_cents / 100 : 4.0)
    );
    setManualApprovalRequired(Boolean(event.manual_approval_required));
    setRulesText(event.rules_text || '');
    setPosterUrl(event.poster_image_url || null);
  }, [event]);

  // Form submission state
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const MAX_POSTER_SIZE = 5 * 1024 * 1024; // 5 Mo
  const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/webp'];

  const handlePosterSelected = async (file: File) => {
    if (uploadingPoster) return;
    setPosterError(null);

    // Format check
    if (!ALLOWED_TYPES.includes(file.type)) {
      setPosterError('Format de fichier non supporté. Formats acceptés : PNG, JPEG, WebP.');
      return;
    }

    // Size check <= 5 MB
    if (file.size > MAX_POSTER_SIZE) {
      const sizeMo = (file.size / (1024 * 1024)).toFixed(2);
      setPosterError(
        `L'affiche dépasse la taille maximale autorisée de 5 Mo (taille actuelle : ${sizeMo} Mo). Veuillez choisir une image plus légère.`
      );
      return;
    }

    setUploadingPoster(true);
    try {
      const updated = await uploadEventPoster(event.id, file);
      setPosterUrl(updated.poster_image_url || null);
      onSaved(updated);
      setSuccessMessage('Affiche officielle téléversée et mise à jour avec succès !');
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setPosterError(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
      } else if (err instanceof Error) {
        setPosterError(err.message);
      } else {
        setPosterError("Erreur lors de l'envoi de l'affiche");
      }
    } finally {
      setUploadingPoster(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDeletePoster = async () => {
    if (!posterUrl || uploadingPoster) return;
    if (!window.confirm("Êtes-vous sûr de vouloir supprimer l'affiche officielle de cet événement ?")) {
      return;
    }

    setUploadingPoster(true);
    setPosterError(null);
    try {
      const updated = await deleteEventPoster(event.id);
      setPosterUrl(null);
      onSaved(updated);
      setSuccessMessage("L'affiche officielle a été supprimée.");
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setPosterError(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
      } else if (err instanceof Error) {
        setPosterError(err.message);
      } else {
        setPosterError("Erreur lors de la suppression de l'affiche");
      }
    } finally {
      setUploadingPoster(false);
    }
  };

  const handleGeneralSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    const startD = new Date(startDate);
    const endD = new Date(endDate);

    if (isNaN(startD.getTime()) || isNaN(endD.getTime())) {
      setError('Veuillez renseigner des dates de début et de fin valides.');
      return;
    }

    if (endD < startD) {
      setError('La date de fin doit être postérieure ou égale à la date de début.');
      return;
    }

    if (pricePerMeter <= 0) {
      setError('Le tarif au mètre linéaire doit être strictement supérieur à 0 €.');
      return;
    }

    setSaving(true);
    try {
      const updatePayload: EventUpdateInput = {
        title: title.trim(),
        description: description.trim() || null,
        status,
        start_date: startD.toISOString(),
        end_date: endD.toISOString(),
        setup_start_time: setupStartTime.trim() || null,
        setup_end_time: setupEndTime.trim() || null,
        public_start_time: publicStartTime.trim() || null,
        public_end_time: publicEndTime.trim() || null,
        location_address: locationAddress.trim() || null,
        organizer_email: organizerEmail.trim() || null,
        price_per_meter: pricePerMeter,
        manual_approval_required: manualApprovalRequired,
        rules_text: rulesText.trim() || null,
      };

      const updated = await updateEvent(event.id, updatePayload);
      onSaved(updated);
      setSuccessMessage('Les paramètres de l’événement ont été enregistrés avec succès !');
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Une erreur inattendue est survenue.');
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-8 pb-16 max-w-5xl mx-auto">
      {/* Top Bar with Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-200 pb-5">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            className="p-2 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition"
            title="Retour aux événements"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-gray-900">Paramètres de l'événement</h1>
              <span
                className={`text-xs px-2.5 py-0.5 rounded-full font-semibold ${
                  status === 'published'
                    ? 'bg-emerald-100 text-emerald-800'
                    : status === 'archived'
                    ? 'bg-gray-100 text-gray-700'
                    : 'bg-amber-100 text-amber-800'
                }`}
              >
                {status === 'published' ? 'Publié' : status === 'archived' ? 'Archivé' : 'Brouillon'}
              </span>
            </div>
            <p className="text-sm text-gray-500 mt-0.5">
              Identifiant : <code className="font-mono text-xs">{event.slug}</code>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {onViewPublic && (
            <button
              type="button"
              onClick={() => onViewPublic(event.slug)}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 text-xs font-semibold rounded-lg border border-emerald-200 transition"
              title="Voir la vitrine publique"
            >
              <ExternalLink className="w-4 h-4" />
              <span>Voir la vitrine publique</span>
            </button>
          )}
        </div>
      </div>

      {/* Global Alerts */}
      {successMessage && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 px-4 py-3.5 rounded-xl flex items-center justify-between shadow-xs">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            <p className="text-sm font-semibold">{successMessage}</p>
          </div>
          <button
            type="button"
            onClick={() => setSuccessMessage(null)}
            className="text-xs text-emerald-700 hover:underline font-bold"
          >
            Fermer
          </button>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3.5 rounded-xl flex items-start gap-3 shadow-xs">
          <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <div className="text-sm font-medium">{error}</div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Official Poster Upload */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-xs p-6 space-y-5">
            <div>
              <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
                <ImageIcon className="w-5 h-5 text-emerald-600" />
                <span>Affiche Officielle</span>
              </h2>
              <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                Téléversez l'affiche grand format de l'événement (max 5 Mo, formats JPEG, PNG, WebP). Elle sera mise en avant sur votre vitrine publique.
              </p>
            </div>

            {posterError && (
              <div className="bg-red-50 border border-red-200 text-red-700 p-3 rounded-xl flex items-start gap-2 text-xs">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-red-600" />
                <span>{posterError}</span>
              </div>
            )}

            {/* Poster Preview or Dropzone */}
            {posterUrl ? (
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  if (!uploadingPoster) setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragging(false);
                  if (uploadingPoster) return;
                  if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                    handlePosterSelected(e.dataTransfer.files[0]);
                  }
                }}
                className={`space-y-3 p-2 rounded-xl transition ${
                  isDragging ? 'ring-2 ring-emerald-500 bg-emerald-50/50' : ''
                }`}
              >
                <div className="relative group rounded-xl overflow-hidden border border-gray-200 bg-gray-50 shadow-inner">
                  <img
                    src={posterUrl}
                    alt="Affiche officielle"
                    className="w-full h-72 object-cover object-center transition duration-300 group-hover:scale-105"
                  />
                  {uploadingPoster ? (
                    <div className="absolute inset-0 bg-black/60 flex flex-col items-center justify-center gap-2 text-white">
                      <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
                      <span className="text-xs font-semibold">Téléversement...</span>
                    </div>
                  ) : (
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3">
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={uploadingPoster}
                        className="px-3 py-1.5 bg-white/90 hover:bg-white text-gray-900 text-xs font-semibold rounded-lg shadow-md transition"
                      >
                        Remplacer
                      </button>
                      <button
                        type="button"
                        onClick={handleDeletePoster}
                        disabled={uploadingPoster}
                        className="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-lg shadow-md transition"
                      >
                        Supprimer
                      </button>
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span className="font-medium text-emerald-700">✓ Affiche enregistrée (glissez un fichier pour remplacer)</span>
                  <button
                    type="button"
                    onClick={handleDeletePoster}
                    disabled={uploadingPoster}
                    className="text-red-600 hover:text-red-700 hover:underline flex items-center gap-1 font-semibold"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Supprimer</span>
                  </button>
                </div>
              </div>
            ) : (
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  if (!uploadingPoster) setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragging(false);
                  if (uploadingPoster) return;
                  if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                    handlePosterSelected(e.dataTransfer.files[0]);
                  }
                }}
                className={`border-2 border-dashed rounded-xl p-6 text-center transition flex flex-col items-center justify-center min-h-[220px] ${
                  isDragging
                    ? 'border-emerald-500 bg-emerald-50/50'
                    : 'border-gray-300 hover:border-emerald-400 bg-gray-50/40 hover:bg-emerald-50/20'
                }`}
              >
                {uploadingPoster ? (
                  <div className="flex flex-col items-center gap-2 text-emerald-600">
                    <Loader2 className="w-8 h-8 animate-spin" />
                    <p className="text-xs font-semibold">Téléversement de l'affiche...</p>
                  </div>
                ) : (
                  <>
                    <div className="w-12 h-12 bg-emerald-100 text-emerald-700 rounded-full flex items-center justify-center mb-3">
                      <UploadCloud className="w-6 h-6" />
                    </div>
                    <p className="text-sm font-semibold text-gray-800">
                      Glissez votre affiche ici
                    </p>
                    <p className="text-xs text-gray-500 mt-1 mb-4">
                      PNG, JPEG ou WebP (max 5 Mo)
                    </p>
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg shadow-xs transition"
                    >
                      Sélectionner un fichier
                    </button>
                  </>
                )}
              </div>
            )}

            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  handlePosterSelected(e.target.files[0]);
                }
              }}
            />
          </div>
        </div>

        {/* Right Columns: Metadata & Parameters Form */}
        <div className="lg:col-span-2">
          <form
            onSubmit={handleGeneralSubmit}
            className="bg-white rounded-2xl border border-gray-200 shadow-xs p-6 md:p-8 space-y-6"
          >
            <div>
              <h2 className="text-base font-bold text-gray-900">Renseignements Généraux</h2>
              <p className="text-xs text-gray-500 mt-1">
                Modifiez les dates, horaires, tarifs et informations pratiques de l'événement.
              </p>
            </div>

            {/* Statut de l'événement */}
            <div className="pt-2">
              <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">
                Statut de publication <span className="text-red-500">*</span>
              </label>
              <div className="grid grid-cols-3 gap-3">
                <button
                  type="button"
                  onClick={() => setStatus('draft')}
                  className={`p-3 rounded-xl border text-left transition ${
                    status === 'draft'
                      ? 'border-amber-500 bg-amber-50/50 text-amber-900 ring-2 ring-amber-500/20'
                      : 'border-gray-200 hover:border-gray-300 bg-white text-gray-700'
                  }`}
                >
                  <div className="font-bold text-sm">Brouillon</div>
                  <div className="text-xs text-gray-500 mt-0.5">Invisible du public</div>
                </button>

                <button
                  type="button"
                  onClick={() => setStatus('published')}
                  className={`p-3 rounded-xl border text-left transition ${
                    status === 'published'
                      ? 'border-emerald-600 bg-emerald-50/50 text-emerald-900 ring-2 ring-emerald-500/20'
                      : 'border-gray-200 hover:border-gray-300 bg-white text-gray-700'
                  }`}
                >
                  <div className="font-bold text-sm text-emerald-900">Publié</div>
                  <div className="text-xs text-gray-500 mt-0.5">Visible sur le portail</div>
                </button>

                <button
                  type="button"
                  onClick={() => setStatus('archived')}
                  className={`p-3 rounded-xl border text-left transition ${
                    status === 'archived'
                      ? 'border-gray-500 bg-gray-50 text-gray-900 ring-2 ring-gray-400/20'
                      : 'border-gray-200 hover:border-gray-300 bg-white text-gray-700'
                  }`}
                >
                  <div className="font-bold text-sm">Archivé</div>
                  <div className="text-xs text-gray-500 mt-0.5">Événement passé</div>
                </button>
              </div>
            </div>

            {/* Titre & Description */}
            <div className="space-y-4 pt-4 border-t border-gray-100">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">
                  Nom de l'événement <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  maxLength={255}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="ex: Grand Vide-Grenier de la Madeleine"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none text-sm font-medium transition"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">
                  Description générale
                </label>
                <textarea
                  rows={3}
                  maxLength={5000}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Présentez votre événement, les commodités (restauration, buvette, sanitaires) et les accès..."
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none text-sm transition"
                />
              </div>
            </div>

            {/* Dates et Horaires */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pt-4 border-t border-gray-100">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1 flex items-center gap-1.5">
                  <Calendar className="w-4 h-4 text-emerald-600" />
                  Date et heure de début <span className="text-red-500">*</span>
                </label>
                <input
                  type="datetime-local"
                  required
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none text-sm transition"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1 flex items-center gap-1.5">
                  <Calendar className="w-4 h-4 text-emerald-600" />
                  Date et heure de fin <span className="text-red-500">*</span>
                </label>
                <input
                  type="datetime-local"
                  required
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none text-sm transition"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1 flex items-center gap-1.5">
                  <Clock className="w-4 h-4 text-gray-500" />
                  Horaires d'installation des exposants
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="time"
                    value={setupStartTime}
                    onChange={(e) => setSetupStartTime(e.target.value)}
                    className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none text-center text-sm"
                  />
                  <input
                    type="time"
                    value={setupEndTime}
                    onChange={(e) => setSetupEndTime(e.target.value)}
                    className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none text-center text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1 flex items-center gap-1.5">
                  <Clock className="w-4 h-4 text-gray-500" />
                  Horaires d'ouverture au public
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="time"
                    value={publicStartTime}
                    onChange={(e) => setPublicStartTime(e.target.value)}
                    className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none text-center text-sm"
                  />
                  <input
                    type="time"
                    value={publicEndTime}
                    onChange={(e) => setPublicEndTime(e.target.value)}
                    className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none text-center text-sm"
                  />
                </div>
              </div>
            </div>

            {/* Lieu et Tarification */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pt-4 border-t border-gray-100">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1 flex items-center gap-1.5">
                  <MapPin className="w-4 h-4 text-emerald-600" />
                  Adresse / Lieu physique
                </label>
                <input
                  type="text"
                  maxLength={500}
                  value={locationAddress}
                  onChange={(e) => setLocationAddress(e.target.value)}
                  placeholder="ex: Esplanade des Quinconces, 33000 Bordeaux"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none text-sm transition"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1 flex items-center gap-1.5">
                  <Euro className="w-4 h-4 text-emerald-600" />
                  Tarif au mètre linéaire (€ / m) <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    value={pricePerMeter}
                    onChange={(e) => setPricePerMeter(parseFloat(e.target.value) || 0)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none text-sm font-bold text-emerald-800 pr-12 transition"
                  />
                  <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none text-gray-400 font-medium text-xs">
                    € / m
                  </div>
                </div>
              </div>
            </div>

            {/* Email contact organisateur */}
            <div className="pt-4 border-t border-gray-100">
              <label className="block text-sm font-semibold text-gray-700 mb-1 flex items-center gap-1.5">
                <Mail className="w-4 h-4 text-emerald-600" />
                Email de contact pour les exposants
              </label>
              <input
                type="email"
                maxLength={255}
                value={organizerEmail}
                onChange={(e) => setOrganizerEmail(e.target.value)}
                placeholder="contact@association-organisatrice.fr"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none text-sm transition"
              />
            </div>

            {/* Règlement intérieur */}
            <div className="pt-4 border-t border-gray-100">
              <label className="block text-sm font-semibold text-gray-700 mb-1 flex items-center gap-1.5">
                <FileText className="w-4 h-4 text-gray-500" />
                Règlement intérieur de l'événement
              </label>
              <textarea
                rows={4}
                maxLength={10000}
                value={rulesText}
                onChange={(e) => setRulesText(e.target.value)}
                placeholder="Consignes de sécurité, propreté, restitution des emplacements..."
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none text-sm transition"
              />
            </div>

            {/* Modération manuelle */}
            <div className="pt-4 border-t border-gray-100">
              <label className="flex items-start gap-3 cursor-pointer p-4 rounded-xl border border-gray-200 hover:border-emerald-300 bg-gray-50/50 hover:bg-emerald-50/20 transition">
                <input
                  type="checkbox"
                  checked={manualApprovalRequired}
                  onChange={(e) => setManualApprovalRequired(e.target.checked)}
                  className="w-5 h-5 rounded-md text-emerald-600 border-gray-300 focus:ring-emerald-500 mt-0.5 cursor-pointer"
                />
                <div className="space-y-0.5">
                  <span className="text-sm font-bold text-gray-900 flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-emerald-600" />
                    <span>Modération manuelle des inscriptions</span>
                  </span>
                  <p className="text-xs text-gray-500 leading-relaxed">
                    Si activée, les réservations exposants seront soumises à votre validation manuelle préalable depuis l'onglet Inscriptions.
                  </p>
                </div>
              </label>
            </div>

            {/* Submit Button */}
            <div className="flex items-center justify-end gap-3 pt-6 border-t border-gray-100">
              <button
                type="button"
                onClick={onBack}
                className="px-4 py-2.5 rounded-lg border border-gray-200 text-gray-700 text-sm font-semibold hover:bg-gray-50 transition"
              >
                Annuler
              </button>
              <button
                type="submit"
                disabled={saving}
                className="inline-flex items-center gap-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold rounded-lg shadow-sm focus:ring-4 focus:ring-emerald-500/20 transition disabled:opacity-50"
              >
                {saving ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Enregistrement...</span>
                  </>
                ) : (
                  <>
                    <Save className="w-4 h-4" />
                    <span>Enregistrer les paramètres</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default EventSettingsPage;

