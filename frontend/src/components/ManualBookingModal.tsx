import React, { useState, useEffect } from 'react';
import {
  X,
  Check,
  Banknote,
  Receipt,
  Gift,
  AlertCircle,
  RefreshCw,
  Tag,
  User,
  Phone,
  Mail,
  MapPin,
  FileText,
} from 'lucide-react';
import { SpotFeature } from '../types/spot';
import { EventModel } from '../types/event';
import { fetchSpots, createManualBooking, ApiError } from '../lib/api';
import { OfflineBookingPayload } from '../types/order';

interface ManualBookingModalProps {
  isOpen: boolean;
  event: EventModel;
  preSelectedSpot?: SpotFeature | null;
  onClose: () => void;
  onSuccess: (orderNumber: string) => void;
}

export const ManualBookingModal: React.FC<ManualBookingModalProps> = ({
  isOpen,
  event,
  preSelectedSpot,
  onClose,
  onSuccess,
}) => {
  const [availableSpots, setAvailableSpots] = useState<SpotFeature[]>([]);
  const [selectedSpotIds, setSelectedSpotIds] = useState<string[]>([]);
  const [loadingSpots, setLoadingSpots] = useState<boolean>(false);

  // Form fields
  const [firstName, setFirstName] = useState<string>('');
  const [lastName, setLastName] = useState<string>('');
  const [phone, setPhone] = useState<string>('');
  const [email, setEmail] = useState<string>('');
  const [streetAddress, setStreetAddress] = useState<string>('');
  const [postalCode, setPostalCode] = useState<string>('');
  const [city, setCity] = useState<string>('');
  const [paymentMethod, setPaymentMethod] = useState<'check' | 'cash' | 'other'>('check');
  const [offlineRef, setOfflineRef] = useState<string>('');
  const [adminNotes, setAdminNotes] = useState<string>('');
  const [customPrice, setCustomPrice] = useState<string>('');

  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    setError(null);
    setSubmitting(false);

    // Reset form fields
    setFirstName('');
    setLastName('');
    setPhone('');
    setEmail('');
    setStreetAddress('');
    setPostalCode('');
    setCity('');
    setPaymentMethod('check');
    setOfflineRef('');
    setAdminNotes('');
    setCustomPrice('');

    // If preSelectedSpot is provided
    if (preSelectedSpot) {
      setSelectedSpotIds([preSelectedSpot.id]);
    } else {
      setSelectedSpotIds([]);
    }

    // Load available spots for selection
    const loadSpots = async () => {
      setLoadingSpots(true);
      try {
        const fc = await fetchSpots(event.id);
        const avail = fc.features.filter((f) => f.properties.status === 'available');
        // Ensure preSelectedSpot is in the list even if already selected
        if (preSelectedSpot && !avail.some((f) => f.id === preSelectedSpot.id)) {
          avail.unshift(preSelectedSpot);
        }
        setAvailableSpots(avail);
      } catch {
        // Non-critical, fallback to empty list
      } finally {
        setLoadingSpots(false);
      }
    };

    loadSpots();
  }, [isOpen, event.id, preSelectedSpot]);

  if (!isOpen) return null;

  const selectedSpots = availableSpots.filter((s) => selectedSpotIds.includes(s.id));
  const autoPriceCents = selectedSpots.reduce((sum, s) => sum + s.properties.price_cents, 0);
  const autoPriceEuros = (autoPriceCents / 100).toFixed(2);
  const totalMeters = selectedSpots.reduce((sum, s) => sum + s.properties.linear_meters, 0);

  const toggleSpotSelection = (spotId: string) => {
    if (selectedSpotIds.includes(spotId)) {
      setSelectedSpotIds(selectedSpotIds.filter((id) => id !== spotId));
    } else {
      setSelectedSpotIds([...selectedSpotIds, spotId]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (selectedSpotIds.length === 0) {
      setError('Veuillez sélectionner au moins un stand à réserver.');
      return;
    }

    if (!lastName.trim()) {
      setError('Le nom de l’exposant est obligatoire.');
      return;
    }
    if (!firstName.trim()) {
      setError('Le prénom de l’exposant est obligatoire.');
      return;
    }
    if (!phone.trim()) {
      setError('Le numéro de téléphone est obligatoire.');
      return;
    }

    let parsedCustomPriceCents: number | undefined = undefined;
    if (customPrice.trim()) {
      const sanitized = customPrice.trim().replace(',', '.');
      const parsed = parseFloat(sanitized);
      if (isNaN(parsed) || parsed < 0) {
        setError('Le montant personnalisé doit être un nombre positif ou nul.');
        return;
      }
      parsedCustomPriceCents = Math.round(parsed * 100);
    }

    const payload: OfflineBookingPayload = {
      spot_ids: selectedSpotIds,
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      email: email.trim() ? email.trim() : undefined,
      phone: phone.trim(),
      street_address: streetAddress.trim() ? streetAddress.trim() : undefined,
      postal_code: postalCode.trim() ? postalCode.trim() : undefined,
      city: city.trim() ? city.trim() : undefined,
      payment_method: paymentMethod,
      offline_payment_reference: offlineRef.trim() ? offlineRef.trim() : undefined,
      admin_notes: adminNotes.trim() ? adminNotes.trim() : undefined,
      custom_price_cents: parsedCustomPriceCents,
    };

    setSubmitting(true);
    try {
      const order = await createManualBooking(event.id, payload);
      onSuccess(order.order_number);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (Array.isArray(err.detail)) {
          const msg = err.detail
            .map((item: any) => (typeof item === 'object' && item && item.msg ? item.msg : String(item)))
            .join(', ');
          setError(msg || 'Erreur de validation des données.');
        } else if (typeof err.detail === 'string') {
          setError(err.detail);
        } else if (err.detail && typeof err.detail === 'object') {
          setError(JSON.stringify(err.detail));
        } else {
          setError(err.message || 'Une erreur est survenue.');
        }
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Une erreur inattendue est survenue.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-2xs animate-fade-in"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-gray-100 overflow-hidden flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gray-50/70">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
              Saisie Manuelle Hors-Ligne
            </span>
            <h3 className="text-lg font-bold text-gray-900 mt-1">
              Enregistrer une inscription (Guichet / Hors-ligne)
            </h3>
          </div>
          <button
            onClick={onClose}
            disabled={submitting}
            className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-full transition"
            aria-label="Fermer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Form */}
        <form onSubmit={handleSubmit} className="overflow-y-auto p-6 space-y-6 flex-1">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded-xl flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm">
                <span className="font-bold">Erreur de validation :</span> {error}
              </div>
            </div>
          )}

          {/* Stand Selection */}
          <div className="space-y-3">
            <label className="block text-sm font-bold text-gray-900 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <Tag className="w-4 h-4 text-emerald-600" />
                Emplacement(s) à affecter
              </span>
              <span className="text-xs font-normal text-gray-500">
                {selectedSpotIds.length} stand(s) sélectionné(s) &bull; {totalMeters.toFixed(1)} m
              </span>
            </label>

            {loadingSpots ? (
              <div className="py-4 text-center text-sm text-gray-500 flex items-center justify-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
                Chargement des stands disponibles...
              </div>
            ) : availableSpots.length === 0 ? (
              <div className="p-3 bg-amber-50 border border-amber-200 text-amber-800 text-sm rounded-xl">
                Aucun stand disponible à la réservation dans cet événement.
              </div>
            ) : (
              <div className="flex flex-wrap gap-2 max-h-36 overflow-y-auto p-2 bg-gray-50 rounded-xl border border-gray-200">
                {availableSpots.map((spot) => {
                  const isSelected = selectedSpotIds.includes(spot.id);
                  return (
                    <button
                      key={spot.id}
                      type="button"
                      onClick={() => toggleSpotSelection(spot.id)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
                        isSelected
                          ? 'bg-emerald-600 text-white shadow-xs'
                          : 'bg-white text-gray-700 border border-gray-200 hover:border-emerald-300'
                      }`}
                    >
                      <span>{spot.properties.label}</span>
                      <span className={isSelected ? 'text-emerald-100' : 'text-gray-400'}>
                        ({spot.properties.linear_meters}m - {spot.properties.price.toFixed(2)}€)
                      </span>
                      {isSelected && <Check className="w-3.5 h-3.5 ml-1" />}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Exhibitor Details */}
          <div className="space-y-4 pt-2 border-t border-gray-100">
            <h4 className="text-sm font-bold text-gray-900 flex items-center gap-2">
              <User className="w-4 h-4 text-emerald-600" />
              Identité de l'exposant
            </h4>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Nom <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  placeholder="ex: Dupont"
                  required
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Prénom <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="ex: Jean"
                  required
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1 flex items-center gap-1">
                  <Phone className="w-3.5 h-3.5 text-gray-400" />
                  Téléphone portable <span className="text-red-500">*</span>
                </label>
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="ex: 06 12 34 56 78"
                  required
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1 flex items-center justify-between">
                  <span className="flex items-center gap-1">
                    <Mail className="w-3.5 h-3.5 text-gray-400" />
                    Adresse email
                  </span>
                  <span className="text-[11px] text-gray-400 font-normal">Optionnelle</span>
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="ex: exposant@email.fr"
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1 flex items-center justify-between">
                <span className="flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-gray-400" />
                  Adresse postale
                </span>
                <span className="text-[11px] text-gray-400 font-normal">Optionnelle</span>
              </label>
              <input
                type="text"
                value={streetAddress}
                onChange={(e) => setStreetAddress(e.target.value)}
                placeholder="12 rue de la Paix"
                className="w-full px-3.5 py-2 text-sm rounded-lg border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Code postal</label>
                <input
                  type="text"
                  value={postalCode}
                  onChange={(e) => setPostalCode(e.target.value)}
                  placeholder="35000"
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Ville</label>
                <input
                  type="text"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  placeholder="Rennes"
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>
            </div>
          </div>

          {/* Payment Method */}
          <div className="space-y-4 pt-2 border-t border-gray-100">
            <h4 className="text-sm font-bold text-gray-900 flex items-center gap-2">
              <Receipt className="w-4 h-4 text-emerald-600" />
              Moyen de règlement hors-ligne
            </h4>

            <div className="grid grid-cols-3 gap-3">
              <button
                type="button"
                onClick={() => setPaymentMethod('check')}
                className={`p-3 rounded-xl border text-left flex flex-col justify-between transition ${
                  paymentMethod === 'check'
                    ? 'border-indigo-600 bg-indigo-50/50 text-indigo-900 ring-1 ring-indigo-600'
                    : 'border-gray-200 hover:border-gray-300 text-gray-700 bg-white'
                }`}
              >
                <div className="flex items-center justify-between w-full mb-1">
                  <Receipt className={`w-4 h-4 ${paymentMethod === 'check' ? 'text-indigo-600' : 'text-gray-400'}`} />
                  {paymentMethod === 'check' && <Check className="w-3.5 h-3.5 text-indigo-600" />}
                </div>
                <div className="text-xs font-bold">Chèque</div>
                <div className="text-[10px] text-gray-500">Ordre association</div>
              </button>

              <button
                type="button"
                onClick={() => setPaymentMethod('cash')}
                className={`p-3 rounded-xl border text-left flex flex-col justify-between transition ${
                  paymentMethod === 'cash'
                    ? 'border-amber-600 bg-amber-50/50 text-amber-900 ring-1 ring-amber-600'
                    : 'border-gray-200 hover:border-gray-300 text-gray-700 bg-white'
                }`}
              >
                <div className="flex items-center justify-between w-full mb-1">
                  <Banknote className={`w-4 h-4 ${paymentMethod === 'cash' ? 'text-amber-600' : 'text-gray-400'}`} />
                  {paymentMethod === 'cash' && <Check className="w-3.5 h-3.5 text-amber-600" />}
                </div>
                <div className="text-xs font-bold">Espèces</div>
                <div className="text-[10px] text-gray-500">Dépôt guichet</div>
              </button>

              <button
                type="button"
                onClick={() => setPaymentMethod('other')}
                className={`p-3 rounded-xl border text-left flex flex-col justify-between transition ${
                  paymentMethod === 'other'
                    ? 'border-purple-600 bg-purple-50/50 text-purple-900 ring-1 ring-purple-600'
                    : 'border-gray-200 hover:border-gray-300 text-gray-700 bg-white'
                }`}
              >
                <div className="flex items-center justify-between w-full mb-1">
                  <Gift className={`w-4 h-4 ${paymentMethod === 'other' ? 'text-purple-600' : 'text-gray-400'}`} />
                  {paymentMethod === 'other' && <Check className="w-3.5 h-3.5 text-purple-600" />}
                </div>
                <div className="text-xs font-bold">Autre / Gratuité</div>
                <div className="text-[10px] text-gray-500">Bénévole, guichet</div>
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  {paymentMethod === 'check'
                    ? 'N° de chèque ou référence banque'
                    : 'Référence du paiement (optionnel)'}
                </label>
                <input
                  type="text"
                  value={offlineRef}
                  onChange={(e) => setOfflineRef(e.target.value)}
                  placeholder={paymentMethod === 'check' ? 'ex: CHQ-829103' : 'ex: Reçu #42'}
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1 flex items-center justify-between">
                  <span>Montant perçu (€)</span>
                  <span className="text-[11px] text-gray-400 font-normal">
                    Auto : {autoPriceEuros} €
                  </span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={customPrice}
                  onChange={(e) => setCustomPrice(e.target.value)}
                  placeholder={autoPriceEuros}
                  className="w-full px-3.5 py-2 text-sm rounded-lg border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1 flex items-center gap-1">
                <FileText className="w-3.5 h-3.5 text-gray-400" />
                Notes administrateur internes
              </label>
              <textarea
                rows={2}
                value={adminNotes}
                onChange={(e) => setAdminNotes(e.target.value)}
                placeholder="ex: Remis en main propre par M. Durand lors de la permanence du samedi matin."
                className="w-full px-3.5 py-2 text-sm rounded-lg border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 resize-none"
              />
            </div>
          </div>
        </form>

        {/* Footer Actions */}
        <div className="px-6 py-4 border-t border-gray-100 bg-gray-50 flex items-center justify-between">
          <div>
            <span className="text-xs text-gray-500">Montant total :</span>{' '}
            <span className="text-base font-black text-gray-900">
              {customPrice.trim() ? parseFloat(customPrice || '0').toFixed(2) : autoPriceEuros} €
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-200/70 rounded-lg transition"
            >
              Annuler
            </button>

            <button
              type="button"
              onClick={handleSubmit}
              disabled={submitting || selectedSpotIds.length === 0}
              className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm font-bold rounded-lg shadow-sm transition flex items-center gap-2"
            >
              {submitting && <RefreshCw className="w-4 h-4 animate-spin" />}
              <span>Valider la réservation</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

