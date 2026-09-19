import React, { useState, useEffect, useMemo } from 'react';
import {
  Banknote,
  Receipt,
  Gift,
  CheckCircle2,
  AlertCircle,
  PlusCircle,
  RefreshCw,
  Tag,
  Phone,
  Mail,
  FileText,
  Search,
} from 'lucide-react';
import { EventModel } from '../../types/event';
import { AdminOrder, DashboardStats, OfflineBookingPayload } from '../../types/order';
import { SpotFeature } from '../../types/spot';
import { fetchSpots, createManualBooking, getAdminAttestationPdfUrl, ApiError } from '../../lib/api';

interface GuichetTabProps {
  event: EventModel;
  orders: AdminOrder[];
  stats: DashboardStats | null;
  onBookingCreated: (orderNumber: string) => void;
  renderPaymentBadge: (method: string, isOffline: boolean, ref?: string | null) => React.ReactNode;
  formatDate: (dateStr?: string | null) => string;
}

export const GuichetTab: React.FC<GuichetTabProps> = ({
  event,
  orders,
  stats,
  onBookingCreated,
  renderPaymentBadge,
  formatDate,
}) => {
  // Available spots
  const [availableSpots, setAvailableSpots] = useState<SpotFeature[]>([]);
  const [loadingSpots, setLoadingSpots] = useState<boolean>(false);
  const [selectedSpotIds, setSelectedSpotIds] = useState<string[]>([]);

  // Form fields
  const [firstName, setFirstName] = useState<string>('');
  const [lastName, setLastName] = useState<string>('');
  const [phone, setPhone] = useState<string>('');
  const [email, setEmail] = useState<string>('');
  const [streetAddress, setStreetAddress] = useState<string>('');
  const [postalCode, setPostalCode] = useState<string>('');
  const [city, setCity] = useState<string>('');
  const [paymentMethod, setPaymentMethod] = useState<'cash' | 'check' | 'other'>('cash');
  const [offlineRef, setOfflineRef] = useState<string>('');
  const [adminNotes, setAdminNotes] = useState<string>('');
  const [customPrice, setCustomPrice] = useState<string>('');

  // Local spot and registry search filters
  const [spotFilterQuery, setSpotFilterQuery] = useState<string>('');
  const [searchOfflineQuery, setSearchOfflineQuery] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [successOrderNumber, setSuccessOrderNumber] = useState<string | null>(null);

  const isEventCancelled =
    event.status === 'archived' || (event as any).status === 'cancelled';

  const loadAvailableSpots = async () => {
    setLoadingSpots(true);
    try {
      const allSpots = await fetchSpots(event.id);
      // Keep only spots that are available (status == 'available')
      const available = (allSpots.features || []).filter(
        (s) => !s.properties.status || s.properties.status === 'available'
      );
      setAvailableSpots(available);
    } catch {
      // ignore
    } finally {
      setLoadingSpots(false);
    }
  };

  useEffect(() => {
    loadAvailableSpots();
  }, [event.id]);

  const toggleSpot = (spotId: string) => {
    setSelectedSpotIds((prev) =>
      prev.includes(spotId) ? prev.filter((id) => id !== spotId) : [...prev, spotId]
    );
  };

  const selectedSpots = useMemo(() => {
    return availableSpots.filter((s) => selectedSpotIds.includes(s.id));
  }, [availableSpots, selectedSpotIds]);

  const totalLinearMeters = useMemo(() => {
    return selectedSpots.reduce((acc, s) => acc + (s.properties.linear_meters || 0), 0);
  }, [selectedSpots]);

  const autoCalculatedPrice = useMemo(() => {
    const pricePerMeter = (event.price_per_meter_cents || 0) / 100;
    return totalLinearMeters * pricePerMeter;
  }, [totalLinearMeters, event.price_per_meter_cents]);

  const finalPrice = useMemo(() => {
    if (customPrice.trim() !== '') {
      const parsed = parseFloat(customPrice);
      return isNaN(parsed) ? autoCalculatedPrice : Math.max(0, parsed);
    }
    return autoCalculatedPrice;
  }, [customPrice, autoCalculatedPrice]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (isEventCancelled) {
      setFormError("L'événement est archivé ou annulé. Les inscriptions sont closes.");
      return;
    }

    if (selectedSpotIds.length === 0) {
      setFormError('Veuillez sélectionner au moins un stand disponible.');
      return;
    }
    if (!firstName.trim() || !lastName.trim()) {
      setFormError("Le prénom et le nom de l'exposant sont obligatoires.");
      return;
    }
    if (!phone.trim()) {
      setFormError("Le numéro de téléphone est obligatoire pour l'émargement et la sécurité.");
      return;
    }
    if (paymentMethod === 'check' && !offlineRef.trim()) {
      setFormError('Veuillez renseigner le numéro du chèque pour le suivi comptable.');
      return;
    }
    if (customPrice.trim() !== '') {
      const parsed = parseFloat(customPrice);
      if (isNaN(parsed) || parsed < 0) {
        setFormError('Le tarif personnalisé doit être un nombre positif ou nul.');
        return;
      }
    }

    setSubmitting(true);
    try {
      const payload: OfflineBookingPayload = {
        spot_ids: selectedSpotIds,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        phone: phone.trim(),
        email: email.trim() || undefined,
        street_address: streetAddress.trim() || undefined,
        postal_code: postalCode.trim() || undefined,
        city: city.trim() || undefined,
        payment_method: paymentMethod,
        offline_payment_reference: offlineRef.trim() || undefined,
        admin_notes: adminNotes.trim() || undefined,
        custom_price_cents:
          customPrice.trim() !== '' ? Math.round(finalPrice * 100) : undefined,
      };

      const res = await createManualBooking(event.id, payload);
      setSuccessOrderNumber(res.order_number);
      onBookingCreated(res.order_number);

      // Reset form
      setSelectedSpotIds([]);
      setFirstName('');
      setLastName('');
      setPhone('');
      setEmail('');
      setStreetAddress('');
      setPostalCode('');
      setCity('');
      setOfflineRef('');
      setAdminNotes('');
      setCustomPrice('');
      await loadAvailableSpots();
    } catch (err: unknown) {
      if (err instanceof ApiError || (err && typeof err === 'object' && 'detail' in err)) {
        const detail = (err as any).detail;
        if (typeof detail === 'string') {
          setFormError(detail);
        } else if (Array.isArray(detail)) {
          setFormError(
            detail.map((e: any) => e.msg || JSON.stringify(e)).join(', ')
          );
        } else {
          setFormError(JSON.stringify(detail));
        }
      } else if (err instanceof Error) {
        setFormError(err.message);
      } else {
        setFormError("Une erreur est survenue lors de l'enregistrement de l'inscription.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  // Filter offline orders
  const offlineOrders = useMemo(() => {
    return orders.filter((o) => o.is_offline || o.payment_method !== 'stripe');
  }, [orders]);

  const filteredOfflineOrders = useMemo(() => {
    if (!searchOfflineQuery.trim()) return offlineOrders;
    const q = searchOfflineQuery.toLowerCase();
    return offlineOrders.filter(
      (o) =>
        o.full_name?.toLowerCase().includes(q) ||
        o.order_number?.toLowerCase().includes(q) ||
        (o.spot_labels || []).some((l) => l.toLowerCase().includes(q))
    );
  }, [offlineOrders, searchOfflineQuery]);

  return (
    <div className="space-y-6">
      {/* Financial Summary Cards for Walk-in Desk */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-amber-700">
              Espèces encaissées
            </span>
            <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
              <Banknote className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-black text-amber-900">
              {(stats?.offline_cash_revenue ?? 0).toFixed(2)} €
            </div>
            <div className="text-xs text-gray-500 mt-1">Caisse physique sur place</div>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-700">
              Chèques reçus
            </span>
            <div className="w-8 h-8 rounded-lg bg-slate-50 text-slate-600 flex items-center justify-center">
              <Receipt className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-black text-slate-900">
              {(stats?.offline_check_revenue ?? 0).toFixed(2)} €
            </div>
            <div className="text-xs text-gray-500 mt-1">À remettre en banque</div>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-indigo-700">
              Inscriptions au guichet
            </span>
            <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <PlusCircle className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-black text-indigo-900">
              {stats?.offline_orders_count ?? 0}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              Total des règlements manuels sur place
            </div>
          </div>
        </div>
      </div>

      {/* Main Registration Box */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Form */}
        <div className="lg:col-span-7 bg-white rounded-2xl border border-gray-200 shadow-sm p-6 space-y-5">
          <div className="flex items-center justify-between border-b border-gray-100 pb-4">
            <div>
              <h3 className="text-lg font-bold text-gray-900">Saisie d'un Exposant sur Place</h3>
              <p className="text-xs text-gray-500 mt-0.5">
                Enregistrement rapide sans obligation d'adresse e-mail.
              </p>
            </div>
            <button
              type="button"
              onClick={loadAvailableSpots}
              className="p-1.5 text-gray-500 hover:text-gray-900 rounded-lg hover:bg-gray-100 transition"
              title="Rafraîchir les stands disponibles"
            >
              <RefreshCw className={`w-4 h-4 ${loadingSpots ? 'animate-spin text-emerald-600' : ''}`} />
            </button>
          </div>

          {formError && (
            <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{formError}</span>
            </div>
          )}

          {successOrderNumber && (
            <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-xs flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>
                  Inscription <strong>n° {successOrderNumber}</strong> enregistrée avec succès !
                </span>
              </div>
              <button
                type="button"
                onClick={() => setSuccessOrderNumber(null)}
                className="text-emerald-700 font-bold hover:underline"
              >
                Fermer
              </button>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* 1. Spot Selection */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-gray-700 mb-1.5 flex items-center justify-between">
                <span>1. Choisir le(s) stand(s) disponible(s) *</span>
                <span className="text-[11px] text-gray-400 font-normal">
                  {selectedSpots.length} sélectionné(s) &bull; {totalLinearMeters.toFixed(1)} m
                </span>
              </label>

              {/* Spot label filter */}
              {availableSpots.length > 6 && (
                <div className="mb-2 relative">
                  <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="Filtrer les stands disponibles (ex: A-1)..."
                    value={spotFilterQuery}
                    onChange={(e) => setSpotFilterQuery(e.target.value)}
                    className="w-full pl-8 pr-3 py-1 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:bg-white focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              )}

              {loadingSpots ? (
                <div className="py-4 text-center text-xs text-gray-400">
                  <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-1 text-emerald-600" />
                  <span>Chargement des stands libres...</span>
                </div>
              ) : availableSpots.length === 0 ? (
                <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-800 text-xs text-center">
                  Aucun stand disponible pour le moment (tous les emplacements sont réservés).
                </div>
              ) : (
                <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto p-2.5 bg-gray-50 border border-gray-200 rounded-xl">
                  {availableSpots
                    .filter((spot) =>
                      spot.properties.label.toLowerCase().includes(spotFilterQuery.toLowerCase())
                    )
                    .map((spot) => {
                      const isSelected = selectedSpotIds.includes(spot.id);
                      return (
                        <button
                          type="button"
                          key={spot.id}
                          onClick={() => toggleSpot(spot.id)}
                          className={`px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1 ${
                            isSelected
                              ? 'bg-emerald-600 text-white shadow-xs'
                              : 'bg-white text-gray-700 border border-gray-200 hover:border-emerald-300'
                          }`}
                        >
                          <Tag className="w-3 h-3" />
                          <span>{spot.properties.label}</span>
                          <span className="opacity-75 text-[10px]">
                            ({spot.properties.linear_meters}m)
                          </span>
                        </button>
                      );
                    })}
                </div>
              )}
            </div>

            {/* 2. Exhibitor Identity */}
            <div className="pt-2 border-t border-gray-100">
              <label className="block text-xs font-bold uppercase tracking-wider text-gray-700 mb-2">
                2. Identité de l'exposant
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <input
                    type="text"
                    placeholder="Prénom *"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    required
                    className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs sm:text-sm focus:bg-white focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
                <div>
                  <input
                    type="text"
                    placeholder="Nom *"
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    required
                    className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs sm:text-sm focus:bg-white focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
                <div className="relative">
                  <Phone className="w-3.5 h-3.5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="tel"
                    placeholder="Téléphone portable *"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    required
                    className="w-full pl-8 pr-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs sm:text-sm focus:bg-white focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
                <div className="relative">
                  <Mail className="w-3.5 h-3.5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="email"
                    placeholder="Adresse e-mail (facultative)"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full pl-8 pr-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs sm:text-sm focus:bg-white focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-3">
                <input
                  type="text"
                  placeholder="Rue / Adresse"
                  value={streetAddress}
                  onChange={(e) => setStreetAddress(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:ring-2 focus:ring-emerald-500"
                />
                <input
                  type="text"
                  placeholder="Code Postal"
                  value={postalCode}
                  onChange={(e) => setPostalCode(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:ring-2 focus:ring-emerald-500"
                />
                <input
                  type="text"
                  placeholder="Ville"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:ring-2 focus:ring-emerald-500"
                />
              </div>
            </div>

            {/* 3. Payment Method & Amount */}
            <div className="pt-2 border-t border-gray-100 space-y-3">
              <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
                3. Règlement sur place
              </label>

              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => setPaymentMethod('cash')}
                  className={`p-2.5 rounded-xl border text-xs font-bold flex flex-col items-center gap-1 transition ${
                    paymentMethod === 'cash'
                      ? 'border-amber-500 bg-amber-50 text-amber-900 shadow-sm'
                      : 'border-gray-200 bg-gray-50 text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <Banknote className="w-4 h-4 text-amber-600" />
                  <span>Espèces</span>
                </button>

                <button
                  type="button"
                  onClick={() => setPaymentMethod('check')}
                  className={`p-2.5 rounded-xl border text-xs font-bold flex flex-col items-center gap-1 transition ${
                    paymentMethod === 'check'
                      ? 'border-slate-500 bg-slate-100 text-slate-900 shadow-sm'
                      : 'border-gray-200 bg-gray-50 text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <Receipt className="w-4 h-4 text-slate-600" />
                  <span>Chèque</span>
                </button>

                <button
                  type="button"
                  onClick={() => setPaymentMethod('other')}
                  className={`p-2.5 rounded-xl border text-xs font-bold flex flex-col items-center gap-1 transition ${
                    paymentMethod === 'other'
                      ? 'border-purple-500 bg-purple-50 text-purple-900 shadow-sm'
                      : 'border-gray-200 bg-gray-50 text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <Gift className="w-4 h-4 text-purple-600" />
                  <span>Gratuité / Autre</span>
                </button>
              </div>

              {paymentMethod === 'check' && (
                <div>
                  <input
                    type="text"
                    placeholder="Numéro de chèque / Banque émettrice *"
                    value={offlineRef}
                    onChange={(e) => setOfflineRef(e.target.value)}
                    required
                    className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs sm:text-sm focus:bg-white focus:ring-2 focus:ring-slate-500"
                  />
                </div>
              )}

              {paymentMethod === 'other' && (
                <div>
                  <input
                    type="text"
                    placeholder="Motif de gratuité ou précision (ex: Bénévole)"
                    value={offlineRef}
                    onChange={(e) => setOfflineRef(e.target.value)}
                    className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs sm:text-sm focus:bg-white focus:ring-2 focus:ring-purple-500"
                  />
                </div>
              )}

              {/* Price summary & Custom override */}
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-xl border border-gray-200">
                <div>
                  <div className="text-xs text-gray-500">Montant calculé</div>
                  <div className="text-base font-extrabold text-gray-900">
                    {autoCalculatedPrice.toFixed(2)} €
                  </div>
                </div>
                <div className="text-right">
                  <label className="block text-[11px] text-gray-500">Tarif spécial (€)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="0"
                    placeholder={autoCalculatedPrice.toFixed(2)}
                    value={customPrice}
                    onChange={(e) => setCustomPrice(e.target.value)}
                    className="w-24 text-right px-2 py-1 bg-white border border-gray-300 rounded-lg text-xs font-bold focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              </div>

              {/* 4. Internal Admin Notes */}
              <div className="pt-2 border-t border-gray-100 space-y-1.5">
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
                  4. Notes internes (optionnel)
                </label>
                <textarea
                  value={adminNotes}
                  onChange={(e) => setAdminNotes(e.target.value)}
                  placeholder="Ex. Reçu pièce d'identité en main propre, stand accordé par le président..."
                  rows={2}
                  className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:ring-2 focus:ring-emerald-500"
                />
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={submitting || selectedSpotIds.length === 0 || isEventCancelled}
              className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-bold text-sm shadow-sm transition disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {submitting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Enregistrement en cours...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>
                    {isEventCancelled
                      ? 'Inscriptions closes (Événement annulé/archivé)'
                      : `Valider et Encaisser (${finalPrice.toFixed(2)} €)`}
                  </span>
                </>
              )}
            </button>
          </form>
        </div>

        {/* Right Column: Offline Registrations Log */}
        <div className="lg:col-span-5 bg-white rounded-2xl border border-gray-200 shadow-sm p-6 space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <div>
                <h4 className="font-bold text-gray-900 text-sm">Registre du Guichet</h4>
                <p className="text-xs text-gray-500">
                  {offlineOrders.length} inscription(s) hors-ligne
                </p>
              </div>
              <div className="relative w-44">
                <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Filtrer nom..."
                  value={searchOfflineQuery}
                  onChange={(e) => setSearchOfflineQuery(e.target.value)}
                  className="w-full pl-8 pr-2.5 py-1 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:bg-white focus:ring-2 focus:ring-emerald-500"
                />
              </div>
            </div>

            <div className="space-y-2 max-h-[460px] overflow-y-auto pr-1">
              {filteredOfflineOrders.length === 0 ? (
                <div className="py-12 text-center text-gray-400 text-xs">
                  Aucune inscription guichet enregistrée pour le moment.
                </div>
              ) : (
                filteredOfflineOrders.map((order) => (
                  <div
                    key={order.id}
                    className="p-3 bg-gray-50 rounded-xl border border-gray-200/80 hover:border-gray-300 transition flex items-center justify-between gap-3 text-xs"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-1.5">
                        <span className="font-bold text-gray-900">{order.full_name}</span>
                        <span className="font-mono text-[10px] text-gray-400">
                          {order.order_number}
                        </span>
                        <span className="text-[10px] text-gray-400 font-medium">
                          · {formatDate(order.created_at)}
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-1 text-gray-500 text-[11px]">
                        <span>Stands :</span>
                        {(order.spot_labels || []).map((lbl) => (
                          <span
                            key={lbl}
                            className="px-1.5 py-0.5 bg-emerald-100 text-emerald-800 font-extrabold rounded-md text-[10px]"
                          >
                            {lbl}
                          </span>
                        ))}
                      </div>
                      <div>
                        {renderPaymentBadge(order.payment_method, true, order.offline_payment_reference)}
                      </div>
                    </div>

                    <div className="text-right flex flex-col items-end gap-1.5 shrink-0">
                      <span className="font-extrabold text-gray-900 text-sm">
                        {order.total_price.toFixed(2)} €
                      </span>
                      <a
                        href={getAdminAttestationPdfUrl(event.slug || event.id, order.id)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1 text-emerald-700 hover:bg-emerald-50 rounded-md border border-emerald-200 transition"
                        title="Imprimer l'attestation PDF"
                      >
                        <FileText className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="pt-3 border-t border-gray-100 text-[11px] text-gray-400">
            Conforme à l'art. L310-2 du Code de commerce (registre des brocantes).
          </div>
        </div>
      </div>
    </div>
  );
};
