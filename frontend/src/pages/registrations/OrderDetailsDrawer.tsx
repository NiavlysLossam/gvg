import React, { useState, useEffect } from 'react';
import {
  X,
  Save,
  Mail,
  FileText,
  CheckCircle2,
  AlertCircle,
  Lock,
  RefreshCw,
  User,
  CreditCard,
  Send,
  ExternalLink,
} from 'lucide-react';
import { EventModel } from '../../types/event';
import { AdminOrder, OrderEmailLog, getCancellationReasonLabel } from '../../types/order';
import {
  updateAdminOrder,
  resendOrderAttestationEmail,
  fetchOrderEmails,
  getAdminAttestationPdfUrl,
} from '../../lib/api';

interface OrderDetailsDrawerProps {
  event: EventModel;
  order: AdminOrder | null;
  isOpen: boolean;
  onClose: () => void;
  onOrderUpdated: (updatedOrder: AdminOrder) => void;
}

const EMAIL_REGEX = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export const OrderDetailsDrawer: React.FC<OrderDetailsDrawerProps> = ({
  event,
  order,
  isOpen,
  onClose,
  onOrderUpdated,
}) => {
  // Contact Form State
  const [firstName, setFirstName] = useState<string>('');
  const [lastName, setLastName] = useState<string>('');
  const [email, setEmail] = useState<string>('');
  const [phone, setPhone] = useState<string>('');
  const [streetAddress, setStreetAddress] = useState<string>('');
  const [postalCode, setPostalCode] = useState<string>('');
  const [city, setCity] = useState<string>('');

  // Internal Notes State
  const [adminNotes, setAdminNotes] = useState<string>('');

  // UI Status State
  const [savingContact, setSavingContact] = useState<boolean>(false);
  const [contactSuccess, setContactSuccess] = useState<string | null>(null);
  const [contactError, setContactError] = useState<string | null>(null);

  const [savingNotes, setSavingNotes] = useState<boolean>(false);
  const [notesSuccess, setNotesSuccess] = useState<string | null>(null);
  const [notesError, setNotesError] = useState<string | null>(null);

  const [resendingAttestation, setResendingAttestation] = useState<boolean>(false);
  const [resendSuccess, setResendSuccess] = useState<string | null>(null);
  const [resendError, setResendError] = useState<string | null>(null);

  // Email Logs State
  const [emailLogs, setEmailLogs] = useState<OrderEmailLog[]>([]);
  const [loadingLogs, setLoadingLogs] = useState<boolean>(false);
  const [logsError, setLogsError] = useState<string | null>(null);

  // Track current order ID to prevent state wiping on updates
  const prevOrderIdRef = React.useRef<string | null>(null);
  const currentOrderIdRef = React.useRef<string | null>(null);
  currentOrderIdRef.current = order?.id || null;

  // Track timers for cleanup
  const timersRef = React.useRef<number[]>([]);
  const addTimer = (timerId: number) => {
    timersRef.current.push(timerId);
  };

  useEffect(() => {
    return () => {
      timersRef.current.forEach((t) => window.clearTimeout(t));
      timersRef.current = [];
    };
  }, []);

  // Lock body scroll when drawer is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  // Synchronize form when order changes or drawer opens
  useEffect(() => {
    if (!isOpen || !order) {
      prevOrderIdRef.current = null;
      return;
    }

    if (order.id !== prevOrderIdRef.current) {
      prevOrderIdRef.current = order.id;
      setFirstName(order.first_name || '');
      setLastName(order.last_name || '');
      setEmail(order.email || '');
      setPhone(order.phone || '');
      setStreetAddress(order.street_address || '');
      setPostalCode(order.postal_code || '');
      setCity(order.city || '');
      setAdminNotes(order.admin_notes || '');

      setContactSuccess(null);
      setContactError(null);
      setNotesSuccess(null);
      setNotesError(null);
      setResendSuccess(null);
      setResendError(null);

      // Load email audit logs for this order
      loadEmailLogs(order.id);
    }
  }, [order?.id, isOpen]);

  // Handle escape key to close drawer
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const loadEmailLogs = async (orderId: string) => {
    setLoadingLogs(true);
    setLogsError(null);
    try {
      const res = await fetchOrderEmails(event.slug || event.id, orderId);
      if (currentOrderIdRef.current === orderId) {
        setEmailLogs(res.items || []);
      }
    } catch (err: any) {
      if (currentOrderIdRef.current === orderId) {
        setLogsError(err.message || "Erreur lors du chargement de l'historique des e-mails.");
      }
    } finally {
      if (currentOrderIdRef.current === orderId) {
        setLoadingLogs(false);
      }
    }
  };

  if (!isOpen || !order) {
    return null;
  }

  const isConfirmed = order.status === 'confirmed';
  const totalLinearMeters = (order.items || []).reduce(
    (acc, it) => acc + (it.spot_linear_meters || 0),
    0
  );

  // Submit Contact Changes
  const handleSaveContact = async (e: React.FormEvent) => {
    e.preventDefault();
    setContactSuccess(null);
    setContactError(null);

    const trimmedFirstName = firstName.trim();
    const trimmedLastName = lastName.trim();
    const trimmedEmail = email.trim();
    const trimmedPhone = phone.trim();

    if (!trimmedFirstName || !trimmedLastName) {
      setContactError('Le prénom et le nom de famille sont obligatoires.');
      return;
    }

    if (trimmedEmail && !EMAIL_REGEX.test(trimmedEmail)) {
      setContactError("L'adresse e-mail saisie n'a pas un format valide.");
      return;
    }

    const digitsOnly = trimmedPhone.replace(/\D/g, '');
    if (digitsOnly.length < 8 || digitsOnly.length > 15) {
      setContactError('Le numéro de téléphone doit contenir entre 8 et 15 chiffres.');
      return;
    }

    setSavingContact(true);
    try {
      const updated = await updateAdminOrder(event.slug || event.id, order.id, {
        first_name: trimmedFirstName,
        last_name: trimmedLastName,
        email: trimmedEmail || null,
        phone: trimmedPhone,
        street_address: streetAddress.trim() || null,
        postal_code: postalCode.trim() || null,
        city: city.trim() || null,
      });

      onOrderUpdated(updated);
      setContactSuccess('Coordonnées mises à jour avec succès.');
      addTimer(window.setTimeout(() => setContactSuccess(null), 4000));
    } catch (err: any) {
      setContactError(err.message || 'Erreur lors de la mise à jour des coordonnées.');
    } finally {
      setSavingContact(false);
    }
  };

  // Submit Internal Notes Changes
  const handleSaveNotes = async () => {
    setNotesSuccess(null);
    setNotesError(null);
    setSavingNotes(true);

    try {
      const updated = await updateAdminOrder(event.slug || event.id, order.id, {
        admin_notes: adminNotes.trim() || null,
      });

      onOrderUpdated(updated);
      setNotesSuccess('Note interne enregistrée avec succès.');
      addTimer(window.setTimeout(() => setNotesSuccess(null), 4000));
    } catch (err: any) {
      setNotesError(err.message || "Erreur lors de l'enregistrement de la note.");
    } finally {
      setSavingNotes(false);
    }
  };

  // Resend Attestation PDF
  const handleResendAttestation = async () => {
    if (!isConfirmed) return;
    const isFirstNameChanged = firstName.trim() !== (order.first_name || '').trim();
    const isLastNameChanged = lastName.trim() !== (order.last_name || '').trim();
    const isEmailChanged = email.trim().toLowerCase() !== (order.email || '').trim().toLowerCase();

    if (isFirstNameChanged || isLastNameChanged || isEmailChanged) {
      setResendError("Les coordonnées de l'exposant ont été modifiées dans le formulaire. Veuillez d'abord cliquer sur « Enregistrer les coordonnées » avant de renvoyer l'attestation.");
      return;
    }
    if (!order.email || !order.email.trim()) {
      setResendError("L'exposant ne possède pas d'adresse e-mail enregistrée. Veuillez d'abord renseigner et enregistrer un e-mail.");
      return;
    }

    setResendingAttestation(true);
    setResendSuccess(null);
    setResendError(null);

    try {
      const res = await resendOrderAttestationEmail(event.slug || event.id, order.id);
      setResendSuccess(res.message || `Attestation envoyée avec succès à ${res.email}`);
      // Refresh audit logs immediately and after delay so background task result appears
      loadEmailLogs(order.id);
      addTimer(window.setTimeout(() => loadEmailLogs(order.id), 1500));
      addTimer(window.setTimeout(() => loadEmailLogs(order.id), 3500));
      addTimer(window.setTimeout(() => setResendSuccess(null), 5000));
    } catch (err: any) {
      setResendError(err.message || "Erreur lors de l'envoi de l'attestation.");
    } finally {
      setResendingAttestation(false);
    }
  };

  const formatDateTime = (dateStr?: string | null) => {
    if (!dateStr) return '—';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('fr-FR', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden" aria-labelledby="slide-over-title" role="dialog" aria-modal="true">
      {/* Backdrop semi-transparent */}
      <div
        className="fixed inset-0 bg-gray-900/60 backdrop-blur-sm transition-opacity duration-300"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className="fixed inset-y-0 right-0 max-w-xl w-full flex pl-10">
        <div className="w-full bg-white shadow-2xl flex flex-col overflow-hidden transition-transform duration-300 ease-out">
          {/* Header */}
          <div className="px-6 py-5 bg-gradient-to-r from-gray-900 to-gray-800 text-white flex items-center justify-between shadow-md">
            <div>
              <div className="flex items-center gap-2.5">
                <span className="text-xs font-mono font-bold uppercase tracking-wider bg-white/10 px-2 py-0.5 rounded text-emerald-400">
                  {order.order_number}
                </span>
                <span
                  className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full ${
                    order.status === 'confirmed'
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      : order.status === 'pending_approval'
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                      : order.status === 'cancellation_requested'
                      ? 'bg-amber-500/20 text-amber-200 border border-amber-400/40'
                      : order.status === 'refunded'
                      ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                      : order.status === 'cancelled' || order.status === 'rejected'
                      ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                      : 'bg-gray-500/20 text-gray-300 border border-gray-500/30'
                  }`}
                >
                  {order.status === 'confirmed'
                    ? 'Confirmée'
                    : order.status === 'pending_approval'
                    ? 'À valider'
                    : order.status === 'cancellation_requested'
                    ? 'Annulation demandée'
                    : order.status === 'refunded'
                    ? 'Remboursée'
                    : order.status === 'cancelled'
                    ? 'Annulée'
                    : order.status === 'rejected'
                    ? 'Refusée'
                    : order.status}
                </span>
              </div>
              <h2 id="slide-over-title" className="text-lg font-black text-white mt-1">
                Fiche Inscription : {order.full_name}
              </h2>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded-xl text-gray-400 hover:text-white hover:bg-white/10 transition"
              title="Fermer la fiche (Échap)"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body Content (Scrollable) */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-gray-50/50">
            {/* Action Bar: PDF & Email Resend */}
            <div className="bg-white p-4 rounded-2xl border border-gray-200 shadow-xs space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-gray-500 flex items-center gap-1.5">
                  <FileText className="w-4 h-4 text-emerald-600" />
                  <span>Attestation sur l'honneur (Art. L. 310-2)</span>
                </span>
                {order.honor_declaration_accepted ? (
                  <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
                    Acceptée {order.honor_declaration_accepted_at ? `le ${formatDateTime(order.honor_declaration_accepted_at)}` : ''}
                  </span>
                ) : (
                  <span className="text-[11px] font-bold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-md border border-amber-200">
                    Non acceptée
                  </span>
                )}
              </div>

              {resendSuccess && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs font-semibold text-emerald-800 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>{resendSuccess}</span>
                </div>
              )}

              {resendError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs font-semibold text-red-800 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
                  <span>{resendError}</span>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
                {/* Download PDF Button */}
                {isConfirmed ? (
                  <a
                    href={getAdminAttestationPdfUrl(event.slug || event.id, order.id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-full inline-flex items-center justify-center gap-2 px-3.5 py-2.5 bg-gray-100 hover:bg-gray-200 text-gray-800 text-xs font-bold rounded-xl border border-gray-200 shadow-sm transition"
                  >
                    <ExternalLink className="w-4 h-4 text-gray-600" />
                    <span>Télécharger l'attestation PDF</span>
                  </a>
                ) : (
                  <div
                    className="w-full inline-flex items-center justify-center gap-2 px-3.5 py-2.5 bg-gray-50 text-gray-400 text-xs font-semibold rounded-xl border border-gray-200 cursor-not-allowed"
                    title="L'attestation n'est disponible que pour les commandes confirmées."
                  >
                    <FileText className="w-4 h-4 opacity-50" />
                    <span>Attestation non disponible</span>
                  </div>
                )}

                {/* Resend Email Button */}
                <button
                  type="button"
                  onClick={handleResendAttestation}
                  disabled={!isConfirmed || !order.email || resendingAttestation}
                  title={
                    !isConfirmed
                      ? "L'attestation ne peut être expédiée que pour une commande confirmée."
                      : !order.email
                      ? 'Renseignez une adresse e-mail ci-dessous pour pouvoir réexpédier.'
                      : 'Régénère le PDF en mémoire et expédie un e-mail avec pièce jointe.'
                  }
                  className={`w-full inline-flex items-center justify-center gap-2 px-3.5 py-2.5 text-xs font-bold rounded-xl shadow-xs transition ${
                    isConfirmed && order.email
                      ? 'bg-emerald-600 hover:bg-emerald-700 text-white cursor-pointer'
                      : 'bg-gray-100 text-gray-400 border border-gray-200 cursor-not-allowed'
                  }`}
                >
                  {resendingAttestation ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Génération & Envoi...</span>
                    </>
                  ) : (
                    <>
                      <Send className="w-4 h-4" />
                      <span>Renvoyer l'attestation par e-mail</span>
                    </>
                  )}
                </button>
              </div>

              {!order.email && isConfirmed && (
                <p className="text-[11px] text-amber-700 bg-amber-50 p-2 rounded-lg border border-amber-200">
                  💡 Inscription sans adresse e-mail. Renseignez l'e-mail dans le formulaire ci-dessous et enregistrez pour activer la réexpédition.
                </p>
              )}
            </div>

            {/* Editable Contact Information Form */}
            <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-xs space-y-4">
              <div className="flex items-center justify-between border-b border-gray-100 pb-3">
                <span className="text-xs font-bold uppercase tracking-wider text-gray-500 flex items-center gap-1.5">
                  <User className="w-4 h-4 text-emerald-600" />
                  <span>Coordonnées de l'exposant</span>
                </span>
                <span className="text-[11px] text-gray-400">Modifiable par l'organisateur</span>
              </div>

              {contactSuccess && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs font-semibold text-emerald-800 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>{contactSuccess}</span>
                </div>
              )}

              {contactError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs font-semibold text-red-800 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
                  <span>{contactError}</span>
                </div>
              )}

              <form onSubmit={handleSaveContact} className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-gray-700 mb-1">Prénom *</label>
                    <input
                      type="text"
                      required
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs sm:text-sm focus:bg-white focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition"
                      placeholder="Prénom"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-gray-700 mb-1">Nom *</label>
                    <input
                      type="text"
                      required
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs sm:text-sm focus:bg-white focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition"
                      placeholder="Nom de famille"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-gray-700 mb-1">
                      Adresse e-mail
                      <span className="text-[10px] text-gray-400 font-normal ml-1">(Format RFC)</span>
                    </label>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs sm:text-sm focus:bg-white focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition"
                      placeholder="exposant@exemple.fr"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-gray-700 mb-1">
                      Téléphone *
                      <span className="text-[10px] text-gray-400 font-normal ml-1">(8-15 chiffres)</span>
                    </label>
                    <input
                      type="tel"
                      required
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs sm:text-sm focus:bg-white focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition"
                      placeholder="06 12 34 56 78"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">Adresse postale</label>
                  <input
                    type="text"
                    value={streetAddress}
                    onChange={(e) => setStreetAddress(e.target.value)}
                    className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs sm:text-sm focus:bg-white focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition"
                    placeholder="Numéro et nom de rue"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-gray-700 mb-1">Code postal</label>
                    <input
                      type="text"
                      value={postalCode}
                      onChange={(e) => setPostalCode(e.target.value)}
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs sm:text-sm focus:bg-white focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition"
                      placeholder="Code postal (ex: 35000)"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-gray-700 mb-1">Ville</label>
                    <input
                      type="text"
                      value={city}
                      onChange={(e) => setCity(e.target.value)}
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs sm:text-sm focus:bg-white focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition"
                      placeholder="Ville"
                    />
                  </div>
                </div>

                <div className="pt-2 flex justify-end">
                  <button
                    type="submit"
                    disabled={savingContact}
                    className="inline-flex items-center gap-1.5 px-4 py-2 bg-gray-900 hover:bg-black text-white text-xs font-bold rounded-xl shadow-sm transition disabled:opacity-50"
                  >
                    {savingContact ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Enregistrement...</span>
                      </>
                    ) : (
                      <>
                        <Save className="w-3.5 h-3.5" />
                        <span>Enregistrer les coordonnées</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>

            {/* Stands & Financials Summary (Strictly immutable from here) */}
            <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-xs space-y-3">
              <div className="flex items-center justify-between border-b border-gray-100 pb-3">
                <span className="text-xs font-bold uppercase tracking-wider text-gray-500 flex items-center gap-1.5">
                  <CreditCard className="w-4 h-4 text-emerald-600" />
                  <span>Stands réservés & Règlement</span>
                </span>
                <span className="text-[11px] font-bold text-gray-500">
                  {order.total_price.toFixed(2)} €
                </span>
              </div>

              {/* Spot Pills & Linear Meters */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-semibold text-gray-500">
                    Emplacement(s) attribué(s) :
                  </label>
                  {totalLinearMeters > 0 && (
                    <span className="text-[11px] font-bold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
                      Total : {totalLinearMeters} m
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {order.items && order.items.length > 0 ? (
                    order.items.map((it) => (
                      <span
                        key={it.id || it.spot_id}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-emerald-50 border border-emerald-200 text-emerald-800 font-extrabold text-xs rounded-lg shadow-sm"
                      >
                        <span>Stand {it.spot_label || '—'}</span>
                        {it.spot_linear_meters ? (
                          <span className="text-[10px] text-emerald-600 font-semibold">({it.spot_linear_meters}m)</span>
                        ) : null}
                      </span>
                    ))
                  ) : order.spot_labels && order.spot_labels.length > 0 ? (
                    order.spot_labels.map((lbl) => (
                      <span
                        key={lbl}
                        className="px-2.5 py-1 bg-emerald-50 border border-emerald-200 text-emerald-800 font-extrabold text-xs rounded-lg shadow-sm"
                      >
                        Stand {lbl}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-gray-400 italic">Aucun stand attribué</span>
                  )}
                </div>
              </div>

              {/* Financial & Payment details */}
              <div className="grid grid-cols-2 gap-3 pt-2 text-xs">
                <div className="p-3 bg-gray-50 rounded-xl border border-gray-100">
                  <div className="text-gray-400 text-[11px] uppercase font-bold">Paiement</div>
                  <div className="font-bold text-gray-800 mt-0.5 capitalize">
                    {order.payment_method === 'stripe'
                      ? 'Carte bancaire (En ligne)'
                      : order.payment_method === 'cash'
                      ? 'Espèces (Guichet)'
                      : order.payment_method === 'check'
                      ? 'Chèque (Guichet)'
                      : order.payment_method}
                  </div>
                  {order.offline_payment_reference && (
                    <div className="text-gray-500 text-[11px] mt-0.5">
                      Réf: {order.offline_payment_reference}
                    </div>
                  )}
                </div>

                <div className="p-3 bg-gray-50 rounded-xl border border-gray-100">
                  <div className="text-gray-400 text-[11px] uppercase font-bold">Date de dossier</div>
                  <div className="font-bold text-gray-800 mt-0.5">
                    {formatDateTime(order.created_at)}
                  </div>
                  <div className="text-gray-400 text-[11px] mt-0.5">
                    Mise à jour : {formatDateTime(order.updated_at)}
                  </div>
                </div>
              </div>

              {/* Cancellation Request details if present */}
              {order.cancellation_reason && (
                <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl text-xs space-y-1">
                  <div className="font-bold text-amber-900 flex items-center gap-1.5">
                    <AlertCircle className="w-4 h-4 text-amber-600" />
                    <span>Demande d'annulation soumise</span>
                  </div>
                  <div className="text-amber-800">
                    <strong>Motif :</strong> {getCancellationReasonLabel(order.cancellation_reason)}
                  </div>
                  {order.cancellation_comment && (
                    <div className="text-amber-700 italic">
                      « {order.cancellation_comment} »
                    </div>
                  )}
                  {order.cancellation_requested_at && (
                    <div className="text-amber-600 text-[11px]">
                      Demandée le : {formatDateTime(order.cancellation_requested_at)}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Private Internal Notes Block */}
            <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-xs space-y-3">
              <div className="flex items-center justify-between border-b border-gray-100 pb-3">
                <div className="flex items-center gap-1.5">
                  <Lock className="w-4 h-4 text-indigo-600" />
                  <span className="text-xs font-bold uppercase tracking-wider text-gray-700">
                    Notes & Annotations internes
                  </span>
                </div>
                <span className="text-[10px] font-bold text-indigo-700 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded-full">
                  Privé organisateurs
                </span>
              </div>

              <p className="text-[11px] text-gray-500">
                Ces notes sont strictement confidentielles et ne sont jamais visibles par l'exposant sur sa confirmation ou ses attestations.
              </p>

              {notesSuccess && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs font-semibold text-emerald-800 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>{notesSuccess}</span>
                </div>
              )}

              {notesError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs font-semibold text-red-800 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
                  <span>{notesError}</span>
                </div>
              )}

              <div>
                <textarea
                  rows={4}
                  maxLength={5000}
                  value={adminNotes}
                  onChange={(e) => setAdminNotes(e.target.value)}
                  placeholder="Ajoutez des consignes d'équipe, un statut de paiement différé, un rappel téléphonique..."
                  className="w-full px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-xs sm:text-sm focus:bg-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition resize-y"
                />
                <div className="flex items-center justify-between mt-1 text-[11px] text-gray-400">
                  <span>Sauvegardé directement dans la fiche</span>
                  <span>{adminNotes.length} / 5000 caractères</span>
                </div>
              </div>

              <div className="flex justify-end pt-1">
                <button
                  type="button"
                  onClick={handleSaveNotes}
                  disabled={savingNotes}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-xs transition disabled:opacity-50"
                >
                  {savingNotes ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Enregistrement...</span>
                    </>
                  ) : (
                    <>
                      <Save className="w-3.5 h-3.5" />
                      <span>Enregistrer la note</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Email Communications Audit Trail */}
            <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-xs space-y-3">
              <div className="flex items-center justify-between border-b border-gray-100 pb-3">
                <div className="flex items-center gap-1.5">
                  <Mail className="w-4 h-4 text-emerald-600" />
                  <span className="text-xs font-bold uppercase tracking-wider text-gray-700">
                    Historique des e-mails expédiés
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => loadEmailLogs(order.id)}
                  className="p-1 text-gray-400 hover:text-gray-700 rounded-md transition"
                  title="Rafraîchir les logs d'e-mails"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loadingLogs ? 'animate-spin text-emerald-600' : ''}`} />
                </button>
              </div>

              {logsError && (
                <div className="text-xs text-red-600 bg-red-50 p-2.5 rounded-lg border border-red-200">
                  {logsError}
                </div>
              )}

              {loadingLogs && emailLogs.length === 0 ? (
                <div className="py-6 text-center text-gray-400 text-xs flex items-center justify-center gap-2">
                  <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
                  <span>Chargement des communications...</span>
                </div>
              ) : emailLogs.length === 0 ? (
                <div className="py-6 text-center text-gray-400 text-xs">
                  Aucun e-mail consigné pour cette inscription.
                </div>
              ) : (
                <div className="divide-y divide-gray-100 -mx-2">
                  {emailLogs.map((log) => (
                    <div key={log.id} className="p-2.5 hover:bg-gray-50 rounded-xl transition text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-gray-900 truncate max-w-[260px]" title={log.subject}>
                          {log.subject}
                        </span>
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            log.status === 'sent'
                              ? 'bg-emerald-100 text-emerald-800'
                              : log.status === 'simulated'
                              ? 'bg-blue-100 text-blue-800'
                              : 'bg-red-100 text-red-800'
                          }`}
                        >
                          {log.status === 'sent'
                            ? 'Envoyé'
                            : log.status === 'simulated'
                            ? 'Simulé'
                            : 'Échoué'}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-[11px] text-gray-500">
                        <span>
                          Type : <strong className="text-gray-700">{log.email_type}</strong> &bull; {log.recipient}
                        </span>
                        <span>{formatDateTime(log.created_at)}</span>
                      </div>
                      {log.error_message && (
                        <div className="text-[10px] text-red-600 bg-red-50 p-1.5 rounded">
                          Erreur : {log.error_message}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="p-4 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
            <span className="text-xs text-gray-500 font-mono">
              ID: {order.id.slice(0, 8)}...
            </span>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-white hover:bg-gray-100 text-gray-800 text-xs font-bold rounded-xl border border-gray-200 shadow-sm transition"
            >
              Fermer la fiche
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
