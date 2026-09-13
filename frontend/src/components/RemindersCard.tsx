import React, { useState, useEffect } from 'react';
import { Bell, CheckCircle2, AlertCircle, RefreshCw, Send, Sparkles } from 'lucide-react';
import { ReminderStatus, ReminderTriggerReport } from '../types/reminder';
import { fetchEventReminderStatus, triggerEventReminders } from '../lib/api';

interface RemindersCardProps {
  eventIdOrSlug: string;
}

export const RemindersCard: React.FC<RemindersCardProps> = ({ eventIdOrSlug }) => {
  const [status, setStatus] = useState<ReminderStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [triggeringType, setTriggeringType] = useState<string | null>(null);
  const [report, setReport] = useState<ReminderTriggerReport | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadStatus = async () => {
    try {
      setLoading(true);
      setErrorMessage(null);
      const data = await fetchEventReminderStatus(eventIdOrSlug);
      setStatus(data);
    } catch (err: any) {
      setErrorMessage(err.message || 'Impossible de charger le statut des rappels');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, [eventIdOrSlug]);

  const handleTrigger = async (reminderType: 'j7' | 'j2') => {
    const label = reminderType.toUpperCase();
    const confirmed = window.confirm(
      `Confirmez-vous l'envoi des rappels ${label} aux exposants confirmés ?\n(Garantie 0 doublon : les exposants ayant déjà reçu ce rappel seront ignorés).`
    );
    if (!confirmed) return;

    try {
      setTriggeringType(reminderType);
      setReport(null);
      setErrorMessage(null);
      const res = await triggerEventReminders(eventIdOrSlug, reminderType, false);
      setReport(res);
      await loadStatus();
    } catch (err: any) {
      setErrorMessage(err.message || "Erreur lors de l'envoi des rappels");
    } finally {
      setTriggeringType(null);
    }
  };

  if (loading && !status) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm animate-pulse flex items-center justify-between">
        <div className="h-4 bg-gray-200 rounded w-1/3"></div>
        <div className="h-8 bg-gray-200 rounded w-24"></div>
      </div>
    );
  }

  if (!status) return null;

  const getDaysBadge = () => {
    if (status.days_until_event > 1) {
      return `J-${Math.round(status.days_until_event)}`;
    }
    if (status.days_until_event >= 0) {
      return 'Jour J !';
    }
    return 'Événement passé';
  };

  return (
    <div className="bg-gradient-to-r from-slate-50 to-emerald-50/40 rounded-xl border border-emerald-100/80 p-5 shadow-sm mb-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-emerald-100/80 text-emerald-700 rounded-lg shrink-0 mt-0.5">
            <Bell className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-gray-900">Rappels Automatiques (J-7 & J-2)</h3>
              <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-white text-gray-600 border border-gray-200">
                {getDaysBadge()}
              </span>
            </div>
            <p className="text-xs text-gray-600 mt-1">
              Envoi automatique des consignes d'arrivée, de déchargement et du rappel des pièces d'identité obligatoires.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <button
            onClick={loadStatus}
            disabled={loading}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-white rounded-lg transition-colors border border-transparent hover:border-gray-200"
            title="Rafraîchir"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>

          {/* J-7 button */}
          <button
            onClick={() => handleTrigger('j7')}
            disabled={triggeringType !== null || status.total_confirmed_with_email === 0}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all shadow-sm ${
              status.j7_sent_count > 0
                ? 'bg-white text-emerald-700 border border-emerald-300 hover:bg-emerald-50'
                : status.j7_eligible
                ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
            }`}
          >
            <Send className="w-3.5 h-3.5" />
            {triggeringType === 'j7' ? 'Envoi...' : status.j7_sent_count > 0 ? `Rappel J-7 (${status.j7_sent_count})` : 'Envoyer J-7'}
          </button>

          {/* J-2 button */}
          <button
            onClick={() => handleTrigger('j2')}
            disabled={triggeringType !== null || status.total_confirmed_with_email === 0}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all shadow-sm ${
              status.j2_sent_count > 0
                ? 'bg-white text-amber-700 border border-amber-300 hover:bg-amber-50'
                : status.j2_eligible
                ? 'bg-amber-600 text-white hover:bg-amber-700'
                : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            {triggeringType === 'j2' ? 'Envoi...' : status.j2_sent_count > 0 ? `Rappel J-2 (${status.j2_sent_count})` : 'Envoyer J-2'}
          </button>
        </div>
      </div>

      {/* Status details bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 pt-3 border-t border-emerald-100/60 text-xs">
        <div className="bg-white/70 rounded-lg p-2 border border-gray-100">
          <span className="text-gray-500 block">Exposants confirmés</span>
          <span className="font-bold text-gray-900">
            {status.total_confirmed_orders} ({status.total_confirmed_with_email} avec email)
          </span>
        </div>
        <div className="bg-white/70 rounded-lg p-2 border border-gray-100">
          <span className="text-gray-500 block">Échéance J-7</span>
          <span className="font-semibold text-gray-800 flex items-center gap-1">
            {status.j7_sent_count > 0 ? (
              <span className="text-emerald-700 flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                {status.j7_sent_count} envoyé{status.j7_sent_count > 1 ? 's' : ''}
              </span>
            ) : status.j7_eligible ? (
              <span className="text-emerald-600 font-bold">Fenêtre active</span>
            ) : status.days_until_event < 2.5 ? (
              <span className="text-gray-400">Échéance dépassée</span>
            ) : (
              <span className="text-gray-400">Non atteinte</span>
            )}
          </span>
        </div>
        <div className="bg-white/70 rounded-lg p-2 border border-gray-100">
          <span className="text-gray-500 block">Échéance J-2</span>
          <span className="font-semibold text-gray-800 flex items-center gap-1">
            {status.j2_sent_count > 0 ? (
              <span className="text-amber-700 flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5 text-amber-600" />
                {status.j2_sent_count} envoyé{status.j2_sent_count > 1 ? 's' : ''}
              </span>
            ) : status.j2_eligible ? (
              <span className="text-amber-600 font-bold">Fenêtre active</span>
            ) : status.days_until_event < 0 ? (
              <span className="text-gray-400">Échéance dépassée</span>
            ) : (
              <span className="text-gray-400">Non atteinte</span>
            )}
          </span>
        </div>
        <div className="bg-white/70 rounded-lg p-2 border border-gray-100">
          <span className="text-gray-500 block">Idempotence</span>
          <span className="text-gray-600 font-medium">Garantie 0 doublon</span>
        </div>
      </div>

      {/* Trigger report notification */}
      {report && (
        <div className="mt-3 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <div>
              <strong>Rapport d'exécution :</strong> {report.reminders_sent} rappel(s) envoyé(s),{' '}
              {report.reminders_skipped} déjà reçu(s) (ignoré(s)), {report.orders_without_email} sans email.
            </div>
            <button onClick={() => setReport(null)} className="text-emerald-700 font-bold hover:text-emerald-900 ml-2">
              ✕
            </button>
          </div>
          {report.errors && report.errors.length > 0 && (
            <div className="text-red-700 mt-1 pl-2 border-l-2 border-red-400">
              {report.errors.map((err, idx) => (
                <div key={idx}>⚠️ {err}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {errorMessage && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
};
