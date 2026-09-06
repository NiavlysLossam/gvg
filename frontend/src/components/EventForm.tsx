import React, { useState } from 'react';
import { Calendar, Clock, MapPin, Euro, Mail, FileText, CheckCircle2, AlertCircle } from 'lucide-react';
import { EventCreateInput, EventModel } from '../types/event';
import { createEvent, ApiError } from '../lib/api';

interface EventFormProps {
  onSuccess: (event: EventModel) => void;
}

export const EventForm: React.FC<EventFormProps> = ({ onSuccess }) => {
  const [formData, setFormData] = useState<EventCreateInput>({
    title: '',
    description: '',
    map_type: 'geographic',
    start_date: '',
    end_date: '',
    setup_start_time: '06:00',
    setup_end_time: '08:00',
    public_start_time: '08:00',
    public_end_time: '18:00',
    location_address: '',
    organizer_email: '',
    price_per_meter: 4.0,
    manual_approval_required: false,
    rules_text: '',
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Client-side validations
    if (new Date(formData.end_date) < new Date(formData.start_date)) {
      setError('La date de fin doit être postérieure ou égale à la date de début.');
      return;
    }
    if (formData.price_per_meter <= 0) {
      setError('Le tarif au mètre linéaire doit être strictement supérieur à 0 €.');
      return;
    }

    setLoading(true);
    try {
      const created = await createEvent({
        ...formData,
        start_date: new Date(formData.start_date).toISOString(),
        end_date: new Date(formData.end_date).toISOString(),
      });
      onSuccess(created);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (typeof err.detail === 'string') {
          setError(err.detail);
        } else {
          setError(JSON.stringify(err.detail));
        }
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Une erreur inattendue est survenue.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 md:p-8 space-y-8">
      <div>
        <h2 className="text-xl font-bold text-gray-900">Nouvel Événement</h2>
        <p className="text-sm text-gray-500 mt-1">
          Renseignez les informations de base de votre vide-grenier pour configurer ensuite les emplacements.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-start space-x-3">
          <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <div className="text-sm">{error}</div>
        </div>
      )}

      {/* Titre & Description */}
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1">
            Nom de l'événement <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            required
            value={formData.title}
            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
            placeholder="ex: Vide-Grenier de Printemps"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
          <textarea
            rows={2}
            value={formData.description || ''}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="Quelques détails pratiques ou d'accueil..."
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition"
          />
        </div>
      </div>

      {/* Dates et Horaires */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-gray-100">
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1 flex items-center gap-1.5">
            <Calendar className="w-4 h-4 text-emerald-600" />
            Date et heure de début <span className="text-red-500">*</span>
          </label>
          <input
            type="datetime-local"
            required
            value={formData.start_date}
            onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition"
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
            value={formData.end_date}
            onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1 flex items-center gap-1.5">
            <Clock className="w-4 h-4 text-gray-500" />
            Créneau d'installation des exposants
          </label>
          <div className="grid grid-cols-2 gap-2">
            <input
              type="time"
              value={formData.setup_start_time || ''}
              onChange={(e) => setFormData({ ...formData, setup_start_time: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none text-center"
            />
            <input
              type="time"
              value={formData.setup_end_time || ''}
              onChange={(e) => setFormData({ ...formData, setup_end_time: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none text-center"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1 flex items-center gap-1.5">
            <Clock className="w-4 h-4 text-gray-500" />
            Créneau d'ouverture au public
          </label>
          <div className="grid grid-cols-2 gap-2">
            <input
              type="time"
              value={formData.public_start_time || ''}
              onChange={(e) => setFormData({ ...formData, public_start_time: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none text-center"
            />
            <input
              type="time"
              value={formData.public_end_time || ''}
              onChange={(e) => setFormData({ ...formData, public_end_time: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none text-center"
            />
          </div>
        </div>
      </div>

      {/* Lieu et Tarification */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-gray-100">
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1 flex items-center gap-1.5">
            <MapPin className="w-4 h-4 text-emerald-600" />
            Adresse / Lieu du vide-grenier
          </label>
          <input
            type="text"
            value={formData.location_address || ''}
            onChange={(e) => setFormData({ ...formData, location_address: e.target.value })}
            placeholder="ex: Place de la Mairie, 33000 Bordeaux"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1 flex items-center gap-1.5">
            <Euro className="w-4 h-4 text-emerald-600" />
            Tarif unitaire au mètre linéaire (€ / m) <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <input
              type="number"
              step="0.01"
              min="0.01"
              required
              value={formData.price_per_meter}
              onChange={(e) => setFormData({ ...formData, price_per_meter: parseFloat(e.target.value) || 0 })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition pr-12"
            />
            <div className="absolute inset-y-0 right-0 flex items-center pr-4 pointer-events-none text-gray-400 font-medium">
              € / m
            </div>
          </div>
          <p className="text-xs text-gray-500 mt-1">Exemple : 4.00 € pour 1 mètre linéaire (2m = 8.00 €)</p>
        </div>
      </div>

      {/* Type de fond de plan & Email organisateur */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-gray-100">
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">Type d'environnement</label>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setFormData({ ...formData, map_type: 'geographic' })}
              className={`p-3 rounded-lg border text-left flex flex-col justify-between transition ${
                formData.map_type === 'geographic'
                  ? 'border-emerald-600 bg-emerald-50 text-emerald-900 font-medium ring-2 ring-emerald-500/20'
                  : 'border-gray-200 hover:border-gray-300 bg-white text-gray-700'
              }`}
            >
              <span className="font-semibold text-sm">Extérieur</span>
              <span className="text-xs text-gray-500 mt-1">Satellite OSM / Rues</span>
            </button>

            <button
              type="button"
              onClick={() => setFormData({ ...formData, map_type: 'planar' })}
              className={`p-3 rounded-lg border text-left flex flex-col justify-between transition ${
                formData.map_type === 'planar'
                  ? 'border-emerald-600 bg-emerald-50 text-emerald-900 font-medium ring-2 ring-emerald-500/20'
                  : 'border-gray-200 hover:border-gray-300 bg-white text-gray-700'
              }`}
            >
              <span className="font-semibold text-sm">Intérieur</span>
              <span className="text-xs text-gray-500 mt-1">Salle des fêtes / Image</span>
            </button>
          </div>
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1 flex items-center gap-1.5">
            <Mail className="w-4 h-4 text-emerald-600" />
            Email de contact organisateur
          </label>
          <input
            type="email"
            value={formData.organizer_email || ''}
            onChange={(e) => setFormData({ ...formData, organizer_email: e.target.value })}
            placeholder="organisateur@association.fr"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition"
          />
        </div>
      </div>

      {/* Règlement intérieur */}
      <div className="pt-4 border-t border-gray-100">
        <label className="block text-sm font-medium text-gray-700 mb-1 flex items-center gap-1.5">
          <FileText className="w-4 h-4 text-gray-500" />
          Règlement intérieur (affiché aux exposants lors de l'inscription)
        </label>
        <textarea
          rows={2}
          value={formData.rules_text || ''}
          onChange={(e) => setFormData({ ...formData, rules_text: e.target.value })}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition"
        />
      </div>

      <div className="flex justify-end pt-4 border-t border-gray-100">
        <button
          type="submit"
          disabled={loading}
          className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-lg shadow-sm focus:ring-4 focus:ring-emerald-500/20 transition flex items-center gap-2 disabled:opacity-50"
        >
          {loading ? (
            <span>Enregistrement en cours...</span>
          ) : (
            <>
              <CheckCircle2 className="w-5 h-5" />
              <span>Créer l'événement</span>
            </>
          )}
        </button>
      </div>
    </form>
  );
};

