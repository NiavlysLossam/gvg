import React, { useState, useEffect, useRef } from 'react';
import {
  X,
  Send,
  Eye,
  Edit3,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Mail,
  Users,
  Sparkles,
} from 'lucide-react';
import { EventModel } from '../types/event';
import { AdminOrder } from '../types/order';
import {
  BroadcastPreviewResponse,
  BroadcastSendResponse,
  AVAILABLE_DYNAMIC_TAGS,
} from '../types/broadcast';
import { previewBroadcastEmail, sendBroadcastEmail, ApiError } from '../lib/api';

interface BroadcastModalProps {
  isOpen: boolean;
  onClose: () => void;
  event: EventModel;
  totalConfirmedCount: number;
  selectedOrders?: AdminOrder[];
  onSuccess: (report: BroadcastSendResponse) => void;
}

export const BroadcastModal: React.FC<BroadcastModalProps> = ({
  isOpen,
  onClose,
  event,
  totalConfirmedCount,
  selectedOrders = [],
  onSuccess,
}) => {
  const [activeTab, setActiveTab] = useState<'edit' | 'preview'>('edit');
  const [targetAudience, setTargetAudience] = useState<'all_confirmed' | 'selected'>(
    selectedOrders.length > 0 ? 'selected' : 'all_confirmed'
  );

  // Form inputs
  const [subject, setSubject] = useState<string>('');
  const [body, setBody] = useState<string>('');
  const [isTestMode, setIsTestMode] = useState<boolean>(false);
  const [testRecipient, setTestRecipient] = useState<string>(event.organizer_email || '');

  // Live preview state
  const [previewData, setPreviewData] = useState<BroadcastPreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState<boolean>(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewMode, setPreviewMode] = useState<'html' | 'text'>('html');

  // Confirmation dialog step
  const [showConfirmStep, setShowConfirmStep] = useState<boolean>(false);
  const [sending, setSending] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [testSuccessMessage, setTestSuccessMessage] = useState<string | null>(null);

  // Input refs for cursor tag insertion
  const bodyTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const subjectInputRef = useRef<HTMLInputElement | null>(null);
  const lastFocusedInputRef = useRef<'subject' | 'body'>('body');

  useEffect(() => {
    if (!isOpen) return;

    setError(null);
    setTestSuccessMessage(null);
    setShowConfirmStep(false);
    setSending(false);
    setActiveTab('edit');
    setTargetAudience(selectedOrders.length > 0 ? 'selected' : 'all_confirmed');
    if (!subject) {
      setSubject(`[${event.title}] Consignes importantes pour votre stand`);
    }
    if (!body) {
      setBody(
        `Bonjour {{exposant.prenom}},\n\nNous vous transmettons les dernières informations concernant votre emplacement {{commande.emplacements}} pour {{evenement.titre}} le {{evenement.date}}.\n\nMerci de bien vouloir vous présenter dès l'ouverture avec votre pièce d'identité.\n\nCordialement,\nL'organisateur`
      );
    }
    if (!testRecipient && event.organizer_email) {
      setTestRecipient(event.organizer_email);
    }
  }, [isOpen, selectedOrders.length, event]);

  const targetCount =
    targetAudience === 'selected' ? selectedOrders.length : totalConfirmedCount;

  // Fetch live preview when switching to the preview tab
  useEffect(() => {
    if (activeTab !== 'preview' || !isOpen) return;

    let isMounted = true;
    setPreviewLoading(true);
    setPreviewError(null);

    previewBroadcastEmail(event.id, {
      subject: subject.trim() || 'Sans objet',
      body: body.trim() || 'Sans contenu',
      order_id: selectedOrders.length > 0 ? selectedOrders[0].id : undefined,
    })
      .then((data) => {
        if (isMounted) {
          setPreviewData(data);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setPreviewError(
            err instanceof ApiError ? String(err.detail) : 'Erreur de prévisualisation'
          );
        }
      })
      .finally(() => {
        if (isMounted) {
          setPreviewLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [activeTab, isOpen, event.id, subject, body, selectedOrders]);

  if (!isOpen) return null;

  const insertTag = (tag: string) => {
    if (lastFocusedInputRef.current === 'subject' && subjectInputRef.current) {
      const input = subjectInputRef.current;
      const start = input.selectionStart ?? subject.length;
      const end = input.selectionEnd ?? subject.length;
      const updated = subject.slice(0, start) + tag + subject.slice(end);
      setSubject(updated);
      setTimeout(() => {
        input.focus();
        input.setSelectionRange(start + tag.length, start + tag.length);
      }, 10);
    } else if (bodyTextareaRef.current) {
      const textarea = bodyTextareaRef.current;
      const start = textarea.selectionStart ?? body.length;
      const end = textarea.selectionEnd ?? body.length;
      const updated = body.slice(0, start) + tag + body.slice(end);
      setBody(updated);
      setTimeout(() => {
        textarea.focus();
        textarea.setSelectionRange(start + tag.length, start + tag.length);
      }, 10);
    } else {
      setBody((prev) => `${prev} ${tag}`);
    }
  };

  const handleStartSend = () => {
    if (!subject.trim()) {
      setError("Veuillez saisir un objet pour l'e-mail.");
      return;
    }
    if (!body.trim()) {
      setError("Veuillez rédiger le corps de l'e-mail.");
      return;
    }
    if (isTestMode) {
      if (!testRecipient.trim() || !testRecipient.includes('@')) {
        setError('Veuillez saisir une adresse e-mail valide pour le test.');
        return;
      }
      // Execute test send directly
      executeSend();
    } else {
      if (targetCount === 0) {
        setError('Aucun exposant confirmé ne correspond à cette sélection.');
        return;
      }
      setError(null);
      setShowConfirmStep(true);
    }
  };

  const executeSend = async () => {
    setSending(true);
    setError(null);
    setTestSuccessMessage(null);

    try {
      const payload = {
        subject: subject.trim(),
        body: body.trim(),
        target_audience: targetAudience,
        selected_order_ids:
          targetAudience === 'selected' ? selectedOrders.map((o) => o.id) : undefined,
        is_test: isTestMode,
        test_recipient: isTestMode ? testRecipient.trim() : undefined,
      };

      const res = await sendBroadcastEmail(event.id, payload);
      if (isTestMode) {
        setTestSuccessMessage(
          `E-mail de test envoyé avec succès à ${testRecipient.trim()}.`
        );
      } else {
        onSuccess(res);
        onClose();
      }
    } catch (err) {
      setError(
        err instanceof ApiError ? String(err.detail) : "Erreur lors de l'envoi de la diffusion."
      );
      setShowConfirmStep(false);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 sm:p-6 backdrop-blur-xs overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-xl border border-gray-100 w-full max-w-3xl overflow-hidden my-auto animate-in fade-in zoom-in duration-200 flex flex-col max-h-[92vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-emerald-700 text-white">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white/10 rounded-xl">
              <Mail className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-bold text-base leading-tight">Diffuser un e-mail aux exposants</h2>
              <p className="text-xs text-emerald-100">
                {event.title} &bull; {totalConfirmedCount} inscrit(s) confirmé(s)
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={sending}
            className="text-white/80 hover:text-white p-1 rounded-lg hover:bg-white/10 transition disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation Tabs */}
        <div className="px-6 pt-3 pb-0 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setActiveTab('edit')}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-bold border-b-2 transition ${
                activeTab === 'edit'
                  ? 'border-emerald-600 text-emerald-700 bg-white rounded-t-lg shadow-xs'
                  : 'border-transparent text-gray-500 hover:text-gray-900'
              }`}
            >
              <Edit3 className="w-4 h-4" />
              <span>Rédiger le message</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('preview')}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-bold border-b-2 transition ${
                activeTab === 'preview'
                  ? 'border-emerald-600 text-emerald-700 bg-white rounded-t-lg shadow-xs'
                  : 'border-transparent text-gray-500 hover:text-gray-900'
              }`}
            >
              <Eye className="w-4 h-4" />
              <span>Aperçu dynamique en direct</span>
            </button>
          </div>

          <div className="text-[11px] text-gray-500 font-medium hidden sm:block">
            Variables dynamiques supportées
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {error && (
            <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl flex items-start gap-2 text-red-800 text-xs">
              <AlertTriangle className="w-4 h-4 text-red-600 mt-0.5 shrink-0" />
              <div className="flex-1">{error}</div>
            </div>
          )}

          {testSuccessMessage && (
            <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl flex items-start gap-2 text-emerald-800 text-xs">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
              <div className="flex-1">{testSuccessMessage}</div>
            </div>
          )}

          {/* TAB 1: EDIT */}
          {activeTab === 'edit' && (
            <>
              {/* Audience Selector */}
              <div className="bg-gray-50/80 border border-gray-200 rounded-xl p-3.5 space-y-2">
                <div className="text-xs font-bold text-gray-700 flex items-center gap-1.5">
                  <Users className="w-4 h-4 text-emerald-600" />
                  <span>Destinataires ciblés</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                  <label
                    className={`flex items-center gap-2.5 p-2.5 rounded-lg border cursor-pointer transition ${
                      targetAudience === 'all_confirmed'
                        ? 'bg-emerald-50/60 border-emerald-300 text-emerald-900 font-bold'
                        : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <input
                      type="radio"
                      name="audience"
                      value="all_confirmed"
                      checked={targetAudience === 'all_confirmed'}
                      onChange={() => setTargetAudience('all_confirmed')}
                      className="text-emerald-600 focus:ring-emerald-500"
                    />
                    <span>Tous les confirmés ({totalConfirmedCount})</span>
                  </label>

                  <label
                    className={`flex items-center gap-2.5 p-2.5 rounded-lg border transition ${
                      selectedOrders.length === 0
                        ? 'opacity-50 cursor-not-allowed bg-gray-100 border-gray-200 text-gray-400'
                        : targetAudience === 'selected'
                        ? 'bg-emerald-50/60 border-emerald-300 text-emerald-900 font-bold cursor-pointer'
                        : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-100 cursor-pointer'
                    }`}
                  >
                    <input
                      type="radio"
                      name="audience"
                      value="selected"
                      checked={targetAudience === 'selected'}
                      disabled={selectedOrders.length === 0}
                      onChange={() => setTargetAudience('selected')}
                      className="text-emerald-600 focus:ring-emerald-500"
                    />
                    <span>
                      Sélection courante du tableau ({selectedOrders.length} sélectionné{selectedOrders.length > 1 ? 's' : ''})
                    </span>
                  </label>
                </div>
              </div>

              {/* Dynamic Variables Badges */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-gray-700 flex items-center gap-1">
                    <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                    Insérer une variable dynamique (cliquez pour insérer) :
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {AVAILABLE_DYNAMIC_TAGS.map((tagItem) => (
                    <button
                      key={tagItem.tag}
                      type="button"
                      onClick={() => insertTag(tagItem.tag)}
                      className="px-2.5 py-1 text-xs font-mono font-semibold bg-gray-100 hover:bg-emerald-50 hover:text-emerald-700 hover:border-emerald-300 text-gray-700 border border-gray-200 rounded-md transition shadow-2xs"
                      title={`${tagItem.description} (Ex: ${tagItem.example})`}
                    >
                      {tagItem.tag}
                    </button>
                  ))}
                </div>
              </div>

              {/* Subject Input */}
              <div className="space-y-1">
                <label className="block text-xs font-bold text-gray-700">
                  Objet de l'e-mail <span className="text-red-500">*</span>
                </label>
                <input
                  ref={subjectInputRef}
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  onFocus={() => {
                    lastFocusedInputRef.current = 'subject';
                  }}
                  placeholder="Ex: [Vide-Grenier] Alerte météo et rappel des accès"
                  className="w-full text-xs sm:text-sm px-3.5 py-2.5 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                />
              </div>

              {/* Message Body Textarea */}
              <div className="space-y-1">
                <label className="block text-xs font-bold text-gray-700">
                  Corps du message <span className="text-red-500">*</span>
                </label>
                <textarea
                  ref={bodyTextareaRef}
                  rows={9}
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  onFocus={() => {
                    lastFocusedInputRef.current = 'body';
                  }}
                  placeholder="Rédigez votre message ici. Les balises {{exposant.prenom}}, {{commande.emplacements}}, etc. seront remplacées par les données réelles de chaque exposant."
                  className="w-full text-xs sm:text-sm px-3.5 py-2.5 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 font-sans leading-relaxed"
                />
              </div>

              {/* Test Mode Card */}
              <div className="p-3.5 bg-amber-50/70 border border-amber-200 rounded-xl space-y-2">
                <label className="flex items-center gap-2 text-xs font-bold text-amber-900 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isTestMode}
                    onChange={(e) => setIsTestMode(e.target.checked)}
                    className="rounded text-amber-600 focus:ring-amber-500 h-4 w-4"
                  />
                  <span>Mode Test : envoyer un e-mail de validation préalable uniquement à moi</span>
                </label>

                {isTestMode && (
                  <div className="pt-1 flex items-center gap-2">
                    <input
                      type="email"
                      value={testRecipient}
                      onChange={(e) => setTestRecipient(e.target.value)}
                      placeholder="votre-email@organisateur.fr"
                      className="flex-1 text-xs px-3 py-1.5 bg-white border border-amber-300 rounded-lg focus:ring-1 focus:ring-amber-500"
                    />
                    <span className="text-[11px] text-amber-700 shrink-0">
                      (Aucun exposant ne sera notifié)
                    </span>
                  </div>
                )}
              </div>
            </>
          )}

          {/* TAB 2: LIVE PREVIEW */}
          {activeTab === 'preview' && (
            <div className="space-y-4">
              {previewLoading ? (
                <div className="py-16 text-center text-gray-500 space-y-2">
                  <RefreshCw className="w-7 h-7 animate-spin mx-auto text-emerald-600" />
                  <p className="text-xs font-medium">Génération de l'aperçu dynamique avec données réelles...</p>
                </div>
              ) : previewError ? (
                <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs">
                  {previewError}
                </div>
              ) : previewData ? (
                <>
                  {/* Sample Data Banner */}
                  <div className="p-3 bg-emerald-50/70 border border-emerald-200 rounded-xl flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2 text-emerald-800">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                      <span>
                        Aperçu simulé pour : <strong>{previewData.sample_exhibitor_name || 'Exposant test'}</strong> &bull; Commande{' '}
                        <strong>{previewData.sample_order_number || 'N/A'}</strong> (Stand{' '}
                        <strong>{previewData.sample_spots || 'N/A'}</strong>)
                      </span>
                    </div>
                    <div className="flex items-center gap-1 text-[11px] font-bold">
                      <button
                        type="button"
                        onClick={() => setPreviewMode('html')}
                        className={`px-2 py-1 rounded transition ${
                          previewMode === 'html'
                            ? 'bg-emerald-600 text-white'
                            : 'bg-white text-gray-600 border border-gray-200'
                        }`}
                      >
                        HTML
                      </button>
                      <button
                        type="button"
                        onClick={() => setPreviewMode('text')}
                        className={`px-2 py-1 rounded transition ${
                          previewMode === 'text'
                            ? 'bg-emerald-600 text-white'
                            : 'bg-white text-gray-600 border border-gray-200'
                        }`}
                      >
                        Texte
                      </button>
                    </div>
                  </div>

                  {/* Rendered Subject */}
                  <div className="p-3 bg-gray-50 border border-gray-200 rounded-xl text-xs space-y-1">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400">
                      Objet évalué :
                    </span>
                    <div className="font-bold text-gray-900 text-sm">
                      {isTestMode ? `[TEST] ${previewData.subject}` : previewData.subject}
                    </div>
                  </div>

                  {/* Rendered Content Frame */}
                  {previewMode === 'html' ? (
                    <div className="border border-gray-200 rounded-xl overflow-hidden bg-gray-100 shadow-inner">
                      <iframe
                        title="HTML Preview"
                        srcDoc={previewData.body_html}
                        className="w-full h-96 bg-white border-0"
                        sandbox="allow-same-origin"
                      />
                    </div>
                  ) : (
                    <div className="border border-gray-200 rounded-xl p-4 bg-gray-50 font-mono text-xs whitespace-pre-wrap text-gray-800 h-96 overflow-y-auto">
                      {previewData.body_text}
                    </div>
                  )}
                </>
              ) : null}
            </div>
          )}

          {/* CONFIRMATION OVERLAY STEP */}
          {showConfirmStep && (
            <div className="p-4 bg-amber-50 border-2 border-amber-300 rounded-xl space-y-3 animate-in fade-in duration-150">
              <div className="flex items-start gap-3">
                <div className="p-2 bg-amber-100 rounded-xl shrink-0">
                  <AlertTriangle className="w-5 h-5 text-amber-700" />
                </div>
                <div className="space-y-1">
                  <h3 className="font-bold text-sm text-amber-900">
                    Confirmer l'expédition générale ?
                  </h3>
                  <p className="text-xs text-amber-800 leading-relaxed">
                    Vous êtes sur le point d'expédier cet e-mail à{' '}
                    <strong>{targetCount} exposant(s)</strong> confirmés. Les e-mails seront envoyés
                    de manière asynchrone en arrière-plan avec les balises personnalisées.
                  </p>
                </div>
              </div>
              <div className="flex items-center justify-end gap-2 pt-2 border-t border-amber-200">
                <button
                  type="button"
                  onClick={() => setShowConfirmStep(false)}
                  disabled={sending}
                  className="px-3 py-1.5 text-xs font-semibold text-gray-700 bg-white hover:bg-gray-100 border border-gray-200 rounded-lg transition"
                >
                  Annuler / Modifier
                </button>
                <button
                  type="button"
                  onClick={executeSend}
                  disabled={sending}
                  className="px-4 py-1.5 text-xs font-bold text-white bg-emerald-700 hover:bg-emerald-800 rounded-lg shadow-sm transition flex items-center gap-1.5 disabled:opacity-50"
                >
                  {sending ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Démarrage...</span>
                    </>
                  ) : (
                    <>
                      <Send className="w-3.5 h-3.5" />
                      <span>Oui, expédier la diffusion</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
          <div className="text-xs text-gray-500">
            {isTestMode ? (
              <span className="text-amber-700 font-semibold">Mode test : 1 destinataire</span>
            ) : (
              <span>
                Cible : <strong>{targetCount}</strong> exposant(s)
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={sending}
              className="px-4 py-2 text-xs font-bold text-gray-700 bg-white hover:bg-gray-100 border border-gray-200 rounded-xl transition disabled:opacity-50"
            >
              Fermer
            </button>

            {!showConfirmStep && (
              <button
                type="button"
                onClick={handleStartSend}
                disabled={sending}
                className={`px-5 py-2 text-xs font-bold text-white rounded-xl shadow-sm transition flex items-center gap-1.5 ${
                  isTestMode
                    ? 'bg-amber-600 hover:bg-amber-700'
                    : 'bg-emerald-600 hover:bg-emerald-700'
                }`}
              >
                {sending ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Traitement...</span>
                  </>
                ) : isTestMode ? (
                  <>
                    <Send className="w-4 h-4" />
                    <span>Envoyer le test</span>
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    <span>Envoyer ({targetCount})</span>
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
